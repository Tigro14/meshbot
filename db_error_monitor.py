#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moniteur d'erreurs de base de données avec auto-reboot
Surveille les échecs d'écriture persistants et déclenche un reboot automatique
"""

import time
from collections import deque
from typing import Optional, Callable, List, Tuple
from utils import info_print, error_print, debug_print
import logging

logger = logging.getLogger(__name__)


class DBErrorMonitor:
    """
    Moniteur des erreurs de base de données avec déclenchement automatique de reboot.
    
    Suit les erreurs d'écriture en base de données sur une fenêtre de temps glissante.
    Si le nombre d'erreurs dépasse un seuil sur une période donnée, déclenche un reboot
    automatique de l'application via le système de sémaphore existant.
    """
    
    def __init__(
        self,
        window_seconds: int = 300,  # 5 minutes
        error_threshold: int = 10,   # 10 erreurs
        enabled: bool = True,
        reboot_callback: Optional[Callable[[], bool]] = None,
        max_errors_stored: int = 100  # Limite de la deque
    ):
        """
        Initialise le moniteur d'erreurs DB.
        
        Args:
            window_seconds: Taille de la fenêtre de temps en secondes (défaut: 300 = 5min)
            error_threshold: Nombre d'erreurs nécessaires pour déclencher reboot
            enabled: Active/désactive le monitoring et auto-reboot
            reboot_callback: Fonction à appeler pour déclencher le reboot
                           Signature: reboot_callback() -> bool
            max_errors_stored: Nombre maximum d'erreurs à conserver en mémoire (défaut: 100)
        """
        self.window_seconds = window_seconds
        self.error_threshold = error_threshold
        self.enabled = enabled
        self.reboot_callback = reboot_callback
        self.max_errors_stored = max_errors_stored
        
        # File des erreurs avec timestamp
        # Structure: deque de (timestamp, exception, operation)
        self.errors = deque(maxlen=max_errors_stored)  # Limite pour éviter croissance illimitée
        
        # État du reboot
        self.reboot_triggered = False
        self.reboot_timestamp = None
        
        # Compteurs pour statistiques
        self.total_errors = 0
        self.total_reboots = 0
        
        if self.enabled:
            debug_print(f"🔍 Moniteur d'erreurs DB initialisé: fenêtre={window_seconds}s, seuil={error_threshold} erreurs")
        else:
            debug_print("ℹ️ Moniteur d'erreurs DB désactivé")
    
    def record_error(self, error: Exception, operation: str):
        """
        Enregistre une erreur d'écriture en base de données.
        
        Args:
            error: L'exception levée
            operation: Nom de l'opération qui a échoué (ex: 'save_packet')
        """
        if not self.enabled:
            return
        
        timestamp = time.time()
        self.errors.append((timestamp, error, operation))
        self.total_errors += 1
        
        # Log de l'erreur
        error_print(f"📝 Erreur DB enregistrée: {operation} - {type(error).__name__}: {error}")
        
        # Vérifier si le seuil est atteint
        self._check_threshold()
    
    def _check_threshold(self):
        """
        Vérifie si le nombre d'erreurs dans la fenêtre dépasse le seuil.
        Si oui, déclenche le reboot automatique.
        """
        # Si reboot déjà déclenché, ne pas re-déclencher
        if self.reboot_triggered:
            return
        
        # Nettoyer les erreurs hors de la fenêtre
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        # Compter les erreurs dans la fenêtre
        errors_in_window = [
            err for err in self.errors
            if err[0] > window_start
        ]
        
        error_count = len(errors_in_window)
        
        # Log de debug pour le suivi
        if error_count > 0:
            debug_print(f"🔍 Erreurs DB dans fenêtre ({self.window_seconds}s): {error_count}/{self.error_threshold}")
        
        # Vérifier le seuil
        if error_count >= self.error_threshold:
            self._trigger_reboot(error_count, errors_in_window)
    
    def _trigger_reboot(self, error_count: int, errors_in_window: List[Tuple[float, Exception, str]]):
        """
        Déclenche le reboot automatique de l'application.
        
        Args:
            error_count: Nombre d'erreurs détectées
            errors_in_window: Liste des erreurs dans la fenêtre
        """
        error_print("=" * 60)
        error_print("🚨 SEUIL D'ERREURS DB ATTEINT - REBOOT AUTOMATIQUE")
        error_print("=" * 60)
        error_print(f"📊 Erreurs détectées: {error_count} en {self.window_seconds}s")
        error_print(f"⚠️ Seuil configuré: {self.error_threshold} erreurs")
        
        # Log des types d'erreurs
        error_types = {}
        for _, err, op in errors_in_window:
            error_type = type(err).__name__
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        error_print("📝 Répartition des erreurs:")
        for error_type, count in error_types.items():
            error_print(f"   {error_type}: {count}")
        
        # Marquer comme déclenché
        self.reboot_triggered = True
        self.reboot_timestamp = time.time()
        self.total_reboots += 1
        
        # Appeler le callback de reboot si configuré
        if self.reboot_callback:
            try:
                info_print("🔄 Déclenchement du reboot via callback...")
                success = self.reboot_callback()
                if success:
                    info_print("✅ Signal de reboot envoyé avec succès")
                else:
                    error_print("❌ Échec du signal de reboot")
            except Exception as e:
                error_print(f"❌ Erreur lors du déclenchement du reboot: {e}")
                import traceback
                error_print(traceback.format_exc())
        else:
            error_print("⚠️ Aucun callback de reboot configuré - reboot non déclenché")
        
        error_print("=" * 60)
    
    def get_stats(self) -> dict:
        """
        Retourne les statistiques du moniteur.
        
        Returns:
            dict: Statistiques incluant compteurs et état
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        # Compter les erreurs dans la fenêtre actuelle
        errors_in_window = sum(
            1 for err in self.errors
            if err[0] > window_start
        )
        
        return {
            'enabled': self.enabled,
            'window_seconds': self.window_seconds,
            'error_threshold': self.error_threshold,
            'total_errors': self.total_errors,
            'errors_in_window': errors_in_window,
            'reboot_triggered': self.reboot_triggered,
            'reboot_timestamp': self.reboot_timestamp,
            'total_reboots': self.total_reboots
        }
    
    def get_status_report(self, compact: bool = False) -> str:
        """
        Génère un rapport d'état du moniteur.
        
        Args:
            compact: Si True, génère un rapport compact (pour LoRa)
        
        Returns:
            str: Rapport d'état formaté
        """
        stats = self.get_stats()
        
        if compact:
            # Format compact pour LoRa (< 180 chars)
            if not stats['enabled']:
                return "🔍 Moniteur DB: désactivé"
            
            status = "✅" if not stats['reboot_triggered'] else "🚨"
            return (
                f"{status} DB Monitor\n"
                f"Erreurs: {stats['errors_in_window']}/{stats['error_threshold']} "
                f"({stats['window_seconds']}s)\n"
                f"Total: {stats['total_errors']} err, {stats['total_reboots']} reboot"
            )
        
        # Format détaillé pour Telegram/CLI
        lines = []
        lines.append("🔍 Moniteur d'erreurs DB")
        lines.append("=" * 40)
        
        if not stats['enabled']:
            lines.append("État: ⚠️ Désactivé")
            return "\n".join(lines)
        
        lines.append(f"État: {'✅ Actif' if not stats['reboot_triggered'] else '🚨 Reboot déclenché'}")
        lines.append("")
        lines.append("Configuration:")
        lines.append(f"  Fenêtre: {stats['window_seconds']}s ({stats['window_seconds']//60} minutes)")
        lines.append(f"  Seuil: {stats['error_threshold']} erreurs")
        lines.append("")
        lines.append("Statistiques:")
        lines.append(f"  Erreurs (fenêtre): {stats['errors_in_window']}/{stats['error_threshold']}")
        lines.append(f"  Erreurs (total): {stats['total_errors']}")
        lines.append(f"  Reboots déclenchés: {stats['total_reboots']}")
        
        if stats['reboot_triggered'] and stats['reboot_timestamp']:
            elapsed = time.time() - stats['reboot_timestamp']
            lines.append("")
            lines.append(f"Dernier reboot: il y a {int(elapsed)}s")
        
        return "\n".join(lines)
    
    def reset(self):
        """
        Réinitialise le moniteur (pour tests ou après maintenance).
        """
        self.errors.clear()
        self.reboot_triggered = False
        self.reboot_timestamp = None
        info_print("🔄 Moniteur d'erreurs DB réinitialisé")
