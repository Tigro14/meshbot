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

# Import cryptography for decryption of encrypted DM packets
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import base64
    CRYPTO_AVAILABLE = True
except ImportError:
    debug_print("⚠️ cryptography library not available - encrypted DM decryption disabled")
    CRYPTO_AVAILABLE = False

# Import protobuf for parsing decrypted packets
try:
    from meshtastic.protobuf import mesh_pb2, portnums_pb2
    PROTOBUF_AVAILABLE = True
except ImportError:
    debug_print("⚠️ meshtastic protobuf not available - encrypted DM decryption disabled")
    PROTOBUF_AVAILABLE = False

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
    
    def _get_channel_psk(self, channel_index=0, interface=None):
        """
        Get the PSK (Pre-Shared Key) for a specific channel.
        
        Returns the configured PSK from config.CHANNEL_0_PSK if set, otherwise
        returns the default Meshtastic PSK.
        
        The interface.localNode.channels[].settings.psk field doesn't contain the
        actual PSK bytes (it appears to be a configuration flag or index), so we
        rely on configuration instead.
        
        Args:
            channel_index: Channel index (default 0 for Primary channel)
            interface: Meshtastic interface object (unused for now)
            
        Returns:
            PSK bytes (16 bytes for AES-128)
        """
        # Try to get custom PSK from config
        custom_psk = globals().get('CHANNEL_0_PSK', None)
        
        if custom_psk:
            # Use custom PSK from configuration
            try:
                psk = base64.b64decode(custom_psk)
                debug_print(f"🔑 Using custom PSK from config for channel {channel_index} ({len(psk)} bytes)")
                return psk
            except Exception as e:
                error_print(f"Failed to decode custom PSK from config: {e}")
                debug_print("Falling back to default Meshtastic PSK")
        
        # Default Meshtastic channel 0 PSK (base64: "1PG7OiApB1nwvP+rz05pAQ==")
        # This is the same default used in mqtt_neighbor_collector.py
        # Reference: https://github.com/liamcottle/meshtastic-map/blob/main/src/mqtt.js#L658
        psk = base64.b64decode("1PG7OiApB1nwvP+rz05pAQ==")
        debug_print(f"🔑 Using default Meshtastic PSK for channel {channel_index} ({len(psk)} bytes)")
        return psk
    
    def _find_node_in_interface(self, node_id, interface):
        """
        Find node info in interface.nodes trying multiple key formats.
        
        Interface.nodes can store nodes with different key formats:
        - Integer: 2812625114
        - String: "2812625114"
        - Hex with prefix: "!a76f40da"
        - Hex without prefix: "a76f40da"
        
        This method tries all formats to find the node, matching the logic
        used by the /keys command for consistency.
        
        Args:
            node_id: Node ID as integer
            interface: Meshtastic interface object
            
        Returns:
            tuple: (node_info dict, matched_key) or (None, None) if not found
        """
        if not interface or not hasattr(interface, 'nodes'):
            return None, None
        
        nodes = getattr(interface, 'nodes', {})
        if not nodes:
            return None, None
        
        # Try multiple key formats
        search_keys = [
            node_id,                    # Integer format
            str(node_id),              # String decimal format
            f"!{node_id:08x}",         # Hex with "!" prefix
            f"{node_id:08x}"           # Hex without prefix
        ]
        
        for key in search_keys:
            if key in nodes:
                debug_print(f"🔍 Found node 0x{node_id:08x} in interface.nodes with key={key} (type={type(key).__name__})")
                return nodes[key], key
        
        return None, None
    
    def _try_decrypt_with_nonce(self, encrypted_bytes, psk, nonce, from_id, method_name):
        """
        Try to decrypt with a specific nonce construction.
        
        Args:
            encrypted_bytes: Encrypted data as bytes
            psk: Pre-Shared Key (16 bytes)
            nonce: Nonce to use (16 bytes for AES-CTR)
            from_id: Sender node ID (for logging)
            method_name: Name of the method (for logging)
            
        Returns:
            Decrypted Data protobuf object or None if decryption fails
        """
        try:
            # Create AES-128-CTR cipher
            cipher = Cipher(
                algorithms.AES(psk),
                modes.CTR(nonce),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Decrypt
            decrypted_bytes = decryptor.update(encrypted_bytes) + decryptor.finalize()
            
            # Debug: log decrypted data info
            debug_print(f"🔍 [{method_name}] Decrypted {len(decrypted_bytes)} bytes from 0x{from_id:08x}")
            if len(decrypted_bytes) > 0:
                # Show first few bytes in hex for debugging
                hex_preview = ' '.join(f'{b:02x}' for b in decrypted_bytes[:min(16, len(decrypted_bytes))])
                debug_print(f"🔍 [{method_name}] First bytes (hex): {hex_preview}")
            
            # Parse as Data protobuf - this will fail if wrong nonce/PSK
            decoded = mesh_pb2.Data()
            decoded.ParseFromString(decrypted_bytes)
            
            debug_print(f"✅ Successfully decrypted DM packet from 0x{from_id:08x} using {method_name}")
            return decoded
            
        except Exception as e:
            debug_print(f"❌ [{method_name}] Failed: {e}")
            return None
    
    def _decrypt_packet(self, encrypted_data, packet_id, from_id, channel_index=0, interface=None):
        """
        ⚠️ WARNING: This method is DEPRECATED and should NOT be used for Direct Messages (DMs).
        
        IMPORTANT INFORMATION:
        - Meshtastic 2.5.0+ uses PKI (Public Key Cryptography) for DMs, NOT channel PSK
        - The Meshtastic Python library automatically decrypts PKI DMs if keys are available
        - This PSK-based decryption only works for CHANNEL/BROADCAST messages
        - Attempting to decrypt PKI DMs with channel PSK produces garbage data
        
        If you see encrypted DMs, the issue is missing public key exchange, NOT wrong PSK.
        Fix: Ensure both nodes have each other's public keys (via NODEINFO_APP packets).
        
        This method is kept for potential future use with channel-encrypted broadcasts,
        but is NOT called for DM processing.
        
        ═══════════════════════════════════════════════════════════════════════════
        
        Decrypt an encrypted Meshtastic packet using AES-128-CTR with channel PSK.
        
        ⚠️ ONLY for channel/broadcast messages, NOT for Direct Messages!
        
        Encryption details:
        - Algorithm: AES-128-CTR
        - Key: Channel PSK (from interface or default "1PG7OiApB1nwvP+rz05pAQ==" base64)
        - Nonce: Varies by firmware version (tries multiple methods)
        
        Args:
            encrypted_data: Encrypted data from packet['encrypted'] (bytes or base64 string)
            packet_id: Packet ID (int)
            from_id: Sender node ID (int)
            channel_index: Channel index (default 0 for Primary channel)
            interface: Meshtastic interface (for accessing PSK configuration)
            
        Returns:
            Decrypted Data protobuf object or None if decryption fails
        """
        if not CRYPTO_AVAILABLE or not PROTOBUF_AVAILABLE:
            return None
        
        try:
            # Convert encrypted_data to bytes if it's a string (base64-encoded)
            # Meshtastic Python library may return encrypted field as base64 string
            if isinstance(encrypted_data, str):
                encrypted_bytes = base64.b64decode(encrypted_data)
            else:
                encrypted_bytes = encrypted_data
            
            # Get PSK
            psk = self._get_channel_psk(channel_index, interface=interface)
            
            # Try multiple decryption methods for compatibility with different firmware versions
            decryption_methods = []
            
            # Method 1: Meshtastic 2.7.15+ standard format
            # Nonce: packet_id (8 bytes LE) + from_id (4 bytes LE) + block_counter (4 zeros)
            nonce_2715 = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little') + b'\x00' * 4
            decryption_methods.append(("Meshtastic 2.7.15+", nonce_2715))
            
            # Method 2: Meshtastic 2.6.x alternative format (packet_id only)
            # Some older versions might use shorter packet ID
            try:
                nonce_26x_short = packet_id.to_bytes(4, 'little') + from_id.to_bytes(4, 'little') + b'\x00' * 8
                decryption_methods.append(("Meshtastic 2.6.x (short ID)", nonce_26x_short))
            except OverflowError:
                pass  # packet_id too large for 4 bytes
            
            # Method 3: Alternative nonce with big-endian encoding
            try:
                nonce_be = packet_id.to_bytes(8, 'big') + from_id.to_bytes(4, 'big') + b'\x00' * 4
                decryption_methods.append(("Big-endian variant", nonce_be))
            except OverflowError:
                pass
            
            # Method 4: Reversed order (from_id first, then packet_id)
            try:
                nonce_reversed = from_id.to_bytes(4, 'little') + packet_id.to_bytes(8, 'little') + b'\x00' * 4
                decryption_methods.append(("Reversed order", nonce_reversed))
            except OverflowError:
                pass
            
            # Try each decryption method
            for method_name, nonce in decryption_methods:
                result = self._try_decrypt_with_nonce(encrypted_bytes, psk, nonce, from_id, method_name)
                if result:
                    return result
            
            # All methods failed
            debug_print(f"⚠️ Failed to decrypt packet from 0x{from_id:08x} with all {len(decryption_methods)} methods")
            return None
            
        except Exception as e:
            debug_print(f"⚠️ Failed to decrypt packet from 0x{from_id:08x}: {e}")
            import traceback
            debug_print(f"🔍 Traceback: {traceback.format_exc()}")
            return None
    
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
    
    def add_packet(self, packet, source='unknown', my_node_id=None, interface=None):
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
            interface: Interface Meshtastic (for accessing PSK configuration)
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
                # Paquet chiffré
                is_encrypted = True
                packet_type = 'ENCRYPTED'
                
                # Check if packet is PKI encrypted (different encryption scheme)
                if 'pkiEncrypted' in packet:
                    packet_type = 'PKI_ENCRYPTED'
                
                # Note: Depuis Meshtastic 2.5.0+, les DMs utilisent PKI (Public Key Cryptography)
                # La bibliothèque Meshtastic Python décrypte automatiquement les DMs PKI si les clés sont échangées.
                # Si un DM arrive avec le champ 'encrypted', cela signifie que la bibliothèque ne peut pas le décrypter,
                # probablement parce que :
                #   - Le nœud récepteur n'a pas la clé publique de l'expéditeur
                #   - L'expéditeur n'a pas la clé publique du récepteur
                #   - L'échange de clés n'a pas eu lieu
                #
                # IMPORTANT: NE PAS essayer de décrypter avec PSK de canal !
                # - Les messages de canal/broadcast utilisent PSK
                # - Les DMs utilisent PKI (clés publiques/privées)
                # - Tenter de décrypter un DM PKI avec PSK produit des données invalides
                #
                # Solution: Garder le paquet comme ENCRYPTED et informer l'utilisateur
                # de vérifier l'échange de clés entre les nœuds
                
                is_dm_to_us = my_node_id and (to_id == my_node_id)
                
                if is_dm_to_us:
                    debug_print(f"🔐 Encrypted DM from 0x{from_id:08x} to us - likely PKI encrypted")
                    
                    # Check if we have sender's public key using multi-format search
                    has_key = False
                    public_key = None
                    matched_key_format = None
                    
                    interface = getattr(self.node_manager, 'interface', None)
                    if interface:
                        # Use helper method to find node with multiple key formats
                        node_info, matched_key_format = self._find_node_in_interface(from_id, interface)
                        
                        if node_info and isinstance(node_info, dict):
                            user_info = node_info.get('user', {})
                            if isinstance(user_info, dict):
                                # Try both field names: 'public_key' (protobuf) and 'publicKey' (dict)
                                public_key = user_info.get('public_key') or user_info.get('publicKey')
                                if public_key:
                                    has_key = True
                    
                    if not has_key:
                        debug_print(f"❌ Missing public key for sender 0x{from_id:08x}")
                        debug_print(f"💡 Solution: The sender's node needs to broadcast NODEINFO")
                        debug_print(f"   - Wait for automatic NODEINFO broadcast (every 15-30 min)")
                        debug_print(f"   - Or manually request: meshtastic --request-telemetry --dest {from_id:08x}")
                        debug_print(f"   - Or use: /keys {from_id:08x} to check key exchange status")
                    else:
                        key_preview = public_key[:16] if isinstance(public_key, str) else f"{len(public_key)} bytes"
                        debug_print(f"✅ Sender's public key FOUND (matched with key format: {matched_key_format})")
                        debug_print(f"   Key preview: {key_preview}...")
                        debug_print(f"⚠️ Yet Meshtastic library couldn't decrypt - PKI encryption issue!")
                        debug_print(f"   This is PKI (public key) encryption, not channel PSK encryption.")
                        debug_print(f"   ")
                        debug_print(f"   💡 Most likely cause: The SENDER doesn't have YOUR public key")
                        debug_print(f"   ")
                        debug_print(f"   How PKI encryption works:")
                        debug_print(f"   • To SEND encrypted DM to you: Sender needs YOUR public key")
                        debug_print(f"   • To READ encrypted DM from sender: You need SENDER's public key (✅ you have it)")
                        debug_print(f"   ")
                        debug_print(f"   📋 Solution:")
                        debug_print(f"   1. Your node needs to broadcast NODEINFO (with your public key)")
                        debug_print(f"   2. Sender's node must receive your NODEINFO packet")
                        debug_print(f"   3. Then sender can encrypt DMs to you properly")
                        debug_print(f"   ")
                        debug_print(f"   🔍 Check if sender has your key:")
                        debug_print(f"      Ask sender to run: /keys [your_node_name]")
                        debug_print(f"      Should show: ✅ Clé publique: PRÉSENTE")
                        debug_print(f"   ")
                        debug_print(f"   Other possible causes (less likely):")
                        debug_print(f"   • Firmware incompatibility (sender or receiver < 2.5.0)")
                        debug_print(f"   • Key exchange incomplete (wait for NODEINFO broadcast)")
                    
                    debug_print(f"📖 More info: https://meshtastic.org/docs/overview/encryption/")
                else:
                    debug_print(f"🔐 Encrypted packet not for us (to=0x{to_id:08x})")
        
            # Obtenir le nom du nœud
            sender_name = self.node_manager.get_node_name(from_id)
            
            # Calculer la taille approximative du paquet
            packet_size = len(str(packet))
            
            # Calculer les hops
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 5)
            hops_taken = hop_start - hop_limit
            
            # === EXTRACTION MÉTADONNÉES SUPPLÉMENTAIRES ===
            # Extract additional routing metadata for DEBUG mode and SQLite
            channel = packet.get('channel', 0)  # Channel index (0-7)
            via_mqtt = packet.get('viaMqtt', False)  # Whether via MQTT gateway
            want_ack = packet.get('wantAck', False)  # Sender wants acknowledgment
            want_response = packet.get('wantResponse', False)  # Sender expects response
            priority = packet.get('priority', 0)  # Priority level (0=default, 32=ACK_REQ, 64=RELIABLE, 100=CRITICAL)
            
            # Determine packet family (FLOOD = broadcast, DIRECT = unicast)
            is_broadcast = to_id in [0xFFFFFFFF, 0]
            family = 'FLOOD' if is_broadcast else 'DIRECT'
            
            # Extract public key from sender's node info (if available from NODEINFO_APP)
            public_key = self._get_sender_public_key(from_id, interface)
            
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
                'hop_limit': hop_limit,
                'hop_start': hop_start,
                'size': packet_size,
                'is_broadcast': is_broadcast,
                'is_encrypted': is_encrypted,
                # NEW: Additional routing metadata
                'channel': channel,
                'via_mqtt': via_mqtt,
                'want_ack': want_ack,
                'want_response': want_response,
                'priority': priority,
                'family': family,
                'public_key': public_key
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

            # Capturer les positions GPS (AVANT la sauvegarde du paquet)
            if packet_entry['packet_type'] == 'POSITION_APP':
                if packet and 'decoded' in packet:
                    decoded = packet['decoded']
                    if 'position' in decoded:
                        position = decoded['position']
                        lat = position.get('latitude')
                        lon = position.get('longitude')
                        alt = position.get('altitude')

                        if lat is not None and lon is not None:
                            # Ajouter la position au packet_entry pour la sauvegarde DB
                            packet_entry['position'] = {
                                'latitude': lat,
                                'longitude': lon,
                                'altitude': alt
                            }
                            # Mise à jour du node_manager (en mémoire)
                            self.node_manager.update_node_position(from_id, lat, lon, alt)
                            debug_print(f"📍 Position capturée: {from_id:08x} -> {lat:.5f}, {lon:.5f}")

            self.all_packets.append(packet_entry)

            # Log périodique des paquets enregistrés (tous les 25 paquets)
            if not hasattr(self, '_packet_saved_count'):
                self._packet_saved_count = 0
            self._packet_saved_count += 1
            if self._packet_saved_count % 25 == 0:
                logger.info(f"💾 {self._packet_saved_count} paquets enregistrés dans all_packets (size: {len(self.all_packets)})")

            # Sauvegarder le paquet dans SQLite
            # IMPORTANT: Séparer les paquets MeshCore des paquets Meshtastic
            try:
                packet_source = packet_entry.get('source', 'unknown')
                
                if packet_source == 'meshcore':
                    # Paquet MeshCore → table meshcore_packets
                    self.persistence.save_meshcore_packet(packet_entry)
                    logger.debug(f"📦 Paquet MeshCore sauvegardé: {packet_type} de {sender_name}")
                else:
                    # Paquet Meshtastic (local, tcp, tigrog2) → table packets
                    self.persistence.save_packet(packet_entry)
                    logger.debug(f"📡 Paquet Meshtastic sauvegardé: {packet_type} de {sender_name}")
                    
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde du paquet : {e}")

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
        Log debug unifié pour tous les types de paquets avec affichage complet
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
            
            # === AFFICHAGE COMPLET MESHCORE (comprehensive debug) ===
            self._log_comprehensive_packet_debug(packet, packet_type, sender_name, from_id, snr, hops_taken)

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

    def _log_comprehensive_packet_debug(self, packet, packet_type, sender_name, from_id, snr, hops_taken):
        """
        Affichage complet et détaillé du paquet Meshcore pour debug approfondi
        """
        try:
            # === SECTION 1: IDENTITÉ DU PAQUET ===
            packet_id = packet.get('id', 'N/A')
            rx_time = packet.get('rxTime', 0)
            rx_time_str = datetime.fromtimestamp(rx_time).strftime('%H:%M:%S') if rx_time else 'N/A'
            
            debug_print(f"╔═══════════════════════════════════════════════════════════════")
            debug_print(f"║ 📦 MESHCORE PACKET DEBUG - {packet_type}")
            debug_print(f"╠═══════════════════════════════════════════════════════════════")
            debug_print(f"║ Packet ID: {packet_id}")
            debug_print(f"║ RX Time:   {rx_time_str} ({rx_time})")
            
            # === SECTION 2: ROUTAGE ===
            to_id = packet.get('to', 0)
            to_id_hex = f"0x{to_id:08x}"
            from_id_hex = f"0x{from_id:08x}"
            is_broadcast = to_id in [0xFFFFFFFF, 0]
            
            debug_print(f"╟───────────────────────────────────────────────────────────────")
            debug_print(f"║ 🔀 ROUTING")
            debug_print(f"║   From:      {sender_name} ({from_id_hex})")
            debug_print(f"║   To:        {'BROADCAST' if is_broadcast else to_id_hex}")
            
            # Hop information
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 0)
            hops_taken_calc = hop_start - hop_limit if hop_start > 0 else 0
            
            debug_print(f"║   Hops:      {hops_taken_calc}/{hop_start} (limit: {hop_limit})")
            
            if hops_taken_calc > 0:
                suspected_relay = self._guess_relay_node(snr, from_id)
                if suspected_relay:
                    debug_print(f"║   Via:       {suspected_relay} (suspected)")
            
            # === NEW SECTION: PACKET METADATA (Family, Channel, Flags, Priority, PublicKey) ===
            debug_print(f"╟───────────────────────────────────────────────────────────────")
            debug_print(f"║ 📋 PACKET METADATA")
            
            # Family (FLOOD/DIRECT)
            family = 'FLOOD' if is_broadcast else 'DIRECT'
            family_desc = 'broadcast' if is_broadcast else 'unicast'
            debug_print(f"║   Family:    {family} ({family_desc})")
            
            # Channel
            channel = packet.get('channel', 0)
            channel_name = "Primary" if channel == 0 else f"Ch{channel}"
            debug_print(f"║   Channel:   {channel} ({channel_name})")
            
            # Priority
            priority = packet.get('priority', 0)
            priority_map = {
                100: 'CRITICAL',
                64: 'RELIABLE', 
                32: 'ACK_REQ',
                0: 'DEFAULT'
            }
            priority_name = priority_map.get(priority, f'CUSTOM({priority})')
            debug_print(f"║   Priority:  {priority_name} ({priority})")
            
            # Flags
            via_mqtt = packet.get('viaMqtt', False)
            want_ack = packet.get('wantAck', False)
            want_response = packet.get('wantResponse', False)
            debug_print(f"║   Via MQTT:  {'Yes' if via_mqtt else 'No'}")
            debug_print(f"║   Want ACK:  {'Yes' if want_ack else 'No'}")
            debug_print(f"║   Want Resp: {'Yes' if want_response else 'No'}")
            
            # Public Key (from sender's NODEINFO)
            public_key = self._get_sender_public_key(from_id, getattr(self, 'node_manager', None) and getattr(self.node_manager, 'interface', None))
            if public_key:
                key_preview = public_key[:16] if len(public_key) > 16 else public_key
                key_length = len(public_key) if isinstance(public_key, str) else 0
                debug_print(f"║   PublicKey: {key_preview}... ({key_length} chars)")
            else:
                debug_print(f"║   PublicKey: Not available")
            
            # === SECTION 3: RADIO METRICS ===
            rssi = packet.get('rssi', packet.get('rxRssi', 0))
            snr_value = packet.get('snr', packet.get('rxSnr', 0.0))
            
            # Visual indicators for signal quality
            if snr_value >= 10:
                snr_indicator = "🟢 Excellent"
            elif snr_value >= 5:
                snr_indicator = "🟡 Good"
            elif snr_value >= 0:
                snr_indicator = "🟠 Fair"
            else:
                snr_indicator = "🔴 Poor"
            
            debug_print(f"╟───────────────────────────────────────────────────────────────")
            debug_print(f"║ 📡 RADIO METRICS")
            debug_print(f"║   RSSI:      {rssi} dBm")
            debug_print(f"║   SNR:       {snr_value:.1f} dB ({snr_indicator})")
            
            # === SECTION 4: CONTENU DÉCODÉ ===
            debug_print(f"╟───────────────────────────────────────────────────────────────")
            debug_print(f"║ 📄 DECODED CONTENT")
            
            if 'decoded' in packet:
                decoded = packet['decoded']
                
                # TEXT_MESSAGE_APP
                if packet_type == 'TEXT_MESSAGE_APP':
                    text = decoded.get('text', '')
                    if not text:
                        try:
                            payload = decoded.get('payload', b'')
                            text = payload.decode('utf-8') if payload else ''
                        except:
                            text = '<decode error>'
                    debug_print(f"║   Message:   \"{text}\"")
                
                # POSITION_APP
                elif packet_type == 'POSITION_APP':
                    if 'position' in decoded:
                        pos = decoded['position']
                        lat = pos.get('latitude', 0) / 1e7 if 'latitude' in pos else pos.get('latitudeI', 0) / 1e7
                        lon = pos.get('longitude', 0) / 1e7 if 'longitude' in pos else pos.get('longitudeI', 0) / 1e7
                        alt = pos.get('altitude', 'N/A')
                        debug_print(f"║   Latitude:  {lat:.6f}°")
                        debug_print(f"║   Longitude: {lon:.6f}°")
                        if alt != 'N/A':
                            debug_print(f"║   Altitude:  {alt} m")
                
                # TELEMETRY_APP
                elif packet_type == 'TELEMETRY_APP':
                    if 'telemetry' in decoded:
                        telem = decoded['telemetry']
                        
                        # Device Metrics
                        if 'deviceMetrics' in telem:
                            metrics = telem['deviceMetrics']
                            debug_print(f"║   Device Metrics:")
                            if 'batteryLevel' in metrics:
                                debug_print(f"║     Battery:      {metrics['batteryLevel']}%")
                            if 'voltage' in metrics:
                                debug_print(f"║     Voltage:      {metrics['voltage']:.2f}V")
                            if 'channelUtilization' in metrics:
                                debug_print(f"║     Channel Util: {metrics['channelUtilization']}%")
                            if 'airUtilTx' in metrics:
                                debug_print(f"║     Air Util TX:  {metrics['airUtilTx']}%")
                            if 'uptimeSeconds' in metrics:
                                uptime = metrics['uptimeSeconds']
                                hours = uptime // 3600
                                minutes = (uptime % 3600) // 60
                                debug_print(f"║     Uptime:       {hours}h {minutes}m")
                        
                        # Environment Metrics
                        if 'environmentMetrics' in telem:
                            env = telem['environmentMetrics']
                            debug_print(f"║   Environment Metrics:")
                            if 'temperature' in env:
                                debug_print(f"║     Temperature:  {env['temperature']:.1f}°C")
                            if 'relativeHumidity' in env:
                                debug_print(f"║     Humidity:     {env['relativeHumidity']:.1f}%")
                            if 'barometricPressure' in env:
                                debug_print(f"║     Pressure:     {env['barometricPressure']:.1f} hPa")
                
                # NODEINFO_APP
                elif packet_type == 'NODEINFO_APP':
                    if 'user' in decoded:
                        user = decoded['user']
                        debug_print(f"║   Long Name:  {user.get('longName', 'N/A')}")
                        debug_print(f"║   Short Name: {user.get('shortName', 'N/A')}")
                        debug_print(f"║   Hardware:   {user.get('hwModel', 'N/A')}")
                
                # NEIGHBORINFO_APP
                elif packet_type == 'NEIGHBORINFO_APP':
                    if 'neighborinfo' in decoded:
                        neighbors = decoded['neighborinfo'].get('neighbors', [])
                        debug_print(f"║   Neighbors:  {len(neighbors)} node(s)")
                        for i, neighbor in enumerate(neighbors[:5]):  # Limit to first 5
                            neighbor_id = neighbor.get('nodeId', 0)
                            neighbor_snr = neighbor.get('snr', 0)
                            debug_print(f"║     [{i+1}] 0x{neighbor_id:08x} SNR:{neighbor_snr:.1f}dB")
                        if len(neighbors) > 5:
                            debug_print(f"║     ... and {len(neighbors)-5} more")
                
                # TRACEROUTE_APP
                elif packet_type == 'TRACEROUTE_APP':
                    if 'route' in decoded:
                        route = decoded['route']
                        route_list = route.get('route', [])
                        debug_print(f"║   Route:      {' -> '.join([f'0x{node:08x}' for node in route_list])}")
                
                # Generic portnum display
                portnum = decoded.get('portnum', 'UNKNOWN')
                if portnum not in ['TEXT_MESSAGE_APP', 'POSITION_APP', 'TELEMETRY_APP', 
                                   'NODEINFO_APP', 'NEIGHBORINFO_APP', 'TRACEROUTE_APP']:
                    debug_print(f"║   Portnum:    {portnum}")
            
            # === SECTION 5: ENCRYPTION STATUS ===
            if 'encrypted' in packet or packet_type in ['ENCRYPTED', 'PKI_ENCRYPTED']:
                debug_print(f"╟───────────────────────────────────────────────────────────────")
                debug_print(f"║ 🔐 ENCRYPTION")
                if packet_type == 'PKI_ENCRYPTED':
                    debug_print(f"║   Type:       PKI (Public Key)")
                else:
                    debug_print(f"║   Type:       Channel PSK")
                
                encrypted_size = len(packet.get('encrypted', b''))
                if encrypted_size > 0:
                    debug_print(f"║   Size:       {encrypted_size} bytes")
            
            # === SECTION 6: PACKET SIZE ===
            # Calculate approximate packet size
            packet_size = 0
            if 'decoded' in packet:
                decoded = packet['decoded']
                if 'payload' in decoded:
                    packet_size = len(decoded['payload'])
                elif 'text' in decoded:
                    packet_size = len(decoded['text'].encode('utf-8'))
            elif 'encrypted' in packet:
                packet_size = len(packet['encrypted'])
            
            if packet_size > 0:
                debug_print(f"╟───────────────────────────────────────────────────────────────")
                debug_print(f"║ 📊 PACKET SIZE")
                debug_print(f"║   Payload:    {packet_size} bytes")
            
            debug_print(f"╚═══════════════════════════════════════════════════════════════")
            
        except Exception as e:
            import traceback
            debug_print(f"❌ Error in comprehensive packet debug: {e}")
            debug_print(traceback.format_exc())

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

    def _get_sender_public_key(self, from_id, interface):
        """
        Get the sender's public key from node info (if available from previous NODEINFO_APP)
        
        Args:
            from_id: Sender node ID
            interface: Meshtastic interface
            
        Returns:
            str or None: Public key in base64 format, or None if not available
        """
        try:
            if not interface or not hasattr(interface, 'nodes'):
                return None
            
            # Use helper method to find node with multiple key formats
            node_info, matched_key_format = self._find_node_in_interface(from_id, interface)
            
            if not node_info or not isinstance(node_info, dict):
                return None
            
            user_info = node_info.get('user', {})
            if not isinstance(user_info, dict):
                return None
            
            # Try both field names: 'public_key' (protobuf) and 'publicKey' (dict)
            public_key = user_info.get('public_key') or user_info.get('publicKey')
            
            # Return base64 string if available
            if public_key:
                if isinstance(public_key, bytes):
                    import base64
                    return base64.b64encode(public_key).decode('ascii')
                elif isinstance(public_key, str):
                    return public_key
            
            return None
        except Exception as e:
            logger.debug(f"Error getting public key for node {from_id:08x}: {e}")
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
                    
                    # Device metrics (battery, voltage, channel utilization)
                    if 'deviceMetrics' in telemetry:
                        metrics = telemetry['deviceMetrics']
                        tel_stats['last_battery'] = metrics.get('batteryLevel')
                        tel_stats['last_voltage'] = metrics.get('voltage')
                        tel_stats['last_channel_util'] = metrics.get('channelUtilization')
                        tel_stats['last_air_util'] = metrics.get('airUtilTx')
                    
                    # Environment metrics (temperature, humidity, pressure, air quality)
                    if 'environmentMetrics' in telemetry:
                        env_metrics = telemetry['environmentMetrics']
                        tel_stats['last_temperature'] = env_metrics.get('temperature')
                        tel_stats['last_humidity'] = env_metrics.get('relativeHumidity')
                        tel_stats['last_pressure'] = env_metrics.get('barometricPressure')
                        tel_stats['last_air_quality'] = env_metrics.get('iaq')
        
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
        Pour Telegram: inclut aussi les données de canal (channel_util et air_util)
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
                'name': '',
                'channel_utils': [],  # Pour calculer moyenne canal%
                'air_utils': []  # Pour calculer moyenne Air TX
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
                        # Collecter les données de canal pour Telegram (uniquement depuis TELEMETRY_APP)
                        if include_packet_types and packet.get('telemetry'):
                            telemetry = packet['telemetry']
                            if telemetry.get('channel_util') is not None:
                                stats['channel_utils'].append(telemetry['channel_util'])
                            if telemetry.get('air_util') is not None:
                                stats['air_utils'].append(telemetry['air_util'])
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
                name = truncate_text(stats['name'], 35)
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
                
                # Temps depuis dernier paquet
                time_str = format_elapsed_time(stats['last_seen'])
                lines.append(f"\n{icon} {name} {time_str} ago")
                # Taille des données
                if stats['bytes'] > 1024:
                    lines.append(f" 📦 {packet_count} paquets ({percentage:.1f}%)  {stats['bytes']/1024:.1f}KB")
                else:
                    lines.append(f" 📦 {packet_count} paquets ({percentage:.1f}%)  {stats['bytes']}B")
                
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
                    
                    # Ajouter les données de canal (Channel% et Air TX) uniquement pour Telegram
                    # Vérifier que les listes ne sont pas vides avant de calculer les moyennes
                    if include_packet_types and (stats['channel_utils'] or stats['air_utils']):
                        channel_line_parts = []
                        if stats['channel_utils']:
                            avg_channel = sum(stats['channel_utils']) / len(stats['channel_utils'])
                            channel_line_parts.append(f"Canal: {avg_channel:.1f}%")
                        if stats['air_utils']:
                            avg_air = sum(stats['air_utils']) / len(stats['air_utils'])
                            if avg_air > 0.2:
                                channel_line_parts.append(f"Air TX: {avg_air:.1f}%")
                        if channel_line_parts:
                            lines.append(f"   📡 {' | '.join(channel_line_parts)}")
                
                
            
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
                    # Utiliser -999 si SNR est None ou absent
                    sorted_neighbors = sorted(
                        neighbors,
                        key=lambda x: x.get('snr') if x.get('snr') is not None else -999,
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
    
    def get_propagation_report(self, hours=24, top_n=5, max_distance_km=100, compact=True):
        """
        Générer un rapport des plus longues liaisons radio.
        
        Args:
            hours: Nombre d'heures à analyser (défaut: 24)
            top_n: Nombre de liaisons à afficher (défaut: 5)
            max_distance_km: Distance maximale depuis le bot (défaut: 100km)
            compact: Format compact pour LoRa (180 chars) ou détaillé pour Telegram
            
        Returns:
            Rapport formaté des plus longues liaisons radio
        """
        try:
            # Charger les liaisons radio depuis la DB
            links = self.persistence.load_radio_links_with_positions(hours=hours)
            
            debug_print(f"📊 /propag: {len(links)} liaisons chargées depuis la DB (dernières {hours}h)")
            
            if not links:
                return "❌ Aucune donnée de liaison radio disponible"
            
            # Obtenir la position de référence (bot)
            ref_pos = self.node_manager.get_reference_position()
            debug_print(f"📍 Position de référence du bot: {ref_pos}")
            
            # Calculer les distances pour chaque liaison
            links_with_distance = []
            
            for link in links:
                from_id_db = link['from_id']  # Original database ID (string format)
                to_id_db = link['to_id']      # Original database ID (string format)
                
                # Convertir les IDs en entiers pour node_manager
                from_id = from_id_db
                to_id = to_id_db
                
                try:
                    if isinstance(from_id, str):
                        if from_id.startswith('!'):
                            from_id = int(from_id[1:], 16)
                        else:
                            from_id = int(from_id)  # Decimal string from database
                    if isinstance(to_id, str):
                        if to_id.startswith('!'):
                            to_id = int(to_id[1:], 16)
                        else:
                            to_id = int(to_id)  # Decimal string from database
                except (ValueError, AttributeError):
                    continue
                
                # Obtenir les positions des nœuds - d'abord depuis la DB, puis depuis node_manager
                from_lat = None
                from_lon = None
                from_alt = None
                to_lat = None
                to_lon = None
                to_alt = None
                
                # Essayer d'obtenir la position depuis la base de données (30 jours de rétention)
                # Utiliser les IDs au format original de la DB
                debug_print(f"🔍 Recherche GPS pour liaison: {from_id_db} → {to_id_db}")
                from_pos_db = self.persistence.get_node_position_from_db(from_id_db, hours=720)
                to_pos_db = self.persistence.get_node_position_from_db(to_id_db, hours=720)
                
                if from_pos_db:
                    from_lat = from_pos_db.get('latitude')
                    from_lon = from_pos_db.get('longitude')
                    from_alt = from_pos_db.get('altitude')
                    #debug_print(f"  ✅ FROM DB: {from_id_db} = ({from_lat}, {from_lon}, {from_alt}m)")
                
                if to_pos_db:
                    to_lat = to_pos_db.get('latitude')
                    to_lon = to_pos_db.get('longitude')
                    to_alt = to_pos_db.get('altitude')
                    #debug_print(f"  ✅ TO DB: {to_id_db} = ({to_lat}, {to_lon}, {to_alt}m)")
                
                # Si pas trouvé dans la DB, essayer depuis node_manager (mémoire)
                if not (from_lat and from_lon):
                    from_data = self.node_manager.get_node_data(from_id)
                    if from_data:
                        from_lat = from_data.get('latitude')
                        from_lon = from_data.get('longitude')
                        from_alt = from_data.get('altitude')
                        #debug_print(f"  ✅ FROM MEM: {from_id} = ({from_lat}, {from_lon}, {from_alt}m)")
                    #else:
                        #debug_print(f"  ❌ FROM: Aucune position trouvée pour {from_id_db}")
                
                if not (to_lat and to_lon):
                    to_data = self.node_manager.get_node_data(to_id)
                    if to_data:
                        to_lat = to_data.get('latitude')
                        to_lon = to_data.get('longitude')
                        to_alt = to_data.get('altitude')
                        #debug_print(f"  ✅ TO MEM: {to_id} = ({to_lat}, {to_lon}, {to_alt}m)")
                    #else:
                        #debug_print(f"  ❌ TO: Aucune position trouvée pour {to_id_db}")
                
                # Vérifier que les deux nœuds ont des positions GPS
                if not all([from_lat, from_lon, to_lat, to_lon]):
                    #debug_print(f"  ⚠️ SKIP: Position GPS manquante (from: {from_lat},{from_lon}, to: {to_lat},{to_lon})")
                    continue
                
                # Calculer la distance de la liaison
                distance_km = self.node_manager.haversine_distance(
                    from_lat, from_lon, to_lat, to_lon
                )
                
                # Filtrer par distance depuis le bot si position de référence disponible
                if ref_pos and ref_pos[0] != 0 and ref_pos[1] != 0:
                    ref_lat, ref_lon = ref_pos
                    
                    # Distance du nœud FROM au bot
                    from_distance = self.node_manager.haversine_distance(
                        ref_lat, ref_lon, from_lat, from_lon
                    )
                    # Distance du nœud TO au bot
                    to_distance = self.node_manager.haversine_distance(
                        ref_lat, ref_lon, to_lat, to_lon
                    )
                    
                    debug_print(f"  📏 Distances au bot: FROM={from_distance:.1f}km, TO={to_distance:.1f}km (max={max_distance_km}km)")
                    
                    # Filtrer si AUCUN des deux nœuds n'est dans le rayon
                    # (on garde la liaison si au moins un nœud est dans le rayon)
                    if from_distance > max_distance_km and to_distance > max_distance_km:
                        debug_print(f"  ⚠️ SKIP: Aucun nœud dans le rayon de {max_distance_km}km")
                        continue
                
                # Obtenir les noms des nœuds - utiliser les IDs entiers pour la recherche
                # get_node_name() attend un int, pas une string hex
                # Passer l'interface pour permettre la recherche en temps réel
                from_name = self.node_manager.get_node_name(from_id, self.node_manager.interface)
                to_name = self.node_manager.get_node_name(to_id, self.node_manager.interface)
                
                debug_print(f"  ✅ LIAISON VALIDE: {from_name} ↔ {to_name} ({distance_km:.1f}km)")
                
                links_with_distance.append({
                    'from_id': from_id,
                    'to_id': to_id,
                    'from_name': from_name,
                    'to_name': to_name,
                    'from_alt': from_alt if from_alt is not None else 0,
                    'to_alt': to_alt if to_alt is not None else 0,
                    'distance_km': distance_km,
                    'snr': link.get('snr'),
                    'rssi': link.get('rssi'),
                    'timestamp': link.get('timestamp')
                })
            
            debug_print(f"📊 Total liaisons valides avec GPS: {len(links_with_distance)}")
            
            if not links_with_distance:
                return "❌ Aucune liaison radio avec GPS dans le rayon configuré"
            
            # Déduplication par paire (from_id, to_id)
            # Conserver uniquement le meilleur lien pour chaque paire de nœuds
            unique_links = {}
            for link in links_with_distance:
                # Créer une clé unique pour la paire de nœuds (bidirectionnelle)
                # Trier les IDs pour que A→B et B→A soient considérés comme la même liaison
                pair_key = tuple(sorted([link['from_id'], link['to_id']]))
                
                # Si cette paire n'existe pas encore, ou si ce lien a un meilleur signal
                if pair_key not in unique_links:
                    unique_links[pair_key] = link
                else:
                    # Comparer et garder le meilleur lien (priorité: distance > SNR > timestamp)
                    existing = unique_links[pair_key]
                    
                    # Critère 1: Même distance (devrait être le cas pour une paire)
                    # Critère 2: Meilleur SNR (plus élevé = meilleur)
                    # Critère 3: Plus récent (timestamp plus grand)
                    
                    replace = False
                    if link['snr'] is not None and existing['snr'] is not None:
                        if link['snr'] > existing['snr']:
                            replace = True
                    elif link['snr'] is not None and existing['snr'] is None:
                        replace = True
                    elif link['timestamp'] > existing['timestamp']:
                        replace = True
                    
                    if replace:
                        unique_links[pair_key] = link
            
            # Convertir le dictionnaire en liste
            links_with_distance = list(unique_links.values())
            debug_print(f"📊 Liaisons uniques après déduplication: {len(links_with_distance)}")
            
            # Trier par distance décroissante
            links_with_distance.sort(key=lambda x: x['distance_km'], reverse=True)
            
            # Prendre les top N
            top_links = links_with_distance[:top_n]
            
            # Formater le rapport
            if compact:
                # Format compact pour LoRa (180 chars max)
                lines = [f"📡 Top {len(top_links)} liaisons ({hours}h):"]
                for i, link in enumerate(top_links, 1):
                    dist = self.node_manager.format_distance(link['distance_km'])
                    snr_str = f"SNR:{link['snr']:.0f}" if link['snr'] else ""
                    # Format ultra-compact: "1.A→B 45km SNR:8"
                    from_short = link['from_name'].split('-')[0][:6]  # Tronquer le nom
                    to_short = link['to_name'].split('-')[0][:6]
                    lines.append(f"{i}.{from_short}→{to_short} {dist} {snr_str}")
                
                # Ajouter le record 30j en compact
                try:
                    record_links = self.persistence.load_radio_links_with_positions(hours=30*24)
                    record_distance = 0
                    
                    for link in record_links:
                        from_id_db = link['from_id']  # Original DB format
                        to_id_db = link['to_id']      # Original DB format
                        
                        # Convertir pour node_manager
                        from_id = from_id_db
                        to_id = to_id_db
                        
                        try:
                            if isinstance(from_id, str):
                                if from_id.startswith('!'):
                                    from_id = int(from_id[1:], 16)
                                else:
                                    from_id = int(from_id)  # Decimal string from database
                            if isinstance(to_id, str):
                                if to_id.startswith('!'):
                                    to_id = int(to_id[1:], 16)
                                else:
                                    to_id = int(to_id)  # Decimal string from database
                        except (ValueError, AttributeError):
                            continue
                        
                        # Obtenir les positions depuis la DB ou node_manager
                        from_lat = None
                        from_lon = None
                        to_lat = None
                        to_lon = None
                        
                        # Utiliser les IDs au format DB original
                        from_pos_db = self.persistence.get_node_position_from_db(from_id_db, hours=720)
                        to_pos_db = self.persistence.get_node_position_from_db(to_id_db, hours=720)
                        
                        if from_pos_db:
                            from_lat = from_pos_db.get('latitude')
                            from_lon = from_pos_db.get('longitude')
                        
                        if to_pos_db:
                            to_lat = to_pos_db.get('latitude')
                            to_lon = to_pos_db.get('longitude')
                        
                        # Fallback to node_manager if not in DB
                        if not (from_lat and from_lon):
                            from_data = self.node_manager.get_node_data(from_id)
                            if from_data:
                                from_lat = from_data.get('latitude')
                                from_lon = from_data.get('longitude')
                        
                        if not (to_lat and to_lon):
                            to_data = self.node_manager.get_node_data(to_id)
                            if to_data:
                                to_lat = to_data.get('latitude')
                                to_lon = to_data.get('longitude')
                        
                        if not all([from_lat, from_lon, to_lat, to_lon]):
                            continue
                        
                        distance = self.node_manager.haversine_distance(from_lat, from_lon, to_lat, to_lon)
                        if distance > record_distance:
                            record_distance = distance
                    
                    if record_distance > 0:
                        lines.append(f"🏆 Record 30j: {self.node_manager.format_distance(record_distance)}")
                
                except Exception:
                    pass  # Ignore errors in compact mode
                
                # Joindre en une ligne pour rester sous 180 chars
                result = " | ".join(lines)
                if len(result) > 180:
                    # Si trop long, réduire encore (sans record)
                    lines = [f"📡 Top {len(top_links)} ({hours}h):"]
                    for i, link in enumerate(top_links, 1):
                        dist = self.node_manager.format_distance(link['distance_km'])
                        lines.append(f"{i}.{dist}")
                    result = " | ".join(lines)
                
                return result
            else:
                # Format détaillé pour Telegram
                lines = [
                    f"📡 **Top {len(top_links)} liaisons radio** (dernières {hours}h)",
                    f"🎯 Rayon maximum: {max_distance_km}km",
                    ""
                ]
                
                for i, link in enumerate(top_links, 1):
                    dist_str = self.node_manager.format_distance(link['distance_km'])
                    
                    lines.append(f"#{i} - {dist_str}")
                    
                    # Node FROM with altitude
                    from_info = f"   {link['from_name']}"
                    if link.get('from_alt') is not None:
                        from_info += f" - Alt: {int(link['from_alt'])}m"
                    lines.append(from_info)
                    
                    # Node TO with altitude
                    to_info = f"   {link['to_name']}"
                    if link.get('to_alt') is not None:
                        to_info += f" - Alt: {int(link['to_alt'])}m"
                    lines.append(to_info)
                    
                    # Signal quality
                    if link['snr']:
                        lines.append(f"   📊 SNR: {link['snr']:.1f} dB")
                    if link['rssi']:
                        lines.append(f"   📶 RSSI: {link['rssi']} dBm")
                    
                    # Timestamp
                    if link['timestamp']:
                        from datetime import datetime
                        dt = datetime.fromtimestamp(link['timestamp'])
                        lines.append(f"   🕐 {dt.strftime('%d/%m %H:%M')}")
                    
                    lines.append("")
                
                # Statistiques
                avg_distance = sum(l['distance_km'] for l in top_links) / len(top_links)
                lines.append(f"📊 Distance moyenne: {self.node_manager.format_distance(avg_distance)}")
                lines.append(f"📈 Total liaisons analysées: {len(links_with_distance)}")
                
                # Record de distance sur 30 jours
                try:
                    record_links = self.persistence.load_radio_links_with_positions(hours=30*24)  # 30 jours
                    record_distance = 0
                    record_link = None
                    
                    for link in record_links:
                        from_id_db = link['from_id']  # Original DB format
                        to_id_db = link['to_id']      # Original DB format
                        
                        # Convertir les IDs pour node_manager
                        from_id = from_id_db
                        to_id = to_id_db
                        
                        try:
                            if isinstance(from_id, str):
                                if from_id.startswith('!'):
                                    from_id = int(from_id[1:], 16)
                                else:
                                    from_id = int(from_id)  # Decimal string from database
                            if isinstance(to_id, str):
                                if to_id.startswith('!'):
                                    to_id = int(to_id[1:], 16)
                                else:
                                    to_id = int(to_id)  # Decimal string from database
                        except (ValueError, AttributeError):
                            continue
                        
                        # Obtenir les positions depuis la DB ou node_manager
                        from_lat = None
                        from_lon = None
                        to_lat = None
                        to_lon = None
                        
                        # Utiliser les IDs au format DB original
                        from_pos_db = self.persistence.get_node_position_from_db(from_id_db, hours=720)
                        to_pos_db = self.persistence.get_node_position_from_db(to_id_db, hours=720)
                        
                        if from_pos_db:
                            from_lat = from_pos_db.get('latitude')
                            from_lon = from_pos_db.get('longitude')
                        
                        if to_pos_db:
                            to_lat = to_pos_db.get('latitude')
                            to_lon = to_pos_db.get('longitude')
                        
                        # Fallback to node_manager if not in DB
                        if not (from_lat and from_lon):
                            from_data = self.node_manager.get_node_data(from_id)
                            if from_data:
                                from_lat = from_data.get('latitude')
                                from_lon = from_data.get('longitude')
                        
                        if not (to_lat and to_lon):
                            to_data = self.node_manager.get_node_data(to_id)
                            if to_data:
                                to_lat = to_data.get('latitude')
                                to_lon = to_data.get('longitude')
                        
                        if not all([from_lat, from_lon, to_lat, to_lon]):
                            continue
                        
                        # Calculer distance
                        distance = self.node_manager.haversine_distance(from_lat, from_lon, to_lat, to_lon)
                        
                        if distance > record_distance:
                            record_distance = distance
                            record_link = {
                                'from_id': from_id,
                                'to_id': to_id,
                                'distance_km': distance,
                                'from_name': self.node_manager.get_node_name(from_id, self.node_manager.interface),
                                'to_name': self.node_manager.get_node_name(to_id, self.node_manager.interface),
                                'timestamp': link.get('timestamp')
                            }
                    
                    if record_link:
                        lines.append("")
                        lines.append(f"🏆 **Record 30 jours: {self.node_manager.format_distance(record_distance)}**")
                        lines.append(f"   {record_link['from_name']} ↔ {record_link['to_name']}")
                        if record_link['timestamp']:
                            from datetime import datetime
                            dt = datetime.fromtimestamp(record_link['timestamp'])
                            lines.append(f"   🕐 {dt.strftime('%d/%m/%Y %H:%M')}")
                
                except Exception as record_error:
                    logger.debug(f"Impossible de calculer le record 30j: {record_error}")
                
                return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Erreur dans get_propagation_report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"⚠️ Erreur: {str(e)[:50]}"


