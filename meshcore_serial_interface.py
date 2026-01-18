#!/usr/bin/env python3
"""
Interface série MeshCore pour le bot en mode companion
Permet de recevoir des DM depuis MeshCore et d'envoyer des réponses
"""

import serial
import threading
import time
from utils import info_print, debug_print, error_print
import traceback


class MeshCoreSerialInterface:
    """
    Interface série simple pour MeshCore
    
    En mode companion, le bot:
    - Reçoit uniquement des DM via serial MeshCore
    - Envoie des réponses en DM
    - Ne gère pas les broadcasts ni les fonctionnalités Meshtastic
    
    Note: Cette implémentation est basique et devra être adaptée
    selon le protocole exact de MeshCore utilisé.
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
        
        # Simulation d'un localNode pour compatibilité avec le code existant
        self.localNode = type('obj', (object,), {
            'nodeNum': 0xFFFFFFFF,  # ID fictif pour mode companion
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
                            debug_print(f"📨 [MESHCORE-TEXT] Reçu: {line[:80]}{'...' if len(line) > 80 else ''}")
                            self._process_meshcore_line(line)
                    except UnicodeDecodeError:
                        # Données binaires (probablement protobuf)
                        debug_print(f"📨 [MESHCORE-BINARY] Reçu: {len(raw_data)} octets (protobuf)")
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
        try:
            # Parser le message (format simple pour l'instant)
            if line.startswith("DM:"):
                parts = line[3:].split(":", 1)
                if len(parts) >= 2:
                    sender_id = int(parts[0], 16)  # ID en hexa
                    message = parts[1]
                    
                    info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {message[:50]}{'...' if len(message) > 50 else ''}")
                    
                    # Créer un pseudo-packet compatible avec le code existant
                    packet = {
                        'from': sender_id,
                        'to': self.localNode.nodeNum,
                        'decoded': {
                            'portnum': 'TEXT_MESSAGE_APP',
                            'payload': message.encode('utf-8')
                        }
                    }
                    
                    # Appeler le callback si défini
                    if self.message_callback:
                        self.message_callback(packet, None)
            else:
                debug_print(f"⚠️ [MESHCORE] Ligne non reconnue: {line[:80]}")
        
        except Exception as e:
            error_print(f"❌ [MESHCORE] Erreur parsing message texte: {e}")
            error_print(traceback.format_exc())
    
    def _process_meshcore_binary(self, raw_data):
        """
        Traite des données binaires (protobuf) reçues de MeshCore
        
        Args:
            raw_data: Données binaires brutes
        """
        try:
            # Pour l'instant, logger les données binaires sans les afficher
            debug_print(f"🔍 [MESHCORE-PROTOBUF] Tentative de décodage protobuf ({len(raw_data)} octets)")
            
            # TODO: Implémenter le décodage protobuf MeshCore
            # Pour l'instant, on ignore les données binaires
            # Le protocole protobuf de MeshCore devra être documenté et implémenté ici
            
            # Exemple de structure attendue (à adapter):
            # - Magic bytes
            # - Message type
            # - Protobuf payload
            
            debug_print(f"⚠️ [MESHCORE-PROTOBUF] Décodage protobuf non implémenté - données ignorées")
            
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
        self.message_callback = callback
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
        self.localNode = type('obj', (object,), {
            'nodeNum': 0xFFFFFFFF,
        })()
    
    def sendText(self, message, destinationId=None):
        """Simule l'envoi d'un message (aucune action réelle)"""
        debug_print(f"📤 [STANDALONE] Message ignoré: {message[:50]}...")
        return False
    
    def close(self):
        """Aucune action nécessaire"""
        pass
