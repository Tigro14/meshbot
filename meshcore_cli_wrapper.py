#!/usr/bin/env python3
"""
Wrapper pour meshcore-cli library
Intégration avec le bot MeshBot en mode companion
"""

import threading
import time
import asyncio
from utils import info_print, debug_print, error_print
import traceback

# Try to import meshcore-cli
try:
    from meshcore import MeshCore, EventType
    MESHCORE_CLI_AVAILABLE = True
    info_print("✅ [MESHCORE] Library meshcore-cli disponible")
except ImportError:
    MESHCORE_CLI_AVAILABLE = False
    info_print("⚠️ [MESHCORE] Library meshcore-cli non disponible (pip install meshcore)")
    # Fallback to basic implementation
    MeshCore = None
    EventType = None

# Try to import meshcore-decoder for packet parsing
try:
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    MESHCORE_DECODER_AVAILABLE = True
    info_print("✅ [MESHCORE] Library meshcore-decoder disponible (packet decoding)")
except ImportError:
    MESHCORE_DECODER_AVAILABLE = False
    info_print("⚠️ [MESHCORE] Library meshcore-decoder non disponible (pip install meshcoredecoder)")
    MeshCoreDecoder = None
    get_route_type_name = None
    get_payload_type_name = None

# Try to import PyNaCl for key validation
try:
    import nacl.public
    import nacl.encoding
    NACL_AVAILABLE = True
    debug_print("✅ [MESHCORE] PyNaCl disponible (validation clés)")
except ImportError:
    NACL_AVAILABLE = False
    debug_print("ℹ️  [MESHCORE] PyNaCl non disponible (validation clés désactivée)")


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
        
        # Determine debug mode: explicit parameter > config > False
        if debug is None:
            try:
                import config
                self.debug = getattr(config, 'DEBUG_MODE', False)
            except ImportError:
                self.debug = False
        else:
            self.debug = debug
        
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
        
        info_print(f"🔧 [MESHCORE-CLI] Initialisation: {port} (debug={self.debug})")
    
    def connect(self):
        """Établit la connexion avec MeshCore via meshcore-cli"""
        try:
            info_print(f"🔌 [MESHCORE-CLI] Connexion à {self.port}...")
            
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
            
            info_print(f"✅ [MESHCORE-CLI] Device connecté sur {self.port}")
            
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
                    info_print(f"   Node ID: 0x{self.localNode.nodeNum:08x}")
            except Exception as e:
                debug_print(f"⚠️ [MESHCORE-CLI] Impossible de récupérer node_id: {e}")
            
            return True
            
        except Exception as e:
            error_print(f"❌ [MESHCORE-CLI] Erreur connexion: {e}")
            error_print(traceback.format_exc())
            return False
    
    def set_message_callback(self, callback):
        """
        Définit le callback pour les messages reçus
        Compatible avec l'interface Meshtastic
        
        Args:
            callback: Fonction à appeler lors de la réception d'un message
        """
        info_print(f"📝 [MESHCORE-CLI] Setting message_callback to {callback}")
        self.message_callback = callback
        info_print(f"✅ [MESHCORE-CLI] message_callback set successfully")
    
    def set_node_manager(self, node_manager):
        """
        Set the node manager for pubkey lookups
        
        Args:
            node_manager: NodeManager instance
        """
        self.node_manager = node_manager
        debug_print("✅ [MESHCORE-CLI] NodeManager configuré")
    
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
            debug_print("⚠️ [MESHCORE-DM] meshcore.contacts non disponible")
            return False
        
        try:
            # Extract pubkey_prefix from publicKey
            public_key = contact_data.get('publicKey')
            if not public_key:
                debug_print("⚠️ [MESHCORE-DM] Pas de publicKey dans contact_data")
                return False
            
            # Convert publicKey to hex string if it's bytes
            if isinstance(public_key, bytes):
                pubkey_hex = public_key.hex()
            elif isinstance(public_key, str):
                pubkey_hex = public_key
            else:
                debug_print(f"⚠️ [MESHCORE-DM] Type publicKey non supporté: {type(public_key)}")
                return False
            
            # Extract first 12 hex chars (6 bytes) = pubkey_prefix
            pubkey_prefix = pubkey_hex[:12]
            
            # Create contact dict compatible with meshcore format
            # CRITICAL: meshcore-cli expects 'public_key' (snake_case), not 'publicKey' (camelCase)
            contact = {
                'node_id': contact_data['node_id'],
                'adv_name': contact_data.get('name', f"Node-{contact_data['node_id']:08x}"),
                'public_key': contact_data['publicKey'],  # Use snake_case for meshcore-cli API
            }
            
            # Initialize contacts dict if needed
            if self.meshcore.contacts is None:
                self.meshcore.contacts = {}
            
            # Add to internal dict
            self.meshcore.contacts[pubkey_prefix] = contact
            debug_print(f"✅ [MESHCORE-DM] Contact ajouté à meshcore.contacts: {pubkey_prefix}")
            debug_print(f"📊 [MESHCORE-DM] Dict keys après ajout: {list(self.meshcore.contacts.keys())}")
            debug_print(f"📊 [MESHCORE-DM] Dict size: {len(self.meshcore.contacts)}")
            return True
            
        except Exception as e:
            debug_print(f"⚠️ [MESHCORE-DM] Erreur ajout contact à meshcore: {e}")
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
            debug_print("⚠️ [MESHCORE-QUERY] No meshcore connection available")
            return None
        
        if not self.node_manager:
            debug_print("⚠️ [MESHCORE-QUERY] No node_manager configured")
            return None
        
        try:
            debug_print(f"🔍 [MESHCORE-QUERY] Recherche contact avec pubkey_prefix: {pubkey_prefix}")
            
            # Ensure contacts are loaded
            # CRITICAL FIX: Actually call ensure_contacts() to load contacts from device
            # NOTE: meshcore-cli may populate contacts asynchronously, so we check if they're
            # already loaded before calling ensure_contacts()
            
            # First, try to flush any pending contacts
            if hasattr(self.meshcore, 'flush_pending_contacts') and callable(self.meshcore.flush_pending_contacts):
                try:
                    debug_print(f"🔄 [MESHCORE-QUERY] Appel flush_pending_contacts() pour finaliser les contacts en attente...")
                    self.meshcore.flush_pending_contacts()
                    debug_print(f"✅ [MESHCORE-QUERY] flush_pending_contacts() terminé")
                except Exception as flush_err:
                    debug_print(f"⚠️ [MESHCORE-QUERY] Erreur flush_pending_contacts(): {flush_err}")
            
            # Check if contacts are already loaded (may have been populated during connection)
            initial_count = 0
            if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                initial_count = len(self.meshcore.contacts)
                debug_print(f"📊 [MESHCORE-QUERY] Contacts déjà disponibles: {initial_count}")
            
            # If no contacts yet, try to load them
            if initial_count == 0 and hasattr(self.meshcore, 'ensure_contacts'):
                debug_print(f"🔄 [MESHCORE-QUERY] Appel ensure_contacts() pour charger les contacts...")
                try:
                    # Call ensure_contacts() - it will load contacts if not already loaded
                    if asyncio.iscoroutinefunction(self.meshcore.ensure_contacts):
                        # It's async - DON'T use run_coroutine_threadsafe as it hangs
                        # Instead, just mark contacts as dirty and they'll load in background
                        debug_print(f"⚠️ [MESHCORE-QUERY] ensure_contacts() est async - impossible d'appeler depuis ce contexte")
                        debug_print(f"💡 [MESHCORE-QUERY] Les contacts se chargeront en arrière-plan")
                        
                        # Try to mark contacts as dirty to trigger reload
                        # FIX: contacts_dirty is a read-only property, use private attribute _contacts_dirty instead
                        if hasattr(self.meshcore, '_contacts_dirty'):
                            self.meshcore._contacts_dirty = True
                            debug_print(f"🔄 [MESHCORE-QUERY] _contacts_dirty défini à True pour forcer le rechargement")
                        elif hasattr(self.meshcore, 'contacts_dirty'):
                            # Fallback: try the property (may fail if read-only)
                            try:
                                self.meshcore.contacts_dirty = True
                                debug_print(f"🔄 [MESHCORE-QUERY] contacts_dirty défini à True pour forcer le rechargement")
                            except AttributeError as e:
                                debug_print(f"⚠️ [MESHCORE-QUERY] Impossible de définir contacts_dirty: {e}")
                    else:
                        # It's synchronous - just call it
                        self.meshcore.ensure_contacts()
                        debug_print(f"✅ [MESHCORE-QUERY] ensure_contacts() terminé")
                except Exception as ensure_err:
                    error_print(f"⚠️ [MESHCORE-QUERY] Erreur ensure_contacts(): {ensure_err}")
                    error_print(traceback.format_exc())
                
                # Try flush again after ensure_contacts
                if hasattr(self.meshcore, 'flush_pending_contacts') and callable(self.meshcore.flush_pending_contacts):
                    try:
                        self.meshcore.flush_pending_contacts()
                        debug_print(f"✅ [MESHCORE-QUERY] flush_pending_contacts() après ensure_contacts")
                    except Exception as flush_err:
                        debug_print(f"⚠️ [MESHCORE-QUERY] Erreur flush après ensure: {flush_err}")
                
                # Check again if contacts are now available
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts is None:
                    debug_print(f"⚠️ [MESHCORE-QUERY] Contacts toujours non chargés après ensure_contacts()")
                else:
                    debug_print(f"✅ [MESHCORE-QUERY] Contacts disponibles après ensure_contacts()")
            elif initial_count > 0:
                debug_print(f"✅ [MESHCORE-QUERY] Contacts déjà chargés, pas besoin d'appeler ensure_contacts()")
            else:
                debug_print(f"⚠️ [MESHCORE-QUERY] meshcore.ensure_contacts() non disponible")
            
            # Debug: check if meshcore has contacts attribute
            if hasattr(self.meshcore, 'contacts'):
                try:
                    contacts_count = len(self.meshcore.contacts) if self.meshcore.contacts else 0
                    debug_print(f"📊 [MESHCORE-QUERY] Nombre de contacts disponibles: {contacts_count}")
                    
                    # Enhanced debug: show why contacts might be empty
                    if contacts_count == 0:
                        debug_print("⚠️ [MESHCORE-QUERY] Base de contacts VIDE - diagnostic:")
                        
                        # Check if sync_contacts was called
                        if hasattr(self.meshcore, 'contacts_synced'):
                            debug_print(f"   contacts_synced flag: {self.meshcore.contacts_synced}")
                        
                        # Check for alternative contact access methods
                        alt_methods = ['get_contacts', 'list_contacts', 'contacts_list', 'contact_list']
                        found_methods = [m for m in alt_methods if hasattr(self.meshcore, m)]
                        if found_methods:
                            debug_print(f"   Méthodes alternatives disponibles: {', '.join(found_methods)}")
                            
                            # Try alternative methods to get contacts
                            for method_name in found_methods:
                                try:
                                    method = getattr(self.meshcore, method_name)
                                    if callable(method):
                                        debug_print(f"   Tentative {method_name}()...")
                                        # Don't call async methods here
                                        if not asyncio.iscoroutinefunction(method):
                                            result = method()
                                            debug_print(f"   → {method_name}() retourne: {type(result).__name__} (len={len(result) if result else 0})")
                                except Exception as alt_err:
                                    debug_print(f"   → Erreur {method_name}(): {alt_err}")
                        
                        # Check meshcore object attributes
                        debug_print("   Attributs meshcore disponibles:")
                        relevant_attrs = [attr for attr in dir(self.meshcore) if 'contact' in attr.lower() or 'key' in attr.lower()]
                        for attr in relevant_attrs[:10]:  # Show first 10
                            try:
                                value = getattr(self.meshcore, attr)
                                debug_print(f"      • {attr}: {type(value).__name__}")
                            except:
                                pass
                    
                except Exception as ce:
                    debug_print(f"⚠️ [MESHCORE-QUERY] Impossible de compter les contacts: {ce}")
            
            # Query meshcore for contact by pubkey prefix
            contact = None
            if hasattr(self.meshcore, 'get_contact_by_key_prefix'):
                debug_print(f"🔍 [MESHCORE-QUERY] Appel get_contact_by_key_prefix('{pubkey_prefix}')...")
                contact = self.meshcore.get_contact_by_key_prefix(pubkey_prefix)
                debug_print(f"📋 [MESHCORE-QUERY] Résultat: {type(contact).__name__} = {contact}")
            else:
                error_print(f"❌ [MESHCORE-QUERY] meshcore.get_contact_by_key_prefix() non disponible")
                error_print(f"   → Vérifier version meshcore-cli (besoin >= 2.2.5)")
                return None
            
            if not contact:
                debug_print(f"⚠️ [MESHCORE-QUERY] Aucun contact trouvé pour pubkey_prefix: {pubkey_prefix}")
                # Debug: list available pubkey prefixes
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    try:
                        debug_print(f"🔑 [MESHCORE-QUERY] Préfixes de clés disponibles:")
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
                                debug_print(f"   {i+1}. {prefix}... (nom: {c.get('name', 'unknown')})")
                    except Exception as debug_err:
                        debug_print(f"⚠️ [MESHCORE-QUERY] Erreur debug contacts: {debug_err}")
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
                        debug_print(f"🔑 [MESHCORE-QUERY] Node ID dérivé du public_key: 0x{contact_id:08x}")
                    elif isinstance(public_key, bytes) and len(public_key) >= 4:
                        # If public_key is bytes, extract first 4 bytes
                        contact_id = int.from_bytes(public_key[:4], 'big')
                        debug_print(f"🔑 [MESHCORE-QUERY] Node ID dérivé du public_key: 0x{contact_id:08x}")
                except Exception as pk_err:
                    debug_print(f"⚠️ [MESHCORE-QUERY] Erreur extraction node_id depuis public_key: {pk_err}")
            
            if not contact_id:
                debug_print("⚠️ [MESHCORE-QUERY] Contact trouvé mais pas de contact_id et impossible de dériver du public_key")
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
            
            debug_print(f"✅ [MESHCORE-QUERY] Contact trouvé: {name or 'Unknown'} (0x{contact_id:08x})")
            
            # Extract GPS coordinates from meshcore contact (uses adv_lat/adv_lon fields)
            lat = contact.get('lat') or contact.get('latitude') or contact.get('adv_lat')
            lon = contact.get('lon') or contact.get('longitude') or contact.get('adv_lon')
            alt = contact.get('alt') or contact.get('altitude')
            
            # Save to SQLite meshcore_contacts table (separate from Meshtastic nodes)
            if hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                contact_data = {
                    'node_id': contact_id,
                    'name': name or f"Node-{contact_id:08x}",
                    'shortName': contact.get('short_name', ''),
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
                debug_print(f"💾 [MESHCORE-QUERY] Contact sauvegardé: {name}")
            else:
                # Fallback to in-memory storage if SQLite not available
                if contact_id not in self.node_manager.node_names:
                    self.node_manager.node_names[contact_id] = {
                        'name': name or f"Node-{contact_id:08x}",
                        'shortName': contact.get('short_name', ''),
                        'hwModel': contact.get('hw_model', None),
                        'lat': None,
                        'lon': None,
                        'alt': None,
                        'last_update': None,
                        'publicKey': public_key  # Store public key for future lookups
                    }
                    
                    # Data is automatically saved to SQLite via persistence
                    info_print(f"💾 [MESHCORE-QUERY] Contact ajouté à la base SQLite: {name}")
                else:
                    # Update publicKey if not present
                    if public_key and not self.node_manager.node_names[contact_id].get('publicKey'):
                        self.node_manager.node_names[contact_id]['publicKey'] = public_key
                        # Data is automatically saved to SQLite via persistence
                        debug_print(f"💾 [MESHCORE-QUERY] PublicKey ajouté: {name}")
            
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
        info_print("\n" + "="*60)
        info_print("🔍 [MESHCORE-CLI] Diagnostic de configuration")
        info_print("="*60)
        
        issues_found = []
        
        # Check 1: Private key access
        debug_print("\n1️⃣  Vérification clé privée...")
        has_private_key = False
        try:
            key_attrs = ['private_key', 'key', 'node_key', 'device_key', 'crypto']
            found_key_attrs = [attr for attr in key_attrs if hasattr(self.meshcore, attr)]
            
            if found_key_attrs:
                info_print(f"   ✅ Attributs clé trouvés: {', '.join(found_key_attrs)}")
                has_private_key = True
                
                for attr in found_key_attrs:
                    try:
                        value = getattr(self.meshcore, attr)
                        if value is None:
                            error_print(f"   ⚠️  {attr} est None")
                            issues_found.append(f"{attr} est None - le déchiffrement peut échouer")
                        else:
                            debug_print(f"   ✅ {attr} est défini")
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
                info_print(f"   ✅ Fichier(s) clé privée trouvé(s): {', '.join(found_key_files)}")
                has_private_key = True
                
                # Try to check if files are readable and non-empty
                for key_file in found_key_files:
                    try:
                        if os.path.exists(key_file) and os.path.isfile(key_file):
                            file_size = os.path.getsize(key_file)
                            if file_size > 0:
                                info_print(f"   ✅ {key_file} est lisible ({file_size} octets)")
                            else:
                                error_print(f"   ⚠️  {key_file} est vide")
                                issues_found.append(f"{key_file} est vide - impossible de charger la clé privée")
                    except Exception as e:
                        error_print(f"   ⚠️  Impossible d'accéder à {key_file}: {e}")
            else:
                debug_print("   ℹ️  Aucun fichier de clé privée trouvé dans le répertoire courant")
            
            if not has_private_key:
                issues_found.append("Aucune clé privée trouvée (ni en mémoire ni sous forme de fichier) - les messages chiffrés ne peuvent pas être déchiffrés")
            else:
                # NEW: Validate key pair if PyNaCl is available
                debug_print("\n   🔐 Validation paire de clés privée/publique...")
                if not NACL_AVAILABLE:
                    debug_print("   ℹ️  PyNaCl non disponible - validation de clé ignorée")
                    debug_print("      Installer avec: pip install PyNaCl")
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
                                debug_print(f"   📝 Utilisation de {attr} pour validation")
                                break
                        except Exception:
                            pass
                    
                    # Try to get from key file
                    if private_key_data is None and found_key_files:
                        try:
                            key_file = found_key_files[0]
                            with open(key_file, 'rb') as f:
                                private_key_data = f.read()
                            debug_print(f"   📝 Utilisation du fichier {key_file} pour validation")
                        except Exception as e:
                            debug_print(f"   ⚠️  Impossible de lire {key_file}: {e}")
                    
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
                            debug_print(f"   ℹ️  {error_msg}")
                        elif is_valid:
                            info_print("   ✅ Clé privée valide - peut dériver une clé publique")
                            if derived_public_key:
                                derived_hex = derived_public_key.hex()
                                info_print(f"   🔑 Clé publique dérivée: {derived_hex[:16]}...{derived_hex[-16:]}")
                                # Derive node_id from public key (first 4 bytes)
                                derived_node_id = int.from_bytes(derived_public_key[:4], 'big')
                                info_print(f"   🆔 Node ID dérivé: 0x{derived_node_id:08x}")
                                
                                # Compare with actual node_id if available
                                if hasattr(self.meshcore, 'node_id'):
                                    actual_node_id = self.meshcore.node_id
                                    if actual_node_id == derived_node_id:
                                        info_print(f"   ✅ Node ID correspond: 0x{actual_node_id:08x}")
                                    else:
                                        error_print(f"   ❌ Node ID ne correspond PAS!")
                                        error_print(f"      Dérivé:  0x{derived_node_id:08x}")
                                        error_print(f"      Actuel:  0x{actual_node_id:08x}")
                                        issues_found.append(f"Node ID dérivé (0x{derived_node_id:08x}) != Node ID actuel (0x{actual_node_id:08x}) - la clé privée ne correspond pas au device!")
                        else:
                            error_print(f"   ❌ Validation de clé échouée: {error_msg}")
                            issues_found.append(f"Validation de paire de clés échouée: {error_msg}")
                    else:
                        debug_print("   ⚠️  Impossible d'obtenir les données de clé privée pour validation")
        except Exception as e:
            error_print(f"   ⚠️  Erreur vérification clé privée: {e}")
            issues_found.append(f"Erreur vérification clé privée: {e}")
        
        # Check 2: Contact sync capability
        debug_print("\n2️⃣  Vérification capacité sync contacts...")
        if hasattr(self.meshcore, 'sync_contacts'):
            debug_print("   ✅ Méthode sync_contacts() disponible")
        else:
            error_print("   ❌ Méthode sync_contacts() NON disponible")
            issues_found.append("sync_contacts() non disponible - la synchronisation des contacts ne peut pas être effectuée")
        
        # Check 3: Auto message fetching
        debug_print("\n3️⃣  Vérification auto message fetching...")
        if hasattr(self.meshcore, 'start_auto_message_fetching'):
            info_print("   ✅ start_auto_message_fetching() disponible")
        else:
            error_print("   ❌ start_auto_message_fetching() NON disponible")
            issues_found.append("start_auto_message_fetching() non disponible - les messages doivent être récupérés manuellement")
        
        # Check 4: Event dispatcher
        debug_print("\n4️⃣  Vérification event dispatcher...")
        if hasattr(self.meshcore, 'events'):
            info_print("   ✅ Event dispatcher (events) disponible")
        elif hasattr(self.meshcore, 'dispatcher'):
            info_print("   ✅ Event dispatcher (dispatcher) disponible")
        else:
            error_print("   ❌ Aucun event dispatcher trouvé")
            issues_found.append("Aucun event dispatcher - les événements ne peuvent pas être reçus")
        
        # Summary
        info_print("\n" + "="*60)
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
            info_print("✅ Aucun problème de configuration détecté")
        info_print("="*60 + "\n")
        
        return len(issues_found) == 0
    
    async def _verify_contacts(self):
        """Verify that contacts were actually synced"""
        try:
            if hasattr(self.meshcore, 'contacts'):
                contacts = self.meshcore.contacts
                if contacts:
                    debug_print(f"   ✅ {len(contacts)} contact(s) synchronisé(s)")
                else:
                    error_print("   ⚠️  Liste de contacts vide")
                    error_print("      Le déchiffrement des DM peut échouer")
            elif hasattr(self.meshcore, 'get_contacts'):
                contacts = await self.meshcore.get_contacts()
                if contacts:
                    debug_print(f"   ✅ {len(contacts)} contact(s) synchronisé(s)")
                else:
                    error_print("   ⚠️  Liste de contacts vide")
                    error_print("      Le déchiffrement des DM peut échouer")
            else:
                debug_print("   ℹ️  Impossible de vérifier la liste des contacts")
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
                info_print("✅ [MESHCORE-CLI] Souscription aux messages DM (events.subscribe)")
                
                # Also subscribe to RX_LOG_DATA to monitor ALL RF packets
                # This allows the bot to see broadcasts, telemetry, and all mesh traffic (not just DMs)
                rx_log_enabled = False
                try:
                    import config
                    rx_log_enabled = getattr(config, 'MESHCORE_RX_LOG_ENABLED', True)
                except ImportError:
                    rx_log_enabled = True  # Default to enabled
                
                if rx_log_enabled and hasattr(EventType, 'RX_LOG_DATA'):
                    self.meshcore.events.subscribe(EventType.RX_LOG_DATA, self._on_rx_log_data)
                    info_print("✅ [MESHCORE-CLI] Souscription à RX_LOG_DATA (tous les paquets RF)")
                    info_print("   → Le bot peut maintenant voir TOUS les paquets mesh (broadcasts, télémétrie, etc.)")
                elif not rx_log_enabled:
                    info_print("ℹ️  [MESHCORE-CLI] RX_LOG_DATA désactivé (MESHCORE_RX_LOG_ENABLED=False)")
                    info_print("   → Le bot ne verra que les DM, pas les broadcasts")
                elif not hasattr(EventType, 'RX_LOG_DATA'):
                    debug_print("⚠️ [MESHCORE-CLI] EventType.RX_LOG_DATA non disponible (version meshcore-cli ancienne?)")
                
            elif hasattr(self.meshcore, 'dispatcher'):
                self.meshcore.dispatcher.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_message)
                info_print("✅ [MESHCORE-CLI] Souscription aux messages DM (dispatcher.subscribe)")
                
                # Also subscribe to RX_LOG_DATA
                rx_log_enabled = False
                try:
                    import config
                    rx_log_enabled = getattr(config, 'MESHCORE_RX_LOG_ENABLED', True)
                except ImportError:
                    rx_log_enabled = True
                
                if rx_log_enabled and hasattr(EventType, 'RX_LOG_DATA'):
                    self.meshcore.dispatcher.subscribe(EventType.RX_LOG_DATA, self._on_rx_log_data)
                    info_print("✅ [MESHCORE-CLI] Souscription à RX_LOG_DATA (tous les paquets RF)")
                    info_print("   → Le bot peut maintenant voir TOUS les paquets mesh")
                elif not rx_log_enabled:
                    info_print("ℹ️  [MESHCORE-CLI] RX_LOG_DATA désactivé")
            else:
                error_print("❌ [MESHCORE-CLI] Ni events ni dispatcher trouvé")
                return False
            
            debug_print(f"[MESHCORE-CLI] MeshCore object: {self.meshcore}")
            debug_print(f"[MESHCORE-CLI] EventType.CONTACT_MSG_RECV: {EventType.CONTACT_MSG_RECV}")
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
        info_print("✅ [MESHCORE-CLI] Thread événements démarré")
        
        # Start healthcheck monitoring
        self.healthcheck_thread = threading.Thread(
            target=self._healthcheck_monitor,
            name="MeshCore-Healthcheck",
            daemon=True
        )
        self.healthcheck_thread.start()
        info_print("✅ [MESHCORE-CLI] Healthcheck monitoring démarré")
        
        # Initialize last message time
        self.last_message_time = time.time()
        
        return True
    
    def _healthcheck_monitor(self):
        """Monitor meshcore connection health and alert on failures"""
        info_print("🏥 [MESHCORE-HEALTHCHECK] Healthcheck monitoring started")
        
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
                            error_print(f"⚠️ [MESHCORE-HEALTHCHECK] ALERTE: Aucun message reçu depuis {int(time_since_last_message)}s")
                            error_print(f"   → La connexion au nœud semble perdue")
                            error_print(f"   → Vérifiez: 1) Le nœud est allumé")
                            error_print(f"   →          2) Le câble série est connecté ({self.port})")
                            error_print(f"   →          3) meshcore-cli peut se connecter: meshcore-cli -s {self.port} -b {self.baudrate} chat")
                            self.connection_healthy = False
                    else:
                        # Connection is healthy
                        if not self.connection_healthy:
                            info_print(f"✅ [MESHCORE-HEALTHCHECK] Connexion rétablie (message reçu il y a {int(time_since_last_message)}s)")
                            self.connection_healthy = True
                        
                        if self.debug:
                            debug_print(f"🏥 [MESHCORE-HEALTHCHECK] OK - dernier message: {int(time_since_last_message)}s")
                
                # Sleep until next check
                time.sleep(self.healthcheck_interval)
                
            except Exception as e:
                error_print(f"❌ [MESHCORE-HEALTHCHECK] Erreur: {e}")
                error_print(traceback.format_exc())
                time.sleep(self.healthcheck_interval)
        
        info_print("🏥 [MESHCORE-HEALTHCHECK] Healthcheck monitoring stopped")
    
    def _async_event_loop(self):
        """Boucle asyncio pour gérer les événements MeshCore"""
        info_print("📡 [MESHCORE-CLI] Début écoute événements...")
        
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
                    if hasattr(self.meshcore, 'sync_contacts'):
                        # Get initial count for comparison
                        initial_count = 0
                        if hasattr(self.meshcore, 'contacts'):
                            initial_contacts = self.meshcore.contacts
                            initial_count = len(initial_contacts) if initial_contacts else 0
                        
                        # Sync contacts (silent unless DEBUG_MODE)
                        await self.meshcore.sync_contacts()
                        
                        # Check post-sync state
                        if hasattr(self.meshcore, 'contacts'):
                            post_contacts = self.meshcore.contacts
                            post_count = len(post_contacts) if post_contacts else 0
                            
                            # SAVE CONTACTS TO DATABASE (like NODEINFO for Meshtastic)
                            if post_count > 0 and self.node_manager and hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                                saved_count = 0
                                for contact in post_contacts:
                                    try:
                                        contact_id = contact.get('contact_id') or contact.get('node_id')
                                        name = contact.get('name') or contact.get('long_name')
                                        public_key = contact.get('public_key') or contact.get('publicKey')
                                        
                                        # Convert contact_id to int if string
                                        if isinstance(contact_id, str):
                                            if contact_id.startswith('!'):
                                                contact_id = int(contact_id[1:], 16)
                                            else:
                                                try:
                                                    contact_id = int(contact_id, 16)
                                                except ValueError:
                                                    contact_id = int(contact_id)
                                        
                                        contact_data = {
                                            'node_id': contact_id,
                                            'name': name or f"Node-{contact_id:08x}",
                                            'shortName': contact.get('short_name', ''),
                                            'hwModel': contact.get('hw_model', None),
                                            'publicKey': public_key,
                                            'lat': contact.get('latitude', None),
                                            'lon': contact.get('longitude', None),
                                            'alt': contact.get('altitude', None),
                                            'source': 'meshcore'
                                        }
                                        self.node_manager.persistence.save_meshcore_contact(contact_data)
                                        # CRITICAL: Also add to meshcore.contacts dict
                                        self._add_contact_to_meshcore(contact_data)
                                        saved_count += 1
                                    except Exception as save_err:
                                        # Only log errors, not every save
                                        debug_print(f"⚠️ [MESHCORE-SYNC] Erreur sauvegarde contact {contact.get('name', 'Unknown')}: {save_err}")
                                
                                # Single summary line instead of verbose logging
                                info_print(f"💾 [MESHCORE-SYNC] {saved_count}/{post_count} contacts sauvegardés")
                            elif post_count > 0:
                                # Contacts were synced but save conditions failed - only show in DEBUG
                                debug_print(f"⚠️ [MESHCORE-SYNC] {post_count} contacts synchronisés mais NON SAUVEGARDÉS")
                                if not self.node_manager:
                                    debug_print("   → node_manager non configuré")
                                elif not hasattr(self.node_manager, 'persistence') or not self.node_manager.persistence:
                                    debug_print("   → persistence non configuré")
                            
                            if post_count == 0:
                                # Only warn if no contacts found - important to know
                                error_print("⚠️ [MESHCORE-SYNC] ATTENTION: sync_contacts() n'a trouvé AUCUN contact!")
                                error_print("   → Raisons: mode companion (appairage requis), base vide, ou problème de clé")
                        
                        # Check if contacts were actually synced (silent unless DEBUG)
                        await self._verify_contacts()
                    else:
                        info_print("⚠️ [MESHCORE-CLI] sync_contacts() non disponible")
                        error_print("   ⚠️ Sans sync_contacts(), le déchiffrement des DM peut échouer")
                except Exception as e:
                    error_print(f"❌ [MESHCORE-CLI] Erreur sync_contacts: {e}")
                    error_print(traceback.format_exc())
                    error_print("   ⚠️ Le déchiffrement des messages entrants peut échouer")
                
                # CRITICAL: Start auto message fetching to receive events
                try:
                    if hasattr(self.meshcore, 'start_auto_message_fetching'):
                        await self.meshcore.start_auto_message_fetching()
                        info_print("✅ [MESHCORE-CLI] Auto message fetching démarré")
                    else:
                        info_print("⚠️ [MESHCORE-CLI] start_auto_message_fetching() non disponible")
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
            info_print("🔄 [MESHCORE-CLI] Démarrage boucle d'événements...")
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
                debug_print(f"⚠️ [MESHCORE-CLI] Erreur nettoyage loop: {cleanup_err}")
        
        info_print("📡 [MESHCORE-CLI] Arrêt écoute événements")
    
    def _on_contact_message(self, event):
        """
        Callback pour les messages de contact (DM)
        Appelé par le dispatcher de meshcore-cli
        
        Args:
            event: Event object from meshcore dispatcher
        """
        info_print("🔔🔔🔔 [MESHCORE-CLI] _on_contact_message CALLED! Event received!")
        try:
            # Update last message time for healthcheck
            self.last_message_time = time.time()
            self.connection_healthy = True
            
            # Safely log event - don't convert to string as it may contain problematic characters
            try:
                debug_print(f"🔔 [MESHCORE-CLI] Event reçu - type: {type(event).__name__}")
                if hasattr(event, 'type'):
                    debug_print(f"   Event.type: {event.type}")
            except Exception as log_err:
                debug_print(f"🔔 [MESHCORE-CLI] Event reçu (erreur log: {log_err})")
            
            # Extraire les informations de l'événement
            # L'API meshcore fournit un objet event avec payload
            payload = event.payload if hasattr(event, 'payload') else event
            
            # Safely log payload
            try:
                debug_print(f"📦 [MESHCORE-CLI] Payload type: {type(payload).__name__}")
                if isinstance(payload, dict):
                    debug_print(f"📦 [MESHCORE-CLI] Payload keys: {list(payload.keys())}")
                    # Log important fields individually
                    for key in ['type', 'pubkey_prefix', 'contact_id', 'sender_id', 'text']:
                        if key in payload:
                            value = payload[key]
                            if key == 'text':
                                value = value[:50] + '...' if len(str(value)) > 50 else value
                            debug_print(f"   {key}: {value}")
                else:
                    debug_print(f"📦 [MESHCORE-CLI] Payload: {str(payload)[:200]}")
            except Exception as log_err:
                debug_print(f"📦 [MESHCORE-CLI] Payload (erreur log: {log_err})")
            
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
                debug_print(f"📋 [MESHCORE-DM] Payload dict - contact_id: {sender_id}, pubkey_prefix: {pubkey_prefix}")
            
            # Méthode 2: Chercher dans les attributs de l'event
            if sender_id is None and hasattr(event, 'attributes'):
                attributes = event.attributes
                debug_print(f"📋 [MESHCORE-DM] Event attributes: {attributes}")
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
                    debug_print(f"📋 [MESHCORE-DM] Event direct contact_id: {sender_id}")
            
            # Méthode 3b: Chercher pubkey_prefix directement sur l'event
            if pubkey_prefix is None:
                for attr_name in ['pubkey_prefix', 'pubkeyPrefix', 'public_key_prefix', 'publicKeyPrefix']:
                    if hasattr(event, attr_name):
                        attr_value = getattr(event, attr_name)
                        # Only use if it's a non-empty string
                        if attr_value and isinstance(attr_value, str):
                            pubkey_prefix = attr_value
                            debug_print(f"📋 [MESHCORE-DM] Event direct {attr_name}: {pubkey_prefix}")
                            break
            
            debug_print(f"🔍 [MESHCORE-DM] Après extraction - sender_id: {sender_id}, pubkey_prefix: {pubkey_prefix}")
            
            # Méthode 4: Si sender_id est None mais qu'on a un pubkey_prefix, essayer de le résoudre
            # IMPORTANT: Pour les DMs via meshcore-cli, on recherche SEULEMENT dans meshcore_contacts
            # (pas dans meshtastic_nodes) pour éviter de mélanger les deux sources
            if sender_id is None and pubkey_prefix and self.node_manager:
                debug_print(f"🔍 [MESHCORE-DM] Tentative résolution pubkey_prefix: {pubkey_prefix}")
                
                # First try: lookup in meshcore_contacts ONLY (not meshtastic_nodes)
                sender_id = self.node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
                if sender_id:
                    info_print(f"✅ [MESHCORE-DM] Résolu pubkey_prefix {pubkey_prefix} → 0x{sender_id:08x} (meshcore cache)")
                    
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
                            debug_print(f"💾 [MESHCORE-DM] Contact chargé depuis DB et ajouté au dict")
                    except Exception as load_err:
                        debug_print(f"⚠️ [MESHCORE-DM] Erreur chargement contact depuis DB: {load_err}")
                else:
                    # Second try: query meshcore-cli API directly
                    debug_print(f"🔍 [MESHCORE-DM] Pas dans le cache meshcore, interrogation API meshcore-cli...")
                    sender_id = self.query_contact_by_pubkey_prefix(pubkey_prefix)
                    if sender_id:
                        info_print(f"✅ [MESHCORE-DM] Résolu pubkey_prefix {pubkey_prefix} → 0x{sender_id:08x} (meshcore-cli API)")
            
            # Méthode 5: FALLBACK - Derive node_id from pubkey_prefix
            # In MeshCore/Meshtastic, the node_id is the FIRST 4 BYTES of the 32-byte public key
            # If we have a pubkey_prefix (which is a hex string of the public key), we can derive the node_id
            # This allows us to process DMs even when the contact isn't in the device's contact list yet
            if sender_id is None and pubkey_prefix:
                try:
                    debug_print(f"🔑 [MESHCORE-DM] FALLBACK: Dérivation node_id depuis pubkey_prefix")
                    
                    # pubkey_prefix is a hex string (e.g., '143bcd7f1b1f...')
                    # We need the first 8 hex chars (= 4 bytes) for the node_id
                    if len(pubkey_prefix) >= 8:
                        # First 8 hex chars = first 4 bytes = node_id
                        node_id_hex = pubkey_prefix[:8]
                        sender_id = int(node_id_hex, 16)
                        info_print(f"✅ [MESHCORE-DM] Node_id dérivé de pubkey: {pubkey_prefix[:12]}... → 0x{sender_id:08x}")
                        
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
                                    'shortName': f"{sender_id:08x}",
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
                                debug_print(f"💾 [MESHCORE-DM] Contact dérivé sauvegardé: 0x{sender_id:08x}")
                            except Exception as save_err:
                                debug_print(f"⚠️ [MESHCORE-DM] Erreur sauvegarde contact dérivé: {save_err}")
                    else:
                        debug_print(f"⚠️ [MESHCORE-DM] pubkey_prefix trop court pour dériver node_id: {pubkey_prefix}")
                except Exception as derive_err:
                    error_print(f"❌ [MESHCORE-DM] Erreur dérivation node_id: {derive_err}")
                    error_print(traceback.format_exc())
            
            text = payload.get('text', '') if isinstance(payload, dict) else ''
            
            # Log avec gestion de None pour sender_id
            if sender_id is not None:
                info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
            else:
                # Fallback: afficher pubkey_prefix si disponible
                if pubkey_prefix:
                    info_print(f"📬 [MESHCORE-DM] De: {pubkey_prefix} (non résolu) | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
                else:
                    info_print(f"📬 [MESHCORE-DM] De: <inconnu> | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
            
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
                '_meshcore_dm': True  # Marquer comme DM MeshCore pour traitement spécial
            }
            
            # Appeler le callback
            if self.message_callback:
                info_print(f"📞 [MESHCORE-CLI] Calling message_callback for message from 0x{sender_id:08x}")
                self.message_callback(packet, None)
                info_print(f"✅ [MESHCORE-CLI] Callback completed successfully")
            else:
                error_print(f"⚠️ [MESHCORE-CLI] No message_callback set!")
                
        except Exception as e:
            error_print(f"❌ [MESHCORE-CLI] Erreur traitement message: {e}")
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
                debug_print(f"⚠️ [RX_LOG] Payload non-dict: {type(payload).__name__}")
                return
            
            # Extract packet metadata
            snr = payload.get('snr', 0.0)
            rssi = payload.get('rssi', 0)
            raw_hex = payload.get('raw_hex', '')
            
            # Log RF activity with basic info
            debug_print(f"📡 [RX_LOG] Paquet RF reçu - SNR:{snr}dB RSSI:{rssi}dBm Hex:{raw_hex[:20]}...")
            
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
                    
                    # Add message hash if available
                    if packet.message_hash:
                        info_parts.append(f"Hash: {packet.message_hash[:8]}")
                    
                    # Add path info if available
                    if packet.path_length > 0:
                        info_parts.append(f"Hops: {packet.path_length}")
                    
                    # Check if packet is valid (only flag as invalid for non-unknown-type errors)
                    if unknown_type_error:
                        # Unknown types are common and not really "invalid"
                        validity = "ℹ️"  # Info icon instead of warning
                    else:
                        validity = "✅" if packet.is_valid else "⚠️"
                    info_parts.append(f"Status: {validity}")
                    
                    # Log decoded packet information
                    debug_print(f"📦 [RX_LOG] {' | '.join(info_parts)}")
                    
                    # Log non-unknown-type errors only
                    if packet.errors:
                        other_errors = [e for e in packet.errors if "is not a valid PayloadType" not in e]
                        for error in other_errors[:3]:  # Show first 3 non-type errors
                            debug_print(f"   ⚠️ {error}")
                    
                    # If payload is decoded, show a preview
                    if packet.payload and isinstance(packet.payload, dict):
                        decoded_payload = packet.payload.get('decoded')
                        if decoded_payload:
                            # Show payload type-specific info
                            if hasattr(decoded_payload, 'text'):
                                # TextMessage
                                text_preview = decoded_payload.text[:50] if len(decoded_payload.text) > 50 else decoded_payload.text
                                debug_print(f"📝 [RX_LOG] Message: \"{text_preview}\"")
                            elif hasattr(decoded_payload, 'app_data'):
                                # Advert with app_data
                                app_data = decoded_payload.app_data
                                if isinstance(app_data, dict):
                                    name = app_data.get('name', 'Unknown')
                                    debug_print(f"📢 [RX_LOG] Advert from: {name}")
                    
                except Exception as decode_error:
                    # Decoder failed, but that's OK - packet might be malformed or incomplete
                    debug_print(f"📊 [RX_LOG] Décodage non disponible: {str(decode_error)[:60]}")
            else:
                # Decoder not available, show basic info
                if not MESHCORE_DECODER_AVAILABLE:
                    debug_print(f"📊 [RX_LOG] RF monitoring only (meshcore-decoder not installed)")
                else:
                    debug_print(f"📊 [RX_LOG] RF monitoring only (no hex data)")
            
        except Exception as e:
            debug_print(f"⚠️ [RX_LOG] Erreur traitement RX_LOG_DATA: {e}")
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
            debug_print("⚠️ [MESHCORE-DM] NodeManager ou persistence non disponible")
            return None
        
        try:
            debug_print(f"🔍 [MESHCORE-DM] Recherche pubkey_prefix pour node 0x{node_id:08x}")
            
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
                debug_print(f"✅ [MESHCORE-DM] pubkey_prefix trouvé: {pubkey_prefix}")
                return pubkey_prefix
            else:
                debug_print(f"⚠️ [MESHCORE-DM] Pas de publicKey en DB pour node 0x{node_id:08x}")
                return None
                
        except Exception as e:
            debug_print(f"⚠️ [MESHCORE-DM] Erreur recherche pubkey_prefix: {e}")
            if self.debug:
                error_print(traceback.format_exc())
            return None

    def sendText(self, text, destinationId, wantAck=False, channelIndex=0):
        """
        Envoie un message texte via MeshCore
        
        Args:
            text: Texte à envoyer
            destinationId: ID du destinataire (node_id)
            wantAck: Demander un accusé de réception (ignoré en mode companion)
            channelIndex: Canal (ignoré en mode companion)
        
        Returns:
            bool: True si envoyé avec succès
        """
        if not self.meshcore:
            error_print("❌ [MESHCORE-CLI] Non connecté")
            return False
        
        try:
            debug_print(f"📤 [MESHCORE-DM] Envoi à 0x{destinationId:08x}: {text[:50]}{'...' if len(text) > 50 else ''}")
            
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
                debug_print(f"🔍 [MESHCORE-DM] Recherche contact avec pubkey_prefix: {pubkey_prefix}")
                
                # DIAGNOSTIC: Show what's in meshcore.contacts dict
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    debug_print(f"📊 [MESHCORE-DM] meshcore.contacts dict size: {len(self.meshcore.contacts)}")
                    debug_print(f"📊 [MESHCORE-DM] Dict keys: {list(self.meshcore.contacts.keys())}")
                else:
                    debug_print(f"⚠️ [MESHCORE-DM] meshcore.contacts is None or empty!")
                
                # FIX: Direct dict access instead of meshcore-cli method
                # The get_contact_by_key_prefix() method doesn't work with our manually added contacts
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    contact = self.meshcore.contacts.get(pubkey_prefix)
                    if contact:
                        debug_print(f"✅ [MESHCORE-DM] Contact trouvé via dict direct: {contact.get('adv_name', 'unknown')}")
                    else:
                        debug_print(f"⚠️ [MESHCORE-DM] Contact non trouvé dans dict (clé: {pubkey_prefix})")
            else:
                debug_print(f"⚠️ [MESHCORE-DM] Pas de pubkey_prefix en DB, recherche avec node_id")
                # Fallback: try with node_id hex (8 chars) in dict
                hex_id = f"{destinationId:08x}"
                if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                    contact = self.meshcore.contacts.get(hex_id)
            
            # If not found, use the destinationId directly
            # The send_msg API should accept either contact dict or node_id
            if not contact:
                debug_print(f"⚠️ [MESHCORE-DM] Contact non trouvé, utilisation de l'ID directement")
                contact = destinationId
            
            # Send via commands.send_msg
            # Use run_coroutine_threadsafe since the event loop is already running
            debug_print(f"🔍 [MESHCORE-DM] Appel de commands.send_msg(contact={type(contact).__name__}, text=...)")
            
            # DIAGNOSTIC: Check event loop status
            debug_print(f"🔄 [MESHCORE-DM] Event loop running: {self._loop.is_running()}")
            debug_print(f"🔄 [MESHCORE-DM] Submitting coroutine to event loop...")
            
            future = asyncio.run_coroutine_threadsafe(
                self.meshcore.commands.send_msg(contact, text),
                self._loop
            )
            
            # FIRE-AND-FORGET APPROACH
            # Don't wait for result - the coroutine is hanging waiting for ACK that never comes
            # Let the message send asynchronously in the background
            debug_print(f"✅ [MESHCORE-DM] Message submitted to event loop (fire-and-forget)")
            debug_print(f"📤 [MESHCORE-DM] Coroutine will complete asynchronously in background")
            
            # Optional: Add error handler to the future to log any exceptions
            def _log_future_result(fut):
                try:
                    if fut.exception():
                        error_print(f"❌ [MESHCORE-DM] Async send error: {fut.exception()}")
                    else:
                        debug_print(f"✅ [MESHCORE-DM] Async send completed successfully")
                except Exception as e:
                    debug_print(f"⚠️ [MESHCORE-DM] Future check error: {e}")
            
            future.add_done_callback(_log_future_result)
            
            # Return immediately - don't block waiting for result
            # LoRa is inherently unreliable anyway, we send and hope it arrives
            debug_print("✅ [MESHCORE-DM] Message envoyé (fire-and-forget)")
            return True
                
        except Exception as e:
            error_print(f"❌ [MESHCORE-DM] Erreur envoi: {e}")
            error_print(traceback.format_exc())
            return False
    
    def close(self):
        """Ferme la connexion MeshCore"""
        info_print("🔌 [MESHCORE-CLI] Fermeture connexion...")
        
        self.running = False
        
        # Stop the async event loop if running
        if hasattr(self, '_loop') and self._loop and self._loop.is_running():
            info_print("🛑 [MESHCORE-CLI] Arrêt de la boucle d'événements...")
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self.message_thread and self.message_thread.is_alive():
            info_print("⏳ [MESHCORE-CLI] Attente du thread de messages...")
            self.message_thread.join(timeout=5)
        
        if self.healthcheck_thread and self.healthcheck_thread.is_alive():
            info_print("⏳ [MESHCORE-CLI] Attente du thread healthcheck...")
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
                info_print("✅ [MESHCORE-CLI] Boucle d'événements fermée")
            except Exception as e:
                debug_print(f"⚠️ [MESHCORE-CLI] Erreur fermeture loop: {e}")
        
        info_print("✅ [MESHCORE-CLI] Connexion fermée")


# Alias pour compatibilité avec le code existant
MeshCoreSerialInterface = MeshCoreCLIWrapper
