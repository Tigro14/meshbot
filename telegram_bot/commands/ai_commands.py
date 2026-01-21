#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes IA Telegram : bot, clearcontext
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio


class AICommands(TelegramCommandBase):
    """Gestionnaire des commandes IA Telegram"""

    async def bot_command(self, update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /bot <question> - Chat avec l'IA
        """
        user = update.effective_user
        # Vérifier qu'il y a bien une question
        if not context.args or len(context.args) == 0:
            await update.effective_message.reply_text(
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
            await update.effective_message.reply_text("🤔 Réflexion en cours...")

        def query_ai():
            return self.message_handler.llama_client.query_llama_telegram(
                question, sender_id)

        try:
            response = await asyncio.to_thread(query_ai)
            await update.effective_message.reply_text(response)
        except Exception as e:
            error_print(f"Erreur /bot: {e}")
            await update.effective_message.reply_text(f"❌ Erreur lors du traitement: {str(e)[:100]}")

    async def ia_command(self, update: Update,
                         context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /ia <question> - Alias français de /bot
        """
        user = update.effective_user
        # Vérifier qu'il y a bien une question
        if not context.args or len(context.args) == 0:
            await update.effective_message.reply_text(
                "Usage: /ia <question>\n"
                "Exemple: /ia Quelle est la météo ?\n"
                "(/ia est un alias français de /bot)"
            )
            return

        # Reconstruire la question complète
        question = ' '.join(context.args)

        info_print(f"📱 Telegram /ia: {user.username} -> '{question[:50]}'")

        sender_id = user.id & 0xFFFFFFFF

        # Message d'attente pour les longues questions
        if len(question) > 100:
            await update.effective_message.reply_text("🤔 Réflexion en cours...")

        def query_ai():
            return self.message_handler.llama_client.query_llama_telegram(
                question, sender_id)

        try:
            response = await asyncio.to_thread(query_ai)
            await update.effective_message.reply_text(response)
        except Exception as e:
            error_print(f"Erreur /ia: {e}")
            await update.effective_message.reply_text(f"❌ Erreur lors du traitement: {str(e)[:100]}")


    async def clearcontext_command(
            self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /clearcontext - Nettoyer le contexte"""
        user = update.effective_user
        info_print(f"📱 Telegram /clearcontext: {user.username}")

        # Utiliser le mapping
        mesh_identity = self.get_mesh_identity(user.id)
        node_id = mesh_identity['node_id'] if mesh_identity else (
            user.id & 0xFFFFFFFF)

        # Nettoyer le contexte
        if node_id in self.context_manager.conversation_context:
            msg_count = len(self.context_manager.conversation_context[node_id])
            del self.context_manager.conversation_context[node_id]
            await update.effective_message.reply_text(f"✅ Contexte nettoyé ({msg_count} messages supprimés)")
        else:
            await update.effective_message.reply_text("ℹ️ Pas de contexte actif")
