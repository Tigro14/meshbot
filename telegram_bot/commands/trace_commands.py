#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes traceroute Telegram : trace
Délègue au TracerouteManager
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print


class TraceCommands(TelegramCommandBase):
    """Gestionnaire des commandes traceroute Telegram"""

    async def trace_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /trace <node>
        Délègue au TracerouteManager
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        # Déléguer au TracerouteManager
        await self.telegram.traceroute_manager._trace_command(update, context)
