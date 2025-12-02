#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes réseau Telegram : nodes, fullnodes, nodeinfo, rx
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio
import time
import traceback

# Import optionnel de REMOTE_NODE_HOST/NAME avec fallback
try:
    from config import REMOTE_NODE_HOST, REMOTE_NODE_NAME
except ImportError:
    REMOTE_NODE_HOST = None
    REMOTE_NODE_NAME = "RemoteNode"


class NetworkCommands(TelegramCommandBase):
    """Gestionnaire des commandes réseau Telegram"""

    def __init__(self, telegram_integration):
        """
        Initialiser les commandes réseau

        Args:
            telegram_integration: Instance de TelegramIntegration
        """
        super().__init__(telegram_integration)
        self.mesh_commands = telegram_integration.mesh_commands
        self.stats_commands = telegram_integration.stats_commands

    async def rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx [page]"""
        user = update.effective_user
        page = int(context.args[0]) if context.args else 1
        info_print(f"📱 Telegram /rx {page}: {user.username}")

        response = await asyncio.to_thread(
            self.message_handler.remote_nodes_client.get_tigrog2_paginated,
            page
        )
        await update.effective_message.reply_text(response)

    async def nodes_command(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        """Commande /nodes - Affiche tous les nœuds directs de votre node"""
        user = update.effective_user
        info_print(f"📱 Telegram /nodes: {user.username}")

        def get_nodes_list():
            try:
                # Vérifier que REMOTE_NODE_HOST est configuré
                if not REMOTE_NODE_HOST:
                    return "❌ REMOTE_NODE_HOST non configuré dans config.py"

                nodes = self.message_handler.remote_nodes_client.get_remote_nodes(
                    REMOTE_NODE_HOST)
                if not nodes:
                    return f"❌ Aucun nœud trouvé sur {REMOTE_NODE_NAME}"

                nodes.sort(key=lambda x: x.get('snr', -999), reverse=True)
                lines = [
                    f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} ({len(nodes)}):\n"]

                for node in nodes:
                    name = node.get('name', 'Unknown')
                    snr = node.get('snr', 0.0)
                    rssi = node.get('rssi', 0)
                    last_heard = node.get('last_heard', 0)
                    hops_away = node.get('hops_away', 0)

                    elapsed = int(
                        time.time() - last_heard) if last_heard > 0 else 0
                    if elapsed < 60:
                        time_str = f"{elapsed}s"
                    elif elapsed < 3600:
                        time_str = f"{elapsed // 60}m"
                    elif elapsed < 86400:
                        time_str = f"{elapsed // 3600}h"
                    else:
                        time_str = f"{elapsed // 86400}j"

                    icon = "🟢" if snr >= 10 else "🟡" if snr >= 5 else "🟠" if snr >= 0 else "🔴"
                    lines.append(
                        f"{icon} {name}: SNR {snr:.1f}dB ({time_str})")

                return "\n".join(lines)
            except Exception as e:
                return f"❌ Erreur: {str(e)[:100]}"

        response = await asyncio.to_thread(get_nodes_list)
        await update.effective_message.reply_text(response)

    async def fullnodes_command(
            self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /fullnodes - Liste complète alphabétique des nœuds
        
        Usage:
            /fullnodes [days] [search_expr]
            
        Examples:
            /fullnodes                    -> Tous les nœuds (30 derniers jours)
            /fullnodes 7                  -> Tous les nœuds (7 derniers jours)
            /fullnodes tigro              -> Nœuds contenant 'tigro' (30j)
            /fullnodes 7 tigro            -> Nœuds contenant 'tigro' (7j)
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("Non autorisé")
            return

        # Extraire les arguments: [days] [search_expr]
        days = 30
        max_days = 365  # ✅ Limite raisonnable : 1 an
        search_expr = None

        if context.args and len(context.args) > 0:
            # Premier argument: soit un nombre de jours, soit une recherche
            try:
                requested_days = int(context.args[0])
                if requested_days > max_days:
                    # ✅ Informer l'utilisateur si demande excessive
                    await update.effective_message.reply_text(
                        f"⚠️ Maximum {max_days}j autorisé. Utilisation de {max_days}j."
                    )
                    days = max_days
                else:
                    days = max(1, requested_days)
                
                # Si il y a un second argument, c'est la recherche
                if len(context.args) > 1:
                    search_expr = ' '.join(context.args[1:])
            except ValueError:
                # Ce n'est pas un nombre, donc c'est directement une recherche
                search_expr = ' '.join(context.args)
                days = 30

        info_print(f"Telegram /fullnodes ({days}j, search='{search_expr}'): {user.username}")

        def get_full_nodes():
            try:
                return self.message_handler.remote_nodes_client.get_all_nodes_alphabetical(
                    days, search_expr=search_expr)
            except Exception as e:
                error_print(f"Erreur get_full_nodes: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"Erreur: {str(e)[:100]}"

        response = await asyncio.to_thread(get_full_nodes)

        # Telegram a une limite de 4096 caractères par message
        if len(response) > 4000:
            # Découper en plusieurs messages
            chunks = []
            lines = response.split('\n')
            current_chunk = []
            current_length = 0

            for line in lines:
                line_length = len(line) + 1  # +1 pour le \n
                if current_length + line_length > 4000:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_length = line_length
                else:
                    current_chunk.append(line)
                    current_length += line_length

            if current_chunk:
                chunks.append('\n'.join(current_chunk))

            # Envoyer les chunks
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await asyncio.sleep(1)  # Éviter rate limiting
                await update.effective_message.reply_text(chunk)
        else:
            await update.effective_message.reply_text(response)

    async def nodeinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /nodeinfo <nom_partiel_ou_id> [heures]
        Rapport détaillé sur un nœud spécifique

        AMÉLIORATION: Détecte et affiche tous les nœuds avec le même nom
        """
        user = update.effective_user
        if not context.args:
            await update.effective_message.reply_text("Usage: /nodeinfo <nom_ou_id> [heures]\\nEx: /nodeinfo tigrobot\\nEx: /nodeinfo !16fad3dc")
            return

        node_name_partial = context.args[0].lower()
        hours = 24
        if len(context.args) > 1:
            try:
                hours = int(context.args[1])
                hours = max(1, min(168, hours))
            except ValueError:
                hours = 24

        info_print(f"📱 Telegram /nodeinfo {node_name_partial} {hours}h: {user.username}")

        # Utiliser la logique métier partagée
        def get_node_report():
            success, report = self.mesh_commands.get_node_behavior_report(
                node_name_partial, hours
            )
            return report

        response = await asyncio.to_thread(get_node_report)

        # Diviser si trop long
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.effective_message.reply_text(chunk)
                await asyncio.sleep(0.5)
        else:
            await update.effective_message.reply_text(response)
