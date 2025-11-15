#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes utilitaires Telegram : power, weather, graphs
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio


class UtilityCommands(TelegramCommandBase):
    """Gestionnaire des commandes utilitaires Telegram"""

    async def power_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /power avec graphiques d'historique"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        info_print(f"📱 Telegram /power: {user.username}")

        # Extraire le nombre d'heures (optionnel, défaut 24)
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))  # Entre 1 et 48 heures
            except ValueError:
                hours = 24

        # Message 1 : Données actuelles
        response_current = await asyncio.to_thread(
            self.message_handler.esphome_client.parse_esphome_data
        )
        await update.message.reply_text(f"⚡ Power:\n{response_current}")

        # Message 2 : Graphiques d'historique
        response_graphs = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.message.reply_text(response_graphs)

    async def weather_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user

        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        info_print(f"📱 Telegram /weather: {user.username}")

        # Utiliser directement le module utils.weather
        from utils_weather import get_weather_data

        try:
            weather = await asyncio.to_thread(get_weather_data)
            await update.message.reply_text(weather)
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {str(e)[:50]}")

    async def graphs_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /graphs pour afficher uniquement les graphiques d'historique"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        # Extraire le nombre d'heures (optionnel, défaut 24)
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))  # Entre 1 et 48 heures
            except ValueError:
                hours = 24

        info_print(f"📱 Telegram /graphs {hours}h: {user.username}")

        # Générer les graphiques
        response = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.message.reply_text(response)

    async def graph_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /graph - À définir selon vos besoins"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        info_print(f"📱 Telegram /graph: {user.username}")

        # TODO: Implémenter selon vos besoins
        await update.message.reply_text("🚧 Commande /graph en cours d'implémentation")
