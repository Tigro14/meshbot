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

        info_print(f"🔍 /db parsing: subcommand='{subcommand}', args={args}")

        # Obtenir le handler DB depuis le message router
        try:
            db_handler = self.telegram.message_handler.router.db_handler
            info_print(f"✅ db_handler trouvé: {db_handler is not None}")
        except AttributeError as e:
            error_msg = f"❌ Gestionnaire DB non disponible: {e}"
            info_print(error_msg)
            await update.message.reply_text("❌ Gestionnaire DB non disponible")
            return

        if not db_handler:
            info_print("❌ db_handler est None")
            await update.message.reply_text("❌ Gestionnaire DB non disponible")
            return

        def get_db_response():
            """Générer la réponse DB dans un thread"""
            try:
                info_print(f"🔄 get_db_response: subcommand='{subcommand}'")
                # Appeler directement les méthodes privées qui retournent du texte
                if subcommand == '':
                    result = db_handler._get_help('telegram')
                elif subcommand in ['stats', 's']:
                    info_print("📊 Appel _get_db_stats...")
                    result = db_handler._get_db_stats('telegram')
                    info_print(f"✅ _get_db_stats retourné: {len(result) if result else 0} chars")
                elif subcommand in ['clean', 'cleanup']:
                    result = db_handler._cleanup_db(args, 'telegram')
                elif subcommand in ['vacuum', 'v']:
                    result = db_handler._vacuum_db(args, 'telegram')
                elif subcommand in ['info', 'i']:
                    result = db_handler._get_db_info('telegram')
                elif subcommand in ['nb', 'neighbors']:
                    info_print("👥 Appel _get_neighbors_stats...")
                    result = db_handler._get_neighbors_stats('telegram')
                    info_print(f"✅ _get_neighbors_stats retourné: {len(result) if result else 0} chars")
                elif subcommand in ['mc', 'meshcore']:
                    info_print("📡 Appel _get_meshcore_table...")
                    result = db_handler._get_meshcore_table('telegram')
                    info_print(f"✅ _get_meshcore_table retourné: {len(result) if result else 0} chars")
                else:
                    result = db_handler._get_help('telegram')

                info_print(f"📤 Retour get_db_response: {len(result) if result else 0} chars")
                return result
            except Exception as e:
                from utils import error_print
                import traceback as tb
                error_print(f"Erreur DB command: {e}")
                error_print(tb.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"

        # Exécuter en thread pour ne pas bloquer
        info_print("⏳ Lancement asyncio.to_thread...")
        response = await asyncio.to_thread(get_db_response)
        info_print(f"✅ Thread terminé, réponse: {len(response) if response else 0} chars")

        # Diviser si trop long (limite Telegram: 4096 chars)
        # IMPORTANT: Ne pas utiliser parse_mode='Markdown' car peut causer des erreurs
        if response and len(response) > 4000:
            info_print(f"📦 Division en chunks ({len(response)} chars)")
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for idx, chunk in enumerate(chunks):
                info_print(f"📤 Envoi chunk {idx+1}/{len(chunks)}")
                await update.message.reply_text(chunk)
                await asyncio.sleep(0.5)
        else:
            info_print(f"📤 Envoi message direct")
            await update.message.reply_text(response or "✅ Commande exécutée")

        info_print("✅ /db command terminé")
