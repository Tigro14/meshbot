#!/usr/bin/env python3
"""
Gestionnaire des nœuds avec positions GPS et calcul de distances
VERSION AMÉLIORÉE avec stockage SQLite
"""

import time
import threading
import gc
from config import *
from utils import *
from math import radians, cos, sin, asin, sqrt

class NodeManager:
    def __init__(self, interface=None):
        self.node_names = {}
        self.rx_history = {}
        self.interface = interface
        self.persistence = None  # Will be set by main_bot after initialization
        from collections import deque
        self.packet_type_counts = {
            'POSITION_APP': deque(maxlen=24),
            'TELEMETRY_APP': deque(maxlen=24),
            'NODEINFO_APP': deque(maxlen=24),
            'TEXT_MESSAGE_APP': deque(maxlen=24)
        }
        self.last_packet_hour = None
        
        # Cache state for pubkey sync to avoid excessive interface.nodes access
        # which can cause TCP disconnections on ESP32-based nodes
        self._last_sync_time = 0
        self._last_synced_keys_hash = None
        
        # Position du bot (à récupérer depuis config.py)
        try:
            from config import BOT_POSITION
            self.bot_position = BOT_POSITION
        except ImportError:
            self.bot_position = None
            debug_print("⚠️ BOT_POSITION non défini dans config.py")

    
    def _get_log_funcs(self, source):
        """Get appropriate logging functions based on source
        
        Args:
            source: 'meshtastic', 'meshcore', 'tcp', 'local', etc.
            
        Returns:
            tuple: (debug_func, info_func)
        """
        if source == 'meshcore':
            return debug_print_mc, info_print_mc
        else:
            # Default to MT for meshtastic, tcp, local, etc.
            return debug_print_mt, info_print_mt
    
    def set_interface(self, interface):
        """Définir l'interface Meshtastic"""
        self.interface = interface
    
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculer la distance entre deux points GPS en utilisant la formule de Haversine
        Retourne la distance en kilomètres
        """
        # Convertir en radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Formule de Haversine
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Rayon de la Terre en km
        r = 6371
        
        return c * r
    
    def format_distance(self, distance_km):
        """
        Formater la distance de manière lisible
        """
        if distance_km < 1:
            return f"{int(distance_km * 1000)}m"
        elif distance_km < 10:
            return f"{distance_km:.1f}km"
        else:
            return f"{int(distance_km)}km"
    
    
    def load_nodes_from_sqlite(self):
        """Charger les nœuds depuis la base SQLite"""
        try:
            if not hasattr(self, 'persistence') or not self.persistence:
                debug_print("⚠️ Persistence non disponible, nodes cache vide")
                self.node_names = {}
                return
            
            # Charger tous les nœuds depuis SQLite
            self.node_names = self.persistence.get_all_meshtastic_nodes()
            debug_print(f"📚 {len(self.node_names)} nœuds chargés depuis SQLite")
            
        except Exception as e:
            error_print(f"Erreur chargement nœuds depuis SQLite: {e}")
            self.node_names = {}
    
    
    def get_node_name(self, node_id, interface=None):
        """Récupérer le nom d'un nœud par son ID"""
        # Return fallback name when node_id is None (e.g., when node lookup fails)
        if node_id is None:
            return "Unknown"
        
        if node_id in self.node_names:
            return self.node_names[node_id]['name']
        
        # If not in cache, try to load from SQLite
        if hasattr(self, 'persistence') and self.persistence:
            node_data = self.persistence.get_node_by_id(node_id)
            if node_data:
                self.node_names[node_id] = node_data
                return node_data['name']
        
        # Tenter de récupérer depuis l'interface en temps réel
        try:
            if interface and hasattr(interface, 'nodes'):
                nodes = getattr(interface, 'nodes', {})
                if node_id in nodes:
                    node_info = nodes[node_id]
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            name = user_info.get('longName') or user_info.get('shortName')
                            if name and len(name.strip()) > 0:
                                name = clean_node_name(name)
                                # Créer l'entrée si elle n'existe pas
                                if node_id not in self.node_names:
                                    self.node_names[node_id] = {
                                        'name': name,
                                        'shortName': None,
                                        'hwModel': None,
                                        'lat': None,
                                        'lon': None,
                                        'alt': None,
                                        'last_update': None
                                    }
                                else:
                                    self.node_names[node_id]['name'] = name
                                # Node will be saved to SQLite when update_node_from_packet is called
                                return name
        except Exception as e:
            debug_print(f"Erreur récupération nom {node_id}: {e}")

        # Générer un nom par défaut selon le type de node_id
        if isinstance(node_id, str):
            # Si c'est déjà une chaîne (ex: "!12345678"), l'utiliser tel quel
            return node_id
        else:
            # Si c'est un int, formater en hex
            return f"Node-{node_id:08x}"
    
    def get_node_data(self, node_id):
        """
        Récupérer les données complètes d'un nœud (position, nom, etc.)
        
        Args:
            node_id: ID du nœud (int)
            
        Returns:
            dict avec 'latitude', 'longitude', 'altitude', 'name', 'last_update'
            ou None si le nœud n'existe pas ou n'a pas de position
        """
        if node_id not in self.node_names:
            return None
        
        node_data = self.node_names[node_id]
        
        # Retourner None si pas de position GPS
        if node_data.get('lat') is None or node_data.get('lon') is None:
            return None
        
        # Mapper les clés internes (lat/lon) vers le format attendu (latitude/longitude)
        return {
            'latitude': node_data['lat'],
            'longitude': node_data['lon'],
            'altitude': node_data.get('alt'),
            'name': node_data.get('name'),
            'last_update': node_data.get('last_update')
        }
    
    def find_node_by_pubkey_prefix(self, pubkey_prefix):
        """
        Find a node ID by matching the public key prefix
        
        This method handles multiple publicKey formats:
        - Hex string (e.g., '143bcd7f1b1f...')
        - Base64-encoded string (e.g., 'FDvNfxsfAAA...')
        - Bytes
        
        Search order:
        1. In-memory node_names (JSON cache)
        2. SQLite database (meshtastic_nodes and meshcore_contacts tables)
        
        Args:
            pubkey_prefix: Hex string prefix of the public key (e.g., '143bcd7f1b1f')
            
        Returns:
            int: node_id if found, None otherwise
        """
        if not pubkey_prefix:
            return None
        
        # Normalize the prefix (lowercase, no spaces)
        pubkey_prefix = str(pubkey_prefix).lower().strip()
        
        # Search through in-memory nodes first (JSON cache)
        for node_id, node_data in self.node_names.items():
            if 'publicKey' in node_data:
                public_key = node_data['publicKey']
                public_key_hex = None
                
                # Handle different formats
                if isinstance(public_key, str):
                    # Check if it's already hex (all chars are hex digits)
                    if all(c in '0123456789abcdefABCDEF' for c in public_key.replace(' ', '')):
                        # Already hex format
                        public_key_hex = public_key.lower().replace(' ', '')
                    else:
                        # Assume base64, try to decode
                        try:
                            import base64
                            decoded_bytes = base64.b64decode(public_key)
                            public_key_hex = decoded_bytes.hex().lower()
                        except Exception as e:
                            debug_print(f"⚠️ Failed to decode base64 publicKey for node 0x{node_id:08x}: {e}")
                            continue
                            
                elif isinstance(public_key, bytes):
                    # Bytes format: convert to hex
                    public_key_hex = public_key.hex().lower()
                
                # Check if prefix matches
                if public_key_hex and public_key_hex.startswith(pubkey_prefix):
                    debug_print(f"🔍 Found node 0x{node_id:08x} with pubkey prefix {pubkey_prefix} (in-memory)")
                    return node_id
        
        # Not found in memory, search in SQLite database
        if hasattr(self, 'persistence') and self.persistence:
            found_id, source = self.persistence.find_node_by_pubkey_prefix(pubkey_prefix)
            if found_id:
                debug_print(f"🔍 Found node 0x{found_id:08x} with pubkey prefix {pubkey_prefix} (SQLite/{source})")
                return found_id
        
        debug_print(f"⚠️ No node found with pubkey prefix {pubkey_prefix}")
        return None
    
    def find_node_by_pubkey_prefix_in_db(self, pubkey_prefix):
        """
        Find a node by pubkey prefix in SQLite database only
        
        This is a helper method for the test suite that directly accesses
        the SQLite tables without going through the in-memory cache.
        
        Args:
            pubkey_prefix: Hex string prefix of the public key
            
        Returns:
            tuple: (node_id, source) where source is 'meshtastic' or 'meshcore'
        """
        if hasattr(self, 'persistence') and self.persistence:
            return self.persistence.find_node_by_pubkey_prefix(pubkey_prefix)
        return None, None
    
    def find_meshcore_contact_by_pubkey_prefix(self, pubkey_prefix):
        """
        Find a MeshCore contact ONLY by public key prefix
        
        This method searches ONLY in meshcore_contacts table, not meshtastic_nodes.
        Used for DM resolution via meshcore-cli where we want to keep sources separate.
        
        Search order:
        1. In-memory node_names (but only for nodes from meshcore source)
        2. SQLite meshcore_contacts table ONLY
        
        Args:
            pubkey_prefix: Hex string prefix of the public key (e.g., '143bcd7f1b1f')
            
        Returns:
            int: node_id if found, None otherwise
        """
        if not pubkey_prefix:
            return None
        
        # Normalize the prefix (lowercase, no spaces)
        pubkey_prefix = str(pubkey_prefix).lower().strip()
        
        # Search in SQLite meshcore_contacts table ONLY
        if hasattr(self, 'persistence') and self.persistence:
            node_id = self.persistence.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
            if node_id:
                debug_print(f"🔍 [MESHCORE-ONLY] Found contact 0x{node_id:08x} with pubkey prefix {pubkey_prefix}")
                return node_id
        
        debug_print(f"⚠️ [MESHCORE-ONLY] No MeshCore contact found with pubkey prefix {pubkey_prefix}")
        return None
    
    def get_reference_position(self):
        """
        Obtenir la position de référence (position du bot)
        
        Returns:
            tuple (latitude, longitude) ou None si pas de position configurée
        """
        if self.bot_position is None:
            return None
        
        # BOT_POSITION est déjà un tuple (lat, lon)
        return self.bot_position
    
    def get_node_distance(self, node_id, reference_lat=None, reference_lon=None):
        """
        Calculer la distance jusqu'à un nœud
        Si reference_lat/lon non fournis, utilise la position du bot
        Retourne None si pas de position disponible
        """
        if node_id not in self.node_names:
            return None
        
        node_data = self.node_names[node_id]
        node_lat = node_data.get('lat')
        node_lon = node_data.get('lon')
        
        if node_lat is None or node_lon is None:
            return None
        
        # Utiliser la référence fournie ou la position du bot
        if reference_lat is None or reference_lon is None:
            if self.bot_position is None:
                return None
            reference_lat, reference_lon = self.bot_position
        
        return self.haversine_distance(reference_lat, reference_lon, node_lat, node_lon)
    
    def update_node_position(self, node_id, lat, lon, alt=None):
        """
        Mettre à jour la position d'un nœud
        """
        if node_id not in self.node_names:
            # Créer l'entrée si elle n'existe pas
            default_name = node_id if isinstance(node_id, str) else f"Node-{node_id:08x}"
            self.node_names[node_id] = {
                'name': default_name,
                'shortName': None,
                'hwModel': None,
                'lat': lat,
                'lon': lon,
                'alt': alt,
                'last_update': time.time()
            }
        else:
            # Mettre à jour la position
            self.node_names[node_id]['lat'] = lat
            self.node_names[node_id]['lon'] = lon
            self.node_names[node_id]['alt'] = alt
            self.node_names[node_id]['last_update'] = time.time()
        
        #debug_print_mt(f"📍 Position mise à jour pour {node_id:08x}: {lat:.5f}, {lon:.5f}")
    
    def update_node_database(self, interface):
        """Mettre à jour la base de données des nœuds"""
        if not interface:
            return
        
        try:
            debug_print("🔄 Mise à jour base de nœuds...")
            updated_count = 0
            
            # Récupérer tous les nœuds connus
            nodes = getattr(interface, 'nodes', {})
            
            for node_id, node_info in nodes.items():
                try:
                    # Convertir node_id en entier si c'est une string
                    if isinstance(node_id, str):
                        if node_id.startswith('!'):
                            clean_id = node_id[1:]
                            node_id_int = int(clean_id, 16)
                        else:
                            try:
                                node_id_int = int(node_id, 16)
                            except ValueError:
                                node_id_int = int(node_id)
                    else:
                        node_id_int = int(node_id)
                    
                    # Mise à jour du nom
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            # Handle None values before calling .strip()
                            long_name = (user_info.get('longName') or '').strip()
                            short_name_raw = (user_info.get('shortName') or '').strip()
                            hw_model = (user_info.get('hwModel') or '').strip()
                            
                            # Sanitize names to prevent SQL injection and XSS
                            name = clean_node_name(long_name or short_name_raw)
                            short_name = clean_node_name(short_name_raw) if short_name_raw else None
                            
                            # Extract public key if present (for DM decryption)
                            # Try both field names: 'public_key' (protobuf) and 'publicKey' (dict)
                            public_key = user_info.get('public_key') or user_info.get('publicKey')
                            
                            if name and len(name) > 0:
                                # Initialiser l'entrée si nécessaire
                                if node_id_int not in self.node_names:
                                    self.node_names[node_id_int] = {
                                        'name': name,
                                        'shortName': short_name,
                                        'hwModel': hw_model if hw_model else None,
                                        'lat': None,
                                        'lon': None,
                                        'alt': None,
                                        'last_update': None,
                                        'publicKey': public_key  # Store public key for DM decryption
                                    }
                                    updated_count += 1
                                    #if public_key:
                                        #debug_print(f"🔑 Clé publique extraite pour {name}")
                                elif self.node_names[node_id_int]['name'] != name:
                                    old_name = self.node_names[node_id_int]['name']
                                    self.node_names[node_id_int]['name'] = name
                                    # Also update shortName and hwModel
                                    self.node_names[node_id_int]['shortName'] = short_name
                                    self.node_names[node_id_int]['hwModel'] = hw_model or None
                                    debug_print(f"🔄 {node_id_int:08x}: '{old_name}' -> '{name}'")
                                    updated_count += 1
                                
                                # Always update public key if available (even if name didn't change)
                                if public_key:
                                    old_key = self.node_names[node_id_int].get('publicKey')
                                    if old_key != public_key:
                                        self.node_names[node_id_int]['publicKey'] = public_key
                                        #debug_print(f"🔑 Clé publique mise à jour pour {name}")
                                        # Invalidate sync cache since we updated a key
                                        self._last_synced_keys_hash = None
                    
                    # Mise à jour de la position si disponible
                    if isinstance(node_info, dict) and 'position' in node_info:
                        position = node_info['position']
                        if isinstance(position, dict):
                            lat = position.get('latitude')
                            lon = position.get('longitude')
                            alt = position.get('altitude')
                            
                            if lat is not None and lon is not None:
                                # Vérifier si la position a changé
                                if node_id_int not in self.node_names:
                                    self.node_names[node_id_int] = {
                                        'name': f"Node-{node_id_int:08x}",
                                        'shortName': None,
                                        'hwModel': None,
                                        'lat': lat,
                                        'lon': lon,
                                        'alt': alt,
                                        'last_update': time.time()
                                    }
                                    updated_count += 1
                                else:
                                    old_lat = self.node_names[node_id_int].get('lat')
                                    old_lon = self.node_names[node_id_int].get('lon')
                                    
                                    # Mise à jour si nouvelle position ou position différente
                                    if old_lat != lat or old_lon != lon:
                                        self.node_names[node_id_int]['lat'] = lat
                                        self.node_names[node_id_int]['lon'] = lon
                                        self.node_names[node_id_int]['alt'] = alt
                                        self.node_names[node_id_int]['last_update'] = time.time()
                                        #debug_print(f"📍 Position mise à jour: {node_id_int:08x}")
                                        updated_count += 1
                
                except Exception as e:
                    debug_print(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            if updated_count > 0:
                # Nodes are already saved to SQLite via save_meshtastic_node()
                debug_print(f"✅ {updated_count} nœuds mis à jour")
            else:
                debug_print(f"ℹ️ Base à jour ({len(self.node_names)} nœuds)")
                
        except Exception as e:
            error_print(f"Erreur mise à jour base: {e}")
    
    def format_rx_report(self):
        """Générer un rapport des nœuds reçus récemment avec distances"""
        try:
            # Filtrer les nœuds récents (30 dernières minutes)
            recent_cutoff = time.time() - 1800
            recent_nodes = [
                (node_id, data) for node_id, data in self.rx_history.items()
                if data['last_seen'] > recent_cutoff
            ]
            
            if not recent_nodes:
                return "Aucun nœud récent (30min)"
            
            # Trier par qualité SNR (descendant)
            # Utiliser 0 si SNR est None pour éviter TypeError
            recent_nodes.sort(key=lambda x: x[1].get('snr', 0) if x[1].get('snr') is not None else 0, reverse=True)
            
            # Formater le rapport
            lines = []
            lines.append(f"📡 Nœuds DIRECTS ({len(recent_nodes)}):")
            
            for node_id, data in recent_nodes[:10]:
                name = truncate_text(data['name'], 12)
                snr = data['snr']
                count = data['count']
                
                # Indicateur de qualité basé sur SNR
                signal_icon = get_signal_quality_icon(snr)
                
                # Temps depuis dernière réception
                time_str = format_elapsed_time(data['last_seen'])
                
                # Distance si disponible
                distance = self.get_node_distance(node_id)
                distance_str = f" {self.format_distance(distance)}" if distance else ""
                
                line = f"{signal_icon} {name}: SNR:{snr:.1f}dB ({count}x) {time_str}{distance_str}"
                lines.append(line)
            
            if len(recent_nodes) > 10:
                lines.append(f"... et {len(recent_nodes) - 10} autres")
            
            result = "\n".join(lines)
            
            # Limiter la taille totale du message
            if len(result) > 500:
                lines_short = lines[:6]
                if len(recent_nodes) > 5:
                    lines_short.append(f"... et {len(recent_nodes) - 5} autres")
                result = "\n".join(lines_short)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur format RX: {e}")
            return f"Erreur génération rapport RX: {truncate_text(str(e), 30)}"
    
    def update_node_from_packet(self, packet, source='meshtastic'):
        """Mettre à jour la base de nœuds depuis un packet reçu (NODEINFO_APP)
        
        Args:
            packet: Packet reçu
            source: Source du packet ('meshtastic', 'meshcore', 'tcp', 'local')
        """
        try:
            if 'decoded' in packet and packet['decoded'].get('portnum') == 'NODEINFO_APP':
                node_id = packet.get('from')
                decoded = packet['decoded']
                
                if 'user' in decoded and node_id:
                    user_info = decoded['user']
                    long_name = user_info.get('longName', '').strip()
                    short_name_raw = user_info.get('shortName', '').strip()
                    hw_model = user_info.get('hwModel', '').strip()
                    
                    # Sanitize names to prevent SQL injection and XSS
                    name = clean_node_name(long_name or short_name_raw)
                    short_name = clean_node_name(short_name_raw) if short_name_raw else None
                    
                    # Extract public key if present (for DM decryption)
                    # Try both field names: 'public_key' (protobuf) and 'publicKey' (dict)
                    public_key = user_info.get('public_key') or user_info.get('publicKey')
                    
                    # Get appropriate log functions based on source
                    debug_func, info_func = self._get_log_funcs(source)
                    
                    # DEBUG: Log public key preview if present (consolidated)
                    if public_key and DEBUG_MODE:
                        pk_len = len(public_key)
                        pk_preview = public_key[:20] if len(public_key) > 20 else public_key
                        #debug_func(f"🔑 Key preview: {name} (len={pk_len})")
                    
                    # Log when public key field is completely absent (firmware < 2.5.0)
                    if not public_key and 'public_key' not in user_info and 'publicKey' not in user_info:
                        info_func(f"⚠️ {name}: NODEINFO without public_key field (firmware < 2.5.0?)")
                    
                    if name and len(name) > 0:
                        # Initialiser l'entrée si elle n'existe pas
                        if node_id not in self.node_names:
                            self.node_names[node_id] = {
                                'name': name,
                                'shortName': short_name,
                                'hwModel': hw_model if hw_model else None,
                                'lat': None,
                                'lon': None,
                                'alt': None,
                                'last_update': None,
                                'publicKey': public_key  # Store public key for DM decryption
                            }
                            info_func(f"📱 New node: {name} (0x{node_id:08x})")
                            if public_key:
                                # Consolidated log: one line for new key
                                #info_func(f"✅ Key extracted: {name} (len={len(public_key)})")
                                
                                # Immediately sync to interface.nodes for DM decryption
                                self._sync_single_pubkey_to_interface(node_id, self.node_names[node_id], source)
                                
                                # Invalidate sync cache since we added a new key
                                self._last_synced_keys_hash = None
                            else:
                                info_func(f"❌ NO public key for {name} - DM decryption will NOT work")
                            
                            # Save to SQLite meshtastic_nodes table
                            if hasattr(self, 'persistence') and self.persistence:
                                node_data = {
                                    'node_id': node_id,
                                    'name': name,
                                    'shortName': short_name,
                                    'hwModel': hw_model if hw_model else None,
                                    'publicKey': public_key,
                                    'lat': None,
                                    'lon': None,
                                    'alt': None,
                                    'source': source
                                }
                                self.persistence.save_meshtastic_node(node_data, source)
                        else:
                            #Track whether any data actually changed
                            data_changed = False
                            
                            old_name = self.node_names[node_id]['name']
                            if old_name != name:
                                self.node_names[node_id]['name'] = name
                                info_func(f"📱 Node renamed: {old_name} → {name} (0x{node_id:08x})")
                                data_changed = True
                            # Always update shortName and hwModel even if name didn't change
                            old_short_name = self.node_names[node_id].get('shortName')
                            old_hw_model = self.node_names[node_id].get('hwModel')
                            if old_short_name != short_name or old_hw_model != hw_model:
                                data_changed = True
                            self.node_names[node_id]['shortName'] = short_name
                            self.node_names[node_id]['hwModel'] = hw_model or None
                            
                            # Update public key if present (for DM decryption)
                            old_key = self.node_names[node_id].get('publicKey')
                            if public_key and public_key != old_key:
                                self.node_names[node_id]['publicKey'] = public_key
                                # Consolidated log: one line for key update
                                #info_func(f"✅ Key updated: {name} (len={len(public_key)})")
                                data_changed = True
                                
                                # Immediately sync to interface.nodes for DM decryption
                                self._sync_single_pubkey_to_interface(node_id, self.node_names[node_id], source)
                                
                                # Invalidate sync cache since we updated a key
                                self._last_synced_keys_hash = None
                            elif public_key and old_key:
                                # Key already exists and matches - this is the common case
                                #debug_func(f"ℹ️ Key unchanged: {name}")
                                
                                # CRITICAL: Still sync to interface.nodes even if unchanged
                                # After bot restart, interface.nodes is empty but SQLite DB has keys
                                # Without this sync, /keys will report nodes as "without keys"
                                self._sync_single_pubkey_to_interface(node_id, self.node_names[node_id], source)
                            elif not public_key and not old_key:
                                info_func(f"⚠️ Still NO key for {name}")
                            
                            # Save to SQLite meshtastic_nodes table if data changed
                            if data_changed:
                                if hasattr(self, 'persistence') and self.persistence:
                                    node_data = {
                                        'node_id': node_id,
                                        'name': name,
                                        'shortName': short_name,
                                        'hwModel': hw_model or None,
                                        'publicKey': public_key,
                                        'lat': self.node_names[node_id].get('lat'),
                                        'lon': self.node_names[node_id].get('lon'),
                                        'alt': self.node_names[node_id].get('alt'),
                                        'source': source
                                    }
                                    self.persistence.save_meshtastic_node(node_data, source)
        except Exception as e:
            debug_print(f"Erreur traitement NodeInfo: {e}")

    def update_rx_history(self, packet):
        """Mettre à jour l'historique des signaux reçus (DIRECT uniquement - 0 hop) - SNR UNIQUEMENT"""
        try:
            from_id = packet.get('from')
            if not from_id:
                return
            
            # FILTRER UNIQUEMENT LES MESSAGES DIRECTS (0 hop)
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 5)
            hops_taken = hop_start - hop_limit
            
            # Extraire SNR (essayer plusieurs clés)
            snr = packet.get('snr')
            if snr is None:
                snr = packet.get('rxSnr')
            if snr is None:
                snr = 0.0
            
            # ✅ FIX: Skip rx_history update for DM packets (not RF data)
            # DM packets (MeshCore/Telegram) have snr=0.0 by default
            # RX_LOG packets have real RF data and should ALWAYS be recorded
            is_meshcore_dm = packet.get('_meshcore_dm', False)
            is_meshcore_rx_log = packet.get('_meshcore_rx_log', False)
            
            # DEBUG: Log packet type and SNR value
            debug_print(f"🔍 [RX_HISTORY] Node 0x{from_id:08x} | snr={snr} | DM={is_meshcore_dm} | RX_LOG={is_meshcore_rx_log} | hops={hops_taken}")
            
            if snr == 0.0 and not is_meshcore_rx_log:
                # Skip SNR update but STILL update last_seen timestamp
                # This ensures /my shows recent activity even without RF signal data
                if from_id in self.rx_history:
                    self.rx_history[from_id]['last_seen'] = time.time()
                    name = self.get_node_name(from_id, self.interface if hasattr(self, 'interface') else None)
                    self.rx_history[from_id]['name'] = name
                    debug_print(f"✅ [RX_HISTORY] TIMESTAMP updated 0x{from_id:08x} ({name}) | snr=0.0, no SNR update")
                elif is_meshcore_dm:
                    # Create new entry with snr=0.0 for DM packets
                    name = self.get_node_name(from_id, self.interface if hasattr(self, 'interface') else None)
                    self.rx_history[from_id] = {
                        'name': name,
                        'snr': 0.0,
                        'last_seen': time.time(),
                        'count': 1
                    }
                    debug_print(f"✅ [RX_HISTORY] NEW entry 0x{from_id:08x} ({name}) | snr=0.0 (DM packet)")
                return
            
            # Obtenir le nom
            name = self.get_node_name(from_id, self.interface if hasattr(self, 'interface') else None)
        
            # Mettre à jour l'historique RX
            if from_id not in self.rx_history:
                self.rx_history[from_id] = {
                    'name': name,
                    'snr': snr,
                    'last_seen': time.time(),
                    'count': 1
                }
                debug_print(f"✅ [RX_HISTORY] NEW entry for 0x{from_id:08x} ({name}) | snr={snr:.1f}dB")
            else:
                # Moyenne mobile du SNR
                old_snr = self.rx_history[from_id]['snr']
                count = self.rx_history[from_id]['count']
                new_snr = (old_snr * count + snr) / (count + 1)
                
                self.rx_history[from_id]['snr'] = new_snr
                self.rx_history[from_id]['last_seen'] = time.time()
                self.rx_history[from_id]['count'] += 1
                self.rx_history[from_id]['name'] = name
                debug_print(f"✅ [RX_HISTORY] UPDATED 0x{from_id:08x} ({name}) | old_snr={old_snr:.1f}→new_snr={new_snr:.1f}dB | count={count+1}")
            
            # Limiter la taille de l'historique
            if len(self.rx_history) > MAX_RX_HISTORY:
                # Supprimer les plus anciens
                sorted_by_time = sorted(self.rx_history.items(), key=lambda x: x[1]['last_seen'])
                for old_node_id, _ in sorted_by_time[:len(self.rx_history) - MAX_RX_HISTORY]:
                    del self.rx_history[old_node_id]
                    
        except Exception as e:
            debug_print(f"Erreur MAJ RX history: {e}")
    
    def sync_pubkeys_to_interface(self, interface, force=False):
        """
        Synchronize public keys from SQLite DB to interface.nodes
        
        This is critical for DM decryption in TCP mode where interface.nodes
        starts empty. We inject public keys from our persistent database
        to enable PKI decryption without violating ESP32 single-connection limit.
        
        OPTIMIZATION: Uses hash-based caching to avoid excessive interface.nodes access
        which can cause TCP disconnections on ESP32-based Meshtastic nodes.
        
        Args:
            interface: Meshtastic interface (serial or TCP)
            force: If True, skip the cache check and always perform full sync
                   Used at startup and after reconnection
        
        Returns:
            int: Number of public keys injected
        """
        if not interface or not hasattr(interface, 'nodes'):
            info_print("⚠️ Interface doesn't have nodes attribute")
            return 0
        
        # Quick check: if not forced and we have no keys in DB, skip immediately
        keys_in_db = sum(1 for n in self.node_names.values() if n.get('publicKey'))
        if not force and keys_in_db == 0:
            debug_print("⏭️ Skipping pubkey sync: no keys in database")
            return 0
        
        # OPTIMIZATION: Cache-based skip to avoid excessive interface.nodes access
        # Compute a hash of current keys to detect if anything changed
        if not force:
            # Create a simple hash of all public keys in our database
            # Format: "node_id:key_length,node_id:key_length,..."
            current_keys_list = []
            for node_id in sorted(self.node_names.keys()):
                node_data = self.node_names[node_id]
                public_key = node_data.get('publicKey')
                if public_key:
                    # Use node_id and key length as a lightweight fingerprint
                    current_keys_list.append(f"{node_id}:{len(public_key)}")
            
            current_keys_hash = ','.join(current_keys_list)
            
            # Check if keys haven't changed since last sync (within last 4 minutes)
            # This avoids the expensive interface.nodes iteration every 5 minutes
            current_time = time.time()
            time_since_last_sync = current_time - self._last_sync_time
            
            if (self._last_synced_keys_hash == current_keys_hash and 
                time_since_last_sync < 240):  # 4 minutes
                debug_print(f"⏭️ Skipping pubkey sync: keys unchanged since last sync ({time_since_last_sync:.0f}s ago)")
                return 0
        
        # If we reach here, either:
        # - force=True (startup/reconnection)
        # - keys changed in our database
        # - more than 4 minutes since last sync
        # Perform the actual sync
        
        # CRITICAL: Safely access interface.nodes with error handling
        # After TCP reconnection, interface.nodes access can hang/block
        nodes = None
        
        try:
            # Attempt to access nodes dict
            # If this hangs, the deferred sync (after 15s) gives the interface time to stabilize
            nodes = getattr(interface, 'nodes', {})
        except Exception as e:
            error_print(f"⚠️ Error accessing interface.nodes: {e}")
            error_print("❌ Cannot sync pubkeys: interface.nodes not accessible")
            return 0
        
        if nodes is None:
            error_print("❌ Cannot sync pubkeys: interface.nodes is None")
            return 0
        
        # Perform full sync (forced or keys missing)
        info_print("🔄 Starting public key synchronization to interface.nodes...")
        injected_count = 0
        
        # Safe access to nodes length with error handling
        try:
            nodes_count = len(nodes)
            info_print(f"   Current interface.nodes count: {nodes_count}")
        except Exception as e:
            error_print(f"⚠️ Error getting nodes count: {e}")
            nodes_count = 0
        
        info_print(f"   Keys to sync from node_names: {keys_in_db}")
        
        for node_id, node_data in self.node_names.items():
            # Get public key from our database
            public_key = node_data.get('publicKey')
            if not public_key:
                continue
            
            node_name = node_data.get('name', f"Node-{node_id:08x}")
            #debug_print(f"   Processing {node_name} (0x{node_id:08x}): has key in DB")
            
            # Try to find node in interface.nodes with various key formats
            node_info = None
            possible_keys = [
                node_id,
                str(node_id),
                f"!{node_id:08x}",
                f"{node_id:08x}"
            ]
            
            for key in possible_keys:
                if key in nodes:
                    node_info = nodes[key]
                    #debug_print(f"      Found in interface.nodes with key: {key}")
                    break
            
            if node_info and isinstance(node_info, dict):
                # Node exists in interface.nodes
                user_info = node_info.get('user', {})
                if isinstance(user_info, dict):
                    # Try both field names when checking existing key
                    existing_key = user_info.get('public_key') or user_info.get('publicKey')
                    if not existing_key or existing_key != public_key:
                        # Inject public key using both field names for compatibility
                        user_info['public_key'] = public_key  # Protobuf style
                        user_info['publicKey'] = public_key   # Dict style
                        injected_count += 1
                        #debug_print(f"      ✅ Injected key into existing node")
                    else:
                        #debug_print(f"      ℹ️ Key already present and matches")
                        # CRITICAL DEBUG: Verify the key is actually accessible
                        verify_key = user_info.get('public_key') or user_info.get('publicKey')
                        #if verify_key:
                            #debug_print(f"      ✓ DEBUG: Key verified present (len={len(verify_key)})")
                        #else:
                            #error_print(f"      ✗ BUG: Key shows as present but NOT accessible!")
            else:
                # Node doesn't exist in interface.nodes yet
                # Create minimal entry with public key
                node_name = node_data.get('name', f"Node-{node_id:08x}")
                short_name = node_data.get('shortName', '')
                hw_model = node_data.get('hwModel', '')
                
                #debug_print(f"      Not in interface.nodes yet - creating entry")
                nodes[node_id] = {
                    'num': node_id,
                    'user': {
                        'id': f"!{node_id:08x}",
                        'longName': node_name,
                        'shortName': short_name,
                        'hwModel': hw_model,
                        'public_key': public_key,  # Protobuf style
                        'publicKey': public_key    # Dict style
                    }
                }
                injected_count += 1
                #debug_print(f"      ✅ Created node in interface.nodes with key")
        
        if injected_count > 0:
            info_print(f"✅ SYNC COMPLETE: {injected_count} public keys synchronized to interface.nodes")
        else:
            info_print(f"ℹ️ SYNC COMPLETE: No new keys to inject (all already present)")
        
        # Update cache to avoid re-checking unnecessarily
        # This prevents the expensive interface.nodes iteration on next periodic sync
        current_keys_list = []
        for node_id in sorted(self.node_names.keys()):
            node_data = self.node_names[node_id]
            public_key = node_data.get('publicKey')
            if public_key:
                current_keys_list.append(f"{node_id}:{len(public_key)}")
        self._last_synced_keys_hash = ','.join(current_keys_list)
        self._last_sync_time = time.time()
        debug_print(f"📌 Sync cache updated: {len(current_keys_list)} keys tracked")
        
        # CRITICAL DEBUG: Verify interface.nodes state after sync
        total_nodes_in_interface = len(nodes)
        nodes_with_keys_in_interface = 0
        for node_id, node_info in list(nodes.items())[:5]:  # Check first 5 for debugging
            if isinstance(node_info, dict):
                user_info = node_info.get('user', {})
                if isinstance(user_info, dict):
                    has_key = user_info.get('public_key') or user_info.get('publicKey')
                    if has_key:
                        nodes_with_keys_in_interface += 1
                        #debug_print(f"   DEBUG: Node {node_id} HAS key (len={len(has_key)})")
                    #else:
                        #debug_print(f"   DEBUG: Node {node_id} NO key")
        
        debug_print(f"   DEBUG SUMMARY: interface.nodes has {total_nodes_in_interface} total nodes")
        debug_print(f"   DEBUG SUMMARY: Checked {min(5, total_nodes_in_interface)} nodes, {nodes_with_keys_in_interface} have keys")
        
        return injected_count
    
    def _sync_single_pubkey_to_interface(self, node_id, node_data, source='meshtastic'):
        """
        Immediately sync a single public key to interface.nodes
        
        This is called when a new public key is extracted from NODEINFO
        to make it available for DM decryption without waiting for periodic sync.
        
        Args:
            node_id: Node ID (integer)
            node_data: Node data dict from node_names
            source: Source of the packet ('meshtastic', 'meshcore', etc.)
        """
        if not self.interface or not hasattr(self.interface, 'nodes'):
            debug_print("⚠️ Interface not available for immediate key sync")
            return
        
        public_key = node_data.get('publicKey')
        if not public_key:
            return
        
        node_name = node_data.get('name', f"Node-{node_id:08x}")
        nodes = getattr(self.interface, 'nodes', {})
        
        # Get appropriate log functions
        debug_func, info_func = self._get_log_funcs(source)
        
        # Try to find node in interface.nodes with various key formats
        node_info = None
        possible_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
        
        for key in possible_keys:
            if key in nodes:
                node_info = nodes[key]
                break
        
        if node_info and isinstance(node_info, dict):
            # Node exists - inject key
            user_info = node_info.get('user', {})
            if isinstance(user_info, dict):
                user_info['public_key'] = public_key   # Protobuf style
                user_info['publicKey'] = public_key    # Dict style
                debug_func(f"🔑 Key synced: {node_name} → interface.nodes")
        else:
            # Create minimal entry
            short_name = node_data.get('shortName', '')
            hw_model = node_data.get('hwModel', '')
            nodes[node_id] = {
                'num': node_id,
                'user': {
                    'id': f"!{node_id:08x}",
                    'longName': node_name,
                    'shortName': short_name,
                    'hwModel': hw_model,
                    'public_key': public_key,  # Protobuf style
                    'publicKey': public_key    # Dict style
                }
            }
            debug_func(f"🔑 Created interface.nodes entry: {node_name}")
    
    def track_packet_type(self, packet):
        """Suivre les types de paquets par heure pour l'histogramme"""
        try:
            if 'decoded' not in packet:
                return
            
            packet_type = packet['decoded'].get('portnum', 'UNKNOWN_APP')
            
            # Ne suivre que certains types
            if packet_type not in self.packet_type_counts:
                return
            
            # Obtenir l'heure actuelle
            current_hour = time.strftime('%Y-%m-%d %H:00')
            
            # Si c'est une nouvelle heure, ajouter un nouveau slot
            if self.last_packet_hour != current_hour:
                self.last_packet_hour = current_hour
                for ptype in self.packet_type_counts:
                    self.packet_type_counts[ptype].append(0)
            
            # Incrémenter le compteur pour cette heure
            if len(self.packet_type_counts[packet_type]) > 0:
                self.packet_type_counts[packet_type][-1] += 1
                
        except Exception as e:
            debug_print(f"Erreur track_packet_type: {e}")
    
    def list_known_nodes(self):
        """Lister tous les nœuds connus avec leurs positions"""
        if not DEBUG_MODE:
            return
            
        print(f"\n📋 Nœuds connus ({len(self.node_names)}):")
        print("-" * 80)
        for node_id, node_data in sorted(self.node_names.items()):
            name = node_data['name']
            lat = node_data.get('lat')
            lon = node_data.get('lon')
            
            position_str = ""
            if lat and lon:
                position_str = f" @ {lat:.5f}, {lon:.5f}"
                distance = self.get_node_distance(node_id)
                if distance:
                    position_str += f" ({self.format_distance(distance)})"
            
            print(f"  !{node_id:08x} = {name}{position_str}")
        print()


    def format_rx_report(self):
        """Formater le rapport des nœuds reçus - SNR UNIQUEMENT"""
        try:
            if not self.rx_history:
                return "Aucun nœud reçu récemment"
            
            current_time = time.time()
            recent_nodes = []
            
            # Filtrer les nœuds vus dans les dernières 30 minutes
            for node_id, data in self.rx_history.items():
                if current_time - data['last_seen'] <= 1800:  # 30 minutes
                    recent_nodes.append((node_id, data))
            
            if not recent_nodes:
                return "Aucun nœud récent (30min)"
            
            # Trier par qualité SNR (descendant)
            # Utiliser 0 si SNR est None pour éviter TypeError
            recent_nodes.sort(key=lambda x: x[1].get('snr', 0) if x[1].get('snr') is not None else 0, reverse=True)
            
            # Formater le rapport
            lines = []
            lines.append(f"📡 Nœuds DIRECTS ({len(recent_nodes)}):")
            
            for node_id, data in recent_nodes[:10]:  # Limiter à 10 pour la taille du message
                name = truncate_text(data['name'], 12)
                snr = data['snr']
                count = data['count']
                
                # Indicateur de qualité basé sur SNR UNIQUEMENT
                signal_icon = get_signal_quality_icon(snr)
                
                # Temps depuis dernière réception
                time_str = format_elapsed_time(data['last_seen'])
                
                line = f"{signal_icon} {name}: SNR:{snr:.1f}dB ({count}x) {time_str}"
                lines.append(line)
            
            if len(recent_nodes) > 10:
                lines.append(f"... et {len(recent_nodes) - 10} autres")
            
            result = "\n".join(lines)
            
            # Limiter la taille totale du message
            if len(result) > 500:
                # Prendre seulement les 5 premiers
                lines_short = lines[:6]  # Header + 5 nœuds
                if len(recent_nodes) > 5:
                    lines_short.append(f"... et {len(recent_nodes) - 5} autres")
                result = "\n".join(lines_short)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur format RX: {e}")
            return f"Erreur génération rapport RX: {truncate_text(str(e), 30)}"
    
    def list_known_nodes(self):
        """Lister tous les nœuds connus"""
        if not DEBUG_MODE:
            return
            
        print(f"\n📋 Nœuds connus ({len(self.node_names)}):")
        print("-" * 60)
        for node_id, name in sorted(self.node_names.items()):
            print(f"  !{node_id:08x} -> {name}")
        print("-" * 60)
    
    def cleanup_old_rx_history(self):
        """Nettoyer l'historique RX ancien"""
        try:
            current_time = time.time()
            cutoff_time = current_time - 3600  # 1 heure
            
            to_remove = []
            for node_id, data in self.rx_history.items():
                if data['last_seen'] < cutoff_time:
                    to_remove.append(node_id)
            
            for node_id in to_remove:
                del self.rx_history[node_id]
            
            if to_remove:
                debug_print(f"🧹 {len(to_remove)} entrées RX anciennes supprimées")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage RX: {e}")

    def get_packet_histogram_single(self, packet_type='ALL', hours=24):
        """
        Générer un histogramme pour un type de paquet spécifique

        Args:
            packet_type: 'POS', 'TELE', 'NODE', 'TEXT' ou 'ALL' pour vue d'ensemble
            hours: Nombre d'heures à analyser (défaut 24)

        Returns:
            str: Histogramme formaté pour un seul type ou vue d'ensemble
        """
        try:
            if not hasattr(self, 'packet_type_counts'):
                return "❌ Historique non disponible"

            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)

            # Symboles pour le graphique ASCII
            symbols = "▁▂▃▄▅▆▇█"

            # Types de paquets avec leurs labels
            packet_types = {
                'POS': 'POSITION_APP',
                'TELE': 'TELEMETRY_APP',
                'NODE': 'NODEINFO_APP',
                'TEXT': 'TEXT_MESSAGE_APP'
            }

            # Si ALL, retourner vue d'ensemble compacte
            if packet_type.upper() == 'ALL':
                return self._format_histogram_overview(packet_types, cutoff_time, hours)

            # Vérifier que le type demandé existe
            packet_type_upper = packet_type.upper()
            if packet_type_upper not in packet_types:
                return f"❌ Type inconnu: {packet_type}\nTypes: pos, tele, node, text"

            # Obtenir les données pour ce type
            portnum = packet_types[packet_type_upper]

            if portnum not in self.packet_type_counts:
                return f"📦 {packet_type_upper}: Aucune donnée"

            # Filtrer les données dans la fenêtre temporelle
            data_points = [
                count for timestamp, count in self.packet_type_counts[portnum]
                if timestamp >= cutoff_time
            ]

            if not data_points:
                return f"📦 {packet_type_upper}: Aucune donnée ({hours}h)"

            # Générer la sparkline
            sparkline = self._generate_sparkline(data_points, symbols, 24)

            # Statistiques
            total = sum(data_points)
            min_val = min(data_points)
            max_val = max(data_points)
            current = data_points[-1] if data_points else 0

            # Tendance (comparer les 3 derniers points)
            if len(data_points) >= 3:
                recent = data_points[-3:]
                if recent[-1] > recent[-2]:
                    trend = "↗️"
                elif recent[-1] < recent[-2]:
                    trend = "↘️"
                else:
                    trend = "→"
            else:
                trend = "→"

            # Formater la réponse
            lines = [
                f"📦 {packet_type_upper} ({hours}h):",
                sparkline,
                f"Min:{min_val} | Max:{max_val} | Now:{current} {trend} | Tot:{total}"
            ]

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur histogram single: {e}")
            return f"❌ Erreur: {str(e)[:30]}"

    def _format_histogram_overview(self, packet_types, cutoff_time, hours):
        """
        Formater une vue d'ensemble compacte de tous les types
        """
        try:
            lines = [f"📦 Paquets ({hours}h):"]
            total_all = 0

            for short_name, portnum in packet_types.items():
                if portnum not in self.packet_type_counts:
                    continue

                # Filtrer les données
                data_points = [
                    count for timestamp, count in self.packet_type_counts[portnum]
                    if timestamp >= cutoff_time
                ]

                if data_points:
                    total = sum(data_points)
                    total_all += total
                    lines.append(f"{short_name}: {total}")

            lines.append(f"📊 Total: {total_all} paquets")
            lines.append("")
            lines.append("Détails: /histo <type>")
            lines.append("Types: pos, tele, node, text")

            return "\n".join(lines)

        except Exception as e:
            return f"❌ Erreur: {str(e)[:30]}"

    def _generate_sparkline(self, values, symbols, target_length=24):
        """
        Générer une sparkline ASCII

        Args:
            values: Liste des valeurs
            symbols: String des symboles (8 niveaux)
            target_length: Longueur cible du graphique

        Returns:
            str: Sparkline ASCII
        """
        if not values:
            return '─' * target_length

        # Sous-échantillonner si nécessaire
        if len(values) > target_length:
            step = len(values) / target_length
            sampled_values = [
                values[int(i * step)]
                for i in range(target_length)
            ]
        elif len(values) < target_length:
            # Répéter la dernière valeur
            sampled_values = values + [values[-1]] * (target_length - len(values))
        else:
            sampled_values = values

        # Normaliser les valeurs
        min_val = min(sampled_values)
        max_val = max(sampled_values)

        if max_val == min_val:
            # Valeur constante
            return symbols[4] * target_length

        sparkline = ""
        for value in sampled_values:
            # Normaliser entre 0 et 1
            normalized = (value - min_val) / (max_val - min_val)
            # Mapper sur les symboles (0-7)
            symbol_index = int(normalized * (len(symbols) - 1))
            symbol_index = max(0, min(len(symbols) - 1, symbol_index))
            sparkline += symbols[symbol_index]

        return sparkline

    def track_packet_type(self, packet):
        """
        Enregistrer le type de paquet pour les statistiques /histo
        Compte les paquets par heure
        """
        try:
            if 'decoded' not in packet:
                return

            portnum = packet['decoded'].get('portnum', '')

            # Seulement les types qu'on veut traquer
            if portnum not in self.packet_type_counts:
                return

            current_time = time.time()
            current_hour = int(current_time // 3600)

            # Initialiser le compteur horaire si nécessaire
            if self.last_packet_hour != current_hour:
                self.last_packet_hour = current_hour

                # Ajouter un nouveau point pour la nouvelle heure
                for ptype in self.packet_type_counts:
                    self.packet_type_counts[ptype].append((current_time, 0))

            # Incrémenter le compteur pour ce type
            if self.packet_type_counts[portnum]:
                last_time, last_count = self.packet_type_counts[portnum][-1]
                self.packet_type_counts[portnum][-1] = (last_time, last_count + 1)
            else:
                self.packet_type_counts[portnum].append((current_time, 1))

            #debug_print(f"📊 Packet tracké: {portnum}")

        except Exception as e:
            debug_print(f"Erreur track_packet_type: {e}")
