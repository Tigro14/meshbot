#!/usr/bin/env python3
"""
Module de surveillance du trafic avec statistiques avancées
Collecte les top talkers et génère des rapports détaillés
Version améliorée avec métriques complètes
"""

import time
from collections import deque, defaultdict
from datetime import datetime, timedelta
from config import *
from utils import *

class TrafficMonitor:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        # File des messages publics
        self.public_messages = deque(maxlen=2000)  # Augmenté pour meilleures stats
        self.traffic_retention_hours = 24
        
        # === NOUVELLES STRUCTURES POUR STATS ===
        # Statistiques par node_id
        self.node_stats = defaultdict(lambda: {
            'total_messages': 0,
            'total_chars': 0,
            'first_seen': None,
            'last_seen': None,
            'hourly_activity': defaultdict(int),  # Heure -> nombre de messages
            'daily_activity': defaultdict(int),   # Jour -> nombre de messages
            'avg_message_length': 0,
            'peak_hour': None,
            'commands_sent': 0,
            'echo_sent': 0
        })
        
        # Top mots utilisés (optionnel)
        self.word_frequency = defaultdict(int)
        
        # Statistiques globales
        self.global_stats = {
            'total_messages': 0,
            'total_unique_nodes': 0,
            'busiest_hour': None,
            'quietest_hour': None,
            'avg_messages_per_hour': 0,
            'peak_activity_time': None,
            'last_reset': time.time()
        }
    
    def add_public_message(self, packet, message_text):
        """
        Enregistrer un message public avec collecte de statistiques avancées
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
                'snr': packet.get('snr', 0.0),
                'message_length': len(message_text)
            }
            
            self.public_messages.append(message_entry)
            
            # === MISE À JOUR DES STATISTIQUES ===
            self._update_node_statistics(from_id, sender_name, message_text, timestamp)
            self._update_global_statistics(timestamp)
            
            # Analyser les commandes
            if message_text.startswith('/'):
                self.node_stats[from_id]['commands_sent'] += 1
                if message_text.startswith('/echo'):
                    self.node_stats[from_id]['echo_sent'] += 1
            
            debug_print(f"📊 Stats mises à jour pour {sender_name}: {self.node_stats[from_id]['total_messages']} msgs")
            
        except Exception as e:
            debug_print(f"Erreur enregistrement message public: {e}")
    
    def _update_node_statistics(self, node_id, sender_name, message_text, timestamp):
        """Mettre à jour les statistiques d'un nœud"""
        stats = self.node_stats[node_id]
        
        # Compteurs de base
        stats['total_messages'] += 1
        stats['total_chars'] += len(message_text)
        
        # Timestamps
        if stats['first_seen'] is None:
            stats['first_seen'] = timestamp
        stats['last_seen'] = timestamp
        
        # Activité horaire et journalière
        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        day_key = dt.strftime("%Y-%m-%d")
        
        stats['hourly_activity'][hour] += 1
        stats['daily_activity'][day_key] += 1
        
        # Moyenne de longueur de message
        stats['avg_message_length'] = stats['total_chars'] / stats['total_messages']
        
        # Heure de pointe pour ce nœud
        if stats['hourly_activity']:
            peak_hour = max(stats['hourly_activity'].items(), key=lambda x: x[1])
            stats['peak_hour'] = peak_hour[0]
    
    def _update_global_statistics(self, timestamp):
        """Mettre à jour les statistiques globales"""
        self.global_stats['total_messages'] += 1
        self.global_stats['total_unique_nodes'] = len(self.node_stats)
        
        # Calculer l'heure la plus active
        all_hourly = defaultdict(int)
        for node_stats in self.node_stats.values():
            for hour, count in node_stats['hourly_activity'].items():
                all_hourly[hour] += count
        
        if all_hourly:
            busiest = max(all_hourly.items(), key=lambda x: x[1])
            quietest = min(all_hourly.items(), key=lambda x: x[1])
            self.global_stats['busiest_hour'] = f"{busiest[0]}h ({busiest[1]} msgs)"
            self.global_stats['quietest_hour'] = f"{quietest[0]}h ({quietest[1]} msgs)"
    
    def get_top_talkers_report(self, hours=24, top_n=10):
        """
        Générer un rapport des top talkers
        
        Args:
            hours: Période à analyser (défaut: 24h)
            top_n: Nombre de top talkers à afficher (défaut: 10)
        
        Returns:
            str: Rapport formaté
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # Calculer les stats pour la période
            period_stats = defaultdict(lambda: {
                'messages': 0,
                'chars': 0,
                'last_seen': 0,
                'name': ''
            })
            
            for msg in self.public_messages:
                if msg['timestamp'] >= cutoff_time:
                    from_id = msg['from_id']
                    period_stats[from_id]['messages'] += 1
                    period_stats[from_id]['chars'] += msg['message_length']
                    period_stats[from_id]['last_seen'] = msg['timestamp']
                    period_stats[from_id]['name'] = msg['sender_name']
            
            if not period_stats:
                return f"📊 Aucune activité dans les {hours}h"
            
            # Trier par nombre de messages
            sorted_nodes = sorted(
                period_stats.items(),
                key=lambda x: x[1]['messages'],
                reverse=True
            )[:top_n]
            
            # Construire le rapport
            lines = []
            lines.append(f"🏆 TOP TALKERS ({hours}h)")
            lines.append(f"{'='*30}")
            
            total_messages = sum(s['messages'] for _, s in period_stats.items())
            
            for rank, (node_id, stats) in enumerate(sorted_nodes, 1):
                name = truncate_text(stats['name'], 15)
                msg_count = stats['messages']
                percentage = (msg_count / total_messages * 100) if total_messages > 0 else 0
                avg_len = stats['chars'] / msg_count if msg_count > 0 else 0
                
                # Icône selon le rang
                if rank == 1:
                    icon = "🥇"
                elif rank == 2:
                    icon = "🥈"
                elif rank == 3:
                    icon = "🥉"
                else:
                    icon = f"{rank}."
                
                # Barre de progression visuelle
                bar_length = int(percentage / 5)  # Max 20 caractères
                progress_bar = "█" * bar_length + "░" * (20 - bar_length)
                
                lines.append(f"\n{icon} {name}")
                lines.append(f"   {progress_bar}")
                lines.append(f"   📨 {msg_count} msgs ({percentage:.1f}%)")
                lines.append(f"   📝 Moy: {avg_len:.0f} chars")
                
                # Temps depuis dernier message
                time_str = format_elapsed_time(stats['last_seen'])
                lines.append(f"   ⏰ Dernier: {time_str}")
            
            # Statistiques globales
            lines.append(f"\n{'='*30}")
            lines.append(f"📊 STATISTIQUES GLOBALES")
            lines.append(f"{'='*30}")
            lines.append(f"Total messages: {total_messages}")
            lines.append(f"Nœuds actifs: {len(period_stats)}")
            lines.append(f"Moy/nœud: {total_messages/len(period_stats):.1f}")
            
            # Heure de pointe
            hourly_distribution = defaultdict(int)
            for msg in self.public_messages:
                if msg['timestamp'] >= cutoff_time:
                    hour = datetime.fromtimestamp(msg['timestamp']).hour
                    hourly_distribution[hour] += 1
            
            if hourly_distribution:
                peak = max(hourly_distribution.items(), key=lambda x: x[1])
                lines.append(f"Heure de pointe: {peak[0]:02d}h00 ({peak[1]} msgs)")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur génération top talkers: {e}")
            import traceback
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:50]}"
    
    def get_node_statistics(self, node_id):
        """
        Obtenir les statistiques détaillées d'un nœud spécifique
        
        Args:
            node_id: ID du nœud
        
        Returns:
            dict: Statistiques du nœud
        """
        if node_id in self.node_stats:
            return self.node_stats[node_id]
        return None
    
    def get_activity_pattern(self, hours=24):
        """
        Obtenir le pattern d'activité sur la période
        Retourne un graphique ASCII de l'activité par heure
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # Compter les messages par heure
            hourly_counts = defaultdict(int)
            for msg in self.public_messages:
                if msg['timestamp'] >= cutoff_time:
                    hour = datetime.fromtimestamp(msg['timestamp']).hour
                    hourly_counts[hour] += 1
            
            if not hourly_counts:
                return "📊 Aucune activité"
            
            # Créer le graphique ASCII
            max_count = max(hourly_counts.values())
            lines = ["📈 Activité par heure:"]
            lines.append("")
            
            for hour in range(24):
                count = hourly_counts.get(hour, 0)
                bar_length = int((count / max_count * 20)) if max_count > 0 else 0
                bar = "█" * bar_length + "░" * (20 - bar_length)
                lines.append(f"{hour:02d}h {bar} {count}")
            
            return "\n".join(lines)
            
        except Exception as e:
            debug_print(f"Erreur pattern activité: {e}")
            return "❌ Erreur génération pattern"
    
    def get_quick_stats(self):
        """
        Obtenir des stats rapides pour affichage concis
        Format court pour Meshtastic
        """
        try:
            # Stats des dernières 3 heures pour concision
            current_time = time.time()
            cutoff_time = current_time - (3 * 3600)
            
            recent_messages = [
                msg for msg in self.public_messages
                if msg['timestamp'] >= cutoff_time
            ]
            
            if not recent_messages:
                return "📊 Silence radio (3h)"
            
            # Top 3 talkers
            talker_counts = defaultdict(int)
            for msg in recent_messages:
                talker_counts[msg['sender_name']] += 1
            
            top_3 = sorted(talker_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            lines = [f"🏆TOP 3h ({len(recent_messages)} msgs):"]
            for i, (name, count) in enumerate(top_3, 1):
                name_short = truncate_text(name, 8)
                lines.append(f"{i}.{name_short}:{count}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return "❌ Erreur stats"
    
    def reset_statistics(self):
        """Réinitialiser toutes les statistiques"""
        self.node_stats.clear()
        self.word_frequency.clear()
        self.global_stats = {
            'total_messages': 0,
            'total_unique_nodes': 0,
            'busiest_hour': None,
            'quietest_hour': None,
            'avg_messages_per_hour': 0,
            'peak_activity_time': None,
            'last_reset': time.time()
        }
        debug_print("📊 Statistiques réinitialisées")
    
    def cleanup_old_messages(self):
        """Nettoyer les messages trop anciens"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (self.traffic_retention_hours * 3600)
            
            # Compter les messages à supprimer
            old_count = sum(1 for msg in self.public_messages if msg['timestamp'] < cutoff_time)
            
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
    
    def export_statistics(self):
        """
        Exporter les statistiques en format JSON (pour analyse externe)
        """
        try:
            export_data = {
                'timestamp': time.time(),
                'global_stats': self.global_stats,
                'node_stats': dict(self.node_stats),
                'message_count_24h': self.get_message_count(24),
                'message_count_1h': self.get_message_count(1)
            }
            
            import json
            return json.dumps(export_data, indent=2)
            
        except Exception as e:
            error_print(f"Erreur export stats: {e}")
            return "{}"
