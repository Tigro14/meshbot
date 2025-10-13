#!/usr/bin/env python3
"""
Bridge pour capturer le trafic public depuis tigrog2
Connexion TCP persistante avec reconnexion automatique
"""

import time
import threading
from pubsub import pub
import meshtastic.tcp_interface
from config import *
from utils import *

class TigroG2TrafficBridge:
    def __init__(self, traffic_monitor, node_manager):
        self.traffic_monitor = traffic_monitor
        self.node_manager = node_manager
        self.running = False
        self.bridge_thread = None
        self.remote_interface = None
        self.connection_failures = 0
        self.max_failures = 5
        self.reconnect_delay = 30
        self.last_messages = {}
        
    def start(self):
        """Démarrer le bridge en arrière-plan"""
        if self.running:
            return
        
        self.running = True
        self.bridge_thread = threading.Thread(target=self._bridge_loop, daemon=True)
        self.bridge_thread.start()
        info_print(f"🌉 TigroG2 Traffic Bridge démarré")
    
    def stop(self):
        """Arrêter le bridge"""
        self.running = False
        
        # Se désabonner de pubsub
        try:
            pub.unsubscribe(self._on_tigrog2_message, "meshtastic.receive")
        except:
            pass
        
        if self.remote_interface:
            try:
                self.remote_interface.close()
            except:
                pass
        
        info_print("🛑 TigroG2 Traffic Bridge arrêté")
    
    def _bridge_loop(self):
        """Boucle principale de connexion/reconnexion"""
        info_print("⏳ Bridge : délai initial 15s...")
        time.sleep(15)
       
        while self.running:
            try:
                data = self.tcp_interface.read()
                if data:
                    self.process(data)
                # CRITIQUE : Ajouter un sleep
                time.sleep(0.5)  # 500ms entre lectures
            except Exception as e:
                error_print(f"Erreur bridge loop: {e}")
                self.remote_interface = None
                time.sleep(10)
    
    def _connect_to_tigrog2(self):
        """Se connecter à tigrog2 et souscrire via pubsub"""
        try:
            info_print(f"🔌 Connexion à tigrog2 ({REMOTE_NODE_HOST})...")
            
            if self.remote_interface:
                try:
                    pub.unsubscribe(self._on_tigrog2_message, "meshtastic.receive")
                    self.remote_interface.close()
                    time.sleep(2)
                except:
                    pass
                self.remote_interface = None
            
            self.remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )
            
            time.sleep(3)
            
            # Souscrire via pubsub
            pub.subscribe(self._on_tigrog2_message, "meshtastic.receive")
            
            self.connection_failures = 0
            info_print(f"✅ Bridge tigrog2 connecté et à l'écoute")
            
        except Exception as e:
            self.connection_failures += 1
            error_print(f"❌ Erreur connexion tigrog2 ({self.connection_failures}/{self.max_failures}): {e}")
            self.remote_interface = None
            
            if self.connection_failures >= self.max_failures:
                error_print(f"⚠️ Bridge tigrog2 désactivé après {self.max_failures} échecs")
                time.sleep(self.reconnect_delay * 3)
                self.connection_failures = 0
            else:
                time.sleep(self.reconnect_delay)
    
    def _on_tigrog2_message(self, packet, interface):
        """Gestionnaire des messages reçus depuis tigrog2"""
        try:
            # CRITIQUE : Filtrer seulement les messages de NOTRE interface
            if interface != self.remote_interface:
                return
            
            if 'decoded' not in packet:
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
            
            if portnum != 'TEXT_MESSAGE_APP':
                return
            
            from_id = packet.get('from', 0)
            to_id = packet.get('to', 0)
            
            is_broadcast = to_id in [0xFFFFFFFF, 0]
            if not is_broadcast:
                return
            
            message = self._extract_message_text(decoded)
            if not message:
                return
            
            if self._is_duplicate(from_id, message):
                debug_print(f"🔄 Message dupliqué ignoré: {self.node_manager.get_node_name(from_id)}")
                return
            
            sender_name = self.node_manager.get_node_name(from_id)
            debug_print(f"📡 Message tigrog2: {sender_name} -> '{message[:50]}...'")
            
            self.traffic_monitor.add_public_message(
                packet, 
                message, 
                source='tigrog2'
            )
            
        except Exception as e:
            debug_print(f"Erreur traitement message tigrog2: {e}")
    
    def _extract_message_text(self, decoded):
        """Extraire le texte du message"""
        message = ""
        
        if 'text' in decoded:
            message = decoded['text']
        elif 'payload' in decoded:
            payload = decoded['payload']
            if isinstance(payload, bytes):
                try:
                    message = payload.decode('utf-8')
                except UnicodeDecodeError:
                    message = payload.decode('utf-8', errors='replace')
            else:
                message = str(payload)
        
        return message
    
    def _is_duplicate(self, from_id, message):
        """Vérifier si le message est un doublon récent"""
        current_time = time.time()
        
        if from_id in self.last_messages:
            last_msg, last_time = self.last_messages[from_id]
            
            if last_msg == message and (current_time - last_time) < 10:
                return True
        
        self.last_messages[from_id] = (message, current_time)
        return False
    
    def _cleanup_dedup_cache(self):
        """Nettoyer le cache de déduplication"""
        try:
            current_time = time.time()
            to_remove = []
            
            for node_id, (msg, timestamp) in self.last_messages.items():
                if current_time - timestamp > 60:
                    to_remove.append(node_id)
            
            for node_id in to_remove:
                del self.last_messages[node_id]
            
            if to_remove and DEBUG_MODE:
                debug_print(f"🧹 Cache dédup nettoyé: {len(to_remove)} entrées")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage cache dédup: {e}")
