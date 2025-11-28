#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes mesh Telegram : echo
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio

# Import optionnel de REMOTE_NODE_HOST avec fallback
try:
    from config import REMOTE_NODE_HOST
except ImportError:
    REMOTE_NODE_HOST = None


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
                # Vérifier que REMOTE_NODE_HOST est configuré
                if not REMOTE_NODE_HOST:
                    return "❌ REMOTE_NODE_HOST non configuré dans config.py"

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

                # ✅ IMPORT SIMPLIFIÉ - Fonction au niveau module
                from safe_tcp_connection import send_text_to_remote
                import traceback

                info_print(
                    f"📤 Envoi message vers {REMOTE_NODE_HOST}: '{message}'")

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
