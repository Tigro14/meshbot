#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire centralisé des plateformes de messagerie
Gère le cycle de vie de toutes les plateformes actives
"""

from typing import Dict, List, Optional
from .platform_interface import MessagingPlatform
from utils import info_print, error_print


class PlatformManager:
    """
    Gestionnaire centralisé pour toutes les plateformes de messagerie
    Permet d'activer/désactiver dynamiquement Telegram, Discord, etc.
    """

    def __init__(self):
        """Initialiser le gestionnaire de plateformes"""
        self.platforms: Dict[str, MessagingPlatform] = {}
        info_print("🌐 PlatformManager initialisé")

    def register_platform(self, platform: MessagingPlatform):
        """
        Enregistrer une plateforme

        Args:
            platform: Instance de MessagingPlatform
        """
        platform_name = platform.platform_name

        if platform_name in self.platforms:
            error_print(f"⚠️ Plateforme {platform_name} déjà enregistrée")
            return

        if not platform.is_enabled():
            info_print(f"⏸️ Plateforme {platform_name} désactivée (not registered)")
            return

        self.platforms[platform_name] = platform
        info_print(f"✅ Plateforme {platform_name} enregistrée")

    def unregister_platform(self, platform_name: str):
        """
        Désenregistrer une plateforme

        Args:
            platform_name: Nom de la plateforme
        """
        if platform_name in self.platforms:
            platform = self.platforms[platform_name]
            if platform.running:
                platform.stop()
            del self.platforms[platform_name]
            info_print(f"❌ Plateforme {platform_name} désenregistrée")

    def get_platform(self, platform_name: str) -> Optional[MessagingPlatform]:
        """
        Obtenir une plateforme par son nom

        Args:
            platform_name: Nom de la plateforme

        Returns:
            MessagingPlatform ou None
        """
        return self.platforms.get(platform_name)

    def start_all(self):
        """Démarrer toutes les plateformes enregistrées"""
        info_print(f"🚀 Démarrage de {len(self.platforms)} plateforme(s)...")

        for platform_name, platform in self.platforms.items():
            try:
                info_print(f"  Démarrage {platform_name}...")
                platform.start()
            except Exception as e:
                error_print(f"❌ Erreur démarrage {platform_name}: {e}")

    def stop_all(self):
        """Arrêter toutes les plateformes"""
        info_print(f"🛑 Arrêt de {len(self.platforms)} plateforme(s)...")

        for platform_name, platform in self.platforms.items():
            try:
                info_print(f"  Arrêt {platform_name}...")
                platform.stop()
            except Exception as e:
                error_print(f"❌ Erreur arrêt {platform_name}: {e}")

    def send_alert_to_all(self, message: str):
        """
        Envoyer une alerte sur toutes les plateformes

        Args:
            message: Message d'alerte
        """
        for platform_name, platform in self.platforms.items():
            try:
                platform.send_alert(message)
            except Exception as e:
                error_print(f"❌ Erreur envoi alerte sur {platform_name}: {e}")

    def get_active_platforms(self) -> List[str]:
        """
        Obtenir la liste des plateformes actives

        Returns:
            list: Liste des noms de plateformes actives
        """
        return [name for name, platform in self.platforms.items() if platform.running]

    def get_all_platforms(self) -> List[str]:
        """
        Obtenir la liste de toutes les plateformes enregistrées

        Returns:
            list: Liste des noms de plateformes
        """
        return list(self.platforms.keys())

    def is_platform_active(self, platform_name: str) -> bool:
        """
        Vérifier si une plateforme est active

        Args:
            platform_name: Nom de la plateforme

        Returns:
            bool: True si active
        """
        platform = self.platforms.get(platform_name)
        return platform.running if platform else False

    def handle_trace_response(self, from_id: int, message_text: str):
        """
        Distribuer une réponse de traceroute à toutes les plateformes

        Args:
            from_id: ID du nœud qui répond
            message_text: Texte de la réponse
        """
        for platform in self.platforms.values():
            try:
                platform.handle_trace_response(from_id, message_text)
            except Exception as e:
                error_print(f"Erreur trace response sur {platform.platform_name}: {e}")

    def handle_traceroute_response(self, packet, decoded):
        """
        Distribuer une réponse de traceroute native à toutes les plateformes

        Args:
            packet: Paquet Meshtastic
            decoded: Données décodées
        """
        for platform in self.platforms.values():
            try:
                platform.handle_traceroute_response(packet, decoded)
            except Exception as e:
                error_print(f"Erreur traceroute response sur {platform.platform_name}: {e}")
