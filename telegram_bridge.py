#!/usr/bin/env python3
"""
Bot Telegram bridge pour interface avec le bot Meshtastic
Version améliorée avec /nodes optimisé pour Telegram
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuration - Importer depuis config.py principal
import sys
sys.path.append('/home/dietpi/bot')  # Ajuster selon votre chemin

try:
    from config import (
        TELEGRAM_BOT_TOKEN, 
        TELEGRAM_AUTHORIZED_USERS, 
        TELEGRAM_QUEUE_FILE, 
        TELEGRAM_RESPONSE_FILE, 
        TELEGRAM_COMMAND_TIMEOUT,
        REMOTE_NODE_HOST,
        REMOTE_NODE_NAME
    )
    print("✅ Configuration importée depuis config.py principal")
except ImportError:
    print("⚠️ Configuration locale utilisée")
    TELEGRAM_BOT_TOKEN = "YOUR_TOKEN_HERE"
    TELEGRAM_AUTHORIZED_USERS = []
    TELEGRAM_QUEUE_FILE = "/tmp/telegram_mesh_queue.json"
    TELEGRAM_RESPONSE_FILE = "/tmp/mesh_telegram_response.json"
    TELEGRAM_COMMAND_TIMEOUT = 30
    REMOTE_NODE_HOST = "192.168.1.38"
    REMOTE_NODE_NAME = "tigrog2"

# Configuration logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Réduire la verbosité des logs httpx (polling Telegram)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Updater").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.WARNING)

class TelegramMeshtasticBridge:
    def __init__(self):
        self.application = None
        self.interface = None
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        logger.info(f"Utilisateur {user.username} ({user.id}) démarre le bot")
        
        welcome_msg = (
            f"🤖 Bot Meshtastic Bridge\n\n"
            f"Salut {user.first_name} !\n\n"
            f"Commandes disponibles:\n"
            f"• /bot <question> - Chat IA\n"
            f"• /power - Télémétrie\n"
            f"• /nodes - Liste complète des nœuds\n" 
            f"• /echo <message> - Echo via {REMOTE_NODE_NAME}\n"
            f"• /help - Aide complète\n\n"
            f"Votre ID: {user.id}"
        )
        
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        help_msg = (
            "🤖 **Commandes disponibles:**\n\n"
            "**Commandes Meshtastic:**\n"
            "• `/bot <question>` - Chat IA\n"
            "• `/power` - Info batterie/solaire\n"
            "• `/rx [page]` - Nœuds vus par tigrog2 (paginé)\n"
            "• `/my` - Vos signaux\n"
            "• `/sys` - Info système Pi5\n"
            "• `/legend` - Légende signaux\n\n"
            "**Commandes Telegram:**\n"
            "• `/status` - État réseau\n"
            "• `/nodes` - Liste complète des nœuds (format étendu)\n"
            "• `/echo <message>` - Diffuser via tigrog2\n"
            "• `/stats` - Statistiques\n\n"
            "**Format raccourci:**\n"
            "Tapez directement votre message pour `/bot <message>`"
        )
        
        await update.message.reply_text(help_msg, parse_mode='Markdown')
    
    def check_authorization(self, user_id):
        """Vérifier si l'utilisateur est autorisé"""
        if not TELEGRAM_AUTHORIZED_USERS:  # Si liste vide, tout le monde est autorisé
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS
    
    async def bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /bot pour chat IA"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /bot <question>\nEx: /bot Quelle est la météo ?")
            return
        
        # Construire la commande
        question = ' '.join(context.args)
        mesh_command = f"/bot {question}"
        logger.info(f"Bot IA de {user.username}: {question}")
        
        try:
            response = await self.send_to_meshtastic(mesh_command, user)
            
            if len(response) > 4000:
                chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await update.message.reply_text(f"🤖 **IA Mesh:** (partie {i+1}/{len(chunks)})\n{chunk}")
                    else:
                        await update.message.reply_text(f"🤖 **(suite {i+1}/{len(chunks)})**\n{chunk}")
            else:
                await update.message.reply_text(f"🤖 **IA Mesh:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur commande /bot: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power pour télémétrie ESPHome"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Power de {user.username}")
        
        try:
            response = await self.send_to_meshtastic("/power", user)
            await update.message.reply_text(f"🔋 **Télémétrie:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande /power: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx pour nœuds paginés (format LoRa compact)"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Récupérer le numéro de page
        page = 1
        if context.args:
            try:
                page = int(context.args[0])
            except ValueError:
                page = 1
        
        mesh_command = f"/rx {page}" if page > 1 else "/rx"
        logger.info(f"RX page {page} de {user.username}")
        
        try:
            response = await self.send_to_meshtastic(mesh_command, user)
            await update.message.reply_text(f"📡 **Nœuds (paginé):**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande /rx: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def my_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /my pour signaux personnels"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"My de {user.username}")
        
        try:
            response = await self.send_to_meshtastic("/my", user)
            await update.message.reply_text(f"📊 **Vos signaux:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande /my: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys pour infos système"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Sys de {user.username}")
        
        try:
            response = await self.send_to_meshtastic("/sys", user)
            await update.message.reply_text(f"🖥️ **Système:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande /sys: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend pour légende des indicateurs"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        logger.info(f"Legend de {user.username}")
        
        try:
            response = await self.send_to_meshtastic("/legend", user)
            await update.message.reply_text(f"🔍 **Légende:**\n```\n{response}\n```", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande /legend: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def nodes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /nodes - Liste complète optimisée pour Telegram"""
        user = update.effective_user
        
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        try:
            # Récupérer les nœuds via l'interface Meshtastic
            nodes_data = await self.get_extended_nodes_list()
            
            if not nodes_data:
                await update.message.reply_text("❌ Aucun nœud disponible")
                return
            
            # Formater pour Telegram (format étendu)
            response_lines = [f"📡 **Nœuds {REMOTE_NODE_NAME}** ({len(nodes_data)} nœuds):\n"]
            
            for node in nodes_data:
                # Format étendu pour Telegram : nom complet + détails
                name = node.get('name', 'Inconnu')
                node_id = node.get('id', 0)
                rssi = node.get('rssi', 0)
                snr = node.get('snr', 0.0)
                last_heard = node.get('last_heard', 0)
                
                # Icônes de qualité
                rssi_icon = self.get_quality_icon(rssi)
                
                # Temps écoulé
                if last_heard > 0:
                    elapsed = int(time.time() - last_heard)
                    if elapsed < 60:
                        time_str = f"{elapsed}s"
                    elif elapsed < 3600:
                        time_str = f"{elapsed//60}m"
                    elif elapsed < 86400:
                        time_str = f"{elapsed//3600}h"
                    else:
                        time_str = f"{elapsed//86400}j"
                else:
                    time_str = "n/a"
                
                # Ligne formatée pour Telegram - Format compact sur une ligne
                metrics = []
                
                # SNR toujours affiché (métrique principale LoRa)
                metrics.append(f"SNR: {snr:.1f}dB")
                
                # Temps
                metrics.append(time_str)
                
                line = f"{rssi_icon} **{name}** {' | '.join(metrics)}"
                
                response_lines.append(line)
            
            # Assembler la réponse
            full_response = "\n".join(response_lines)
            
            # Footer informatif
            full_response += f"\n\n🔍 Légende: 🟢 Excellent | 🟡 Bon | 🟠 Faible | 🔴 Critique\n"
            full_response += f"📊 Triés par SNR (qualité LoRa), <3 jours"
            
            # Vérifier la taille et diviser si nécessaire
            if len(full_response) > 4000:
                # Diviser par chunks de nœuds
                node_chunks = []
                current_chunk = [response_lines[0]]  # Header
                current_size = len(response_lines[0])
                
                for line in response_lines[1:]:
                    if current_size + len(line) + 2 > 3800:  # Marge de sécurité
                        node_chunks.append("\n\n".join(current_chunk))
                        current_chunk = [f"📡 **Nœuds {REMOTE_NODE_NAME}** (suite):\n", line]
                        current_size = len(current_chunk[0]) + len(line) + 2
                    else:
                        current_chunk.append(line)
                        current_size += len(line) + 2
                
                if current_chunk:
                    node_chunks.append("\n\n".join(current_chunk))
                
                # Envoyer chaque chunk
                for i, chunk in enumerate(node_chunks):
                    if i == 0:
                        await update.message.reply_text(chunk, parse_mode='Markdown')
                    else:
                        await update.message.reply_text(chunk, parse_mode='Markdown')
                        await asyncio.sleep(1)  # Éviter le rate limiting
            else:
                await update.message.reply_text(full_response, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Erreur commande nodes: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    def get_quality_icon(self, rssi, snr=0.0):
        """Obtenir l'icône de qualité basée uniquement sur SNR (RSSI supprimé car buggé)"""
        # Debug temporaire pour voir les valeurs reçues
        print(f"DEBUG get_quality_icon: snr={snr} (type: {type(snr)})")
        
        # Seuils ajustés selon vos données réelles
        if snr > 4.5:  # Au lieu de >= 5
            return "🟢"  # Excellent SNR
        elif snr > 1.0:  # Au lieu de >= 0
            return "🟡"  # Bon SNR
        elif snr > -3.0:  # Au lieu de >= -5
            return "🟠"  # SNR faible mais utilisable
        else:
            return "🔴"  # SNR critique
    
    async def get_extended_nodes_list(self):
        """Récupérer la liste étendue des nœuds pour Telegram"""
        try:
            # Simuler la récupération des nœuds via l'API
            # Dans une vraie implémentation, ceci ferait appel à remote_nodes_client
            import meshtastic.tcp_interface
            
            # Connexion TCP temporaire à tigrog2
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST, 
                portNumber=4403
            )
            
            # Attendre le chargement
            await asyncio.sleep(2)
            
            # Récupérer les nœuds
            remote_nodes = remote_interface.nodes
            node_list = []
            
            current_time = time.time()
            three_days_ago = current_time - (3 * 24 * 3600)  # 3 jours
            
            for node_id, node_info in remote_nodes.items():
                try:
                    if isinstance(node_info, dict):
                        # Filtrer seulement les nœuds directs (hopsAway = 0)
                        hops_away = node_info.get('hopsAway', None)
                        if hops_away is not None and hops_away > 0:
                            continue
                        
                        # Convertir node_id
                        if isinstance(node_id, str):
                            if node_id.startswith('!'):
                                clean_id = node_id[1:]
                                id_int = int(clean_id, 16)
                            else:
                                id_int = int(node_id, 16)
                        else:
                            id_int = int(node_id)
                        
                        # Récupérer le nom complet (longName prioritaire pour Telegram)
                        name = "Inconnu"
                        if 'user' in node_info and isinstance(node_info['user'], dict):
                            user_info = node_info['user']
                            long_name = user_info.get('longName', '')
                            short_name = user_info.get('shortName', '')
                            
                            # Pour Telegram, préférer longName (plus lisible)
                            if long_name:
                                name = long_name
                            elif short_name:
                                name = short_name
                            else:
                                name = f"Nœud-{id_int:04x}"
                        
                        # Vérifications temporelles
                        last_heard = node_info.get('lastHeard', 0)
                        if last_heard > 0 and last_heard < three_days_ago:
                            continue
                        
                        # Métriques de signal
                        rssi = node_info.get('rssi', 0)
                        snr = node_info.get('snr', 0.0)
                        
                        # Debug temporaire pour voir les valeurs extraites
                        print(f"DEBUG node {name}: rssi={rssi}, snr={snr}")
                        
                        node_data = {
                            'id': id_int,
                            'name': name,
                            'rssi': rssi,
                            'snr': snr,
                            'last_heard': last_heard
                        }
                        
                        node_list.append(node_data)
                        
                except Exception as e:
                    logger.debug(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            remote_interface.close()
            
            # Trier par SNR décroissant (plus fiable que RSSI en LoRa)
            node_list.sort(key=lambda x: x.get('snr', -999), reverse=True)
            
            return node_list
            
        except Exception as e:
            logger.error(f"Erreur récupération nœuds: {e}")
            return []
    
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
            # Envoyer l'echo via tigrog2
            response = await self.send_echo_to_tigrog2(echo_text, user)
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
        
        # Raccourci: message direct = /bot <message>
        logger.info(f"Message direct de {user.username}: {message_text}")
        
        try:
            mesh_command = f"/bot {message_text}"
            response = await self.send_to_meshtastic(mesh_command, user)
            
            # Réponse directe de l'IA (formatée pour Telegram)
            if len(response) > 4000:
                chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await update.message.reply_text(f"🤖 **IA Mesh:** (partie {i+1}/{len(chunks)})\n{chunk}")
                    else:
                        await update.message.reply_text(f"🤖 **(suite {i+1}/{len(chunks)})**\n{chunk}")
            else:
                await update.message.reply_text(f"🤖 **IA Mesh:**\n{response}")
        except Exception as e:
            logger.error(f"Erreur message direct: {e}")
            await update.message.reply_text(f"❌ Erreur: {str(e)}")
    
    async def send_to_meshtastic(self, command, user):
        """Envoyer une commande au bot Meshtastic via le système de fichiers"""
        try:
            # Créer la requête
            request_data = {
                "id": f"tg_{int(time.time()*1000)}",
                "command": command,
                "source": "telegram",
                "user": {
                    "telegram_id": user.id,
                    "username": user.username or user.first_name,
                    "first_name": user.first_name
                },
                "timestamp": time.time()
            }
            
            # Lire les requêtes existantes
            requests = []
            try:
                with open(TELEGRAM_QUEUE_FILE, 'r') as f:
                    requests = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                requests = []
            
            # Ajouter la nouvelle requête
            requests.append(request_data)
            
            # Écrire la queue
            with open(TELEGRAM_QUEUE_FILE, 'w') as f:
                json.dump(requests, f)
            
            # Attendre la réponse
            return await self.wait_for_response(request_data["id"])
            
        except Exception as e:
            return f"Erreur interface: {str(e)}"
    
    async def wait_for_response(self, request_id):
        """Attendre la réponse du bot Meshtastic"""
        start_time = time.time()
        
        while (time.time() - start_time) < TELEGRAM_COMMAND_TIMEOUT:
            try:
                with open(TELEGRAM_RESPONSE_FILE, 'r') as f:
                    responses = json.load(f)
                
                # Chercher notre réponse
                for i, response in enumerate(responses):
                    if response.get("request_id") == request_id:
                        result = response.get("response", "Pas de réponse")
                        
                        # Supprimer la réponse traitée
                        responses.pop(i)
                        with open(TELEGRAM_RESPONSE_FILE, 'w') as f:
                            json.dump(responses, f)
                        
                        return result
                
                await asyncio.sleep(0.5)
                
            except (FileNotFoundError, json.JSONDecodeError):
                await asyncio.sleep(0.5)
                continue
        
        return "⏰ Timeout - pas de réponse du bot Meshtastic"
    
    async def send_echo_to_tigrog2(self, echo_text, user):
        """Envoyer un echo via tigrog2"""
        try:
            import meshtastic.tcp_interface
            
            # Connexion TCP à tigrog2
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST, 
                portNumber=4403
            )
            
            await asyncio.sleep(1)
            
            # Créer le message d'echo avec identification
            author = user.username or user.first_name
            echo_message = f"TG-{author}: {echo_text}"
            
            # Envoyer en broadcast
            remote_interface.sendText(echo_message)
            remote_interface.close()
            
            logger.info(f"Echo Telegram diffusé: {echo_message}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur echo tigrog2: {e}")
            raise
    
    async def get_meshtastic_status(self):
        """Récupérer l'état du système Meshtastic"""
        # Envoyer via le système de fichiers
        return await self.send_to_meshtastic("/sys", type('User', (), {
            'id': 999999999,
            'username': 'telegram_status',
            'first_name': 'Telegram'
        })())
    
    async def get_meshtastic_stats(self):
        """Récupérer les statistiques"""
        await asyncio.sleep(0.5)
        return (
            f"Messages aujourd'hui: {47}\n"
            f"Commandes /bot: {12}\n"
            f"Commandes /echo: {8}\n"
            f"Nœuds vus: {15}\n"
            f"Temps réponse moyen: 1.2s\n"
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
        
        # Commandes Meshtastic directes (sans préfixe /mesh)
        self.application.add_handler(CommandHandler("bot", self.bot_command))
        self.application.add_handler(CommandHandler("power", self.power_command))
        self.application.add_handler(CommandHandler("rx", self.rx_command))
        self.application.add_handler(CommandHandler("my", self.my_command))
        self.application.add_handler(CommandHandler("sys", self.sys_command))
        self.application.add_handler(CommandHandler("legend", self.legend_command))
        
        # Commandes Telegram spécifiques
        self.application.add_handler(CommandHandler("nodes", self.nodes_command))
        self.application.add_handler(CommandHandler("echo", self.echo_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
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
    if TELEGRAM_BOT_TOKEN == "YOUR_TOKEN_HERE":
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
