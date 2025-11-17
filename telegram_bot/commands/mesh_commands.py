#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes mesh Telegram : echo, annonce
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
from config import REMOTE_NODE_HOST
import asyncio


class MeshCommands(TelegramCommandBase):
    """Gestionnaire des commandes mesh Telegram"""

    async def echo_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo <message> - Diffuser sur le mesh"""
        user = update.effective_user
        if not context.args:
            await update.message.reply_text("Usage: /echo <message>")
            return

        echo_text = ' '.join(context.args)
        info_print(f"📱 Telegram /echo: {user.username} -> '{echo_text}'")

        # Message de confirmation immédiat
        status_msg = await update.message.reply_text("📤 Envoi en cours...")
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
        thread = threading.Thread(target=execute_and_reply, daemon=True)
        thread.start()
        info_print(f"✅ Thread echo lancé: {thread.name}")

    async def annonce_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        info_print("🔴 DÉBUT _annonce_command")
        user = update.effective_user

        info_print(f"📱 Telegram /annonce appelée par {user.username}")

        if not self.check_authorization(user.id):
            info_print("❌ Non autorisé")
            await update.message.reply_text("❌ Non autorisé")
            return

        info_print(f"✅ Autorisé - context.args: {context.args}")

        if not context.args:
            info_print("⚠️ Pas d'arguments")
            await update.message.reply_text("Usage: /annonce <message>")
            return

        info_print("✅ Arguments présents, suite du traitement...")
        annonce_text = ' '.join(context.args)
        info_print(f"✅ Texte: '{annonce_text}'")

        try:
            info_print("📤 Tentative envoi message status...")
            status_msg = await update.message.reply_text("📤 Envoi en cours...")
            info_print("✅ Message status envoyé")
        except Exception as e:
            error_print(f"❌ Erreur envoi status: {e}")
            raise

        def send_annonce():
            try:
                # Utiliser le mapping Telegram → Meshtastic
                mesh_identity = self.get_mesh_identity(user.id)

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
                    return "❌ Interface non disponible"

                # Si c'est un SafeSerialConnection, récupérer l'interface
                # réelle
                if hasattr(interface, 'get_interface'):
                    actual_interface = interface.get_interface()
                    if not actual_interface:
                        error_print("❌ Interface non connectée")
                        return "❌ Bot en cours de reconnexion"
                    interface = actual_interface

                info_print(f"✅ Interface trouvée: {type(interface).__name__}")

                # Envoyer directement en broadcast depuis le bot local
                interface.sendText(message, destinationId='^all')

                info_print(f"✅ Annonce diffusée depuis bot local")
                return "✅ Annonce envoyée depuis le bot local"

            except Exception as e:
                error_print(f"Erreur /annonce Telegram: {e}")
                import traceback
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:50]}"

        # Exécuter la fonction dans un thread
        def execute_and_reply():
            try:
                result = send_annonce()

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
        thread = threading.Thread(target=execute_and_reply, daemon=True)
        thread.start()
        info_print(f"✅ Thread annonce lancé: {thread.name}")
