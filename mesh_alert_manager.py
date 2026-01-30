#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire d'alertes pour Meshtastic (DM)
Envoie des alertes critiques aux nœuds abonnés via Direct Messages
"""

import time
from typing import List, Dict, Optional
from utils import info_print, error_print, debug_print


class MeshAlertManager:
    """
    Gestionnaire centralisé pour les alertes Meshtastic via DM
    
    Envoie des alertes critiques (vigilance météo, éclairs) aux nœuds
    abonnés via Direct Messages Meshtastic.
    """
    
    def __init__(self, message_sender, subscribed_nodes: List[int], 
                 throttle_seconds: int = 1800):
        """
        Initialiser le gestionnaire d'alertes Mesh
        
        Args:
            message_sender: Instance de MessageSender pour envoyer les DMs
            subscribed_nodes: Liste d'IDs de nœuds à alerter (int)
            throttle_seconds: Temps minimum entre deux alertes identiques (défaut: 30min)
        """
        self.message_sender = message_sender
        self.subscribed_nodes = subscribed_nodes
        self.throttle_seconds = throttle_seconds
        
        # Tracking des alertes envoyées pour throttling
        # Format: {node_id: {alert_type: last_alert_time}}
        self._alert_history: Dict[int, Dict[str, float]] = {}
        
        # Compteurs statistiques
        self.total_alerts_sent = 0
        self.alerts_throttled = 0
        
        if subscribed_nodes:
            info_print(f"📢 MeshAlertManager initialisé")
            info_print(f"   Nœuds abonnés: {len(subscribed_nodes)}")
            info_print(f"   IDs: {', '.join(hex(n) for n in subscribed_nodes)}")
            info_print(f"   Throttle: {throttle_seconds}s ({throttle_seconds//60}min)")
        else:
            debug_print("📢 MeshAlertManager: Aucun nœud abonné aux alertes")
    
    def send_alert(self, alert_type: str, message: str, force: bool = False) -> int:
        """
        Envoyer une alerte à tous les nœuds abonnés
        
        Args:
            alert_type: Type d'alerte (ex: "vigilance", "blitz") pour throttling
            message: Message d'alerte à envoyer (format compact LoRa)
            force: Ignorer le throttling si True (défaut: False)
        
        Returns:
            int: Nombre de nœuds ayant reçu l'alerte
        """
        if not self.subscribed_nodes:
            debug_print(f"📢 Alerte {alert_type}: Aucun nœud abonné")
            return 0
        
        if not message:
            error_print(f"❌ Alerte {alert_type}: Message vide")
            return 0
        
        current_time = time.time()
        sent_count = 0
        
        info_print(f"📢 Envoi alerte {alert_type} à {len(self.subscribed_nodes)} nœud(s)")
        debug_print(f"   Message: {message[:50]}...")
        
        for node_id in self.subscribed_nodes:
            try:
                # Vérifier le throttling (sauf si force=True)
                if not force and not self._should_send_alert(node_id, alert_type, current_time):
                    debug_print(f"   → 0x{node_id:08x}: Throttlé")
                    self.alerts_throttled += 1
                    continue
                
                # Récupérer le nom du nœud pour les logs
                node_name = f"0x{node_id:08x}"
                node_info = {"name": node_name}
                
                # Envoyer le DM via MessageSender
                debug_print(f"   → {node_name}: Envoi DM...")
                self.message_sender.send_single(message, node_id, node_info)
                
                # Enregistrer l'envoi pour throttling
                self._record_alert_sent(node_id, alert_type, current_time)
                
                sent_count += 1
                info_print(f"✅ Alerte envoyée à {node_name}")
                
            except Exception as e:
                error_print(f"❌ Erreur envoi alerte à 0x{node_id:08x}: {e}")
                import traceback
                debug_print(traceback.format_exc())
        
        self.total_alerts_sent += sent_count
        
        if sent_count > 0:
            info_print(f"📊 Alerte {alert_type}: {sent_count}/{len(self.subscribed_nodes)} envoyées")
        
        return sent_count
    
    def _should_send_alert(self, node_id: int, alert_type: str, current_time: float) -> bool:
        """
        Vérifier si une alerte doit être envoyée (throttling)
        
        Args:
            node_id: ID du nœud
            alert_type: Type d'alerte
            current_time: Timestamp actuel
        
        Returns:
            bool: True si l'alerte doit être envoyée
        """
        # Premier envoi pour ce nœud
        if node_id not in self._alert_history:
            return True
        
        # Premier envoi de ce type d'alerte pour ce nœud
        if alert_type not in self._alert_history[node_id]:
            return True
        
        # Vérifier le temps écoulé depuis dernière alerte
        last_alert_time = self._alert_history[node_id][alert_type]
        time_elapsed = current_time - last_alert_time
        
        if time_elapsed < self.throttle_seconds:
            # Throttlé
            time_remaining = int(self.throttle_seconds - time_elapsed)
            debug_print(f"   Alerte {alert_type} throttlée pour 0x{node_id:08x}: "
                       f"{time_remaining}s restants")
            return False
        
        return True
    
    def _record_alert_sent(self, node_id: int, alert_type: str, timestamp: float):
        """
        Enregistrer l'envoi d'une alerte pour le throttling
        
        Args:
            node_id: ID du nœud
            alert_type: Type d'alerte
            timestamp: Timestamp de l'envoi
        """
        if node_id not in self._alert_history:
            self._alert_history[node_id] = {}
        
        self._alert_history[node_id][alert_type] = timestamp
    
    def cleanup_old_history(self, max_age_seconds: int = 7200):
        """
        Nettoyer l'historique des alertes anciennes (> 2h par défaut)
        
        Args:
            max_age_seconds: Age maximum pour conserver l'historique
        """
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds
        
        cleaned_count = 0
        
        for node_id in list(self._alert_history.keys()):
            for alert_type in list(self._alert_history[node_id].keys()):
                if self._alert_history[node_id][alert_type] < cutoff_time:
                    del self._alert_history[node_id][alert_type]
                    cleaned_count += 1
            
            # Supprimer le nœud si plus d'alertes
            if not self._alert_history[node_id]:
                del self._alert_history[node_id]
        
        if cleaned_count > 0:
            debug_print(f"🧹 Nettoyage historique alertes: {cleaned_count} entrées supprimées")
    
    def get_stats(self) -> Dict:
        """
        Obtenir les statistiques du gestionnaire d'alertes
        
        Returns:
            dict: Statistiques (total envoyé, throttlé, etc.)
        """
        return {
            'subscribed_nodes': len(self.subscribed_nodes),
            'total_alerts_sent': self.total_alerts_sent,
            'alerts_throttled': self.alerts_throttled,
            'active_history_entries': sum(len(alerts) for alerts in self._alert_history.values())
        }
    
    def get_status_report(self, compact: bool = True) -> str:
        """
        Générer un rapport de statut
        
        Args:
            compact: True pour format court (LoRa), False pour long (Telegram)
        
        Returns:
            str: Rapport formaté
        """
        stats = self.get_stats()
        
        if compact:
            # Format court
            lines = [
                f"📢 Alertes Mesh: {stats['subscribed_nodes']} nœuds",
                f"Envoyées: {stats['total_alerts_sent']}",
                f"Throttlées: {stats['alerts_throttled']}"
            ]
        else:
            # Format détaillé
            lines = [
                "📢 STATUT ALERTES MESH",
                f"Nœuds abonnés: {stats['subscribed_nodes']}",
                f"Total alertes envoyées: {stats['total_alerts_sent']}",
                f"Alertes throttlées: {stats['alerts_throttled']}",
                f"Historique actif: {stats['active_history_entries']} entrées"
            ]
            
            if self.subscribed_nodes:
                lines.append("")
                lines.append("Nœuds abonnés:")
                for node_id in self.subscribed_nodes:
                    node_hex = f"0x{node_id:08x}"
                    lines.append(f"  - {node_hex}")
        
        return '\n'.join(lines)
