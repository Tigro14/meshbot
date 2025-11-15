#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion des plateformes de messagerie
Permet d'intégrer Telegram, Discord, Matrix, etc.
"""

from .platform_interface import MessagingPlatform, PlatformConfig
from .platform_manager import PlatformManager

__all__ = ['MessagingPlatform', 'PlatformConfig', 'PlatformManager']
