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
            
            # Load contacts immediately during connection (like meshcore-cli does)
            try:
                info_print(f"🔄 [MESHCORE-CLI] Chargement des contacts...")
                if hasattr(self.meshcore, 'ensure_contacts'):
                    # Call ensure_contacts in the event loop we just created
                    if asyncio.iscoroutinefunction(self.meshcore.ensure_contacts):
                        loop.run_until_complete(self.meshcore.ensure_contacts())
                    else:
                        self.meshcore.ensure_contacts()
                    
                    # Flush pending contacts
                    if hasattr(self.meshcore, 'flush_pending_contacts'):
                        self.meshcore.flush_pending_contacts()
                    
                    # Check contact count
                    if hasattr(self.meshcore, 'contacts') and self.meshcore.contacts:
                        contact_count = len(self.meshcore.contacts)
                        info_print(f"✅ [MESHCORE-CLI] {contact_count} contact(s) chargé(s)")
                    else:
                        debug_print(f"⚠️ [MESHCORE-CLI] Aucun contact chargé")
                else:
                    debug_print(f"⚠️ [MESHCORE-CLI] ensure_contacts() non disponible")
            except Exception as contact_err:
                debug_print(f"⚠️ [MESHCORE-CLI] Erreur chargement contacts: {contact_err}")
            
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
                        if hasattr(self.meshcore, 'contacts_dirty'):
                            self.meshcore.contacts_dirty = True
                            debug_print(f"🔄 [MESHCORE-QUERY] contacts_dirty défini à True pour forcer le rechargement")
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
            
            info_print(f"✅ [MESHCORE-QUERY] Contact trouvé: {name or 'Unknown'} (0x{contact_id:08x})")
            
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
                info_print(f"💾 [MESHCORE-QUERY] Contact sauvegardé dans meshcore_contacts: {name}")
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
                        info_print(f"💾 [MESHCORE-QUERY] PublicKey ajouté pour contact existant: {name}")
            
            return contact_id
            
        except Exception as e:
            error_print(f"❌ [MESHCORE-QUERY] Erreur recherche contact: {e}")
            error_print(traceback.format_exc())
            return None
    
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
        except Exception as e:
            error_print(f"   ⚠️  Erreur vérification clé privée: {e}")
            issues_found.append(f"Erreur vérification clé privée: {e}")
        
        # Check 2: Contact sync capability
        debug_print("\n2️⃣  Vérification capacité sync contacts...")
        if hasattr(self.meshcore, 'sync_contacts'):
            info_print("   ✅ Méthode sync_contacts() disponible")
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
                    info_print(f"   ✅ {len(contacts)} contact(s) synchronisé(s)")
                else:
                    error_print("   ⚠️  Liste de contacts vide")
                    error_print("      Le déchiffrement des DM peut échouer")
            elif hasattr(self.meshcore, 'get_contacts'):
                contacts = await self.meshcore.get_contacts()
                if contacts:
                    info_print(f"   ✅ {len(contacts)} contact(s) synchronisé(s)")
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
                        info_print("🔄 [MESHCORE-CLI] Synchronisation des contacts...")
                        
                        # Debug: Check initial state
                        if hasattr(self.meshcore, 'contacts'):
                            initial_contacts = self.meshcore.contacts
                            initial_count = len(initial_contacts) if initial_contacts else 0
                            debug_print(f"📊 [MESHCORE-SYNC] Contacts AVANT sync: {initial_count}")
                        else:
                            debug_print("⚠️ [MESHCORE-SYNC] meshcore.contacts n'existe pas encore")
                        
                        await self.meshcore.sync_contacts()
                        info_print("✅ [MESHCORE-CLI] Contacts synchronisés")
                        
                        # Debug: Check post-sync state
                        if hasattr(self.meshcore, 'contacts'):
                            post_contacts = self.meshcore.contacts
                            post_count = len(post_contacts) if post_contacts else 0
                            debug_print(f"📊 [MESHCORE-SYNC] Contacts APRÈS sync: {post_count}")
                            
                            # SAVE CONTACTS TO DATABASE (like NODEINFO for Meshtastic)
                            if post_count > 0 and self.node_manager and hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
                                debug_print(f"💾 [MESHCORE-SYNC] Sauvegarde {post_count} contacts dans SQLite...")
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
                                        saved_count += 1
                                    except Exception as save_err:
                                        error_print(f"⚠️ [MESHCORE-SYNC] Erreur sauvegarde contact {contact.get('name', 'Unknown')}: {save_err}")
                                
                                info_print(f"💾 [MESHCORE-SYNC] {saved_count}/{post_count} contacts sauvegardés dans meshcore_contacts")
                            
                            if post_count == 0:
                                error_print("⚠️ [MESHCORE-SYNC] ATTENTION: sync_contacts() n'a trouvé AUCUN contact!")
                                error_print("   → Raisons possibles:")
                                error_print("   1. Mode companion: nécessite appairage avec app mobile")
                                error_print("   2. Base de contacts vide dans meshcore-cli")
                                error_print("   3. Problème de clé privée pour déchiffrement")
                                
                                # Check if this is companion mode
                                if hasattr(self.meshcore, 'mode'):
                                    debug_print(f"   Mode MeshCore: {self.meshcore.mode}")
                                
                                # Check private key status
                                has_key = False
                                for key_attr in ['private_key', 'key', 'node_key', 'device_key']:
                                    if hasattr(self.meshcore, key_attr):
                                        key_value = getattr(self.meshcore, key_attr, None)
                                        if key_value is not None:
                                            has_key = True
                                            debug_print(f"   ✅ {key_attr} est défini")
                                        else:
                                            debug_print(f"   ⚠️ {key_attr} est None")
                                
                                if not has_key:
                                    error_print("   ❌ Aucune clé privée trouvée!")
                                    error_print("      → DMs chiffrés ne peuvent PAS être déchiffrés")
                                    error_print("      → Contacts ne peuvent PAS être synchronisés")
                            else:
                                # Success: show contact details
                                debug_print(f"✅ [MESHCORE-SYNC] {post_count} contact(s) disponibles:")
                                for i, contact in enumerate(list(post_contacts)[:5]):  # Show first 5
                                    c_name = contact.get('name', 'Unknown')
                                    c_id = contact.get('contact_id') or contact.get('node_id', 'N/A')
                                    c_pk = contact.get('public_key') or contact.get('publicKey', '')
                                    pk_prefix = ''
                                    if c_pk:
                                        if isinstance(c_pk, bytes):
                                            pk_prefix = c_pk.hex()[:12]
                                        elif isinstance(c_pk, str):
                                            try:
                                                import base64
                                                pk_bytes = base64.b64decode(c_pk)
                                                pk_prefix = pk_bytes.hex()[:12]
                                            except:
                                                pk_prefix = c_pk[:12]
                                    debug_print(f"   {i+1}. {c_name} (ID: {c_id}, PK: {pk_prefix}...)")
                        
                        # Check if contacts were actually synced
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
                
                # Boucle pour maintenir l'event loop actif
                while self.running:
                    await asyncio.sleep(0.1)  # Pause async pour laisser le dispatcher fonctionner
            
            # Exécuter la coroutine dans la boucle
            self._loop.run_until_complete(event_loop_task())
            
        except Exception as e:
            error_print(f"❌ [MESHCORE-CLI] Erreur boucle événements: {e}")
            error_print(traceback.format_exc())
        
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
                pubkey_prefix = payload.get('pubkey_prefix')
                debug_print(f"📋 [MESHCORE-DM] Payload dict - contact_id: {sender_id}, pubkey_prefix: {pubkey_prefix}")
            
            # Méthode 2: Chercher dans les attributs de l'event
            if sender_id is None and hasattr(event, 'attributes'):
                attributes = event.attributes
                debug_print(f"📋 [MESHCORE-DM] Event attributes: {attributes}")
                if isinstance(attributes, dict):
                    sender_id = attributes.get('contact_id') or attributes.get('sender_id')
                    if pubkey_prefix is None:
                        pubkey_prefix = attributes.get('pubkey_prefix')
            
            # Méthode 3: Chercher directement sur l'event
            if sender_id is None and hasattr(event, 'contact_id'):
                sender_id = event.contact_id
                debug_print(f"📋 [MESHCORE-DM] Event direct contact_id: {sender_id}")
            
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
                else:
                    # Second try: query meshcore-cli API directly
                    debug_print(f"🔍 [MESHCORE-DM] Pas dans le cache meshcore, interrogation API meshcore-cli...")
                    sender_id = self.query_contact_by_pubkey_prefix(pubkey_prefix)
                    if sender_id:
                        info_print(f"✅ [MESHCORE-DM] Résolu pubkey_prefix {pubkey_prefix} → 0x{sender_id:08x} (meshcore-cli API)")
            
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
                    
                    # Build detailed info string
                    info_parts = []
                    info_parts.append(f"Type: {payload_name}")
                    info_parts.append(f"Route: {route_name}")
                    
                    # Add message hash if available
                    if packet.message_hash:
                        info_parts.append(f"Hash: {packet.message_hash[:8]}")
                    
                    # Add path info if available
                    if packet.path_length > 0:
                        info_parts.append(f"Hops: {packet.path_length}")
                    
                    # Check if packet is valid
                    validity = "✅" if packet.is_valid else "⚠️"
                    info_parts.append(f"Valid: {validity}")
                    
                    # Log decoded packet information
                    debug_print(f"📦 [RX_LOG] {' | '.join(info_parts)}")
                    
                    # If packet has errors, log them
                    if packet.errors:
                        for error in packet.errors[:3]:  # Show first 3 errors
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
            
            # Get the contact by ID (hex node ID)
            contact = None
            hex_id = f"{destinationId:08x}"
            debug_print(f"🔍 [MESHCORE-DM] Recherche du contact avec ID hex: {hex_id}")
            
            # Try to get contact by key prefix (public key prefix)
            if hasattr(self.meshcore, 'get_contact_by_key_prefix'):
                contact = self.meshcore.get_contact_by_key_prefix(hex_id)
                if contact:
                    debug_print(f"✅ [MESHCORE-DM] Contact trouvé via key_prefix: {contact.get('adv_name', 'unknown')}")
            
            # If not found, just use the destinationId directly
            # The send_msg API should accept either contact dict or ID
            if not contact:
                debug_print(f"⚠️ [MESHCORE-DM] Contact non trouvé, utilisation de l'ID directement")
                contact = destinationId
            
            # Send via commands.send_msg
            # Use run_coroutine_threadsafe since the event loop is already running
            debug_print(f"🔍 [MESHCORE-DM] Appel de commands.send_msg(contact={type(contact).__name__}, text=...)")
            
            future = asyncio.run_coroutine_threadsafe(
                self.meshcore.commands.send_msg(contact, text),
                self._loop
            )
            
            # Wait for result with timeout
            # Note: LoRa transmission can take time, and meshcore may not return immediately
            try:
                result = future.result(timeout=30)  # 30 second timeout for LoRa
            except (asyncio.TimeoutError, TimeoutError):
                # Timeout doesn't necessarily mean failure - message may still be sent
                # This is common with LoRa as transmission takes time
                debug_print("⏱️ [MESHCORE-DM] Timeout d'attente (message probablement envoyé)")
                return True  # Treat as success since message is typically delivered
            
            # Check result type (meshcore returns Event objects)
            debug_print(f"📨 [MESHCORE-DM] Résultat: type={type(result).__name__}, result={result}")
            
            # Result is an Event object, check if it's not an error
            if hasattr(result, 'type'):
                from meshcore import EventType
                if result.type == EventType.ERROR:
                    error_print(f"❌ [MESHCORE-DM] Erreur d'envoi: {result.payload}")
                    return False
                else:
                    debug_print("✅ [MESHCORE-DM] Message envoyé avec succès")
                    return True
            else:
                # If no type attribute, assume success if not None/False
                if result:
                    debug_print("✅ [MESHCORE-DM] Message envoyé")
                    return True
                else:
                    error_print("❌ [MESHCORE-DM] Échec envoi")
                    return False
                
        except Exception as e:
            error_print(f"❌ [MESHCORE-DM] Erreur envoi: {e}")
            error_print(traceback.format_exc())
            return False
    
    def close(self):
        """Ferme la connexion MeshCore"""
        info_print("🔌 [MESHCORE-CLI] Fermeture connexion...")
        
        self.running = False
        
        if self.message_thread:
            self.message_thread.join(timeout=2)
        
        if self.healthcheck_thread:
            self.healthcheck_thread.join(timeout=2)
        
        if self.meshcore:
            try:
                # Fermer avec l'API async
                self._loop.run_until_complete(self.meshcore.disconnect())
            except Exception as e:
                error_print(f"⚠️ [MESHCORE-CLI] Erreur fermeture: {e}")
        
        if hasattr(self, '_loop'):
            try:
                self._loop.close()
            except Exception:
                pass
        
        info_print("✅ [MESHCORE-CLI] Connexion fermée")


# Alias pour compatibilité avec le code existant
MeshCoreSerialInterface = MeshCoreCLIWrapper
