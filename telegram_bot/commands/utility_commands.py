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
        """
        Commande /weather [rain|astro] [ville] [days]

        Exemples:
        /weather → Météo locale
        /weather Paris → Météo Paris
        /weather rain → Pluie locale aujourd'hui
        /weather rain 3 → Pluie locale 3 jours
        /weather rain Paris 3 → Pluie Paris 3 jours
        /weather astro → Infos astronomiques locales
        /weather astro Paris → Infos astronomiques Paris
        """
        user = update.effective_user

        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        # Parser les arguments: [rain|astro] [ville] [days]
        subcommand = None
        location = None
        days = 1  # Par défaut: aujourd'hui seulement

        if context.args and len(context.args) > 0:
            # Vérifier si le premier argument est une sous-commande
            if context.args[0].lower() in ['rain', 'astro']:
                subcommand = context.args[0].lower()
                remaining = context.args[1:]  # Arguments après la sous-commande

                # Le dernier argument est un nombre de jours ?
                if remaining and remaining[-1].isdigit():
                    days_arg = int(remaining[-1])
                    if days_arg in [1, 3]:
                        days = days_arg
                        remaining = remaining[:-1]

                # Ce qui reste est la ville (peut avoir des espaces)
                if remaining:
                    location = ' '.join(remaining)
            else:
                # Sinon c'est directement la ville
                location = ' '.join(context.args)

        # Si "help"/"aide", afficher l'aide
        if location and location.lower() in ['help', 'aide', '?']:
            help_text = (
                "🌤️ /weather [rain|astro] [ville] [days]\n\n"
                "Exemples:\n"
                "/weather → Météo locale\n"
                "/weather Paris → Météo Paris\n"
                "/weather rain → Pluie aujourd'hui\n"
                "/weather rain 3 → Pluie 3 jours\n"
                "/weather rain Paris 3 → Pluie Paris 3j\n"
                "/weather astro → Infos astro\n"
                "/weather astro Paris → Astro Paris"
            )
            await update.message.reply_text(help_text)
            return

        # Log avec détails
        cmd_str = f"/weather {subcommand or ''} {location or ''} {days if subcommand == 'rain' else ''}".strip()
        info_print(f"📱 Telegram {cmd_str}: {user.username}")

        # Utiliser les modules utils.weather appropriés
        from utils_weather import get_weather_data, get_rain_graph, get_weather_astro
        import time

        try:
            if subcommand == 'rain':
                # Graphe de précipitations
                weather_data = await asyncio.to_thread(get_rain_graph, location, days)

                # Découper et envoyer jour par jour (1 ou 3 messages)
                day_messages = weather_data.split('\n\n')
                for i, day_msg in enumerate(day_messages):
                    await update.message.reply_text(day_msg)
                    # Petit délai entre les messages
                    if i < len(day_messages) - 1:
                        await asyncio.sleep(1)

            elif subcommand == 'astro':
                # Informations astronomiques
                weather_data = await asyncio.to_thread(get_weather_astro, location)
                await update.message.reply_text(weather_data)

            else:
                # Météo normale
                weather_data = await asyncio.to_thread(get_weather_data, location)
                await update.message.reply_text(weather_data)

        except Exception as e:
            error_print(f"Erreur /weather: {e}")
            await update.message.reply_text(f"❌ Erreur météo: {str(e)[:80]}")

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
