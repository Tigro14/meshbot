#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes DB Telegram : db (gestion base de données)
Utilise la classe DBCommands partagée avec le canal Mesh
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print
import asyncio


class DBCommandsTelegram(TelegramCommandBase):
    """Gestionnaire des commandes DB Telegram"""

    async def db_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /db [subcommand] [args] - Gestion de la base de données

        Sous-commandes:
        - stats: Statistiques DB
        - info: Informations détaillées
        - clean [hours]: Nettoyer données anciennes
        - vacuum: Optimiser DB (VACUUM)

        Exemples:
        /db stats
        /db clean 72
        /db vacuum
        """
        user = update.effective_user
        info_print(f"📱 Telegram /db: {user.username or user.first_name}")

        # Parser les arguments
        params = context.args if context.args else []
        subcommand = params[0].lower() if params else ''
        args = params[1:] if len(params) > 1 else []

        # Obtenir le handler DB depuis le bot
        db_handler = self.telegram.meshbot.message_handler.router.db_handler

        if not db_handler:
            await update.message.reply_text("❌ Gestionnaire DB non disponible")
            return

        def get_db_response():
            """Générer la réponse DB dans un thread"""
            try:
                # Appeler directement les méthodes privées qui retournent du texte
                if subcommand == '':
                    return db_handler._get_help('telegram')
                elif subcommand in ['stats', 's']:
                    return db_handler._get_db_stats('telegram')
                elif subcommand in ['clean', 'cleanup']:
                    return db_handler._cleanup_db(args, 'telegram')
                elif subcommand in ['vacuum', 'v']:
                    return db_handler._vacuum_db('telegram')
                elif subcommand in ['info', 'i']:
                    return db_handler._get_db_info('telegram')
                else:
                    return db_handler._get_help('telegram')
            except Exception as e:
                from utils import error_print
                import traceback as tb
                error_print(f"Erreur DB command: {e}")
                error_print(tb.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"

        # Exécuter en thread pour ne pas bloquer
        response = await asyncio.to_thread(get_db_response)

        # Diviser si trop long (limite Telegram: 4096 chars)
        if response and len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='Markdown')
                await asyncio.sleep(0.5)
        else:
            await update.message.reply_text(response or "✅ Commande exécutée", parse_mode='Markdown')
