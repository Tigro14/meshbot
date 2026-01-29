#!/usr/bin/env python3
"""
Interface série MeshCore pour le bot en mode companion
Implémentation du protocole binaire MeshCore selon:
https://github.com/meshcore-dev/MeshCore/wiki/Companion-Radio-Protocol
"""

import serial
import threading
import time
import struct
from utils import info_print, debug_print, error_print
import traceback


# Command codes (app -> radio)
CMD_APP_START = 1
CMD_SEND_TXT_MSG = 2
CMD_SEND_CHANNEL_TXT_MSG = 3
CMD_GET_CONTACTS = 4
CMD_GET_DEVICE_TIME = 5
CMD_SET_DEVICE_TIME = 6
CMD_SEND_SELF_ADVERT = 7
CMD_SET_ADVERT_NAME = 8
CMD_ADD_UPDATE_CONTACT = 9
CMD_SYNC_NEXT_MESSAGE = 10
CMD_DEVICE_QUERY = 22

# Response codes (radio -> app)
RESP_CODE_OK = 0
RESP_CODE_ERR = 1
RESP_CODE_CONTACTS_START = 2
RESP_CODE_CONTACT = 3
RESP_CODE_END_OF_CONTACTS = 4
RESP_CODE_SELF_INFO = 5
RESP_CODE_SENT = 6
RESP_CODE_CONTACT_MSG_RECV = 7
RESP_CODE_CHANNEL_MSG_RECV = 8
RESP_CODE_CURR_TIME = 9
RESP_CODE_NO_MORE_MESSAGES = 10
RESP_CODE_DEVICE_INFO = 13

# Push notification codes
PUSH_CODE_ADVERT = 0x80
PUSH_CODE_PATH_UPDATED = 0x81
PUSH_CODE_SEND_CONFIRMED = 0x82
PUSH_CODE_MSG_WAITING = 0x83


class MeshCoreSerialInterface:
    """
    Interface série MeshCore avec support du protocole binaire complet
    
    Protocole de framing:
    - Outbound (radio -> app): 0x3E ('>') + 2 bytes length (little-endian) + payload
    - Inbound (app -> radio): 0x3C ('<') + 2 bytes length (little-endian) + payload
    """
    
    def __init__(self, port, baudrate=115200):
        """
        Initialise la connexion série MeshCore
        
        Args:
            port: Port série (ex: /dev/ttyUSB0)
            baudrate: Vitesse de communication (défaut: 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = False
        self.read_thread = None
        self.message_callback = None
        
        # Buffer pour assembly de trames
        self.read_buffer = bytearray()
        
        # Informations du device MeshCore
        self.device_info = None
        self.self_info = None
        self.contacts = {}
        
        # Simulation d'un localNode pour compatibilité avec le code existant
        # Note: 0xFFFFFFFE = unknown local node (NOT broadcast 0xFFFFFFFF)
        # This ensures DMs are not treated as broadcasts when real node ID unavailable
        self.localNode = type('obj', (object,), {
            'nodeNum': 0xFFFFFFFE,  # Non-broadcast ID for companion mode
        })()
        
        info_print(f"🔧 [MESHCORE] Initialisation interface série: {port}")
        
    def connect(self):
        """Établit la connexion série avec MeshCore"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            info_print(f"✅ [MESHCORE] Connexion série établie: {self.port}")
            return True
        except serial.SerialException as e:
            error_print(f"❌ [MESHCORE] Erreur connexion série: {e}")
            return False
        except Exception as e:
            error_print(f"❌ [MESHCORE] Erreur inattendue connexion: {e}")
            error_print(traceback.format_exc())
            return False
    
    def start_reading(self):
        """Démarre la lecture en arrière-plan des messages MeshCore"""
        if not self.serial or not self.serial.is_open:
            error_print("❌ [MESHCORE] Port série non ouvert, impossible de démarrer la lecture")
            return False
        
        self.running = True
        self.read_thread = threading.Thread(
            target=self._read_loop,
            name="MeshCore-Reader",
            daemon=True
        )
        self.read_thread.start()
        info_print("✅ [MESHCORE] Thread de lecture démarré")
        return True
    
    def _read_loop(self):
        """Boucle de lecture des messages série (exécutée dans un thread)"""
        info_print("📡 [MESHCORE] Début lecture messages MeshCore...")
        
        while self.running and self.serial and self.serial.is_open:
            try:
                # Lecture des données disponibles
                if self.serial.in_waiting > 0:
                    # Lire les données brutes
                    raw_data = self.serial.read(self.serial.in_waiting)
                    
                    # Vérifier si c'est du texte ou du binaire
                    try:
                        # Tenter de décoder comme texte UTF-8
                        line = raw_data.decode('utf-8', errors='strict').strip()
                        if line:
                            # CRITICAL: Use info_print so messages are ALWAYS visible (not just DEBUG_MODE)
                            info_print(f"📨 [MESHCORE-TEXT] Reçu: {line[:80]}{'...' if len(line) > 80 else ''}")
                            self._process_meshcore_line(line)
                    except UnicodeDecodeError:
                        # Données binaires (protocole binaire MeshCore natif)
                        # CRITICAL: Use info_print so messages are ALWAYS visible
                        info_print(f"📨 [MESHCORE-BINARY] Reçu: {len(raw_data)} octets (protocole binaire MeshCore)")
                        self._process_meshcore_binary(raw_data)
                
                time.sleep(0.1)  # Éviter de saturer le CPU
                
            except serial.SerialException as e:
                error_print(f"❌ [MESHCORE] Erreur lecture série: {e}")
                break
            except Exception as e:
                error_print(f"❌ [MESHCORE] Erreur traitement message: {e}")
                error_print(traceback.format_exc())
        
        info_print("🛑 [MESHCORE] Thread de lecture arrêté")
    
    def _process_meshcore_line(self, line):
        """
        Traite une ligne texte reçue de MeshCore
        
        Format attendu (à adapter selon protocole MeshCore):
        DM:<sender_id>:<message_text>
        
        Args:
            line: Ligne reçue du serial MeshCore
        """
        info_print(f"🔍 [MESHCORE-SERIAL] _process_meshcore_line CALLED with: {line[:80]}")
        try:
            # Parser le message (format simple pour l'instant)
            if line.startswith("DM:"):
                parts = line[3:].split(":", 1)
                if len(parts) >= 2:
                    sender_id = int(parts[0], 16)  # ID en hexa
                    message = parts[1]
                    
                    info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {message[:50]}{'...' if len(message) > 50 else ''}")
                    
                    # Créer un pseudo-packet compatible avec le code existant
                    # IMPORTANT: Ajouter TOUS les champs nécessaires pour le logging
                    import random
                    packet = {
                        'from': sender_id,
                        'to': self.localNode.nodeNum,
                        'id': random.randint(100000, 999999),  # ID unique pour déduplication
                        'rxTime': int(time.time()),  # Timestamp de réception
                        'rssi': 0,  # Pas de métrique radio pour MeshCore
                        'snr': 0.0,  # Pas de métrique radio pour MeshCore
                        'hopLimit': 0,  # Message direct (pas de relay)
                        'hopStart': 0,  # Message direct
                        'channel': 0,  # Canal par défaut
                        'decoded': {
                            'portnum': 'TEXT_MESSAGE_APP',
                            'payload': message.encode('utf-8')
                        }
                    }
                    
                    # Appeler le callback si défini
                    if self.message_callback:
                        info_print(f"📞 [MESHCORE-TEXT] Calling message_callback for message from 0x{sender_id:08x}")
                        self.message_callback(packet, None)
                        info_print(f"✅ [MESHCORE-TEXT] Callback completed successfully")
                    else:
                        error_print(f"⚠️ [MESHCORE-TEXT] No message_callback set!")
            else:
                debug_print(f"⚠️ [MESHCORE] Ligne non reconnue: {line[:80]}")
        
        except Exception as e:
            error_print(f"❌ [MESHCORE] Erreur parsing message texte: {e}")
            error_print(traceback.format_exc())
    
    def _process_meshcore_binary(self, raw_data):
        """
        Traite des données binaires reçues de MeshCore
        
        MeshCore utilise son propre protocole binaire (pas protobuf).
        Format attendu : framing avec magic bytes, command codes, longueur, CRC
        
        Args:
            raw_data: Données binaires brutes
        """
        try:
            # Pour l'instant, logger les données binaires sans les afficher
            debug_print(f"🔍 [MESHCORE-BINARY] Tentative de décodage protocole MeshCore ({len(raw_data)} octets)")
            
            # TODO: Implémenter le décodage du protocole binaire MeshCore
            # Pour l'instant, on ignore les données binaires
            # Le protocole binaire de MeshCore devra être documenté et implémenté ici
            
            # Structure attendue (à documenter/adapter selon spec MeshCore):
            # - Magic bytes (sync)
            # - Command code (CMD_SEND_TXT_MSG, CMD_RCV_TXT_MSG, etc.)
            # - Length field
            # - Payload
            # - CRC checksum
            
            debug_print(f"⚠️ [MESHCORE-BINARY] Décodage protocole MeshCore non implémenté - données ignorées")
            
        except Exception as e:
            error_print(f"❌ [MESHCORE] Erreur traitement données binaires: {e}")
            error_print(traceback.format_exc())
    
    def sendText(self, message, destinationId=None):
        """
        Envoie un message texte via MeshCore
        
        Args:
            message: Texte à envoyer
            destinationId: ID du destinataire (None = broadcast, mais désactivé en mode companion)
        """
        if not self.serial or not self.serial.is_open:
            error_print("❌ [MESHCORE] Port série non ouvert, impossible d'envoyer")
            return False
        
        # En mode companion, on envoie uniquement des DM (pas de broadcast)
        if destinationId is None:
            debug_print("⚠️ [MESHCORE] Broadcast désactivé en mode companion")
            return False
        
        try:
            # Format simple pour envoi DM via MeshCore
            # TODO: Adapter selon le protocole binaire MeshCore réel
            cmd = f"SEND_DM:{destinationId:08x}:{message}\n"
            self.serial.write(cmd.encode('utf-8'))
            debug_print(f"📤 [MESHCORE-DM] Envoyé à 0x{destinationId:08x}: {message[:50]}{'...' if len(message) > 50 else ''}")
            return True
        
        except Exception as e:
            error_print(f"❌ [MESHCORE] Erreur envoi message: {e}")
            return False
    
    def set_message_callback(self, callback):
        """Définit le callback pour les messages reçus"""
        info_print(f"📝 [MESHCORE-SERIAL] Setting message_callback to {callback}")
        self.message_callback = callback
        info_print(f"✅ [MESHCORE-SERIAL] message_callback set successfully")
        debug_print("✅ [MESHCORE] Callback message configuré")
    
    def close(self):
        """Ferme la connexion série MeshCore"""
        info_print("🛑 [MESHCORE] Fermeture interface...")
        self.running = False
        
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=2.0)
        
        if self.serial and self.serial.is_open:
            self.serial.close()
        
        info_print("✅ [MESHCORE] Interface fermée")
    
    def __enter__(self):
        """Support du context manager"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support du context manager"""
        self.close()


class MeshCoreStandaloneInterface:
    """
    Interface factice pour mode standalone (ni Meshtastic ni MeshCore)
    Permet au bot de démarrer sans connexion radio pour tests
    """
    
    def __init__(self):
        info_print("⚠️ Mode standalone: aucune connexion radio active")
        # Note: 0xFFFFFFFE = unknown local node (NOT broadcast 0xFFFFFFFF)
        self.localNode = type('obj', (object,), {
            'nodeNum': 0xFFFFFFFE,
        })()
    
    def sendText(self, message, destinationId=None):
        """Simule l'envoi d'un message (aucune action réelle)"""
        debug_print(f"📤 [STANDALONE] Message ignoré: {message[:50]}...")
        return False
    
    def close(self):
        """Aucune action nécessaire"""
        pass
