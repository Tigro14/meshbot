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
        
        info_print(f"🔧 Initialisation interface série MeshCore: {port}")
        
    def connect(self):
        """Établit la connexion série avec MeshCore"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            info_print(f"✅ Connexion série MeshCore établie: {self.port}")
            return True
        except serial.SerialException as e:
            error_print(f"❌ Erreur connexion série MeshCore: {e}")
            return False
        except Exception as e:
            error_print(f"❌ Erreur inattendue connexion MeshCore: {e}")
            error_print(traceback.format_exc())
            return False
    
    def start_reading(self):
        """Démarre la lecture en arrière-plan des messages MeshCore"""
        if not self.serial or not self.serial.is_open:
            error_print("❌ Port série non ouvert, impossible de démarrer la lecture")
            return False
        
        self.running = True
        self.read_thread = threading.Thread(
            target=self._read_loop,
            name="MeshCore-Reader",
            daemon=True
        )
        self.read_thread.start()
        info_print("✅ Thread de lecture MeshCore démarré")
        return True
    
    def _read_loop(self):
        """Boucle de lecture des messages série (exécutée dans un thread)"""
        info_print("📡 Début lecture messages MeshCore...")
        
        while self.running and self.serial and self.serial.is_open:
            try:
                # Lecture ligne par ligne (protocole texte simple)
                # TODO: Adapter selon le protocole binaire MeshCore réel
                if self.serial.in_waiting > 0:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        debug_print(f"📨 MeshCore reçu: {line}")
                        self._process_meshcore_line(line)
                
                time.sleep(0.1)  # Éviter de saturer le CPU
                
            except serial.SerialException as e:
                error_print(f"❌ Erreur lecture série MeshCore: {e}")
                break
            except Exception as e:
                error_print(f"❌ Erreur traitement message MeshCore: {e}")
                error_print(traceback.format_exc())
        
        info_print("🛑 Thread de lecture MeshCore arrêté")
    
    def _process_meshcore_line(self, line):
        """
        Traite une ligne reçue de MeshCore
        
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
        
        except Exception as e:
            error_print(f"❌ Erreur parsing message MeshCore: {e}")
            error_print(traceback.format_exc())
    
    def sendText(self, message, destinationId=None):
        """
        Envoie un message texte via MeshCore
        
        Args:
            message: Texte à envoyer
            destinationId: ID du destinataire (None = broadcast, mais désactivé en mode companion)
        """
        if not self.serial or not self.serial.is_open:
            error_print("❌ Port série non ouvert, impossible d'envoyer")
            return False
        
        # En mode companion, on envoie uniquement des DM (pas de broadcast)
        if destinationId is None:
            debug_print("⚠️ Broadcast désactivé en mode companion MeshCore")
            return False
        
        try:
            # Format simple pour envoi DM via MeshCore
            # TODO: Adapter selon le protocole binaire MeshCore réel
            cmd = f"SEND_DM:{destinationId:08x}:{message}\n"
            self.serial.write(cmd.encode('utf-8'))
            debug_print(f"📤 MeshCore envoyé: {cmd.strip()}")
            return True
        
        except Exception as e:
            error_print(f"❌ Erreur envoi message MeshCore: {e}")
            return False
    
    def set_message_callback(self, callback):
        """Définit le callback pour les messages reçus"""
        self.message_callback = callback
        debug_print("✅ Callback message MeshCore configuré")
    
    def close(self):
        """Ferme la connexion série MeshCore"""
        info_print("🛑 Fermeture interface MeshCore...")
        self.running = False
        
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=2.0)
        
        if self.serial and self.serial.is_open:
            self.serial.close()
        
        info_print("✅ Interface MeshCore fermée")
    
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
