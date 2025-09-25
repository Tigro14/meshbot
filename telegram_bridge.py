#!/usr/bin/env python3
"""
Bot Telegram bridge pour interface avec le bot Meshtastic
"""

import asyncio
import logging
import json
import os
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuration
import sys
import os

# Essayer d'importer la configuration
config_found = False
try:
    from config import *
    config_found = True
    print("✅ Configuration chargée depuis le répertoire courant")
except ImportError:
    try:
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, parent_dir)
        from config import *
        config_found = True
        print(f"✅ Configuration chargée depuis {parent_dir}")
    except ImportError:
        print("❌ config.py non trouvé - utilisation valeurs par défaut")

# Valeurs par défaut si config.py non trouvé
if not config_found:
    TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    TELEGRAM_AUTHORIZED_USERS = []
    TELEGRAM_QUEUE_FILE = "/tmp/telegram_mesh_queue.json"
    TELEGRAM_RESPONSE_FILE = "/tmp/mesh_telegram_response.json"
    TELEGRAM_COMMAND_TIMEOUT = 50
    DEBUG_MODE = False
    TELEGRAM_TO_MESH_MAPPING = {}

# Importer le mapping s'il existe
try:
    from config import TELEGRAM_TO_MESH_MAPPING
except (ImportError, NameError):
    TELEGRAM_TO_MESH_MAPPING = {}

# Configuration logging - réduire le niveau des librairies externes
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO if not DEBUG_MODE else logging.DEBUG
)

if not DEBUG_MODE:
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('telegram.ext').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    logger = logging.getLogger('telegram_bridge')
    logger.setLevel(logging.INFO)
else:
    logging.getLogger('httpx').setLevel(logging.INFO)
    logging.getLogger('telegram').setLevel(logging.INFO)
    logger = logging.getLogger('telegram_bridge')
    logger.setLevel(logging.DEBUG)

logger = logging.getLogger('telegram_bridge')

class TelegramMeshtasticBridge:
    def __init__(self):
        self.application = None
        self.command_queue = asyncio.Queue()
        
    def get_mesh_display_name(self, user_id, username):
        """Obtenir le nom d'affichage Meshtastic pour un utilisateur"""
        if user_id in TELEGRAM_TO_MESH_MAPPING:
            return TELEGRAM_TO_MESH_MAPPING[user_id]["short_name"]
        return username or f"tg{user_id}"
    
    def check_authorization(self, user_id):
        """Vérifier si l'utilisateur est autorisé"""
        if not TELEGRAM_AUTHORIZED_USERS:
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        logger.info(f"Utilisateur {user.username} ({user.id}) démarre le bot")
        
        welcome_msg = (
            f"🤖 Bot Meshtastic Bridge\n\n"
            f"Salut {user.first_name} !\n\n"
            f"🎯 **Vous êtes mappé comme:** {self.get_mesh_display_name(user.id, user.username or user.first_name)}\n\n"
            f"Commandes disponibles:\n"
            f"• /bot <question> - Chat avec l'IA\n"
            f"• /power - Info batterie/solaire\n"
            f"• /rx [page] - Nœuds vus par tigrog2\n"
            f"• /sys - Info système Pi5\n"
            f"• /echo <message> - Diffuser via tigrog2\n"
            f"• /legend - Légende signaux\n"
            f"• /help - Aide complète\n\n"
            f"💬 **Raccourci:** Tapez directement votre message pour /bot\n\n"
            f"Votre ID Telegram: {user.id}"
        )
        
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        user = update.effective_user
        mesh_name = self.get_mesh_display_name(user.id, user.username or user.first_name)
        
        help_msg = (
            f"🤖 **Bot Meshtastic - Aide complète**\n\n"
            f"🎯 **Votre identité mesh:** `{mesh_name}`\n\n"
            f"**📱 Commandes principales:**\n"
            f"• `/bot <question>` - Chat avec l'IA Llama\n"
            f"• `/power` - Info batterie/solaire ESPHome\n"
            f"• `/rx [page]` - Nœuds vus par tigrog2\n"
            f"• `/sys` - Info système Pi5\n"
            f"• `/echo <message>` - Diffuser via tigrog2\n"
            f"• `/legend` - Légende des indicateurs\n\n"
            f"**🔧 Commandes système:**\n"
            f"• `/status` - État général du système\n"
            f"• `/nodes` - Liste des nœuds actifs\n"
            f"• `/help` - Cette aide\n\n"
            f"**💡 Conseils d'utilisation:**\n"
            f"• **Raccourci IA:** Tapez directement votre message pour `/bot`\n"
            f"• **Echo mesh:** Vos messages `/echo` apparaissent comme `{mesh_name}: ...`\n"
            f"• **Pagination:** `/rx 2` pour voir la page 2 des nœuds\n\n"
            f"**⚠️ Limitations:**\n"
            f"• `/my` non disponible depuis Telegram (position requise)\n"
            f"• Messages LoRa limités à ~180 caractères\n"
            f"• Throttling: 5 commandes/5min max\n\n"
            f"**🆔 Votre ID Telegram:** `{user.id}`"
        )
        
        await update.message.reply_text(help_msg, parse_mode='Markdown')
    
    async def bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /bot directe"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /bot <question>\nEx: /bot Comment ça va ?")
            return
        
        question = ' '.join(context.args)
        bot_command = f"/bot {question}"
        logger.info(f"Commande bot directe de {user.username}: {question}")
        
        try:
            response = await self.send_to_meshtastic(bot_command, user)
            mesh_name = self.get_mesh_display_name(user.id, user.username or user.first_name)
            await update.message.reply_text(f"🤖 **IA Mesh** (en tant que `{mesh_name}`):\n{response}", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande bot: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power directe"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Commande power de {user.username}")
        
        try:
            response = await self.send_to_meshtastic("/power", user)
            await update.message.reply_text(f"🔋 **Power:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur commande power: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx directe"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        page = ""
        if context.args and context.args[0].isdigit():
            page = f" {context.args[0]}"
        
        rx_command = f"/rx{page}"
        logger.info(f"Commande rx de {user.username}: {rx_command}")
        
        try:
            response = await self.send_to_meshtastic(rx_command, user)
            await update.message.reply_text(f"📡 **Nœuds:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande rx: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys directe"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Commande sys de {user.username}")
        
        try:
            response = await self.send_to_meshtastic("/sys", user)
            await update.message.reply_text(f"💻 **Système:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande sys: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend directe"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Commande legend de {user.username}")
        
        try:
            response = await self.send_to_meshtastic("/legend", user)
            await update.message.reply_text(f"📶 **Légende:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur commande legend: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def mesh_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /mesh pour compatibilité (optionnelle)"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("⚠️ Commande /mesh dépréciée\n\nUtilisez directement:\n• /bot <question>\n• /power\n• /rx\n• /sys\n• /legend")
            return
        
        mesh_command = ' '.join(context.args)
        logger.info(f"Commande mesh (legacy) de {user.username}: {mesh_command}")
        
        try:
            response = await self.send_to_meshtastic(mesh_command, user)
            await update.message.reply_text(f"📡 **Réponse:**\n{response}")
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
            display_name = self.get_mesh_display_name(user.id, user.username or user.first_name)
            
            echo_command = f"/echo {echo_text}"
            fake_user = type('User', (), {
                'id': user.id,
                'username': display_name,
                'first_name': display_name
            })()
            
            response = await self.send_to_meshtastic(echo_command, fake_user)
            
            await update.message.reply_text(f"📡 **Echo diffusé:**\n`{display_name}: {echo_text}`", parse_mode='Markdown')
            
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
            return f"Erreur stats: {str(e)}"
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gérer les messages texte (raccourci pour /bot)"""
        user = update.effective_user
        message_text = update.message.text
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Message direct de {user.username}: {message_text}")
        
        try:
            mesh_command = f"/bot {message_text}"
            response = await self.send_to_meshtastic(mesh_command, user)
            mesh_name = self.get_mesh_display_name(user.id, user.username or user.first_name)
            await update.message.reply_text(f"🤖 **IA Mesh** (en tant que `{mesh_name}`):\n{response}", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur message direct: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def send_to_meshtastic(self, command, user):
        """Envoyer une commande au bot Meshtastic via système de fichiers"""
        try:
            request_id = f"tg_{int(time.time()*1000)}_{user.id}"
            
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
            
            existing_requests = []
            try:
                if os.path.exists(TELEGRAM_QUEUE_FILE):
                    with open(TELEGRAM_QUEUE_FILE, 'r') as f:
                        existing_requests = json.load(f)
                        if not isinstance(existing_requests, list):
                            existing_requests = []
            except (json.JSONDecodeError, FileNotFoundError):
                existing_requests = []
            
            existing_requests.append(request_data)
            
            with open(TELEGRAM_QUEUE_FILE, 'w') as f:
                json.dump(existing_requests, f, indent=2)
            
            logger.info(f"Requête {request_id} envoyée au bot Meshtastic")
            
            return await self.wait_for_response(request_id, TELEGRAM_COMMAND_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Erreur envoi commande à Meshtastic: {e}")
            return f"Erreur communication: {str(e)[:50]}"
    
    async def wait_for_response(self, request_id, timeout=30):
        """Attendre la réponse du bot Meshtastic"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                if os.path.exists(TELEGRAM_RESPONSE_FILE):
                    with open(TELEGRAM_RESPONSE_FILE, 'r') as f:
                        try:
                            responses = json.load(f)
                            if not isinstance(responses, list):
                                responses = []
                        except json.JSONDecodeError:
                            responses = []
                    
                    for i, response in enumerate(responses):
                        if response.get("request_id") == request_id:
                            result = response.get("response", "Pas de réponse")
                            
                            responses.pop(i)
                            with open(TELEGRAM_RESPONSE_FILE, 'w') as f:
                                json.dump(responses, f, indent=2)
                            
                            logger.info(f"Réponse reçue pour {request_id}")
                            return result
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Erreur lecture réponse: {e}")
                continue
        
        logger.warning(f"Timeout pour la requête {request_id}")
        return f"⏰ Timeout - pas de réponse du bot Meshtastic après {timeout}s"
    
    async def get_meshtastic_status(self):
        """Récupérer l'état du système Meshtastic"""
        try:
            fake_user = type('User', (), {
                'id': 999999999,
                'username': 'telegram_status',
                'first_name': 'Telegram'
            })()
            
            response = await self.send_to_meshtastic("/sys", fake_user)
            return response
            
        except Exception as e:
            logger.error(f"Erreur récupération status: {e}")
            return f"Erreur status: {str(e)}"
    
    async def get_meshtastic_nodes(self):
        """Récupérer la liste des nœuds"""
        try:
            fake_user = type('User', (), {
                'id': 999999998,
                'username': 'telegram_nodes',
                'first_name': 'Telegram'
            })()
            
            response = await self.send_to_meshtastic("/rx", fake_user)
            return response
            
        except Exception as e:
            logger.error(f"Erreur récupération nodes: {e}")
            return f"Erreur nodes: {str(e)}"
    
    async def get_meshtastic_stats(self):
        """Récupérer les statistiques"""
        try:
            fake_user = type('User', (), {
                'id': 999999997,
                'username': 'telegram_stats', 
                'first_name': 'Telegram'
            })()
            
            response = await self.send_to_meshtastic("/sys", fake_user)
            return f"📈 Statistiques système:\n{response}"
            
        except Exception as e:
            logger.error(f"Erreur récupération stats: {e}")
            return f"Erreur stats: {str(e)}"
    
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
        
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Ajouter les handlers - nouvelles commandes directes
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Commandes principales (directes)
        self.application.add_handler(CommandHandler("bot", self.bot_command))
        self.application.add_handler(CommandHandler("power", self.power_command))
        self.application.add_handler(CommandHandler("rx", self.rx_command))
        self.application.add_handler(CommandHandler("sys", self.sys_command))
        self.application.add_handler(CommandHandler("legend", self.legend_command))
        self.application.add_handler(CommandHandler("echo", self.echo_command))
        
        # Commandes système
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("nodes", self.nodes_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        
        # Compatibilité ancienne interface
        self.application.add_handler(CommandHandler("mesh", self.mesh_command))
        
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
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Veuillez configurer TELEGRAM_BOT_TOKEN dans le fichier")
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
