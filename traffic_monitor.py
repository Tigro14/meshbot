#!/usr/bin/env python3
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
            import traceback
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
                name_short = truncate_text(name, 8)
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

    def get_traffic_report(self, hours=None):
        """ 
        Générer un rapport du trafic public des dernières heures
                
        Args:   
            hours: Nombre d'heures à inclure (défaut: 8)
            
        Returns:
            str: Rapport formaté du trafic
        """ 
        if hours is None:
            hours = 8  # ✅ Défaut à 8h pour compatibilité

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

            # ✅ CORRECTION: Adapter la limite selon la période demandée
            # Plus la période est longue, plus on peut afficher de messages
            if hours <= 2:
                max_display = 50
            elif hours <= 8:
                max_display = 100
            elif hours <= 12:
                max_display = 150 
            else:  # 24h
                max_display = 200

            # Construire le rapport
            lines = []
            lines.append(f"📡 Trafic public ({len(recent_messages)} msgs - {hours}h):")
            lines.append("")

            # ✅ Prendre les messages les plus récents selon la limite
            display_messages = recent_messages[-max_display:]

            # ✅ OPTIMISATION: Grouper par heure pour les longues périodes
            if hours > 12 and len(display_messages) > 100:
                lines.extend(self._format_grouped_messages(display_messages))
            else:
                # Format détaillé pour les courtes périodes
                for msg in display_messages:
                    line = self._format_message_line(msg)
                    lines.append(line)

            # Ajouter footer si messages tronqués
            if len(recent_messages) > max_display:
                lines.append("")
                lines.append(f"... et {len(recent_messages) - max_display} messages plus anciens")

            # Statistiques rapides
            lines.append("")
            lines.append(self._get_traffic_stats(recent_messages, hours))

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur génération rapport trafic: {e}")
            return f"Erreur génération rapport: {str(e)[:50]}"
    
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
