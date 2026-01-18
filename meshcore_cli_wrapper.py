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
    from meshcore import MeshCore
    MESHCORE_CLI_AVAILABLE = True
    info_print("✅ [MESHCORE] Library meshcore-cli disponible")
except ImportError:
    MESHCORE_CLI_AVAILABLE = False
    info_print("⚠️ [MESHCORE] Library meshcore-cli non disponible (pip install meshcore)")
    # Fallback to basic implementation
    MeshCore = None


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
    
    def start_reading(self):
        """Démarre la lecture des messages en arrière-plan"""
        if not self.meshcore:
            error_print("❌ [MESHCORE-CLI] Non connecté, impossible de démarrer la lecture")
            return False
        
        self.running = True
        self.message_thread = threading.Thread(
            target=self._message_loop,
            name="MeshCore-CLI-Reader",
            daemon=True
        )
        self.message_thread.start()
        info_print("✅ [MESHCORE-CLI] Thread de lecture démarré")
        return True
    
    def _message_loop(self):
        """Boucle de lecture des messages"""
        info_print("📡 [MESHCORE-CLI] Début lecture messages...")
        
        while self.running:
            try:
                # Synchroniser les messages en attente avec l'API async
                messages = self._loop.run_until_complete(
                    self.meshcore.sync_messages()
                )
                
                if messages:
                    for msg in messages:
                        self._process_message(msg)
                
                # Pause courte pour ne pas surcharger le CPU
                time.sleep(0.5)
                
            except Exception as e:
                error_print(f"❌ [MESHCORE-CLI] Erreur lecture: {e}")
                error_print(traceback.format_exc())
                time.sleep(1)
        
        info_print("📡 [MESHCORE-CLI] Arrêt lecture messages")
    
    def _process_message(self, msg):
        """
        Traite un message reçu de meshcore-cli
        
        Args:
            msg: Message dict from meshcore-cli
        """
        try:
            # Extraire les informations du message
            sender_id = msg.get('sender_id')
            text = msg.get('text', '')
            msg_type = msg.get('type', 'contact')  # 'contact' (DM) ou 'channel'
            
            if msg_type == 'contact':  # DM uniquement pour le bot
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
                debug_print(f"📢 [MESHCORE-CHANNEL] Message canal ignoré (mode companion)")
                
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
