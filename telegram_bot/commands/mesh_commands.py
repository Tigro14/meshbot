#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes mesh Telegram : echo
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print, debug_print
import asyncio
import time

# Import optionnel de REMOTE_NODE_HOST avec fallback
try:
    from config import REMOTE_NODE_HOST, CONNECTION_MODE
except ImportError:
    REMOTE_NODE_HOST = None
    CONNECTION_MODE = 'serial'


class MeshCommands(TelegramCommandBase):
    """Gestionnaire des commandes mesh Telegram"""

    async def echo_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo <message> - Diffuser sur le mesh"""
        user = update.effective_user
        if not context.args:
            await update.effective_message.reply_text("Usage: /echo <message>")
            return

        echo_text = ' '.join(context.args)
        info_print(f"📱 Telegram /echo: {user.username} -> '{echo_text}'")

        # Message de confirmation immédiat
        status_msg = await update.effective_message.reply_text("📤 Envoi en cours...")
        info_print(f"✅ Message status créé")

        def send_echo():
            info_print("✅ 3. ENTRÉE dans send_echo()")
            try:
                # Utiliser le mapping Telegram → Meshtastic
                mesh_identity = self.get_mesh_identity(user.id)

                if mesh_identity:
                    prefix = mesh_identity['short_name']
                    info_print(f"🔄 Echo avec identité mappée: {prefix}")
                else:
                    username = user.username or user.first_name
                    prefix = username[:4]
                    info_print(f"⚠️ Echo sans mapping: {prefix}")

                message = f"{prefix}: {echo_text}"

                # ========================================
                # MODE DETECTION: Avoid TCP conflicts
                # ========================================
                # If bot is in TCP mode, use the existing interface to avoid
                # violating ESP32's single TCP connection limit
                # If bot is in serial mode, create a temporary TCP connection
                connection_mode = CONNECTION_MODE.lower() if CONNECTION_MODE else 'serial'
                
                if connection_mode == 'tcp':
                    # TCP MODE: Use existing bot interface (no second connection)
                    debug_print(f"🔌 Mode TCP: utilisation de l'interface existante du bot")
                    
                    if not self.interface:
                        return "❌ Interface bot non disponible"
                    
                    try:
                        debug_print(f"📤 Envoi via interface bot: '{message}'")
                        
                        # Detect interface type to handle MeshCore vs Meshtastic differences
                        is_meshcore = hasattr(self.interface, '__class__') and 'MeshCore' in self.interface.__class__.__name__
                        
                        if is_meshcore:
                            # MeshCore: Send as broadcast (0xFFFFFFFF) on public channel (channelIndex=0)
                            debug_print("🔍 Interface MeshCore détectée - envoi broadcast sur canal public")
                            self.interface.sendText(message, destinationId=0xFFFFFFFF, channelIndex=0)
                        else:
                            # Meshtastic: Broadcast on public channel (channelIndex=0 is default)
                            debug_print("🔍 Interface Meshtastic détectée - envoi broadcast sur canal public")
                            self.interface.sendText(message, channelIndex=0)
                        
                        # Wait a bit for message to be queued
                        time.sleep(2)
                        info_print(f"✅ Message envoyé via interface TCP principale")
                        return f"✅ Echo diffusé: {message}"
                    except Exception as e:
                        error_print(f"❌ Erreur sendText via interface: {e}")
                        return f"❌ Échec envoi: {str(e)[:50]}"
                        
                else:
                    # SERIAL MODE: Create temporary TCP connection
                    debug_print(f"📡 Mode serial: création connexion TCP temporaire")
                    
                    if not REMOTE_NODE_HOST:
                        return "❌ REMOTE_NODE_HOST non configuré dans config.py"
                    
                    from safe_tcp_connection import send_text_to_remote
                    import traceback

                    info_print(f"📤 Envoi message vers {REMOTE_NODE_HOST}: '{message}'")

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

            info_print(f"✅ 4. send_echo définie")

        # Exécuter la fonction dans un thread
        def execute_and_reply():
            info_print("✅ 5. ENTRÉE dans execute_and_reply()")
            try:
                result = send_echo()

                # Envoyer le résultat via l'event loop de Telegram
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit_text(result),
                    self.telegram.loop
                ).result(timeout=5)

            except Exception as e:
                error_print(f"❌ Erreur execute_and_reply: {e}")
                try:
                    asyncio.run_coroutine_threadsafe(
                        status_msg.edit_text(f"❌ Erreur: {str(e)[:50]}"),
                        self.telegram.loop
                    ).result(timeout=5)
                except BaseException:
                    pass

        # Lancer dans un thread
        import threading
        thread = threading.Thread(target=execute_and_reply, daemon=True, name="TelegramEcho")
        thread.start()
        info_print(f"✅ Thread echo lancé: {thread.name}")
