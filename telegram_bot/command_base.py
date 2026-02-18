#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classe de base pour les commandes Telegram
Fournit des fonctionnalités communes à toutes les commandes
"""

from telegram import Update
from telegram.ext import ContextTypes
from config import TELEGRAM_AUTHORIZED_USERS
from utils import info_print, error_print, debug_print
import traceback


class TelegramCommandBase:
    """Classe de base pour toutes les commandes Telegram"""

    def __init__(self, telegram_integration):
        """
        Initialiser la commande

        Args:
            telegram_integration: Instance de TelegramIntegration
        """
        self.telegram = telegram_integration
        self.message_handler = telegram_integration.message_handler
        self.node_manager = telegram_integration.node_manager
        self.context_manager = telegram_integration.context_manager
        self.traffic_monitor = telegram_integration.message_handler.traffic_monitor
        # Provide access to the bot's interface for commands that need to send messages
        self.interface = telegram_integration.message_handler.interface
        # Provide access to dual interface manager for network-specific commands
        self.dual_interface = getattr(telegram_integration.message_handler, 'dual_interface', None)

    def check_authorization(self, user_id):
        """
        Vérifier si l'utilisateur est autorisé

        Args:
            user_id: ID Telegram de l'utilisateur

        Returns:
            bool: True si autorisé, False sinon
        """
        if not TELEGRAM_AUTHORIZED_USERS:
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS

    async def send_message(self, update: Update, message: str):
        """
        Envoyer un message à l'utilisateur (avec gestion des messages longs)

        Args:
            update: Update Telegram
            message: Message à envoyer
        """
        # Découper les messages longs (limite Telegram: 4096 caractères)
        max_length = 4096
        if len(message) <= max_length:
            await update.message.reply_text(message)
        else:
            # Découper intelligemment par lignes
            chunks = self._split_message(message, max_length)
            for chunk in chunks:
                await update.message.reply_text(chunk)

    def _split_message(self, message, max_length=4096):
        """
        Découper un message en chunks de taille maximale

        Args:
            message: Message à découper
            max_length: Taille maximale d'un chunk

        Returns:
            list: Liste de chunks
        """
        if len(message) <= max_length:
            return [message]

        chunks = []
        lines = message.split('\n')
        current_chunk = ""

        for line in lines:
            # Si une seule ligne dépasse la limite, la découper brutalement
            if len(line) > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                # Découper la ligne en morceaux
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
                continue

            # Si ajouter cette ligne dépasse la limite, commencer un nouveau chunk
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def get_mesh_identity(self, telegram_user_id):
        """
        Obtenir l'identité Meshtastic d'un utilisateur Telegram

        Args:
            telegram_user_id: ID Telegram

        Returns:
            dict: {'node_id': int, 'short_name': str, 'display_name': str} ou None
        """
        return self.telegram._get_mesh_identity(telegram_user_id)

    def log_command(self, command_name, username, args=""):
        """
        Logger l'exécution d'une commande

        Args:
            command_name: Nom de la commande
            username: Nom d'utilisateur Telegram
            args: Arguments de la commande
        """
        if args:
            info_print(f"📱 Telegram /{command_name} {args}: {username}")
        else:
            info_print(f"📱 Telegram /{command_name}: {username}")

    async def handle_error(self, update: Update, error: Exception, context_message=""):
        """
        Gérer une erreur dans une commande

        Args:
            update: Update Telegram
            error: Exception levée
            context_message: Message de contexte
        """
        error_msg = f"❌ Erreur: {context_message}\n{str(error)}"
        error_print(error_msg)
        error_print(traceback.format_exc())

        # Envoyer un message d'erreur simplifié à l'utilisateur
        user_msg = f"❌ Erreur lors de l'exécution de la commande"
        if context_message:
            user_msg = f"❌ {context_message}"

        try:
            await update.message.reply_text(user_msg)
        except Exception as e:
            error_print(f"Impossible d'envoyer le message d'erreur: {e}")

    def get_command_args(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Obtenir les arguments d'une commande

        Args:
            context: Contexte Telegram

        Returns:
            list: Liste des arguments
        """
        return context.args if context.args else []

    def get_command_text(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Obtenir le texte complet des arguments d'une commande

        Args:
            context: Contexte Telegram

        Returns:
            str: Texte des arguments (joints par espaces)
        """
        return " ".join(context.args) if context.args else ""
