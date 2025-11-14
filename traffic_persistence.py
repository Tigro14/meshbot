"""
Module de persistance SQLite pour l'historique du trafic Meshtastic.
Permet de conserver les données de trafic entre les redémarrages du bot.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import os

logger = logging.getLogger(__name__)


class TrafficPersistence:
    """Gère la persistance des données de trafic dans SQLite."""

    def __init__(self, db_path: str = "traffic_history.db"):
        """
        Initialise la connexion à la base de données.

        Args:
            db_path: Chemin vers le fichier de base de données SQLite
        """
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        """Initialise la base de données et crée les tables si nécessaire."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            cursor = self.conn.cursor()

            # Table pour tous les paquets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS packets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    from_id TEXT NOT NULL,
                    to_id TEXT,
                    source TEXT,
                    sender_name TEXT,
                    packet_type TEXT NOT NULL,
                    message TEXT,
                    rssi INTEGER,
                    snr REAL,
                    hops INTEGER,
                    size INTEGER,
                    is_broadcast INTEGER,
                    telemetry TEXT,
                    position TEXT
                )
            ''')

            # Index pour optimiser les requêtes sur les paquets
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_packets_timestamp
                ON packets(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_packets_from_id
                ON packets(from_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_packets_type
                ON packets(packet_type)
            ''')

            # Table pour les messages publics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS public_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    from_id TEXT NOT NULL,
                    sender_name TEXT,
                    message TEXT,
                    rssi INTEGER,
                    snr REAL,
                    message_length INTEGER,
                    source TEXT
                )
            ''')

            # Index pour optimiser les requêtes sur les messages
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON public_messages(timestamp)
            ''')

            # Table pour les statistiques par nœud
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS node_stats (
                    node_id TEXT PRIMARY KEY,
                    total_packets INTEGER,
                    total_bytes INTEGER,
                    packet_types TEXT,
                    hourly_activity TEXT,
                    message_stats TEXT,
                    telemetry_stats TEXT,
                    position_stats TEXT,
                    routing_stats TEXT,
                    last_updated REAL
                )
            ''')

            # Table pour les statistiques globales
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS global_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_packets INTEGER,
                    total_bytes INTEGER,
                    packet_types TEXT,
                    unique_nodes TEXT,
                    last_reset REAL
                )
            ''')

            # Table pour les statistiques réseau
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS network_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_hops INTEGER,
                    max_hops_seen INTEGER,
                    avg_rssi REAL,
                    avg_snr REAL,
                    packets_direct INTEGER,
                    packets_relayed INTEGER
                )
            ''')

            self.conn.commit()
            logger.info(f"Base de données initialisée : {self.db_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données : {e}")
            raise

    def save_packet(self, packet: Dict[str, Any]):
        """
        Sauvegarde un paquet dans la base de données.

        Args:
            packet: Dictionnaire contenant les informations du paquet
        """
        try:
            cursor = self.conn.cursor()

            # Convertir les structures complexes en JSON
            telemetry = json.dumps(packet.get('telemetry')) if packet.get('telemetry') else None
            position = json.dumps(packet.get('position')) if packet.get('position') else None

            cursor.execute('''
                INSERT INTO packets (
                    timestamp, from_id, to_id, source, sender_name, packet_type,
                    message, rssi, snr, hops, size, is_broadcast, telemetry, position
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                packet.get('timestamp'),
                packet.get('from_id'),
                packet.get('to_id'),
                packet.get('source'),
                packet.get('sender_name'),
                packet.get('packet_type'),
                packet.get('message'),
                packet.get('rssi'),
                packet.get('snr'),
                packet.get('hops'),
                packet.get('size'),
                1 if packet.get('is_broadcast') else 0,
                telemetry,
                position
            ))

            self.conn.commit()

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du paquet : {e}")

    def save_public_message(self, message_data: Dict[str, Any]):
        """
        Sauvegarde un message public dans la base de données.

        Args:
            message_data: Dictionnaire contenant les informations du message
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute('''
                INSERT INTO public_messages (
                    timestamp, from_id, sender_name, message, rssi, snr,
                    message_length, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                message_data.get('timestamp'),
                message_data.get('from_id'),
                message_data.get('sender_name'),
                message_data.get('message'),
                message_data.get('rssi'),
                message_data.get('snr'),
                message_data.get('message_length'),
                message_data.get('source')
            ))

            self.conn.commit()

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du message public : {e}")

    def save_node_stats(self, node_stats: Dict[str, Dict]):
        """
        Sauvegarde les statistiques par nœud.

        Args:
            node_stats: Dictionnaire des statistiques par nœud
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.now().timestamp()

            for node_id, stats in node_stats.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO node_stats (
                        node_id, total_packets, total_bytes, packet_types,
                        hourly_activity, message_stats, telemetry_stats,
                        position_stats, routing_stats, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    node_id,
                    stats.get('total_packets', 0),
                    stats.get('total_bytes', 0),
                    json.dumps(dict(stats.get('by_type', {}))),
                    json.dumps(stats.get('hourly_activity', {})),
                    json.dumps(stats.get('message_stats', {})),
                    json.dumps(stats.get('telemetry_stats', {})),
                    json.dumps(stats.get('position_stats', {})),
                    json.dumps(stats.get('routing_stats', {})),
                    timestamp
                ))

            self.conn.commit()

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des statistiques par nœud : {e}")

    def save_global_stats(self, global_stats: Dict):
        """
        Sauvegarde les statistiques globales.

        Args:
            global_stats: Dictionnaire des statistiques globales
        """
        try:
            cursor = self.conn.cursor()

            # Convertir le set en liste pour JSON
            unique_nodes = list(global_stats.get('unique_nodes', set()))

            cursor.execute('''
                INSERT OR REPLACE INTO global_stats (
                    id, total_packets, total_bytes, packet_types,
                    unique_nodes, last_reset
                ) VALUES (1, ?, ?, ?, ?, ?)
            ''', (
                global_stats.get('total_packets', 0),
                global_stats.get('total_bytes', 0),
                json.dumps(dict(global_stats.get('by_type', {}))),
                json.dumps(unique_nodes),
                global_stats.get('last_reset', datetime.now().timestamp())
            ))

            self.conn.commit()

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des statistiques globales : {e}")

    def save_network_stats(self, network_stats: Dict):
        """
        Sauvegarde les statistiques réseau.

        Args:
            network_stats: Dictionnaire des statistiques réseau
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO network_stats (
                    id, total_hops, max_hops_seen, avg_rssi, avg_snr,
                    packets_direct, packets_relayed
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
            ''', (
                network_stats.get('total_hops', 0),
                network_stats.get('max_hops_seen', 0),
                network_stats.get('avg_rssi', 0.0),
                network_stats.get('avg_snr', 0.0),
                network_stats.get('packets_direct', 0),
                network_stats.get('packets_relayed', 0)
            ))

            self.conn.commit()

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des statistiques réseau : {e}")

    def load_packets(self, hours: int = 24, limit: int = 5000) -> List[Dict]:
        """
        Charge les paquets depuis la base de données.

        Args:
            hours: Nombre d'heures à charger
            limit: Nombre maximum de paquets à charger

        Returns:
            Liste des paquets
        """
        try:
            cursor = self.conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=hours)).timestamp()

            cursor.execute('''
                SELECT * FROM packets
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (cutoff, limit))

            packets = []
            for row in cursor.fetchall():
                packet = dict(row)

                # Reconvertir les JSON en objets
                if packet.get('telemetry'):
                    packet['telemetry'] = json.loads(packet['telemetry'])
                if packet.get('position'):
                    packet['position'] = json.loads(packet['position'])

                packet['is_broadcast'] = bool(packet.get('is_broadcast'))

                packets.append(packet)

            return packets

        except Exception as e:
            logger.error(f"Erreur lors du chargement des paquets : {e}")
            return []

    def load_public_messages(self, hours: int = 24, limit: int = 2000) -> List[Dict]:
        """
        Charge les messages publics depuis la base de données.

        Args:
            hours: Nombre d'heures à charger
            limit: Nombre maximum de messages à charger

        Returns:
            Liste des messages
        """
        try:
            cursor = self.conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=hours)).timestamp()

            cursor.execute('''
                SELECT * FROM public_messages
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (cutoff, limit))

            messages = [dict(row) for row in cursor.fetchall()]
            return messages

        except Exception as e:
            logger.error(f"Erreur lors du chargement des messages publics : {e}")
            return []

    def load_node_stats(self) -> Dict[str, Dict]:
        """
        Charge les statistiques par nœud.

        Returns:
            Dictionnaire des statistiques par nœud
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM node_stats')

            node_stats = {}
            for row in cursor.fetchall():
                node_id = row['node_id']
                node_stats[node_id] = {
                    'total_packets': row['total_packets'],
                    'total_bytes': row['total_bytes'],
                    'by_type': defaultdict(int, json.loads(row['packet_types']) if row['packet_types'] else {}),
                    'hourly_activity': defaultdict(int, json.loads(row['hourly_activity']) if row['hourly_activity'] else {}),
                    'message_stats': json.loads(row['message_stats']) if row['message_stats'] else {},
                    'telemetry_stats': json.loads(row['telemetry_stats']) if row['telemetry_stats'] else {},
                    'position_stats': json.loads(row['position_stats']) if row['position_stats'] else {},
                    'routing_stats': json.loads(row['routing_stats']) if row['routing_stats'] else {}
                }

            return node_stats

        except Exception as e:
            logger.error(f"Erreur lors du chargement des statistiques par nœud : {e}")
            return {}

    def load_global_stats(self) -> Optional[Dict]:
        """
        Charge les statistiques globales.

        Returns:
            Dictionnaire des statistiques globales ou None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM global_stats WHERE id = 1')
            row = cursor.fetchone()

            if row:
                unique_nodes = set(json.loads(row['unique_nodes']) if row['unique_nodes'] else [])

                return {
                    'total_packets': row['total_packets'],
                    'total_bytes': row['total_bytes'],
                    'by_type': defaultdict(int, json.loads(row['packet_types']) if row['packet_types'] else {}),
                    'unique_nodes': unique_nodes,
                    'last_reset': row['last_reset']
                }

            return None

        except Exception as e:
            logger.error(f"Erreur lors du chargement des statistiques globales : {e}")
            return None

    def load_network_stats(self) -> Optional[Dict]:
        """
        Charge les statistiques réseau.

        Returns:
            Dictionnaire des statistiques réseau ou None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM network_stats WHERE id = 1')
            row = cursor.fetchone()

            if row:
                return {
                    'total_hops': row['total_hops'],
                    'max_hops_seen': row['max_hops_seen'],
                    'avg_rssi': row['avg_rssi'],
                    'avg_snr': row['avg_snr'],
                    'packets_direct': row['packets_direct'],
                    'packets_relayed': row['packets_relayed']
                }

            return None

        except Exception as e:
            logger.error(f"Erreur lors du chargement des statistiques réseau : {e}")
            return None

    def cleanup_old_data(self, hours: int = 48):
        """
        Supprime les données plus anciennes que le nombre d'heures spécifié.

        Args:
            hours: Nombre d'heures à conserver
        """
        try:
            cursor = self.conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=hours)).timestamp()

            cursor.execute('DELETE FROM packets WHERE timestamp < ?', (cutoff,))
            cursor.execute('DELETE FROM public_messages WHERE timestamp < ?', (cutoff,))

            deleted_packets = cursor.rowcount
            self.conn.commit()

            logger.info(f"Nettoyage : {deleted_packets} paquets supprimés (> {hours}h)")

            # Optimiser la base de données après le nettoyage
            cursor.execute('VACUUM')

        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des anciennes données : {e}")

    def clear_all_data(self):
        """Efface toutes les données de trafic de la base de données."""
        try:
            cursor = self.conn.cursor()

            cursor.execute('DELETE FROM packets')
            cursor.execute('DELETE FROM public_messages')
            cursor.execute('DELETE FROM node_stats')
            cursor.execute('DELETE FROM global_stats')
            cursor.execute('DELETE FROM network_stats')

            self.conn.commit()

            # Optimiser la base de données
            cursor.execute('VACUUM')

            logger.info("Toutes les données de trafic ont été effacées")

        except Exception as e:
            logger.error(f"Erreur lors de l'effacement des données : {e}")
            raise

    def get_stats_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé des statistiques de la base de données.

        Returns:
            Dictionnaire avec les statistiques de la base
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute('SELECT COUNT(*) as count FROM packets')
            total_packets = cursor.fetchone()['count']

            cursor.execute('SELECT COUNT(*) as count FROM public_messages')
            total_messages = cursor.fetchone()['count']

            cursor.execute('SELECT COUNT(*) as count FROM node_stats')
            total_nodes = cursor.fetchone()['count']

            cursor.execute('SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM packets')
            row = cursor.fetchone()
            oldest = row['oldest']
            newest = row['newest']

            # Taille du fichier de base de données
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            db_size_mb = db_size / (1024 * 1024)

            return {
                'total_packets': total_packets,
                'total_messages': total_messages,
                'total_nodes': total_nodes,
                'oldest_packet': datetime.fromtimestamp(oldest).isoformat() if oldest else None,
                'newest_packet': datetime.fromtimestamp(newest).isoformat() if newest else None,
                'database_size_mb': round(db_size_mb, 2)
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques : {e}")
            return {}

    def close(self):
        """Ferme la connexion à la base de données."""
        if self.conn:
            self.conn.close()
            logger.info("Connexion à la base de données fermée")

    def __del__(self):
        """Destructeur pour s'assurer que la connexion est fermée."""
        self.close()
