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
            raise ImportError("python-telegram-bot requis. Installez: pip3 install python-telegram-bot")
        
        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager
        
        self.running = False
        self.telegram_thread = None
        self.application = None
        self.loop = None
        # Liste des utilisateurs pour les alertes
        self.alert_users = TELEGRAM_ALERT_USERS if TELEGRAM_ALERT_USERS else TELEGRAM_AUTHORIZED_USERS

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
            self.application.add_handler(CommandHandler("rx", self._rx_command))
            self.application.add_handler(CommandHandler("sys", self._sys_command))
            self.application.add_handler(CommandHandler("legend", self._legend_command))
            self.application.add_handler(CommandHandler("echo", self._echo_command))
            self.application.add_handler(CommandHandler("nodes", self._nodes_command))
            self.application.add_handler(CommandHandler("trafic", self._trafic_command))
            self.application.add_handler(CommandHandler("rebootg2", self._rebootg2_command))
            self.application.add_handler(CommandHandler("rebootpi", self._rebootpi_command))
            self.application.add_handler(CommandHandler("fullnodes", self._fullnodes_command))
            
            # Handler pour messages texte
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            
            # Gestionnaire d'erreurs
            self.application.add_error_handler(self._error_handler)
            
            # Démarrer l'application
            await self.application.initialize()
            await self.application.start()
            
            # Démarrer le polling (BLOQUANT - pas besoin de boucle while)
            info_print("Bot Telegram en écoute...")
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                poll_interval=2.0  # Vérifier toutes les 2 secondes au lieu de 1
            )
            
            # Attendre que running devienne False (pas de boucle active)
            while self.running:
                await asyncio.sleep(5)  # Vérifier moins souvent
            
            # Arrêter proprement
            info_print("Arrêt du polling Telegram...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
        except Exception as e:
            error_print(f"Erreur démarrage Telegram: {e}")
            import traceback
            error_print(traceback.format_exc())

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
            f"• /rx [page] - Nœuds tigrog2\n"
            f"• /sys - Système Pi5\n"
            f"• /echo <msg> - Diffuser\n"
            f"• /nodes - Nœuds tigrog2\n"
            f"• /fullnodes [jours] - Liste complète alphabétique (défaut: 30j)\n"
            f"• /trafic [heures] - Messages publics (défaut: 8h)\n"
            f"• /legend - Légende\n"
            f"• /help - Aide\n\n"
            f"Votre ID: {user.id}"
        )
        await update.message.reply_text(welcome_msg)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /help: {user.username}")
        help_text = self.message_handler.format_help()
        await update.message.reply_text(f"📖 Aide:\n{help_text}")
    
    async def _power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /power: {user.username}")
        response = await asyncio.to_thread(
            self.message_handler.esphome_client.parse_esphome_data
        )
        await update.message.reply_text(f"⚡ Power:\n{response}")
    
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
                    last_heard = node.get('last_heard', 0)
                    
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
        if context.args and len(context.args) > 0:
            try:
                days = int(context.args[0])
                days = max(1, min(90, days))  # Entre 1 et 90 jours
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
    
