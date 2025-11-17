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
        info_print("=" * 60)
        info_print("🔵 TRACE_COMMAND APPELÉ DANS TRACE_COMMANDS.PY")
        info_print(f"   User: {user.username or user.first_name}")
        info_print(f"   Args: {context.args}")
        info_print("=" * 60)

        # Déléguer au TracerouteManager
        await self.telegram.traceroute_manager._trace_command(update, context)
