#!/usr/bin/env python3
"""
Bot Telegram bridge pour interface avec le bot Meshtastic
Utilise UNIQUEMENT les chemins définis dans config.py
"""

import asyncio
import logging
import json
import time
import os
import sys
from datetime import datetime

# Utiliser UNIQUEMENT le config.py - pas d'autres chemins codés en dur
try:
    from config import (
        TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_USERS, 
        TELEGRAM_QUEUE_FILE, TELEGRAM_RESPONSE_FILE, 
        TELEGRAM_COMMAND_TIMEOUT, REMOTE_NODE_HOST, REMOTE_NODE_NAME
    )
    config_loaded = True
except ImportError as e:
    print(f"❌ Erreur import config.py: {e}")
    sys.exit(1)

class TelegramLogFilter(logging.Filter):
    """Filtre les logs bruyants de Telegram pour systemd"""
    
    def filter(self, record):
        message = record.getMessage().lower()
        
        # Messages à filtrer complètement
        spam_patterns = [
            'getupdates', 'getting updates', 'received update',
            'http request: get', 'http request: post',
            'httpx', 'httpcore', 'urllib3', 'connectionpool',
            'starting new https connection', 'resetting dropped connection'
        ]
        
        for pattern in spam_patterns:
            if pattern in message:
                return False
        
        # Garder les messages importants
        important_keywords = [
            'error', 'exception', 'failed', 'timeout', 'unauthorized',
            'commande', 'démarrage', 'arrêt', 'start de', 'help de', 
            'bot de', 'power de', 'rx de', 'my de', 'sys de', 'echo de', 'legend de'
        ]
        
        for keyword in important_keywords:
            if keyword in message:
                return True
        
        # Pour les libs externes, seulement WARNING+
        if record.name.startswith(('telegram', 'httpx', 'httpcore', 'urllib3')):
            return record.levelno >= logging.WARNING
        
        return True

def setup_clean_logging():
    """Configure logging propre pour systemd (pas de fichiers de log)"""
    
    # Configuration basique pour systemd
    logging.basicConfig(
        format='%(levelname)s - %(message)s',  # Pas besoin de timestamp avec systemd
        level=logging.INFO,
        stream=sys.stdout
    )
    
    # Créer et appliquer le filtre
    log_filter = TelegramLogFilter()
    
    # Appliquer aux loggers bruyants
    noisy_loggers = ['telegram', 'httpx', 'httpcore', 'urllib3', 'telegram.ext']
    for logger_name in noisy_loggers:
        logger_obj = logging.getLogger(logger_name)
        logger_obj.addFilter(log_filter)
        logger_obj.setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

# Configuration logging
logger = setup_clean_logging()

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError as e:
    logger.error(f"❌ Modules Telegram manquants: {e}")
    logger.info("💡 Installer: pip install python-telegram-bot==20.7")
    sys.exit(1)

class MeshtasticInterface:
    """Interface pour communiquer avec le bot Meshtastic via les fichiers définis dans config.py"""
    
    def __init__(self):
        # Utiliser UNIQUEMENT les chemins du config.py
        self.queue_file = TELEGRAM_QUEUE_FILE
        self.response_file = TELEGRAM_RESPONSE_FILE
        self._ensure_files_exist()
    
    def _ensure_files_exist(self):
        """Créer les fichiers de communication s'ils n'existent pas"""
        for file_path in [self.queue_file, self.response_file]:
            if not os.path.exists(file_path):
                try:
                    # Créer le répertoire parent si nécessaire
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'w') as f:
                        json.dump([], f)
                    logger.debug(f"Fichier créé: {file_path}")
                except Exception as e:
                    logger.error(f"Erreur création {file_path}: {e}")
    
    async def send_command(self, command, user):
        """Envoyer une commande au bot Meshtastic"""
        request_data = {
            "id": f"tg_{int(time.time()*1000)}_{user.id}",
            "command": command,
            "source": "telegram",
            "user": {
                "telegram_id": user.id,
                "username": user.username or user.first_name or "Unknown",
                "first_name": user.first_name or "Unknown"
            },
            "timestamp": time.time()
        }
        
        try:
            # Lire requests existantes
            requests = []
            if os.path.exists(self.queue_file):
                try:
                    with open(self.queue_file, 'r') as f:
                        requests = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    requests = []
            
            # Ajouter nouvelle request
            requests.append(request_data)
            
            # Sauvegarder dans le fichier défini par config.py
            with open(self.queue_file, 'w') as f:
                json.dump(requests, f)
            
            logger.info(f"📡 Commande: {command} pour {user.username or user.first_name}")
            
            # Attendre la réponse
            return await self._wait_for_response(request_data["id"], TELEGRAM_COMMAND_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Erreur envoi commande: {e}")
            return f"❌ Erreur: {str(e)[:50]}"
    
    async def _wait_for_response(self, request_id, timeout):
        """Attendre la réponse du bot Meshtastic dans le fichier défini par config.py"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                if os.path.exists(self.response_file):
                    with open(self.response_file, 'r') as f:
                        try:
                            responses = json.load(f)
                        except json.JSONDecodeError:
                            responses = []
                    
                    # Chercher notre réponse
                    for i, response in enumerate(responses):
                        if response.get("request_id") == request_id:
                            result = response.get("response", "Pas de réponse")
                            
                            # Supprimer la réponse traitée
                            responses.pop(i)
                            with open(self.response_file, 'w') as f:
                                json.dump(responses, f)
                            
                            return result
                
                await asyncio.sleep(1)
                
            except Exception:
                await asyncio.sleep(1)
        
        return "⏰ Timeout - pas de réponse du bot Meshtastic"

class TelegramMeshtasticBridge:
    def __init__(self):
        self.application = None
        self.mesh_interface = MeshtasticInterface()
        
        # Validation du token depuis config.py
        if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            logger.error("❌ TELEGRAM_BOT_TOKEN non configuré dans config.py")
            raise ValueError("Token Telegram manquant dans config.py")
        
        logger.info("✅ Bot Telegram initialisé")
    
    def check_authorization(self, user_id):
        """Vérifier autorisation utilisateur selon config.py"""
        if not TELEGRAM_AUTHORIZED_USERS:
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        logger.info(f"👤 /start de {user.username or user.first_name} ({user.id})")
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        welcome_msg = (
            f"🤖 **Bot Meshtastic Bridge**\n\n"
            f"Salut {user.first_name} !\n\n"
            f"**Commandes directes:**\n"
            f"• `/bot <question>` - Chat avec l'IA\n"
            f"• `/power` - Info batterie/solaire\n"
            f"• `/rx [page]` - Nœuds vus par {REMOTE_NODE_NAME}\n"
            f"• `/my` - Vos signaux radio\n"
            f"• `/sys` - Info système Pi5\n"
            f"• `/echo <message>` - Echo via {REMOTE_NODE_NAME}\n"
            f"• `/legend` - Légende des signaux\n"
            f"• `/help` - Aide complète\n\n"
            f"**Raccourci:** Tapez directement votre message pour chat IA\n\n"
            f"Votre ID: `{user.id}`"
        )
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        user = update.effective_user
        logger.info(f"❓ /help de {user.username or user.first_name}")
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        help_msg = (
            "🤖 **Commandes disponibles:**\n\n"
            "**Commandes principales:**\n"
            "• `/bot <question>` - Chat avec l'IA\n"
            "• `/power` - Info batterie/solaire\n"
            f"• `/rx [page]` - Nœuds vus par {REMOTE_NODE_NAME}\n"
            "• `/my` - Vos signaux radio\n"
            "• `/sys` - Info système Pi5\n"
            f"• `/echo <message>` - Diffuser via {REMOTE_NODE_NAME}\n"
            "• `/legend` - Légende des signaux\n\n"
            "**Format raccourci:**\n"
            "Tapez directement votre message pour `/bot <message>`"
        )
        
        await update.message.reply_text(help_msg, parse_mode='Markdown')
    
    async def bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /bot - Chat IA direct"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("**Usage:** `/bot <question>`\n**Exemple:** `/bot Salut !`", parse_mode='Markdown')
            return
        
        question = ' '.join(context.args)
        logger.info(f"🤖 /bot de {user.username or user.first_name}: {question[:50]}...")
        
        processing_msg = await update.message.reply_text("🤖 L'IA réfléchit...")
        
        try:
            response = await self.mesh_interface.send_command(f"/bot {question}", user)
            if len(response) > 4000:
                response = response[:3950] + "\n\n...(tronqué)"
            
            await processing_msg.edit_text(f"🤖 **IA:**\n{response}")
            
        except Exception as e:
            logger.error(f"Erreur /bot: {e}")
            await processing_msg.edit_text(f"❌ Erreur: {str(e)[:200]}")
    
    async def power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power direct"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        logger.info(f"🔋 /power de {user.username or user.first_name}")
        processing_msg = await update.message.reply_text("🔋 Récupération données...")
        
        try:
            response = await self.mesh_interface.send_command("/power", user)
            await processing_msg.edit_text(f"🔋 **Alimentation:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur /power: {e}")
            await processing_msg.edit_text(f"❌ Erreur: {str(e)[:200]}")
    
    async def rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx direct"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        page = ""
        if context.args:
            page = f" {context.args[0]}"
        
        logger.info(f"📡 /rx{page} de {user.username or user.first_name}")
        processing_msg = await update.message.reply_text("📡 Récupération nœuds...")
        
        try:
            command = f"/rx{page}" if page else "/rx"
            response = await self.mesh_interface.send_command(command, user)
            await processing_msg.edit_text(f"📡 **Nœuds:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur /rx: {e}")
            await processing_msg.edit_text(f"❌ Erreur: {str(e)[:200]}")
    
    async def my_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /my direct"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        logger.info(f"📶 /my de {user.username or user.first_name}")
        processing_msg = await update.message.reply_text("📶 Vérification signal...")
        
        try:
            response = await self.mesh_interface.send_command("/my", user)
            await processing_msg.edit_text(f"📶 **Votre signal:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur /my: {e}")
            await processing_msg.edit_text(f"❌ Erreur: {str(e)[:200]}")
    
    async def sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys direct"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        logger.info(f"🖥️ /sys de {user.username or user.first_name}")
        processing_msg = await update.message.reply_text("🖥️ Info système...")
        
        try:
            response = await self.mesh_interface.send_command("/sys", user)
            await processing_msg.edit_text(f"🖥️ **Système:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur /sys: {e}")
            await processing_msg.edit_text(f"❌ Erreur: {str(e)[:200]}")
    
    async def echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo direct"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("**Usage:** `/echo <message>`\n**Exemple:** `/echo Salut le réseau !`", parse_mode='Markdown')
            return
        
        echo_text = ' '.join(context.args)
        logger.info(f"📢 /echo de {user.username or user.first_name}: {echo_text}")
        
        try:
            response = await self.mesh_interface.send_command(f"/echo {echo_text}", user)
            await update.message.reply_text(f"📢 **Echo diffusé:**\n`{user.first_name}: {echo_text}`", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur /echo: {e}")
            await update.message.reply_text(f"❌ Erreur echo: {str(e)[:200]}")
    
    async def legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend direct"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        logger.info(f"🔍 /legend de {user.username or user.first_name}")
        
        try:
            response = await self.mesh_interface.send_command("/legend", user)
            await update.message.reply_text(f"🔍 **Légende:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur /legend: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)[:200]}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Messages texte = raccourci pour /bot"""
        user = update.effective_user
        message_text = update.message.text
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Accès non autorisé")
            return
        
        logger.info(f"💬 Message de {user.username or user.first_name}: {message_text[:50]}...")
        
        processing_msg = await update.message.reply_text("🤖 L'IA réfléchit...")
        
        try:
            response = await self.mesh_interface.send_command(f"/bot {message_text}", user)
            if len(response) > 4000:
                response = response[:3950] + "\n\n...(tronqué)"
            
            await processing_msg.edit_text(f"🤖 **IA:**\n{response}")
            
        except Exception as e:
            logger.error(f"Erreur message direct: {e}")
            await processing_msg.edit_text(f"❌ Erreur: {str(e)[:200]}")
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs global"""
        logger.error(f"Exception Telegram: {context.error}")
        
        if update and hasattr(update, 'message') and update.message:
            try:
                await update.message.reply_text("❌ Erreur interne. Veuillez réessayer.")
            except:
                pass
    
    async def start_bot(self):
        """Démarrer le bot Telegram"""
        logger.info("🚀 Démarrage du bot Telegram Meshtastic Bridge")
        
        try:
            # Créer l'application avec le token du config.py
            self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            
            # Ajouter TOUS les handlers de commandes directes
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("bot", self.bot_command))
            self.application.add_handler(CommandHandler("power", self.power_command))
            self.application.add_handler(CommandHandler("rx", self.rx_command))
            self.application.add_handler(CommandHandler("my", self.my_command))
            self.application.add_handler(CommandHandler("sys", self.sys_command))
            self.application.add_handler(CommandHandler("echo", self.echo_command))
            self.application.add_handler(CommandHandler("legend", self.legend_command))
            
            # Handler pour messages texte (raccourci /bot)
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )
            
            # Gestionnaire d'erreurs
            self.application.add_error_handler(self.error_handler)
            
            # Démarrer le bot
            await self.application.initialize()
            await self.application.start()
            
            await self.application.updater.start_polling(
                poll_interval=2.0,
                timeout=20,
                bootstrap_retries=3,
                read_timeout=15,
                write_timeout=15,
                connect_timeout=15,
                pool_timeout=15
            )
            
            logger.info("✅ Bot Telegram opérationnel")
            
            # Maintenir le bot actif
            try:
                await asyncio.Future()  # Run forever
            except (KeyboardInterrupt, SystemExit):
                logger.info("📴 Arrêt demandé")
                
        except Exception as e:
            logger.error(f"Erreur fatale: {e}")
            raise
        finally:
            # Nettoyage
            if self.application:
                try:
                    await self.application.updater.stop()
                    await self.application.stop()
                    await self.application.shutdown()
                except:
                    pass

def main():
    """Point d'entrée principal"""
    
    # Validation du token depuis config.py
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Token Telegram non configuré dans config.py")
        logger.info("💡 Configurez TELEGRAM_BOT_TOKEN dans config.py")
        return 1
    
    bridge = TelegramMeshtasticBridge()
    
    try:
        logger.info("🌟 Lancement...")
        asyncio.run(bridge.start_bot())
        
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt manuel")
        return 0
        
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
