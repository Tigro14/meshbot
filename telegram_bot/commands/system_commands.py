#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes système Telegram : sys, cpu, rebootpi, rebootg2
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio
import time
import subprocess
import traceback


class SystemCommands(TelegramCommandBase):
    """Gestionnaire des commandes système Telegram"""

    async def sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys"""
        user = update.effective_user
        self.log_command("sys", user.username or user.first_name)

        def get_sys_info():
            import subprocess
            system_info = []
            try:
                if hasattr(self.message_handler, 'router') and \
                   hasattr(self.message_handler.router, 'system_handler') and \
                   self.message_handler.router.system_handler.bot_start_time:

                    bot_uptime_seconds = int(
                        time.time() - self.message_handler.router.system_handler.bot_start_time)

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
                temp_result = subprocess.run(
                    temp_cmd, capture_output=True, text=True, timeout=5)

                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_value = temp_output.split(
                            '=')[1].replace("'C", "°C")
                        system_info.append(f"🌡️ CPU: {temp_value}")
                else:
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        temp_celsius = int(f.read().strip()) / 1000.0
                        system_info.append(f"🌡️ CPU: {temp_celsius:.1f}°C")
            except Exception as e:
                system_info.append("🌡️ CPU: Error")

            try:
                uptime_cmd = ['uptime', '-p']
                uptime_result = subprocess.run(
                    uptime_cmd, capture_output=True, text=True, timeout=5)
                if uptime_result.returncode == 0:
                    uptime_clean = uptime_result.stdout.strip().replace('up ', '')
                    system_info.append(f"⏱️ Up: {uptime_clean}")
            except Exception as e:
                pass

            try:
                with open('/proc/loadavg', 'r') as f:
                    loadavg = f.read().strip().split()
                    system_info.append(
                        f"📊 Load: {loadavg[0]} {loadavg[1]} {loadavg[2]}")
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
                    system_info.append(
                        f"💾 RAM: {mem_used // 1024}MB/{mem_total // 1024}MB ({mem_percent:.0f}%)")
            except Exception as e:
                pass

            return "🖥️ Système RPI5:\n" + \
                "\n".join(system_info) if system_info else "❌ Erreur système"

        response = await asyncio.to_thread(get_sys_info)
        await self.send_message(update, response)

    async def cpu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /cpu - Monitoring CPU en temps réel"""
        user = update.effective_user
        self.log_command("cpu", user.username or user.first_name)

        # Message initial
        await update.effective_message.reply_text("📊 Monitoring CPU (10 secondes)...")

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
                    measurements.append(
                        f"[{i + 1}/10] CPU: {cpu:.1f}% | Threads: {threads} | RAM: {mem:.0f}MB")

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
        await self.send_message(update, response)

    async def rebootg2_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rebootg2 - Redémarrage tigrog2"""
        user = update.effective_user

        info_print("=" * 60)
        info_print("🔥 rebootg2_command() APPELÉ !")
        info_print(f"   User Telegram: {user.username}")
        info_print(f"   User ID Telegram: {user.id}")
        info_print(f"   Arguments: {context.args}")
        info_print("=" * 60)

        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return

        # Parser les arguments (mot de passe)
        password = context.args[0] if context.args else ""
        message_parts = ["/rebootg2", password] if password else ["/rebootg2"]

        info_print(f"📝 message_parts construit: {message_parts}")

        # Utiliser le mapping Telegram → Meshtastic
        mesh_identity = self.get_mesh_identity(user.id)

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
        await self.send_message(update, response)

    async def rebootpi_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rebootpi - Redémarrage Pi5"""
        user = update.effective_user

        info_print("=" * 60)
        info_print("🔥 rebootpi_command() APPELÉ !")
        info_print(f"   User Telegram: {user.username}")
        info_print(f"   User ID Telegram: {user.id}")
        info_print(f"   Arguments: {context.args}")
        info_print("=" * 60)

        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return

        # Parser les arguments (mot de passe)
        password = context.args[0] if context.args else ""
        message_parts = ["/rebootpi", password] if password else ["/rebootpi"]

        info_print(f"📝 message_parts construit: {message_parts}")

        # Utiliser le mapping Telegram → Meshtastic
        mesh_identity = self.get_mesh_identity(user.id)

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
        await self.send_message(update, response)
