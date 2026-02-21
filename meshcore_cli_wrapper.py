#!/usr/bin/env python3
"""
Wrapper pour meshcore-cli library
Intégration avec le bot MeshBot en mode companion
"""

import threading
import time
import asyncio
import hashlib
from utils import info_print, debug_print, error_print, info_print_mc, debug_print_mc
import traceback

# Try to import meshcore-cli
try:
    from meshcore import MeshCore, EventType
    MESHCORE_CLI_AVAILABLE = True
    debug_print_mc("✅ [MESHCORE] Library meshcore-cli disponible")
except ImportError:
    MESHCORE_CLI_AVAILABLE = False
    info_print_mc("⚠️ [MESHCORE] Library meshcore-cli non disponible (pip install meshcore)")
    # Fallback to basic implementation
    MeshCore = None
    EventType = None

# Try to import meshcore-decoder for packet parsing
try:
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    MESHCORE_DECODER_AVAILABLE = True
    debug_print_mc("✅ [MESHCORE] Library meshcore-decoder disponible (packet decoding)")
except ImportError:
    MESHCORE_DECODER_AVAILABLE = False
    info_print_mc("⚠️ [MESHCORE] Library meshcore-decoder non disponible (pip install meshcoredecoder)")
    MeshCoreDecoder = None
    get_route_type_name = None
    get_payload_type_name = None

# Try to import PyNaCl for key validation
try:
    import nacl.public
    import nacl.encoding
    NACL_AVAILABLE = True
    debug_print_mc("✅  PyNaCl disponible (validation clés)")
except ImportError:
    NACL_AVAILABLE = False
    debug_print_mc("ℹ️  [MESHCORE] PyNaCl non disponible (validation clés désactivée)")

# Try to import cryptography for MeshCore Public channel decryption
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import base64
    CRYPTO_AVAILABLE = True
    debug_print_mc("✅ [MESHCORE] cryptography disponible (déchiffrement canal Public)")
except ImportError:
    CRYPTO_AVAILABLE = False
    info_print_mc("⚠️ [MESHCORE] cryptography non disponible (pip install cryptography)")
    info_print_mc("   → Déchiffrement canal Public MeshCore désactivé")


def decrypt_meshcore_public(encrypted_bytes, packet_id, from_id, psk):
    """
    Decrypt MeshCore Public channel encrypted message using AES-128-CTR.
    
    Args:
        encrypted_bytes: Encrypted payload data (bytes)
        packet_id: Packet ID from decoded packet
        from_id: Sender node ID from decoded packet
        psk: Pre-Shared Key as base64 string or bytes (16 bytes for AES-128)
        
    Returns:
        Decrypted text string or None if decryption fails
    """
    if not CRYPTO_AVAILABLE:
        return None
        
    try:
        # Convert PSK from base64 to bytes if needed
        if isinstance(psk, str):
            psk_bytes = base64.b64decode(psk)
        else:
            psk_bytes = psk
            
        # Ensure PSK is 16 bytes for AES-128
        if len(psk_bytes) != 16:
            debug_print_mc(f"⚠️  [DECRYPT] PSK length is {len(psk_bytes)} bytes, expected 16 bytes")
            return None
        
        # Debug: Show PSK length
        debug_print_mc(f"🔍 [DECRYPT] PSK: {len(psk_bytes)} bytes")
        
        # Construct nonce for AES-CTR (16 bytes)
        # MeshCore uses: packet_id (8 bytes LE) + from_id (4 bytes LE) + padding (4 zeros)
        nonce = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little') + b'\x00' * 4
        
        # Debug: Show nonce
        debug_print_mc(f"🔍 [DECRYPT] Nonce: {nonce.hex()}")
        
        # Debug: Show encrypted payload (first 32 bytes)
        debug_print_mc(f"🔍 [DECRYPT] Encrypted (first 32B): {encrypted_bytes[:32].hex()}")
        
        # Create AES-128-CTR cipher
        cipher = Cipher(
            algorithms.AES(psk_bytes),
            modes.CTR(nonce),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt
        decrypted_bytes = decryptor.update(encrypted_bytes) + decryptor.finalize()
        
        # Debug: Show decrypted bytes (first 32 bytes)
        debug_print_mc(f"🔍 [DECRYPT] Decrypted (first 32B): {decrypted_bytes[:32].hex()}")
        
        # Try to decode as UTF-8 text
        decrypted_text = decrypted_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
        
        # Debug: Show UTF-8 decoded text
        debug_print_mc(f"🔍 [DECRYPT] Decrypted as UTF-8: \"{decrypted_text}\"")
        
        debug_print_mc(f"✅ [DECRYPT] Successfully decrypted {len(encrypted_bytes)}B → \"{decrypted_text[:50]}{'...' if len(decrypted_text) > 50 else ''}\"")
        return decrypted_text
        
    except Exception as e:
        debug_print_mc(f"❌ [DECRYPT] Decryption failed: {e}")
        return None


def _regroup_path_bytes(path_items):
    """
    Fix for meshcoredecoder library bug: it returns packet.path as a flat list of
    individual bytes (each 0-255) instead of a list of 4-byte little-endian uint32
    node IDs, causing hop counts like 143 for a packet that should show ~35 hops.

    Detection: if every item in path_items is an integer that fits in a single byte
    (value 0-255), we treat the whole list as raw bytes and regroup them as 4-byte
    little-endian uint32 node IDs.  Any trailing bytes that do not form a complete
    4-byte group are discarded.

    If the path already contains values > 255 (i.e. real uint32 node IDs), it is
    returned unchanged.

    Returns (corrected_hop_count: int, regrouped_path: list[int]).
    """
    if not path_items:
        return 0, []

    all_bytes = all(isinstance(n, int) and 0 <= n <= 255 for n in path_items)
    if not all_bytes:
        # Values look like real uint32 node IDs already — nothing to fix.
        return len(path_items), list(path_items)

    # Regroup as 4-byte little-endian uint32 node IDs.
    # Use integer division to determine how many complete 4-byte groups exist,
    # avoiding accidental out-of-range access for odd-length lists.
    node_ids = []
    complete_groups = len(path_items) // 4
    for i in range(0, complete_groups * 4, 4):
        b0, b1, b2, b3 = path_items[i], path_items[i+1], path_items[i+2], path_items[i+3]
        node_ids.append(b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))

    return len(node_ids), node_ids


class MeshCoreCLIWrapper:
    """
    Wrapper pour meshcore-cli library
    
    Utilise la library officielle meshcore-cli si disponible,
    sinon fallback vers implémentation basique
    """
    
    def __init__(self, port, baudrate=115200, debug=None):
        """
        Initialise l'interface MeshCore via meshcore-cli
        
        Args:
            port: Port série (ex: /dev/ttyUSB0)
            baudrate: Vitesse de communication (défaut: 115200)
            debug: Enable debug mode (default: None, uses DEBUG_MODE from config if available)
        """
        self.port = port
        self.baudrate = baudrate
        self.meshcore = None
        self.running = False
        self.message_callback = None
        self.message_thread = None
        self.node_manager = None  # Will be set via set_node_manager()
        
        # Healthcheck tracking
        self.last_message_time = None
        self.connection_healthy = False
        self.healthcheck_interval = 60  # Check every 60 seconds
        self.message_timeout = 300  # Alert if no messages for 5 minutes
        self.healthcheck_thread = None
        
        # Message deduplication tracking
        # Format: {message_hash: {'timestamp': float, 'count': int}}
        # Prevents sending same message multiple times within short window
        self._sent_messages = {}
        self._message_dedup_window = 30  # seconds - prevent duplicates within 30s
        
        # Latest RX_LOG_DATA for channel echo correlation
        # Stores SNR/RSSI/path from the most recent RF packet received
        # Used to attach signal data to CHANNEL_MSG_RECV events (echoes pattern)
        self.latest_rx_log = {}  # {'snr': float, 'rssi': int, 'path_len': int, 'timestamp': float}
        
        # Determine debug mode: explicit parameter > config > False
        if debug is None:
            try:
                import config
                self.debug = getattr(config, 'DEBUG_MODE', False)
            except ImportError:
                self.debug = False
        else:
            self.debug = debug
        
        # Load MeshCore Public channel PSK from config
        try:
            import config
            self.meshcore_public_psk = getattr(config, 'MESHCORE_PUBLIC_PSK', "izOH6cXN6mrJ5e26oRXNcg==")
            debug_print_mc(f"✅ [MESHCORE] PSK chargée depuis config")
        except ImportError:
            # Use default MeshCore Public channel PSK
            self.meshcore_public_psk = "izOH6cXN6mrJ5e26oRXNcg=="
            debug_print_mc(f"ℹ️  [MESHCORE] PSK par défaut utilisée")
        
        # Simulation d'un localNode pour compatibilité
        # Note: 0xFFFFFFFE = unknown local node (NOT broadcast 0xFFFFFFFF)
        # This ensures DMs are not treated as broadcasts when real node ID unavailable
        self.localNode = type('obj', (object,), {
            'nodeNum': 0xFFFFFFFE,  # Non-broadcast ID for companion mode
        })()
        
        if not MESHCORE_CLI_AVAILABLE:
            error_print("❌ [MESHCORE] meshcore-cli non disponible")
            error_print("   Installation: pip install meshcore")
            raise ImportError("meshcore-cli library required")
        
        info_print_mc(f"🔧 Initialisation: {port} (debug={self.debug})")
    
    def connect(self):
        """Établit la connexion avec MeshCore via meshcore-cli"""
        try:
            info_print_mc(f"🔌 Connexion à {self.port}...")
            
            # Créer l'objet MeshCore via factory method async
            # MeshCore utilise des factory methods: create_serial, create_ble, create_tcp
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Créer la connexion série avec la factory method
            self.meshcore = loop.run_until_complete(
                MeshCore.create_serial(self.port, baudrate=self.baudrate, debug=self.debug)
            )
            
            # Sauvegarder l'event loop pour les opérations futures
            self._loop = loop
            
            info_print_mc(f"✅  Device connecté sur {self.port}")
            
            # NOTE: Contact loading removed from connect() to reduce noise
            # Contacts will be synced in the event loop via sync_contacts()
            # This sync is essential for DM decryption but doesn't need to happen
            # twice (once in connect, once in event loop)
            
            # Récupérer le node ID si possible
            try:
                # Essayer de récupérer les infos du device
                # Note: l'API meshcore-cli peut varier selon la version
                if hasattr(self.meshcore, 'node_id'):
                    self.localNode.nodeNum = self.meshcore.node_id
                    info_print_mc(f"   Node ID: 0x{self.localNode.nodeNum:08x}")
            except Exception as e:
                debug_print_mc(f"⚠️ Impossible de récupérer node_id: {e}")
            
            return True
            
        except Exception as e:
            error_print(f"❌ [MC] Erreur connexion: {e}")
            error_print(traceback.format_exc())
            return False
    
    def set_message_callback(self, callback):
        """
        Définit le callback pour les messages reçus
        Compatible avec l'interface Meshtastic
        
        Args:
            callback: Fonction à appeler lors de la réception d'un message
        """
        debug_print_mc(f"📝 Setting message_callback to {callback}")
        self.message_callback = callback
        info_print_mc(f"✅  message_callback set successfully")
    
    def set_node_manager(self, node_manager):
        """
        Set the node manager for pubkey lookups
        
        Args:
            node_manager: NodeManager instance
        """
        self.node_manager = node_manager
        debug_print_mc("✅  NodeManager configuré")

    def fetch_contacts_initial(self):
        """
        Synchronously fetch MeshCore contacts at bot startup and save them to the SQLite DB.

        This mirrors what Meshtastic does with load_nodes_from_sqlite() at startup:
        contacts are retrieved from the device and persisted immediately so that
        /nodesmc (and the CLI bot) can show full, up-to-date results as soon as the
        bot is ready — without waiting for the async event loop to run sync_contacts().

        Must be called AFTER connect() and set_node_manager(), but BEFORE start_reading()
        (so the event loop is not yet running and we can safely use run_until_complete).

        Returns:
            int: Number of contacts saved (0 on failure or if not supported)
        """
        if not self.meshcore:
            debug_print_mc("⚠️ [STARTUP] fetch_contacts_initial: pas de connexion meshcore")
            return 0

        if not self.node_manager:
            debug_print_mc("⚠️ [STARTUP] fetch_contacts_initial: node_manager non configuré")
            return 0

        if not hasattr(self.node_manager, 'persistence') or not self.node_manager.persistence:
            debug_print_mc("⚠️ [STARTUP] fetch_contacts_initial: persistence non configurée")
            return 0

        if not hasattr(self, '_loop') or self._loop is None:
            debug_print_mc("⚠️ [STARTUP] fetch_contacts_initial: event loop non disponible")
            return 0

        try:
            debug_print_mc("📋 [STARTUP] Récupération des contacts MeshCore au démarrage...")

            async def _do_fetch():
                contacts = None

                # PRIMARY: commands.get_contacts() is the official API and returns adv_name
                # This is the correct way to get contacts with real names from the device
                if hasattr(self.meshcore, 'commands') and hasattr(self.meshcore.commands, 'get_contacts'):
                    try:
                        result = await self.meshcore.commands.get_contacts()
                        # Result is an Event; payload is the contacts dict {pubkey_prefix: contact_dict}
                        if result is not None:
                            # Check for error event type if EventType is available
                            is_error = False
                            if EventType is not None and hasattr(result, 'type'):
                                is_error = (result.type == EventType.ERROR)
                            if not is_error:
                                contacts = result.payload if hasattr(result, 'payload') else result
                                if contacts:
                                    debug_print_mc(f"✅ [STARTUP] {len(contacts)} contacts récupérés via commands.get_contacts()")
                    except Exception as e:
                        debug_print_mc(f"⚠️ [STARTUP] commands.get_contacts() échoué: {e}")

                # FALLBACK: sync_contacts() + self.meshcore.contacts
                if not contacts and hasattr(self.meshcore, 'sync_contacts'):
                    try:
                        await self.meshcore.sync_contacts()
                        contacts = self.meshcore.contacts if hasattr(self.meshcore, 'contacts') else None
                        if contacts:
                            debug_print_mc(f"ℹ️  [STARTUP] {len(contacts)} contacts via sync_contacts() (fallback)")
                    except Exception as e:
                        debug_print_mc(f"⚠️ [STARTUP] sync_contacts() échoué: {e}")

                return contacts

            contacts = self._loop.run_until_complete(_do_fetch())

            if not contacts:
                error_print("⚠️ [STARTUP] Aucun contact MeshCore récupéré au démarrage")
                return 0

            # contacts can be a dict {pubkey_prefix: contact_dict} or a list
            contact_items = contacts.values() if isinstance(contacts, dict) else contacts
            saved_count = 0
            for contact in contact_items:
                try:
                    contact_id = contact.get('contact_id') or contact.get('node_id')
                    # adv_name is the primary name field in meshcore-cli contacts; fall back to name/long_name
                    name = contact.get('adv_name') or contact.get('name') or contact.get('long_name')
                    public_key = contact.get('public_key') or contact.get('publicKey')

                    # Derive contact_id from public_key if not provided
                    if not contact_id and public_key:
                        try:
                            pk_hex = public_key if isinstance(public_key, str) else public_key.hex()
                            if len(pk_hex) >= 8:
                                contact_id = int(pk_hex[:8], 16)
                        except Exception:
                            pass

                    if not contact_id:
                        debug_print_mc("⚠️ [STARTUP] Contact sans ID ignoré")
                        continue

                    # Convert contact_id to int if string
                    if isinstance(contact_id, str):
                        if contact_id.startswith('!'):
                            contact_id = int(contact_id[1:], 16)
                        else:
                            try:
                                contact_id = int(contact_id, 16)
                            except ValueError:
                                contact_id = int(contact_id)

                    best_name = name or f"Node-{contact_id:08x}"
                    contact_data = {
                        'node_id': contact_id,
                        'name': best_name,
                        'shortName': name or best_name,
                        'hwModel': contact.get('hw_model', None),
                        'publicKey': public_key,
                        'lat': contact.get('lat') or contact.get('latitude') or contact.get('adv_lat'),
                        'lon': contact.get('lon') or contact.get('longitude') or contact.get('adv_lon'),
                        'alt': contact.get('alt') or contact.get('altitude'),
                        'source': 'meshcore'
                    }
                    self.node_manager.persistence.save_meshcore_contact(contact_data)
                    self._add_contact_to_meshcore(contact_data)
                    saved_count += 1
                except Exception as save_err:
                    debug_print_mc(f"⚠️ [STARTUP] Erreur sauvegarde contact: {save_err}")

            info_print_mc(f"✅ [STARTUP] {saved_count} contacts MeshCore chargés")
            return saved_count

        except Exception as e:
            error_print(f"❌ [STARTUP] Erreur fetch_contacts_initial: {e}")
            error_print(traceback.format_exc())
            return 0

    def _add_contact_to_meshcore(self, contact_data):
        """
        Add a contact to meshcore's internal contact list
        
        This is CRITICAL for get_contact_by_key_prefix() to work when sending responses.
        The method searches self.meshcore.contacts dict, not the database.
        
        Args:
            contact_data: Dict with node_id, name, publicKey, etc.
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        if not self.meshcore or not hasattr(self.meshcore, 'contacts'):
            debug_print_mc("⚠️ [MESHCORE-DM] meshcore.contacts non disponible")
            return False
        
        try:
            # Extract pubkey_prefix from publicKey
            public_key = contact_data.get('publicKey')
            if not public_key:
                debug_print_mc("⚠️ [MESHCORE-DM] Pas de publicKey dans contact_data")
                return False
            
            # Convert publicKey to hex string if it's bytes
            if isinstance(public_key, bytes):
                pubkey_hex = public_key.hex()
            elif isinstance(public_key, str):
                pubkey_hex = public_key
            else:
                debug_print_mc(f"⚠️ [DM] Type publicKey non supporté: {type(public_key)}")
                return False
            
            # Extract first 12 hex chars (6 bytes) = pubkey_prefix
            pubkey_prefix = pubkey_hex[:12]
            
            # Create contact dict compatible with meshcore format
            # CRITICAL: meshcore-cli expects 'public_key' (snake_case), not 'publicKey' (camelCase)
            # CRITICAL: meshcore-cli expects hex string, not bytes (calls fromhex() internally)
            contact = {
                'node_id': contact_data['node_id'],
                'adv_name': contact_data.get('name', f"Node-{contact_data['node_id']:08x}"),
                'public_key': pubkey_hex,  # Already a hex string (converted above)
            }
            
            # Initialize contacts dict if needed
            if self.meshcore.contacts is None:
                self.meshcore.contacts = {}
            
            # Add to internal dict
            self.meshcore.contacts[pubkey_prefix] = contact
            return True
            
        except Exception as e:
            debug_print_mc(f"⚠️ [DM] Erreur ajout contact à meshcore: {e}")
            return False
    
    def query_contact_by_pubkey_prefix(self, pubkey_prefix):
        """
        Query meshcore-cli for a contact by public key prefix
        
        This method:
        1. Queries meshcore's internal contact database
        2. Extracts contact information (node_id, name, publicKey)
        3. Adds the contact to node_manager for future lookups
        4. Returns the node_id
        
        Args:
            pubkey_prefix: Hex string prefix of the public key
            
        Returns:
            int: node_id if found and added, None otherwise
        """
        if not self.meshcore:
            debug_print_mc("⚠️ [MESHCORE-QUERY] No meshcore connection available")
            return None
        
        if not self.node_manager:
            debug_print_mc("⚠️ [MESHCORE-QUERY] No node_manager configured")
            return None
        
        try:
            debug_print_mc(f"🔍 [QUERY] Recherche contact avec pubkey_prefix: {pubkey_prefix}")
            
            # Ensure contacts are loaded
            # CRITICAL FIX: Actually call ensure_contacts() to load contacts from device
            # NOTE: meshcore-cli may populate contacts asynchronously, so we check if they're
            # already loaded before calling ensure_contacts()
            
            # First, try to flush any pending contacts
            if hasattr(self.meshcore, 'flush_pending_contacts') and callable(self.meshcore.flush_pending_contacts):
                try:
                    debug_print_mc(f"🔄 [QUERY] Appel flush_pending_contacts() pour finaliser les contacts en attente...")
                    self.meshcore.flush_pending_contacts()
                    debug_print_mc(f"✅ [QUERY] flush_pending_contacts() terminé")
                except Exception as flush_err:
                    debug_print_mc(f"⚠️ [QUERY] Erreur flush_pending_contacts(): {flush_err}")
            
            # Check if contacts are already loaded (may have been populated during connection)
            initial_count = 0
            if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                initial_count = len(self.meshcore.contacts)
                debug_print_mc(f"📊 [QUERY] Contacts déjà disponibles: {initial_count}")
            
            # If no contacts yet, try to load them
            if initial_count == 0 and hasattr(self.meshcore, 'ensure_contacts'):
                debug_print_mc(f"🔄 [QUERY] Appel ensure_contacts() pour charger les contacts...")
                try:
                    # Call ensure_contacts() - it will load contacts if not already loaded
                    if asyncio.iscoroutinefunction(self.meshcore.ensure_contacts):
                        # It's async - DON'T use run_coroutine_threadsafe as it hangs
                        # Instead, just mark contacts as dirty and they'll load in background
                        debug_print_mc(f"⚠️ [QUERY] ensure_contacts() est async - impossible d'appeler depuis ce contexte")
                        debug_print_mc(f"💡 [QUERY] Les contacts se chargeront en arrière-plan")
                        
                        # Try to mark contacts as dirty to trigger reload
                        # FIX: contacts_dirty is a read-only property, use private attribute _contacts_dirty instead
                        if hasattr(self.meshcore, '_contacts_dirty'):
                            self.meshcore._contacts_dirty = True
                            debug_print_mc(f"🔄 [QUERY] _contacts_dirty défini à True pour forcer le rechargement")
                        elif hasattr(self.meshcore, 'contacts_dirty'):
                            # Fallback: try the property (may fail if read-only)
                            try:
                                self.meshcore.contacts_dirty = True
                                debug_print_mc(f"🔄 [QUERY] contacts_dirty défini à True pour forcer le rechargement")
                            except AttributeError as e:
                                debug_print_mc(f"⚠️ [QUERY] Impossible de définir contacts_dirty: {e}")
                    else:
                        # It's synchronous - just call it
                        self.meshcore.ensure_contacts()
                        debug_print_mc(f"✅ [QUERY] ensure_contacts() terminé")
                except Exception as ensure_err:
                    error_print(f"⚠️ [MESHCORE-QUERY] Erreur ensure_contacts(): {ensure_err}")
                    error_print(traceback.format_exc())
                
                # Try flush again after ensure_contacts
                if hasattr(self.meshcore, 'flush_pending_contacts') and callable(self.meshcore.flush_pending_contacts):
                    try:
                        self.meshcore.flush_pending_contacts()
                        debug_print_mc(f"✅ [QUERY] flush_pending_contacts() après ensure_contacts")
                    except Exception as flush_err:
                        debug_print_mc(f"⚠️ [QUERY] Erreur flush après ensure: {flush_err}")
                
                # Check again if contacts are now available
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts is None:
                    debug_print_mc(f"⚠️ [QUERY] Contacts toujours non chargés après ensure_contacts()")
                else:
                    debug_print_mc(f"✅ [QUERY] Contacts disponibles après ensure_contacts()")
            elif initial_count > 0:
                debug_print_mc(f"✅ [QUERY] Contacts déjà chargés, pas besoin d'appeler ensure_contacts()")
            else:
                debug_print_mc(f"⚠️ [QUERY] meshcore.ensure_contacts() non disponible")
            
            # Debug: check if meshcore has contacts attribute
            if hasattr(self.meshcore, 'contacts'):
                try:
                    contacts_count = len(self.meshcore.contacts) if self.meshcore.contacts else 0
                    debug_print_mc(f"📊 [QUERY] Nombre de contacts disponibles: {contacts_count}")
                    
                    # Enhanced debug: show why contacts might be empty
                    if contacts_count == 0:
                        debug_print_mc("⚠️ [MESHCORE-QUERY] Base de contacts VIDE - diagnostic:")
                        
                        # Check if sync_contacts was called
                        if hasattr(self.meshcore, 'contacts_synced'):
                            debug_print_mc(f"   contacts_synced flag: {self.meshcore.contacts_synced}")
                        
                        # Check for alternative contact access methods
                        alt_methods = ['get_contacts', 'list_contacts', 'contacts_list', 'contact_list']
                        found_methods = [m for m in alt_methods if hasattr(self.meshcore, m)]
                        if found_methods:
                            debug_print_mc(f"   Méthodes alternatives disponibles: {', '.join(found_methods)}")
                            
                            # Try alternative methods to get contacts
                            for method_name in found_methods:
                                try:
                                    method = getattr(self.meshcore, method_name)
                                    if callable(method):
                                        debug_print_mc(f"   Tentative {method_name}()...")
                                        # Don't call async methods here
                                        if not asyncio.iscoroutinefunction(method):
                                            result = method()
                                            debug_print_mc(f"   → {method_name}() retourne: {type(result).__name__} (len={len(result) if result else 0})")
                                except Exception as alt_err:
                                    debug_print_mc(f"   → Erreur {method_name}(): {alt_err}")
                        
                        # Check meshcore object attributes
                        debug_print_mc("   Attributs meshcore disponibles:")
                        relevant_attrs = [attr for attr in dir(self.meshcore) if 'contact' in attr.lower() or 'key' in attr.lower()]
                        for attr in relevant_attrs[:10]:  # Show first 10
                            try:
                                value = getattr(self.meshcore, attr)
                                debug_print_mc(f"      • {attr}: {type(value).__name__}")
                            except:
                                pass
                    
                except Exception as ce:
                    debug_print_mc(f"⚠️ [QUERY] Impossible de compter les contacts: {ce}")
            
            # Query meshcore for contact by pubkey prefix
            contact = None
            if hasattr(self.meshcore, 'get_contact_by_key_prefix'):
                debug_print_mc(f"🔍 [QUERY] Appel get_contact_by_key_prefix('{pubkey_prefix}')...")
                contact = self.meshcore.get_contact_by_key_prefix(pubkey_prefix)
                debug_print_mc(f"📋 [QUERY] Résultat: {type(contact).__name__} = {contact}")
            else:
                error_print(f"❌ [MESHCORE-QUERY] meshcore.get_contact_by_key_prefix() non disponible")
                error_print(f"   → Vérifier version meshcore-cli (besoin >= 2.2.5)")
                return None
            
            if not contact:
                debug_print_mc(f"⚠️ [QUERY] Aucun contact trouvé pour pubkey_prefix: {pubkey_prefix}")
                # Debug: list available pubkey prefixes
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    try:
                        debug_print_mc(f"🔑 [MESHCORE-QUERY] Préfixes de clés disponibles:")
                        contact_list = list(self.meshcore.contacts)[:5] if hasattr(self.meshcore.contacts, '__iter__') else []
                        for i, c in enumerate(contact_list):  # Show first 5
                            cpk = c.get('public_key', '') or c.get('publicKey', '')
                            if cpk:
                                if isinstance(cpk, bytes):
                                    prefix = cpk.hex()[:12]
                                elif isinstance(cpk, str):
                                    import base64
                                    try:
                                        decoded = base64.b64decode(cpk)
                                        prefix = decoded.hex()[:12]
                                    except:
                                        prefix = cpk[:12]
                                debug_print_mc(f"   {i+1}. {prefix}... (nom: {c.get('name', 'unknown')})")
                    except Exception as debug_err:
                        debug_print_mc(f"⚠️ [QUERY] Erreur debug contacts: {debug_err}")
                return None
            
            # Extract contact information
            # MeshCore contact dict structure (from meshcore-cli):
            # - public_key: full hex string (64 chars = 32 bytes)
            # - adv_name: advertised name
            # - adv_lat, adv_lon: GPS coordinates
            # - type, flags, out_path_len, out_path, last_advert, lastmod
            #
            # The contact_id/node_id is NOT provided directly, we need to derive it
            # from the public_key prefix (first 4 bytes = first 8 hex chars)
            
            contact_id = contact.get('contact_id') or contact.get('node_id')
            name = contact.get('name') or contact.get('long_name') or contact.get('adv_name')
            public_key = contact.get('public_key') or contact.get('publicKey')
            
            # If contact_id not provided, derive it from public_key prefix
            if not contact_id and public_key:
                # public_key is a hex string, first 4 bytes (8 hex chars) = node_id
                # Example: '143bcd7f1b1f...' -> node_id = 0x143bcd7f
                try:
                    if isinstance(public_key, str) and len(public_key) >= 8:
                        # Extract first 4 bytes (8 hex chars) as node_id
                        contact_id = int(public_key[:8], 16)
                        debug_print_mc(f"🔑 [MESHCORE-QUERY] Node ID dérivé du public_key: 0x{contact_id:08x}")
                    elif isinstance(public_key, bytes) and len(public_key) >= 4:
                        # If public_key is bytes, extract first 4 bytes
                        contact_id = int.from_bytes(public_key[:4], 'big')
                        debug_print_mc(f"🔑 [MESHCORE-QUERY] Node ID dérivé du public_key: 0x{contact_id:08x}")
                except Exception as pk_err:
                    debug_print_mc(f"⚠️ [QUERY] Erreur extraction node_id depuis public_key: {pk_err}")
            
            if not contact_id:
                debug_print_mc("⚠️ [MESHCORE-QUERY] Contact trouvé mais pas de contact_id et impossible de dériver du public_key")
                return None
            
            # Convert contact_id to int if it's a string
            if isinstance(contact_id, str):
                if contact_id.startswith('!'):
                    contact_id = int(contact_id[1:], 16)
                else:
                    try:
                        contact_id = int(contact_id, 16)
                    except ValueError:
                        contact_id = int(contact_id)
            
            debug_print_mc(f"✅ [QUERY] Contact trouvé: {name or 'Unknown'} (0x{contact_id:08x})")
            
            # Extract GPS coordinates from meshcore contact (uses adv_lat/adv_lon fields)
            lat = contact.get('lat') or contact.get('latitude') or contact.get('adv_lat')
            lon = contact.get('lon') or contact.get('longitude') or contact.get('adv_lon')
            alt = contact.get('alt') or contact.get('altitude')
            
            # Save to SQLite meshcore_contacts table (separate from Meshtastic nodes)
            if hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                # Use the extracted name for both name and shortName
                # This ensures the display logic can find the real name
                best_name = name or f"Node-{contact_id:08x}"
                contact_data = {
                    'node_id': contact_id,
                    'name': best_name,
                    'shortName': name or '',  # Use extracted name, not short_name field
                    'hwModel': contact.get('hw_model', None),
                    'publicKey': public_key,
                    'lat': lat,
                    'lon': lon,
                    'alt': alt,
                    'source': 'meshcore'
                }
                self.node_manager.persistence.save_meshcore_contact(contact_data)
                # CRITICAL: Also add to meshcore.contacts dict for get_contact_by_key_prefix() to work
                self._add_contact_to_meshcore(contact_data)
                debug_print_mc(f"💾 [QUERY] Contact sauvegardé: {name}")
            else:
                # Fallback to in-memory storage if SQLite not available
                if contact_id not in self.node_manager.node_names:
                    best_name = name or f"Node-{contact_id:08x}"
                    self.node_manager.node_names[contact_id] = {
                        'name': best_name,
                        'shortName': name or '',  # Use extracted name, not short_name field
                        'hwModel': contact.get('hw_model', None),
                        'lat': None,
                        'lon': None,
                        'alt': None,
                        'last_update': None,
                        'publicKey': public_key  # Store public key for future lookups
                    }
                    
                    # Data is automatically saved to SQLite via persistence
                    info_print_mc(f"💾 [MESHCORE-QUERY] Contact ajouté à la base SQLite: {name}")
                else:
                    # Update publicKey if not present
                    if public_key and not self.node_manager.node_names[contact_id].get('publicKey'):
                        self.node_manager.node_names[contact_id]['publicKey'] = public_key
                        # Data is automatically saved to SQLite via persistence
                        debug_print_mc(f"💾 [QUERY] PublicKey ajouté: {name}")
            
            return contact_id
            
        except Exception as e:
            error_print(f"❌ [MESHCORE-QUERY] Erreur recherche contact: {e}")
            error_print(traceback.format_exc())
            return None
    
    def _validate_key_pair(self, private_key_data, public_key_data=None):
        """
        Validate that a private key can derive the expected public key
        
        Args:
            private_key_data: Private key as bytes, hex string, or base64 string
            public_key_data: Optional expected public key for comparison
            
        Returns:
            tuple: (is_valid: bool, derived_public_key: bytes or None, error_message: str or None)
        """
        if not NACL_AVAILABLE:
            return (None, None, "PyNaCl non disponible - installer avec: pip install PyNaCl")
        
        try:
            import base64
            
            # Parse private key
            private_key_bytes = None
            
            if isinstance(private_key_data, bytes):
                private_key_bytes = private_key_data
            elif isinstance(private_key_data, str):
                # Try hex first
                try:
                    if len(private_key_data) == 64:  # 32 bytes in hex = 64 chars
                        private_key_bytes = bytes.fromhex(private_key_data)
                    elif len(private_key_data) == 128:  # 64 bytes in hex (priv+pub)
                        private_key_bytes = bytes.fromhex(private_key_data[:64])  # First 32 bytes
                except ValueError:
                    pass
                
                # Try base64 if hex failed
                if private_key_bytes is None:
                    try:
                        decoded = base64.b64decode(private_key_data)
                        if len(decoded) >= 32:
                            private_key_bytes = decoded[:32]  # First 32 bytes
                    except Exception:
                        pass
            
            if private_key_bytes is None or len(private_key_bytes) != 32:
                return (False, None, f"Clé privée invalide (doit être 32 octets, reçu: {len(private_key_bytes) if private_key_bytes else 0})")
            
            # Create Curve25519 private key object
            private_key = nacl.public.PrivateKey(private_key_bytes)
            
            # Derive public key
            derived_public_key = private_key.public_key
            derived_public_key_bytes = bytes(derived_public_key)
            
            # If expected public key provided, compare
            if public_key_data is not None:
                # Parse expected public key
                expected_public_key_bytes = None
                
                if isinstance(public_key_data, bytes):
                    expected_public_key_bytes = public_key_data
                elif isinstance(public_key_data, str):
                    # Try hex
                    try:
                        if len(public_key_data) == 64:  # 32 bytes in hex
                            expected_public_key_bytes = bytes.fromhex(public_key_data)
                    except ValueError:
                        pass
                    
                    # Try base64
                    if expected_public_key_bytes is None:
                        try:
                            expected_public_key_bytes = base64.b64decode(public_key_data)
                        except Exception:
                            pass
                
                if expected_public_key_bytes and len(expected_public_key_bytes) >= 32:
                    expected_public_key_bytes = expected_public_key_bytes[:32]
                    
                    # Compare keys
                    if derived_public_key_bytes == expected_public_key_bytes:
                        return (True, derived_public_key_bytes, None)
                    else:
                        derived_hex = derived_public_key_bytes.hex()[:16]
                        expected_hex = expected_public_key_bytes.hex()[:16]
                        return (False, derived_public_key_bytes, 
                               f"Clé publique ne correspond pas! Dérivée: {derived_hex}... vs Attendue: {expected_hex}...")
            
            # No comparison needed, just validate derivation worked
            return (True, derived_public_key_bytes, None)
            
        except Exception as e:
            return (False, None, f"Erreur validation clé: {e}")
    
    async def _check_configuration(self):
        """Check MeshCore configuration and report potential issues"""
        info_print_mc("\n" + "="*60)
        info_print_mc("🔍 [MESHCORE-CLI] Diagnostic de configuration")
        info_print_mc("="*60)
        
        issues_found = []
        
        # Check 1: Private key access
        debug_print_mc("\n1️⃣  Vérification clé privée...")
        has_private_key = False
        try:
            key_attrs = ['private_key', 'key', 'node_key', 'device_key', 'crypto']
            found_key_attrs = [attr for attr in key_attrs if hasattr(self.meshcore, attr)]
            
            if found_key_attrs:
                info_print_mc(f"   ✅ Attributs clé trouvés: {', '.join(found_key_attrs)}")
                has_private_key = True
                
                for attr in found_key_attrs:
                    try:
                        value = getattr(self.meshcore, attr)
                        if value is None:
                            error_print(f"   ⚠️  {attr} est None")
                            issues_found.append(f"{attr} est None - le déchiffrement peut échouer")
                        else:
                            debug_print_mc(f"   ✅ {attr} est défini")
                    except Exception as e:
                        error_print(f"   ⚠️  Impossible d'accéder à {attr}: {e}")
            else:
                error_print("   ⚠️  Aucun attribut de clé privée trouvé en mémoire")
            
            # Check for private key files
            import os
            import glob
            key_file_patterns = ['*.priv', 'private_key*', 'node_key*', '*_priv.key']
            found_key_files = []
            for pattern in key_file_patterns:
                files = glob.glob(pattern)
                found_key_files.extend(files)
            
            if found_key_files:
                info_print_mc(f"   ✅ Fichier(s) clé privée trouvé(s): {', '.join(found_key_files)}")
                has_private_key = True
                
                # Try to check if files are readable and non-empty
                for key_file in found_key_files:
                    try:
                        if os.path.exists(key_file) and os.path.isfile(key_file):
                            file_size = os.path.getsize(key_file)
                            if file_size > 0:
                                info_print_mc(f"   ✅ {key_file} est lisible ({file_size} octets)")
                            else:
                                error_print(f"   ⚠️  {key_file} est vide")
                                issues_found.append(f"{key_file} est vide - impossible de charger la clé privée")
                    except Exception as e:
                        error_print(f"   ⚠️  Impossible d'accéder à {key_file}: {e}")
            else:
                debug_print_mc("   ℹ️  Aucun fichier de clé privée trouvé dans le répertoire courant")
            
            if not has_private_key:
                issues_found.append("Aucune clé privée trouvée (ni en mémoire ni sous forme de fichier) - les messages chiffrés ne peuvent pas être déchiffrés")
            else:
                # NEW: Validate key pair if PyNaCl is available
                debug_print_mc("\n   🔐 Validation paire de clés privée/publique...")
                if not NACL_AVAILABLE:
                    debug_print_mc("   ℹ️  PyNaCl non disponible - validation de clé ignorée")
                    debug_print_mc("      Installer avec: pip install PyNaCl")
                else:
                    # Try to get private key data for validation
                    private_key_data = None
                    public_key_data = None
                    
                    # Try to get from memory attributes
                    for attr in found_key_attrs:
                        try:
                            value = getattr(self.meshcore, attr)
                            if value is not None:
                                private_key_data = value
                                debug_print_mc(f"   📝 Utilisation de {attr} pour validation")
                                break
                        except Exception:
                            pass
                    
                    # Try to get from key file
                    if private_key_data is None and found_key_files:
                        try:
                            key_file = found_key_files[0]
                            # Read as text first (key files are usually hex or base64 text)
                            with open(key_file, 'r') as f:
                                private_key_data = f.read().strip()
                            debug_print_mc(f"   📝 Utilisation du fichier {key_file} pour validation")
                        except Exception as e:
                            # If text reading fails, try binary
                            try:
                                with open(key_file, 'rb') as f:
                                    private_key_data = f.read()
                                debug_print_mc(f"   📝 Utilisation du fichier {key_file} (binaire) pour validation")
                            except Exception as e2:
                                debug_print_mc(f"   ⚠️  Impossible de lire {key_file}: {e2}")
                    
                    # Try to get public key for comparison
                    if hasattr(self.meshcore, 'public_key'):
                        try:
                            public_key_data = getattr(self.meshcore, 'public_key')
                        except Exception:
                            pass
                    elif hasattr(self.meshcore, 'node_id'):
                        # node_id is derived from first 4 bytes of public key
                        # but we can't reverse it, so just validate derivation works
                        pass
                    
                    if private_key_data is not None:
                        is_valid, derived_public_key, error_msg = self._validate_key_pair(
                            private_key_data, 
                            public_key_data
                        )
                        
                        if is_valid is None:
                            debug_print_mc(f"   ℹ️  {error_msg}")
                        elif is_valid:
                            info_print_mc("   ✅ Clé privée valide - peut dériver une clé publique")
                            if derived_public_key:
                                derived_hex = derived_public_key.hex()
                                info_print_mc(f"   🔑 Clé publique dérivée: {derived_hex[:16]}...{derived_hex[-16:]}")
                                # Derive node_id from public key (first 4 bytes)
                                derived_node_id = int.from_bytes(derived_public_key[:4], 'big')
                                info_print_mc(f"   🆔 Node ID dérivé: 0x{derived_node_id:08x}")
                                
                                # Compare with actual node_id if available
                                if hasattr(self.meshcore, 'node_id'):
                                    actual_node_id = self.meshcore.node_id
                                    if actual_node_id == derived_node_id:
                                        info_print_mc(f"   ✅ Node ID correspond: 0x{actual_node_id:08x}")
                                    else:
                                        error_print(f"   ❌ Node ID ne correspond PAS!")
                                        error_print(f"      Dérivé:  0x{derived_node_id:08x}")
                                        error_print(f"      Actuel:  0x{actual_node_id:08x}")
                                        issues_found.append(f"Node ID dérivé (0x{derived_node_id:08x}) != Node ID actuel (0x{actual_node_id:08x}) - la clé privée ne correspond pas au device!")
                        else:
                            error_print(f"   ❌ Validation de clé échouée: {error_msg}")
                            issues_found.append(f"Validation de paire de clés échouée: {error_msg}")
                    else:
                        debug_print_mc("   ⚠️  Impossible d'obtenir les données de clé privée pour validation")
        except Exception as e:
            error_print(f"   ⚠️  Erreur vérification clé privée: {e}")
            issues_found.append(f"Erreur vérification clé privée: {e}")
        
        # Check 2: Contact sync capability
        debug_print_mc("\n2️⃣  Vérification capacité sync contacts...")
        if hasattr(self.meshcore, 'sync_contacts'):
            debug_print_mc("   ✅ Méthode sync_contacts() disponible")
        else:
            debug_print_mc("   ℹ️  Méthode sync_contacts() NON disponible (fonctionnalité optionnelle)")
            # Note: Not added to issues_found - this is optional, not critical
        
        # Check 3: Auto message fetching
        debug_print_mc("\n3️⃣  Vérification auto message fetching...")
        if hasattr(self.meshcore, 'start_auto_message_fetching'):
            debug_print_mc("   ✅ start_auto_message_fetching() disponible")
        else:
            error_print("   ❌ start_auto_message_fetching() NON disponible")
            issues_found.append("start_auto_message_fetching() non disponible - les messages doivent être récupérés manuellement")
        
        # Check 4: Event dispatcher
        debug_print_mc("\n4️⃣  Vérification event dispatcher...")
        if hasattr(self.meshcore, 'events'):
            debug_print_mc("   ✅ Event dispatcher (events) disponible")
        elif hasattr(self.meshcore, 'dispatcher'):
            debug_print_mc("   ✅ Event dispatcher (dispatcher) disponible")
        else:
            error_print("   ❌ Aucun event dispatcher trouvé")
            issues_found.append("Aucun event dispatcher - les événements ne peuvent pas être reçus")
        
        # Summary
        debug_print_mc("\n" + "="*60)
        if issues_found:
            error_print("⚠️  Problèmes de configuration détectés:")
            for i, issue in enumerate(issues_found, 1):
                error_print(f"   {i}. {issue}")
            error_print("\n💡 Conseils de dépannage:")
            error_print("   • Assurez-vous que le device MeshCore a une clé privée configurée")
            error_print("   • Vérifiez que les contacts sont correctement synchronisés")
            error_print("   • Assurez-vous que auto message fetching est démarré")
            error_print("   • Activez le mode debug pour des logs plus détaillés")
        else:
            debug_print_mc("✅ Aucun problème de configuration détecté")
        debug_print_mc("="*60 + "\n")
        
        return len(issues_found) == 0
    
    async def _verify_contacts(self):
        """Verify that contacts were actually synced"""
        try:
            if hasattr(self.meshcore, 'contacts'):
                contacts = self.meshcore.contacts
                if contacts:
                    debug_print_mc(f"   ✅ {len(contacts)} contact(s) synchronisé(s)")
                else:
                    error_print("   ⚠️  Liste de contacts vide")
                    error_print("      Le déchiffrement des DM peut échouer")
            elif hasattr(self.meshcore, 'get_contacts'):
                contacts = await self.meshcore.get_contacts()
                if contacts:
                    debug_print_mc(f"   ✅ {len(contacts)} contact(s) synchronisé(s)")
                else:
                    error_print("   ⚠️  Liste de contacts vide")
                    error_print("      Le déchiffrement des DM peut échouer")
            else:
                debug_print_mc("   ℹ️  Impossible de vérifier la liste des contacts")
        except Exception as e:
            error_print(f"   ⚠️  Erreur vérification contacts: {e}")
    
    def start_reading(self):
        """Démarre la lecture des messages en arrière-plan"""
        if not self.meshcore:
            error_print("❌ [MESHCORE-CLI] Non connecté, impossible de démarrer la lecture")
            return False
        
        # Subscribe to contact (DM) messages via dispatcher/events
        try:
            # MeshCore uses 'events' attribute for subscriptions
            if hasattr(self.meshcore, 'events'):
                self.meshcore.events.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_message)
                debug_print_mc("✅ Souscription aux messages DM (events.subscribe)")

                # Subscribe to ADVERTISEMENT events to capture/update real contact names
                # MeshCore nodes periodically broadcast their name via advertisements
                if hasattr(EventType, 'ADVERTISEMENT'):
                    self.meshcore.events.subscribe(EventType.ADVERTISEMENT, self._on_advertisement)
                    debug_print_mc("✅ Souscription aux ADVERTISEMENT events (mise à jour noms contacts)")
                
                # Subscribe to CHANNEL_MSG_RECV for decoded public channel messages (with path_len)
                if hasattr(EventType, 'CHANNEL_MSG_RECV'):
                    self.meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_message)
                    debug_print_mc("✅ Souscription aux messages de canal public (CHANNEL_MSG_RECV)")
                else:
                    debug_print_mc("⚠️  EventType.CHANNEL_MSG_RECV non disponible (version meshcore-cli ancienne?)")
                
                # Always subscribe to RX_LOG_DATA for channel echo correlation (SNR/RSSI)
                # RX_LOG_DATA arrives just before CHANNEL_MSG_RECV for the same packet, allowing
                # us to attach SNR/RSSI from the RF layer to the decoded channel message.
                if hasattr(EventType, 'RX_LOG_DATA'):
                    self.meshcore.events.subscribe(EventType.RX_LOG_DATA, self._on_rx_log_data)
                    debug_print_mc("✅ Souscription à RX_LOG_DATA (channel echo: SNR/path correlation)")
                else:
                    debug_print_mc("⚠️  EventType.RX_LOG_DATA non disponible - pas de SNR pour les messages de canal")
                
            elif hasattr(self.meshcore, 'dispatcher'):
                self.meshcore.dispatcher.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_message)
                debug_print_mc("✅ Souscription aux messages DM (dispatcher.subscribe)")

                # Subscribe to ADVERTISEMENT events to capture/update real contact names
                if hasattr(EventType, 'ADVERTISEMENT'):
                    self.meshcore.dispatcher.subscribe(EventType.ADVERTISEMENT, self._on_advertisement)
                    debug_print_mc("✅ Souscription aux ADVERTISEMENT events (mise à jour noms contacts)")
                
                # Subscribe to CHANNEL_MSG_RECV for decoded public channel messages (with path_len)
                if hasattr(EventType, 'CHANNEL_MSG_RECV'):
                    self.meshcore.dispatcher.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_message)
                    debug_print_mc("✅ Souscription aux messages de canal public (CHANNEL_MSG_RECV)")
                else:
                    debug_print_mc("⚠️  EventType.CHANNEL_MSG_RECV non disponible")
                
                # Always subscribe to RX_LOG_DATA for channel echo correlation (SNR/RSSI)
                if hasattr(EventType, 'RX_LOG_DATA'):
                    self.meshcore.dispatcher.subscribe(EventType.RX_LOG_DATA, self._on_rx_log_data)
                    debug_print_mc("✅ Souscription à RX_LOG_DATA (channel echo: SNR/path correlation)")
                else:
                    debug_print_mc("⚠️  EventType.RX_LOG_DATA non disponible - pas de SNR pour les messages de canal")
            else:
                error_print("❌ [MESHCORE-CLI] Ni events ni dispatcher trouvé")
                return False
            
            debug_print_mc(f"[MESHCORE-CLI] MeshCore object: {self.meshcore}")
            debug_print_mc(f"[MESHCORE-CLI] EventType.CONTACT_MSG_RECV: {EventType.CONTACT_MSG_RECV}")
        except Exception as e:
            error_print(f"❌ [MESHCORE-CLI] Erreur souscription: {e}")
            error_print(traceback.format_exc())
            return False
        
        self.running = True
        
        # Lancer une boucle asyncio dans un thread séparé pour traiter les événements
        self.message_thread = threading.Thread(
            target=self._async_event_loop,
            name="MeshCore-CLI-AsyncLoop",
            daemon=True
        )
        self.message_thread.start()
        info_print_mc("✅ Thread événements démarré")
        
        # Start healthcheck monitoring
        self.healthcheck_thread = threading.Thread(
            target=self._healthcheck_monitor,
            name="MeshCore-Healthcheck",
            daemon=True
        )
        self.healthcheck_thread.start()
        info_print_mc("✅ Healthcheck monitoring démarré")
        
        # Initialize last message time
        self.last_message_time = time.time()
        
        return True
    
    def _healthcheck_monitor(self):
        """Monitor meshcore connection health and alert on failures"""
        info_print_mc("🏥 [MESHCORE-HEALTHCHECK] Healthcheck monitoring started")
        
        # Wait for initial connection to stabilize
        time.sleep(300)
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if we've received any messages recently
                if self.last_message_time is not None:
                    time_since_last_message = current_time - self.last_message_time
                    
                    if time_since_last_message > self.message_timeout:
                        if self.connection_healthy:
                            # First time detecting the issue
                            error_print(f"⚠️ [MC] ALERTE HEALTHCHECK: Aucun message reçu depuis {int(time_since_last_message)}s")
                            error_print(f"   [MC] → La connexion au nœud semble perdue")
                            error_print(f"   [MC] → Vérifiez: 1) Le nœud est allumé")
                            error_print(f"   [MC] →          2) Le câble série est connecté ({self.port})")
                            error_print(f"   [MC] →          3) meshcore-cli peut se connecter: meshcore-cli -s {self.port} -b {self.baudrate} chat")
                            self.connection_healthy = False
                    else:
                        # Connection is healthy
                        if not self.connection_healthy:
                            info_print_mc(f"✅ Connexion rétablie (message reçu il y a {int(time_since_last_message)}s)")
                            self.connection_healthy = True
                        
                        if self.debug:
                            debug_print_mc(f"🏥 Healthcheck OK - dernier message: {int(time_since_last_message)}s")
                
                # Sleep until next check
                time.sleep(self.healthcheck_interval)
                
            except Exception as e:
                error_print(f"❌ [MESHCORE-HEALTHCHECK] Erreur: {e}")
                error_print(traceback.format_exc())
                time.sleep(self.healthcheck_interval)
        
        info_print_mc("🏥 [MESHCORE-HEALTHCHECK] Healthcheck monitoring stopped")
    
    def _async_event_loop(self):
        """Boucle asyncio pour gérer les événements MeshCore"""
        info_print_mc("📡 [MESHCORE-CLI] Début écoute événements...")
        
        try:
            # Exécuter la boucle asyncio pour traiter les événements
            # Le dispatcher meshcore a besoin d'une boucle active
            asyncio.set_event_loop(self._loop)
            
            # Créer une coroutine qui tourne tant que running est True
            async def event_loop_task():
                # Run configuration diagnostics
                await self._check_configuration()
                
                # CRITICAL: Sync contacts first to enable CONTACT_MSG_RECV events
                try:
                    # Step 1: sync_contacts() enables DM decryption (key exchange)
                    if hasattr(self.meshcore, 'sync_contacts'):
                        await self.meshcore.sync_contacts()
                        
                        # Check post-sync state
                        if hasattr(self.meshcore, 'contacts'):
                            post_contacts = self.meshcore.contacts
                            post_count = len(post_contacts) if post_contacts else 0
                            
                            # SAVE CONTACTS TO DATABASE (like NODEINFO for Meshtastic)
                            if post_count > 0 and self.node_manager and hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                                saved_count = 0
                                # post_contacts is a dict keyed by pubkey_prefix; iterate .items() to get values
                                contacts_items = post_contacts.items() if isinstance(post_contacts, dict) else enumerate(post_contacts)
                                for _key, contact in contacts_items:
                                    try:
                                        contact_id = contact.get('contact_id') or contact.get('node_id')
                                        # meshcore library stores display name as 'adv_name'
                                        name = contact.get('adv_name') or contact.get('name') or contact.get('long_name')
                                        public_key = contact.get('public_key') or contact.get('publicKey')
                                        
                                        # Derive node_id from public_key prefix when not explicitly provided
                                        if not contact_id and public_key:
                                            try:
                                                if isinstance(public_key, str) and len(public_key) >= 8:
                                                    contact_id = int(public_key[:8], 16)
                                                elif isinstance(public_key, bytes) and len(public_key) >= 4:
                                                    contact_id = int.from_bytes(public_key[:4], 'big')
                                            except Exception:
                                                pass
                                        
                                        if not contact_id:
                                            debug_print_mc(f"⚠️ [MESHCORE-SYNC] Contact sans ID dérivable, ignoré: {name}")
                                            continue
                                        
                                        # Convert contact_id to int if string
                                        if isinstance(contact_id, str):
                                            if contact_id.startswith('!'):
                                                contact_id = int(contact_id[1:], 16)
                                            else:
                                                try:
                                                    contact_id = int(contact_id, 16)
                                                except ValueError:
                                                    contact_id = int(contact_id)
                                        
                                        # Use the extracted name for both name and shortName
                                        best_name = name or f"Node-{contact_id:08x}"
                                        contact_data = {
                                            'node_id': contact_id,
                                            'name': best_name,
                                            'shortName': name or '',
                                            'hwModel': contact.get('hw_model', None),
                                            'publicKey': public_key,
                                            'lat': contact.get('adv_lat') if contact.get('adv_lat') is not None else contact.get('latitude'),
                                            'lon': contact.get('adv_lon') if contact.get('adv_lon') is not None else contact.get('longitude'),
                                            'alt': contact.get('altitude', None),
                                            'source': 'meshcore'
                                        }
                                        self.node_manager.persistence.save_meshcore_contact(contact_data)
                                        # Populate in-memory name cache so get_node_name() resolves immediately
                                        self.node_manager.node_names[contact_id] = {
                                            'name': best_name,
                                            'shortName': name or '',
                                            'hwModel': contact_data['hwModel'],
                                            'lat': contact_data['lat'],
                                            'lon': contact_data['lon'],
                                            'alt': contact_data['alt'],
                                            'last_update': None
                                        }
                                        saved_count += 1
                                    except Exception as save_err:
                                        debug_print_mc(f"⚠️ [MESHCORE-SYNC] Erreur sauvegarde contact: {save_err}")
                                
                                # Single summary line instead of verbose logging
                                debug_print_mc(f"💾 [MESHCORE-SYNC] {saved_count}/{post_count} contacts sauvegardés")
                            elif post_count > 0:
                                # Contacts were synced but save conditions failed - only show in DEBUG
                                debug_print_mc(f"⚠️ [MESHCORE-SYNC] {post_count} contacts synchronisés mais NON SAUVEGARDÉS")
                                if not self.node_manager:
                                    debug_print_mc("   → node_manager non configuré")
                                elif not hasattr(self.node_manager, 'persistence') or not self.node_manager.persistence:
                                    debug_print_mc("   → persistence non configuré")
                            
                            if post_count == 0:
                                # Only warn if no contacts found - important to know
                                error_print("⚠️ [MESHCORE-SYNC] ATTENTION: sync_contacts() n'a trouvé AUCUN contact!")
                                error_print("   → Raisons: mode companion (appairage requis), base vide, ou problème de clé")
                        
                        # Check if contacts were actually synced (silent unless DEBUG)
                        await self._verify_contacts()
                    else:
                        debug_print_mc("ℹ️  [MESHCORE-CLI] sync_contacts() non disponible (fonctionnalité optionnelle)")

                    # Step 2: Use commands.get_contacts() (official API) to get contacts WITH adv_name
                    # This is the correct API for fetching named contacts from the device
                    contacts_to_save = None

                    if hasattr(self.meshcore, 'commands') and hasattr(self.meshcore.commands, 'get_contacts'):
                        try:
                            result = await self.meshcore.commands.get_contacts()
                            is_error = False
                            if EventType is not None and hasattr(result, 'type'):
                                is_error = (result.type == EventType.ERROR)
                            if not is_error:
                                contacts_to_save = result.payload if hasattr(result, 'payload') else result
                                if contacts_to_save:
                                    debug_print_mc(f"📋 [MESHCORE-SYNC] {len(contacts_to_save)} contacts récupérés via commands.get_contacts()")
                        except Exception as e:
                            debug_print_mc(f"⚠️ [MESHCORE-SYNC] commands.get_contacts() échoué: {e}")

                    # Fallback to self.meshcore.contacts if commands API not available
                    if contacts_to_save is None and hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                        contacts_to_save = self.meshcore.contacts
                        debug_print_mc(f"ℹ️  [MESHCORE-SYNC] Utilisation de meshcore.contacts ({len(contacts_to_save)}) en fallback")

                    # Step 3: Save contacts to database
                    if contacts_to_save and self.node_manager and hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                        saved_count = 0
                        # contacts can be a dict {pubkey_prefix: contact_dict} or a list
                        contact_items = contacts_to_save.values() if isinstance(contacts_to_save, dict) else contacts_to_save
                        for contact in contact_items:
                            try:
                                contact_id = contact.get('contact_id') or contact.get('node_id')
                                # adv_name is the primary name field in meshcore-cli contacts; fall back to name/long_name
                                name = contact.get('adv_name') or contact.get('name') or contact.get('long_name')
                                public_key = contact.get('public_key') or contact.get('publicKey')

                                # Derive contact_id from public_key if not provided
                                if not contact_id and public_key:
                                    try:
                                        pk_hex = public_key if isinstance(public_key, str) else public_key.hex()
                                        if len(pk_hex) >= 8:
                                            contact_id = int(pk_hex[:8], 16)
                                    except Exception:
                                        pass

                                if not contact_id:
                                    debug_print_mc(f"⚠️ [MESHCORE-SYNC] Contact sans ID ignoré")
                                    continue

                                # Convert contact_id to int if string
                                if isinstance(contact_id, str):
                                    if contact_id.startswith('!'):
                                        contact_id = int(contact_id[1:], 16)
                                    else:
                                        try:
                                            contact_id = int(contact_id, 16)
                                        except ValueError:
                                            contact_id = int(contact_id)

                                best_name = name or f"Node-{contact_id:08x}"
                                contact_data = {
                                    'node_id': contact_id,
                                    'name': best_name,
                                    'shortName': name or best_name,
                                    'hwModel': contact.get('hw_model', None),
                                    'publicKey': public_key,
                                    'lat': contact.get('lat') or contact.get('latitude') or contact.get('adv_lat'),
                                    'lon': contact.get('lon') or contact.get('longitude') or contact.get('adv_lon'),
                                    'alt': contact.get('alt') or contact.get('altitude'),
                                    'source': 'meshcore'
                                }
                                self.node_manager.persistence.save_meshcore_contact(contact_data)
                                self._add_contact_to_meshcore(contact_data)
                                saved_count += 1
                            except Exception as save_err:
                                debug_print_mc(f"⚠️ [MESHCORE-SYNC] Erreur sauvegarde contact: {save_err}")

                        debug_print_mc(f"💾 [MESHCORE-SYNC] {saved_count}/{len(contacts_to_save)} contacts sauvegardés")
                    elif contacts_to_save is None:
                        error_print("⚠️ [MESHCORE-SYNC] ATTENTION: aucun contact récupéré!")
                        error_print("   → Raisons: mode companion (appairage requis), base vide, ou problème de clé")

                except Exception as e:
                    error_print(f"❌ [MESHCORE-CLI] Erreur sync_contacts: {e}")
                    error_print(traceback.format_exc())
                    error_print("   ⚠️ Le déchiffrement des messages entrants peut échouer")
                
                # CRITICAL: Start auto message fetching to receive events
                try:
                    if hasattr(self.meshcore, 'start_auto_message_fetching'):
                        await self.meshcore.start_auto_message_fetching()
                        debug_print_mc("✅ [MESHCORE-CLI] Auto message fetching démarré")
                    else:
                        info_print_mc("⚠️ [MESHCORE-CLI] start_auto_message_fetching() non disponible")
                        error_print("   ⚠️ Sans auto message fetching, les messages ne seront pas reçus automatiquement")
                except Exception as e:
                    error_print(f"❌ [MESHCORE-CLI] Erreur start_auto_message_fetching: {e}")
                    error_print(traceback.format_exc())
                    error_print("   ⚠️ Les messages peuvent ne pas être reçus automatiquement")
                
                # NOTE: Ne PAS utiliser while self.running ici!
                # La boucle d'événements se termine automatiquement quand on appelle stop()
                # On schedule juste les tâches d'initialisation et on laisse la boucle tourner
            
            # Schedule la coroutine d'initialisation
            self._loop.create_task(event_loop_task())
            
            # Exécuter la boucle d'événements jusqu'à ce qu'elle soit arrêtée
            # CRITICAL FIX: Utiliser run_forever() au lieu de run_until_complete()
            # run_forever() permet au dispatcher meshcore de traiter les événements
            # run_until_complete() bloquait et empêchait les callbacks d'être invoqués
            info_print_mc("🔄 [MESHCORE-CLI] Démarrage boucle d'événements...")
            self._loop.run_forever()
            
        except Exception as e:
            error_print(f"❌ [MESHCORE-CLI] Erreur boucle événements: {e}")
            error_print(traceback.format_exc())
        finally:
            # Cleanup: fermer proprement la boucle
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                # Wait for cancellation
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.close()
            except Exception as cleanup_err:
                debug_print_mc(f"⚠️ [MESHCORE-CLI] Erreur nettoyage loop: {cleanup_err}")
        
        info_print_mc("📡 [MESHCORE-CLI] Arrêt écoute événements")
    
    def _on_contact_message(self, event):
        """
        Callback pour les messages de contact (DM)
        Appelé par le dispatcher de meshcore-cli
        
        Args:
            event: Event object from meshcore dispatcher
        """
        info_print_mc("🔔🔔🔔 [MESHCORE-CLI] _on_contact_message CALLED! Event received!")
        try:
            # Update last message time for healthcheck
            self.last_message_time = time.time()
            self.connection_healthy = True
            
            # Safely log event - don't convert to string as it may contain problematic characters
            try:
                debug_print_mc(f"🔔 [MESHCORE-CLI] Event reçu - type: {type(event).__name__}")
                if hasattr(event, 'type'):
                    debug_print_mc(f"   Event.type: {event.type}")
            except Exception as log_err:
                debug_print_mc(f"🔔 [MESHCORE-CLI] Event reçu (erreur log: {log_err})")
            
            # Extraire les informations de l'événement
            # L'API meshcore fournit un objet event avec payload
            payload = event.payload if hasattr(event, 'payload') else event
            
            # Safely log payload
            try:
                debug_print_mc(f"📦 [MESHCORE-CLI] Payload type: {type(payload).__name__}")
                if isinstance(payload, dict):
                    debug_print_mc(f"📦 [MESHCORE-CLI] Payload keys: {list(payload.keys())}")
                    # Log important fields individually
                    for key in ['type', 'pubkey_prefix', 'contact_id', 'sender_id', 'text']:
                        if key in payload:
                            value = payload[key]
                            if key == 'text':
                                value = value[:50] + '...' if len(str(value)) > 50 else value
                            debug_print_mc(f"   {key}: {value}")
                else:
                    debug_print_mc(f"📦 [MESHCORE-CLI] Payload: {str(payload)[:200]}")
            except Exception as log_err:
                debug_print_mc(f"📦 [MESHCORE-CLI] Payload (erreur log: {log_err})")
            
            # Essayer plusieurs sources pour le sender_id
            sender_id = None
            pubkey_prefix = None
            
            # Méthode 1: Chercher dans payload (dict)
            if isinstance(payload, dict):
                sender_id = payload.get('contact_id') or payload.get('sender_id')
                # FIX: Check multiple field name variants for pubkey_prefix
                # Similar to publicKey vs public_key issue, meshcore-cli may use different naming
                pubkey_prefix = (payload.get('pubkey_prefix') or 
                                payload.get('pubkeyPrefix') or 
                                payload.get('public_key_prefix') or 
                                payload.get('publicKeyPrefix'))
                debug_print_mc(f"📋 [MESHCORE-DM] Payload dict - contact_id: {sender_id}, pubkey_prefix: {pubkey_prefix}")
            
            # Méthode 2: Chercher dans les attributs de l'event
            if sender_id is None and hasattr(event, 'attributes'):
                attributes = event.attributes
                debug_print_mc(f"📋 [MESHCORE-DM] Event attributes: {attributes}")
                if isinstance(attributes, dict):
                    sender_id = attributes.get('contact_id') or attributes.get('sender_id')
                    if pubkey_prefix is None:
                        # FIX: Check multiple field name variants for pubkey_prefix
                        pubkey_prefix = (attributes.get('pubkey_prefix') or 
                                       attributes.get('pubkeyPrefix') or 
                                       attributes.get('public_key_prefix') or 
                                       attributes.get('publicKeyPrefix'))
            
            # Méthode 3: Chercher directement sur l'event
            # IMPORTANT: Check for actual None, not just falsy (to handle MagicMock in tests)
            if sender_id is None and hasattr(event, 'contact_id'):
                attr_value = event.contact_id
                # Only use it if it's actually a valid value (not None, not mock)
                if attr_value is not None and isinstance(attr_value, int):
                    sender_id = attr_value
                    debug_print_mc(f"📋 [MESHCORE-DM] Event direct contact_id: {sender_id}")
            
            # Méthode 3b: Chercher pubkey_prefix directement sur l'event
            if pubkey_prefix is None:
                for attr_name in ['pubkey_prefix', 'pubkeyPrefix', 'public_key_prefix', 'publicKeyPrefix']:
                    if hasattr(event, attr_name):
                        attr_value = getattr(event, attr_name)
                        # Only use if it's a non-empty string
                        if attr_value and isinstance(attr_value, str):
                            pubkey_prefix = attr_value
                            debug_print_mc(f"📋 [MESHCORE-DM] Event direct {attr_name}: {pubkey_prefix}")
                            break
            
            debug_print_mc(f"🔍 [MESHCORE-DM] Après extraction - sender_id: {sender_id}, pubkey_prefix: {pubkey_prefix}")
            
            # Méthode 4: Si sender_id est None mais qu'on a un pubkey_prefix, essayer de le résoudre
            # IMPORTANT: Pour les DMs via meshcore-cli, on recherche SEULEMENT dans meshcore_contacts
            # (pas dans meshtastic_nodes) pour éviter de mélanger les deux sources
            if sender_id is None and pubkey_prefix and self.node_manager:
                debug_print_mc(f"🔍 [MESHCORE-DM] Tentative résolution pubkey_prefix: {pubkey_prefix}")
                
                # First try: lookup in meshcore_contacts ONLY (not meshtastic_nodes)
                sender_id = self.node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
                if sender_id:
                    info_print_mc(f"✅ [MESHCORE-DM] Résolu pubkey_prefix {pubkey_prefix} → 0x{sender_id:08x} (meshcore cache)")
                    
                    # CRITICAL FIX: Load full contact data from DB and add to meshcore.contacts dict
                    # This ensures get_contact_by_key_prefix() can find it when sending responses
                    try:
                        cursor = self.node_manager.persistence.conn.cursor()
                        cursor.execute(
                            "SELECT node_id, name, shortName, hwModel, publicKey, lat, lon, alt, source FROM meshcore_contacts WHERE node_id = ?",
                            (str(sender_id),)
                        )
                        row = cursor.fetchone()
                        if row:
                            contact_data = {
                                'node_id': sender_id,
                                'name': row[1] if row[1] else f"Node-{sender_id:08x}",
                                'shortName': row[2] if row[2] else '',
                                'hwModel': row[3],
                                'publicKey': row[4],  # BLOB
                                'lat': row[5],
                                'lon': row[6],
                                'alt': row[7],
                                'source': row[8] if row[8] else 'meshcore'
                            }
                            # Add to meshcore.contacts dict so get_contact_by_key_prefix() can find it
                            self._add_contact_to_meshcore(contact_data)
                            debug_print_mc(f"💾 [MESHCORE-DM] Contact chargé depuis DB et ajouté au dict")
                    except Exception as load_err:
                        debug_print_mc(f"⚠️ [DM] Erreur chargement contact depuis DB: {load_err}")
                else:
                    # Second try: query meshcore-cli API directly
                    debug_print_mc(f"🔍 [MESHCORE-DM] Pas dans le cache meshcore, interrogation API meshcore-cli...")
                    sender_id = self.query_contact_by_pubkey_prefix(pubkey_prefix)
                    if sender_id:
                        info_print_mc(f"✅ [MESHCORE-DM] Résolu pubkey_prefix {pubkey_prefix} → 0x{sender_id:08x} (meshcore-cli API)")
            
            # Méthode 5: FALLBACK - Derive node_id from pubkey_prefix
            # In MeshCore/Meshtastic, the node_id is the FIRST 4 BYTES of the 32-byte public key
            # If we have a pubkey_prefix (which is a hex string of the public key), we can derive the node_id
            # This allows us to process DMs even when the contact isn't in the device's contact list yet
            if sender_id is None and pubkey_prefix:
                try:
                    debug_print_mc(f"🔑 [MESHCORE-DM] FALLBACK: Dérivation node_id depuis pubkey_prefix")
                    
                    # pubkey_prefix is a hex string (e.g., '143bcd7f1b1f...')
                    # We need the first 8 hex chars (= 4 bytes) for the node_id
                    if len(pubkey_prefix) >= 8:
                        # First 8 hex chars = first 4 bytes = node_id
                        node_id_hex = pubkey_prefix[:8]
                        sender_id = int(node_id_hex, 16)
                        info_print_mc(f"✅ [MESHCORE-DM] Node_id dérivé de pubkey: {pubkey_prefix[:12]}... → 0x{sender_id:08x}")
                        
                        # Save this contact for future reference (even though not in device's contact list)
                        if self.node_manager and hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                            try:
                                # Reconstruct full 32-byte public key from prefix (pad with zeros if needed)
                                # pubkey_prefix might be partial, so we pad to 64 hex chars (32 bytes)
                                full_pubkey_hex = pubkey_prefix + '0' * (64 - len(pubkey_prefix))
                                public_key_bytes = bytes.fromhex(full_pubkey_hex)
                                
                                contact_data = {
                                    'node_id': sender_id,
                                    'name': f"Node-{sender_id:08x}",  # Default name
                                    'shortName': '',  # Empty - let display logic use Node-{hex} fallback
                                    'hwModel': None,
                                    'publicKey': public_key_bytes,
                                    'lat': None,
                                    'lon': None,
                                    'alt': None,
                                    'source': 'meshcore_derived'  # Mark as derived, not synced
                                }
                                self.node_manager.persistence.save_meshcore_contact(contact_data)
                                # CRITICAL: Also add to meshcore.contacts dict
                                self._add_contact_to_meshcore(contact_data)
                                debug_print_mc(f"💾 [MESHCORE-DM] Contact dérivé sauvegardé: 0x{sender_id:08x}")
                            except Exception as save_err:
                                debug_print_mc(f"⚠️ [DM] Erreur sauvegarde contact dérivé: {save_err}")
                    else:
                        debug_print_mc(f"⚠️ [DM] pubkey_prefix trop court pour dériver node_id: {pubkey_prefix}")
                except Exception as derive_err:
                    error_print(f"❌ [MESHCORE-DM] Erreur dérivation node_id: {derive_err}")
                    error_print(traceback.format_exc())
            
            text = payload.get('text', '') if isinstance(payload, dict) else ''
            path_len = payload.get('path_len', 0) if isinstance(payload, dict) else 0
            
            # Log avec gestion de None pour sender_id
            if sender_id is not None:
                info_print_mc(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
            else:
                # Fallback: afficher pubkey_prefix si disponible
                if pubkey_prefix:
                    info_print_mc(f"📬 [MESHCORE-DM] De: {pubkey_prefix} (non résolu) | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
                else:
                    info_print_mc(f"📬 [MESHCORE-DM] De: <inconnu> | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            # Créer un pseudo-packet compatible avec le code existant
            # Si sender_id est toujours None après tous les essais, utiliser 0xFFFFFFFF
            # MAIS marquer le paquet comme DM (pas broadcast) via le champ 'to'
            if sender_id is None:
                sender_id = 0xFFFFFFFF
                # Marquer comme DM en utilisant to=localNode (pas broadcast)
                to_id = self.localNode.nodeNum
                
                # AVERTISSEMENT: Le bot ne pourra pas répondre sans ID de contact valide
                error_print(f"⚠️ [MESHCORE-DM] Expéditeur inconnu (pubkey {pubkey_prefix} non trouvé)")
                error_print(f"   → Le message sera traité mais le bot ne pourra pas répondre")
                error_print(f"   → Pour résoudre: Ajouter le contact dans la base de données")
            else:
                to_id = self.localNode.nodeNum
            
            # Créer un packet avec TOUS les champs nécessaires pour le logging
            import random
            packet = {
                'from': sender_id,
                'to': to_id,  # DM: to our node, not broadcast
                'id': random.randint(100000, 999999),  # ID unique pour déduplication
                'rxTime': int(time.time()),  # Timestamp de réception
                'rssi': 0,  # Pas de métrique radio pour MeshCore
                'snr': 0.0,  # Pas de métrique radio pour MeshCore
                'hopLimit': 0,  # Message direct (pas de relay)
                'hopStart': 0,  # Message direct
                'channel': 0,  # Canal par défaut
                'decoded': {
                    'portnum': 'TEXT_MESSAGE_APP',
                    'payload': text.encode('utf-8')
                },
                '_meshcore_dm': True,  # Marquer comme DM MeshCore pour traitement spécial
                '_meshcore_path_len': path_len  # Nombre de hops du DM
            }
            
            # Appeler le callback
            if self.message_callback:
                info_print_mc(f"📞 [MESHCORE-CLI] Calling message_callback for message from 0x{sender_id:08x}")
                self.message_callback(packet, None)
                info_print_mc(f"✅  Callback completed successfully")
            else:
                error_print(f"⚠️ [MESHCORE-CLI] No message_callback set!")
                
        except Exception as e:
            error_print(f"❌ [MESHCORE-CLI] Erreur traitement message: {e}")
            error_print(traceback.format_exc())
    
    def _parse_meshcore_header(self, hex_string):
        """
        Parse MeshCore packet header to extract sender/receiver information
        
        MeshCore packet structure:
        - Byte 0-3: Message type + version (1 byte type, 3 bytes reserved)
        - Byte 4-7: Sender node ID (4 bytes, little-endian)
        - Byte 8-11: Receiver node ID (4 bytes, little-endian)
        - Byte 12-15: Message hash (4 bytes)
        - Byte 16+: Payload data
        
        Args:
            hex_string: Raw packet hex string
            
        Returns:
            dict with sender_id, receiver_id, msg_hash or None if parsing fails
        """
        if not hex_string or len(hex_string) < 32:  # At least 16 bytes for header
            return None
        
        try:
            # Convert hex to bytes
            data = bytes.fromhex(hex_string)
            
            # Parse header fields
            sender_id = int.from_bytes(data[4:8], 'little')
            receiver_id = int.from_bytes(data[8:12], 'little')
            msg_hash = data[12:16].hex()
            
            return {
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'msg_hash': msg_hash,
            }
        except Exception:
            return None
    
    def _get_node_name(self, node_id):
        """
        Get human-readable name for a node ID from node database
        
        Args:
            node_id: Node ID (integer)
            
        Returns:
            Node name or "Unknown" if not in database
        """
        if not self.node_manager:
            return "Unknown"
        
        try:
            # Try to get node info from node manager
            node_info = self.node_manager.get_node_info(node_id)
            if node_info:
                # Return short name if available, else long name, else hex ID
                return node_info.get('short_name') or node_info.get('long_name') or f"0x{node_id:08x}"
            return f"0x{node_id:08x}"
        except Exception:
            return f"0x{node_id:08x}"

    def _fmt_node(self, node_id):
        """
        Return a compact node label for log output.
        Uses shortName/longName if known, otherwise last 6 hex chars of the ID.
        """
        name = self._get_node_name(node_id)
        # _get_node_name returns "0x{node_id:08x}" for unknown nodes
        if name.startswith("0x") or name == "Unknown":
            return f"{node_id & 0xFFFFFF:06x}"
        # Truncate long real names to keep the log line compact
        return name[:12]

    def _on_channel_message(self, event):
        """
        Callback pour les messages de canal public (CHANNEL_MSG_RECV)
        Permet au bot de traiter les commandes envoyées sur le canal public (ex: /echo)
        
        Args:
            event: Event object from meshcore dispatcher
        """
        info_print_mc("📢 [MESHCORE-CHANNEL] Canal public message reçu!")
        try:
            # Update last message time for healthcheck
            self.last_message_time = time.time()
            self.connection_healthy = True
            
            # Log event structure for debugging
            try:
                debug_print_mc(f"📦 [CHANNEL] Event type: {type(event).__name__}")
                if hasattr(event, 'type'):
                    debug_print_mc(f"   Event.type: {event.type}")
                # Log event attributes if available
                if hasattr(event, '__dict__'):
                    debug_print_mc(f"   Event attributes: {list(event.__dict__.keys())}")
                    # COMPREHENSIVE DEBUG: Log ALL event fields with values
                    for key in event.__dict__.keys():
                        value = getattr(event, key, None)
                        debug_print_mc(f"      event.{key} = {value}")
            except Exception as log_err:
                debug_print_mc(f"📦 [CHANNEL] Event (erreur log: {log_err})")
            
            # Extract event payload
            payload = event.payload if hasattr(event, 'payload') else event
            
            # Log payload structure for debugging
            try:
                debug_print_mc(f"📦 [CHANNEL] Payload type: {type(payload).__name__}")
                if isinstance(payload, dict):
                    debug_print_mc(f"📦 [CHANNEL] Payload keys: {list(payload.keys())}")
                else:
                    debug_print_mc(f"📦 [CHANNEL] Payload: {str(payload)[:200]}")
            except Exception as log_err:
                debug_print_mc(f"📦 [CHANNEL] Payload (erreur log: {log_err})")
            
            # Extract sender_id using multiple fallback methods (like _on_contact_message)
            sender_id = None
            pubkey_prefix = None
            
            # Méthode 1: Chercher dans payload (dict)
            if isinstance(payload, dict):
                sender_id = payload.get('sender_id') or payload.get('contact_id') or payload.get('from')
                # Check for pubkey_prefix (multiple variants like in _on_contact_message)
                pubkey_prefix = (payload.get('pubkey_prefix') or 
                                payload.get('pubkeyPrefix') or 
                                payload.get('public_key_prefix') or 
                                payload.get('publicKeyPrefix'))
                debug_print_mc(f"📋 [CHANNEL] Payload dict - sender_id: {sender_id}, pubkey_prefix: {pubkey_prefix}")
            
            # Méthode 2: Chercher dans les attributs de l'event
            if sender_id is None and hasattr(event, 'attributes'):
                attributes = event.attributes
                debug_print_mc(f"📋 [CHANNEL] Event attributes: {attributes}")
                if isinstance(attributes, dict):
                    sender_id = attributes.get('sender_id') or attributes.get('contact_id') or attributes.get('from')
                    if pubkey_prefix is None:
                        pubkey_prefix = (attributes.get('pubkey_prefix') or 
                                       attributes.get('pubkeyPrefix') or 
                                       attributes.get('public_key_prefix') or 
                                       attributes.get('publicKeyPrefix'))
            
            # Méthode 3: Chercher directement sur l'event
            if sender_id is None:
                for attr_name in ['sender_id', 'contact_id', 'from']:
                    if hasattr(event, attr_name):
                        attr_value = getattr(event, attr_name)
                        # Only use if it's actually a valid value (not None)
                        if attr_value is not None and isinstance(attr_value, int):
                            sender_id = attr_value
                            debug_print_mc(f"📋 [CHANNEL] Event direct {attr_name}: {sender_id}")
                            break
            
            # Méthode 3b: Chercher pubkey_prefix directement sur l'event
            if pubkey_prefix is None:
                for attr_name in ['pubkey_prefix', 'pubkeyPrefix', 'public_key_prefix', 'publicKeyPrefix']:
                    if hasattr(event, attr_name):
                        attr_value = getattr(event, attr_name)
                        # Only use if it's a non-empty string
                        if attr_value and isinstance(attr_value, str):
                            pubkey_prefix = attr_value
                            debug_print_mc(f"📋 [CHANNEL] Event direct {attr_name}: {pubkey_prefix}")
                            break
            
            debug_print_mc(f"🔍 [CHANNEL] Après extraction - sender_id: {sender_id}, pubkey_prefix: {pubkey_prefix}")
            
            # Méthode 4: Si sender_id est None mais qu'on a un pubkey_prefix, essayer de le résoudre
            if sender_id is None and pubkey_prefix and self.node_manager:
                debug_print_mc(f"🔍 [CHANNEL] Tentative résolution pubkey_prefix: {pubkey_prefix}")
                
                # Try to find in meshcore_contacts first (most reliable)
                sender_id = self.node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
                if sender_id:
                    info_print_mc(f"✅ [CHANNEL] Résolu pubkey_prefix {pubkey_prefix} → 0x{sender_id:08x} (meshcore cache)")
                    
                    # Load full contact data from DB and ensure it's in meshcore.contacts dict
                    try:
                        cursor = self.node_manager.persistence.conn.cursor()
                        cursor.execute(
                            "SELECT node_id, name, shortName, hwModel, publicKey, lat, lon, alt, source FROM meshcore_contacts WHERE node_id = ?",
                            (str(sender_id),)
                        )
                        row = cursor.fetchone()
                        if row:
                            contact_data = {
                                'node_id': sender_id,
                                'name': row[1] if row[1] else f"Node-{sender_id:08x}",
                                'shortName': row[2] if row[2] else '',
                                'hwModel': row[3] if row[3] else 'UNKNOWN',
                                'publicKey': row[4] if row[4] else '',
                                'position': {
                                    'latitude': float(row[5]) if row[5] else 0.0,
                                    'longitude': float(row[6]) if row[6] else 0.0,
                                    'altitude': int(row[7]) if row[7] else 0
                                },
                                'source': row[8] if row[8] else 'meshcore'
                            }
                            # Add to meshcore.contacts if meshcore instance exists
                            if hasattr(self, 'meshcore') and self.meshcore and hasattr(self.meshcore, 'contacts'):
                                pubkey_key = row[4][:12] if row[4] else pubkey_prefix
                                self.meshcore.contacts[pubkey_key] = contact_data
                                debug_print_mc(f"✅ [CHANNEL] Contact ajouté à meshcore.contacts: {pubkey_key}")
                    except Exception as db_err:
                        debug_print_mc(f"⚠️ [CHANNEL] Erreur lors du chargement contact DB: {db_err}")
                else:
                    # Fallback: try to derive node_id from pubkey_prefix (first 4 bytes as hex)
                    try:
                        if len(pubkey_prefix) >= 8:
                            sender_id = int(pubkey_prefix[:8], 16)
                            info_print_mc(f"⚡ [CHANNEL] Node_id dérivé de pubkey_prefix: {pubkey_prefix} → 0x{sender_id:08x}")
                        else:
                            debug_print_mc(f"⚠️ [CHANNEL] pubkey_prefix trop court pour dérivation: {pubkey_prefix}")
                    except ValueError as e:
                        debug_print_mc(f"⚠️ [CHANNEL] Erreur dérivation node_id: {e}")
            
            # Extract channel index (default to 0 for public channel)
            # Try multiple field names for channel
            if isinstance(payload, dict):
                channel_index = payload.get('channel') or payload.get('chan') or payload.get('channel_idx') or 0
            else:
                channel_index = 0
            
            # Extract path_len from CHANNEL_MSG_RECV payload (number of hops)
            # This is provided directly by the meshcore library in the event payload.
            # Use `or 0` to handle the case where path_len is present but set to None.
            if isinstance(payload, dict):
                channel_path_len = payload.get('path_len') or 0
            else:
                channel_path_len = getattr(payload, 'path_len', None) or 0
            
            # Get SNR/RSSI from latest_rx_log (channel echo correlation)
            # RX_LOG_DATA arrives just before CHANNEL_MSG_RECV for the same packet.
            # Only use if the RX_LOG was recent (within 2 seconds).
            echo_snr = 0.0
            echo_rssi = 0
            if self.latest_rx_log and (time.time() - self.latest_rx_log.get('timestamp', 0)) < 2.0:
                echo_snr = self.latest_rx_log.get('snr', 0.0)
                echo_rssi = self.latest_rx_log.get('rssi', 0)
                # Use decoder path_len if CHANNEL_MSG_RECV didn't provide one
                if not channel_path_len:
                    channel_path_len = self.latest_rx_log.get('path_len', 0)
                debug_print_mc(f"📡 [CHANNEL-ECHO] SNR:{echo_snr}dB RSSI:{echo_rssi}dBm Hops:{channel_path_len}")
            
            # Extract message text
            if isinstance(payload, dict):
                message_text = payload.get('text') or payload.get('message') or payload.get('msg') or ''
            else:
                # Try to get text from event directly if payload is not dict
                message_text = getattr(event, 'text', '') or getattr(payload, 'text', '') if hasattr(payload, 'text') else ''
            
            if not message_text:
                debug_print_mc("⚠️ [CHANNEL] Message vide, ignoré")
                return
            
            # Méthode 5: FALLBACK - For Public channel messages, if sender_id still None after pubkey_prefix,
            # try to extract sender from message prefix "SenderName: message"
            # NOTE: This is unreliable when multiple nodes have similar names, so pubkey_prefix is preferred
            if sender_id is None:
                # Try to extract sender name from message text prefix
                if ': ' in message_text:
                    sender_name = message_text.split(': ', 1)[0]
                    debug_print_mc(f"📝 [CHANNEL] Extracted sender name from prefix: '{sender_name}'")
                    
                    # Look up sender's node ID by name if node_manager is available
                    if self.node_manager:
                        try:
                            # Search for node by name (partial match)
                            matching_nodes = []
                            sender_name_lower = sender_name.lower()
                            for node_id, name_info in self.node_manager.node_names.items():
                                if isinstance(name_info, dict):
                                    node_name = name_info.get('name', '').lower()
                                else:
                                    node_name = str(name_info).lower()
                                
                                if sender_name_lower in node_name or node_name in sender_name_lower:
                                    matching_nodes.append((node_id, name_info))
                            
                            if len(matching_nodes) == 1:
                                sender_id = matching_nodes[0][0]
                                debug_print_mc(f"✅ [CHANNEL] Found sender ID by name: 0x{sender_id:08x}")
                            elif len(matching_nodes) > 1:
                                debug_print_mc(f"⚠️ [CHANNEL] Multiple nodes match '{sender_name}', using first")
                                sender_id = matching_nodes[0][0]
                            else:
                                debug_print_mc(f"⚠️ [CHANNEL] No node found matching '{sender_name}'")
                        except Exception as e:
                            debug_print_mc(f"⚠️ [CHANNEL] Error looking up sender: {e}")
                
                # If still no sender_id, use broadcast address
                if sender_id is None:
                    sender_id = 0xFFFFFFFF
                    debug_print_mc("📢 [CHANNEL] Using broadcast sender ID (0xFFFFFFFF) - sender unknown")
            
            # Log the channel message
            info_print_mc(f"📢 [CHANNEL] Message de 0x{sender_id:08x} sur canal {channel_index}: {message_text[:50]}{'...' if len(message_text) > 50 else ''}")
            if echo_snr or echo_rssi:
                debug_print_mc(f"   📶 SNR:{echo_snr}dB RSSI:{echo_rssi}dBm Hops:{channel_path_len}")
            
            # Convert to bot-compatible packet format
            # CRITICAL: Set to_id=0xFFFFFFFF so message is recognized as broadcast by message_router.py
            packet = {
                'from': sender_id,
                'to': 0xFFFFFFFF,  # Broadcast address - critical for routing
                'snr': echo_snr,           # From channel echo (RX_LOG correlation)
                'rssi': echo_rssi,         # From channel echo (RX_LOG correlation)
                'hopLimit': 0,             # Received: 0 hops remaining
                'hopStart': channel_path_len,  # Total hops taken (from CHANNEL_MSG_RECV or RX_LOG)
                'decoded': {
                    'portnum': 'TEXT_MESSAGE_APP',
                    'payload': message_text.encode('utf-8')
                },
                'channel': channel_index,
                '_meshcore_dm': False,             # NOT a DM - this is a public channel message
                '_meshcore_path_len': channel_path_len  # Path length for rx_history
            }
            
            decoded = packet['decoded']
            
            # Forward to bot's message_callback if registered
            if self.message_callback:
                debug_print_mc(f"📤 [CHANNEL] Forwarding to bot callback: {message_text[:30]}...")
                try:
                    self.message_callback(packet, self)
                    info_print_mc(f"✅ [CHANNEL] Message transmis au bot pour traitement")
                except Exception as fwd_err:
                    error_print(f"❌ [CHANNEL] Erreur transmission au bot: {fwd_err}")
                    error_print(traceback.format_exc())
            else:
                debug_print_mc("⚠️ [CHANNEL] Pas de callback message_callback enregistré")
        
        except Exception as e:
            error_print(f"❌ [MESHCORE-CHANNEL] Erreur traitement message de canal: {e}")
            error_print(traceback.format_exc())

    def _on_advertisement(self, event):
        """
        Callback pour les événements ADVERTISEMENT (annonces de nœuds MeshCore).

        MeshCore nodes periodically broadcast their name, GPS position, and public key
        via advertisement packets.  This event is the *primary* source of real contact
        names on the mesh and is used to keep the SQLite DB up-to-date so that
        /nodesmc always shows human-readable names.

        Args:
            event: Event object from meshcore dispatcher
        """
        try:
            payload = event.payload if hasattr(event, 'payload') else event
            if not isinstance(payload, dict):
                debug_print_mc(f"⚠️ [ADVERT] Payload non-dict: {type(payload).__name__}")
                return

            # Extract name — adv_name is the canonical field in meshcore-cli advertisements
            adv_name = payload.get('adv_name') or payload.get('name') or payload.get('long_name')
            public_key = payload.get('public_key') or payload.get('publicKey')

            if not adv_name and not public_key:
                debug_print_mc("⚠️ [ADVERT] Pas de nom ni de clé dans l'événement, ignoré")
                return

            # Derive contact_id (= first 4 bytes of public_key)
            contact_id = payload.get('node_id') or payload.get('contact_id')
            if not contact_id and public_key:
                try:
                    pk_hex = public_key if isinstance(public_key, str) else public_key.hex()
                    if len(pk_hex) >= 8:
                        contact_id = int(pk_hex[:8], 16)
                except Exception:
                    pass

            if not contact_id:
                debug_print_mc("⚠️ [ADVERT] Impossible de dériver l'ID depuis la clé publique, ignoré")
                return

            if isinstance(contact_id, str):
                try:
                    contact_id = int(contact_id, 16) if not contact_id.startswith('!') else int(contact_id[1:], 16)
                except ValueError:
                    contact_id = int(contact_id)

            if not adv_name:
                # No name — nothing useful to update
                return

            info_print_mc(f"📡 [ADVERT] {adv_name} (0x{contact_id:08x}) - mise à jour en base")

            if self.node_manager and hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                contact_data = {
                    'node_id': contact_id,
                    'name': adv_name,
                    'shortName': adv_name,
                    'hwModel': payload.get('hw_model') or payload.get('hwModel'),
                    'publicKey': public_key,
                    'lat': payload.get('adv_lat') or payload.get('lat') or payload.get('latitude'),
                    'lon': payload.get('adv_lon') or payload.get('lon') or payload.get('longitude'),
                    'alt': payload.get('alt') or payload.get('altitude'),
                    'source': 'meshcore'
                }
                self.node_manager.persistence.save_meshcore_contact(contact_data)
                debug_print_mc(f"✅ [ADVERT] Contact sauvegardé: {adv_name} (0x{contact_id:08x})")

                # Also update in-memory node_names for consistent display
                if hasattr(self.node_manager, 'node_names'):
                    self.node_manager.node_names[contact_id] = {
                        'name': adv_name,
                        'shortName': adv_name,
                        'publicKey': public_key,
                    }

        except Exception as e:
            error_print(f"❌ [MESHCORE-ADVERT] Erreur traitement advertisement: {e}")
            error_print(traceback.format_exc())

    def _on_rx_log_data(self, event):
        """
        Callback pour les événements RX_LOG_DATA (données RF brutes)
        Permet de voir TOUS les paquets mesh (broadcasts, télémétrie, etc.)
        
        Utilise meshcore-decoder pour décoder les paquets et afficher
        le type, la famille et d'autres informations utiles pour le debug.
        
        Args:
            event: Event object from meshcore dispatcher
        """
        try:
            # Update last message time for healthcheck (any RF activity is good)
            self.last_message_time = time.time()
            self.connection_healthy = True
            
            # Extract RF packet data
            payload = event.payload if hasattr(event, 'payload') else event
            
            if not isinstance(payload, dict):
                debug_print_mc(f"⚠️ [RX_LOG] Payload non-dict: {type(payload).__name__}")
                return
            
            # Extract packet metadata
            snr = payload.get('snr', 0.0)
            rssi = payload.get('rssi', 0)
            raw_hex = payload.get('raw_hex', '')
            
            # Compute size and header upfront for early-exit check
            hex_len = len(raw_hex) // 2 if raw_hex else 0  # 2 hex chars = 1 byte
            header_info = self._parse_meshcore_header(raw_hex)
            
            # Store latest RF signal data for channel echo correlation
            # CHANNEL_MSG_RECV events arrive just after RX_LOG_DATA for the same packet;
            # storing here lets _on_channel_message attach real SNR/RSSI to channel messages.
            self.latest_rx_log = {
                'snr': snr,
                'rssi': rssi,
                'timestamp': time.time(),
                'path_len': 0  # Will be updated below if decoder is available
            }
            
            # Packets whose header cannot be parsed (too short, malformed, etc.) cannot be
            # attributed to any node — skip all downstream processing with one compact line.
            if header_info is None:
                debug_print_mc(f"⏭️  [RX_LOG] Short/unidentifiable packet ({hex_len}B, SNR:{snr}dB) — likely ACK/routing, skipped")
                return
            
            # DEBUG: Log SNR/RSSI extraction (identifiable packets only)
            debug_print_mc(f"📊 [RX_LOG] Extracted signal data: snr={snr}dB, rssi={rssi}dBm")
            
            # Build first log line with sender/receiver info if available
            if header_info:
                sender_id = header_info['sender_id']
                receiver_id = header_info['receiver_id']
                sender_name = self._get_node_name(sender_id)
                receiver_name = self._get_node_name(receiver_id)
                
                # Check if broadcast (0xFFFFFFFF)
                if receiver_id == 0xFFFFFFFF:
                    direction_info = f"From: {sender_name} → Broadcast"
                else:
                    direction_info = f"From: {sender_name} → To: {receiver_name}"
                
                debug_print_mc(f"📡 [RX_LOG] Paquet RF reçu ({hex_len}B) - {direction_info}")
                debug_print_mc(f"   📶 SNR:{snr}dB RSSI:{rssi}dBm | Hex:{raw_hex[:40]}...")
            
            # True for Path/Trace routing-only packets — logged once then skipped
            is_routing_packet = False

            # Try to decode packet if meshcore-decoder is available
            if MESHCORE_DECODER_AVAILABLE and raw_hex:
                try:
                    # Decode the packet using meshcore-decoder
                    packet = MeshCoreDecoder.decode(raw_hex)
                    
                    # Get human-readable names for route and payload types
                    route_name = get_route_type_name(packet.route_type)
                    payload_name = get_payload_type_name(packet.payload_type)
                    
                    # Check for unknown payload type errors
                    unknown_type_error = None
                    if packet.errors:
                        for error in packet.errors:
                            if "is not a valid PayloadType" in error:
                                # Extract the numeric type ID from error message
                                import re
                                match = re.search(r'(\d+) is not a valid PayloadType', error)
                                if match:
                                    unknown_type_error = match.group(1)
                                break
                    
                    # Build detailed info string
                    info_parts = []
                    
                    # Show unknown types with their numeric ID
                    if unknown_type_error:
                        info_parts.append(f"Type: Unknown({unknown_type_error})")
                    else:
                        info_parts.append(f"Type: {payload_name}")
                    
                    info_parts.append(f"Route: {route_name}")
                    
                    # Add packet size and version info
                    if packet.total_bytes > 0:
                        info_parts.append(f"Size: {packet.total_bytes}B")
                    
                    # Add payload version if not default
                    if hasattr(packet, 'payload_version') and packet.payload_version:
                        version_str = str(packet.payload_version).replace('PayloadVersion.', '')
                        if version_str != 'Version1':  # Only show if not default
                            info_parts.append(f"Ver: {version_str}")
                    
                    # Add message hash if available
                    if packet.message_hash:
                        info_parts.append(f"Hash: {packet.message_hash[:8]}")
                    
                    # Fix meshcoredecoder library bug: path may be a flat byte list
                    # instead of a list of 4-byte little-endian node IDs.
                    raw_path = packet.path if hasattr(packet, 'path') and packet.path else []
                    corrected_hops, corrected_path = _regroup_path_bytes(raw_path)
                    # If decoder path_length looks wrong (>64, MeshCore's hard limit)
                    # use our regrouped count instead.
                    display_hops = corrected_hops if packet.path_length > 64 else packet.path_length

                    # Add hop count (always show, even if 0, for routing visibility)
                    info_parts.append(f"Hops: {display_hops}")
                    
                    # Update path_len in latest_rx_log for channel echo correlation
                    self.latest_rx_log['path_len'] = display_hops if display_hops else 0
                    
                    # Add actual routing path if available (shows which nodes the packet traversed)
                    if corrected_path:
                        # Truncate long paths (show first 5 hops + count of remaining)
                        format_node_id = lambda n: f"0x{n:08x}" if isinstance(n, int) else str(n)
                        if len(corrected_path) > 5:
                            remaining_count = len(corrected_path) - 5
                            path_str = ' → '.join(format_node_id(n) for n in corrected_path[:5]) + f' … (+{remaining_count} more)'
                        else:
                            path_str = ' → '.join(format_node_id(n) for n in corrected_path)
                        info_parts.append(f"Path: {path_str}")
                    
                    # Add transport codes if available (useful for debugging routing)
                    if hasattr(packet, 'transport_codes') and packet.transport_codes:
                        info_parts.append(f"Transport: {packet.transport_codes}")
                    
                    # Check if packet is valid (only flag as invalid for non-unknown-type errors)
                    if unknown_type_error:
                        # Unknown types are common and not really "invalid"
                        validity = "ℹ️"  # Info icon instead of warning
                    else:
                        validity = "✅" if packet.is_valid else "⚠️"
                    info_parts.append(f"Status: {validity}")
                    
                    # Log decoded packet information
                    debug_print_mc(f"📦 [RX_LOG] {' | '.join(info_parts)}")
                    
                    # Categorize and display errors with better formatting
                    if packet.errors:
                        # Separate errors into categories
                        structural_errors = []
                        content_errors = []
                        unknown_type_errors = []
                        
                        for error in packet.errors:
                            if "is not a valid PayloadType" in error:
                                unknown_type_errors.append(error)
                            elif "too short" in error.lower() or "truncated" in error.lower():
                                structural_errors.append(error)
                            else:
                                content_errors.append(error)
                        
                        # Display structural errors first (most critical)
                        for error in structural_errors[:2]:  # Show first 2
                            debug_print_mc(f"   ⚠️ {error}")
                        
                        # Display content errors
                        for error in content_errors[:2]:  # Show first 2
                            debug_print_mc(f"   ⚠️ {error}")
                        
                        # Unknown type errors are informational only (already shown in Type field)
                        # Don't re-display them unless in debug mode
                        if self.debug and unknown_type_errors:
                            for error in unknown_type_errors:
                                debug_print_mc(f"   ℹ️  {error}")
                    
                    # Determine if packet is public/broadcast
                    from meshcoredecoder.types import RouteType as RT
                    is_public = packet.route_type in [RT.Flood, RT.TransportFlood]
                    
                    # If payload is decoded, show a preview with enhanced context
                    if packet.payload and isinstance(packet.payload, dict):
                        decoded_payload = packet.payload.get('decoded')
                        if decoded_payload:
                            # Show payload type-specific info with public/family context
                            if hasattr(decoded_payload, 'text'):
                                # TextMessage - show if public or direct
                                text_preview = decoded_payload.text[:50] if len(decoded_payload.text) > 50 else decoded_payload.text
                                msg_type = "📢 Public" if is_public else "📨 Direct"
                                debug_print_mc(f"📝 [RX_LOG] {msg_type} Message: \"{text_preview}\"")
                            
                            elif hasattr(decoded_payload, 'app_data'):
                                # Advert with app_data - show device info
                                app_data = decoded_payload.app_data
                                if isinstance(app_data, dict):
                                    name = app_data.get('name', 'Unknown')
                                    
                                    # Build advert info with device role and location
                                    advert_parts = [f"from: {name}"]
                                    
                                    # Add public key prefix for node identification
                                    if hasattr(decoded_payload, 'public_key') and decoded_payload.public_key:
                                        pubkey_prefix = decoded_payload.public_key[:12]  # First 6 bytes (12 hex chars)
                                        # Derive node ID from public key (first 4 bytes)
                                        node_id_hex = decoded_payload.public_key[:8]  # First 4 bytes (8 hex chars)
                                        try:
                                            node_id = int(node_id_hex, 16)
                                            advert_parts.append(f"Node: 0x{node_id:08x}")
                                        except:
                                            advert_parts.append(f"PubKey: {pubkey_prefix}...")
                                    
                                    # Add device role if available
                                    if 'device_role' in app_data:
                                        role = app_data['device_role']
                                        role_name = str(role).split('.')[-1]  # Extract enum name
                                        advert_parts.append(f"Role: {role_name}")
                                    
                                    # Add location indicator
                                    if app_data.get('has_location'):
                                        location = app_data.get('location', {})
                                        if location:
                                            lat = location.get('latitude', 0)
                                            lon = location.get('longitude', 0)
                                            advert_parts.append(f"GPS: ({lat:.4f}, {lon:.4f})")
                                    
                                    debug_print_mc(f"📢 [RX_LOG] Advert {' | '.join(advert_parts)}")
                            
                            # Group messages
                            elif packet.payload_type.name in ['GroupText', 'GroupData']:
                                content_type = "Group Text" if packet.payload_type.name == 'GroupText' else "Group Data"
                                debug_print_mc(f"👥 [RX_LOG] {content_type} (public broadcast)")
                            
                            # Routing packets — flag for early skip before forwarding
                            elif packet.payload_type.name == 'Trace':
                                is_routing_packet = True
                                debug_print_mc(f"🔍 [RX_LOG] Trace packet (routing diagnostic)")
                            elif packet.payload_type.name == 'Path':
                                is_routing_packet = True
                                debug_print_mc(f"🛣️  [RX_LOG] Path packet (routing info)")
                        
                        # In debug mode, show raw payload info if available
                        if self.debug:
                            raw_payload = packet.payload.get('raw', '')
                            if raw_payload:
                                debug_print_mc(f"   🔍 Raw payload: {raw_payload[:40]}...")
                    
                except Exception as decode_error:
                    # Decoder failed, but that's OK - packet might be malformed or incomplete
                    debug_print_mc(f"📊 [RX_LOG] Décodage non disponible: {str(decode_error)[:60]}")
            else:
                # Decoder not available, show basic info
                if not MESHCORE_DECODER_AVAILABLE:
                    debug_print_mc(f"📊 [RX_LOG] RF monitoring only (meshcore-decoder not installed)")
                else:
                    debug_print_mc(f"📊 [RX_LOG] RF monitoring only (no hex data)")
            
            # CRITICAL FIX: Forward ALL packets to bot for statistics
            # This allows the bot to count ALL MeshCore packets (not just text messages)
            # The bot's traffic_monitor will handle packet type filtering and counting
            if MESHCORE_DECODER_AVAILABLE and raw_hex and self.message_callback and not is_routing_packet:
                try:
                    # IMPORTANT: Parse header FIRST to get correct sender/receiver addresses
                    # The header_info is already parsed above, but we need it here too
                    packet_header = self._parse_meshcore_header(raw_hex)
                    
                    # Extract sender and receiver from packet header (CORRECT SOURCE!)
                    sender_id = packet_header['sender_id'] if packet_header else 0xFFFFFFFF
                    receiver_id = packet_header['receiver_id'] if packet_header else 0xFFFFFFFF
                    
                    # Decode packet again (we already did above, but need clean decode for forwarding)
                    decoded_packet = MeshCoreDecoder.decode(raw_hex)
                    
                    # Extract packet information for all packet types
                    packet_text = None
                    portnum = 'UNKNOWN_APP'  # Default
                    payload_bytes = b''
                    
                    if decoded_packet.payload and isinstance(decoded_packet.payload, dict):
                        decoded_payload = decoded_packet.payload.get('decoded')
                        
                        if decoded_payload:
                            # Determine packet type and extract payload
                            if hasattr(decoded_payload, 'text'):
                                # Text message
                                portnum = 'TEXT_MESSAGE_APP'
                                packet_text = decoded_payload.text
                                payload_bytes = packet_text.encode('utf-8')
                            elif hasattr(decoded_payload, 'app_data'):
                                # Node info advert
                                portnum = 'NODEINFO_APP'
                                # Store app_data as payload (will be handled by traffic_monitor)
                                payload_bytes = str(decoded_payload.app_data).encode('utf-8')
                            elif decoded_packet.payload_type.name in ['Position', 'PositionApp']:
                                portnum = 'POSITION_APP'
                                payload_bytes = b''  # Position data is in decoded_payload attributes
                            elif decoded_packet.payload_type.name in ['Telemetry', 'TelemetryApp']:
                                portnum = 'TELEMETRY_APP'
                                payload_bytes = b''  # Telemetry data is in decoded_payload attributes
                            else:
                                # Other packet types - use payload type name
                                portnum = decoded_packet.payload_type.name.upper() + '_APP'
                                payload_bytes = b''
                        else:
                            # Payload not decoded (encrypted or unknown type)
                            # Check if there's raw payload data in decoded_packet
                            raw_payload = decoded_packet.payload.get('raw', b'')
                            
                            # CRITICAL FIX: If decoded raw is empty, use original raw_hex from event
                            # The decoder can't decrypt encrypted packets, so payload['raw'] is empty
                            # But the original hex data is available in the event payload
                            if not raw_payload and raw_hex:
                                debug_print_mc(f"🔧 [RX_LOG] Decoded raw empty, using original raw_hex: {len(raw_hex)//2}B")
                                raw_payload = raw_hex
                            
                            if raw_payload:
                                # Have raw payload - use it
                                if isinstance(raw_payload, str):
                                    # Convert hex string to bytes
                                    try:
                                        payload_bytes = bytes.fromhex(raw_payload)
                                        debug_print_mc(f"✅ [RX_LOG] Converted hex to bytes: {len(payload_bytes)}B")
                                    except ValueError:
                                        payload_bytes = raw_payload.encode('utf-8')
                                        debug_print_mc(f"✅ [RX_LOG] Encoded string to bytes: {len(payload_bytes)}B")
                                else:
                                    payload_bytes = raw_payload
                                    debug_print_mc(f"✅ [RX_LOG] Using raw bytes directly: {len(payload_bytes)}B")
                                
                                # Try to determine portnum from payload_type
                                if hasattr(decoded_packet, 'payload_type') and decoded_packet.payload_type:
                                    try:
                                        # Use the numeric payload type value
                                        payload_type_value = decoded_packet.payload_type.value if hasattr(decoded_packet.payload_type, 'value') else None
                                        
                                        if payload_type_value == 1:
                                            portnum = 'TEXT_MESSAGE_APP'
                                        elif payload_type_value == 3:
                                            portnum = 'POSITION_APP'
                                        elif payload_type_value == 4:
                                            portnum = 'NODEINFO_APP'
                                        elif payload_type_value == 7:
                                            portnum = 'TELEMETRY_APP'
                                        elif payload_type_value in [12, 13, 15]:
                                            # Types 12, 13, 15 are encrypted message wrappers
                                            # If receiver is not broadcast, this is a private ECDH DM
                                            # between other nodes - PSK decryption will always fail.
                                            # Label it as ECDH_DM so statistics can be tracked,
                                            # but skip the pointless decryption attempt.
                                            if receiver_id != 0xFFFFFFFF:
                                                src = self._fmt_node(sender_id)
                                                dst = self._fmt_node(receiver_id)
                                                debug_print_mc(f"🔒 [ECDH_DM] {src}→{dst} (type={payload_type_value})")
                                                portnum = 'ECDH_DM'
                                                packet_text = '[FOREIGN_DM]'
                                            # Try to decrypt with MeshCore Public channel PSK
                                            # (only for broadcast packets - directed ones are ECDH, already handled above)
                                            # Try decryption if crypto is available
                                            decrypted_text = None
                                            if portnum != 'ECDH_DM' and CRYPTO_AVAILABLE and payload_bytes:
                                                # Get packet_id for decryption nonce
                                                # Extract from message_hash (available in decoded_packet)
                                                packet_id = None
                                                if hasattr(decoded_packet, 'message_hash') and decoded_packet.message_hash:
                                                    # message_hash is hex string, convert first 8 chars (4 bytes) to int
                                                    packet_id = int(decoded_packet.message_hash[:8], 16)
                                                elif packet_header and 'msg_hash' in packet_header:
                                                    # Fall back to packet header
                                                    packet_id = int(packet_header['msg_hash'][:8], 16)
                                                
                                                # Always strip 16-byte MeshCore header from payload
                                                # Header: type(4) + sender(4) + receiver(4) + msg_hash(4) = 16 bytes (NOT encrypted)
                                                # Only payload after byte 16 is encrypted
                                                if len(payload_bytes) > 16:
                                                    encrypted_payload = payload_bytes[16:]
                                                    payload_bytes = encrypted_payload  # Update payload_bytes to strip header
                                                    
                                                    # Skip protobuf varint length prefix before decryption
                                                    # After MeshCore header, there's a protobuf varint that encodes the payload length
                                                    # We need to skip this varint before decrypting
                                                    def decode_varint(data):
                                                        """Decode protobuf varint from bytes."""
                                                        result = 0
                                                        shift = 0
                                                        index = 0
                                                        while index < len(data):
                                                            byte = data[index]
                                                            result |= (byte & 0x7F) << shift
                                                            index += 1
                                                            if (byte & 0x80) == 0:
                                                                break
                                                            shift += 7
                                                        return result, index
                                                    
                                                    # Decode and skip varint
                                                    if len(encrypted_payload) > 0:
                                                        length, varint_size = decode_varint(encrypted_payload)
                                                        encrypted_payload = encrypted_payload[varint_size:]
                                                        payload_bytes = encrypted_payload  # Update again after varint skip
                                                else:
                                                    encrypted_payload = payload_bytes
                                                
                                                # Always attempt PSK decryption (Public channel uses PSK even for messages to specific users)
                                                # Public channel messages decrypt to readable text, DMs produce garbage (detected by readability check)
                                                if packet_id is not None and sender_id != 0xFFFFFFFF:
                                                    debug_print_mc(f"🔓 [DECRYPT] type={payload_type_value} id=0x{packet_id:08x} from=0x{sender_id:08x} payload={len(encrypted_payload)}B")
                                                    
                                                    decrypted_text = decrypt_meshcore_public(
                                                        encrypted_payload, 
                                                        packet_id, 
                                                        sender_id, 
                                                        self.meshcore_public_psk
                                                    )
                                                    
                                                    # Validate decryption result is readable text
                                                    # Public channel: PSK decryption produces readable UTF-8
                                                    # DMs: PSK decryption produces garbage (ECDH-encrypted)
                                                    if decrypted_text and all(c.isprintable() or c in '\n\r\t' for c in decrypted_text):
                                                        debug_print_mc(f"✅ [DECRYPT] Decrypted: \"{decrypted_text[:50]}{'...' if len(decrypted_text) > 50 else ''}\"")
                                                        # Update payload with decrypted text
                                                        packet_text = decrypted_text
                                                        payload_bytes = decrypted_text.encode('utf-8')
                                                    else:
                                                        # Non-printable result = ECDH-encrypted DM
                                                        debug_print_mc(f"⚠️  [DECRYPT] Non-printable result (likely ECDH DM) or decryption failed")
                                                        # Mark as encrypted for display
                                                        packet_text = '[ENCRYPTED]'
                                            
                                            # Map to TEXT_MESSAGE_APP (encrypted or decrypted)
                                            portnum = 'TEXT_MESSAGE_APP'
                                            if not decrypted_text:
                                                debug_print_mc(f"🔐 [RX_LOG] Encrypted packet (type {payload_type_value}) → TEXT_MESSAGE_APP (not decrypted)")
                                        else:
                                            # Unknown type - keep as UNKNOWN_APP
                                            portnum = 'UNKNOWN_APP'
                                    except:
                                        portnum = 'UNKNOWN_APP'
                    elif decoded_packet.payload:
                        # Payload exists but is not a dict
                        # Try to use it directly as bytes
                        debug_print_mc(f"⚠️ [RX_LOG] Payload is not a dict: {type(decoded_packet.payload).__name__}")
                        if isinstance(decoded_packet.payload, (bytes, bytearray)):
                            payload_bytes = bytes(decoded_packet.payload)
                            debug_print_mc(f"✅ [RX_LOG] Using payload directly as bytes: {len(payload_bytes)}B")
                        elif isinstance(decoded_packet.payload, str):
                            # Try to decode as hex
                            try:
                                payload_bytes = bytes.fromhex(decoded_packet.payload)
                                debug_print_mc(f"✅ [RX_LOG] Converted hex string to bytes: {len(payload_bytes)}B")
                            except ValueError:
                                payload_bytes = decoded_packet.payload.encode('utf-8')
                                debug_print_mc(f"✅ [RX_LOG] Encoded string to bytes: {len(payload_bytes)}B")
                        
                        # Try to determine portnum from payload_type
                        if hasattr(decoded_packet, 'payload_type') and decoded_packet.payload_type:
                            try:
                                payload_type_value = decoded_packet.payload_type.value if hasattr(decoded_packet.payload_type, 'value') else None
                                if payload_type_value == 1:
                                    portnum = 'TEXT_MESSAGE_APP'
                                elif payload_type_value == 3:
                                    portnum = 'POSITION_APP'
                                elif payload_type_value == 4:
                                    portnum = 'NODEINFO_APP'
                                elif payload_type_value == 7:
                                    portnum = 'TELEMETRY_APP'
                            except:
                                pass
                    else:
                        # No payload at all - check if raw data is in the packet object itself
                        debug_print_mc(f"⚠️ [RX_LOG] No payload found in decoded_packet")
                        # Check if there's raw data elsewhere
                        if hasattr(decoded_packet, 'raw_data') and decoded_packet.raw_data:
                            payload_bytes = decoded_packet.raw_data
                            debug_print_mc(f"✅ [RX_LOG] Found raw_data in packet: {len(payload_bytes)}B")
                        elif hasattr(decoded_packet, 'data') and decoded_packet.data:
                            payload_bytes = decoded_packet.data
                            debug_print_mc(f"✅ [RX_LOG] Found data in packet: {len(payload_bytes)}B")
                    
                    # Determine if broadcast based on receiver address (not route type)
                    # Route type can be Flood even for DMs (flood routing)
                    is_broadcast = (receiver_id == 0xFFFFFFFF)
                    
                    # Create bot-compatible packet for ALL packet types
                    import random
                    
                    # Build decoded dict with text field for TEXT_MESSAGE_APP
                    decoded_dict = {
                        'portnum': portnum,
                        'payload': payload_bytes
                    }
                    
                    # Add text field if we have packet_text (decrypted or [ENCRYPTED])
                    if portnum == 'TEXT_MESSAGE_APP' and packet_text is not None:
                        decoded_dict['text'] = packet_text
                    
                    # Apply the same byte-list fix for hopStart and path forwarding
                    fwd_raw_path = decoded_packet.path if hasattr(decoded_packet, 'path') and decoded_packet.path else []
                    fwd_hops, fwd_path = _regroup_path_bytes(fwd_raw_path)
                    raw_pl = decoded_packet.path_length if hasattr(decoded_packet, 'path_length') else 0
                    hop_start = fwd_hops if raw_pl > 64 else raw_pl

                    bot_packet = {
                        'from': sender_id,  # Use header sender (CORRECT!)
                        'to': receiver_id,  # Use header receiver (CORRECT!)
                        'id': random.randint(100000, 999999),
                        'rxTime': int(time.time()),
                        'rssi': rssi,
                        'snr': snr,
                        'hopLimit': 0,  # Packet received with 0 hops remaining
                        'hopStart': hop_start,
                        'channel': 0,
                        'decoded': decoded_dict,
                        '_meshcore_rx_log': True,  # Mark as RX_LOG packet
                        '_meshcore_broadcast': is_broadcast
                    }
                    
                    # Add routing path if available (for hop visualization)
                    if fwd_path:
                        bot_packet['_meshcore_path'] = fwd_path
                    
                    # Forward to bot callback
                    self.message_callback(bot_packet, None)
                    if portnum == 'ECDH_DM':
                        src = self._fmt_node(sender_id)
                        dst = self._fmt_node(receiver_id)
                        debug_print_mc(f"🔒 [ECDH_DM] {src}→{dst} stored for stats")
                    else:
                        debug_print_mc(f"✅ [RX_LOG] Packet forwarded successfully")
                    
                except Exception as forward_error:
                    debug_print_mc(f"⚠️ [RX_LOG] Error forwarding packet: {forward_error}")
                    if self.debug:
                        error_print(traceback.format_exc())
            
        except Exception as e:
            debug_print_mc(f"⚠️ [RX_LOG] Erreur traitement RX_LOG_DATA: {e}")
            if self.debug:
                error_print(traceback.format_exc())

    def _get_pubkey_prefix_for_node(self, node_id):
        """
        Get public key prefix for a node_id from database
        
        When a MeshCore DM arrives, we save the contact with its full publicKey.
        When sending a response, we need to look up the contact in meshcore using
        the pubkey_prefix, not the node_id (node_id is only the first 4 bytes of the key).
        
        Args:
            node_id: int node ID
            
        Returns:
            str: hex string of public key prefix (first 12 chars minimum), or None
        """
        if not self.node_manager or not hasattr(self.node_manager, 'persistence'):
            debug_print_mc("⚠️ [MESHCORE-DM] NodeManager ou persistence non disponible")
            return None
        
        try:
            debug_print_mc(f"🔍 [MESHCORE-DM] Recherche pubkey_prefix pour node 0x{node_id:08x}")
            
            # Query meshcore_contacts table
            cursor = self.node_manager.persistence.conn.cursor()
            cursor.execute(
                "SELECT publicKey FROM meshcore_contacts WHERE node_id = ?",
                (str(node_id),)
            )
            row = cursor.fetchone()
            
            if row and row[0]:
                public_key_bytes = row[0]
                # Convert to hex, take first 12 chars minimum (6 bytes)
                # But we can use the full key prefix for better matching
                pubkey_hex = public_key_bytes.hex()
                pubkey_prefix = pubkey_hex[:12]  # First 6 bytes = 12 hex chars minimum
                debug_print_mc(f"✅ [DM] pubkey_prefix trouvé: {pubkey_prefix}")
                return pubkey_prefix
            else:
                debug_print_mc(f"⚠️ [DM] Pas de publicKey en DB pour node 0x{node_id:08x}")
                return None
                
        except Exception as e:
            debug_print_mc(f"⚠️ [DM] Erreur recherche pubkey_prefix: {e}")
            if self.debug:
                error_print(traceback.format_exc())
            return None

    def sendText(self, text, destinationId, wantAck=False, channelIndex=0):
        """
        Envoie un message texte via MeshCore
        
        Args:
            text: Texte à envoyer
            destinationId: ID du destinataire (node_id) or 0xFFFFFFFF for broadcast
            wantAck: Demander un accusé de réception (ignoré en mode companion)
            channelIndex: Canal (utilisé pour broadcasts, ignoré pour DMs)
        
        Returns:
            bool: True si envoyé avec succès
        """
        if not self.meshcore:
            error_print("❌ [MESHCORE-CLI] Non connecté")
            return False
        
        # ========================================
        # MESSAGE DEDUPLICATION
        # ========================================
        # Create hash of message + destination to detect duplicates
        import hashlib
        message_key = f"{destinationId}:{text}"
        message_hash = hashlib.md5(message_key.encode()).hexdigest()
        
        current_time = time.time()
        
        # Clean up old entries (older than dedup window)
        self._sent_messages = {
            k: v for k, v in self._sent_messages.items()
            if current_time - v['timestamp'] < self._message_dedup_window
        }
        
        # Check if this message was sent recently
        if message_hash in self._sent_messages:
            last_send = self._sent_messages[message_hash]
            time_since = current_time - last_send['timestamp']
            count = last_send['count']
            
            # Warn if duplicate detected
            debug_print_mc(f"⚠️  [DEDUP] Message déjà envoyé il y a {time_since:.1f}s (x{count}) - SKIP")
            debug_print_mc(f"   Message: {text[:50]}{'...' if len(text) > 50 else ''}")
            # Format destination ID properly (can't use ternary in format specifier)
            dest_str = f"0x{destinationId:08x}" if isinstance(destinationId, int) else str(destinationId)
            debug_print_mc(f"   Destination: {dest_str}")
            
            # Update count but don't resend
            self._sent_messages[message_hash]['count'] += 1
            return False  # Don't send duplicate
        
        # Record this send attempt
        self._sent_messages[message_hash] = {
            'timestamp': current_time,
            'count': 1
        }
        debug_print_mc(f"✅ [DEDUP] Nouveau message enregistré (hash: {message_hash[:8]}...)")
        
        # ========================================
        # SEND MESSAGE
        # ========================================
        
        # Detect if this is a broadcast/channel message
        is_broadcast = (destinationId is None or destinationId == 0xFFFFFFFF)
        
        if is_broadcast:
            # Use send_chan_msg() for channel/broadcast messages
            # API: send_chan_msg(chan, msg, timestamp=None)
            # Channel 0 = public/default channel
            try:
                debug_print_mc(f"📢 [MESHCORE-CHANNEL] Envoi broadcast sur canal {channelIndex}: {text[:50]}{'...' if len(text) > 50 else ''}")
                
                if not hasattr(self.meshcore, 'commands'):
                    error_print(f"❌ [MESHCORE-CHANNEL] MeshCore n'a pas d'attribut 'commands'")
                    return False
                
                # Send via commands.send_chan_msg()
                # Channel 0 = public channel
                debug_print_mc(f"🔍 [MESHCORE-CHANNEL] Appel de commands.send_chan_msg(chan={channelIndex}, msg=...)")
                debug_print_mc(f"🔄 [MESHCORE-CHANNEL] Event loop running: {self._loop.is_running()}")
                
                future = asyncio.run_coroutine_threadsafe(
                    self.meshcore.commands.send_chan_msg(channelIndex, text),
                    self._loop
                )
                
                # Fire-and-forget approach (same as DMs)
                def _log_channel_result(fut):
                    try:
                        if fut.exception():
                            error_print(f"❌ [MESHCORE-CHANNEL] Async send error: {fut.exception()}")
                        else:
                            debug_print_mc(f"✅ [CHANNEL] Async send completed successfully")
                    except Exception as e:
                        debug_print_mc(f"⚠️ [CHANNEL] Future check error: {e}")
                
                future.add_done_callback(_log_channel_result)
                
                debug_print_mc("✅ [MESHCORE-CHANNEL] Broadcast envoyé via send_chan_msg (fire-and-forget)")
                info_print_mc(f"📢 [MESHCORE] Broadcast envoyé sur canal {channelIndex}")
                return True
                
            except Exception as e:
                error_print(f"❌ [MESHCORE-CHANNEL] Erreur envoi broadcast: {e}")
                error_print(traceback.format_exc())
                return False
        
        try:
            debug_print_mc(f"📤 [MESHCORE-DM] Envoi à 0x{destinationId:08x}: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            # Envoyer via meshcore-cli avec l'API commands.send_msg()
            # The correct API is: meshcore.commands.send_msg(contact, text)
            # where contact is a dict or ID
            
            if not hasattr(self.meshcore, 'commands'):
                error_print(f"❌ [MESHCORE-DM] MeshCore n'a pas d'attribut 'commands'")
                error_print(f"   → Attributs disponibles: {[m for m in dir(self.meshcore) if not m.startswith('_')]}")
                return False
            
            # Get the contact using pubkey_prefix (not node_id!)
            # The node_id is only the first 4 bytes of the 32-byte public key
            # meshcore-cli's get_contact_by_key_prefix expects at least 12 hex chars (6 bytes)
            contact = None
            
            # FIX: Look up the full pubkey_prefix from database instead of using node_id
            pubkey_prefix = self._get_pubkey_prefix_for_node(destinationId)
            
            if pubkey_prefix:
                debug_print_mc(f"🔍 [MESHCORE-DM] Recherche contact avec pubkey_prefix: {pubkey_prefix}")
                
                # DIAGNOSTIC: Show what's in meshcore.contacts dict
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    debug_print_mc(f"📊 [DM] meshcore.contacts dict size: {len(self.meshcore.contacts)}")
                else:
                    debug_print_mc(f"⚠️ [DM] meshcore.contacts is None or empty!")
                
                # FIX: Direct dict access instead of meshcore-cli method
                # The get_contact_by_key_prefix() method doesn't work with our manually added contacts
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    contact = self.meshcore.contacts.get(pubkey_prefix)
                    if contact:
                        debug_print_mc(f"✅ [DM] Contact trouvé via dict direct: {contact.get('adv_name', 'unknown')}")
                    else:
                        debug_print_mc(f"⚠️ [DM] Contact non trouvé dans dict (clé: {pubkey_prefix})")
            else:
                debug_print_mc(f"⚠️ [DM] Pas de pubkey_prefix en DB, recherche avec node_id")
                # Fallback: try with node_id hex (8 chars) in dict
                hex_id = f"{destinationId:08x}"
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    contact = self.meshcore.contacts.get(hex_id)
            
            # If not found, use the destinationId directly
            # The send_msg API should accept either contact dict or node_id
            if not contact:
                debug_print_mc(f"⚠️ [DM] Contact non trouvé, utilisation de l'ID directement")
                contact = destinationId
            
            # Send via commands.send_msg
            # Use run_coroutine_threadsafe since the event loop is already running
            debug_print_mc(f"🔍 [MESHCORE-DM] Appel de commands.send_msg(contact={type(contact).__name__}, text=...)")
            
            # DIAGNOSTIC: Check event loop status
            debug_print_mc(f"🔄 [MESHCORE-DM] Event loop running: {self._loop.is_running()}")
            debug_print_mc(f"🔄 [MESHCORE-DM] Submitting coroutine to event loop...")
            
            future = asyncio.run_coroutine_threadsafe(
                self.meshcore.commands.send_msg(contact, text),
                self._loop
            )
            
            # FIRE-AND-FORGET APPROACH
            # Don't wait for result - the coroutine is hanging waiting for ACK that never comes
            # Let the message send asynchronously in the background
            debug_print_mc(f"✅ [DM] Message submitted to event loop (fire-and-forget)")
            debug_print_mc(f"📤 [MESHCORE-DM] Coroutine will complete asynchronously in background")
            
            # Optional: Add error handler to the future to log any exceptions
            def _log_future_result(fut):
                try:
                    if fut.exception():
                        error_print(f"❌ [MESHCORE-DM] Async send error: {fut.exception()}")
                    else:
                        debug_print_mc(f"✅ [DM] Async send completed successfully")
                except Exception as e:
                    debug_print_mc(f"⚠️ [DM] Future check error: {e}")
            
            future.add_done_callback(_log_future_result)
            
            # Return immediately - don't block waiting for result
            # LoRa is inherently unreliable anyway, we send and hope it arrives
            debug_print_mc("✅ [MESHCORE-DM] Message envoyé (fire-and-forget)")
            return True
                
        except Exception as e:
            error_print(f"❌ [MESHCORE-DM] Erreur envoi: {e}")
            error_print(traceback.format_exc())
            return False
    
    
    def get_connection_status(self):
        """
        Retourne le statut de connexion MeshCore pour diagnostics
        
        Returns:
            dict: Statut détaillé de la connexion
        """
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'connected': self.meshcore is not None,
            'running': self.running,
            'event_thread_alive': self.message_thread.is_alive() if self.message_thread else False,
            'healthcheck_thread_alive': self.healthcheck_thread.is_alive() if self.healthcheck_thread else False,
            'callback_configured': self.message_callback is not None,
            'connection_healthy': self.connection_healthy,
            'last_message_time': self.last_message_time,
            'interface_type': 'MeshCoreCLIWrapper (meshcore-cli library)',
        }
    
    def close(self):
        """Ferme la connexion MeshCore"""
        info_print_mc("🔌 [MESHCORE-CLI] Fermeture connexion...")
        
        self.running = False
        
        # Stop the async event loop if running
        if hasattr(self, '_loop') and self._loop and self._loop.is_running():
            info_print_mc("🛑 [MESHCORE-CLI] Arrêt de la boucle d'événements...")
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self.message_thread and self.message_thread.is_alive():
            info_print_mc("⏳ [MESHCORE-CLI] Attente du thread de messages...")
            self.message_thread.join(timeout=5)
        
        if self.healthcheck_thread and self.healthcheck_thread.is_alive():
            info_print_mc("⏳ [MESHCORE-CLI] Attente du thread healthcheck...")
            self.healthcheck_thread.join(timeout=2)
        
        if self.meshcore:
            try:
                # Fermer avec l'API async - créer une nouvelle boucle si nécessaire
                if hasattr(self, '_loop') and not self._loop.is_closed():
                    # Utiliser la boucle existante si pas fermée
                    if not self._loop.is_running():
                        self._loop.run_until_complete(self.meshcore.disconnect())
                else:
                    # Créer une nouvelle boucle temporaire pour la déconnexion
                    temp_loop = asyncio.new_event_loop()
                    try:
                        temp_loop.run_until_complete(self.meshcore.disconnect())
                    finally:
                        temp_loop.close()
            except Exception as e:
                error_print(f"⚠️ [MESHCORE-CLI] Erreur fermeture meshcore: {e}")
        
        # Close the event loop if not already closed
        if hasattr(self, '_loop') and self._loop and not self._loop.is_closed():
            try:
                self._loop.close()
                info_print_mc("✅ [MESHCORE-CLI] Boucle d'événements fermée")
            except Exception as e:
                debug_print_mc(f"⚠️ [MESHCORE-CLI] Erreur fermeture loop: {e}")
        
        info_print_mc("✅ [MESHCORE-CLI] Connexion fermée")


# Alias pour compatibilité avec le code existant
MeshCoreSerialInterface = MeshCoreCLIWrapper
