#!/usr/bin/env python3
import traceback
"""
Module de surveillance du trafic avec statistiques avancées
Collecte TOUS les types de paquets Meshtastic
Version complète avec métriques par type de paquet
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
        self.public_messages = deque(maxlen=2000)
        # File de TOUS les paquets
        self.all_packets = deque(maxlen=5000)  # Plus grand pour tous les types
        self.traffic_retention_hours = 24

        # === HISTOGRAMME : COLLECTE PAR TYPE DE PAQUET ===
        self.packet_history = deque(maxlen=5000)  # Tous les paquets (24h)
        self.packet_types = {
            'TEXT_MESSAGE_APP': 'messages',
            'POSITION_APP': 'pos',
            'NODEINFO_APP': 'info',
            'TELEMETRY_APP': 'telemetry',
            'TRACEROUTE_APP': 'traceroute',
            'ROUTING_APP': 'routing'
        }
        
        # === MAPPING DES TYPES DE PAQUETS ===
        self.packet_type_names = {
            'TEXT_MESSAGE_APP': '💬 Messages',
            'POSITION_APP': '📍 Position',
            'NODEINFO_APP': 'ℹ️ NodeInfo',
            'ROUTING_APP': '🔀 Routage',
            'ADMIN_APP': '⚙️ Admin',
            'TELEMETRY_APP': '📊 Télémétrie',
            'WAYPOINT_APP': '📌 Waypoint',
            'REPLY_APP': '↩️ Réponse',
            'REMOTE_HARDWARE_APP': '🔧 Hardware',
            'SIMULATOR_APP': '🎮 Simulateur',
            'TRACEROUTE_APP': '🔍 Traceroute',
            'NEIGHBORINFO_APP': '👥 Voisins',
            'ATAK_PLUGIN': '🎯 ATAK',
            'PRIVATE_APP': '🔒 Privé',
            'RANGE_TEST_APP': '📡 RangeTest',
            'ENVIRONMENTAL_MEASUREMENT_APP': '🌡️ Environnement',
            'AUDIO_APP': '🎵 Audio',
            'DETECTION_SENSOR_APP': '👁️ Détection',
            'STORE_FORWARD_APP': '💾 StoreForward',
            'PAXCOUNTER_APP': '🚶 Paxcounter',
            'UNKNOWN': '❓ Inconnu'
        }
        
        # === STATISTIQUES PAR NODE ET TYPE ===
        self.node_packet_stats = defaultdict(lambda: {
            'total_packets': 0,
            'by_type': defaultdict(int),  # Type -> count
            'total_bytes': 0,
            'first_seen': None,
            'last_seen': None,
            'hourly_activity': defaultdict(int),
            'message_stats': {  # Stats spécifiques aux messages texte
                'count': 0,
                'total_chars': 0,
                'avg_length': 0
            },
            'telemetry_stats': {  # Stats télémétrie
                'count': 0,
                'last_battery': None,
                'last_voltage': None,
                'last_channel_util': None,
                'last_air_util': None
            },
            'position_stats': {  # Stats position
                'count': 0,
                'last_lat': None,
                'last_lon': None,
                'last_alt': None
            },
            'routing_stats': {  # Stats routage
                'count': 0,
                'packets_relayed': 0,
                'packets_originated': 0
            }
        })
        
        # === STATISTIQUES GLOBALES PAR TYPE ===
        self.global_packet_stats = {
            'total_packets': 0,
            'by_type': defaultdict(int),
            'total_bytes': 0,
            'unique_nodes': set(),
            'busiest_hour': None,
            'quietest_hour': None,
            'last_reset': time.time()
        }
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
        # === STATISTIQUES RÉSEAU ===
        self.network_stats = {
            'total_hops': 0,
            'max_hops_seen': 0,
            'avg_rssi': 0.0,
            'avg_snr': 0.0,
            'packets_direct': 0,
            'packets_relayed': 0
        }
    
    def add_packet(self, packet):
        """
        Enregistrer TOUT type de paquet avec statistiques complètes
        """
        try:
            from_id = packet.get('from', 0)
            to_id = packet.get('to', 0)
            timestamp = time.time()
            
            # Identifier le type de paquet
            packet_type = 'UNKNOWN'
            message_text = None
            
            if 'decoded' in packet:
                decoded = packet['decoded']
                packet_type = decoded.get('portnum', 'UNKNOWN')
                
                # Si c'est un message texte, extraire le contenu
                if packet_type == 'TEXT_MESSAGE_APP':
                    message_text = self._extract_message_text(decoded)
            
            # Obtenir le nom du nœud
            sender_name = self.node_manager.get_node_name(from_id)
            
            # Calculer la taille approximative du paquet
            packet_size = len(str(packet))  # Approximation simple
            
            # Calculer les hops
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 5)
            hops_taken = hop_start - hop_limit
            
            # Enregistrer le paquet complet
            packet_entry = {
                'timestamp': timestamp,
                'from_id': from_id,
                'to_id': to_id,
                'sender_name': sender_name,
                'packet_type': packet_type,
                'message': message_text,
                'rssi': packet.get('rssi', 0),
                'snr': packet.get('snr', 0.0),
                'hops': hops_taken,
                'size': packet_size,
                'is_broadcast': to_id in [0xFFFFFFFF, 0]
            }
            
            self.all_packets.append(packet_entry)
            
            # Si c'est un message texte public, l'ajouter aussi à la file des messages
            if packet_type == 'TEXT_MESSAGE_APP' and message_text and packet_entry['is_broadcast']:
                self.public_messages.append({
                    'timestamp': timestamp,
                    'from_id': from_id,
                    'sender_name': sender_name,
                    'message': message_text,
                    'rssi': packet.get('rssi', 0),
                    'snr': packet.get('snr', 0.0),
                    'message_length': len(message_text)
                })
            
            # Mise à jour des statistiques
            self._update_packet_statistics(from_id, sender_name, packet_entry, packet)
            self._update_global_packet_statistics(packet_entry)
            self._update_network_statistics(packet_entry)
            
            debug_print(f"📦 Paquet {packet_type} de {sender_name}: total {self.node_packet_stats[from_id]['total_packets']}")
            
        except Exception as e:
            debug_print(f"Erreur enregistrement paquet: {e}")
    
    def add_public_message(self, packet, message_text):
        """
        Méthode de compatibilité pour les messages texte
        Redirige vers add_packet
        """
        self.add_packet(packet)
    
    def _extract_message_text(self, decoded):
        """Extraire le texte d'un message décodé"""
        message = ""
        
        if 'text' in decoded:
            message = decoded['text']
        elif 'payload' in decoded:
            payload = decoded['payload']
            if isinstance(payload, bytes):
                try:
                    message = payload.decode('utf-8')
                except UnicodeDecodeError:
                    message = payload.decode('utf-8', errors='replace')
            else:
                message = str(payload)
        
        return message
    
    def _update_packet_statistics(self, node_id, sender_name, packet_entry, original_packet):
        """Mettre à jour les statistiques détaillées par type de paquet"""
        stats = self.node_packet_stats[node_id]
        packet_type = packet_entry['packet_type']
        timestamp = packet_entry['timestamp']
        
        # Compteurs généraux
        stats['total_packets'] += 1
        stats['by_type'][packet_type] += 1
        stats['total_bytes'] += packet_entry['size']
        
        # Timestamps
        if stats['first_seen'] is None:
            stats['first_seen'] = timestamp
        stats['last_seen'] = timestamp
        
        # Activité horaire
        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        stats['hourly_activity'][hour] += 1
        
        # === STATISTIQUES SPÉCIFIQUES PAR TYPE ===
        
        # Messages texte
        if packet_type == 'TEXT_MESSAGE_APP' and packet_entry['message']:
            msg_stats = stats['message_stats']
            msg_stats['count'] += 1
            msg_stats['total_chars'] += len(packet_entry['message'])
            msg_stats['avg_length'] = msg_stats['total_chars'] / msg_stats['count']
        
        # Télémétrie
        elif packet_type == 'TELEMETRY_APP':
            tel_stats = stats['telemetry_stats']
            tel_stats['count'] += 1
            if 'decoded' in original_packet:
                decoded = original_packet['decoded']
                if 'telemetry' in decoded:
                    telemetry = decoded['telemetry']
                    if 'deviceMetrics' in telemetry:
                        metrics = telemetry['deviceMetrics']
                        tel_stats['last_battery'] = metrics.get('batteryLevel')
                        tel_stats['last_voltage'] = metrics.get('voltage')
                        tel_stats['last_channel_util'] = metrics.get('channelUtilization')
                        tel_stats['last_air_util'] = metrics.get('airUtilTx')
        
        # Position
        elif packet_type == 'POSITION_APP':
            pos_stats = stats['position_stats']
            pos_stats['count'] += 1
            if 'decoded' in original_packet:
                decoded = original_packet['decoded']
                if 'position' in decoded:
                    position = decoded['position']
                    pos_stats['last_lat'] = position.get('latitude')
                    pos_stats['last_lon'] = position.get('longitude')
                    pos_stats['last_alt'] = position.get('altitude')
        
        # Routage
        elif packet_type == 'ROUTING_APP':
            rout_stats = stats['routing_stats']
            rout_stats['count'] += 1
            # Analyser si c'est un paquet relayé ou originé
            if packet_entry['hops'] > 0:
                rout_stats['packets_relayed'] += 1
            else:
                rout_stats['packets_originated'] += 1
    
    def _update_global_packet_statistics(self, packet_entry):
        """Mettre à jour les statistiques globales"""
        self.global_packet_stats['total_packets'] += 1
        self.global_packet_stats['by_type'][packet_entry['packet_type']] += 1
        self.global_packet_stats['total_bytes'] += packet_entry['size']
        self.global_packet_stats['unique_nodes'].add(packet_entry['from_id'])
    
    def _update_network_statistics(self, packet_entry):
        """Mettre à jour les statistiques réseau"""
        # Hops
        self.network_stats['total_hops'] += packet_entry['hops']
        if packet_entry['hops'] > self.network_stats['max_hops_seen']:
            self.network_stats['max_hops_seen'] = packet_entry['hops']
        
        # Direct vs relayé
        if packet_entry['hops'] == 0:
            self.network_stats['packets_direct'] += 1
        else:
            self.network_stats['packets_relayed'] += 1
        
        # Moyennes signal (si disponible)
        if packet_entry['rssi'] != 0:
            # Moyenne mobile simple
            total_packets = self.global_packet_stats['total_packets']
            current_avg = self.network_stats['avg_rssi']
            self.network_stats['avg_rssi'] = (current_avg * (total_packets - 1) + packet_entry['rssi']) / total_packets
        
        if packet_entry['snr'] != 0:
            total_packets = self.global_packet_stats['total_packets']
            current_avg = self.network_stats['avg_snr']
            self.network_stats['avg_snr'] = (current_avg * (total_packets - 1) + packet_entry['snr']) / total_packets
    
    def get_top_talkers_report(self, hours=24, top_n=10, include_packet_types=True):
        """
        Générer un rapport des top talkers avec breakdown par type de paquet
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # Calculer les stats pour la période
            period_stats = defaultdict(lambda: {
                'total_packets': 0,
                'messages': 0,
                'telemetry': 0,
                'position': 0,
                'nodeinfo': 0,
                'routing': 0,
                'other': 0,
                'bytes': 0,
                'last_seen': 0,
                'name': ''
            })
                   # ✅ AJOUT : Compter par source
            local_count = 0
            tigrog2_count = 0
            
            for msg in self.public_messages:
                if msg['timestamp'] >= cutoff_time:
                    from_id = msg['from_id']
                    period_stats[from_id]['messages'] += 1
                    #period_stats[from_id]['chars'] += msg['message_length']
                    period_stats[from_id]['chars'] = period_stats[from_id].get('chars', 0) + msg['message_length']
                    period_stats[from_id]['last_seen'] = msg['timestamp']
                    period_stats[from_id]['name'] = msg['sender_name']
                    
                    # Compter par source
                    if msg.get('source') == 'tigrog2':
                        tigrog2_count += 1
                    else:
                        local_count += 1
            
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
        
            # ✅ AJOUT : Afficher les sources
            lines.append(f"Total: {total_messages} messages")
            lines.append(f"  📻 Local: {local_count}")
            lines.append(f"  📡 TigroG2: {tigrog2_count}")
            lines.append("")

            # Parcourir tous les paquets
            for packet in self.all_packets:
                if packet['timestamp'] >= cutoff_time:
                    from_id = packet['from_id']
                    stats = period_stats[from_id]
                    stats['total_packets'] += 1
                    stats['bytes'] += packet['size']
                    stats['last_seen'] = packet['timestamp']
                    stats['name'] = packet['sender_name']
                    
                    # Catégoriser par type
                    packet_type = packet['packet_type']
                    if packet_type == 'TEXT_MESSAGE_APP':
                        stats['messages'] += 1
                    elif packet_type == 'TELEMETRY_APP':
                        stats['telemetry'] += 1
                    elif packet_type == 'POSITION_APP':
                        stats['position'] += 1
                    elif packet_type == 'NODEINFO_APP':
                        stats['nodeinfo'] += 1
                    elif packet_type == 'ROUTING_APP':
                        stats['routing'] += 1
                    else:
                        stats['other'] += 1
            
            if not period_stats:
                return f"📊 Aucune activité dans les {hours}h"
            
            # Trier par nombre total de paquets
            sorted_nodes = sorted(
                period_stats.items(),
                key=lambda x: x[1]['total_packets'],
                reverse=True
            )[:top_n]
            
            # Construire le rapport
            lines = []
            lines.append(f"🏆 TOP TALKERS ({hours}h)")
            lines.append(f"{'='*40}")
            
            total_packets = sum(s['total_packets'] for _, s in period_stats.items())
            
            for rank, (node_id, stats) in enumerate(sorted_nodes, 1):
                name = truncate_text(stats['name'], 15)
                packet_count = stats['total_packets']
                percentage = (packet_count / total_packets * 100) if total_packets > 0 else 0
                
                # Icône selon le rang
                if rank == 1:
                    icon = "🥇"
                elif rank == 2:
                    icon = "🥈"
                elif rank == 3:
                    icon = "🥉"
                else:
                    icon = f"{rank}."
                
                # Barre de progression
                bar_length = int(percentage / 5)
                progress_bar = "█" * bar_length + "░" * (20 - bar_length)
                
                lines.append(f"\n{icon} {name}")
                lines.append(f"   {progress_bar}")
                lines.append(f"   📦 {packet_count} paquets ({percentage:.1f}%)")
                
                # Breakdown par type si demandé
                if include_packet_types:
                    breakdown = []
                    if stats['messages'] > 0:
                        breakdown.append(f"💬{stats['messages']}")
                    if stats['telemetry'] > 0:
                        breakdown.append(f"📊{stats['telemetry']}")
                    if stats['position'] > 0:
                        breakdown.append(f"📍{stats['position']}")
                    if stats['nodeinfo'] > 0:
                        breakdown.append(f"ℹ️{stats['nodeinfo']}")
                    if stats['routing'] > 0:
                        breakdown.append(f"🔀{stats['routing']}")
                    if stats['other'] > 0:
                        breakdown.append(f"❓{stats['other']}")
                    
                    if breakdown:
                        lines.append(f"   Types: {' '.join(breakdown)}")
                
                # Taille des données
                if stats['bytes'] > 1024:
                    lines.append(f"   📊 Data: {stats['bytes']/1024:.1f}KB")
                else:
                    lines.append(f"   📊 Data: {stats['bytes']}B")
                
                # Temps depuis dernier paquet
                time_str = format_elapsed_time(stats['last_seen'])
                lines.append(f"   ⏰ Dernier: {time_str}")
            
            # === STATISTIQUES GLOBALES ===
            lines.append(f"\n{'='*40}")
            lines.append(f"📊 STATISTIQUES GLOBALES")
            lines.append(f"{'='*40}")
            lines.append(f"Total paquets: {total_packets}")
            lines.append(f"Nœuds actifs: {len(period_stats)}")
            lines.append(f"Moy/nœud: {total_packets/len(period_stats):.1f}")
            
            # Distribution par type de paquet
            type_distribution = defaultdict(int)
            for packet in self.all_packets:
                if packet['timestamp'] >= cutoff_time:
                    type_distribution[packet['packet_type']] += 1
            
            if type_distribution:
                lines.append(f"\n📦 Distribution des types:")
                sorted_types = sorted(type_distribution.items(), key=lambda x: x[1], reverse=True)
                for ptype, count in sorted_types[:5]:
                    type_name = self.packet_type_names.get(ptype, ptype)
                    pct = (count / total_packets * 100)
                    lines.append(f"  {type_name}: {count} ({pct:.1f}%)")
            
            # Stats réseau
            lines.append(f"\n🌐 Statistiques réseau:")
            lines.append(f"  Direct: {self.network_stats['packets_direct']}")
            lines.append(f"  Relayé: {self.network_stats['packets_relayed']}")
            if self.network_stats['max_hops_seen'] > 0:
                lines.append(f"  Max hops: {self.network_stats['max_hops_seen']}")
            if self.network_stats['avg_rssi'] != 0:
                lines.append(f"  RSSI moy: {self.network_stats['avg_rssi']:.1f}dBm")
            if self.network_stats['avg_snr'] != 0:
                lines.append(f"  SNR moy: {self.network_stats['avg_snr']:.1f}dB")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur génération top talkers: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:50]}"
    
    def get_packet_type_summary(self, hours=1):
        """
        Obtenir un résumé des types de paquets sur une période
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            type_counts = defaultdict(int)
            total = 0
            
            for packet in self.all_packets:
                if packet['timestamp'] >= cutoff_time:
                    type_counts[packet['packet_type']] += 1
                    total += 1
            
            if not type_counts:
                return f"Aucun paquet dans les {hours}h"
            
            lines = [f"📦 Types de paquets ({hours}h):"]
            sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            
            for ptype, count in sorted_types:
                type_name = self.packet_type_names.get(ptype, ptype)
                percentage = (count / total * 100)
                lines.append(f"{type_name}: {count} ({percentage:.1f}%)")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Erreur: {str(e)[:30]}"
    
    def get_quick_stats(self):
        """
        Stats rapides pour Meshtastic (version courte)
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (3 * 3600)
            
            # Compter tous les paquets récents
            recent_packets = defaultdict(int)
            packet_types = defaultdict(int)
            
            for packet in self.all_packets:
                if packet['timestamp'] >= cutoff_time:
                    recent_packets[packet['sender_name']] += 1
                    packet_types[packet['packet_type']] += 1
            
            if not recent_packets:
                return "📊 Silence radio (3h)"
            
            total = sum(recent_packets.values())
            top_3 = sorted(recent_packets.items(), key=lambda x: x[1], reverse=True)[:3]
            
            lines = [f"🏆TOP 3h ({total} pqts):"]
            for i, (name, count) in enumerate(top_3, 1):
                name_short = truncate_text(name, 20)
                lines.append(f"{i}.{name_short}:{count}")
            
            # Type dominant
            if packet_types:
                dominant = max(packet_types.items(), key=lambda x: x[1])
                type_short = self.packet_type_names.get(dominant[0], dominant[0])[:10]
                lines.append(f"Type:{type_short}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return "❌ Erreur stats"
    
    def get_node_statistics(self, node_id):
        """Obtenir les statistiques détaillées d'un nœud"""
        if node_id in self.node_packet_stats:
            return self.node_packet_stats[node_id]
        return None
    
    def cleanup_old_messages(self):
        """Nettoyer les anciens paquets"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (self.traffic_retention_hours * 3600)
            
            # Nettoyer all_packets
            old_count = sum(1 for p in self.all_packets if p['timestamp'] < cutoff_time)
            if old_count > 0:
                debug_print(f"🧹 {old_count} paquets anciens expirés")

            # Nettoyer aussi l'historique des paquets
            try:
                old_packet_count = sum(1 for pkt in self.packet_history
                                      if pkt['timestamp'] < cutoff_time)
                if old_packet_count > 0:
                    debug_print(f"🧹 {old_packet_count} paquets anciens dans historique")
            except Exception as e:
                debug_print(f"Erreur nettoyage historique paquets: {e}")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage: {e}")
    
    def reset_statistics(self):
        """Réinitialiser toutes les statistiques"""
        self.node_packet_stats.clear()
        self.global_packet_stats = {
            'total_packets': 0,
            'by_type': defaultdict(int),
            'total_bytes': 0,
            'unique_nodes': set(),
            'busiest_hour': None,
            'quietest_hour': None,
            'last_reset': time.time()
        }
        self.network_stats = {
            'total_hops': 0,
            'max_hops_seen': 0,
            'avg_rssi': 0.0,
            'avg_snr': 0.0,
            'packets_direct': 0,
            'packets_relayed': 0
        }
        debug_print("📊 Statistiques réinitialisées")
    
    def export_statistics(self):
        """Exporter les statistiques en JSON"""
        try:
            export_data = {
                'timestamp': time.time(),
                'global_stats': {
                    'total_packets': self.global_packet_stats['total_packets'],
                    'by_type': dict(self.global_packet_stats['by_type']),
                    'total_bytes': self.global_packet_stats['total_bytes'],
                    'unique_nodes': len(self.global_packet_stats['unique_nodes'])
                },
                'network_stats': self.network_stats,
                'top_nodes': []
            }
            
            # Top 10 nodes
            sorted_nodes = sorted(
                self.node_packet_stats.items(),
                key=lambda x: x[1]['total_packets'],
                reverse=True
            )[:10]
            
            for node_id, stats in sorted_nodes:
                export_data['top_nodes'].append({
                    'node_id': node_id,
                    'name': self.node_manager.get_node_name(node_id),
                    'total_packets': stats['total_packets'],
                    'by_type': dict(stats['by_type'])
                })
            
            import json
            return json.dumps(export_data, indent=2)
            
        except Exception as e:
            error_print(f"Erreur export: {e}")
            return "{}"
    
    def get_message_count(self, hours=None):
        """Obtenir le nombre de messages dans la période"""
        if hours is None:
            hours = self.traffic_retention_hours

        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)

        return sum(1 for msg in self.public_messages if msg['timestamp'] >= cutoff_time)

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
        else:
            # ✅ FIX : Initialiser à None si pas de données
            self.global_stats['busiest_hour'] = None
            self.global_stats['quietest_hour'] = None
    def get_traffic_report(self, hours=8):
        """
        Afficher l'historique complet des messages publics (VERSION TELEGRAM)
        
        Args:
            hours: Période à afficher (défaut: 8h)
        
        Returns:
            str: Liste complète des messages publics formatée
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # Filtrer les messages de la période
            recent_messages = [
                msg for msg in self.public_messages
                if msg['timestamp'] >= cutoff_time
            ]
            
            if not recent_messages:
                return f"📭 Aucun message public dans les {hours}h"
            
            # Compter par source
            local_count = sum(1 for m in recent_messages if m.get('source') == 'local')
            tigrog2_count = sum(1 for m in recent_messages if m.get('source') == 'tigrog2')

            lines = []
            lines.append(f"📊 TRAFIC PUBLIC ({hours}h)")
            lines.append(f"{'='*30}")
            lines.append(f"Total: {len(recent_messages)} messages")
            lines.append(f"  📻 Local: {local_count}")
            lines.append(f"  📡 TigroG2: {tigrog2_count}")
            lines.append("")

            # Trier par timestamp (chronologique)
            recent_messages.sort(key=lambda x: x['timestamp'])
            
            # Construire le rapport complet
            lines = []
            lines.append(f"📨 **MESSAGES PUBLICS ({hours}h)**")
            lines.append(f"{'='*40}")
            lines.append(f"Total: {len(recent_messages)} messages")
            lines.append("")
            
            # Afficher tous les messages (Telegram peut gérer de longs messages)
            for msg in recent_messages:
                # Formater le timestamp
                msg_time = datetime.fromtimestamp(msg['timestamp'])
                time_str = msg_time.strftime("%H:%M:%S")
                
                # Nom de l'expéditeur
                sender = msg['sender_name']
                
                # Message complet
                content = msg['message']
                
                # Format: [HH:MM:SS] Sender:
                #           message
                lines.append(f"[{time_str}] **{sender}:**")
                lines.append(f"  {content}")
                lines.append("")
            
            result = "\n".join(lines)
            
            # Si vraiment trop long pour Telegram (>4000 chars), limiter
            if len(result) > 3800:
                lines = []
                lines.append(f"📨 **DERNIERS 20 MESSAGES ({hours}h)**")
                lines.append(f"{'='*40}")
                lines.append(f"(Total: {len(recent_messages)} messages - affichage limité)")
                lines.append("")
                
                # Prendre les 20 plus récents
                for msg in recent_messages[-20:]:
                    msg_time = datetime.fromtimestamp(msg['timestamp'])
                    time_str = msg_time.strftime("%H:%M:%S")
                    sender = msg['sender_name']
                    content = msg['message']
                    
                    lines.append(f"[{time_str}] **{sender}:**")
                    lines.append(f"  {content}")
                    lines.append("")
                
                result = "\n".join(lines)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur génération historique complet: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:50]}"

    def get_traffic_report_compact(self, hours=8):
        """
        Afficher l'historique compact des messages publics (VERSION MESHTASTIC)
        
        Args:
            hours: Période à afficher (défaut: 8h)
        
        Returns:
            str: Liste compacte des messages publics (max ~180 chars)
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # Filtrer les messages de la période
            recent_messages = [
                msg for msg in self.public_messages
                if msg['timestamp'] >= cutoff_time
            ]
            
            if not recent_messages:
                return f"📭 Silence ({hours}h)"
            
            # Trier par timestamp (chronologique)
            recent_messages.sort(key=lambda x: x['timestamp'])
            
            # Limiter à 5 derniers messages pour tenir dans 200 chars
            lines = [f"📨 {len(recent_messages)}msg ({hours}h):"]
            
            for msg in recent_messages[-15:]:
                msg_time = datetime.fromtimestamp(msg['timestamp'])
                time_str = msg_time.strftime("%H:%M")
                sender = truncate_text(msg['sender_name'], 8)
                content = truncate_text(msg['message'], 25)
                
                lines.append(f"{time_str} {sender}: {content}")
            
            if len(recent_messages) > 5:
                lines.append(f"(+{len(recent_messages)-5} plus)")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur génération historique compact: {e}")
            return f"Erreur: {str(e)[:30]}"

    # ============================================================
    # AJOUT 2: Nouvelle méthode add_packet_to_history
    # ============================================================

    def add_packet_to_history(self, packet):
        """
        Enregistrer un paquet dans l'historique pour l'histogramme
        Appelé pour TOUS les paquets reçus
        """
        try:
            from_id = packet.get('from', 0)
            timestamp = time.time()
            
            # Déterminer le type de paquet
            packet_type = 'unknown'
            if 'decoded' in packet:
                portnum = packet['decoded'].get('portnum', '')
                packet_type = self.packet_types.get(portnum, portnum)
            
            # Obtenir le nom du nœud
            sender_name = self.node_manager.get_node_name(from_id)
            
            # Enregistrer le paquet
            packet_entry = {
                'timestamp': timestamp,
                'from_id': from_id,
                'sender_name': sender_name,
                'type': packet_type,
                'rssi': packet.get('rssi', 0),
                'snr': packet.get('snr', 0.0)
            }
            
            self.packet_history.append(packet_entry)
            
            debug_print(f"📊 Paquet enregistré: {packet_type} de {sender_name}")
            
        except Exception as e:
            debug_print(f"Erreur enregistrement paquet: {e}")

    def get_hourly_histogram(self, packet_filter='all', hours=24):
        """
        Générer un histogramme de distribution horaire des paquets
        
        Args:
            packet_filter: 'all', 'messages', 'pos', 'info', 'telemetry', etc.
            hours: Nombre d'heures à analyser (défaut: 24)
        
        Returns:
            str: Histogramme ASCII formaté
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)
            
            # Filtrer les paquets par période et type
            filtered_packets = []
            for pkt in self.packet_history:
                if pkt['timestamp'] >= cutoff_time:
                    if packet_filter == 'all' or pkt['type'] == packet_filter:
                        filtered_packets.append(pkt)
            
            if not filtered_packets:
                return f"📊 Aucun paquet '{packet_filter}' dans les {hours}h"
            
            # Compter les paquets par heure
            hourly_counts = defaultdict(int)
            for pkt in filtered_packets:
                dt = datetime.fromtimestamp(pkt['timestamp'])
                hour = dt.hour
                hourly_counts[hour] += 1
            
            # Statistiques
            total_packets = len(filtered_packets)
            unique_nodes = len(set(pkt['from_id'] for pkt in filtered_packets))
            
            # Construire le graphique
            lines = []
            
            # Header avec stats
            filter_label = {
                'all': 'TOUS TYPES',
                'messages': 'MESSAGES TEXTE',
                'pos': 'POSITIONS',
                'info': 'NODEINFO',
                'telemetry': 'TÉLÉMÉTRIE',
                'traceroute': 'TRACEROUTE',
                'routing': 'ROUTING'
            }.get(packet_filter, packet_filter.upper())
            
            lines.append(f"📊 HISTOGRAMME {filter_label} ({hours}h)")
            lines.append("=" * 40)
            lines.append(f"Total: {total_packets} paquets | {unique_nodes} nœuds")
            lines.append("")
            
            # Trouver le max pour l'échelle
            max_count = max(hourly_counts.values()) if hourly_counts else 1
            
            # Graphique par heure (0-23)
            for hour in range(24):
                count = hourly_counts.get(hour, 0)
                
                # Barre de progression (max 20 caractères)
                bar_length = int((count / max_count * 20)) if max_count > 0 else 0
                bar = "█" * bar_length + "░" * (20 - bar_length)
                
                # Pourcentage
                percentage = (count / total_packets * 100) if total_packets > 0 else 0
                
                lines.append(f"{hour:02d}h {bar} {count:4d} ({percentage:4.1f}%)")
            
            lines.append("")
            lines.append("=" * 40)
            
            # Heure de pointe
            if hourly_counts:
                peak_hour = max(hourly_counts.items(), key=lambda x: x[1])
                lines.append(f"🏆 Pointe: {peak_hour[0]:02d}h00 ({peak_hour[1]} paquets)")
            
            # Moyenne par heure
            avg_per_hour = total_packets / hours if hours > 0 else 0
            lines.append(f"📊 Moyenne: {avg_per_hour:.1f} paquets/heure")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur génération histogramme: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:50]}"
            
    def add_public_message(self, packet, message_text, source='local'):
        """
        Enregistrer un message public avec collecte de statistiques avancées
        
        Args:
            packet: Packet Meshtastic
            message_text: Texte du message
            source: 'local' (série) ou 'tigrog2' (TCP)
        """
        try:
            from_id = packet.get('from', 0)
            timestamp = time.time()
            
            # Obtenir le nom du nœud
            sender_name = self.node_manager.get_node_name(from_id)
            
            # Enregistrer le message avec source
            message_entry = {
                'timestamp': timestamp,
                'from_id': from_id,
                'sender_name': sender_name,
                'message': message_text,
                'rssi': packet.get('rssi', 0),
                'snr': packet.get('snr', 0.0),
                'message_length': len(message_text),
                'source': source  # ← AJOUT
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
            
            # Log avec icône source
            source_icon = "📡" if source == 'tigrog2' else "📻"
            debug_print(f"{source_icon} Stats mises à jour pour {sender_name}: {self.node_stats[from_id]['total_messages']} msgs")
            
        except Exception as e:
            debug_print(f"Erreur enregistrement message public: {e}")
            import traceback
            debug_print(traceback.format_exc())

    def _is_duplicate(self, new_message):
        """Vérifier si le message est un doublon récent"""
        if not self.public_messages:
            return False
        
        # Vérifier les 10 derniers messages
        recent = list(self.public_messages)[-10:]
        
        for msg in reversed(recent):
            # Même expéditeur, même texte, < 5 secondes d'écart
            if (msg['from_id'] == new_message['from_id'] and
                msg['message'] == new_message['message'] and
                abs(msg['timestamp'] - new_message['timestamp']) < 5):
                return True
        
        return False        

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
