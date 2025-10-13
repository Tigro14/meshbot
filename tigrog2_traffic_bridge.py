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
        self.reconnect_delay = 30  # secondes
        
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
        if self.remote_interface:
            try:
                self.remote_interface.close()
            except:
                pass
        info_print("🛑 TigroG2 Traffic Bridge arrêté")
    
    def _bridge_loop(self):
        """Boucle principale de connexion/reconnexion"""
        info_print("⏳ Bridge : délai initial 10s...")
        time.sleep(10)
        
        while self.running:
            try:
                if not self.remote_interface or self.connection_failures >= self.max_failures:
                    self._connect_to_tigrog2()
                
                # Attendre avant de vérifier à nouveau
                time.sleep(30)
                
            except Exception as e:
                error_print(f"Erreur bridge loop: {e}")
                time.sleep(10)
    
    def _connect_to_tigrog2(self):
        """Se connecter à tigrog2 et souscrire aux messages"""
        try:
            info_print(f"🔌 Connexion à tigrog2 ({REMOTE_NODE_HOST})...")
            
            # Fermer l'ancienne connexion si elle existe
            if self.remote_interface:
                try:
                    self.remote_interface.close()
                except:
                    pass
            
            # Nouvelle connexion
            self.remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )
            
            time.sleep(3)
            
            # Souscrire aux messages de tigrog2
            pub.subscribe(
                self._on_tigrog2_message, 
                "meshtastic.receive.tigrog2",  # Topic distinct
                listener=self.remote_interface
            )
            
            self.connection_failures = 0
            info_print(f"✅ Bridge tigrog2 connecté et à l'écoute")
            
        except Exception as e:
            self.connection_failures += 1
            error_print(f"❌ Erreur connexion tigrog2 ({self.connection_failures}/{self.max_failures}): {e}")
            
            if self.connection_failures >= self.max_failures:
                error_print(f"⚠️ Bridge tigrog2 désactivé après {self.max_failures} échecs")
                time.sleep(self.reconnect_delay * 3)  # Long délai avant réessai
                self.connection_failures = 0  # Reset pour réessayer
            else:
                time.sleep(self.reconnect_delay)
    
    def _on_tigrog2_message(self, packet, interface):
        """Gestionnaire des messages reçus depuis tigrog2"""
        try:
            # Filtrer uniquement les messages publics TEXT_MESSAGE_APP
            if 'decoded' not in packet:
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
            
            if portnum != 'TEXT_MESSAGE_APP':
                return
            
            # Extraire les infos
            from_id = packet.get('from', 0)
            to_id = packet.get('to', 0)
            
            # Vérifier que c'est un broadcast
            is_broadcast = to_id in [0xFFFFFFFF, 0]
            if not is_broadcast:
                return
            
            # Extraire le message
            message = self._extract_message_text(decoded)
            if not message:
                return
            
            # Éviter les doublons si le message est aussi reçu localement
            # (on peut marquer la source avec un flag)
            
            debug_print(f"📡 Message tigrog2: {self.node_manager.get_node_name(from_id)} -> '{message[:30]}...'")
            
            # Ajouter au traffic monitor avec flag source
            self.traffic_monitor.add_public_message(
                packet, 
                message, 
                source='tigrog2'  # ← Nouveau paramètre
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
