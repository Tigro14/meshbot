"""
Module de persistance SQLite pour l'historique du trafic Meshtastic.
Permet de conserver les données de trafic entre les redémarrages du bot.
"""

import sqlite3
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict, deque
import os
from utils import debug_print, info_print, error_print

logger = logging.getLogger(__name__)


class TrafficPersistence:
    """Gère la persistance des données de trafic dans SQLite."""

    def __init__(self, db_path: str = "traffic_history.db", error_callback: Optional[Callable[[Exception, str], None]] = None):
        """
        Initialise la connexion à la base de données.

        Args:
            db_path: Chemin vers le fichier de base de données SQLite
            error_callback: Fonction à appeler en cas d'erreur d'écriture (optionnel)
                           Signature: error_callback(error: Exception, operation: str)
        """
        self.db_path = db_path
        self.conn = None
        self.error_callback = error_callback
        self._init_database()

    def _init_database(self):
        """Initialise la base de données et crée les tables si nécessaire."""
        try:
            # Vérifier si le fichier DB existe et est vide (corrompu)
            if os.path.exists(self.db_path):
                file_size = os.path.getsize(self.db_path)
                if file_size == 0:
                    logger.warning(f"⚠️ Base de données vide/corrompue détectée ({self.db_path}), suppression...")
                    os.remove(self.db_path)

            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            # Vérifier l'intégrité de la base de données
            cursor = self.conn.cursor()
            try:
                cursor.execute("PRAGMA integrity_check")
                integrity = cursor.fetchone()[0]
                if integrity != 'ok':
                    logger.error(f"❌ Intégrité DB compromise : {integrity}")
                    # Tentative de réparation ou recréation
                    self.conn.close()
                    logger.info("Recréation de la base de données...")
                    os.remove(self.db_path)
                    self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    self.conn.row_factory = sqlite3.Row
                    cursor = self.conn.cursor()
                else:
                    logger.info("✅ Intégrité de la DB vérifiée")
            except Exception as e:
                logger.warning(f"Impossible de vérifier l'intégrité : {e}")

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
                    is_encrypted INTEGER DEFAULT 0,
                    telemetry TEXT,
                    position TEXT,
                    hop_limit INTEGER,
                    hop_start INTEGER
                )
            ''')

            # Migration : ajouter is_encrypted si elle n'existe pas
            try:
                cursor.execute("SELECT is_encrypted FROM packets LIMIT 1")
            except sqlite3.OperationalError:
                # La colonne n'existe pas, l'ajouter
                logger.info("Migration DB : ajout de la colonne is_encrypted")
                cursor.execute("ALTER TABLE packets ADD COLUMN is_encrypted INTEGER DEFAULT 0")
            
            # Migration : ajouter hop_limit si elle n'existe pas
            try:
                cursor.execute("SELECT hop_limit FROM packets LIMIT 1")
            except sqlite3.OperationalError:
                # La colonne n'existe pas, l'ajouter
                logger.info("Migration DB : ajout de la colonne hop_limit")
                cursor.execute("ALTER TABLE packets ADD COLUMN hop_limit INTEGER")
            
            # Migration : ajouter hop_start si elle n'existe pas
            try:
                cursor.execute("SELECT hop_start FROM packets LIMIT 1")
            except sqlite3.OperationalError:
                # La colonne n'existe pas, l'ajouter
                logger.info("Migration DB : ajout de la colonne hop_start")
                cursor.execute("ALTER TABLE packets ADD COLUMN hop_start INTEGER")

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
                    last_updated REAL,
                    last_battery_level INTEGER,
                    last_battery_voltage REAL,
                    last_telemetry_update REAL,
                    last_temperature REAL,
                    last_humidity REAL,
                    last_pressure REAL,
                    last_air_quality REAL
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

            # Table pour le cache météo (centralise tous les caches weather/rain/astro)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weather_cache (
                    location TEXT NOT NULL,
                    cache_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (location, cache_type)
                )
            ''')

            # Index pour nettoyage périodique du cache expiré
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_weather_cache_timestamp
                ON weather_cache(timestamp)
            ''')

            # Table pour les informations de voisinage (neighbor info)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS neighbors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    node_id TEXT NOT NULL,
                    neighbor_id TEXT NOT NULL,
                    snr REAL,
                    last_rx_time INTEGER,
                    node_broadcast_interval INTEGER,
                    source TEXT DEFAULT 'radio'
                )
            ''')
            
            # Migration : ajouter source si elle n'existe pas
            try:
                cursor.execute("SELECT source FROM neighbors LIMIT 1")
            except sqlite3.OperationalError:
                # La colonne n'existe pas, l'ajouter
                logger.info("Migration DB : ajout de la colonne source aux neighbors")
                cursor.execute("ALTER TABLE neighbors ADD COLUMN source TEXT DEFAULT 'radio'")

            # Index pour optimiser les requêtes sur les voisins
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_neighbors_timestamp
                ON neighbors(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_neighbors_node_id
                ON neighbors(node_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_neighbors_composite
                ON neighbors(node_id, neighbor_id, timestamp)
            ''')

            # Migration : ajouter les colonnes de télémétrie à node_stats si elles n'existent pas
            try:
                cursor.execute("SELECT last_battery_level FROM node_stats LIMIT 1")
            except sqlite3.OperationalError:
                # Les colonnes n'existent pas, les ajouter
                logger.info("Migration DB : ajout des colonnes de télémétrie à node_stats")
                cursor.execute("ALTER TABLE node_stats ADD COLUMN last_battery_level INTEGER")
                cursor.execute("ALTER TABLE node_stats ADD COLUMN last_battery_voltage REAL")
                cursor.execute("ALTER TABLE node_stats ADD COLUMN last_telemetry_update REAL")
            
            # Migration : ajouter les colonnes d'environnement à node_stats si elles n'existent pas
            try:
                cursor.execute("SELECT last_temperature FROM node_stats LIMIT 1")
            except sqlite3.OperationalError:
                # Les colonnes n'existent pas, les ajouter
                logger.info("Migration DB : ajout des colonnes d'environnement à node_stats")
                cursor.execute("ALTER TABLE node_stats ADD COLUMN last_temperature REAL")
                cursor.execute("ALTER TABLE node_stats ADD COLUMN last_humidity REAL")
                cursor.execute("ALTER TABLE node_stats ADD COLUMN last_pressure REAL")
                cursor.execute("ALTER TABLE node_stats ADD COLUMN last_air_quality REAL")

            self.conn.commit()
            logger.info(f"✅ Base de données initialisée : {self.db_path}")

            # Vérifier que les tables sont bien créées
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Tables créées : {', '.join(tables)}")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation de la base de données : {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def save_packet(self, packet: Dict[str, Any]):
        """
        Sauvegarde un paquet dans la base de données.

        Args:
            packet: Dictionnaire contenant les informations du paquet
        """
        try:
            # Vérifier que la connexion est active
            if self.conn is None:
                logger.error("Connexion SQLite non initialisée, tentative de reconnexion")
                self._init_database()
                if self.conn is None:
                    logger.error("Impossible d'initialiser la connexion SQLite")
                    return

            cursor = self.conn.cursor()

            # Convertir les structures complexes en JSON
            telemetry = json.dumps(packet.get('telemetry')) if packet.get('telemetry') else None
            position = json.dumps(packet.get('position')) if packet.get('position') else None

            cursor.execute('''
                INSERT INTO packets (
                    timestamp, from_id, to_id, source, sender_name, packet_type,
                    message, rssi, snr, hops, size, is_broadcast, is_encrypted, telemetry, position,
                    hop_limit, hop_start
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                1 if packet.get('is_encrypted') else 0,
                telemetry,
                position,
                packet.get('hop_limit'),
                packet.get('hop_start')
            ))

            self.conn.commit()

            # Log périodique pour suivre l'activité (tous les 50 paquets)
            if not hasattr(self, '_packet_count'):
                self._packet_count = 0
            self._packet_count += 1
            if self._packet_count % 50 == 0:
                logger.info(f"📦 {self._packet_count} paquets sauvegardés dans SQLite")

        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde du paquet : {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Notifier le callback d'erreur si configuré
            if self.error_callback:
                try:
                    self.error_callback(e, 'save_packet')
                except Exception as cb_error:
                    logger.error(f"Erreur dans error_callback: {cb_error}")

    def save_public_message(self, message_data: Dict[str, Any]):
        """
        Sauvegarde un message public dans la base de données.

        Args:
            message_data: Dictionnaire contenant les informations du message
        """
        try:
            # Vérifier que la connexion est active
            if self.conn is None:
                logger.error("Connexion SQLite non initialisée pour save_public_message")
                self._init_database()
                if self.conn is None:
                    return

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
            
            # Notifier le callback d'erreur si configuré
            if self.error_callback:
                try:
                    self.error_callback(e, 'save_public_message')
                except Exception as cb_error:
                    logger.error(f"Erreur dans error_callback: {cb_error}")

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
                # Extract telemetry stats for last battery data
                telemetry_stats = stats.get('telemetry_stats', {})
                last_battery = telemetry_stats.get('last_battery')
                last_voltage = telemetry_stats.get('last_voltage')
                last_temperature = telemetry_stats.get('last_temperature')
                last_humidity = telemetry_stats.get('last_humidity')
                last_pressure = telemetry_stats.get('last_pressure')
                last_air_quality = telemetry_stats.get('last_air_quality')
                
                # Determine telemetry update timestamp
                # Use current timestamp if we have fresh telemetry data, otherwise None
                has_telemetry = (last_battery is not None or last_voltage is not None or 
                                last_temperature is not None or last_humidity is not None or
                                last_pressure is not None or last_air_quality is not None)
                last_telemetry_update = timestamp if has_telemetry else None
                
                cursor.execute('''
                    INSERT OR REPLACE INTO node_stats (
                        node_id, total_packets, total_bytes, packet_types,
                        hourly_activity, message_stats, telemetry_stats,
                        position_stats, routing_stats, last_updated,
                        last_battery_level, last_battery_voltage, last_telemetry_update,
                        last_temperature, last_humidity, last_pressure, last_air_quality
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    node_id,
                    stats.get('total_packets', 0),
                    stats.get('total_bytes', 0),
                    json.dumps(dict(stats.get('by_type', {}))),
                    json.dumps(stats.get('hourly_activity', {})),
                    json.dumps(stats.get('message_stats', {})),
                    json.dumps(telemetry_stats),
                    json.dumps(stats.get('position_stats', {})),
                    json.dumps(stats.get('routing_stats', {})),
                    timestamp,
                    last_battery,
                    last_voltage,
                    last_telemetry_update,
                    last_temperature,
                    last_humidity,
                    last_pressure,
                    last_air_quality
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
                
                # Load telemetry stats from JSON
                telemetry_stats = json.loads(row['telemetry_stats']) if row['telemetry_stats'] else {}
                
                # Add battery data from dedicated columns (takes precedence over JSON)
                if 'last_battery_level' in row.keys() and row['last_battery_level'] is not None:
                    telemetry_stats['last_battery'] = row['last_battery_level']
                if 'last_battery_voltage' in row.keys() and row['last_battery_voltage'] is not None:
                    telemetry_stats['last_voltage'] = row['last_battery_voltage']
                if 'last_telemetry_update' in row.keys() and row['last_telemetry_update'] is not None:
                    telemetry_stats['last_telemetry_update'] = row['last_telemetry_update']
                
                # Add environment data from dedicated columns
                if 'last_temperature' in row.keys() and row['last_temperature'] is not None:
                    telemetry_stats['last_temperature'] = row['last_temperature']
                if 'last_humidity' in row.keys() and row['last_humidity'] is not None:
                    telemetry_stats['last_humidity'] = row['last_humidity']
                if 'last_pressure' in row.keys() and row['last_pressure'] is not None:
                    telemetry_stats['last_pressure'] = row['last_pressure']
                if 'last_air_quality' in row.keys() and row['last_air_quality'] is not None:
                    telemetry_stats['last_air_quality'] = row['last_air_quality']
                
                node_stats[node_id] = {
                    'total_packets': row['total_packets'],
                    'total_bytes': row['total_bytes'],
                    'by_type': defaultdict(int, json.loads(row['packet_types']) if row['packet_types'] else {}),
                    'hourly_activity': defaultdict(int, json.loads(row['hourly_activity']) if row['hourly_activity'] else {}),
                    'message_stats': json.loads(row['message_stats']) if row['message_stats'] else {},
                    'telemetry_stats': telemetry_stats,
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

    def save_neighbor_info(self, node_id: str, neighbors: List[Dict], source: str = 'radio'):
        """
        Sauvegarde les informations de voisinage pour un nœud.

        Args:
            node_id: ID du nœud (format !xxxxxxxx ou hex)
            neighbors: Liste des voisins avec leurs informations
            source: Source des données ('radio' ou 'mqtt')
        """
        try:
            if not neighbors:
                return

            cursor = self.conn.cursor()
            timestamp = time.time()

            for neighbor in neighbors:
                neighbor_id = neighbor.get('node_id')
                if not neighbor_id:
                    continue

                # Normaliser les IDs
                if isinstance(node_id, int):
                    node_id_str = f"!{node_id:08x}"
                else:
                    node_id_str = node_id if node_id.startswith('!') else f"!{node_id}"

                if isinstance(neighbor_id, int):
                    neighbor_id_str = f"!{neighbor_id:08x}"
                else:
                    neighbor_id_str = neighbor_id if neighbor_id.startswith('!') else f"!{neighbor_id}"

                cursor.execute('''
                    INSERT INTO neighbors (
                        timestamp, node_id, neighbor_id, snr,
                        last_rx_time, node_broadcast_interval, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    node_id_str,
                    neighbor_id_str,
                    neighbor.get('snr'),
                    neighbor.get('last_rx_time'),
                    neighbor.get('node_broadcast_interval'),
                    source
                ))

            self.conn.commit()
            logger.debug(f"💾 Sauvegarde {len(neighbors)} voisins pour {node_id_str} (source: {source})")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des voisins : {e}")

    def load_neighbors(self, hours: int = 48) -> Dict[str, List[Dict]]:
        """
        Charge les informations de voisinage récentes.

        Args:
            hours: Nombre d'heures à charger

        Returns:
            Dictionnaire {node_id: [liste de voisins]}
        """
        try:
            cursor = self.conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=hours)).timestamp()

            # Récupérer les dernières entrées de voisinage par node/neighbor
            cursor.execute('''
                SELECT n1.*
                FROM neighbors n1
                INNER JOIN (
                    SELECT node_id, neighbor_id, MAX(timestamp) as max_timestamp
                    FROM neighbors
                    WHERE timestamp >= ?
                    GROUP BY node_id, neighbor_id
                ) n2 ON n1.node_id = n2.node_id
                    AND n1.neighbor_id = n2.neighbor_id
                    AND n1.timestamp = n2.max_timestamp
                ORDER BY n1.node_id, n1.timestamp DESC
            ''', (cutoff,))

            neighbors_by_node = defaultdict(list)
            for row in cursor.fetchall():
                node_id = row['node_id']
                neighbor_data = {
                    'node_id': row['neighbor_id'],
                    'snr': row['snr'],
                    'last_rx_time': row['last_rx_time'],
                    'node_broadcast_interval': row['node_broadcast_interval'],
                    'timestamp': row['timestamp'],
                    'source': row['source'] if 'source' in row.keys() else 'radio'  # Default for old data
                }
                neighbors_by_node[node_id].append(neighbor_data)

            return dict(neighbors_by_node)

        except Exception as e:
            logger.error(f"Erreur lors du chargement des voisins : {e}")
            return {}

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
            packets_deleted = cursor.rowcount
            
            cursor.execute('DELETE FROM public_messages WHERE timestamp < ?', (cutoff,))
            messages_deleted = cursor.rowcount
            
            cursor.execute('DELETE FROM neighbors WHERE timestamp < ?', (cutoff,))
            neighbors_deleted = cursor.rowcount

            self.conn.commit()

            logger.info(f"Nettoyage : {packets_deleted} paquets, {messages_deleted} messages, {neighbors_deleted} voisins supprimés (> {hours}h)")

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
            cursor.execute('DELETE FROM neighbors')

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

            cursor.execute('SELECT COUNT(*) as count FROM neighbors')
            total_neighbors = cursor.fetchone()['count']

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
                'total_neighbors': total_neighbors,
                'oldest_packet': datetime.fromtimestamp(oldest).isoformat() if oldest else None,
                'newest_packet': datetime.fromtimestamp(newest).isoformat() if newest else None,
                'database_size_mb': round(db_size_mb, 2)
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques : {e}")
            return {}

    def get_weather_cache(self, location: str, cache_type: str, max_age_seconds: int = 300) -> Optional[str]:
        """
        Récupère les données météo en cache si elles sont encore valides.

        Args:
            location: Nom de la localisation (ex: "Paris", "" pour default)
            cache_type: Type de cache ("weather", "rain", "astro")
            max_age_seconds: Durée de validité du cache en secondes (défaut: 300 = 5min)

        Returns:
            Les données en cache si valides, None sinon
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT data, timestamp FROM weather_cache
                WHERE location = ? AND cache_type = ?
            ''', (location, cache_type))

            row = cursor.fetchone()
            if row:
                data, timestamp = row['data'], row['timestamp']
                age = time.time() - timestamp

                if age < max_age_seconds:
                    logger.info(f"✅ Cache météo utilisé ({cache_type}/{location}): {int(age)}s/{max_age_seconds}s")
                    return data
                else:
                    logger.info(f"⏱️ Cache météo expiré ({cache_type}/{location}): {int(age)}s > {max_age_seconds}s")
                    return None

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du cache météo : {e}")
            return None

    def get_weather_cache_with_age(self, location: str, cache_type: str, max_age_seconds: int = 86400) -> tuple:
        """
        Récupère les données météo en cache avec leur âge, même si expirées.
        Utilisé pour le pattern "serve stale first, refresh later".

        Args:
            location: Nom de la localisation (ex: "Paris", "" pour default)
            cache_type: Type de cache ("weather", "rain", "astro")
            max_age_seconds: Âge maximum acceptable (défaut: 86400 = 24h)

        Returns:
            tuple: (data, age_hours) ou (None, 0) si pas de cache ou trop vieux
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT data, timestamp FROM weather_cache
                WHERE location = ? AND cache_type = ?
            ''', (location, cache_type))

            row = cursor.fetchone()
            if row:
                data, timestamp = row['data'], row['timestamp']
                age_seconds = time.time() - timestamp
                age_hours = int(age_seconds / 3600)

                # Rejeter cache trop vieux
                if age_seconds > max_age_seconds:
                    logger.info(f"⏰ Cache trop vieux ({cache_type}/{location}): {age_hours}h > {max_age_seconds//3600}h")
                    return (None, 0)

                logger.info(f"📦 Cache récupéré ({cache_type}/{location}): âge={age_hours}h")
                return (data, age_hours)

            return (None, 0)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du cache météo avec âge : {e}")
            return (None, 0)

    def set_weather_cache(self, location: str, cache_type: str, data: str):
        """
        Stocke les données météo en cache.

        Args:
            location: Nom de la localisation (ex: "Paris", "" pour default)
            cache_type: Type de cache ("weather", "rain", "astro")
            data: Données à stocker (string)
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO weather_cache (location, cache_type, data, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (location, cache_type, data, time.time()))

            self.conn.commit()
            logger.info(f"💾 Cache météo sauvegardé ({cache_type}/{location})")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du cache météo : {e}")

    def cleanup_weather_cache(self, max_age_hours: int = 24):
        """
        Nettoie les entrées de cache météo expirées.

        Args:
            max_age_hours: Supprime les caches plus vieux que ce nombre d'heures
        """
        try:
            cursor = self.conn.cursor()
            cutoff = time.time() - (max_age_hours * 3600)

            cursor.execute('DELETE FROM weather_cache WHERE timestamp < ?', (cutoff,))
            deleted = cursor.rowcount
            self.conn.commit()

            if deleted > 0:
                logger.info(f"Nettoyage cache météo : {deleted} entrées supprimées (> {max_age_hours}h)")

        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du cache météo : {e}")

    def export_neighbors_to_json(self, hours: int = 48):
        """
        Exporter les données de voisinage au format JSON pour les cartes HTML.
        Compatible avec le format attendu par map/export_neighbors.py
        
        Args:
            hours: Nombre d'heures de données à exporter
            
        Returns:
            dict: Structure JSON avec les informations de voisinage
        """
        try:
            from datetime import datetime
            import json
            
            neighbors_data = self.load_neighbors(hours=hours)
            
            # Structure de sortie compatible avec export_neighbors.py
            output_data = {
                'export_time': datetime.now().isoformat(),
                'source': 'meshbot_database',
                'total_nodes': len(neighbors_data),
                'nodes': {}
            }
            
            # Convertir les données pour chaque nœud
            for node_id, neighbors in neighbors_data.items():
                # Convertir node_id en format !xxxxxxxx si nécessaire
                if not node_id.startswith('!'):
                    node_id_formatted = f"!{node_id}"
                else:
                    node_id_formatted = node_id
                
                output_data['nodes'][node_id_formatted] = {
                    'neighbors_extracted': neighbors,
                    'neighbor_count': len(neighbors),
                    'export_timestamp': datetime.now().isoformat()
                }
            
            # Statistiques
            total_neighbors = sum(len(n) for n in neighbors_data.values())
            nodes_with_neighbors = len([n for n in neighbors_data.values() if len(n) > 0])
            
            output_data['statistics'] = {
                'nodes_with_neighbors': nodes_with_neighbors,
                'total_neighbor_entries': total_neighbors,
                'average_neighbors': total_neighbors / len(neighbors_data) if neighbors_data else 0
            }
            
            return output_data
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export JSON des voisins : {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    def get_node_position_from_db(self, node_id: str, hours: int = 720) -> Optional[Dict]:
        """
        Récupère la dernière position GPS connue d'un nœud depuis la base de données.
        
        Args:
            node_id: ID du nœud (peut être int, string décimal, ou hex avec !)
            hours: Nombre d'heures à chercher en arrière (défaut: 720h = 30 jours)
            
        Returns:
            Dict avec 'latitude', 'longitude' et 'altitude' ou None si pas trouvé
        """
        try:
            cursor = self.conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=hours)).timestamp()
            
            # Convertir node_id en différents formats pour maximiser les chances de match
            search_ids = []
            
            # Si c'est un entier ou une chaîne numérique
            try:
                if isinstance(node_id, str) and node_id.startswith('!'):
                    # Format !hex
                    node_id_int = int(node_id[1:], 16)
                    search_ids = [node_id, str(node_id_int), node_id_int]
                elif isinstance(node_id, (int, str)):
                    node_id_int = int(node_id) if isinstance(node_id, str) else node_id
                    node_id_hex = f"!{node_id_int:08x}"
                    search_ids = [str(node_id_int), node_id_int, node_id_hex]
            except (ValueError, AttributeError):
                search_ids = [node_id]
            
            debug_print(f"get_node_position_from_db: node_id={node_id}, search_ids={search_ids}, hours={hours}")
            
            # Essayer de trouver une position avec n'importe quel format d'ID
            for search_id in search_ids:
                cursor.execute('''
                    SELECT position
                    FROM packets
                    WHERE from_id = ?
                        AND timestamp >= ?
                        AND position IS NOT NULL
                        AND position != ''
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', (search_id, cutoff))
                
                row = cursor.fetchone()
                if row and row['position']:
                    try:
                        position = json.loads(row['position'])
                        lat = position.get('latitude')
                        lon = position.get('longitude')
                        alt = position.get('altitude')
                        if lat and lon and lat != 0 and lon != 0:
                            debug_print(f"✅ Position trouvée pour {node_id} (via {search_id}): lat={lat}, lon={lon}, alt={alt}")
                            return {'latitude': lat, 'longitude': lon, 'altitude': alt}
                        else:
                            debug_print(f"⚠️ Position invalide pour {node_id}: lat={lat}, lon={lon}")
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        debug_print(f"❌ Erreur parsing position pour {node_id}: {e}")
                        continue
            
            debug_print(f"❌ Aucune position trouvée pour {node_id} (cherché: {search_ids})")
            return None
            
        except Exception as e:
            error_print(f"Erreur lors de la récupération de la position du nœud {node_id} : {e}")
            return None

    def load_radio_links_with_positions(self, hours: int = 24) -> List[Dict]:
        """
        Charge les liaisons radio avec les positions GPS pour calculer les distances.
        
        Args:
            hours: Nombre d'heures à charger
            
        Returns:
            Liste de dicts avec from_id, to_id, snr, rssi, timestamp, from_lat, from_lon, to_lat, to_lon
        """
        try:
            cursor = self.conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=hours)).timestamp()
            
            # Requête pour récupérer les paquets avec positions GPS quand disponibles
            # On utilise les données de position stockées dans le JSON position
            cursor.execute('''
                SELECT 
                    from_id, 
                    to_id, 
                    snr, 
                    rssi,
                    timestamp,
                    position as position_json
                FROM packets
                WHERE timestamp >= ?
                    AND from_id IS NOT NULL 
                    AND to_id IS NOT NULL
                    AND to_id != 4294967295
                    AND to_id != 0
                    AND from_id != to_id
                    AND (snr IS NOT NULL OR rssi IS NOT NULL)
                ORDER BY timestamp DESC
            ''', (cutoff,))
            
            links = []
            for row in cursor.fetchall():
                link = {
                    'from_id': row['from_id'],
                    'to_id': row['to_id'],
                    'snr': row['snr'],
                    'rssi': row['rssi'],
                    'timestamp': row['timestamp']
                }
                
                # Parser le JSON de position si présent (position de l'émetteur)
                if row['position_json']:
                    try:
                        position = json.loads(row['position_json'])
                        link['sender_lat'] = position.get('latitude')
                        link['sender_lon'] = position.get('longitude')
                    except (json.JSONDecodeError, KeyError):
                        pass
                
                links.append(link)
            
            return links
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des liaisons radio : {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def close(self):
        """Ferme la connexion à la base de données."""
        if self.conn:
            self.conn.close()
            logger.info("Connexion à la base de données fermée")

    def __del__(self):
        """Destructeur pour s'assurer que la connexion est fermée."""
        self.close()
