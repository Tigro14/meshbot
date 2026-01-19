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


class MeshCoreCLIWrapper:
    """
    Wrapper pour meshcore-cli library
    
    Utilise la library officielle meshcore-cli si disponible,
    sinon fallback vers implémentation basique
    """
    
    def __init__(self, port, baudrate=115200):
        """
        Initialise l'interface MeshCore via meshcore-cli
        
        Args:
            port: Port série (ex: /dev/ttyUSB0)
            baudrate: Vitesse de communication (défaut: 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.meshcore = None
        self.running = False
        self.message_callback = None
        self.message_thread = None
        
        # Simulation d'un localNode pour compatibilité
        self.localNode = type('obj', (object,), {
            'nodeNum': 0xFFFFFFFF,  # ID fictif pour mode companion
        })()
        
        if not MESHCORE_CLI_AVAILABLE:
            error_print("❌ [MESHCORE] meshcore-cli non disponible")
            error_print("   Installation: pip install meshcore")
            raise ImportError("meshcore-cli library required")
        
        info_print(f"🔧 [MESHCORE-CLI] Initialisation: {port}")
    
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
                MeshCore.create_serial(self.port, baudrate=self.baudrate, debug=False)
            )
            
            # Sauvegarder l'event loop pour les opérations futures
            self._loop = loop
            
            info_print(f"✅ [MESHCORE-CLI] Device connecté sur {self.port}")
            
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
        self.message_callback = callback
        info_print("✅ [MESHCORE-CLI] Callback message défini")
    
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
            elif hasattr(self.meshcore, 'dispatcher'):
                self.meshcore.dispatcher.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_message)
                info_print("✅ [MESHCORE-CLI] Souscription aux messages DM (dispatcher.subscribe)")
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
        return True
    
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
                        await self.meshcore.sync_contacts()
                        info_print("✅ [MESHCORE-CLI] Contacts synchronisés")
                        
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
        try:
            debug_print(f"🔔 [MESHCORE-CLI] Event reçu: {event}")
            
            # Extraire les informations de l'événement
            # L'API meshcore fournit un objet event avec payload
            payload = event.payload if hasattr(event, 'payload') else event
            
            debug_print(f"📦 [MESHCORE-CLI] Payload: {payload}")
            
            sender_id = payload.get('contact_id') or payload.get('sender_id')
            text = payload.get('text', '')
            
            info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            # Créer un pseudo-packet compatible avec le code existant
            packet = {
                'from': sender_id,
                'to': self.localNode.nodeNum,
                'decoded': {
                    'portnum': 'TEXT_MESSAGE_APP',
                    'payload': text.encode('utf-8')
                }
            }
            
            # Appeler le callback
            if self.message_callback:
                self.message_callback(packet, None)
            else:
                debug_print("⚠️ [MESHCORE-CLI] Pas de callback défini")
                
        except Exception as e:
            error_print(f"❌ [MESHCORE-CLI] Erreur traitement message: {e}")
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
            
            # Envoyer via meshcore-cli avec l'API async
            result = self._loop.run_until_complete(
                self.meshcore.send_text_message(
                    text=text,
                    contact_id=destinationId
                )
            )
            
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
