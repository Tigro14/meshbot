#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration des plateformes de messagerie
Centralise la configuration de Telegram, Discord, Matrix, etc.
"""

from platforms import PlatformConfig
from config import *


# ========================================
# CONFIGURATION TELEGRAM
# ========================================

TELEGRAM_PLATFORM_CONFIG = PlatformConfig(
    platform_name='telegram',
    enabled=TELEGRAM_ENABLED,  # Depuis config.py
    max_message_length=4096,   # Limite Telegram
    chunk_size=4000,
    ai_config=TELEGRAM_AI_CONFIG,  # Depuis config.py
    authorized_users=TELEGRAM_AUTHORIZED_USERS,  # Depuis config.py
    user_to_mesh_mapping=TELEGRAM_TO_MESH_MAPPING,  # Depuis config.py
    extra_config={
        'bot_token': TELEGRAM_BOT_TOKEN,
        'alert_users': TELEGRAM_ALERT_USERS,
        'polling_interval': 5.0,
        'timeout': 30,
    }
)


# ========================================
# CONFIGURATION DISCORD (FUTUR)
# ========================================

# À activer quand Discord sera implémenté
DISCORD_PLATFORM_CONFIG = PlatformConfig(
    platform_name='discord',
    enabled=False,  # Désactivé pour l'instant
    max_message_length=2000,  # Limite Discord
    chunk_size=1900,
    ai_config={
        "system_prompt": "Tu es un assistant Discord pour un réseau Meshtastic LoRa.",
        "max_tokens": 4000,
        "temperature": 0.8,
        "timeout": 120,
        "max_response_chars": 1900
    },
    authorized_users=[],  # Remplir avec les Discord user IDs
    user_to_mesh_mapping={},
    extra_config={
        'bot_token': '',  # Token Discord à remplir
        'guild_id': None,  # ID du serveur Discord
    }
)


# ========================================
# CONFIGURATION MATRIX (FUTUR)
# ========================================

MATRIX_PLATFORM_CONFIG = PlatformConfig(
    platform_name='matrix',
    enabled=False,  # Désactivé pour l'instant
    max_message_length=65536,  # Matrix supporte de longs messages
    chunk_size=60000,
    ai_config={
        "system_prompt": "Tu es un assistant Matrix pour un réseau Meshtastic LoRa.",
        "max_tokens": 4000,
        "temperature": 0.8,
        "timeout": 120,
        "max_response_chars": 60000
    },
    authorized_users=[],
    user_to_mesh_mapping={},
    extra_config={
        'homeserver': '',  # URL du serveur Matrix
        'user_id': '',  # @bot:matrix.org
        'access_token': '',
    }
)


# ========================================
# LISTE DES PLATEFORMES À ACTIVER
# ========================================

ENABLED_PLATFORMS = [
    TELEGRAM_PLATFORM_CONFIG,
    # DISCORD_PLATFORM_CONFIG,  # Décommenter quand implémenté
    # MATRIX_PLATFORM_CONFIG,   # Décommenter quand implémenté
]


def get_enabled_platforms():
    """
    Obtenir la liste des plateformes activées

    Returns:
        list: Liste des PlatformConfig activées
    """
    return [p for p in ENABLED_PLATFORMS if p.enabled]


def get_platform_config(platform_name: str):
    """
    Obtenir la configuration d'une plateforme par son nom

    Args:
        platform_name: Nom de la plateforme

    Returns:
        PlatformConfig ou None
    """
    for config in ENABLED_PLATFORMS:
        if config.platform_name == platform_name:
            return config
    return None
