#!/usr/bin/env python3
"""
Interface série MeshCore pour le bot en mode companion
Implémentation du protocole binaire MeshCore selon:
https://github.com/meshcore-dev/MeshCore/wiki/Companion-Radio-Protocol

⚠️ IMPORTANT: Cette interface est LIMITÉE
===============================================
Cette implémentation est destinée à:
  ✅ Debugging de paquets MeshCore
  ✅ Monitoring RF (voir les paquets qui passent)
  ✅ Développement et tests du protocole

Elle N'EST PAS destinée à:
  ❌ Interaction DM complète avec le bot
  ❌ Gestion complète des contacts
  ❌ Fonctionnalités avancées de l'API MeshCore

Pour une interaction DM complète, utilisez:
  → MeshCoreCLIWrapper (avec library meshcore-cli)
  
Cette interface de base ne devrait être utilisée que si:
  - Vous n'avez pas accès à meshcore-cli library
  - Vous voulez uniquement déboguer les paquets
  - Vous développez/testez le protocole MeshCore
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
    
    def __init__(self, port, baudrate=115200, enable_read_loop=True):
        """
        Initialise la connexion série MeshCore
        
        Args:
            port: Port série (ex: /dev/ttyUSB0)
            baudrate: Vitesse de communication (défaut: 115200)
            enable_read_loop: Si False, ne démarre pas le read loop (utile en mode hybride)
        """
        self.port = port
        self.baudrate = baudrate
        self.enable_read_loop = enable_read_loop
        self.serial = None
        self.running = False
        self.read_thread = None
        self.poll_thread = None  # Thread de polling actif (NEW)
        self.message_callback = None
        
        # Buffer pour assembly de trames
        self.read_buffer = bytearray()
        
        # Statistics for diagnostics
        self.binary_packets_rejected = 0  # Count of binary packets that couldn't be processed
        
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
        
        # IMPORTANT WARNING: This basic implementation has limitations
        error_print("⚠️  " * 20)
        error_print("⚠️  [MESHCORE] UTILISATION DE L'IMPLÉMENTATION BASIQUE")
        error_print("⚠️  " * 20)
        error_print("   LIMITATIONS:")
        error_print("   - Protocole binaire NON supporté (seul format texte)")
        error_print("   - DM encryption NON supportée")
        error_print("   - Auto message fetching LIMITÉ")
        error_print("")
        error_print("   IMPACT:")
        error_print("   - Si MeshCore envoie du binaire: AUCUN paquet ne sera loggué")
        error_print("   - Pas de logs [DEBUG][MC]")
        error_print("   - Bot NE RÉPONDRA PAS aux DM")
        error_print("")
        error_print("   SOLUTION RECOMMANDÉE:")
        error_print("   $ pip install meshcore meshcoredecoder")
        error_print("   $ sudo systemctl restart meshtastic-bot")
        error_print("")
        error_print("   Pour support complet, utilisez meshcore-cli library")
        error_print("⚠️  " * 20)
        
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
        
        # Check if read loop is disabled (hybrid mode with CLI wrapper)
        if not self.enable_read_loop:
            info_print("=" * 80)
            info_print("🔧 [MESHCORE-SERIAL] Read loop disabled (hybrid mode)")
            info_print("=" * 80)
            info_print(f"   Port série: {self.port}")
            info_print(f"   Usage: SEND ONLY (broadcasts via binary protocol)")
            info_print(f"   Receiving: Handled by MeshCoreCLIWrapper")
            info_print("=" * 80)
            return True
        
        self.running = True
        
        # Log initial diagnostics
        info_print("=" * 80)
        info_print("🔧 [MESHCORE] DÉMARRAGE DIAGNOSTICS")
        info_print("=" * 80)
        info_print(f"   Port série: {self.port}")
        info_print(f"   Baudrate: {self.baudrate}")
        info_print(f"   Port ouvert: {self.serial.is_open}")
        info_print(f"   Message callback: {self.message_callback is not None}")
        info_print("=" * 80)
        
        # Thread de lecture (passif + écoute push notifications)
        self.read_thread = threading.Thread(
            target=self._read_loop,
            name="MeshCore-Reader",
            daemon=True
        )
        self.read_thread.start()
        info_print("✅ [MESHCORE] Thread de lecture démarré")
        
        # Thread de polling actif (demande périodique de messages)
        self.poll_thread = threading.Thread(
            target=self._poll_loop,
            name="MeshCore-Poller",
            daemon=True
        )
        self.poll_thread.start()
        info_print("✅ [MESHCORE] Thread de polling démarré")
        
        # Wait a moment and verify threads are running
        time.sleep(0.5)
        read_ok = self.read_thread.is_alive()
        poll_ok = self.poll_thread.is_alive()
        
        if read_ok:
            info_print("✅ [MESHCORE] Read thread confirmed running")
        else:
            error_print("❌ [MESHCORE] Read thread NOT running!")
        
        if poll_ok:
            info_print("✅ [MESHCORE] Poll thread confirmed running")
        else:
            error_print("❌ [MESHCORE] Poll thread NOT running!")
        
        # === CONNECTION VERIFICATION BANNER ===
        info_print("=" * 80)
        info_print("✅ [MESHCORE] CONNECTION VERIFICATION")
        info_print("=" * 80)
        info_print(f"   Port série: {self.port}")
        info_print(f"   Baudrate: {self.baudrate}")
        info_print(f"   Port ouvert: {self.serial.is_open}")
        info_print(f"   Read thread: {'✅ RUNNING' if read_ok else '❌ STOPPED'}")
        info_print(f"   Poll thread: {'✅ RUNNING' if poll_ok else '❌ STOPPED'}")
        info_print(f"   Callback configuré: {'✅ YES' if self.message_callback else '❌ NO'}")
        info_print("")
        info_print("   📊 MONITORING ACTIF:")
        info_print("   → Heartbeat: Toutes les 60 secondes")
        info_print("   → Polling: Toutes les 5 secondes")
        info_print("   → Logs: [MESHCORE-DATA] quand paquets arrivent")
        info_print("")
        if read_ok and poll_ok and self.message_callback:
            info_print("   ✅ MeshCore companion prêt à recevoir des messages")
        else:
            error_print("   ⚠️  PROBLÈME: Vérifier les threads et le callback ci-dessus")
        info_print("=" * 80)
        
        return True
    
    def _poll_loop(self):
        """
        Boucle de polling actif pour demander les messages en attente
        Envoie périodiquement CMD_SYNC_NEXT_MESSAGE pour récupérer les messages
        """
        info_print("🔄 [MESHCORE-POLL] Démarrage du polling actif...")
        poll_interval = 5  # Demander les messages toutes les 5 secondes
        
        while self.running and self.serial and self.serial.is_open:
            try:
                # Envoyer CMD_SYNC_NEXT_MESSAGE pour demander le prochain message en attente
                # Format protocole MeshCore:
                # - 0x3C ('<') : start marker (app -> radio)
                # - 2 bytes : length (little-endian)
                # - N bytes : payload (command code + data)
                
                # Payload: juste le command code
                payload = bytes([CMD_SYNC_NEXT_MESSAGE])
                length = len(payload)
                
                # Construire le paquet
                packet = bytes([0x3C]) + struct.pack('<H', length) + payload
                
                self.serial.write(packet)
                debug_print(f"📤 [MESHCORE-POLL] Demande de messages en attente (protocole binaire)")
                
                # Attendre avant la prochaine demande
                time.sleep(poll_interval)
                
            except serial.SerialException as e:
                error_print(f"❌ [MESHCORE-POLL] Erreur série: {e}")
                break
            except Exception as e:
                error_print(f"❌ [MESHCORE-POLL] Erreur polling: {e}")
                error_print(traceback.format_exc())
                # Continuer malgré l'erreur
                time.sleep(poll_interval)
        
        info_print("🛑 [MESHCORE-POLL] Thread de polling arrêté")
    
    def _read_loop(self):
        """Boucle de lecture des messages série (exécutée dans un thread)"""
        info_print("📡 [MESHCORE] Début lecture messages MeshCore...")
        
        # Counter for diagnostics
        loop_iterations = 0
        data_received_count = 0
        last_activity_log = time.time()
        
        while self.running and self.serial and self.serial.is_open:
            try:
                loop_iterations += 1
                
                # Log activity periodically (every 60 seconds)
                # INFO level (not debug) so users can see MeshCore is alive
                if time.time() - last_activity_log > 60:
                    status_icon = "✅" if data_received_count > 0 else "⏸️"
                    info_print(f"{status_icon} [MESHCORE-HEARTBEAT] Connexion active | Iterations: {loop_iterations} | Paquets reçus: {data_received_count}")
                    if data_received_count == 0:
                        info_print("   ⚠️  Aucun paquet reçu depuis 60s - Vérifier radio MeshCore")
                    last_activity_log = time.time()
                
                # Lecture des données disponibles
                waiting = self.serial.in_waiting
                if waiting > 0:
                    data_received_count += 1
                    info_print(f"📥 [MESHCORE-DATA] {waiting} bytes waiting (packet #{data_received_count})")
                    
                    # Lire les données brutes
                    raw_data = self.serial.read(waiting)
                    info_print(f"📦 [MESHCORE-RAW] Read {len(raw_data)} bytes: {raw_data[:20].hex() if len(raw_data) <= 20 else raw_data[:20].hex() + '...'}")
                    
                    # Vérifier si c'est du texte ou du binaire
                    try:
                        # Tenter de décoder comme texte UTF-8
                        line = raw_data.decode('utf-8', errors='strict').strip()
                        if line:
                            info_print(f"📨 [MESHCORE-TEXT] Reçu: {line[:80]}{'...' if len(line) > 80 else ''}")
                            self._process_meshcore_line(line)
                    except UnicodeDecodeError:
                        # Données binaires (protocole binaire MeshCore natif)
                        info_print(f"📨 [MESHCORE-BINARY] Reçu: {len(raw_data)} octets (protocole binaire MeshCore)")
                        self._process_meshcore_binary(raw_data)
                
                time.sleep(0.1)  # Éviter de saturer le CPU
                
            except serial.SerialException as e:
                error_print(f"❌ [MESHCORE] Erreur lecture série: {e}")
                break
            except Exception as e:
                error_print(f"❌ [MESHCORE] Erreur traitement message: {e}")
                error_print(traceback.format_exc())
        
        info_print(f"🛑 [MESHCORE] Thread de lecture arrêté (après {loop_iterations} iterations, {data_received_count} packets)")
    
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
                        # MC DEBUG: Ultra-visible callback invocation
                        info_print_mc("=" * 80)
                        info_print_mc("🔗 MC DEBUG: CALLING message_callback FROM meshcore_serial_interface")
                        info_print_mc("=" * 80)
                        info_print_mc(f"📍 Entry point: meshcore_serial_interface.py::_process_meshcore_line()")
                        info_print_mc(f"📦 From: 0x{sender_id:08x}")
                        info_print_mc(f"📨 Message: {message[:50]}{'...' if len(message) > 50 else ''}")
                        info_print_mc(f"➡️  Calling callback: {self.message_callback}")
                        info_print_mc("=" * 80)
                        self.message_callback(packet, None)
                        info_print(f"✅ [MESHCORE-TEXT] Callback completed successfully")
                        info_print_mc("✅ MC DEBUG: Callback returned successfully")
                    else:
                        error_print(f"⚠️ [MESHCORE-TEXT] No message_callback set!")
                        info_print_mc("❌ MC DEBUG: No message_callback configured!")
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
            
            # Check for push notification codes
            if len(raw_data) > 0:
                first_byte = raw_data[0]
                
                # PUSH_CODE_MSG_WAITING = 0x83
                if first_byte == 0x83:
                    info_print(f"📬 [MESHCORE-PUSH] Message en attente détecté (PUSH_CODE_MSG_WAITING)")
                    # Demander immédiatement le message via CMD_SYNC_NEXT_MESSAGE
                    try:
                        # Utiliser le protocole binaire
                        payload = bytes([CMD_SYNC_NEXT_MESSAGE])
                        length = len(payload)
                        packet = bytes([0x3C]) + struct.pack('<H', length) + payload
                        self.serial.write(packet)
                        debug_print(f"📤 [MESHCORE-PUSH] Demande de récupération du message (protocole binaire)")
                    except Exception as sync_err:
                        error_print(f"❌ [MESHCORE-PUSH] Erreur envoi SYNC_NEXT: {sync_err}")
                    return
                
                # PUSH_CODE_ADVERT = 0x80
                elif first_byte == 0x80:
                    debug_print(f"📡 [MESHCORE-PUSH] Advertisement reçu (PUSH_CODE_ADVERT)")
                    return
                
                # PUSH_CODE_PATH_UPDATED = 0x81
                elif first_byte == 0x81:
                    debug_print(f"🗺️ [MESHCORE-PUSH] Route mise à jour (PUSH_CODE_PATH_UPDATED)")
                    return
                
                # PUSH_CODE_SEND_CONFIRMED = 0x82
                elif first_byte == 0x82:
                    debug_print(f"✅ [MESHCORE-PUSH] Envoi confirmé (PUSH_CODE_SEND_CONFIRMED)")
                    return
            
            # TODO: Implémenter le décodage complet du protocole binaire MeshCore
            # Pour l'instant, on ignore les données binaires non reconnues
            # Le protocole binaire de MeshCore devra être documenté et implémenté ici
            
            # Structure attendue (à documenter/adapter selon spec MeshCore):
            # - Magic bytes (sync)
            # - Command code (CMD_SEND_TXT_MSG, CMD_RCV_TXT_MSG, etc.)
            # - Length field
            # - Payload
            # - CRC checksum
            
            # PROMINENT WARNING: This is why no packets are logged!
            self.binary_packets_rejected += 1  # Track for diagnostics
            
            error_print("=" * 80)
            error_print("❌ [MESHCORE-BINARY] PROTOCOLE BINAIRE NON SUPPORTÉ!")
            error_print("=" * 80)
            error_print("   PROBLÈME: Données binaires MeshCore reçues mais non décodées")
            error_print(f"   TAILLE: {len(raw_data)} octets ignorés")
            error_print(f"   TOTAL REJETÉ: {self.binary_packets_rejected} packet(s)")
            error_print("   IMPACT: Pas de logs [DEBUG][MC], pas de réponse aux DM")
            error_print("")
            error_print("   SOLUTION: Installer meshcore-cli library")
            error_print("   $ pip install meshcore meshcoredecoder")
            error_print("   $ sudo systemctl restart meshtastic-bot")
            error_print("")
            error_print("   Cette implémentation basique ne supporte QUE le format texte:")
            error_print("   DM:<sender_id>:<message>")
            error_print("")
            error_print("   Pour un support complet, utilisez meshcore-cli library")
            error_print("=" * 80)
            
            # Also log at debug level for those who filter errors
            debug_print(f"⚠️ [MESHCORE-BINARY] Décodage protocole MeshCore non implémenté - données ignorées")
            
        except Exception as e:
            error_print(f"❌ [MESHCORE] Erreur traitement données binaires: {e}")
            error_print(traceback.format_exc())
    
    def sendText(self, message, destinationId=None, channelIndex=0):
        """
        Envoie un message texte via MeshCore
        
        Args:
            message: Texte à envoyer
            destinationId: ID du destinataire (None or 0xFFFFFFFF = broadcast sur canal)
            channelIndex: Index du canal (0 = public, ignoré pour DM directs)
        """
        if not self.serial or not self.serial.is_open:
            error_print("❌ [MESHCORE] Port série non ouvert, impossible d'envoyer")
            return False
        
        # Detect if this is a broadcast/channel message
        is_broadcast = (destinationId is None or destinationId == 0xFFFFFFFF)
        
        if is_broadcast:
            # Send as channel message (broadcast on specified channel)
            try:
                info_print(f"📢 [MESHCORE] Envoi broadcast sur canal {channelIndex}: {message[:50]}{'...' if len(message) > 50 else ''}")
                
                # Build binary packet for CMD_SEND_CHANNEL_TXT_MSG
                # Protocol: 0x3C ('<') + length (2 bytes LE) + command (1 byte) + channel (1 byte) + message (UTF-8)
                message_bytes = message.encode('utf-8')
                payload = bytes([CMD_SEND_CHANNEL_TXT_MSG, channelIndex]) + message_bytes
                length = len(payload)
                
                # Construct packet with framing
                packet = bytes([0x3C]) + struct.pack('<H', length) + payload
                
                self.serial.write(packet)
                self.serial.flush()  # Force immediate transmission to hardware
                info_print(f"✅ [MESHCORE-CHANNEL] Broadcast envoyé sur canal {channelIndex} ({len(message_bytes)} octets)")
                return True
                
            except Exception as e:
                error_print(f"❌ [MESHCORE] Erreur envoi broadcast: {e}")
                error_print(traceback.format_exc())
                return False
        else:
            # Send as direct message (DM) to specific node
            try:
                # Format simple pour envoi DM via MeshCore
                # TODO: Implémenter protocole binaire complet avec CMD_SEND_TXT_MSG
                cmd = f"SEND_DM:{destinationId:08x}:{message}\n"
                self.serial.write(cmd.encode('utf-8'))
                self.serial.flush()  # Force immediate transmission to hardware
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
    
    def get_connection_status(self):
        """
        Retourne le statut de connexion MeshCore pour diagnostics
        
        Returns:
            dict: Statut détaillé de la connexion
        """
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'connected': self.serial and self.serial.is_open if self.serial else False,
            'running': self.running,
            'read_thread_alive': self.read_thread.is_alive() if self.read_thread else False,
            'poll_thread_alive': self.poll_thread.is_alive() if self.poll_thread else False,
            'callback_configured': self.message_callback is not None,
            'interface_type': 'MeshCoreSerialInterface (basic)',
        }
    
    def close(self):
        """Ferme la connexion série MeshCore"""
        info_print("🛑 [MESHCORE] Fermeture interface...")
        self.running = False
        
        # Attendre l'arrêt du thread de lecture
        if self.read_thread and self.read_thread.is_alive():
            info_print("⏳ [MESHCORE] Attente du thread de lecture...")
            self.read_thread.join(timeout=2.0)
        
        # Attendre l'arrêt du thread de polling
        if self.poll_thread and self.poll_thread.is_alive():
            info_print("⏳ [MESHCORE] Attente du thread de polling...")
            self.poll_thread.join(timeout=2.0)
        
        # Fermer le port série
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
