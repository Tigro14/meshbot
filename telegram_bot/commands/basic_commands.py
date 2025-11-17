#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes Telegram basiques : start, help, legend, health
"""

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
import sys
import os
# Ajouter le répertoire parent au path pour importer depuis telegram/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio


class BasicCommands(TelegramCommandBase):
    """Gestionnaire des commandes basiques Telegram"""

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start - Message de bienvenue"""
        user = update.effective_user
        self.log_command("start", user.username)

        # Ajouter le handler pour les messages texte (non-commandes)
        try:
            self.telegram.application.add_handler(
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self._raw_log_handler),
                group=-1)
        except Exception as e:
            error_print(f"Erreur ajout raw_log_handler: {e}")

        welcome_msg = (
            f"🤖 Bot Meshtastic Bridge\n"
            f"Commandes:\n"
            f"• /bot - Chat IA\n"
            f"• /power - Batterie/solaire\n"
            f"• /weather - Météo Paris\n"
            f"• /rx [page]\n"
            f"• /sys\n"
            f"• /echo <msg>\n"
            f"• /annonce <msg>\n"
            f"• /nodes\n"
            f"• /health\n"
            f"• /nodeinfo\n"
            f"• /fullnodes [jours]\n"
            f"• /trafic [heures]\n"
            f"• /histo [type] [h]\n"
            f"• /top [h] [n]\n"
            f"• /stats\n"
            f"• /legend\n"
            f"• /cpu\n"
            f"• /help - Aide\n\n"
            f"Votre ID: {user.id}"
        )
        await update.effective_message.reply_text(welcome_msg)

    async def _raw_log_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler pour les messages texte non-commandes"""
        try:
            user = update.effective_user
            text = update.message.text
            info_print(f"📱 Telegram message (non-commande): {user.username}: {text[:50]}")
        except Exception as e:
            error_print(f"Erreur raw_log_handler: {e}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help - Aide détaillée pour Telegram"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return

        self.log_command("help", user.username)

        # Utiliser la version détaillée pour Telegram
        help_text = self.message_handler.format_help_telegram(user.id)

        # Debug
        info_print(f"DEBUG help_text length: {len(help_text) if help_text else 'None'}")
        info_print(f"DEBUG help_text preview: {help_text[:100] if help_text else 'None'}")

        if not help_text or len(help_text.strip()) == 0:
            await update.effective_message.reply_text("❌ Erreur: texte d'aide vide")
            return

        # Envoyer le message (sans Markdown pour éviter les erreurs)
        try:
            await self.send_message(update, help_text)
            info_print("✅ /help envoyé avec succès")
        except Exception as e:
            error_print(f"Erreur envoi /help: {e}")
            await update.effective_message.reply_text("❌ Erreur envoi aide")

    async def legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend - Légende des indicateurs de signal"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return

        self.log_command("legend", user.username)

        legend = self.message_handler.format_legend()
        await self.send_message(update, legend)

    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /health [heures]
        Analyse de santé du réseau mesh
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return

        # Parser les arguments
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(168, hours))  # Entre 1h et 7 jours
            except ValueError:
                hours = 24

        self.log_command("health", user.username, f"{hours}h")

        def get_health_report():
            """Générer le rapport de santé (fonction sync pour asyncio.to_thread)"""
            try:
                if not self.traffic_monitor:
                    return "❌ Traffic monitor non disponible"

                return self.traffic_monitor.analyze_network_health(hours)
            except Exception as e:
                error_print(f"Erreur health: {e}")
                return f"❌ Erreur: {str(e)[:100]}"

        # Exécuter dans un thread séparé (fonction sync)
        response = await asyncio.to_thread(get_health_report)

        # Envoyer la réponse (avec gestion des messages longs)
        await self.send_message(update, response)
