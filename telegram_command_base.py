#!/usr/bin/env python3
"""
Classe de base pour les commandes Telegram
Fournit des utilitaires communs à toutes les commandes
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes


class TelegramCommandBase:
    """
    Classe de base pour les gestionnaires de commandes Telegram
    """

    def __init__(self, telegram_integration):
        """
        Args:
            telegram_integration: Instance de TelegramIntegration parente
        """
        self.integration = telegram_integration
        self.message_handler = telegram_integration.message_handler
        self.node_manager = telegram_integration.node_manager
        self.context_manager = telegram_integration.context_manager
        self.application = telegram_integration.application
        self.loop = telegram_integration.loop

    def _check_authorization(self, user_id):
        """
        Vérifier si l'utilisateur est autorisé

        Args:
            user_id: Telegram user ID

        Returns:
            bool: True si autorisé
        """
        return self.integration._check_authorization(user_id)

    async def run_sync_in_thread(self, sync_func, *args, **kwargs):
        """
        Exécuter une fonction synchrone dans un thread séparé

        Args:
            sync_func: Fonction synchrone à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés

        Returns:
            Résultat de la fonction
        """
        return await asyncio.to_thread(sync_func, *args, **kwargs)

    async def send_long_message(self, update: Update, message: str, chunk_size: int = 4000):
        """
        Envoyer un message long en le divisant en chunks si nécessaire

        Args:
            update: Telegram Update object
            message: Message à envoyer
            chunk_size: Taille maximale des chunks (défaut: 4000)
        """
        if len(message) > chunk_size:
            chunks = [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
                await asyncio.sleep(0.5)
        else:
            await update.message.reply_text(message)

    def log_command(self, command_name: str, username: str, args: str = ""):
        """
        Logger une commande exécutée

        Args:
            command_name: Nom de la commande
            username: Nom d'utilisateur Telegram
            args: Arguments optionnels
        """
        from utils import info_print
        if args:
            info_print(f"📱 Telegram /{command_name} {args}: {username}")
        else:
            info_print(f"📱 Telegram /{command_name}: {username}")
