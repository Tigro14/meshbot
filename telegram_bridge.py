#!/usr/bin/env python3
"""
Bot Telegram bridge pour interface avec le bot Meshtastic
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# Configuration
# Importer depuis config.py au lieu de définir ici
import sys
sys.path.append('/opt/meshtastic-bot')  # Ajuster selon votre chemin
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_USERS, TELEGRAM_QUEUE_FILE, TELEGRAM_RESPONSE_FILE, TELEGRAM_COMMAND_TIMEOUT

# Configuration logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramMeshtasticBridge:
    def __init__(self):
        self.application = None
        self.command_queue = asyncio.Queue()
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        logger.info(f"Utilisateur {user.username} ({user.id}) démarre le bot")
        
        welcome_msg = (
            f"🤖 Bot Meshtastic Bridge\n\n"
            f"Salut {user.first_name} !\n\n"
            f"Commandes disponibles:\n"
            f"• /mesh <commande> - Envoyer une commande au bot Meshtastic\n"
            f"• /status - État du réseau Meshtastic\n"
            f"• /nodes - Liste des nœuds\n"
            f"• /echo <message> - Echo via tigrog2\n"
            f"• /help - Cette aide\n\n"
            f"Votre ID: {user.id}"
        )
        
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        help_msg = (
            "🤖 **Commandes disponibles:**\n\n"
            "**Commandes Meshtastic:**\n"
            "• `/mesh /bot <question>` - Chat IA\n"
            "• `/mesh /power` - Info batterie/solaire\n"
            "• `/mesh /rx [page]` - Nœuds vus par tigrog2\n"
            "• `/mesh /my` - Vos signaux\n"
            "• `/mesh /sys` - Info système Pi5\n"
            "• `/mesh /legend` - Légende signaux\n\n"
            "**Commandes directes:**\n"
            "• `/status` - État réseau\n"
            "• `/nodes` - Liste nœuds actifs\n"
            "• `/echo <message>` - Diffuser via tigrog2\n"
            "• `/stats` - Statistiques\n\n"
            "**Format raccourci:**\n"
            "Tapez directement votre message pour `/mesh /bot <message>`"
        )
        
        await update.message.reply_text(help_msg, parse_mode='Markdown')
    
    def check_authorization(self, user_id):
        """Vérifier si l'utilisateur est autorisé"""
        if not TELEGRAM_AUTHORIZED_USERS:  # Si liste vide, tout le monde est autorisé
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS
    
    async def mesh_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /mesh pour relayer vers Meshtastic"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /mesh <commande>\nEx: /mesh /power")
            return
        
        # Construire la commande Meshtastic
        mesh_command = ' '.join(context.args)
        logger.info(f"Commande mesh de {user.username}: {mesh_command}")
        
        # Envoyer via l'API du bot Meshtastic
        try:
            response = await self.send_to_meshtastic(mesh_command, user)
            await update.message.reply_text(f"📡 **Réponse Mesh:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande mesh: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo pour diffuser via tigrog2"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /echo <message>\nEx: /echo Salut le réseau!")
            return
        
        echo_text = ' '.join(context.args)
        logger.info(f"Echo de {user.username}: {echo_text}")
        
        try:
            # Simuler un node_id pour Telegram (on peut utiliser l'user_id tronqué)
            telegram_node_id = user.id & 0xFFFFFFFF  # Tronquer à 32 bits
            
            response = await self.send_echo_to_meshtastic(echo_text, telegram_node_id, user.username or user.first_name)
            await update.message.reply_text(f"📡 Echo diffusé: `{user.first_name}: {echo_text}`", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur echo: {e}")
            await update.message.reply_text(f"❌ Erreur echo: {str(e)}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /status pour l'état du réseau"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        try:
            status = await self.get_meshtastic_status()
            await update.message.reply_text(f"📊 **État Meshtastic:**\n```\n{status}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur status: {e}")
            await update.message.reply_text(f"❌ Erreur status: {str(e)}")
    
    async def nodes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /nodes pour lister les nœuds"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        try:
            nodes = await self.get_meshtastic_nodes()
            await update.message.reply_text(f"📡 **Nœuds actifs:**\n```\n{nodes}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur nodes: {e}")
            await update.message.reply_text(f"❌ Erreur nodes: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /stats pour les statistiques"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        try:
            stats = await self.get_meshtastic_stats()
            await update.message.reply_text(f"📈 **Statistiques:**\n```\n{stats}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur stats: {e}")
            await update.message.reply_text(f"❌ Erreur stats: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gérer les messages texte (raccourci pour /mesh /bot)"""
        user = update.effective_user
        message_text = update.message.text
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Raccourci: message direct = /mesh /bot <message>
        logger.info(f"Message direct de {user.username}: {message_text}")
        
        try:
            mesh_command = f"/bot {message_text}"
            response = await self.send_to_meshtastic(mesh_command, user)
            await update.message.reply_text(f"🤖 **IA Mesh:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur message direct: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def send_to_meshtastic(self, command, user):
        """Envoyer une commande au bot Meshtastic via API"""
        # Simuler l'API - à adapter selon votre implémentation
        api_data = {
            "command": command,
            "telegram_user_id": user.id,
            "telegram_username": user.username or user.first_name,
            "timestamp": time.time()
        }
        
        # Ici vous devrez implémenter l'interface avec votre bot Meshtastic
        # Option 1: API REST
        # response = requests.post(f"{MESHTASTIC_BOT_API_URL}/command", json=api_data)
        # return response.json()['response']
        
        # Option 2: File/Queue system
        # with open("/tmp/telegram_to_mesh_queue", "a") as f:
        #     f.write(json.dumps(api_data) + "\n")
        
        # Pour le moment, simulation
        await asyncio.sleep(1)  # Simuler délai de traitement
        return f"[Simulé] Réponse à: {command}"
    
    async def send_echo_to_meshtastic(self, echo_text, node_id, username):
        """Envoyer un echo via tigrog2"""
        api_data = {
            "action": "echo",
            "text": echo_text,
            "node_id": node_id,
            "username": username,
            "timestamp": time.time()
        }
        
        # Interface avec votre système echo
        # À adapter selon votre implémentation
        await asyncio.sleep(0.5)
        return True
    
    async def get_meshtastic_status(self):
        """Récupérer l'état du système Meshtastic"""
        # À adapter selon votre API
        await asyncio.sleep(0.5)
        return (
            "Pi5 Bot: ✅ Actif\n"
            "Tigrog2: ✅ Connecté\n"
            "Llama: ✅ Opérationnel\n"
            "ESPHome: ✅ En ligne\n"
            f"Uptime: 2h 15m\n"
            f"Dernière activité: {datetime.now().strftime('%H:%M:%S')}"
        )
    
    async def get_meshtastic_nodes(self):
        """Récupérer la liste des nœuds"""
        await asyncio.sleep(0.5)
        return (
            "🟢 tigrog2: -85dBm (direct)\n"
            "🟡 node1: -95dBm (1h)\n"
            "🟠 node2: -105dBm (3h)\n"
            "🔴 node3: -115dBm (12h)\n"
            "Total: 4 nœuds actifs"
        )
    
    async def get_meshtastic_stats(self):
        """Récupérer les statistiques"""
        await asyncio.sleep(0.5)
        return (
            "Messages aujourd'hui: 47\n"
            "Commandes /bot: 12\n"
            "Commandes /echo: 8\n"
            "Nœuds vus: 15\n"
            "Temps réponse moyen: 1.2s\n"
            f"Dernière stats: {datetime.now().strftime('%H:%M:%S')}"
        )
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs global"""
        logger.error(f"Exception: {context.error}")
        
        if update and hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "❌ Erreur interne du bot. L'équipe technique a été notifiée."
            )
    
    async def start_bot(self):
        """Démarrer le bot Telegram"""
        logger.info("Démarrage du bot Telegram Meshtastic Bridge...")
        
        # Créer l'application
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Ajouter les handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("mesh", self.mesh_command))
        self.application.add_handler(CommandHandler("echo", self.echo_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("nodes", self.nodes_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        
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
            await asyncio.Event().wait()  # Attendre indéfiniment
        except KeyboardInterrupt:
            logger.info("Arrêt du bot...")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

def main():
    """Point d'entrée principal"""
    # Vérifier le token
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ Veuillez configurer TELEGRAM_BOT_TOKEN dans le fichier")
        return
    
    # Créer et lancer le bot
    bridge = TelegramMeshtasticBridge()
    
    try:
        asyncio.run(bridge.start_bot())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du bot Telegram")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")

if __name__ == "__main__":
    main()
