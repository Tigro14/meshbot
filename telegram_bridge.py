#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Telegram bridge pour interface avec le bot Meshtastic
VERSION CORRIGÉE - Toutes les commandes via queue
"""

import asyncio
import logging
import json
import time
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuration
import sys
sys.path.append('/home/dietpi/bot')  # Ajuster selon votre chemin
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_USERS, TELEGRAM_QUEUE_FILE, TELEGRAM_RESPONSE_FILE, TELEGRAM_COMMAND_TIMEOUT, TELEGRAM_AI_CONFIG

# Configuration logging vers systemd uniquement (pas de fichier séparé)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]  # Force vers stdout/stderr pour systemd
)
logger = logging.getLogger(__name__)

class TelegramMeshtasticBridge:
    def __init__(self):
        self.application = None
        self.command_queue = asyncio.Queue()
        self.queue_file = TELEGRAM_QUEUE_FILE
        self.response_file = TELEGRAM_RESPONSE_FILE
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        logger.info(f"Utilisateur {user.username} ({user.id}) démarre le bot")
        
        welcome_msg = (
            f"🤖 Bot Meshtastic Bridge\n\n"
            f"Salut {user.first_name} !\n\n"
            f"Commandes disponibles:\n"
            f"• Tapez directement votre message pour parler à l'IA\n"
            f"• /power - Info batterie/solaire\n"
            f"• /rx [page] - Nœuds vus par tigrog2\n"
            f"• /sys - Info système\n"
            f"• /echo <message> - Diffuser via tigrog2\n"
            f"• /nodes <IP> - Nœuds d'un hôte distant\n"
            f"• /legend - Légende des signaux\n"
            f"• /help - Aide complète\n\n"
            f"Votre ID: {user.id}"
        )
        
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        help_msg = (
            "**Commandes disponibles:**\n\n"
            "**Direct:**\n"
            "• Message direct → Chat IA\n"
            "• `/power` - Batterie/solaire\n"
            "• `/rx [page]` - Nœuds tigrog2\n"
            "• `/sys` - Système Pi5\n"
            "• `/echo <message>` - Diffuser\n"
            "• `/nodes <IP>` - Nœuds distants\n"
            "• `/legend` - Légende signaux\n\n"
            "**Note:** /my n'est pas disponible depuis Telegram"
        )
        
        await update.message.reply_text(help_msg, parse_mode='Markdown')
    
    def check_authorization(self, user_id):
        """Vérifier si l'utilisateur est autorisé"""
        if not TELEGRAM_AUTHORIZED_USERS:
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS
    
    async def power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        try:
            response = await self.send_to_meshtastic("/power", user)
            await update.message.reply_text(f"🔋 **Power:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur /power: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx [page]"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Extraire le numéro de page
        page = context.args[0] if context.args else "1"
        command = f"/rx {page}"
        
        try:
            response = await self.send_to_meshtastic(command, user)
            await update.message.reply_text(f"📡 **Nœuds:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur /rx: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        try:
            response = await self.send_to_meshtastic("/sys", user)
            await update.message.reply_text(f"🖥️ **Système:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur /sys: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        try:
            response = await self.send_to_meshtastic("/legend", user)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Erreur /legend: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /echo <message>\nEx: /echo Salut!")
            return
        
        echo_text = ' '.join(context.args)
        command = f"/echo {echo_text}"
        
        try:
            response = await self.send_to_meshtastic(command, user)
            await update.message.reply_text(f"📡 {response}")
        except Exception as e:
            logger.error(f"Erreur /echo: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def nodes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /nodes <IP>"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /nodes <IP>\nEx: /nodes 192.168.1.38")
            return
        
        remote_host = context.args[0]
        command = f"/nodes {remote_host}"
        
        try:
            response = await self.send_to_meshtastic(command, user)
            await update.message.reply_text(f"📡 **Nœuds distants:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur /nodes: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gérer les messages texte (raccourci pour /bot)"""
        user = update.effective_user
        message_text = update.message.text
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Message direct de {user.username}: {message_text}")
        
        try:
            command = f"/bot {message_text}"
            response = await self.send_to_meshtastic(command, user)
            await update.message.reply_text(f"🤖 {response}")
        except Exception as e:
            logger.error(f"Erreur message: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def send_to_meshtastic(self, command, user):
        """Envoyer une commande au bot Meshtastic via queue"""
        request_id = f"tg_{int(time.time()*1000)}"
        request_data = {
            "id": request_id,
            "command": command,
            "source": "telegram",
            "user": {
                "telegram_id": user.id,
                "username": user.username or user.first_name,
                "first_name": user.first_name
            },
            "timestamp": time.time()
        }
        
        logger.info(f"Envoi commande: {command} (ID: {request_id})")
        
        try:
            # Écrire la requête dans le fichier de queue
            requests = []
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    try:
                        requests = json.load(f)
                    except json.JSONDecodeError:
                        requests = []
            
            requests.append(request_data)
            
            with open(self.queue_file, 'w') as f:
                json.dump(requests, f)
            
            logger.info(f"Requête {request_id} ajoutée à la queue")
            
            # Timeout adapté selon le type de commande
            if command.startswith('/bot '):
                timeout = TELEGRAM_AI_CONFIG["timeout"] + 30
                logger.info(f"Attente réponse IA (timeout: {timeout}s)")
            else:
                timeout = TELEGRAM_COMMAND_TIMEOUT
            
            result = await self.wait_for_response(request_id, timeout=timeout)
            logger.info(f"Réponse reçue: '{result[:100]}...'")
            return result
            
        except Exception as e:
            logger.error(f"Erreur interface: {e}")
            return f"Erreur interface: {str(e)}"
    
    async def wait_for_response(self, request_id, timeout=30):
        """Attendre la réponse du bot Meshtastic"""
        logger.info(f"Attente réponse pour {request_id} (timeout: {timeout}s)")
        start_time = time.time()
        check_interval = 0.5
        
        while (time.time() - start_time) < timeout:
            try:
                if not os.path.exists(self.response_file):
                    await asyncio.sleep(check_interval)
                    continue
                
                with open(self.response_file, 'r') as f:
                    try:
                        responses = json.load(f)
                    except json.JSONDecodeError:
                        await asyncio.sleep(check_interval)
                        continue
                
                if not responses:
                    await asyncio.sleep(check_interval)
                    continue
                
                # Chercher notre réponse
                for i, response in enumerate(responses):
                    if response.get("request_id") == request_id:
                        result = response.get("response", "Pas de réponse")
                        
                        logger.info(f"Réponse trouvée pour {request_id}")
                        
                        # Supprimer la réponse traitée
                        responses.pop(i)
                        with open(self.response_file, 'w') as f:
                            json.dump(responses, f)
                        
                        return result
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Erreur attente: {e}")
                await asyncio.sleep(check_interval)
                continue
        
        logger.warning(f"TIMEOUT après {timeout}s pour {request_id}")
        return f"⏰ Timeout - pas de réponse après {timeout}s"
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs global"""
        logger.error(f"Exception: {context.error}")
        
        if update and hasattr(update, 'message') and update.message:
            await update.message.reply_text("❌ Erreur interne du bot")
    
    async def start_bot(self):
        """Démarrer le bot Telegram"""
        logger.info("Démarrage du bot Telegram Meshtastic Bridge...")
        
        # Créer l'application
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Ajouter les handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("power", self.power_command))
        self.application.add_handler(CommandHandler("rx", self.rx_command))
        self.application.add_handler(CommandHandler("sys", self.sys_command))
        self.application.add_handler(CommandHandler("legend", self.legend_command))
        self.application.add_handler(CommandHandler("echo", self.echo_command))
        self.application.add_handler(CommandHandler("nodes", self.nodes_command))
        
        # Handler pour messages texte (raccourci /bot)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Gestionnaire d'erreurs
        self.application.add_error_handler(self.error_handler)
        
        # Démarrer le bot
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("✅ Bot Telegram démarré et en écoute...")
        
        # Garder le bot actif
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Arrêt du bot...")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

def main():
    """Point d'entrée principal"""
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ Veuillez configurer TELEGRAM_BOT_TOKEN")
        return
    
    bridge = TelegramMeshtasticBridge()
    
    try:
        asyncio.run(bridge.start_bot())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du bot Telegram")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")

if __name__ == "__main__":
    main()
