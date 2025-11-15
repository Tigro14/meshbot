#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Implémentation de la plateforme Telegram
Wrapper autour de TelegramIntegration qui implémente MessagingPlatform
"""

from typing import Any, Optional
from .platform_interface import MessagingPlatform, PlatformConfig
from utils import info_print, error_print
import traceback


class TelegramPlatform(MessagingPlatform):
    """
    Plateforme Telegram implémentant l'interface MessagingPlatform
    Wrapper autour de TelegramIntegration pour abstraction
    """

    def __init__(self, config: PlatformConfig, message_handler, node_manager, context_manager):
        """
        Initialiser la plateforme Telegram

        Args:
            config: Configuration de la plateforme
            message_handler: Gestionnaire de messages Meshtastic
            node_manager: Gestionnaire de nœuds
            context_manager: Gestionnaire de contexte pour l'IA
        """
        super().__init__(config, message_handler, node_manager, context_manager)

        # Importer TelegramIntegration uniquement si Telegram est activé
        self.telegram_integration = None

        if config.enabled:
            try:
                # Import paresseux pour éviter les erreurs si python-telegram-bot n'est pas installé
                from telegram_integration import TelegramIntegration

                self.telegram_integration = TelegramIntegration(
                    message_handler,
                    node_manager,
                    context_manager
                )
                info_print("✅ TelegramPlatform initialisé")

            except ImportError as e:
                error_print(f"❌ Impossible d'importer TelegramIntegration: {e}")
                error_print("  Installez: pip3 install python-telegram-bot")
                self.config.enabled = False

            except Exception as e:
                error_print(f"❌ Erreur initialisation TelegramPlatform: {e}")
                error_print(traceback.format_exc())
                self.config.enabled = False

    @property
    def platform_name(self) -> str:
        """Nom de la plateforme"""
        return "telegram"

    def start(self):
        """Démarrer la plateforme Telegram"""
        if not self.config.enabled or not self.telegram_integration:
            info_print("⏸️ Telegram désactivé, pas de démarrage")
            return

        try:
            self.telegram_integration.start()
            self.running = True
            info_print("🤖 Plateforme Telegram démarrée")
        except Exception as e:
            error_print(f"❌ Erreur démarrage Telegram: {e}")
            error_print(traceback.format_exc())

    def stop(self):
        """Arrêter la plateforme Telegram"""
        if not self.telegram_integration:
            return

        try:
            self.telegram_integration.stop()
            self.running = False
            info_print("🛑 Plateforme Telegram arrêtée")
        except Exception as e:
            error_print(f"❌ Erreur arrêt Telegram: {e}")

    def send_message(self, user_id: Any, message: str) -> bool:
        """
        Envoyer un message à un utilisateur Telegram

        Args:
            user_id: ID Telegram de l'utilisateur
            message: Message à envoyer

        Returns:
            bool: True si envoyé avec succès
        """
        if not self.telegram_integration or not self.running:
            return False

        try:
            # Note: Cette fonctionnalité nécessite d'ajouter une méthode à TelegramIntegration
            # Pour l'instant, on retourne False
            # TODO: Implémenter send_direct_message dans TelegramIntegration
            info_print(f"📤 Envoi message à Telegram user {user_id}: {message[:50]}...")
            return False
        except Exception as e:
            error_print(f"❌ Erreur envoi message Telegram: {e}")
            return False

    def send_alert(self, message: str):
        """
        Envoyer une alerte aux utilisateurs Telegram autorisés

        Args:
            message: Message d'alerte
        """
        if not self.telegram_integration or not self.running:
            return

        try:
            self.telegram_integration.send_alert(message)
        except Exception as e:
            error_print(f"❌ Erreur envoi alerte Telegram: {e}")

    def handle_trace_response(self, from_id: int, message_text: str):
        """
        Gérer une réponse de traceroute texte

        Args:
            from_id: ID du nœud qui répond
            message_text: Texte de la réponse
        """
        if not self.telegram_integration or not self.running:
            return

        try:
            self.telegram_integration.handle_trace_response(from_id, message_text)
        except Exception as e:
            error_print(f"❌ Erreur handle_trace_response Telegram: {e}")

    def handle_traceroute_response(self, packet: Any, decoded: Any):
        """
        Gérer une réponse de traceroute native

        Args:
            packet: Paquet Meshtastic
            decoded: Données décodées
        """
        if not self.telegram_integration or not self.running:
            return

        try:
            self.telegram_integration.handle_traceroute_response(packet, decoded)
        except Exception as e:
            error_print(f"❌ Erreur handle_traceroute_response Telegram: {e}")
