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
from traffic_persistence import TrafficPersistence
import logging

logger = logging.getLogger(__name__)

class TrafficMonitor:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        # File des messages publics
        self.public_messages = deque(maxlen=2000)
        # File de TOUS les paquets
        self.all_packets = deque(maxlen=5000)  # Plus grand pour tous les types
        self.traffic_retention_hours = 24

        # === HISTOGRAMME : COLLECTE PAR TYPE DE PAQUET ===
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
            'ENCRYPTED': '🔐 Chiffré',
            'PKI_ENCRYPTED': '🔐 PKI Chiffré',
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

        # === PERSISTANCE SQLITE ===
        self.persistence = TrafficPersistence()
        logger.info("Initialisation de la persistance SQLite")

        # Charger les données existantes au démarrage
        self._load_persisted_data()

        # === DÉDUPLICATION DES PAQUETS ===
        # Cache pour éviter les doublons (même paquet reçu via serial et TCP)
        # Format: {packet_id: timestamp} avec nettoyage automatique
        self._recent_packets = {}
        self._dedup_window = 5.0  # 5 secondes de fenêtre de déduplication
    
    def populate_neighbors_from_interface(self, interface, wait_time=None, max_wait_time=None, poll_interval=None):
        """
        Attempt to populate neighbor database from Meshtastic interface at startup.
        
        IMPORTANT: This is a BEST-EFFORT operation that may return 0 neighbors.
        
        Neighborinfo is NOT part of the initial database sync (nodeinfo, position, etc.).
        It is ONLY populated when NEIGHBORINFO_APP packets are received, which happens:
        - When nodes broadcast (every 15-30 minutes typically)
        - If the connecting node has cached neighborinfo from previous broadcasts
        
        In most cases at startup, this will return 0 neighbors because:
        - The node's cached neighborinfo may be empty
        - No NEIGHBORINFO_APP broadcasts have arrived yet
        - This is EXPECTED and NORMAL behavior
        
        Passive collection via NEIGHBORINFO_APP packets continues after startup.
        Over time (hours/days), the database will populate as broadcasts arrive.
        
        Uses polling mechanism to wait for interface.nodes to fully load, especially
        important for TCP interfaces which may take 30-60+ seconds with large node databases.
        
        Args:
            interface: Meshtastic interface (serial or TCP)
            wait_time: Initial wait time before first check (default: from config or 10)
            max_wait_time: Maximum total time to wait for nodes to load (default: from config or 60)
            poll_interval: Seconds between progress checks (default: from config or 5)
        
        Returns:
            int: Number of neighbor relationships found (may be 0, which is normal)
        """
        try:
            # Use config values if not specified
            # Access via globals() for backward compatibility with optional config values
            if wait_time is None:
                wait_time = globals().get('NEIGHBOR_LOAD_INITIAL_WAIT', 10)
            if max_wait_time is None:
                max_wait_time = globals().get('NEIGHBOR_LOAD_MAX_WAIT', 60)
            if poll_interval is None:
                poll_interval = globals().get('NEIGHBOR_LOAD_POLL_INTERVAL', 5)
            
            info_print(f"👥 Chargement initial des voisins depuis l'interface...")
            info_print(f"   Attente initiale: {wait_time}s, maximum: {max_wait_time}s, vérification tous les {poll_interval}s")
            
            # Initial wait
            time.sleep(wait_time)
            
            # Check if interface has nodes attribute
            if not hasattr(interface, 'nodes'):
                info_print("⚠️  Interface n'a pas d'attribut 'nodes'")
                return 0
            
            # Polling mechanism: wait for nodes to stabilize
            elapsed_time = wait_time
            previous_node_count = 0
            stable_count = 0
            required_stable_checks = 2  # Need 2 consecutive checks with same count
            
            while elapsed_time < max_wait_time:
                current_node_count = len(interface.nodes) if interface.nodes else 0
                
                if current_node_count == 0:
                    info_print(f"   ⏳ {elapsed_time}s: Aucun nœud chargé, attente...")
                elif current_node_count == previous_node_count:
                    stable_count += 1
                    info_print(f"   ⏳ {elapsed_time}s: {current_node_count} nœuds (stable {stable_count}/{required_stable_checks})")
                    if stable_count >= required_stable_checks:
                        info_print(f"   ✅ Chargement stabilisé à {current_node_count} nœuds après {elapsed_time}s")
                        break
                else:
                    stable_count = 0  # Reset stability counter
                    info_print(f"   📈 {elapsed_time}s: {current_node_count} nœuds chargés (+{current_node_count - previous_node_count})")
                
                previous_node_count = current_node_count
                time.sleep(poll_interval)
                elapsed_time += poll_interval
            
            if not interface.nodes or len(interface.nodes) == 0:
                info_print("⚠️  Aucun nœud disponible dans l'interface après attente")
                return 0
            
            final_node_count = len(interface.nodes)
            info_print(f"📊 Début extraction voisins de {final_node_count} nœuds...")
            
            total_neighbors = 0
            nodes_with_neighbors = 0
            nodes_without_neighbors = 0
            nodes_without_neighborinfo = 0  # Track nodes missing neighborinfo completely
            
            # Sample first few nodes without neighborinfo for debugging
            sample_nodes_without_neighborinfo = []
            max_samples = 3
            
            for node_id, node_info in interface.nodes.items():
                # Normalize node_id
                if isinstance(node_id, str):
                    if node_id.startswith('!'):
                        node_id_int = int(node_id[1:], 16)
                    else:
                        node_id_int = int(node_id, 16)
                else:
                    node_id_int = node_id
                
                # Extract neighbors from node
                neighbors = []
                has_neighborinfo = False
                try:
                    # Check for neighborinfo attribute
                    neighborinfo = None
                    if hasattr(node_info, 'neighborinfo'):
                        neighborinfo = node_info.neighborinfo
                        has_neighborinfo = True
                    elif isinstance(node_info, dict) and 'neighborinfo' in node_info:
                        neighborinfo = node_info['neighborinfo']
                        has_neighborinfo = True
                    
                    if neighborinfo:
                        # Get neighbors list
                        neighbor_list = None
                        if hasattr(neighborinfo, 'neighbors'):
                            neighbor_list = neighborinfo.neighbors
                        elif isinstance(neighborinfo, dict) and 'neighbors' in neighborinfo:
                            neighbor_list = neighborinfo['neighbors']
                        
                        if neighbor_list:
                            for neighbor in neighbor_list:
                                neighbor_data = {}
                                
                                # Extract node_id
                                if hasattr(neighbor, 'node_id'):
                                    neighbor_data['node_id'] = neighbor.node_id
                                elif isinstance(neighbor, dict) and 'node_id' in neighbor:
                                    neighbor_data['node_id'] = neighbor['node_id']
                                else:
                                    continue  # Skip if no node_id
                                
                                # Extract SNR
                                if hasattr(neighbor, 'snr'):
                                    neighbor_data['snr'] = neighbor.snr
                                elif isinstance(neighbor, dict) and 'snr' in neighbor:
                                    neighbor_data['snr'] = neighbor['snr']
                                
                                # Extract last_rx_time
                                if hasattr(neighbor, 'last_rx_time'):
                                    neighbor_data['last_rx_time'] = neighbor.last_rx_time
                                elif isinstance(neighbor, dict) and 'last_rx_time' in neighbor:
                                    neighbor_data['last_rx_time'] = neighbor['last_rx_time']
                                
                                # Extract node_broadcast_interval
                                if hasattr(neighbor, 'node_broadcast_interval'):
                                    neighbor_data['node_broadcast_interval'] = neighbor.node_broadcast_interval
                                elif isinstance(neighbor, dict) and 'node_broadcast_interval' in neighbor:
                                    neighbor_data['node_broadcast_interval'] = neighbor['node_broadcast_interval']
                                
                                neighbors.append(neighbor_data)
                
                except Exception as e:
                    logger.debug(f"Erreur extraction voisins pour {node_id_int:08x}: {e}")
                
                # Track nodes without neighborinfo attribute
                if not has_neighborinfo:
                    nodes_without_neighborinfo += 1
                    if len(sample_nodes_without_neighborinfo) < max_samples:
                        # Get node name for debugging
                        node_name = "Unknown"
                        if hasattr(node_info, 'user'):
                            user = node_info.user
                            if hasattr(user, 'longName'):
                                node_name = user.longName
                        elif isinstance(node_info, dict) and 'user' in node_info:
                            user = node_info['user']
                            node_name = user.get('longName', 'Unknown')
                        sample_nodes_without_neighborinfo.append(f"{node_name} (0x{node_id_int:08x})")
                
                # Save neighbors to database if any found
                if neighbors:
                    self.persistence.save_neighbor_info(node_id_int, neighbors, source='radio')
                    total_neighbors += len(neighbors)
                    nodes_with_neighbors += 1
                else:
                    nodes_without_neighbors += 1
            
            info_print(f"✅ Chargement initial terminé:")
            info_print(f"   • Nœuds totaux: {final_node_count}")
            info_print(f"   • Nœuds avec voisins: {nodes_with_neighbors}")
            info_print(f"   • Nœuds sans voisins: {nodes_without_neighbors}")
            info_print(f"   • Relations de voisinage: {total_neighbors}")
            
            if nodes_with_neighbors > 0:
                avg_neighbors = total_neighbors / nodes_with_neighbors
                info_print(f"   • Moyenne voisins/nœud: {avg_neighbors:.1f}")
            
            # Report nodes without neighborinfo
            # NOTE: This is EXPECTED at startup - neighborinfo is only populated when
            # NEIGHBORINFO_APP packets are received, not from initial database sync
            if nodes_without_neighborinfo > 0:
                info_print(f"   ℹ️  Nœuds sans donnée voisinage en cache: {nodes_without_neighborinfo}/{final_node_count}")
                if sample_nodes_without_neighborinfo:
                    info_print(f"      Exemples: {', '.join(sample_nodes_without_neighborinfo)}")
                
                # Explain expected behavior
                if nodes_without_neighborinfo == final_node_count:
                    info_print(f"      ✓ Normal au démarrage: les données de voisinage ne sont pas incluses")
                    info_print(f"        dans la base initiale du nœud (seulement NODEINFO, POSITION, etc.)")
                    info_print(f"      → Collection passive via NEIGHBORINFO_APP broadcasts (15-30 min)")
                else:
                    info_print(f"      Note: Données de voisinage partielles au démarrage")
                    info_print(f"      → Collection continue via NEIGHBORINFO_APP packets")
            
            return total_neighbors
            
        except Exception as e:
            error_print(f"Erreur lors du chargement initial des voisins: {e}")
            error_print(traceback.format_exc())
            return 0
    
    def add_packet(self, packet, source='unknown', my_node_id=None):
        """
        Enregistrer TOUT type de paquet avec statistiques complètes

        IMPORTANT: Filtre les paquets TELEMETRY_APP auto-générés (from_id == my_node_id) car:
        - Device Metrics sont envoyés toutes les 60s sur serial (pour les apps)
        - Ces paquets serial ne passent PAS par la radio
        - Seuls les paquets selon device_update_interval sont envoyés sur radio
        - On ne veut compter que le trafic radio réel dans les stats mesh

        Args:
            packet: Paquet Meshtastic à enregistrer
            source: Source du paquet ('local', 'tcp', ou 'tigrog2' en mode legacy)
            my_node_id: ID du nœud local (pour filtrer auto-génération)
        """
        # Log périodique pour suivre l'activité (tous les 10 paquets)
        if not hasattr(self, '_packet_add_count'):
            self._packet_add_count = 0
        self._packet_add_count += 1
        if self._packet_add_count % 10 == 0:
            logger.info(f"📥 {self._packet_add_count} paquets reçus dans add_packet() (current queue: {len(self.all_packets)})")

        try:
            from_id = packet.get('from', 0)
            to_id = packet.get('to', 0)
            timestamp = time.time()

            # === DÉDUPLICATION DES PAQUETS ===
            # Créer une clé unique pour détecter les doublons
            packet_id = packet.get('id', None)  # ID Meshtastic unique

            # Nettoyer le cache des anciens paquets (> 5 secondes)
            current_time = timestamp
            self._recent_packets = {
                k: v for k, v in self._recent_packets.items()
                if current_time - v < self._dedup_window
            }

            # Créer une clé de déduplication
            if packet_id:
                dedup_key = f"{packet_id}_{from_id}_{to_id}"
            else:
                # Fallback si pas d'ID : utiliser from/to/timestamp arrondi
                dedup_key = f"{from_id}_{to_id}_{int(timestamp)}"

            # Vérifier si c'est un doublon
            if dedup_key in self._recent_packets:
                # Paquet déjà vu récemment, probablement doublon serial/TCP
                logger.debug(f"Paquet dupliqué ignoré: {dedup_key} (source={source})")
                return

            # Enregistrer ce paquet comme vu
            self._recent_packets[dedup_key] = timestamp

            # === EXTRACTION RSSI/SNR ===
            rssi = packet.get('rssi', packet.get('rxRssi', 0))
            snr = packet.get('snr', packet.get('rxSnr', 0.0))

            # Identifier le type de paquet et détecter le chiffrement
            packet_type = 'UNKNOWN'
            message_text = None
            is_encrypted = False

            if 'decoded' in packet:
                decoded = packet['decoded']
                packet_type = decoded.get('portnum', 'UNKNOWN')

                # === FILTRE: Exclure les paquets TELEMETRY_APP AUTO-GÉNÉRÉS ===
                # Seuls les paquets télémétrie du nœud LOCAL sont filtrés (auto-générés)
                # Les paquets télémétrie des AUTRES nœuds reçus par radio sont conservés
                if packet_type == 'TELEMETRY_APP' and my_node_id and from_id == my_node_id:
                    # Paquet auto-généré par le nœud local - silently ignored
                    return

                if packet_type == 'TEXT_MESSAGE_APP':
                    message_text = self._extract_message_text(decoded)
            elif 'encrypted' in packet:
                # Paquet chiffré - on ne peut pas le lire mais on le compte
                is_encrypted = True
                packet_type = 'ENCRYPTED'
                # Essayer de déduire le type si possible depuis le paquet
                if 'pkiEncrypted' in packet:
                    packet_type = 'PKI_ENCRYPTED'
        
            # Obtenir le nom du nœud
            sender_name = self.node_manager.get_node_name(from_id)
            
            # Calculer la taille approximative du paquet
            packet_size = len(str(packet))
            
            # Calculer les hops
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 5)
            hops_taken = hop_start - hop_limit
            
            # Enregistrer le paquet complet
            packet_entry = {
                'timestamp': timestamp,
                'from_id': from_id,
                'to_id': to_id,
                'source': source,
                'sender_name': sender_name,
                'packet_type': packet_type,
                'message': message_text,
                'rssi': rssi,
                'snr': snr,
                'hops': hops_taken,
                'size': packet_size,
                'is_broadcast': to_id in [0xFFFFFFFF, 0],
                'is_encrypted': is_encrypted
            }

            # Extraire les données de télémétrie pour channel_stats
            if packet_type == 'TELEMETRY_APP' and 'decoded' in packet:
                decoded = packet['decoded']
                if 'telemetry' in decoded:
                    telemetry = decoded['telemetry']
                    if 'deviceMetrics' in telemetry:
                        metrics = telemetry['deviceMetrics']
                        packet_entry['telemetry'] = {
                            'battery': metrics.get('batteryLevel'),
                            'voltage': metrics.get('voltage'),
                            'channel_util': metrics.get('channelUtilization'),
                            'air_util': metrics.get('airUtilTx')
                        }

            # Extraire les informations de voisinage pour NEIGHBORINFO_APP
            if packet_type == 'NEIGHBORINFO_APP' and 'decoded' in packet:
                decoded = packet['decoded']
                neighbors = self._extract_neighbor_info(decoded, from_id)
                if neighbors:
                    try:
                        self.persistence.save_neighbor_info(from_id, neighbors, source='radio')
                        logger.debug(f"👥 {len(neighbors)} voisins enregistrés pour {from_id:08x}")
                    except Exception as e:
                        logger.error(f"Erreur sauvegarde voisins: {e}")

            self.all_packets.append(packet_entry)

            # Log périodique des paquets enregistrés (tous les 25 paquets)
            if not hasattr(self, '_packet_saved_count'):
                self._packet_saved_count = 0
            self._packet_saved_count += 1
            if self._packet_saved_count % 25 == 0:
                logger.info(f"💾 {self._packet_saved_count} paquets enregistrés dans all_packets (size: {len(self.all_packets)})")

            # Sauvegarder le paquet dans SQLite
            try:
                self.persistence.save_packet(packet_entry)
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde du paquet : {e}")

            # Capturer les positions GPS
            if packet_entry['packet_type'] == 'POSITION_APP':
                if packet and 'decoded' in packet:
                    decoded = packet['decoded']
                    if 'position' in decoded:
                        position = decoded['position']
                        lat = position.get('latitude')
                        lon = position.get('longitude')
                        alt = position.get('altitude')

                        if lat is not None and lon is not None:
                            self.node_manager.update_node_position(from_id, lat, lon, alt)
                            #debug_print(f"📍 Position capturée: {from_id:08x} -> {lat:.5f}, {lon:.5f}")

            # NOTE: Les messages publics sont maintenant gérés par add_public_message()
            # appelé depuis main_bot.py pour éviter les doublons
            
            # Mise à jour des statistiques
            self._update_packet_statistics(from_id, sender_name, packet_entry, packet)
            self._update_global_packet_statistics(packet_entry)
            self._update_network_statistics(packet_entry)
            
            # === DEBUG LOG UNIFIÉ POUR TOUS LES PAQUETS ===
            source_tag = f"[{packet_entry.get('source', '?')}]"
            debug_print(f"📊 Paquet enregistré ({source_tag}): {packet_type} de {sender_name}")
            self._log_packet_debug(
                packet_type, sender_name, from_id, hops_taken, snr, packet)
            
        except Exception as e:
            import traceback
            debug_print(f"Erreur enregistrement paquet: {e}")
            debug_print(traceback.format_exc())


    def _log_packet_debug(self, packet_type, sender_name, from_id, hops_taken, snr, packet):
        """
        Log debug unifié pour tous les types de paquets
        """
        try:
            # Formater l'ID en hex court (5 derniers caractères)
            node_id_full = f"{from_id:08x}"
            node_id_short = node_id_full[-5:]  # ex: ad3dc

            # Construction de l'info de routage
            if hops_taken > 0:
                suspected_relay = self._guess_relay_node(snr, from_id)
                if suspected_relay:
                    route_info = f" [via {suspected_relay} ×{hops_taken}]"
                else:
                    route_info = f" [relayé ×{hops_taken}]"
            else:
                route_info = " [direct]"

            # Ajouter le SNR si disponible
            if snr != 0:
                route_info += f" (SNR:{snr:.1f}dB)"
            else:
                route_info += " (SNR:n/a)"

            # Info spécifique pour télémétrie
            if packet_type == 'TELEMETRY_APP':
                telemetry_info = self._extract_telemetry_info(packet)

                # DEBUG SPÉCIAL pour tigrobot G2 PV (!16fad3dc)
                if node_id_full == "16fad3dc": 
                    if 'decoded' in packet and 'telemetry' in packet['decoded']:
                        debug_print(f"🔍 DEBUG Paquet télémétrie complet reçu de {node_id_full} :")
                        telemetry = packet['decoded']['telemetry']

                        # C'est un dict, on peut l'afficher directement
                        import json
                        debug_print(f" {json.dumps(telemetry, indent=2, default=str)}")

                if telemetry_info:
                    debug_print(f"📦 TELEMETRY de {sender_name} {node_id_short}{route_info}: {telemetry_info}")
                else:
                    debug_print(f"📦 TELEMETRY de {sender_name} {node_id_short}{route_info}")
            else:
                debug_print(f"📦 {packet_type} de {sender_name} {node_id_short}{route_info}")

        except Exception as e:
            import traceback
            debug_print(f"Erreur log paquet: {e}")
            debug_print(traceback.format_exc())

    def _extract_telemetry_info(self, packet):
        """
        Extraire les informations de télémétrie formatées
        """
        try:
            if 'decoded' not in packet or 'telemetry' not in packet['decoded']:
                return None
            
            telemetry = packet['decoded']['telemetry']
            info_parts = []
            
            if 'deviceMetrics' in telemetry:
                metrics = telemetry['deviceMetrics']
                battery = metrics.get('batteryLevel', 'N/A')
                voltage = metrics.get('voltage', 'N/A')
                channel_util = metrics.get('channelUtilization', 'N/A')
                air_util = metrics.get('airUtilTx', 'N/A')
                
                info_parts.append(f"🔋 {battery}%")
                if voltage != 'N/A':
                    info_parts.append(f"⚡ {voltage:.2f}V")
                info_parts.append(f"📡 Ch:{channel_util}% Air:{air_util}%")
            
            return ' | '.join(info_parts) if info_parts else None
        except Exception:
            return None

    def _guess_relay_node(self, snr, emitter_id):
        """
        Deviner quel nœud a relayé le paquet en comparant le SNR
        avec l'historique des nœuds voisins connus
        
        Args:
            snr: SNR du paquet reçu
            emitter_id: ID du nœud émetteur (à exclure de la recherche)
        """
        try:
            if not snr or snr == 0:
                return None
            
            # Chercher un nœud voisin avec un SNR similaire (±3 dB)
            best_match = None
            min_diff = float('inf')
            
            for node_id, rx_data in self.node_manager.rx_history.items():
                # NE PAS suggérer l'émetteur comme relais !
                if node_id == emitter_id:
                    continue
                    
                if 'snr' in rx_data:
                    snr_diff = abs(rx_data['snr'] - snr)
                    if snr_diff < min_diff and snr_diff < 3.0:  # ±3dB de tolérance
                        min_diff = snr_diff
                        best_match = rx_data.get('name', '?')
            
            return best_match
        except Exception as e:
            return None

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
    
    def _extract_neighbor_info(self, decoded, from_id):
        """
        Extraire les informations de voisinage depuis un paquet NEIGHBORINFO_APP
        
        Args:
            decoded: Paquet décodé contenant les informations de voisinage
            from_id: ID du nœud émetteur
            
        Returns:
            Liste de dictionnaires avec les informations de voisins
        """
        neighbors = []
        
        try:
            # Structure typique d'un paquet neighborinfo:
            # decoded['neighborinfo']['neighbors'] = liste de voisins
            # Chaque voisin a: node_id, snr, last_rx_time, node_broadcast_interval
            
            if 'neighborinfo' in decoded:
                neighborinfo = decoded['neighborinfo']
                
                if hasattr(neighborinfo, 'neighbors'):
                    # Format objet protobuf
                    neighbor_list = neighborinfo.neighbors
                elif isinstance(neighborinfo, dict) and 'neighbors' in neighborinfo:
                    # Format dictionnaire
                    neighbor_list = neighborinfo['neighbors']
                else:
                    logger.debug(f"Format neighborinfo non reconnu pour {from_id:08x}")
                    return []
                
                for neighbor in neighbor_list:
                    neighbor_data = {}
                    
                    # Extraire node_id (peut être dans différents formats)
                    if hasattr(neighbor, 'node_id'):
                        neighbor_data['node_id'] = neighbor.node_id
                    elif isinstance(neighbor, dict) and 'node_id' in neighbor:
                        neighbor_data['node_id'] = neighbor['node_id']
                    elif hasattr(neighbor, 'nodeId'):
                        neighbor_data['node_id'] = neighbor.nodeId
                    elif isinstance(neighbor, dict) and 'nodeId' in neighbor:
                        neighbor_data['node_id'] = neighbor['nodeId']
                    else:
                        logger.debug(f"node_id manquant dans voisin: {neighbor}")
                        continue
                    
                    # Extraire SNR
                    if hasattr(neighbor, 'snr'):
                        neighbor_data['snr'] = neighbor.snr
                    elif isinstance(neighbor, dict) and 'snr' in neighbor:
                        neighbor_data['snr'] = neighbor['snr']
                    
                    # Extraire last_rx_time
                    if hasattr(neighbor, 'last_rx_time'):
                        neighbor_data['last_rx_time'] = neighbor.last_rx_time
                    elif isinstance(neighbor, dict) and 'last_rx_time' in neighbor:
                        neighbor_data['last_rx_time'] = neighbor['last_rx_time']
                    elif hasattr(neighbor, 'lastRxTime'):
                        neighbor_data['last_rx_time'] = neighbor.lastRxTime
                    elif isinstance(neighbor, dict) and 'lastRxTime' in neighbor:
                        neighbor_data['last_rx_time'] = neighbor['lastRxTime']
                    
                    # Extraire node_broadcast_interval
                    if hasattr(neighbor, 'node_broadcast_interval'):
                        neighbor_data['node_broadcast_interval'] = neighbor.node_broadcast_interval
                    elif isinstance(neighbor, dict) and 'node_broadcast_interval' in neighbor:
                        neighbor_data['node_broadcast_interval'] = neighbor['node_broadcast_interval']
                    elif hasattr(neighbor, 'nodeBroadcastInterval'):
                        neighbor_data['node_broadcast_interval'] = neighbor.nodeBroadcastInterval
                    elif isinstance(neighbor, dict) and 'nodeBroadcastInterval' in neighbor:
                        neighbor_data['node_broadcast_interval'] = neighbor['nodeBroadcastInterval']
                    
                    neighbors.append(neighbor_data)
                
                logger.debug(f"👥 Extrait {len(neighbors)} voisins de {from_id:08x}")
            
        except Exception as e:
            logger.error(f"Erreur extraction voisins pour {from_id:08x}: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return neighbors
    
    def _update_packet_statistics(self, node_id, sender_name, packet_entry, packet):
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
            if 'decoded' in packet:
                decoded = packet['decoded']
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
            if 'decoded' in packet:
                decoded = packet['decoded']
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
            # Charger les paquets directement depuis SQLite pour avoir les données les plus récentes
            all_packets = self.persistence.load_packets(hours=hours, limit=10000)

            # Calculer les stats pour la période
            period_stats = defaultdict(lambda: {
                'total_packets': 0,
                'messages': 0,
                'telemetry': 0,
                'position': 0,
                'nodeinfo': 0,
                'routing': 0,
                'encrypted': 0,
                'other': 0,
                'bytes': 0,
                'last_seen': 0,
                'name': ''
            })
                   # ✅ AJOUT : Compter par source
            local_count = 0
            remote_count = 0  # TCP ou legacy tigrog2

            for msg in self.public_messages:
                current_time = time.time()
                cutoff_time = current_time - (hours * 3600)
                if msg['timestamp'] >= cutoff_time:
                    from_id = msg['from_id']
                    period_stats[from_id]['messages'] += 1
                    #period_stats[from_id]['chars'] += msg['message_length']
                    period_stats[from_id]['chars'] = period_stats[from_id].get('chars', 0) + msg['message_length']
                    period_stats[from_id]['last_seen'] = msg['timestamp']
                    period_stats[from_id]['name'] = msg['sender_name']

                    # Compter par source
                    msg_source = msg.get('source', 'local')
                    if msg_source in ['tigrog2', 'tcp']:
                        remote_count += 1
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
            lines.append(f"  📻 Serial: {local_count}")
            lines.append(f"  📡 TCP: {remote_count}")
            lines.append("")

            # Parcourir tous les paquets
            for packet in all_packets:
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
                    elif packet_type in ('ENCRYPTED', 'PKI_ENCRYPTED'):
                        stats['encrypted'] += 1
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
                lines.append(f"\n{icon} {name}")
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
                    if stats['encrypted'] > 0:
                        breakdown.append(f"🔐{stats['encrypted']}")
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
            for packet in all_packets:
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
            # Charger les paquets directement depuis SQLite pour avoir les données les plus récentes
            all_packets = self.persistence.load_packets(hours=hours, limit=10000)

            type_counts = defaultdict(int)
            total = 0

            for packet in all_packets:
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
            # Charger les paquets directement depuis SQLite pour avoir les données les plus récentes
            all_packets = self.persistence.load_packets(hours=3, limit=10000)

            # Compter tous les paquets récents
            recent_packets = defaultdict(int)
            packet_types = defaultdict(int)

            for packet in all_packets:
                recent_packets[packet['sender_name']] += 1
                packet_types[packet['packet_type']] += 1
            
            if not recent_packets:
                return "📊 Silence radio (3h)"
            
            total = sum(recent_packets.values())
            top_7 = sorted(recent_packets.items(), key=lambda x: x[1], reverse=True)[:7]

            lines = [f"🏆TOP 3h ({total} pqts):"]
            for name, count in top_7:
                name_short = truncate_text(name, 20)
                lines.append(f"{name_short}:{count}")
            
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
            remote_count = sum(1 for m in recent_messages if m.get('source') in ['tigrog2', 'tcp'])

            lines = []
            lines.append(f"📊 TRAFIC PUBLIC ({hours}h)")
            lines.append(f"{'='*30}")
            lines.append(f"Total: {len(recent_messages)} messages")
            lines.append(f"  📻 Serial: {local_count}")
            lines.append(f"  📡 TCP: {remote_count}")
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
                
                # Format: [HH:MM:SS] [NodeName] message
                lines.append(f"[{time_str}] [{sender}] {content}")
            
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
                    
                    # Format: [HH:MM:SS] [NodeName] message
                    lines.append(f"[{time_str}] [{sender}] {content}")
                
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

    def get_packet_histogram_overview(self, hours=24):
        """
        Vue d'ensemble compacte de tous les types de paquets (pour /histo).
        Charge les données directement depuis SQLite pour avoir les données les plus récentes.

        Args:
            hours: Période à analyser (défaut: 24h)

        Returns:
            str: Vue d'ensemble formatée avec compteurs par type
        """
        try:
            # Charger les paquets directement depuis la base de données
            packets = self.persistence.load_packets(hours=hours, limit=10000)

            # Compter les paquets par type
            type_counts = defaultdict(int)
            for packet in packets:
                type_counts[packet['packet_type']] += 1

            # Mapping des noms courts
            short_names = {
                'POSITION_APP': 'POS',
                'TELEMETRY_APP': 'TELE',
                'NODEINFO_APP': 'NODE',
                'TEXT_MESSAGE_APP': 'TEXT'
            }

            lines = [f"📦 Paquets ({hours}h):"]
            total = 0

            # Afficher les types principaux
            for full_name, short_name in short_names.items():
                count = type_counts.get(full_name, 0)
                lines.append(f"{short_name}: {count}")
                total += count

            # Autres types (si présents)
            other_count = sum(count for ptype, count in type_counts.items()
                             if ptype not in short_names)
            if other_count > 0:
                lines.append(f"OTHER: {other_count}")
                total += other_count

            lines.append(f"📊 Total: {total} paquets")
            lines.append("")
            lines.append("Détails: /histo <type>")
            lines.append("Types: pos, tele, node, text")

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur génération vue d'ensemble: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:50]}"

    def get_hourly_histogram(self, packet_filter='all', hours=24):
        """
        Générer un histogramme de distribution horaire des paquets.
        Charge les données directement depuis SQLite pour avoir les données les plus récentes.

        Args:
            packet_filter: 'all', 'messages', 'pos', 'info', 'telemetry', etc.
            hours: Nombre d'heures à analyser (défaut: 24)

        Returns:
            str: Histogramme ASCII formaté
        """
        try:
            # Charger les paquets directement depuis la base de données
            all_packets = self.persistence.load_packets(hours=hours, limit=10000)

            # Mapping des filtres vers les types de paquets réels
            filter_mapping = {
                'messages': 'TEXT_MESSAGE_APP',
                'pos': 'POSITION_APP',
                'info': 'NODEINFO_APP',
                'telemetry': 'TELEMETRY_APP',
                'traceroute': 'TRACEROUTE_APP',
                'routing': 'ROUTING_APP'
            }

            # Filtrer les paquets par type
            filtered_packets = []
            for pkt in all_packets:
                if packet_filter == 'all':
                    filtered_packets.append(pkt)
                elif packet_filter in filter_mapping:
                    if pkt['packet_type'] == filter_mapping[packet_filter]:
                        filtered_packets.append(pkt)
                elif pkt['packet_type'] == packet_filter:
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

    def get_histogram_report(self, hours=24, packet_type=None, compact=False):
        """
        Générer un histogramme avec sparkline (version moderne et compacte).

        Args:
            hours: Nombre d'heures à analyser
            packet_type: Type de paquet à filtrer (None = tous)
            compact: True pour version mesh (ultra-compact), False pour Telegram

        Returns:
            str: Histogramme avec sparkline
        """
        try:
            # Charger les paquets depuis SQLite
            all_packets = self.persistence.load_packets(hours=hours, limit=10000)

            # Mapping des types
            type_mapping = {
                'POSITION_APP': ['pos', 'position'],
                'TEXT_MESSAGE_APP': ['text', 'msg', 'message'],
                'NODEINFO_APP': ['node', 'info', 'nodeinfo'],
                'TELEMETRY_APP': ['tele', 'telemetry'],
                'TRACEROUTE_APP': ['trace', 'traceroute'],
                'ROUTING_APP': ['route', 'routing']
            }

            # Filtrer par type si spécifié
            filtered_packets = []
            filter_label = "TOUS"

            if packet_type:
                packet_type_lower = packet_type.lower()
                matched_type = None

                # Trouver le type correspondant
                for full_type, aliases in type_mapping.items():
                    if packet_type_lower in aliases or packet_type == full_type:
                        matched_type = full_type
                        filter_label = aliases[0].upper()
                        break

                if matched_type:
                    filtered_packets = [p for p in all_packets if p['packet_type'] == matched_type]
                else:
                    filtered_packets = [p for p in all_packets if p['packet_type'] == packet_type]
                    filter_label = packet_type.upper()
            else:
                filtered_packets = all_packets

            if not filtered_packets:
                return f"📊 Aucun paquet ({hours}h)"

            # Compter par heure (chronologique sur les dernières X heures)
            from datetime import datetime, timedelta
            now = datetime.now()
            hourly_counts = []
            hour_labels = []

            for i in range(hours - 1, -1, -1):  # De oldest à newest
                target_time = now - timedelta(hours=i)
                hour_start = target_time.replace(minute=0, second=0, microsecond=0)
                hour_end = hour_start + timedelta(hours=1)

                count = sum(1 for p in filtered_packets
                           if hour_start.timestamp() <= p['timestamp'] < hour_end.timestamp())
                hourly_counts.append(count)
                hour_labels.append(hour_start.strftime('%H'))

            # Symboles sparkline
            sparkline_symbols = "▁▂▃▄▅▆▇█"

            # Générer sparkline
            if not hourly_counts or max(hourly_counts) == 0:
                sparkline = "▁" * len(hourly_counts)
            else:
                max_count = max(hourly_counts)
                min_count = min(hourly_counts)

                sparkline = ""
                for count in hourly_counts:
                    if max_count == min_count:
                        symbol_idx = 4  # Milieu si tous égaux
                    else:
                        normalized = (count - min_count) / (max_count - min_count)
                        symbol_idx = int(normalized * (len(sparkline_symbols) - 1))
                        symbol_idx = max(0, min(len(sparkline_symbols) - 1, symbol_idx))
                    sparkline += sparkline_symbols[symbol_idx]

            # Stats
            total = len(filtered_packets)
            unique_nodes = len(set(p['from_id'] for p in filtered_packets))
            avg = total / hours
            current_hour_count = hourly_counts[-1] if hourly_counts else 0

            # Tendance (3 dernières heures)
            if len(hourly_counts) >= 3:
                recent = hourly_counts[-3:]
                if recent[-1] > recent[-2]:
                    trend = "↗"
                elif recent[-1] < recent[-2]:
                    trend = "↘"
                else:
                    trend = "→"
            else:
                trend = "→"

            # Format de sortie
            lines = []

            if compact:
                # Version mesh ultra-compacte
                lines.append(f"📊 {filter_label}({hours}h)")
                lines.append(sparkline)
                lines.append(f"{total}p {unique_nodes}n {trend}")
                lines.append(f"Now:{current_hour_count} Avg:{avg:.1f}/h")
            else:
                # Version Telegram détaillée
                lines.append(f"📊 **HISTOGRAMME {filter_label}** ({hours}h)")
                lines.append("=" * 50)
                lines.append("")
                lines.append(f"**📈 Évolution temporelle:**")
                lines.append(f"`{sparkline}`")
                lines.append("")
                lines.append(f"**📊 Statistiques:**")
                lines.append(f"• Total: {total} paquets")
                lines.append(f"• Nœuds uniques: {unique_nodes}")
                lines.append(f"• Moyenne: {avg:.1f} paquets/heure")
                lines.append(f"• Heure actuelle: {current_hour_count} paquets {trend}")
                lines.append("")

                # Heure de pointe
                if hourly_counts:
                    max_idx = hourly_counts.index(max(hourly_counts))
                    peak_hour = hour_labels[max_idx]
                    peak_count = hourly_counts[max_idx]
                    lines.append(f"🏆 **Pointe:** {peak_hour}h00 ({peak_count} paquets)")

                # Distribution par heure (dernières 6h seulement pour ne pas surcharger)
                if hours <= 12:
                    lines.append("")
                    lines.append("**⏰ Dernières heures:**")
                    for i in range(min(6, len(hourly_counts))):
                        idx = -(i + 1)
                        h = hour_labels[idx]
                        c = hourly_counts[idx]
                        pct = (c / total * 100) if total > 0 else 0
                        bar_len = int(c / max(hourly_counts) * 15) if max(hourly_counts) > 0 else 0
                        bar = "█" * bar_len
                        lines.append(f"{h}h: {bar} {c} ({pct:.1f}%)")

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur histogram_report: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def add_public_message(self, packet, message_text, source='local'):
        """
        Enregistrer un message public avec collecte de statistiques avancées

        Args:
            packet: Packet Meshtastic
            message_text: Texte du message
            source: 'local' (Serial), 'tcp' (TCP), ou 'tigrog2' (legacy)
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

            # Sauvegarder le message dans SQLite
            try:
                self.persistence.save_public_message(message_entry)
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde du message public : {e}")
            
            # === MISE À JOUR DES STATISTIQUES ===
            self._update_node_statistics(from_id, sender_name, message_text, timestamp)
            self._update_global_statistics(timestamp)
            
            # Analyser les commandes
            if message_text.startswith('/'):
                self.node_stats[from_id]['commands_sent'] += 1
                if message_text.startswith('/echo'):
                    self.node_stats[from_id]['echo_sent'] += 1
            
            # Log avec icône source
            source_icon = "📡" if source in ['tigrog2', 'tcp'] else "📻"
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


    # Ajouter à traffic_monitor.py

    def analyze_network_health(self, hours=24):
        """
        Analyser la santé du réseau et détecter les problèmes de configuration

        Retourne un rapport détaillé avec :
        - Top talkers (nœuds bavards)
        - Nœuds avec intervalles de télémétrie trop courts
        - Utilisation excessive du canal
        - Nœuds relayant beaucoup (routeurs efficaces)
        """
        try:
            # Charger les paquets directement depuis SQLite pour avoir les données les plus récentes
            all_packets = self.persistence.load_packets(hours=hours, limit=10000)

            lines = []
            lines.append(f"🔍 ANALYSE SANTÉ RÉSEAU ({hours}h)")
            lines.append("=" * 50)

            # === 1. TOP TALKERS (nœuds bavards) ===
            node_packet_counts = defaultdict(int)
            node_telemetry_intervals = defaultdict(list)
            node_types = defaultdict(lambda: defaultdict(int))
            node_channel_util = defaultdict(list)

            for packet in all_packets:
                    # ✅ FILTRER: En mode legacy, utiliser uniquement paquets TCP (meilleure antenne)
                    if packet.get('source') not in ['tigrog2', 'tcp']:
                        continue

                    from_id = packet['from_id']
                    node_packet_counts[from_id] += 1
                    node_types[from_id][packet['packet_type']] += 1
                    
                    # Tracker les intervalles de télémétrie
                    if packet['packet_type'] == 'TELEMETRY_APP':
                        node_telemetry_intervals[from_id].append(packet['timestamp'])
            
            # Trier par nombre de paquets
            top_talkers = sorted(node_packet_counts.items(), key=lambda x: x[1], reverse=True)
            
            lines.append(f"\n📊 TOP TALKERS (nœuds les plus actifs):")
            lines.append("-" * 50)
            
            for i, (node_id, count) in enumerate(top_talkers[:10], 1):
                name = self.node_manager.get_node_name(node_id)
                pct = (count / len(all_packets) * 100) if len(all_packets) > 0 else 0
                
                # Analyser les types de paquets
                types = node_types[node_id]
                telemetry_count = types.get('TELEMETRY_APP', 0)
                position_count = types.get('POSITION_APP', 0)
                
                icon = "🔴" if count > 100 else "🟡" if count > 50 else "🟢"
                
                lines.append(f"{i}. {icon} {name[:20]}")
                lines.append(f"   Total: {count} paquets ({pct:.1f}% du trafic)")
                lines.append(f"   Télémétrie: {telemetry_count} | Position: {position_count}")
                
                # Détecter intervalle de télémétrie trop court
                if telemetry_count >= 2:
                    intervals = node_telemetry_intervals[node_id]
                    if len(intervals) >= 2:
                        # ✅ Supprimer les doublons et trier
                        unique_intervals = sorted(set(intervals))

                        if len(unique_intervals) >= 2:
                            # ✅ Calculer intervalle moyen sur la durée totale
                            total_time = unique_intervals[-1] - unique_intervals[0]
                            avg_interval = total_time / (len(unique_intervals) - 1)

                            if avg_interval < 300:
                                lines.append(f"   ⚠️  INTERVALLE TÉLÉMÉTRIE COURT: {avg_interval:.0f}s (recommandé: 900s+)")
                                lines.append(f"   📊 Paquets: {len(intervals)} reçus ({len(unique_intervals)} uniques)")

            # === 2. ANALYSE UTILISATION DU CANAL ===
            lines.append(f"\n📡 UTILISATION DU CANAL:")
            lines.append("-" * 50)
            
            # Calculer l'utilisation moyenne par nœud depuis les paquets de télémétrie
            node_channel_stats = {}
            for packet in all_packets:
                if packet['packet_type'] == 'TELEMETRY_APP':
                    from_id = packet['from_id']
                    # Extraire channelUtilization depuis le paquet
                    if from_id in self.node_packet_stats:
                        stats = self.node_packet_stats[from_id]
                        if 'telemetry_stats' in stats and stats['telemetry_stats']['last_channel_util']:
                            ch_util = stats['telemetry_stats']['last_channel_util']
                            if from_id not in node_channel_stats:
                                node_channel_stats[from_id] = []
                            node_channel_stats[from_id].append(ch_util)
            
            # Moyennes par nœud
            for node_id, utils in node_channel_stats.items():
                if utils:
                    avg_util = sum(utils) / len(utils)
                    if avg_util > 15:  # Seuil d'alerte à 15%
                        name = self.node_manager.get_node_name(node_id)
                        icon = "🔴" if avg_util > 25 else "🟡"
                        lines.append(f"{icon} {name[:20]}: {avg_util:.1f}% (moy)")
                        if avg_util > 20:
                            lines.append(f"   ⚠️  UTILISATION ÉLEVÉE - Risque de congestion")
            
            # === 3. ANALYSE DES RELAIS (routeurs efficaces) ===
            lines.append(f"\n🔀 ANALYSE DES RELAIS:")
            lines.append("-" * 50)

            relay_counts = defaultdict(int)
            for packet in all_packets:
                if packet['hops'] > 0:
                    # Les paquets relayés passent par des nœuds intermédiaires
                    # On ne peut pas identifier précisément le relais, mais on peut compter
                    relay_counts['relayed_packets'] += 1

            direct_count = sum(1 for p in all_packets if p['hops'] == 0)
            relayed_count = relay_counts['relayed_packets']
            
            if direct_count + relayed_count > 0:
                relay_pct = (relayed_count / (direct_count + relayed_count) * 100)
                lines.append(f"Paquets directs: {direct_count} ({100-relay_pct:.1f}%)")
                lines.append(f"Paquets relayés: {relayed_count} ({relay_pct:.1f}%)")
                
                if relay_pct > 70:
                    lines.append(f"⚠️  Beaucoup de relayage - Réseau très maillé ou faible portée")
            
            # === 4. DÉTECTION D'ANOMALIES ===
            lines.append(f"\n⚠️  ANOMALIES DÉTECTÉES:")
            lines.append("-" * 50)
            
            anomalies_found = False
            
            # Détecter nœuds avec trop de paquets
            for node_id, count in top_talkers[:5]:
                if count > 100:  # Plus de 100 paquets en 24h
                    name = self.node_manager.get_node_name(node_id)
                    per_hour = count / hours
                    lines.append(f"🔴 {name}: {per_hour:.1f} paquets/h")
                    
                    # Recommandation spécifique
                    telemetry_count = node_types[node_id].get('TELEMETRY_APP', 0)
                    position_count = node_types[node_id].get('POSITION_APP', 0)
                    
                    if telemetry_count > 50:
                        lines.append(f"   → Augmenter device_update_interval (actuellement < {hours*3600/telemetry_count:.0f}s)")
                    if position_count > 50:
                        lines.append(f"   → Augmenter position.broadcast_secs")
                    
                    anomalies_found = True
            
            if not anomalies_found:
                lines.append("✅ Aucune anomalie majeure détectée")
            
            # === 5. STATISTIQUES GLOBALES ===
            lines.append(f"\n📈 STATISTIQUES GLOBALES:")
            lines.append("-" * 50)
            
            total_packets = len([p for p in self.all_packets if p['timestamp'] >= cutoff_time])
            unique_nodes = len(set(p['from_id'] for p in self.all_packets if p['timestamp'] >= cutoff_time))
            
            lines.append(f"Paquets totaux: {total_packets}")
            lines.append(f"Nœuds actifs: {unique_nodes}")
            lines.append(f"Moy. par nœud: {total_packets/unique_nodes:.1f}" if unique_nodes > 0 else "N/A")
            lines.append(f"Paquets/heure: {total_packets/hours:.1f}")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur analyse réseau: {e}")
            import traceback
            error_print(traceback.format_exc())
            return f"❌ Erreur analyse: {str(e)[:100]}"

    def get_node_behavior_report(self, node_id, hours=24):
        """
        Rapport détaillé sur un nœud - Affiche l'ID complet et détecte les doublons
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)

            name = self.node_manager.get_node_name(node_id)

            lines = []
            lines.append(f"🔍 RAPPORT NŒUD: {name}")
            lines.append(f"ID: !{node_id:08x}")
            lines.append(f"PVID: !{node_id:08x}")
            lines.append("=" * 50)

            # Collecter les paquets de CE nœud uniquement (par from_id)
            # Note: En mode single-node, tous les paquets viennent de la même source
            node_packets = [p for p in self.all_packets 
                            if p['from_id'] == node_id 
                            and p['timestamp'] >= cutoff_time]
            
            """if not node_packets:
                # Vérifier s'il y a des paquets serial ignorés (mode legacy uniquement)
                serial_packets = [p for p in self.all_packets 
                                 if p['from_id'] == node_id 
                                 and p['timestamp'] >= cutoff_time
                                 and p.get('source') == 'local']
                
                if serial_packets:
                    return f"⚠️ Aucun paquet TCP pour {name} (!{node_id:08x})\n" \
                           f"({len(serial_packets)} paquets serial ignorés - antenne faible)"
                
                return f"Aucun paquet de {name} (!{node_id:08x}) dans les {hours}h"""

            # Statistiques de base
            lines.append(f"\\n📊 ACTIVITÉ ({hours}h):")
            lines.append(f"Total paquets: {len(node_packets)}")
            lines.append(f"Paquets/heure: {len(node_packets)/hours:.1f}")

            # Par type
            type_counts = defaultdict(int)
            for p in node_packets:
                type_counts[p['packet_type']] += 1

            lines.append(f"\\n📦 RÉPARTITION PAR TYPE:")
            for ptype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                type_name = self.packet_type_names.get(ptype, ptype)
                lines.append(f"  {type_name}: {count}")

            # Analyse télémétrie
            telemetry_packets = [p for p in node_packets if p['packet_type'] == 'TELEMETRY_APP']
            if len(telemetry_packets) >= 2:
                timestamps = [p['timestamp'] for p in telemetry_packets]
                intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
                avg_interval = sum(intervals) / len(intervals)

                lines.append(f"\\n⏱  TÉLÉMÉTRIE:")
                lines.append(f"Intervalle moyen: {avg_interval:.0f}s ({avg_interval/60:.1f}min)")
                lines.append(f"Intervalle min: {min(intervals):.0f}s")
                lines.append(f"Intervalle max: {max(intervals):.0f}s")

                if avg_interval < 300:
                    lines.append(f"\\n⚠  TROP FRÉQUENT (recommandé: 900s+)")
                    lines.append(f"💡 Commande: meshtastic --set telemetry.device_update_interval 900")

            # Analyse position
            position_packets = [p for p in node_packets if p['packet_type'] == 'POSITION_APP']
            if len(position_packets) >= 2:
                timestamps = [p['timestamp'] for p in position_packets]
                intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
                avg_interval = sum(intervals) / len(intervals)

                lines.append(f"\\n📍 POSITION:")
                lines.append(f"Intervalle moyen: {avg_interval:.0f}s ({avg_interval/60:.1f}min)")

                if avg_interval < 300:
                    lines.append(f"\\n⚠  TROP FRÉQUENT (recommandé: 900s+)")
                    lines.append(f"💡 Commande: meshtastic --set position.broadcast_secs 900")

            # Statistiques de réception
            direct_packets = [p for p in node_packets if p['hops'] == 0]
            relayed_packets = [p for p in node_packets if p['hops'] > 0]

            if len(node_packets) > 0:
                lines.append(f"\\n📡 RÉCEPTION:")
                lines.append(f"Paquets directs: {len(direct_packets)} ({len(direct_packets)/len(node_packets)*100:.1f}%)")
                lines.append(f"Paquets relayés: {len(relayed_packets)} ({len(relayed_packets)/len(node_packets)*100:.1f}%)")

                if len(relayed_packets) > 0:
                    avg_hops = sum(p['hops'] for p in relayed_packets) / len(relayed_packets)
                    max_hops = max(p['hops'] for p in relayed_packets)
                    lines.append(f"Hops moyens: {avg_hops:.1f}")
                    lines.append(f"Hops max: {max_hops}")

            # Diagnostic
            lines.append(f"\\n🔍 DIAGNOSTIC:")
            lines.append(f"✅ Tous les paquets proviennent de !{node_id:08x}")
            lines.append(f"✅ Stats correctes pour CE nœud uniquement")

            # Alerte doublons
            same_name_count = sum(1 for nid, ndata in self.node_manager.node_names.items()
                                 if (isinstance(ndata, dict) and ndata.get('name') == name) or
                                    (isinstance(ndata, str) and ndata == name))
            if same_name_count > 1:
                lines.append(f"\\n⚠  ATTENTION: {same_name_count} nœuds portent '{name}'")
                lines.append(f"💡 Utilisez toujours l'ID complet")

            return "\\n".join(lines)

        except Exception as e:
            error_print(f"Erreur rapport nœud: {e}")
            import traceback
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:50]}"

    # ========== MÉTHODES DE PERSISTANCE ==========

    def _load_persisted_data(self):
        """
        Charge les données persistées depuis SQLite au démarrage.
        Restaure les paquets, messages et statistiques.
        """
        try:
            logger.info("📂 Chargement des données persistées depuis SQLite...")

            # Charger les paquets (dernières 48h pour correspondre à la rétention, max 5000)
            packets = self.persistence.load_packets(hours=48, limit=5000)
            for packet in reversed(packets):  # Inverser pour avoir l'ordre chronologique
                self.all_packets.append(packet)
            logger.info(f"✅ {len(packets)} paquets chargés depuis SQLite (all_packets size: {len(self.all_packets)})")

            # Charger les messages publics (dernières 48h pour correspondre à la rétention, max 2000)
            messages = self.persistence.load_public_messages(hours=48, limit=2000)
            for message in reversed(messages):
                self.public_messages.append(message)
            logger.info(f"✓ {len(messages)} messages publics chargés")

            # Charger les statistiques par nœud
            node_stats = self.persistence.load_node_stats()
            if node_stats:
                # Fusionner avec les stats existantes
                for node_id, stats in node_stats.items():
                    self.node_packet_stats[node_id] = stats
                logger.info(f"✓ Statistiques de {len(node_stats)} nœuds chargées")

            # Charger les statistiques globales
            global_stats = self.persistence.load_global_stats()
            if global_stats:
                self.global_packet_stats = global_stats
                logger.info("✓ Statistiques globales chargées")

            # Charger les statistiques réseau
            network_stats = self.persistence.load_network_stats()
            if network_stats:
                self.network_stats = network_stats
                logger.info("✓ Statistiques réseau chargées")

            # Afficher un résumé
            summary = self.persistence.get_stats_summary()
            logger.info(f"Base de données : {summary.get('database_size_mb', 0)} MB")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des données persistées : {e}")
            import traceback
            logger.error(traceback.format_exc())

    def save_statistics(self):
        """
        Sauvegarde les statistiques agrégées dans SQLite.
        À appeler périodiquement pour éviter la perte de données.
        """
        try:
            # Sauvegarder les statistiques par nœud
            self.persistence.save_node_stats(dict(self.node_packet_stats))

            # Sauvegarder les statistiques globales
            self.persistence.save_global_stats(self.global_packet_stats)

            # Sauvegarder les statistiques réseau
            self.persistence.save_network_stats(self.network_stats)

            logger.debug("Statistiques sauvegardées dans SQLite")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des statistiques : {e}")

    def cleanup_old_persisted_data(self, hours: int = 48):
        """
        Nettoie les anciennes données dans SQLite.

        Args:
            hours: Nombre d'heures à conserver (par défaut 48h)
        """
        try:
            self.persistence.cleanup_old_data(hours=hours)
            logger.info(f"Nettoyage des données SQLite (> {hours}h)")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des données : {e}")

    def clear_traffic_history(self):
        """
        Efface tout l'historique du trafic (mémoire et SQLite).
        """
        try:
            # Effacer les données en mémoire
            self.all_packets.clear()
            self.public_messages.clear()
            self.node_packet_stats.clear()

            # Réinitialiser les statistiques globales
            self.global_packet_stats = {
                'total_packets': 0,
                'by_type': defaultdict(int),
                'total_bytes': 0,
                'unique_nodes': set(),
                'busiest_hour': None,
                'quietest_hour': None,
                'last_reset': time.time()
            }

            # Réinitialiser les statistiques réseau
            self.network_stats = {
                'total_hops': 0,
                'max_hops_seen': 0,
                'avg_rssi': 0.0,
                'avg_snr': 0.0,
                'packets_direct': 0,
                'packets_relayed': 0
            }

            # Effacer les données dans SQLite
            self.persistence.clear_all_data()

            logger.info("Historique du trafic effacé (mémoire et SQLite)")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'effacement de l'historique : {e}")
            return False

    def get_persistence_stats(self) -> str:
        """
        Retourne un rapport sur l'état de la persistance.

        Returns:
            Texte formaté avec les statistiques de la base de données
        """
        try:
            summary = self.persistence.get_stats_summary()

            lines = ["📊 STATISTIQUES DE PERSISTANCE"]
            lines.append("=" * 40)
            lines.append(f"Total paquets : {summary.get('total_packets', 0):,}")
            lines.append(f"Total messages : {summary.get('total_messages', 0):,}")
            lines.append(f"Nœuds uniques : {summary.get('total_nodes', 0)}")
            lines.append(f"Taille DB : {summary.get('database_size_mb', 0):.2f} MB")

            if summary.get('oldest_packet'):
                lines.append(f"\nPaquet le plus ancien : {summary['oldest_packet']}")
            if summary.get('newest_packet'):
                lines.append(f"Paquet le plus récent : {summary['newest_packet']}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats de persistance : {e}")
            return f"❌ Erreur : {e}"

    def get_neighbors_report(self, node_filter=None, compact=True, max_distance_km=None):
        """
        Générer un rapport sur les voisins mesh
        
        Args:
            node_filter: Nom ou ID partiel du nœud à filtrer (optionnel)
            compact: Format compact pour LoRa (180 chars) ou détaillé pour Telegram
            max_distance_km: Distance maximale en km pour filtrer les nœuds (défaut: config.NEIGHBORS_MAX_DISTANCE_KM ou 100)
            
        Returns:
            Rapport formaté des voisins
        """
        try:
            # Utiliser la configuration ou la valeur par défaut
            if max_distance_km is None:
                try:
                    from config import NEIGHBORS_MAX_DISTANCE_KM
                    max_distance_km = NEIGHBORS_MAX_DISTANCE_KM
                except ImportError:
                    max_distance_km = 100  # Valeur par défaut si config non disponible
            
            # Charger les données de voisinage depuis SQLite
            neighbors_data = self.persistence.load_neighbors(hours=48)
            
            if not neighbors_data:
                return "❌ Aucune donnée de voisinage disponible. Les nœuds doivent avoir neighborinfo activé."
            
            # Filtrer par distance (supprimer les nœuds trop loin)
            # Ceci filtre les nœuds étrangers du réseau MQTT public
            filtered_by_distance = {}
            nodes_filtered_count = 0
            
            # Obtenir la position de référence (bot)
            ref_pos = self.node_manager.get_reference_position()
            
            if ref_pos and ref_pos[0] != 0 and ref_pos[1] != 0:
                ref_lat, ref_lon = ref_pos
                
                for node_id, neighbors in neighbors_data.items():
                    # Convertir node_id string (!xxxxxxxx) en int
                    try:
                        if node_id.startswith('!'):
                            node_id_int = int(node_id[1:], 16)
                        else:
                            node_id_int = int(node_id, 16)
                    except (ValueError, AttributeError):
                        # Si conversion échoue, garder le nœud par défaut
                        filtered_by_distance[node_id] = neighbors
                        continue
                    
                    # Obtenir les données du nœud (position GPS)
                    node_data = self.node_manager.get_node_data(node_id_int)
                    
                    if node_data and 'latitude' in node_data and 'longitude' in node_data:
                        node_lat = node_data['latitude']
                        node_lon = node_data['longitude']
                        
                        # Calculer la distance
                        distance_km = self.node_manager.haversine_distance(
                            ref_lat, ref_lon, node_lat, node_lon
                        )
                        
                        # Filtrer si > max_distance_km
                        if distance_km <= max_distance_km:
                            filtered_by_distance[node_id] = neighbors
                        else:
                            nodes_filtered_count += 1
                            debug_print(f"👥 Nœud filtré (>{max_distance_km}km): {node_id} à {distance_km:.1f}km")
                    else:
                        # Pas de position GPS - garder le nœud par défaut
                        # (peut être un nœud local sans GPS)
                        filtered_by_distance[node_id] = neighbors
                
                # Remplacer neighbors_data par les données filtrées
                neighbors_data = filtered_by_distance
                
                if nodes_filtered_count > 0:
                    debug_print(f"👥 {nodes_filtered_count} nœud(s) filtré(s) pour distance >{max_distance_km}km")
            else:
                debug_print("👥 Pas de position de référence - filtrage par distance désactivé")
            
            # Filtrer si nécessaire
            if node_filter:
                filtered_data = {}
                node_filter_lower = node_filter.lower()
                
                for node_id, neighbors in neighbors_data.items():
                    # Chercher par ID (hex) ou nom
                    node_name = self.node_manager.get_node_name(
                        int(node_id[1:], 16) if node_id.startswith('!') else int(node_id, 16)
                    )
                    
                    if (node_filter_lower in node_id.lower() or 
                        node_filter_lower in node_name.lower()):
                        filtered_data[node_id] = neighbors
                
                if not filtered_data:
                    return f"❌ Aucun nœud trouvé pour '{node_filter}'"
                
                neighbors_data = filtered_data
            
            if compact:
                # Format compact pour LoRa (180 chars max)
                lines = []
                total_nodes = len(neighbors_data)
                total_neighbors = sum(len(n) for n in neighbors_data.values())
                
                lines.append(f"👥 {total_nodes} nœuds, {total_neighbors} liens")
                
                # Trier par nombre de voisins (décroissant)
                sorted_nodes = sorted(
                    neighbors_data.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
                
                # Afficher les 3 premiers seulement en mode compact
                for node_id, neighbors in sorted_nodes[:3]:
                    node_num = int(node_id[1:], 16) if node_id.startswith('!') else int(node_id, 16)
                    node_name = self.node_manager.get_node_name(node_num)
                    
                    # Nom court (max 8 chars)
                    if len(node_name) > 8:
                        node_name = node_name[:8]
                    
                    # Calculer SNR moyen
                    snrs = [n.get('snr', 0) for n in neighbors if n.get('snr')]
                    avg_snr = sum(snrs) / len(snrs) if snrs else 0
                    
                    lines.append(f"{node_name}: {len(neighbors)}v SNR{avg_snr:.0f}")
                
                if len(sorted_nodes) > 3:
                    lines.append(f"...+{len(sorted_nodes) - 3} autres")
                
                return "\n".join(lines)
            
            else:
                # Format détaillé pour Telegram
                lines = []
                lines.append("👥 **Voisins Mesh**\n")
                
                total_nodes = len(neighbors_data)
                total_neighbors = sum(len(n) for n in neighbors_data.values())
                lines.append(f"📊 **Statistiques**: {total_nodes} nœuds, {total_neighbors} liens totaux\n")
                
                # Trier par nombre de voisins (décroissant)
                sorted_nodes = sorted(
                    neighbors_data.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
                
                for node_id, neighbors in sorted_nodes:
                    node_num = int(node_id[1:], 16) if node_id.startswith('!') else int(node_id, 16)
                    node_name = self.node_manager.get_node_name(node_num)
                    
                    lines.append(f"**{node_name}** ({node_id})")
                    lines.append(f"  └─ {len(neighbors)} voisin(s):")
                    
                    # Trier voisins par SNR (meilleur d'abord)
                    sorted_neighbors = sorted(
                        neighbors,
                        key=lambda x: x.get('snr', -999),
                        reverse=True
                    )
                    
                    for neighbor in sorted_neighbors:
                        neighbor_num = neighbor['node_id']
                        if isinstance(neighbor_num, str):
                            neighbor_num = int(neighbor_num[1:], 16) if neighbor_num.startswith('!') else int(neighbor_num, 16)
                        
                        neighbor_name = self.node_manager.get_node_name(neighbor_num)
                        snr = neighbor.get('snr')
                        
                        snr_str = f"SNR: {snr:.1f}" if snr else "SNR: N/A"
                        lines.append(f"     • {neighbor_name}: {snr_str}")
                    
                    lines.append("")  # Ligne vide entre nœuds
                
                return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Erreur dans get_neighbors_report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"⚠️ Erreur: {str(e)[:50]}"


