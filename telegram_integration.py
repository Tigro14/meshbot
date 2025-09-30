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
    
    def start(self):
        """Démarrer le bot Telegram dans un thread séparé"""
        if self.running:
            return
        
        self.running = True
        self.telegram_thread = threading.Thread(target=self._run_telegram_bot, daemon=True)
        self.telegram_thread.start()
        info_print("Bot Telegram démarré en thread séparé")
    
    def stop(self):
        """Arrêter le bot Telegram"""
        self.running = False
        if self.loop and self.application:
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
            except:
                pass
        info_print("Bot Telegram arrêté")
    
    def _run_telegram_bot(self):
        """Exécuter le bot Telegram dans son propre event loop"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._start_telegram_bot())
        except Exception as e:
            error_print(f"Erreur bot Telegram: {e}")
    
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
            self.application.add_handler(CommandHandler("rebootg2", self._rebootg2_command))
            self.application.add_handler(CommandHandler("rebootpi", self._rebootpi_command))
            
            # Handler pour messages texte (raccourci /bot)
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            
            # Gestionnaire d'erreurs
            self.application.add_error_handler(self._error_handler)
            
            # Démarrer
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            info_print("Bot Telegram en écoute...")
            
            # Garder actif
            while self.running:
                await asyncio.sleep(1)
            
        except Exception as e:
            error_print(f"Erreur démarrage Telegram: {e}")
    
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
        info_print(f"Telegram /start: {user.username} ({user.id})")
        
        welcome_msg = (
            f"Bot Meshtastic Bridge\n\n"
            f"Salut {user.first_name} !\n\n"
            f"Commandes:\n"
            f"• Message direct → Chat IA\n"
            f"• /power - Batterie/solaire\n"
            f"• /rx [page] - Nœuds tigrog2\n"
            f"• /sys - Système Pi5\n"
            f"• /echo <msg> - Diffuser\n"
            f"• /nodes <IP> [page] - Nœuds distants\n"
            f"• /legend - Légende\n"
            f"• /help - Aide\n\n"
            f"Votre ID: {user.id}"
        )
        await update.message.reply_text(welcome_msg)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        help_text = self.message_handler.format_help()
        await update.message.reply_text(f"Aide:\n{help_text}")
    
    async def _power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        info_print(f"Telegram /power: {user.username}")
        response = await asyncio.to_thread(
            self.message_handler.esphome_client.parse_esphome_data
        )
        await update.message.reply_text(f"Power:\n{response}")
    
    async def _rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx [page]"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        page = int(context.args[0]) if context.args else 1
        info_print(f"Telegram /rx {page}: {user.username}")
        
        response = await asyncio.to_thread(
            self.message_handler.remote_nodes_client.get_tigrog2_paginated,
            page
        )
        await update.message.reply_text(response)
    
    async def _sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        info_print(f"Telegram /sys: {user.username}")
        
        # Appeler la fonction sys dans un thread
        def get_sys_info():
            import subprocess
            system_info = []
            
            # 1. Température CPU (RPI5)
            try:
                temp_cmd = ['vcgencmd', 'measure_temp']
                temp_result = subprocess.run(temp_cmd, 
                                           capture_output=True, 
                                           text=True, 
                                           timeout=5)
                
                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_value = temp_output.split('=')[1].replace("'C", "°C")
                        system_info.append(f"🌡️ CPU: {temp_value}")
                    else:
                        system_info.append(f"🌡️ CPU: {temp_output}")
                else:
                    try:
                        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                            temp_millis = int(f.read().strip())
                            temp_celsius = temp_millis / 1000.0
                            system_info.append(f"🌡️ CPU: {temp_celsius:.1f}°C")
                    except:
                        system_info.append("🌡️ CPU: N/A")
            except:
                system_info.append("🌡️ CPU: Error")
            
            # 2. Uptime simplifié
            try:
                uptime_cmd = ['uptime', '-p']
                uptime_result = subprocess.run(uptime_cmd, 
                                             capture_output=True, 
                                             text=True, 
                                             timeout=5)
                
                if uptime_result.returncode == 0:
                    uptime_output = uptime_result.stdout.strip()
                    uptime_clean = uptime_output.replace('up ', '')
                    system_info.append(f"⏱️ Up: {uptime_clean}")
                else:
                    with open('/proc/uptime', 'r') as f:
                        uptime_seconds = float(f.read().split()[0])
                        days = int(uptime_seconds // 86400)
                        hours = int((uptime_seconds % 86400) // 3600)
                        minutes = int((uptime_seconds % 3600) // 60)
                        
                        if days > 0:
                            uptime_str = f"{days}d {hours}h"
                        elif hours > 0:
                            uptime_str = f"{hours}h {minutes}m"
                        else:
                            uptime_str = f"{minutes}m"
                        
                        system_info.append(f"⏱️ Up: {uptime_str}")
            except:
                system_info.append("⏱️ Uptime: Error")
            
            # 3. Load Average
            try:
                with open('/proc/loadavg', 'r') as f:
                    loadavg = f.read().strip().split()
                    load_1m = float(loadavg[0])
                    load_5m = float(loadavg[1])
                    load_15m = float(loadavg[2])
                    system_info.append(f"📊 Load: {load_1m:.2f} {load_5m:.2f} {load_15m:.2f}")
            except:
                pass
            
            # 4. Mémoire
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                
                mem_total = None
                mem_available = None
                
                for line in meminfo.split('\n'):
                    if line.startswith('MemTotal:'):
                        mem_total = int(line.split()[1])
                    elif line.startswith('MemAvailable:'):
                        mem_available = int(line.split()[1])
                
                if mem_total and mem_available:
                    mem_used = mem_total - mem_available
                    mem_percent = (mem_used / mem_total) * 100
                    mem_total_mb = mem_total // 1024
                    mem_used_mb = mem_used // 1024
                    
                    system_info.append(f"💾 RAM: {mem_used_mb}MB/{mem_total_mb}MB ({mem_percent:.0f}%)")
            except:
                pass
            
            return "🖥️ Système RPI5:\n" + "\n".join(system_info) if system_info else "Erreur système"
        
        response = await asyncio.to_thread(get_sys_info)
        await update.message.reply_text(response)

    async def _legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        legend = self.message_handler.format_legend()
        await update.message.reply_text(legend)
    
    async def _echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /echo <message>")
            return
        
        echo_text = ' '.join(context.args)
        info_print(f"Telegram /echo: {user.username} -> '{echo_text}'")
        
        # Simuler un sender_id basé sur Telegram ID
        sender_id = user.id & 0xFFFFFFFF
        
        def send_echo():
            import meshtastic.tcp_interface
            try:
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, portNumber=4403
                )
                time.sleep(1)
                username = user.username or user.first_name
                remote_interface.sendText(f"{username[:4]}: {echo_text}")
                remote_interface.close()
                return f"Echo diffusé: {username[:4]}: {echo_text}"
            except Exception as e:
                return f"Erreur echo: {str(e)[:50]}"
        
        response = await asyncio.to_thread(send_echo)
        await update.message.reply_text(response)
    
    async def _nodes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /nodes - Affiche tous les nœuds de tigrog2"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        info_print(f"Telegram /nodes: {user.username}")
        
        def get_nodes_list():
            try:
                nodes = self.message_handler.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
                if not nodes:
                    return f"Aucun nœud trouvé sur {REMOTE_NODE_NAME}"
                
                nodes.sort(key=lambda x: x.get('snr', -999), reverse=True)
                
                lines = [f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} ({len(nodes)}):\n"]
                
                for node in nodes:
                    name = node.get('name', 'Unknown')
                    snr = node.get('snr', 0.0)
                    last_heard = node.get('last_heard', 0)
                    
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
                    
                    if snr >= 10:
                        icon = "🟢"
                    elif snr >= 5:
                        icon = "🟡"
                    elif snr >= 0:
                        icon = "🟠"
                    elif snr >= -5:
                        icon = "🔴"
                    else:
                        icon = "⚫"
                    
                    lines.append(f"{icon} {name}: SNR {snr:.1f}dB ({time_str})")
                
                return "\n".join(lines)
            except Exception as e:
                error_print(f"Erreur get_nodes_list: {e}")
                import traceback
                error_print(traceback.format_exc())
                return f"Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(get_nodes_list)
        await update.message.reply_text(response)

    async def _rebootg2_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rebootg2 - Redémarrage tigrog2"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"Telegram /rebootg2: {user.username}")
        
        sender_id = user.id & 0xFFFFFFFF
        sender_info = f"TG:{user.username}"
        
        await update.message.reply_text("🔄 Redémarrage tigrog2...")
        
        # Appeler la fonction existante dans message_handler
        def reboot_g2():
            try:
                self.message_handler.handle_rebootg2_command(sender_id, sender_info)
                return "Commande envoyée"
            except Exception as e:
                return f"Erreur: {str(e)[:100]}"
        
        # Note: La réponse viendra de manière asynchrone via le thread
        await asyncio.to_thread(reboot_g2)
        # Ne pas attendre de réponse immédiate, elle sera envoyée par le thread
    
    async def _rebootpi_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rebootpi - Redémarrage Pi5"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"🚨 Telegram /rebootpi: {user.username}")
        
        sender_id = user.id & 0xFFFFFFFF
        sender_info = f"TG:{user.username}"
        
        await update.message.reply_text("🔄 Redémarrage Pi5 en cours...")
        
        # Appeler la fonction existante
        def reboot_pi():
            try:
                self.message_handler.handle_reboot_command(sender_id, sender_info)
                return "Signal créé"
            except Exception as e:
                return f"Erreur: {str(e)[:100]}"
        
        await asyncio.to_thread(reboot_pi)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Messages texte = /bot (Chat IA)"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("Non autorisé")
            return
        
        message_text = update.message.text
        info_print(f"Telegram message: {user.username} -> '{message_text[:50]}'")
        
        sender_id = user.id & 0xFFFFFFFF
        
        def query_ai():
            return self.message_handler.llama_client.query_llama_telegram(message_text, sender_id)
        
        response = await asyncio.to_thread(query_ai)
        await update.message.reply_text(response)

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs"""
        error_print(f"Erreur Telegram: {context.error}")
        if update and hasattr(update, 'message') and update.message:
            await update.message.reply_text("Erreur interne")
