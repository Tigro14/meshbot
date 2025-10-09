#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'intégration Telegram dans le bot Meshtastic - INTÉGRATION COMPLÈTE
Gère directement l'API Telegram sans fichiers queue
"""

import time
import threading
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
        self.telegram_thread = threading.Thread(
    target=self._run_telegram_bot, daemon=True)
        self.telegram_thread.start()
        info_print("🤖 Bot Telegram démarré en thread séparé")

    def stop(self):
        """Arrêter le bot Telegram"""
        self.running = False
        if self.loop and self.application:
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
            except:
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
            error_print(f"Erreur bot Telegram: {e}")
            import traceback
            error_print(traceback.format_exc())
        finally:
            # Nettoyer l'event loop
            try:
                self.loop.close()
            except:
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
            self.application.add_handler(CommandHandler("graphs", self._graphs_command))
            self.application.add_handler(CommandHandler("rx", self._rx_command))
            self.application.add_handler(CommandHandler("sys", self._sys_command))
            self.application.add_handler(CommandHandler("legend", self._legend_command))
            self.application.add_handler(CommandHandler("echo", self._echo_command))
            self.application.add_handler(CommandHandler("nodes", self._nodes_command))
            self.application.add_handler(CommandHandler("trafic", self._trafic_command))
            self.application.add_handler(CommandHandler("trace", self._trace_command))
            self.application.add_handler(CommandHandler("cpu", self._cpu_command))
            self.application.add_handler(CommandHandler("rebootg2", self._rebootg2_command))
            self.application.add_handler(CommandHandler("rebootpi", self._rebootpi_command))
            self.application.add_handler(CommandHandler("fullnodes", self._fullnodes_command))
            self.application.add_handler(CommandHandler("clearcontext", self._clearcontext_command))
            
            # Handler pour messages texte
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            
            # Gestionnaire d'erreurs
            self.application.add_error_handler(self._error_handler)
            
            # Démarrer l'application
            await self.application.initialize()
            await self.application.start()
            # ✅ POLLING OPTIMISÉ - Réduire la charge CPU
            info_print("Bot Telegram en écoute (polling optimisé)...")
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                poll_interval=5.0,        # ✅ 5 secondes au lieu de 2
                timeout=10,                # ✅ Timeout plus court
                read_timeout=10,           # ✅ Timeout lecture
                write_timeout=10,          # ✅ Timeout écriture
                connect_timeout=10,        # ✅ Timeout connexion
                pool_timeout=10            # ✅ Timeout pool
            )
            
            # ✅ Boucle d'attente OPTIMISÉE - Ne pas vérifier trop souvent
            while self.running:
                await asyncio.sleep(10)  # ✅ 10 secondes au lieu de 5

            # Arrêter proprement
            info_print("Arrêt du polling Telegram...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
        except Exception as e:
            error_print(f"Erreur démarrage Telegram: {e}")
            import traceback
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
            f"• Message direct → Chat IA\n"
            f"• /power - Batterie/solaire\n"
            f"• /rx [page]\n"
            f"• /sys \n"
            f"• /echo <msg>\n"
            f"• /nodes \n"
            f"• /fullnodes [jours]  Liste complète alphabétique (défaut: 30j)\n"
            f"• /trafic [heures] - Messages publics (défaut: 8h)\n"
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
        
        # Envoyer en mode Markdown pour le formatage
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown'
        ) 

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
            except:
                system_info.append("🌡️ CPU: Error")
            
            try:
                uptime_cmd = ['uptime', '-p']
                uptime_result = subprocess.run(uptime_cmd, capture_output=True, text=True, timeout=5)
                if uptime_result.returncode == 0:
                    uptime_clean = uptime_result.stdout.strip().replace('up ', '')
                    system_info.append(f"⏱️ Up: {uptime_clean}")
            except:
                pass
            
            try:
                with open('/proc/loadavg', 'r') as f:
                    loadavg = f.read().strip().split()
                    system_info.append(f"📊 Load: {loadavg[0]} {loadavg[1]} {loadavg[2]}")
            except:
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
            except:
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
        """Commande /echo"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        if not context.args:
            await update.message.reply_text("Usage: /echo <message>")
            return

        echo_text = ' '.join(context.args)
        info_print(f"📱 Telegram /echo: {user.username} -> '{echo_text}'")

        def send_echo():
            import meshtastic.tcp_interface
            try:
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, portNumber=4403
                )
                time.sleep(3)

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
                remote_interface.sendText(message)
                time.sleep(4)
                remote_interface.close()
                return f"✅ Echo diffusé: {message}"
            except Exception as e:
                return f"❌ Erreur echo: {str(e)[:50]}"

        response = await asyncio.to_thread(send_echo)
        await update.message.reply_text(response)
    
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
                    cpu = process.cpu_percent(interval=1.0)
                    threads = len(process.threads())
                    mem = process.memory_info().rss / 1024 / 1024
                    measurements.append(f"[{i+1}/10] CPU: {cpu:.1f}% | Threads: {threads} | RAM: {mem:.0f}MB")

                # Moyenne finale
                cpu_avg = process.cpu_percent(interval=1.0)

                report = "📊 Monitoring CPU (10s):\n\n"
                report += "\n".join(measurements)
                report += f"\n\n✅ Moyenne: {cpu_avg:.1f}%"

                return report

            except ImportError:
                return "❌ Module psutil non installé\nInstaller: pip3 install psutil"
            except Exception as e:
                error_print(f"Erreur monitoring CPU: {e}")
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
                error_print(f"Erreur get_traffic: {e}")
                import traceback
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
                error_print(f"Erreur get_full_nodes: {e}")
                import traceback
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
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /rebootg2: {user.username}")
        sender_id = user.id & 0xFFFFFFFF
        sender_info = f"TG:{user.username}"
        
        await update.message.reply_text("🔄 Redémarrage tigrog2...")
        
        def reboot_g2():
            try:
                self.message_handler.handle_rebootg2_command(sender_id, sender_info)
                return "✅ Commande envoyée"
            except Exception as e:
                return f"❌ Erreur: {str(e)[:100]}"

        await asyncio.to_thread(reboot_g2)

    async def _rebootpi_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rebootpi - Redémarrage Pi5"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"🚨 Telegram /rebootpi: {user.username}")

        # Utiliser le mapping Telegram → Meshtastic
        mesh_identity = self._get_mesh_identity(user.id)

        if mesh_identity:
            sender_id = mesh_identity['node_id']
            info_print(f"🔄 Mapping: {user.username} → {mesh_identity['display_name']} (0x{sender_id:08x})")
        else:
           sender_id = user.id & 0xFFFFFFFF
           info_print(f"⚠️ Pas de mapping, utilisation ID Telegram")
           sender_info = f"TG:{user.username}"
        
        await update.message.reply_text("🔄 Redémarrage Pi5 en cours...")
        
        def reboot_pi():
            try:
                self.message_handler.handle_reboot_command(sender_id, sender_info)
                return "✅ Signal créé"
            except Exception as e:
                return f"❌ Erreur: {str(e)[:100]}"
        
        await asyncio.to_thread(reboot_pi)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Messages texte = /bot (Chat IA)"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        message_text = update.message.text
        info_print(f"📱 Telegram message: {user.username} -> '{message_text[:50]}'")
        
        sender_id = user.id & 0xFFFFFFFF
        
        def query_ai():
            return self.message_handler.llama_client.query_llama_telegram(message_text, sender_id)
        
        response = await asyncio.to_thread(query_ai)
        await update.message.reply_text(response)

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs"""
        error_print(f"❌ Erreur Telegram: {context.error}")
        import traceback
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
            )
            
            # Attendre le résultat (avec timeout)
            try:
                future.result(timeout=10)
                info_print("✅ Alerte envoyée avec succès")
            except Exception as e:
                error_print(f"Erreur attente résultat: {e}")
                
        except Exception as e:
            error_print(f"Erreur envoi alerte Telegram: {e}")
            import traceback
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
                    error_print(f"Erreur envoi alerte à {user_id}: {e}")
                
                # Petit délai entre les envois pour éviter rate limiting
                await asyncio.sleep(0.5)
            
            debug_print("_send_alert_async terminé")
                
        except Exception as e:
            error_print(f"Erreur _send_alert_async: {e}")
            import traceback
            error_print(traceback.format_exc())
    
    async def _trace_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /trace [short_id] - Traceroute mesh actif

        Sans argument : trace depuis bot vers l'utilisateur (mode passif)
        Avec argument : trace depuis le nœud spécifié vers bot (mode actif)
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

        def execute_active_trace():
            try:
                # 1. Trouver le node_id correspondant au short_name
                target_node_id = self._find_node_by_short_name(target_short_name)

                if not target_node_id:
                    asyncio.run_coroutine_threadsafe(
                        update.message.reply_text(
                            f"❌ Nœud '{target_short_name}' introuvable\n"
                            f"Utilisez /nodes pour voir la liste"
                        ),
                        self.loop
                    )
                    return

                target_full_name = self.node_manager.get_node_name(target_node_id)
                info_print(f"✅ Nœud trouvé: {target_full_name} (!{target_node_id:08x})")

                # 2. Enregistrer la requête de trace
                self.pending_traces[target_node_id] = {
                    'telegram_chat_id': update.effective_chat.id,
                    'timestamp': time.time(),
                    'short_name': target_short_name,
                    'full_name': target_full_name
                }

                info_print(f"📝 Trace enregistrée pour {target_full_name}")

                # 3. Envoyer la commande /trace au nœud mesh
                try:
                    self.message_handler.interface.sendText(
                        "/trace",
                        destinationId=target_node_id
                    )
                    info_print(f"📤 Commande /trace envoyée à {target_full_name}")
                except Exception as e:
                    error_print(f"Erreur envoi /trace: {e}")
                    # Essayer format hex
                    try:
                        hex_id = f"!{target_node_id:08x}"
                        self.message_handler.interface.sendText(
                            "/trace",
                            destinationId=hex_id
                        )
                        info_print(f"📤 Commande /trace envoyée (hex) à {target_full_name}")
                    except Exception as e2:
                        error_print(f"Erreur envoi /trace (hex): {e2}")
                        asyncio.run_coroutine_threadsafe(
                            update.message.reply_text(
                                f"❌ Impossible d'envoyer la commande au nœud\n"
                                f"Erreur: {str(e)[:50]}"
                            ),
                            self.loop
                        )
                        del self.pending_traces[target_node_id]
                        return

                # 4. Confirmer l'envoi à l'utilisateur
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text(
                        f"⏳ Traceroute lancé vers {target_full_name}\n"
                        f"Attente de la réponse (max {self.trace_timeout}s)...\n\n"
                        f"ℹ️ La réponse arrivera automatiquement ici"
                    ),
                    self.loop
                )

                info_print(f"✅ Traceroute actif lancé vers {target_full_name}")

            except Exception as e:
                error_print(f"Erreur execute_active_trace: {e}")
                import traceback
                error_print(traceback.format_exc())
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text(f"❌ Erreur: {str(e)[:100]}"),
                    self.loop
                )

        # Exécuter dans un thread séparé
        threading.Thread(target=execute_active_trace, daemon=True).start()

    def _find_node_by_short_name(self, short_name):
        """
        Trouver le node_id d'un nœud par son nom court
        Recherche dans la base locale ET dans l'interface
        """
        short_name_lower = short_name.lower().strip()

        # 1. Chercher dans la base locale de node_manager
        for node_id, full_name in self.node_manager.node_names.items():
            # Extraire le short name (première partie avant espace)
            node_short = full_name.split()[0].lower() if ' ' in full_name else full_name.lower()

            if node_short == short_name_lower or full_name.lower() == short_name_lower:
                debug_print(f"✅ Nœud trouvé dans base locale: {full_name}")
                return node_id

        # 2. Chercher dans l'interface en temps réel
        try:
            if hasattr(self.message_handler.interface, 'nodes'):
                nodes = self.message_handler.interface.nodes

                for node_id, node_info in nodes.items():
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            short = user_info.get('shortName', '').lower().strip()
                            long_name = user_info.get('longName', '').lower().strip()

                            if short == short_name_lower or long_name == short_name_lower:
                                # Convertir node_id si nécessaire
                                if isinstance(node_id, str):
                                    if node_id.startswith('!'):
                                        node_id_int = int(node_id[1:], 16)
                                    else:
                                        node_id_int = int(node_id, 16)
                                else:
                                    node_id_int = int(node_id)

                                debug_print(f"✅ Nœud trouvé dans interface: {long_name or short}")
                                return node_id_int
        except Exception as e:
            debug_print(f"Erreur recherche dans interface: {e}")

        # 3. Pas trouvé
        debug_print(f"❌ Nœud '{short_name}' introuvable")
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
                    )
                except Exception as e:
                    error_print(f"Erreur notification timeout: {e}")

                del self.pending_traces[node_id]

            if expired:
                debug_print(f"🧹 {len(expired)} traces expirées nettoyées")

        except Exception as e:
            error_print(f"Erreur cleanup_expired_traces: {e}")

    def handle_trace_response(self, from_id, message_text):
        """
        Traiter une réponse de traceroute depuis le mesh
        Appelé depuis main_bot.py dans on_message()

        Returns:
            bool: True si le message a été traité comme une réponse de trace
        """
        try:
            # Vérifier si c'est une réponse de trace attendue
            if from_id not in self.pending_traces:
                return False

            # Vérifier que le message ressemble à un traceroute
            trace_indicators = [
                "Traceroute",
                "Hops:",
                "Route:",
                "Signal:",
                "hopStart:",
                "hopLimit:"
            ]

            if not any(indicator in message_text for indicator in trace_indicators):
                debug_print(f"Message de {from_id} ne semble pas être une trace")
                return False

            # C'est bien une réponse de trace !
            trace_data = self.pending_traces[from_id]
            chat_id = trace_data['telegram_chat_id']
            node_name = trace_data['full_name']

            info_print(f"📥 Réponse de traceroute reçue de {node_name}")

            # Formater le message pour Telegram
            telegram_message = (
                f"📊 **Traceroute reçu de {node_name}**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{message_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱️ Temps de réponse: {time.time() - trace_data['timestamp']:.1f}s"
            )

            # Envoyer à Telegram
            asyncio.run_coroutine_threadsafe(
                self.application.bot.send_message(
                    chat_id=chat_id,
                    text=telegram_message,
                    parse_mode='Markdown'
                ),
                self.loop
            )

            info_print(f"✅ Traceroute forwarded à Telegram pour {node_name}")

            # Supprimer la trace de la liste
            del self.pending_traces[from_id]

            return True

        except Exception as e:
            error_print(f"Erreur handle_trace_response: {e}")
            import traceback
            error_print(traceback.format_exc())
            return False

