#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes admin Telegram : cleartraffic, dbstats, cleanup, channel_stats
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio


class AdminCommands(TelegramCommandBase):
    """Gestionnaire des commandes admin Telegram"""

    async def raw_log_handler(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """Log BRUT de tous les messages"""
        if update.message and update.message.text:
            info_print(
                f"🔴 RAW MESSAGE: '{update.message.text}' from {update.message.from_user.id}")

    async def channel_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /channel_stats [heures]
        Affiche les statistiques d'utilisation du canal par nœud
        """
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(168, hours))
            except ValueError:
                hours = 24

        info_print(f"📱 Telegram /channel_stats {hours}h: {user.username}")

        # Utiliser la logique métier partagée (business_stats, pas stats_commands)
        response = await asyncio.to_thread(
            self.telegram.business_stats.get_channel_stats,
            hours
        )

        # Diviser si trop long
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
                await asyncio.sleep(0.5)
        else:
            await update.message.reply_text(response)

    async def cleartraffic_command(self, update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /cleartraffic - Efface tout l'historique du trafic
        Usage: /cleartraffic
        """
        user = update.effective_user
        info_print(f"📱 Telegram /cleartraffic: {user.username or user.first_name}")

        # Utiliser la logique métier partagée (business_stats, pas stats_commands)
        response = await asyncio.to_thread(
            self.telegram.business_stats.clear_traffic_history
        )

        await update.message.reply_text(response)

    async def dbstats_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /dbstats - Affiche les statistiques de la base de données
        Usage: /dbstats
        """
        user = update.effective_user
        info_print(f"📱 Telegram /dbstats: {user.username or user.first_name}")

        # Utiliser la logique métier partagée (business_stats, pas stats_commands)
        response = await asyncio.to_thread(
            self.telegram.business_stats.get_persistence_stats
        )

        await update.message.reply_text(response)

    async def cleanup_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /cleanup - Nettoie les anciennes données (par défaut > 48h)
        Usage: /cleanup [heures]
        Exemple: /cleanup 72 (supprime les données de plus de 72h)
        """
        user = update.effective_user

        # Récupérer le nombre d'heures (par défaut 48)
        hours = 48
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(24, min(720, hours))  # Entre 24h et 30 jours
            except ValueError:
                hours = 48

        info_print(f"📱 Telegram /cleanup {hours}h: {user.username}")

        # Utiliser la logique métier partagée (business_stats, pas stats_commands)
        response = await asyncio.to_thread(
            self.telegram.business_stats.cleanup_old_data,
            hours
        )

        await update.message.reply_text(response)
