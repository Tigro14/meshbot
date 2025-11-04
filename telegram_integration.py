#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'intégration Telegram dans le bot Meshtastic - INTÉGRATION COMPLÈTE
Gère directement l'API Telegram sans fichiers queue
"""

import time
import threading
import traceback
from config import *
from utils import *

# Import Telegram (optionnel)
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    import asyncio
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    info_print("Module python-telegram-bot non installé")

# Import Meshtastic protobuf pour traceroute natif
try:
    from meshtastic import portnums_pb2, mesh_pb2
    MESHTASTIC_PROTOBUF_AVAILABLE = True
except ImportError:
    MESHTASTIC_PROTOBUF_AVAILABLE = False
    print("⚠️ Modules protobuf Meshtastic non disponibles")

class TelegramIntegration:
    def __init__(self, message_handler, node_manager, context_manager):
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot requis. Installez: pip3 install python-telegram-bot")

        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager

        self.running = False
        self.telegram_thread = None
        self.application = None
        self.loop = None

        # Liste des utilisateurs pour les alertes
        self.alert_users = TELEGRAM_ALERT_USERS if TELEGRAM_ALERT_USERS else TELEGRAM_AUTHORIZED_USERS
        self.pending_traces = {}  # node_id -> {'telegram_chat_id': int, 'timestamp': float, 'short_name': str}
        self.trace_timeout = 45  # 45 secondes pour recevoir la réponse

    def start(self):
        """Démarrer le bot Telegram dans un thread séparé"""
        if self.running:
            return

        self.running = True
        self.telegram_thread = threading.Thread(target=self._run_telegram_bot, daemon=True)
        self.telegram_thread.start()
        info_print("🤖 Bot Telegram démarré en thread séparé")

    def stop(self):
        """Arrêter le bot Telegram"""
        self.running = False
        if self.loop and self.application:
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop).result(timeout=5)
            except Exception as e:
                pass
        info_print("🛑 Bot Telegram arrêté")

    def _get_mesh_identity(self, telegram_user_id):
        """
        Obtenir l'identité Meshtastic correspondant à un utilisateur Telegram
        
        Args:
            telegram_user_id: ID Telegram de l'utilisateur
            
        Returns:
            dict: {'node_id': int, 'short_name': str, 'display_name': str}
                  ou None si pas de mapping
        """
        from config import TELEGRAM_TO_MESH_MAPPING
        from utils import debug_print
        
        if telegram_user_id in TELEGRAM_TO_MESH_MAPPING:
            mapping = TELEGRAM_TO_MESH_MAPPING[telegram_user_id]
            debug_print(f"✅ Mapping Telegram {telegram_user_id} → {mapping['display_name']}")
            return mapping
        else:
            debug_print(f"⚠️ Pas de mapping pour {telegram_user_id}")
            return None

    def _run_telegram_bot(self):
        """Exécuter le bot Telegram dans son propre event loop"""
        try:
            # Créer un nouvel event loop pour ce thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Lancer le bot et bloquer jusqu'à l'arrêt
            self.loop.run_until_complete(self._start_telegram_bot())
            
        except Exception as e:
            error_print(f"Erreur bot Telegram: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
        finally:
            # Nettoyer l'event loop
            try:
                self.loop.close()
            except Exception as e:
                pass

    async def _start_telegram_bot(self):
        """Démarrer l'application Telegram"""
        try:
            info_print(f"Initialisation bot Telegram...")
            
            self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            
            # Handlers de commandes
            self.application.add_handler(CommandHandler("start", self._start_command))
            self.application.add_handler(CommandHandler("help", self._help_command))
            self.application.add_handler(CommandHandler("power", self._power_command))
            self.application.add_handler(CommandHandler("weather", self._weather_command))
            self.application.add_handler(CommandHandler("graphs", self._graphs_command))
            self.application.add_handler(CommandHandler("rx", self._rx_command))
            self.application.add_handler(CommandHandler("sys", self._sys_command))
            self.application.add_handler(CommandHandler("bot", self._bot_command)) 
            self.application.add_handler(CommandHandler("legend", self._legend_command))
            self.application.add_handler(CommandHandler("echo", self._echo_command))
            info_print("OXOXOXOXOXOXOXOXOXOXOXOXOXO Enregistrement handler /annonce...")
            self.application.add_handler(CommandHandler("annonce", self._annonce_command))
            self.application.add_handler(CommandHandler("nodes", self._nodes_command))
            self.application.add_handler(CommandHandler("trafic", self._trafic_command))
            self.application.add_handler(CommandHandler("trace", self._trace_command))
            self.application.add_handler(CommandHandler("histo", self._histo_command))
            self.application.add_handler(CommandHandler("cpu", self._cpu_command))
            self.application.add_handler(CommandHandler("rebootg2", self._rebootg2_command))
            self.application.add_handler(CommandHandler("rebootpi", self._rebootpi_command))
            self.application.add_handler(CommandHandler("fullnodes", self._fullnodes_command))
            self.application.add_handler(CommandHandler("clearcontext", self._clearcontext_command))
            self.application.add_handler(CommandHandler("top", self._top_command))
            self.application.add_handler(CommandHandler("packets", self._packets_command))
            self.application.add_handler(CommandHandler("stats", self._stats_command))
            
            # Gestionnaire d'erreurs
            self.application.add_error_handler(self._error_handler)
            
            # Démarrer l'application
            await self.application.initialize()
            await self.application.start()
            # ✅ POLLING OPTIMISÉ - Réduire la charge CPU
            info_print("Bot Telegram en écoute (polling optimisé)...")
            
            await self.application.updater.start_polling(
                poll_interval=15.0,        # ✅ 10 secondes (économie CPU)
                timeout=30,                # 30s polling
                read_timeout=120,          # 2 minutes
                write_timeout=120,         # 2 minutes
                connect_timeout=120,       # 2 minutes (CRITIQUE)
                pool_timeout=120,          # 2 minutes
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            # ✅ Boucle d'attente OPTIMISÉE avec nettoyage des traces
            cleanup_counter = 0
            while self.running:
                await asyncio.sleep(60)  # 60 secondes

                cleanup_counter += 1
                if cleanup_counter % 6 == 0:  # CPU fix: Toutes les 3 mn
                    self.cleanup_expired_traces()

            # Arrêter proprement
            info_print("Arrêt du polling Telegram...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
        except Exception as e:
            error_print(f"Erreur démarrage Telegram: {e or 'Unknown error'}")
            error_print(traceback.format_exc())

    async def _graph_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /graph - À définir selon vos besoins"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /graph: {user.username}")
        
        # TODO: Implémenter selon vos besoins
        await update.message.reply_text("🚧 Commande /graph en cours d'implémentation")

    async def _shutdown(self):
        """Arrêter proprement le bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
    
    def _check_authorization(self, user_id):
        """Vérifier si l'utilisateur est autorisé"""
        if not TELEGRAM_AUTHORIZED_USERS:
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS
    
    # === COMMANDES TELEGRAM ===
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        info_print(f"📱 Telegram /start: {user.username} ({user.id})")
        
        welcome_msg = (
            f"🤖 Bot Meshtastic Bridge\n\n"
            f"Salut {user.first_name} !\n\n"
            f"Commandes:\n"
            f"• /bot - Chat IA\n"
            f"• /power - Batterie/solaire\n"
            f"• /weather - Météo Paris\n"
            f"• /rx [page]\n"
            f"• /sys \n"
            f"• /echo <msg>\n"
            f"• /nodes \n"
            f"• /fullnodes [jours]  Liste complète alphabétique (défaut: 30j)\n"
            f"• /trafic [heures] - Messages publics (défaut: 8h)\n"
            f"• /histo [type] [h] \n" 
            f"•         Types disponibles:\n"
            f"•         - all : tous les paquets (défaut)\n"
            f"•         - messages : messages texte uniquement\n"
            f"•         - pos : positions uniquement\n"
            f"•         - info : nodeinfo uniquement\n"
            f"•         - telemetry : télémétrie uniquement\n"
            f"• /top [h] [n] - Top talkers\n"  
            f"• /stats - Stats globales\n"     
            f"• /legend \n"
            f"• /cpu \n"
            f"• /help - Aide\n\n"
            f"Votre ID: {user.id}"
        )
        await update.message.reply_text(welcome_msg)

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help - Version détaillée pour Telegram"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /help: {user.username}")
        
        # Utiliser la version détaillée pour Telegram
        help_text = self.message_handler.format_help_telegram(user.id)
        
        # 🔍 DEBUG
        info_print(f"DEBUG help_text length: {len(help_text) if help_text else 'None'}")
        info_print(f"DEBUG help_text preview: {help_text[:100] if help_text else 'None'}")
        
        if not help_text or len(help_text.strip()) == 0:
            await update.message.reply_text("❌ Erreur: texte d'aide vide")
            return
        
        # Envoyer SANS Markdown d'abord
        try:
            await update.message.reply_text(help_text)
            info_print("✅ /help envoyé avec succès (sans Markdown)")
        except Exception as e:
            error_print(f"Erreur envoir /help : {e or 'Unknown error'}")
            await update.message.reply_text("❌ Erreur envoi aide")


    async def _power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power avec graphiques d'historique"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /power: {user.username}")
        
        # Extraire le nombre d'heures (optionnel, défaut 24)
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))  # Entre 1 et 48 heures
            except ValueError:
                hours = 24
        
        # Message 1 : Données actuelles
        response_current = await asyncio.to_thread(
            self.message_handler.esphome_client.parse_esphome_data
        )
        await update.message.reply_text(f"⚡ Power:\n{response_current}")
        
        # Message 2 : Graphiques d'historique
        response_graphs = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.message.reply_text(response_graphs)

    async def _graphs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /graphs pour afficher uniquement les graphiques d'historique"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Extraire le nombre d'heures (optionnel, défaut 24)
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))  # Entre 1 et 48 heures
            except ValueError:
                hours = 24
        
        info_print(f"📱 Telegram /graphs {hours}h: {user.username}")
        
        # Générer les graphiques
        response = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.message.reply_text(response)


    async def _rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx [page]"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        page = int(context.args[0]) if context.args else 1
        info_print(f"📱 Telegram /rx {page}: {user.username}")
        
        response = await asyncio.to_thread(
            self.message_handler.remote_nodes_client.get_tigrog2_paginated,
            page
        )
        await update.message.reply_text(response)
    
    async def _sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /sys: {user.username}")
        
        def get_sys_info():
            import subprocess
            system_info = []
            # ========================================
            # AJOUT : Uptime du bot
            # ========================================
            try:
                if hasattr(self.message_handler, 'router') and \
                   hasattr(self.message_handler.router, 'system_handler') and \
                   self.message_handler.router.system_handler.bot_start_time:
                    
                    bot_uptime_seconds = int(time.time() - self.message_handler.router.system_handler.bot_start_time)
                    
                    days = bot_uptime_seconds // 86400
                    hours = (bot_uptime_seconds % 86400) // 3600
                    minutes = (bot_uptime_seconds % 3600) // 60
                    
                    uptime_parts = []
                    if days > 0:
                        uptime_parts.append(f"{days}j")
                    if hours > 0:
                        uptime_parts.append(f"{hours}h")
                    if minutes > 0 or len(uptime_parts) == 0:
                        uptime_parts.append(f"{minutes}m")
                    
                    bot_uptime_str = " ".join(uptime_parts)
                    system_info.append(f"🤖 Bot: {bot_uptime_str}")
            except Exception as e:
                pass

            try:
                temp_cmd = ['vcgencmd', 'measure_temp']
                temp_result = subprocess.run(temp_cmd, capture_output=True, text=True, timeout=5)
                
                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_value = temp_output.split('=')[1].replace("'C", "°C")
                        system_info.append(f"🌡️ CPU: {temp_value}")
                else:
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        temp_celsius = int(f.read().strip()) / 1000.0
                        system_info.append(f"🌡️ CPU: {temp_celsius:.1f}°C")
            except Exception as e:
                system_info.append("🌡️ CPU: Error")
            
            try:
                uptime_cmd = ['uptime', '-p']
                uptime_result = subprocess.run(uptime_cmd, capture_output=True, text=True, timeout=5)
                if uptime_result.returncode == 0:
                    uptime_clean = uptime_result.stdout.strip().replace('up ', '')
                    system_info.append(f"⏱️ Up: {uptime_clean}")
            except Exception as e:
                pass
            
            try:
                with open('/proc/loadavg', 'r') as f:
                    loadavg = f.read().strip().split()
                    system_info.append(f"📊 Load: {loadavg[0]} {loadavg[1]} {loadavg[2]}")
            except Exception as e:
                pass
            
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                mem_total = mem_available = None
                for line in meminfo.split('\n'):
                    if line.startswith('MemTotal:'):
                        mem_total = int(line.split()[1])
                    elif line.startswith('MemAvailable:'):
                        mem_available = int(line.split()[1])
                
                if mem_total and mem_available:
                    mem_used = mem_total - mem_available
                    mem_percent = (mem_used / mem_total) * 100
                    system_info.append(f"💾 RAM: {mem_used//1024}MB/{mem_total//1024}MB ({mem_percent:.0f}%)")
            except Exception as e:
                pass
            
            return "🖥️ Système RPI5:\n" + "\n".join(system_info) if system_info else "❌ Erreur système"
        
        response = await asyncio.to_thread(get_sys_info)
        await update.message.reply_text(response)

    async def _legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /legend: {user.username}")
        legend = self.message_handler.format_legend()
        await update.message.reply_text(legend)

    async def _echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo <message> - Diffuser sur le mesh"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        if not context.args:
            await update.message.reply_text("Usage: /echo <message>")
            return

        echo_text = ' '.join(context.args)
        info_print(f"📱 Telegram /echo: {user.username} -> '{echo_text}'")

        # Message de confirmation immédiat
        status_msg = await update.message.reply_text("📤 Envoi en cours...")

        def send_echo():
            try:
                # Utiliser le mapping Telegram → Meshtastic
                mesh_identity = self._get_mesh_identity(user.id)

                if mesh_identity:
                    prefix = mesh_identity['short_name']
                    info_print(f"🔄 Echo avec identité mappée: {prefix}")
                else:
                    username = user.username or user.first_name
                    prefix = username[:4]
                    info_print(f"⚠️ Echo sans mapping: {prefix}")

                message = f"{prefix}: {echo_text}"
                
                # ✅ IMPORT SIMPLIFIÉ - Fonction au niveau module
                from safe_tcp_connection import send_text_to_remote
                import traceback
                
                info_print(f"📤 Envoi message vers {REMOTE_NODE_HOST}: '{message}'")
                
                # ✅ APPEL SIMPLIFIÉ - Plus besoin de SafeTCPConnection.method()
                success, result_msg = send_text_to_remote(
                    REMOTE_NODE_HOST, 
                    message,
                    wait_time=10  # Attendre 10s
                )
                
                info_print(f"📊 Résultat: success={success}, msg={result_msg}")
                
                if success:
                    return f"✅ Echo diffusé: {message}"
                else:
                    return f"❌ Échec: {result_msg}"
                    
            except Exception as e:
                error_print(f"❌ Exception send_echo: {e}")
                import traceback
                error_print(traceback.format_exc())
                return f"❌ Erreur echo: {str(e)[:50]}"

        # Exécuter la fonction dans un thread
        def execute_and_reply():
            try:
                result = send_echo()
                
                # Envoyer le résultat via l'event loop de Telegram
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit_text(result),
                self.loop
            ).result(timeout=5)
            
            except Exception as e:
                error_print(f"❌ Erreur execute_and_reply: {e}")
                try:
                    asyncio.run_coroutine_threadsafe(
                        status_msg.edit_text(f"❌ Erreur: {str(e)[:50]}"),
                        self.loop
                    ).result(timeout=5)
                except:
                    pass
        
            # Lancer dans un thread
            import threading
            thread = threading.Thread(target=execute_and_reply, daemon=True)
            thread.start()
            info_print(f"✅ Thread echo lancé: {thread.name}")

    async def _annonce_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /annonce <message> - Diffuser sur le mesh depuis le bot local"""
        info_print("OXOXOXOXOXOXOXOX/annonce appelée - DEBUT")
        user = update.effective_user
        info_print(f"User: {user.username} (ID: {user.id})") 
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        if not context.args:
            await update.message.reply_text("Usage: /annonce <message>")
            return

        annonce_text = ' '.join(context.args)
        info_print(f"📱 Telegram /annonce: {user.username} -> '{annonce_text}'")

        # Message de confirmation immédiat
        status_msg = await update.message.reply_text("📤 Envoi en cours...")

        def send_annonce():
            try:
                # Utiliser le mapping Telegram → Meshtastic
                mesh_identity = self._get_mesh_identity(user.id)

                if mesh_identity:
                    prefix = mesh_identity['short_name']
                    info_print(f"🔄 Annonce avec identité mappée: {prefix}")
                else:
                    username = user.username or user.first_name
                    prefix = username[:4]
                    info_print(f"⚠️ Annonce sans mapping: {prefix}")

                message = f"{prefix}: {annonce_text}"
                
                info_print(f"📤 Envoi annonce depuis bot local: '{message}'")
                
                interface = self.message_handler.interface

                if not interface:
                    error_print("❌ Interface locale non disponible")
                    return False, "❌ Interface non disponible"

                # Si c'est un SafeSerialConnection, récupérer l'interface réelle
                if hasattr(interface, 'get_interface'):
                    actual_interface = interface.get_interface()
                    if not actual_interface:
                        error_print("❌ Interface non connectée")
                        return False, "❌ Bot en cours de reconnexion"
                    interface = actual_interface

                info_print(f"✅ Interface trouvée: {type(interface).__name__}")

                # Envoyer directement en broadcast depuis le bot local
                interface.sendText(message, destinationId='^all')
                                
                info_print(f"✅ Annonce diffusée depuis bot local")
                return True, "✅ Annonce envoyée depuis le bot local"
                
            except Exception as e:
                error_print(f"Erreur /annonce Telegram: {e}")
                import traceback
                error_print(traceback.format_exc())
                return False, f"❌ Erreur: {str(e)[:50]}"

        # Exécuter l'envoi
        success, result_msg = await asyncio.to_thread(send_annonce)
        
        # Mettre à jour le message de status
        await status_msg.edit_text(result_msg)


    async def _cpu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /cpu - Monitoring CPU en temps réel"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        info_print(f"📱 Telegram /cpu: {user.username}")

        # Message initial
        await update.message.reply_text("📊 Monitoring CPU (10 secondes)...")

        def get_cpu_monitoring():
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())

                measurements = []
                for i in range(10):
                    cpu = process.cpu_percent(interval=0)
                    threads = len(process.threads())
                    mem = process.memory_info().rss / 1024 / 1024
                    measurements.append(f"[{i+1}/10] CPU: {cpu:.1f}% | Threads: {threads} | RAM: {mem:.0f}MB")

                # Moyenne finale
                cpu_avg = process.cpu_percent(interval=0)

                report = "📊 Monitoring CPU (10s):\n\n"
                report += "\n".join(measurements)
                report += f"\n\n✅ Moyenne: {cpu_avg:.1f}%"

                return report

            except ImportError:
                return "❌ Module psutil non installé\nInstaller: pip3 install psutil"
            except Exception as e:
                error_print(f"Erreur monitoring CPU: {e or 'Unknown error'}")
                return f"❌ Erreur: {str(e)[:100]}"

        response = await asyncio.to_thread(get_cpu_monitoring)
        await update.message.reply_text(response)

    async def _trafic_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /trafic pour historique messages publics"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        hours = 8
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(24, hours))
            except ValueError:
                hours = 8
        
        info_print(f"📱 Telegram /trafic {hours}h: {user.username}")
        
        def get_traffic():
            try:
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"
                report = self.message_handler.traffic_monitor.get_traffic_report(hours)
                debug_print(f"📊 Rapport généré: {len(report)} caractères")
                return report
            except Exception as e:
                error_print(f"Erreur get_trafic : {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(get_traffic)
        await update.message.reply_text(response)
    
    async def _nodes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /nodes - Affiche tous les nœuds de tigrog2"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /nodes: {user.username}")
        
        def get_nodes_list():
            try:
                nodes = self.message_handler.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
                if not nodes:
                    return f"❌ Aucun nœud trouvé sur {REMOTE_NODE_NAME}"
                
                nodes.sort(key=lambda x: x.get('snr', -999), reverse=True)
                lines = [f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} ({len(nodes)}):\n"]
                
                for node in nodes:
                    name = node.get('name', 'Unknown')
                    snr = node.get('snr', 0.0)
                    rssi = node.get('rssi', 0)
                    last_heard = node.get('last_heard', 0)
                    hops_away = node.get('hops_away', 0)  
                    
                    elapsed = int(time.time() - last_heard) if last_heard > 0 else 0
                    if elapsed < 60:
                        time_str = f"{elapsed}s"
                    elif elapsed < 3600:
                        time_str = f"{elapsed//60}m"
                    elif elapsed < 86400:
                        time_str = f"{elapsed//3600}h"
                    else:
                        time_str = f"{elapsed//86400}j"
                    
                    icon = "🟢" if snr >= 10 else "🟡" if snr >= 5 else "🟠" if snr >= 0 else "🔴"
                    lines.append(f"{icon} {name}: SNR {snr:.1f}dB ({time_str})")
                
                return "\n".join(lines)
            except Exception as e:
                return f"❌ Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(get_nodes_list)
        await update.message.reply_text(response)

    async def _fullnodes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /fullnodes - Liste complète alphabétique des nœuds"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        # Extraire le nombre de jours (optionnel, défaut 30)
        days = 30
        max_days = 365  # ✅ Limite raisonnable : 1 an
        
        if context.args and len(context.args) > 0:
            try:
                requested_days = int(context.args[0])
                if requested_days > max_days:
                    # ✅ Informer l'utilisateur si demande excessive
                    await update.message.reply_text(
                        f"⚠️ Maximum {max_days}j autorisé. Utilisation de {max_days}j."
                    )
                    days = max_days
                else:
                    days = max(1, requested_days)
            except ValueError:
                days = 30
        
        info_print(f"Telegram /fullnodes ({days}j): {user.username}")
        
        def get_full_nodes():
            try:
                return self.message_handler.remote_nodes_client.get_all_nodes_alphabetical(days)
            except Exception as e:
                error_print(f"Erreur get_full_nodes: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(get_full_nodes)
        
        # Telegram a une limite de 4096 caractères par message
        if len(response) > 4000:
            # Découper en plusieurs messages
            chunks = []
            lines = response.split('\n')
            current_chunk = []
            current_length = 0
            
            for line in lines:
                line_length = len(line) + 1  # +1 pour le \n
                if current_length + line_length > 4000:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_length = line_length
                else:
                    current_chunk.append(line)
                    current_length += line_length

            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            
            # Envoyer les chunks
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await asyncio.sleep(1)  # Éviter rate limiting
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)

    async def _rebootg2_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rebootg2 - Redémarrage tigrog2"""
        user = update.effective_user
        
        info_print("=" * 60)
        info_print("🔥 _rebootg2_command() APPELÉ !")
        info_print(f"   User Telegram: {user.username}")
        info_print(f"   User ID Telegram: {user.id}")
        info_print(f"   Arguments: {context.args}")
        info_print("=" * 60)
        
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Parser les arguments (mot de passe)
        password = context.args[0] if context.args else ""
        message_parts = ["/rebootg2", password] if password else ["/rebootg2"]
        
        info_print(f"📝 message_parts construit: {message_parts}")
        
        # Utiliser le mapping Telegram → Meshtastic
        mesh_identity = self._get_mesh_identity(user.id)
        
        info_print(f"🔍 Recherche mapping pour user.id={user.id}")
        
        if mesh_identity:
            sender_id = mesh_identity['node_id']
            sender_info = mesh_identity['display_name']
            info_print(f"✅ Mapping trouvé:")
            info_print(f"   → node_id: 0x{sender_id:08x} ({sender_id})")
            info_print(f"   → display_name: {sender_info}")
        else:
            sender_id = user.id & 0xFFFFFFFF
            sender_info = f"TG:{user.username}"
            info_print(f"⚠️ Pas de mapping, utilisation ID Telegram")
            info_print(f"   → sender_id: 0x{sender_id:08x} ({sender_id})")
            info_print(f"   → sender_info: {sender_info}")
        
        info_print("=" * 60)
        
        def reboot_g2():
            try:
                info_print(f"📞 Appel handle_rebootg2_command avec:")
                info_print(f"   sender_id: 0x{sender_id:08x}")
                info_print(f"   message_parts: {message_parts}")
                
                # ✅ FIX : Appeler via le router.system_handler
                response = self.message_handler.router.system_handler.handle_rebootg2_command(
                    sender_id, 
                    message_parts
                )
                
                info_print(f"📬 Réponse reçue: {response}")
                return response
            except Exception as e:
                error_print(f"Erreur dans reboot_g2: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(reboot_g2)
        info_print(f"📤 Envoi réponse à Telegram: {response}")
        await update.message.reply_text(response)

    async def _rebootpi_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rebootpi - Redémarrage Pi5"""
        user = update.effective_user
        
        info_print("=" * 60)
        info_print("🔥 _rebootpi_command() APPELÉ !")
        info_print(f"   User Telegram: {user.username}")
        info_print(f"   User ID Telegram: {user.id}")
        info_print(f"   Arguments: {context.args}")
        info_print("=" * 60)
        
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Parser les arguments (mot de passe)
        password = context.args[0] if context.args else ""
        message_parts = ["/rebootpi", password] if password else ["/rebootpi"]
        
        info_print(f"📝 message_parts construit: {message_parts}")
        
        # Utiliser le mapping Telegram → Meshtastic
        mesh_identity = self._get_mesh_identity(user.id)
        
        info_print(f"🔍 Recherche mapping pour user.id={user.id}")
        
        if mesh_identity:
            sender_id = mesh_identity['node_id']
            sender_info = mesh_identity['display_name']
            info_print(f"✅ Mapping trouvé:")
            info_print(f"   → node_id: 0x{sender_id:08x} ({sender_id})")
            info_print(f"   → display_name: {sender_info}")
        else:
            sender_id = user.id & 0xFFFFFFFF
            sender_info = f"TG:{user.username}"
            info_print(f"⚠️ Pas de mapping, utilisation ID Telegram")
            info_print(f"   → sender_id: 0x{sender_id:08x} ({sender_id})")
            info_print(f"   → sender_info: {sender_info}")
        
        info_print("=" * 60)
        
        def reboot_pi():
            try:
                info_print(f"📞 Appel handle_reboot_command avec:")
                info_print(f"   sender_id: 0x{sender_id:08x}")
                info_print(f"   message_parts: {message_parts}")
                
                # ✅ FIX : Appeler via le router.system_handler
                response = self.message_handler.router.system_handler.handle_reboot_command(
                    sender_id, 
                    message_parts
                )
                
                info_print(f"📬 Réponse reçue: {response}")
                return response
            except Exception as e:
                error_print(f"Erreur dans reboot_pi: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(reboot_pi)
        info_print(f"📤 Envoi réponse à Telegram: {response}")
        await update.message.reply_text(response)

    async def _bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /bot <question> - Chat avec l'IA
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Vérifier qu'il y a bien une question
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Usage: /bot <question>\n"
                "Exemple: /bot Quelle est la météo ?"
            )
            return
        
        # Reconstruire la question complète
        question = ' '.join(context.args)
        
        info_print(f"📱 Telegram /bot: {user.username} -> '{question[:50]}'")
        
        sender_id = user.id & 0xFFFFFFFF
        
        # Message d'attente pour les longues questions
        if len(question) > 100:
            await update.message.reply_text("🤔 Réflexion en cours...")
        
        def query_ai():
            return self.message_handler.llama_client.query_llama_telegram(question, sender_id)
        
        try:
            response = await asyncio.to_thread(query_ai)
            await update.message.reply_text(response)
        except Exception as e:
            error_print(f"Erreur /bot: {e}")
            await update.message.reply_text(f"❌ Erreur lors du traitement: {str(e)[:100]}")

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs"""
        error_print(f"❌ Erreur Telegram: {context.error}")
        error_print(traceback.format_exc())
        if update and hasattr(update, 'message') and update.message:
            await update.message.reply_text("❌ Erreur interne")
    
    async def _clearcontext_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /clearcontext - Nettoyer le contexte"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        info_print(f"📱 Telegram /clearcontext: {user.username}")

        # Utiliser le mapping
        mesh_identity = self._get_mesh_identity(user.id)
        node_id = mesh_identity['node_id'] if mesh_identity else (user.id & 0xFFFFFFFF)

        # Nettoyer le contexte
        if node_id in self.context_manager.conversation_context:
            msg_count = len(self.context_manager.conversation_context[node_id])
            del self.context_manager.conversation_context[node_id]
            await update.message.reply_text(f"✅ Contexte nettoyé ({msg_count} messages supprimés)")
        else:
            await update.message.reply_text("ℹ️ Pas de contexte actif")


    def send_alert(self, message):
        """
        Envoyer une alerte à tous les utilisateurs configurés
        Cette méthode peut être appelée depuis n'importe quel thread
        """
        info_print(f"📢 send_alert appelée avec message: {message[:50]}...")
        
        if not self.running:
            error_print("⚠️ Telegram non démarré (running=False)")
            return
        
        if not self.application:
            error_print("⚠️ Application Telegram non initialisée")
            return
        
        if not self.loop:
            error_print("⚠️ Event loop Telegram non disponible")
            return
        
        try:
            # Vérifier que l'event loop est toujours actif
            if self.loop.is_closed():
                error_print("⚠️ Event loop fermé")
                return
            
            # Créer une tâche asynchrone pour envoyer l'alerte
            future = asyncio.run_coroutine_threadsafe(
                self._send_alert_async(message),
                self.loop
            ).result(timeout=5) 
            
            # Attendre le résultat (avec timeout)
            try:
                future.result(timeout=10)
                info_print("✅ Alerte envoyée avec succès")
            except Exception as e:
                error_print(f"Erreur attente résultat: {e or 'Unknown error'}")
                
        except Exception as e:
            error_print(f"Erreur envoi alerte: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
    
    async def _send_alert_async(self, message):
        """Envoyer l'alerte de manière asynchrone à tous les utilisateurs"""
        try:
            debug_print(f"_send_alert_async démarré")
            
            if not self.alert_users:
                error_print("⚠️ Aucun utilisateur configuré pour les alertes")
                error_print(f"TELEGRAM_ALERT_USERS={TELEGRAM_ALERT_USERS}")
                error_print(f"TELEGRAM_AUTHORIZED_USERS={TELEGRAM_AUTHORIZED_USERS}")
                return
            
            info_print(f"Envoi alerte à {len(self.alert_users)} utilisateur(s)")
            
            for user_id in self.alert_users:
                try:
                    debug_print(f"Envoi à {user_id}...")
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=message
                    )
                    info_print(f"✅ Alerte envoyée à {user_id}")
                except Exception as e:
                    error_print(f"Erreur envoie alerte à {user_id}: {e or 'Unknown error'}")
                
                # Petit délai entre les envois pour éviter rate limiting
                await asyncio.sleep(0.5)
            
            debug_print("_send_alert_async terminé")
                
        except Exception as e:
            error_print(f"Erreur _send_alert_async: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
    
    def _find_node_by_short_name(self, identifier):
        """
        Trouver le node_id d'un nœud par plusieurs méthodes:
        - Short name: "tigro"
        - Long name: "tigro Tigro Network"
        - Hex ID: "3c7c", "!3c7c", "0x3c7c", "a76f40da", "!a76f40da"
        - Decimal ID: "15484", "2807920858"

        Returns:
            int: node_id si trouvé, None sinon
        """
        identifier = identifier.strip()
        identifier_lower = identifier.lower()

        # === ÉTAPE 1 : Détection si c'est un ID numérique ===
        node_id_candidate = None

        # Format: !hex (ex: !3c7c ou !a76f40da)
        if identifier.startswith('!'):
            try:
                node_id_candidate = int(identifier[1:], 16)
                debug_print(f"🔍 Format détecté: Hex avec ! → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # Format: 0xhex (ex: 0x3c7c)
        elif identifier_lower.startswith('0x'):
            try:
                node_id_candidate = int(identifier, 16)
                debug_print(f"🔍 Format détecté: Hex avec 0x → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # Format: hex pur (ex: 3c7c ou a76f40da)
        elif len(identifier) in [4, 8] and all(c in '0123456789abcdefABCDEF' for c in identifier):
            try:
                node_id_candidate = int(identifier, 16)
                debug_print(f"🔍 Format détecté: Hex pur → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # Format: decimal (ex: 15484 ou 2807920858)
        elif identifier.isdigit():
            try:
                node_id_candidate = int(identifier)
                debug_print(f"🔍 Format détecté: Décimal → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # === ÉTAPE 2 : Si c'est un ID, vérifier qu'il existe ===
        if node_id_candidate is not None:
            # Normaliser (32 bits)
            node_id_candidate = node_id_candidate & 0xFFFFFFFF

            # Vérifier dans la base locale
            if node_id_candidate in self.node_manager.node_names:
                node_name = self.node_manager.node_names[node_id_candidate]
                info_print(f"✅ Nœud trouvé par ID: {node_name} (!{node_id_candidate:08x})")
                return node_id_candidate

            # Vérifier dans l'interface
            try:
                if hasattr(self.message_handler.interface, 'nodes'):
                    nodes = self.message_handler.interface.nodes

                    for node_id, node_info in nodes.items():
                        # Normaliser node_id de l'interface
                        if isinstance(node_id, str):
                            if node_id.startswith('!'):
                                node_id_int = int(node_id[1:], 16) & 0xFFFFFFFF
                            else:
                                node_id_int = int(node_id, 16) & 0xFFFFFFFF
                        else:
                            node_id_int = int(node_id) & 0xFFFFFFFF

                        if node_id_int == node_id_candidate:
                            # Récupérer le nom
                            node_name = "Unknown"
                            if isinstance(node_info, dict) and 'user' in node_info:
                                user_info = node_info['user']
                                if isinstance(user_info, dict):
                                    node_name = user_info.get('longName') or user_info.get('shortName') or "Unknown"

                            info_print(f"✅ Nœud trouvé par ID dans interface: {node_name} (!{node_id_candidate:08x})")
                            return node_id_candidate
            except Exception as e:
                debug_print(f"Erreur recherche ID dans interface: {e}")

            # ID fourni mais nœud n'existe pas
            debug_print(f"⚠️ ID 0x{node_id_candidate:08x} fourni mais nœud inconnu")
            # Retourner quand même l'ID (peut être un nœud hors ligne mais valide)
            info_print(f"ℹ️ Utilisation de l'ID 0x{node_id_candidate:08x} (nœud peut être hors ligne)")
            return node_id_candidate

        # === ÉTAPE 3 : Recherche par nom (short ou long) ===
        # 3.1. Chercher dans la base locale
        for node_id, full_name in self.node_manager.node_names.items():
            full_name_lower = full_name.lower()

            # Extraire le short name (première partie avant espace)
            node_short = full_name.split()[0].lower() if ' ' in full_name else full_name_lower

            # Match sur short name OU long name
            if node_short == identifier_lower or full_name_lower == identifier_lower:
                info_print(f"✅ Nœud trouvé par nom dans base locale: {full_name} (!{node_id:08x})")
                return node_id

            # Match partiel sur long name (contient)
            if identifier_lower in full_name_lower and len(identifier) >= 3:
                info_print(f"✅ Nœud trouvé par nom partiel: {full_name} (!{node_id:08x})")
                return node_id

        # 3.2. Chercher dans l'interface en temps réel
        try:
            if hasattr(self.message_handler.interface, 'nodes'):
                nodes = self.message_handler.interface.nodes

                for node_id, node_info in nodes.items():
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            short = user_info.get('shortName', '').lower().strip()
                            long_name = user_info.get('longName', '').lower().strip()

                            # Match exact
                            if short == identifier_lower or long_name == identifier_lower:
                                # Convertir node_id
                                if isinstance(node_id, str):
                                    if node_id.startswith('!'):
                                        node_id_int = int(node_id[1:], 16) & 0xFFFFFFFF
                                    else:
                                        node_id_int = int(node_id, 16) & 0xFFFFFFFF
                                else:
                                    node_id_int = int(node_id) & 0xFFFFFFFF

                                display_name = long_name or short
                                info_print(f"✅ Nœud trouvé par nom dans interface: {display_name} (!{node_id_int:08x})")
                                return node_id_int

                            # Match partiel
                            if len(identifier) >= 3 and (identifier_lower in short or identifier_lower in long_name):
                                if isinstance(node_id, str):
                                    if node_id.startswith('!'):
                                        node_id_int = int(node_id[1:], 16) & 0xFFFFFFFF
                                    else:
                                        node_id_int = int(node_id, 16) & 0xFFFFFFFF
                                else:
                                    node_id_int = int(node_id) & 0xFFFFFFFF

                                display_name = long_name or short
                                info_print(f"✅ Nœud trouvé par nom partiel dans interface: {display_name} (!{node_id_int:08x})")
                                return node_id_int
        except Exception as e:
            debug_print(f"Erreur recherche nom dans interface: {e}")

        # === ÉTAPE 4 : Rien trouvé ===
        debug_print(f"❌ Nœud '{identifier}' introuvable")
        return None

    def cleanup_expired_traces(self):
        """Nettoyer les traces expirées (appelé périodiquement)"""
        try:
            current_time = time.time()
            expired = []

            for node_id, trace_data in self.pending_traces.items():
                if current_time - trace_data['timestamp'] > self.trace_timeout:
                    expired.append(node_id)

            for node_id in expired:
                trace_data = self.pending_traces[node_id]
                info_print(f"⏱️ Trace expirée pour {trace_data['full_name']}")

                # Notifier l'utilisateur Telegram
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.application.bot.send_message(
                            chat_id=trace_data['telegram_chat_id'],
                            text=f"⏱️ Timeout: Pas de réponse de {trace_data['full_name']}\n"
                                 f"Le nœud est peut-être hors ligne ou hors de portée."
                        ),
                        self.loop
                    ).result(timeout=5)  # ✅ FIX
                except Exception as e:
                    error_print(f"Erreur notification timeout: {e or 'Unknown error'}")

                del self.pending_traces[node_id]

            if expired:
                debug_print(f"🧹 {len(expired)} traces expirées nettoyées")

        except Exception as e:
            error_print(f"Erreur cleanup_expired_traces: {e or 'Unknown error'}")


    
    def handle_trace_response(self, from_id, message_text):
        """
        Traiter une réponse de traceroute depuis le mesh
        VERSION AVEC DEBUG INTENSIF
        """
        try:
            info_print("=" * 60)
            info_print("🔍 DEBUG handle_trace_response() appelé")
            info_print(f"   from_id: {from_id} (0x{from_id:08x})")
            info_print(f"   message length: {len(message_text)} chars")
            info_print(f"   message preview: {message_text[:100]}...")
            info_print("=" * 60)
            
            # Debug: Afficher l'état des traces en attente
            info_print(f"📋 Traces en attente: {len(self.pending_traces)}")
            for node_id, trace_data in self.pending_traces.items():
                info_print(f"   - 0x{node_id:08x} ({trace_data['full_name']}) depuis {time.time() - trace_data['timestamp']:.1f}s")
            
            # Vérifier si c'est une réponse attendue
            if from_id not in self.pending_traces:
                info_print(f"❌ from_id 0x{from_id:08x} NOT in pending_traces")
                info_print(f"   Ce n'est PAS une réponse de trace attendue")
                return False
            
            info_print(f"✅ from_id 0x{from_id:08x} IS in pending_traces!")
            
            # Vérifier que le message ressemble à un traceroute
            trace_indicators = [
                "Traceroute",
                "🔍",
                "Hops:",
                "Route:",
                "Signal:",
                "hopStart:",
                "hopLimit:"
            ]
            
            info_print("🔍 Vérification des indicateurs de traceroute:")
            matches = []
            for indicator in trace_indicators:
                if indicator in message_text:
                    matches.append(indicator)
                    info_print(f"   ✅ Trouvé: '{indicator}'")
                else:
                    info_print(f"   ❌ Absent: '{indicator}'")
            
            if not matches:
                info_print(f"⚠️ Message de 0x{from_id:08x} ne contient AUCUN indicateur de trace")
                info_print(f"   Message complet:\n{message_text}")
                return False
            
            info_print(f"✅ Message contient {len(matches)} indicateurs de trace: {matches}")
            
            # C'est bien une réponse de trace !
            trace_data = self.pending_traces[from_id]
            chat_id = trace_data['telegram_chat_id']
            node_name = trace_data['full_name']
            elapsed_time = time.time() - trace_data['timestamp']
            
            info_print(f"🎯 RÉPONSE DE TRACE CONFIRMÉE!")
            info_print(f"   Node: {node_name}")
            info_print(f"   Chat ID: {chat_id}")
            info_print(f"   Temps écoulé: {elapsed_time:.1f}s")
            
            # Formater le message pour Telegram
            telegram_message = (
                f"📊 **Traceroute reçu de {node_name}**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{message_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱️ Temps de réponse: {elapsed_time:.1f}s"
            )
            
            info_print(f"📤 Envoi à Telegram...")
            info_print(f"   Chat ID: {chat_id}")
            info_print(f"   Message length: {len(telegram_message)} chars")
            
            # Envoyer à Telegram
            try:
                asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_message(
                        chat_id=chat_id,
                        text=telegram_message,
                        parse_mode='Markdown'
                    ),
                    self.loop
                ).result(timeout=10)  # Attendre max 10s
                
                info_print(f"✅ Message envoyé avec succès à Telegram!")
                
            except Exception as telegram_error:
                error_print(f"❌ ERREUR envoi Telegram: {telegram_error}")
                error_print(traceback.format_exc())
            
            # Supprimer la trace de la liste
            del self.pending_traces[from_id]
            info_print(f"🧹 Trace supprimée de pending_traces")
            info_print(f"📋 Traces restantes: {len(self.pending_traces)}")
            
            info_print("=" * 60)
            info_print("✅ handle_trace_response() terminé avec succès")
            info_print("=" * 60)
            
            return True
            
        except Exception as e:
            error_print(f"Erreur dans handle_trace_response: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
            return False


    def test_trace_system(self):
        """
        Tester le système de traceroute
        À appeler depuis le debug interface ou au démarrage
        """
        info_print("=" * 60)
        info_print("🧪 TEST SYSTÈME TRACEROUTE")
        info_print("=" * 60)
        
        # Test 1: Telegram disponible
        info_print("Test 1: Telegram disponible")
        info_print(f"   running: {self.running}")
        info_print(f"   application: {self.application is not None}")
        info_print(f"   loop: {self.loop is not None}")
        
        # Test 2: Message handler disponible
        info_print("Test 2: Message handler")
        info_print(f"   message_handler: {self.message_handler is not None}")
        if self.message_handler:
            info_print(f"   interface: {self.message_handler.interface is not None}")
        
        # Test 3: Node manager
        info_print("Test 3: Node manager")
        info_print(f"   node_manager: {self.node_manager is not None}")
        if self.node_manager:
            info_print(f"   Nœuds connus: {len(self.node_manager.node_names)}")
        
        # Test 4: Pending traces
        info_print("Test 4: Pending traces")
        info_print(f"   Dict initialisé: {hasattr(self, 'pending_traces')}")
        info_print(f"   Traces actuelles: {len(self.pending_traces)}")
        
        # Test 5: Timeout
        info_print("Test 5: Configuration")
        info_print(f"   trace_timeout: {self.trace_timeout}s")
        
        info_print("=" * 60)
        info_print("✅ Test système terminé")
        info_print("=" * 60)

    async def _trace_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /trace [short_id] - Traceroute mesh actif
        VERSION AVEC FIX THREAD
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /trace: {user.username}")
        
        # Vérifier si un short_id est fourni
        args = context.args
        
        if not args or len(args) == 0:
            # === MODE PASSIF : Trace depuis bot vers utilisateur ===
            mesh_identity = self._get_mesh_identity(user.id)
            
            if mesh_identity:
                node_id = mesh_identity['node_id']
                display_name = mesh_identity['display_name']
            else:
                node_id = user.id & 0xFFFFFFFF
                display_name = user.username or user.first_name
            
            response_parts = []
            response_parts.append(f"🔍 Traceroute Telegram → {display_name}")
            response_parts.append("")
            response_parts.append("✅ Connexion DIRECTE")
            response_parts.append("📱 Via: Internet/Telegram")
            response_parts.append("🔒 Protocol: HTTPS/TLS")
            response_parts.append("")
            response_parts.append(f"Route: Telegram → bot")
            response_parts.append("")
            response_parts.append("ℹ️ Note:")
            response_parts.append("Les commandes Telegram ne passent")
            response_parts.append("pas par le réseau mesh LoRa.")
            response_parts.append("")
            response_parts.append("💡 Astuce:")
            response_parts.append("Utilisez /trace <short_id> pour tracer")
            response_parts.append("depuis un nœud mesh vers le bot.")
            
            await update.message.reply_text("\n".join(response_parts))
            return
        
        # === MODE ACTIF : Trace depuis nœud mesh vers bot ===
        target_short_name = args[0].strip()
        
        info_print(f"🎯 Traceroute actif demandé vers: {target_short_name}")
        
        # ===================================================================
        # FIX: Créer une fonction séparée au lieu d'une nested function
        # pour éviter les problèmes de scope dans le thread
        # ===================================================================
        
        info_print("🔄 Préparation du thread...")
        
        try:
            # Lancer dans un thread avec wrapper
            trace_thread = threading.Thread(
                target=self._execute_active_trace_wrapper,
                args=(target_short_name, update.effective_chat.id, user.username),
                daemon=True
            )
            
            info_print("▶️  Lancement du thread...")
            trace_thread.start()
            info_print("✅ Thread lancé avec succès")
            
        except Exception as thread_error:
            error_print(f"❌ ERREUR lancement thread: {thread_error}")
            error_print(traceback.format_exc())
            await update.message.reply_text(f"❌ Erreur technique: {str(thread_error)[:100]}")


        def _execute_active_trace_wrapper(self, target_short_name, chat_id, username):
            """
            Wrapper pour execute_active_trace qui capture TOUTES les exceptions
            Fonction de classe (pas nested) pour éviter les problèmes de scope
            """
            info_print("=" * 60)
            info_print("🚀 _execute_active_trace_wrapper démarré")
            info_print(f"   Target: {target_short_name}")
            info_print(f"   Chat ID: {chat_id}")
            info_print(f"   User: {username}")
            info_print("=" * 60)
            
            try:
                self._execute_active_trace(target_short_name, chat_id, username)
            except Exception as e:
                error_print(f"Erreur non catchée dans wreappe: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                
                # Notifier l'utilisateur
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.application.bot.send_message(
                            chat_id=chat_id,
                            text=f"❌ Erreur interne: {str(e)[:100]}"
                        ),
                        self.loop
                    ).result(timeout=5)
                except Exception as e:
                    error_print("❌ Impossible de notifier l'utilisateur")

    def _execute_active_trace(self, target_short_name, chat_id, username):
        """Traceroute avec timeout approprié"""
        try:
            info_print("=" * 60)
            info_print("🚀 Traceroute NATIF Meshtastic démarré")
            info_print(f"   Target: {target_short_name}")
            info_print("=" * 60)

            # 1. Trouver le node_id
            info_print("🔍 Étape 1: Recherche du node_id...")
            
            try:
                target_node_id = self._find_node_by_short_name(target_short_name)
            except Exception as find_error:
                error_print(f"❌ ERREUR _find_node_by_short_name: {find_error}")
                error_print(traceback.format_exc())
                
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.application.bot.send_message(
                            chat_id=chat_id,
                            text=f"❌ Erreur recherche nœud: {str(find_error)[:100]}"
                        ),
                        self.loop
                    ).result(timeout=5)
                except:
                    pass
                return
            
            target_full_name = self.node_manager.get_node_name(target_node_id)
            info_print(f"✅ Nœud trouvé: {target_full_name}")
            info_print(f"   Node ID: 0x{target_node_id:08x} ({target_node_id})")

            if not target_node_id:
                error_print(f"❌ Nœud '{target_short_name}' introuvable")
                asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Nœud '{target_short_name}' introuvable\n"
                             f"Utilisez /nodes pour voir la liste"
                    ),
                    self.loop
                ).result(timeout=5)

            info_print(f"✅ Trace enregistrée")
            # Enregistrer la trace
            self.pending_traces[node_id] = {
                'telegram_chat_id': chat_id,
                'timestamp': time.time(),
                'full_name': f"{target_short_name} (!{node_id:08x})"
            }

            # Lancer le traceroute avec timeout plus long
            with tcp_manager.get_connection(REMOTE_NODE_HOST, timeout=45) as remote_interface:
                trace_msg = f"/trace !{node_id:08x}"
                remote_interface.sendText(trace_msg)

                # Message de confirmation
                asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"🎯 Traceroute lancé vers {target_short_name}\n"
                             f"⏳ Attente réponse (max 60s)..."
                    ),
                    self.loop
                ).result(timeout=5)  # ✅ FIX

        except Exception as e:
            error_print(f"Erreur trace active: {e or 'Unknown error'}")
            asyncio.run_coroutine_threadsafe(
                self.application.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Erreur technique: {str(e)[:100]}"
                ),
                self.loop
            ).result(timeout=5)  # ✅ FIX
        
    async def _trace_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /trace [short_id] - Traceroute mesh actif
        VERSION AVEC FIX THREAD
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /trace: {user.username}")
        
        # Vérifier si un short_id est fourni
        args = context.args
        
        if not args or len(args) == 0:
            # === MODE PASSIF : Trace depuis bot vers utilisateur ===
            mesh_identity = self._get_mesh_identity(user.id)
            
            if mesh_identity:
                node_id = mesh_identity['node_id']
                display_name = mesh_identity['display_name']
            else:
                node_id = user.id & 0xFFFFFFFF
                display_name = user.username or user.first_name
            
            response_parts = []
            response_parts.append(f"🔍 Traceroute Telegram → {display_name}")
            response_parts.append("")
            response_parts.append("✅ Connexion DIRECTE")
            response_parts.append("📱 Via: Internet/Telegram")
            response_parts.append("🔒 Protocol: HTTPS/TLS")
            response_parts.append("")
            response_parts.append(f"Route: Telegram → bot")
            response_parts.append("")
            response_parts.append("ℹ️ Note:")
            response_parts.append("Les commandes Telegram ne passent")
            response_parts.append("pas par le réseau mesh LoRa.")
            response_parts.append("")
            response_parts.append("💡 Astuce:")
            response_parts.append("Utilisez /trace <short_id> pour tracer")
            response_parts.append("depuis un nœud mesh vers le bot.")
            
            await update.message.reply_text("\n".join(response_parts))
            return
        
        # === MODE ACTIF : Trace depuis nœud mesh vers bot ===
        target_short_name = args[0].strip()
        
        info_print(f"🎯 Traceroute actif demandé vers: {target_short_name}")
        
        # ===================================================================
        # FIX: Créer une fonction séparée au lieu d'une nested function
        # pour éviter les problèmes de scope dans le thread
        # ===================================================================
        
        info_print("🔄 Préparation du thread...")
        
        try:
            # Lancer dans un thread avec wrapper
            trace_thread = threading.Thread(
                target=self._execute_active_trace_wrapper,
                args=(target_short_name, update.effective_chat.id, user.username),
                daemon=True
            )
            
            info_print("▶️  Lancement du thread...")
            trace_thread.start()
            info_print("✅ Thread lancé avec succès")
            
        except Exception as thread_error:
            error_print(f"❌ ERREUR lancement thread: {thread_error}")
            error_print(traceback.format_exc())
            await update.message.reply_text(f"❌ Erreur technique: {str(thread_error)[:100]}")


    def _execute_active_trace_wrapper(self, target_short_name, chat_id, username):
        """
        Wrapper pour execute_active_trace qui capture TOUTES les exceptions
        Fonction de classe (pas nested) pour éviter les problèmes de scope
        """
        info_print("=" * 60)
        info_print("🚀 _execute_active_trace_wrapper démarré")
        info_print(f"   Target: {target_short_name}")
        info_print(f"   Chat ID: {chat_id}")
        info_print(f"   User: {username}")
        info_print("=" * 60)
        
        try:
            self._execute_active_trace(target_short_name, chat_id, username)
        except Exception as e:
            error_print(f"Erreur non catchée dans wrapper trace: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
            
            # Notifier l'utilisateur
            try:
                asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Erreur interne: {str(e)[:100]}"
                    ),
                    self.loop
                ).result(timeout=5)
            except Exception as e:
                error_print("❌ Impossible de notifier l'utilisateur")

    def handle_traceroute_response(self, packet, decoded):
        """
        Traiter une réponse TRACEROUTE_APP native Meshtastic
        """
        try:
            from_id = packet.get('from', 0)

            info_print(f"🔍 Traitement TRACEROUTE_APP de 0x{from_id:08x}")

            # Vérifier si c'est une réponse attendue
            if from_id not in self.pending_traces:
                info_print(f"⚠️  Traceroute de 0x{from_id:08x} non attendu")
                return

            trace_data = self.pending_traces[from_id]
            chat_id = trace_data['telegram_chat_id']
            node_name = trace_data['full_name']

            info_print(f"✅ Réponse de traceroute attendue trouvée: {node_name}")

            # Parser la réponse traceroute
            route = []

            # Le payload contient la route sous forme de RouteDiscovery protobuf
            if 'payload' in decoded:
                payload = decoded['payload']

                try:
                    # Décoder le protobuf RouteDiscovery
                    from meshtastic import mesh_pb2
                    route_discovery = mesh_pb2.RouteDiscovery()
                    route_discovery.ParseFromString(payload)

                    info_print(f"📋 Route découverte:")
                    for i, node_id in enumerate(route_discovery.route):
                        node_name_route = self.node_manager.get_node_name(node_id)
                        route.append({
                            'node_id': node_id,
                            'name': node_name_route,
                            'position': i
                        })
                        info_print(f"   {i}. {node_name_route} (!{node_id:08x})")

                except Exception as parse_error:
                    error_print(f"❌ Erreur parsing RouteDiscovery: {parse_error}")
                    # Fallback: afficher le payload brut
                    info_print(f"Payload brut: {payload.hex()}")

            # Construire le message pour Telegram
            if route:
                route_parts = []
                route_parts.append(f"📊 **Traceroute vers {node_name}**")
                route_parts.append(f"━━━━━━━━━━━━━━━━━━━━")
                route_parts.append("")
                route_parts.append(f"🎯 Route complète ({len(route)} nœuds):")
                route_parts.append("")

                for i, hop in enumerate(route):
                    hop_name = hop['name']
                    hop_id = hop['node_id']

                    if i == 0:
                        icon = "🏁"  # Départ (bot)
                    elif i == len(route) - 1:
                        icon = "🎯"  # Arrivée (destination)
                    else:
                        icon = "🔀"  # Relay intermédiaire

                    route_parts.append(f"{icon} **Hop {i}:** {hop_name}")
                    route_parts.append(f"   ID: `!{hop_id:08x}`")

                    if i < len(route) - 1:
                        route_parts.append("   ⬇️")

                route_parts.append("")
                route_parts.append(f"📏 **Distance:** {len(route) - 1} hop(s)")

                elapsed = time.time() - trace_data['timestamp']
                route_parts.append(f"⏱️ **Temps:** {elapsed:.1f}s")

                telegram_message = "\n".join(route_parts)
            else:
                # Pas de route décodée
                telegram_message = (
                    f"📊 **Traceroute vers {node_name}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚠️ Route non décodable\n"
                    f"Le nœud a répondu mais le format n'est pas standard.\n\n"
                    f"ℹ️ Cela peut arriver avec certaines versions du firmware."
                )

            # Envoyer à Telegram
            info_print(f"📤 Envoi du traceroute à Telegram...")
            try:
                asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_message(
                        chat_id=chat_id,
                        text=telegram_message,
                        parse_mode='Markdown'
                    ),
                    self.loop
                ).result(timeout=10)
            except Exception as send_error:
                error_print(f"Erreur envoi Telegram: {send_error}")

            info_print(f"✅ Traceroute envoyé à Telegram")

            # Supprimer la trace
            del self.pending_traces[from_id]
            info_print(f"🧹 Trace supprimée")

        except Exception as e:
            error_print(f"Erreur handle_traceroute_response;: {e or 'Unknown error'}")
            error_print(traceback.format_exc())

    # Ajouter ces méthodes dans la classe TelegramIntegration
    
    async def _top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /top [heures] [nombre]
        Affiche les top talkers avec statistiques détaillées
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Parser les arguments
        hours = 24  # Défaut pour Telegram
        top_n = 10  # Top 10 par défaut
        
        args = context.args
        if args and len(args) > 0:
            try:
                hours = int(args[0])
                hours = max(1, min(168, hours))  # Max 7 jours
            except ValueError:
                hours = 24
        
        if args and len(args) > 1:
            try:
                top_n = int(args[1])
                top_n = max(3, min(20, top_n))  # Entre 3 et 20
            except ValueError:
                top_n = 10
        
        info_print(f"📱 Telegram /top {hours}h top{top_n}: {user.username}")
        
        # Message d'attente
        await update.message.reply_text(f"📊 Calcul des statistiques ({hours}h)...")
        
        def get_detailed_stats():
            try:
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"
                
                # Rapport détaillé des top talkers
                report = self.message_handler.traffic_monitor.get_top_talkers_report(hours, top_n)
                
                # Ajouter le pattern d'activité si demandé sur 24h ou moins
                if hours <= 24:
                    pattern = self.message_handler.traffic_monitor.get_activity_pattern(hours)
                    if pattern:
                        report += "\n\n" + pattern
                
                return report
                
            except Exception as e:
                error_print(f"Erreur get_detailed_stats: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"
        
        # Générer le rapport
        response = await asyncio.to_thread(get_detailed_stats)
        
        # Si le message est trop long, le diviser
        if len(response) > 4000:
            # Diviser intelligemment par sections
            sections = response.split('\n\n')
            current_msg = ""
            
            for section in sections:
                if len(current_msg) + len(section) + 2 < 4000:
                    if current_msg:
                        current_msg += "\n\n"
                    current_msg += section
                else:
                    if current_msg:
                        await update.message.reply_text(current_msg)
                        await asyncio.sleep(0.5)
                    current_msg = section
            
            if current_msg:
                await update.message.reply_text(current_msg)
        else:
            await update.message.reply_text(response)
    
    async def _stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /stats - Statistiques globales du réseau
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /stats: {user.username}")
        
        def get_global_stats():
            try:
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"
                
                tm = self.message_handler.traffic_monitor
                
                lines = []
                lines.append("📊 **STATISTIQUES RÉSEAU MESH**")
                lines.append("=" * 40)
                
                # Messages dernières 24h
                msg_24h = tm.get_message_count(24)
                msg_1h = tm.get_message_count(1)
                msg_total = len(tm.public_messages)
                
                lines.append(f"\n**📨 Messages:**")
                lines.append(f"• Dernière heure: {msg_1h}")
                lines.append(f"• Dernières 24h: {msg_24h}")
                lines.append(f"• En mémoire: {msg_total}")
                
                # Nœuds actifs
                active_nodes_1h = set()
                active_nodes_24h = set()
                current_time = time.time()
                
                for msg in tm.public_messages:
                    if msg['timestamp'] >= current_time - 3600:
                        active_nodes_1h.add(msg['from_id'])
                    if msg['timestamp'] >= current_time - 86400:
                        active_nodes_24h.add(msg['from_id'])
                
                lines.append(f"\n**👥 Nœuds actifs:**")
                lines.append(f"• Dernière heure: {len(active_nodes_1h)}")
                lines.append(f"• Dernières 24h: {len(active_nodes_24h)}")
                lines.append(f"• Total connus: {len(self.node_manager.node_names)}")
               
                # ✅ FIX : Vérifier que les stats existent avant de les afficher
                if hasattr(tm, 'global_stats'):
                    busiest_hour = tm.global_stats.get('busiest_hour')
                    quietest_hour = tm.global_stats.get('quietest_hour')
                    
                    if busiest_hour and quietest_hour:
                        lines.append(f"\n⏰ Patterns:")
                        lines.append(f"• Heure de pointe: {busiest_hour}")
                        lines.append(f"• Heure creuse: {quietest_hour}")
                
                # Top 3 des dernières heures
                quick_stats = tm.get_quick_stats()
                if quick_stats and "TOP" in quick_stats:
                    lines.append(f"\n**🏆 Actifs récents (3h):**")
                    for line in quick_stats.split('\n')[1:]:  # Skip header
                        lines.append(f"• {line}")
                
                # Uptime du monitoring
                uptime_seconds = current_time - tm.global_stats.get('last_reset', current_time)
                uptime_hours = int(uptime_seconds / 3600)
                lines.append(f"\n**🕐 Monitoring:**")
                lines.append(f"• Uptime: {uptime_hours}h")
                lines.append(f"• Dernière réinitialisation: {datetime.fromtimestamp(tm.global_stats.get('last_reset', 0)).strftime('%Y-%m-%d %H:%M')}")
                
                return "\n".join(lines)
                
            except Exception as e:
                error_print(f"Erreur stats globales: {e or 'Unknown error'}")
                return f"❌ Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(get_global_stats)
        await update.message.reply_text(response, parse_mode='Markdown')

    async def _top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /top [heures] [nombre]
        Version améliorée avec tous les types de paquets
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        # Parser les arguments
        hours = 24  # Défaut pour Telegram
        top_n = 10  # Top 10 par défaut
        
        args = context.args
        if args and len(args) > 0:
            try:
                hours = int(args[0])
                hours = max(1, min(168, hours))
            except ValueError:
                hours = 24
        
        if args and len(args) > 1:
            try:
                top_n = int(args[1])
                top_n = max(3, min(20, top_n))
            except ValueError:
                top_n = 10
        
        info_print(f"📱 Telegram /top {hours}h top{top_n}: {user.username}")
        
        # Message d'attente
        await update.message.reply_text(f"📊 Calcul des statistiques complètes ({hours}h)...")
        
        def get_detailed_stats():
            try:
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"
                
                # Rapport détaillé avec types de paquets
                report = self.message_handler.traffic_monitor.get_top_talkers_report(
                    hours, top_n, include_packet_types=True
                )
                
                # Ajouter le résumé des types de paquets
                packet_summary = self.message_handler.traffic_monitor.get_packet_type_summary(hours)
                if packet_summary:
                    report += "\n\n" + packet_summary
                
                return report
                
            except Exception as e:
                error_print(f"Erreur get_detailed_stats: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"
        
        # Générer le rapport
        response = await asyncio.to_thread(get_detailed_stats)
        
        # Si le message est trop long, le diviser
        if len(response) > 4000:
            sections = response.split('\n\n')
            current_msg = ""
            
            for section in sections:
                if len(current_msg) + len(section) + 2 < 4000:
                    if current_msg:
                        current_msg += "\n\n"
                    current_msg += section
                else:
                    if current_msg:
                        await update.message.reply_text(current_msg)
                        await asyncio.sleep(0.5)
                    current_msg = section
            
            if current_msg:
                await update.message.reply_text(current_msg)
        else:
            await update.message.reply_text(response)
    
    async def _packets_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /packets [heures]
        Affiche la distribution des types de paquets
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        hours = 1
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(168, hours))
            except ValueError:
                hours = 1
        
        info_print(f"📱 Telegram /packets {hours}h: {user.username}")
        
        def get_packet_stats():
            try:
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"
                
                tm = self.message_handler.traffic_monitor
                
                # Résumé détaillé des types
                summary = tm.get_packet_type_summary(hours)
                
                # Ajouter les stats réseau
                lines = [summary, "\n🌐 **Statistiques réseau:**"]
                lines.append(f"• Paquets directs: {tm.network_stats['packets_direct']}")
                lines.append(f"• Paquets relayés: {tm.network_stats['packets_relayed']}")
                
                if tm.network_stats['max_hops_seen'] > 0:
                    lines.append(f"• Max hops vus: {tm.network_stats['max_hops_seen']}")
                
                if tm.network_stats['avg_rssi'] != 0:
                    lines.append(f"• RSSI moyen: {tm.network_stats['avg_rssi']:.1f}dBm")
                
                if tm.network_stats['avg_snr'] != 0:
                    lines.append(f"• SNR moyen: {tm.network_stats['avg_snr']:.1f}dB")
                
                # Total de données
                total_kb = tm.global_packet_stats['total_bytes'] / 1024
                lines.append(f"\n📊 **Volume total:**")
                lines.append(f"• {tm.global_packet_stats['total_packets']} paquets")
                lines.append(f"• {total_kb:.1f}KB de données")
                
                return "\n".join(lines)
                
            except Exception as e:
                error_print(f"Erreur packet stats: {e or 'Unknown error'}")
                return f"❌ Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(get_packet_stats)
        await update.message.reply_text(response)        

    async def _histo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /histo [type] [heures] - Histogrammes de paquets

        Usage:
            /histo           - Vue d'ensemble
            /histo pos       - Détails POSITION
            /histo tele      - Détails TELEMETRY
            /histo node      - Détails NODEINFO
            /histo text      - Détails TEXT
            /histo pos 12    - POSITION sur 12h
        """
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        # Parser les arguments
        args = context.args
        packet_type = 'ALL'  # Par défaut: vue d'ensemble
        hours = 24

        # Argument 1: type de paquet (optionnel)
        if args and len(args) > 0:
            packet_type = args[0].strip().upper()
            # Valider le type
            if packet_type not in ['ALL', 'POS', 'TELE', 'NODE', 'TEXT']:
                await update.message.reply_text(
                    f"❌ Type inconnu: {args[0]}\n"
                    f"Types disponibles: pos, tele, node, text"
                )
                return

        # Argument 2: heures (optionnel)
        if args and len(args) > 1:
            try:
                hours = int(args[1])
                hours = max(1, min(48, hours))  # Entre 1 et 48h
            except ValueError:
                hours = 24

        info_print(f"📱 Telegram /histo {packet_type} {hours}h: {user.username}")

        def get_histogram():
            """Fonction synchrone pour obtenir l'histogramme"""
            try:
                # Utiliser node_manager pour générer l'histogramme
                return self.node_manager.get_packet_histogram_single(packet_type, hours)
            except Exception as e:
                error_print(f"Erreur get_histogram: {e}")
                import traceback
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:50]}"

        # Exécuter dans un thread séparé
        try:
            histogram = await asyncio.to_thread(get_histogram)
            await update.message.reply_text(histogram)

        except Exception as e:
            error_print(f"Erreur /histo: {e}")
            import traceback
            error_print(traceback.format_exc())
            await update.message.reply_text(f"❌ Erreur: {str(e)[:50]}")

    async def _weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /weather: {user.username}")
        
        # Utiliser directement le module utils.weather
        from utils_weather import get_weather_data
        
        try:
            weather = await asyncio.to_thread(get_weather_data)
            await update.message.reply_text(weather)
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:50]}")

                    
