#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interface abstraite pour les plateformes de messagerie
Définit le contrat que chaque plateforme doit implémenter
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
from utils import info_print


@dataclass
class PlatformConfig:
    """Configuration d'une plateforme de messagerie"""

    # Identité de la plateforme
    platform_name: str                  # "telegram", "discord", "matrix"
    enabled: bool = True                # Activer/désactiver la plateforme

    # Limites de messages
    max_message_length: int = 4096      # Taille max d'un message (Telegram: 4096, Discord: 2000)
    chunk_size: int = 4000              # Taille des chunks pour messages longs

    # Configuration IA
    ai_config: Dict[str, Any] = None    # Config spécifique pour l'IA

    # Autorisation
    authorized_users: list = None       # Liste des utilisateurs autorisés (vide = tous)

    # Mapping utilisateurs vers identités Mesh
    user_to_mesh_mapping: Dict[int, Dict[str, Any]] = None

    # Autres configurations spécifiques
    extra_config: Dict[str, Any] = None


class MessagingPlatform(ABC):
    """
    Interface abstraite pour une plateforme de messagerie
    Toutes les plateformes (Telegram, Discord, etc.) doivent implémenter cette interface
    """

    def __init__(self, config: PlatformConfig, message_handler, node_manager, context_manager):
        """
        Initialiser la plateforme

        Args:
            config: Configuration de la plateforme
            message_handler: Gestionnaire de messages Meshtastic
            node_manager: Gestionnaire de nœuds
            context_manager: Gestionnaire de contexte pour l'IA
        """
        self.config = config
        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager
        self.running = False

        info_print(f"📱 Initialisation plateforme: {config.platform_name}")

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Nom de la plateforme (telegram, discord, etc.)"""
        pass

    @abstractmethod
    def start(self):
        """Démarrer la plateforme"""
        pass

    @abstractmethod
    def stop(self):
        """Arrêter la plateforme"""
        pass

    @abstractmethod
    def send_message(self, user_id: Any, message: str) -> bool:
        """
        Envoyer un message à un utilisateur

        Args:
            user_id: ID de l'utilisateur (int pour Telegram, str pour Discord)
            message: Message à envoyer

        Returns:
            bool: True si envoyé avec succès
        """
        pass

    @abstractmethod
    def send_alert(self, message: str):
        """
        Envoyer une alerte aux utilisateurs autorisés

        Args:
            message: Message d'alerte
        """
        pass

    def check_authorization(self, user_id: Any) -> bool:
        """
        Vérifier si un utilisateur est autorisé

        Args:
            user_id: ID de l'utilisateur

        Returns:
            bool: True si autorisé
        """
        if not self.config.authorized_users:
            return True
        return user_id in self.config.authorized_users

    def get_mesh_identity(self, user_id: Any) -> Optional[Dict[str, Any]]:
        """
        Obtenir l'identité Meshtastic d'un utilisateur

        Args:
            user_id: ID de l'utilisateur sur la plateforme

        Returns:
            dict: {'node_id': int, 'short_name': str, 'display_name': str} ou None
        """
        if not self.config.user_to_mesh_mapping:
            return None
        return self.config.user_to_mesh_mapping.get(user_id)

    def get_ai_config(self) -> Dict[str, Any]:
        """
        Obtenir la configuration IA pour cette plateforme

        Returns:
            dict: Configuration IA
        """
        return self.config.ai_config or {}

    def is_enabled(self) -> bool:
        """Vérifier si la plateforme est activée"""
        return self.config.enabled

    # Méthodes optionnelles que les plateformes peuvent surcharger

    def handle_trace_response(self, from_id: int, message_text: str):
        """
        Gérer une réponse de traceroute (optionnel)

        Args:
            from_id: ID du nœud qui répond
            message_text: Texte de la réponse
        """
        pass

    def handle_traceroute_response(self, packet: Any, decoded: Any):
        """
        Gérer une réponse de traceroute native (optionnel)

        Args:
            packet: Paquet Meshtastic
            decoded: Données décodées
        """
        pass

    def register_command_handler(self, command: str, handler: Callable):
        """
        Enregistrer un handler de commande personnalisé (optionnel)

        Args:
            command: Nom de la commande (sans le /)
            handler: Fonction handler
        """
        pass
