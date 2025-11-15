#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Implémentation de la plateforme Discord (TEMPLATE)
À implémenter dans le futur pour supporter Discord
"""

from typing import Any
from .platform_interface import MessagingPlatform, PlatformConfig
from utils import info_print, error_print


class DiscordPlatform(MessagingPlatform):
    """
    Plateforme Discord - TEMPLATE POUR LE FUTUR
    Structure prête pour implémenter Discord quand nécessaire
    """

    def __init__(self, config: PlatformConfig, message_handler, node_manager, context_manager):
        """Initialiser la plateforme Discord"""
        super().__init__(config, message_handler, node_manager, context_manager)
        info_print("⚠️ DiscordPlatform : implémentation non disponible")

    @property
    def platform_name(self) -> str:
        """Nom de la plateforme"""
        return "discord"

    def start(self):
        """Démarrer Discord"""
        info_print("⏸️ Discord non implémenté")
        # TODO: Implémenter avec discord.py
        # self.bot = discord.Client(...)
        # await self.bot.start(token)

    def stop(self):
        """Arrêter Discord"""
        info_print("⏸️ Discord non implémenté")
        # TODO: await self.bot.close()

    def send_message(self, user_id: Any, message: str) -> bool:
        """Envoyer un message Discord"""
        # TODO: Implémenter
        # channel = await self.bot.fetch_channel(user_id)
        # await channel.send(message)
        return False

    def send_alert(self, message: str):
        """Envoyer une alerte Discord"""
        # TODO: Implémenter pour tous les utilisateurs autorisés
        pass


"""
EXEMPLE D'IMPLÉMENTATION FUTURE:

import discord
from discord.ext import commands

class DiscordPlatform(MessagingPlatform):
    def __init__(self, config, message_handler, node_manager, context_manager):
        super().__init__(config, message_handler, node_manager, context_manager)

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='/', intents=intents)

        # Enregistrer les commandes
        @self.bot.command()
        async def nodes(ctx):
            # Déléguer à NetworkCommands
            response = self.network_commands.get_nodes_list()
            await ctx.send(response)

        @self.bot.command()
        async def bot_command(ctx, *, question: str):
            # Déléguer à AICommands
            response = self.ai_commands.query_ai(question, platform='discord')
            await ctx.send(response)

    def start(self):
        self.bot.run(self.config.extra_config['token'])

    def send_message(self, channel_id, message):
        channel = await self.bot.fetch_channel(channel_id)
        await channel.send(message)

Configuration Discord:
DISCORD_CONFIG = PlatformConfig(
    platform_name='discord',
    enabled=False,  # Activer quand prêt
    max_message_length=2000,  # Limite Discord
    ai_config=DISCORD_AI_CONFIG,
    authorized_users=[...],
    extra_config={
        'token': 'DISCORD_BOT_TOKEN',
        'guild_id': 12345678
    }
)
"""
