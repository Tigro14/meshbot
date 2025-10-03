#!/usr/bin/env python3
"""
Module de surveillance du trafic des messages publics
Pour la commande /trafic (Telegram uniquement)
"""

import time
from collections import deque
from config import *
from utils import *

class TrafficMonitor:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        # File des messages publics avec limite de taille
        self.public_messages = deque(maxlen=200)  # Garder max 200 messages
        self.traffic_retention_hours = 8  # Heures de rétention
    
    def add_public_message(self, packet, message_text):
        """
        Enregistrer un message public dans l'historique
        À appeler depuis on_message() pour chaque message broadcast
        """
        try:
            from_id = packet.get('from', 0)
            timestamp = time.time()
            
            # Obtenir le nom du nœud
            sender_name = self.node_manager.get_node_name(from_id)
            
            # Enregistrer le message
            message_entry = {
                'timestamp': timestamp,
                'from_id': from_id,
                'sender_name': sender_name,
                'message': message_text,
                'rssi': packet.get('rssi', 0),
                'snr': packet.get('snr', 0.0)
            }
            
            self.public_messages.append(message_entry)
            debug_print(f"📝 Message public enregistré: {sender_name}: '{message_text[:30]}'")
            
        except Exception as e:
            debug_print(f"Erreur enregistrement message public: {e}")
    
    def get_traffic_report(self, hours=None):
        """
        Générer un rapport du trafic public des dernières heures
        
        Args:
            hours: Nombre d'heures à inclure (défaut: 8)
        
        Returns:
            str: Rapport formaté du trafic
        """
        if hours is None:
            hours = self.traffic_retention_hours
        
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # Filtrer les messages dans la période
            recent_messages = [
                msg for msg in self.public_messages
                if msg['timestamp'] >= cutoff_time
            ]
            
            if not recent_messages:
                return f"📭 Aucun message public dans les {hours}h"
            
            # Construire le rapport
            lines = []
            lines.append(f"📡 Trafic public ({len(recent_messages)} msgs - {hours}h):")
            lines.append("")
            
            # Limiter à 30 messages pour ne pas dépasser les limites Telegram
            display_messages = recent_messages[-30:]
            
            for msg in display_messages:
                # Format: [HH:MM] Nom: message
                timestamp_str = time.strftime("%H:%M", time.localtime(msg['timestamp']))
                sender_short = truncate_text(msg['sender_name'], 10)
                message_short = truncate_text(msg['message'], 50)
                
                # Ajouter indicateur de signal si disponible
                signal_icon = ""
                if msg['rssi'] != 0:
                    signal_icon = get_signal_quality_icon(msg['rssi']) + " "
                
                line = f"[{timestamp_str}] {signal_icon}{sender_short}: {message_short}"
                lines.append(line)
            
            # Ajouter footer si messages tronqués
            if len(recent_messages) > 30:
                lines.append("")
                lines.append(f"... et {len(recent_messages) - 30} messages plus anciens")
            
            # Statistiques rapides
            lines.append("")
            lines.append(self._get_traffic_stats(recent_messages, hours))
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur génération rapport trafic: {e}")
            return f"Erreur génération rapport: {str(e)[:50]}"
    
    def _get_traffic_stats(self, messages, hours):
        """Générer des statistiques sur le trafic"""
        try:
            # Compter les messages par expéditeur
            sender_counts = {}
            for msg in messages:
                sender = msg['sender_name']
                sender_counts[sender] = sender_counts.get(sender, 0) + 1
            
            # Top 3 expéditeurs
            top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            stats_lines = [f"📊 Stats {hours}h:"]
            stats_lines.append(f"Total: {len(messages)} msgs")
            
            if top_senders:
                stats_lines.append("Top émetteurs:")
                for sender, count in top_senders:
                    sender_short = truncate_text(sender, 12)
                    stats_lines.append(f"  • {sender_short}: {count}")
            
            return "\n".join(stats_lines)
            
        except Exception as e:
            debug_print(f"Erreur stats trafic: {e}")
            return f"Stats: {len(messages)} messages"
    
    def cleanup_old_messages(self):
        """Nettoyer les messages trop anciens (appelé périodiquement)"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (self.traffic_retention_hours * 3600)
            
            # Compter les messages à supprimer
            old_count = sum(1 for msg in self.public_messages if msg['timestamp'] < cutoff_time)
            
            # Filtrer pour ne garder que les récents
            # Note: deque ne permet pas de filtrer facilement, mais la limite maxlen s'en charge
            if old_count > 0:
                debug_print(f"🧹 {old_count} messages publics anciens expirés")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage messages: {e}")
    
    def get_message_count(self, hours=None):
        """Obtenir le nombre de messages dans la période"""
        if hours is None:
            hours = self.traffic_retention_hours
        
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        return sum(1 for msg in self.public_messages if msg['timestamp'] >= cutoff_time)
