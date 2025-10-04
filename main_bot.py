#!/usr/bin/env python3
"""
Bot Mesh Debug - Version refactorisée avec architecture modulaire
"""

import time
import threading
import gc
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# Imports des modules
from config import *
from utils import *
from node_manager import NodeManager
from context_manager import ContextManager
from llama_client import LlamaClient
from esphome_client import ESPHomeClient
from remote_nodes_client import RemoteNodesClient
from message_handler import MessageHandler
from debug_interface import DebugInterface
from traffic_monitor import TrafficMonitor
from system_monitor import SystemMonitor

class DebugMeshBot:
    def __init__(self):
        self.interface = None
        self.running = False
        
        # Initialisation des gestionnaires
        self.node_manager = NodeManager()
        self.context_manager = ContextManager(self.node_manager)
        self.llama_client = LlamaClient(self.context_manager)
        self.esphome_client = ESPHomeClient()
        self.remote_nodes_client = RemoteNodesClient()
        self.traffic_monitor = TrafficMonitor(self.node_manager)
        
        # Gestionnaire de messages (initialisé après interface)
        self.message_handler = None
        
        # Interface de debug
        self.debug_interface = None
        
        # Thread de mise à jour
        self.update_thread = None
   
        self.telegram_integration = None
    

    def on_message(self, packet, interface):
        """Gestionnaire des messages - version optimisée avec modules"""
        try:
            # Mise à jour de la base de nœuds depuis les packets NodeInfo
            self.node_manager.update_node_from_packet(packet)
            
            # Mise à jour de l'historique RX pour tous les packets
            self.node_manager.update_rx_history(packet)
            
            # Vérifier si message pour nous
            to_id = packet.get('to', 0)
            from_id = packet.get('from', 0)
            my_id = None
            
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)
                debug_print(f"Mon ID détecté: {my_id:08x}")
            else:
                debug_print("ATTENTION: localNode non disponible")
            
            is_for_me = (to_id == my_id) if my_id else False
            is_from_me = (from_id == my_id) if my_id else False
            is_broadcast = to_id in [0xFFFFFFFF, 0]  # Messages broadcast
            
            if DEBUG_MODE:
                debug_print(f"Packet: From:{from_id:08x} To:{to_id:08x} ForMe:{is_for_me} FromMe:{is_from_me} Broadcast:{is_broadcast}")
            
            # Ne traiter que si c'est pour nous, de nous, ou broadcast
            if not (is_for_me or is_from_me or is_broadcast):
                if DEBUG_MODE:
                    debug_print("Packet ignoré (pas pour nous)")
                return
            
            if 'decoded' not in packet:
                if DEBUG_MODE:
                    debug_print("Packet non décodé")
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
        
            # Traitement des messages texte
            if portnum == 'TEXT_MESSAGE_APP':
                sender_name = self.node_manager.get_node_name(from_id, self.interface)
                debug_print(f"Message texte de {sender_name}")
                
                message = self._extract_message_text(decoded)
                
                if message and is_broadcast and not is_from_me:
                    self.traffic_monitor.add_public_message(packet, message)
                
                if message and self.message_handler:
                    self.message_handler.process_text_message(packet, decoded, message)
            else:
                # Autres types de packets (télémétrie, etc.) - juste pour debug
                if DEBUG_MODE and portnum in ['TELEMETRY_APP', 'NODEINFO_APP', 'POSITION_APP']:
                    debug_print(f"Packet {portnum} de {self.node_manager.get_node_name(from_id, self.interface)}")
            
        except Exception as e:
            error_print(f"Erreur traitement: {e}")
            import traceback
            error_print(traceback.format_exc())
    
    def _extract_message_text(self, decoded):
        """Extraire le texte du message décodé"""
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
    
    def periodic_update_thread(self):
        """Thread de mise à jour périodique"""
        # ✅ Délai initial pour laisser le système démarrer
        time.sleep(60)

        while self.running:
            try:
                # ✅ Sleep AVANT de faire le travail
                time.sleep(NODE_UPDATE_INTERVAL)
                
                if not self.running:
                    break
                
                # Mise à jour de la base de nœuds
                debug_print("🔄 Mise à jour périodique...")
                self.node_manager.update_node_database(self.interface)
                
                # Nettoyage périodique
                self.context_manager.cleanup_old_contexts()
                self.node_manager.cleanup_old_rx_history()
                self.traffic_monitor.cleanup_old_messages()
                
                debug_print("✅ Mise à jour périodique terminée")
                
            except Exception as e:
                error_print(f"Erreur thread mise à jour: {e}")
            time.sleep(60)  # Attendre avant de réessayer

    def cleanup_cache(self):
        """Nettoyage périodique général"""
        if self.llama_client:
            self.llama_client.cleanup_cache()
        
        self.context_manager.cleanup_old_contexts()
        self.node_manager.cleanup_old_rx_history()
        
        # Nettoyage des données de throttling
        if self.message_handler:
            self.message_handler.cleanup_throttling_data()
        
        gc.collect()
    
    def start(self):
        """Démarrage - version optimisée avec modules"""
        info_print("🤖 Bot Meshtastic-Llama avec architecture modulaire")
        
        # Charger la base de nœuds
        self.node_manager.load_node_names()
        
        # Nettoyage initial
        gc.collect()
        
        if not self.llama_client.test_connection():
            error_print("llama.cpp requis")
            return False
        
        try:
            info_print(f"Connexion {SERIAL_PORT}...")
            self.interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
            time.sleep(3)
            
            info_print("Interface Meshtastic OK")
            
            # Initialiser le gestionnaire de messages maintenant que l'interface existe
            self.message_handler = MessageHandler(
                self.llama_client,
                self.esphome_client, 
                self.remote_nodes_client,
                self.node_manager,
                self.context_manager,
                self.interface,
                self.traffic_monitor
            )
            
            # Intégration Telegram
            try:
                from telegram_integration import TelegramIntegration
                self.telegram_integration = TelegramIntegration(
                    self.message_handler,
                    self.node_manager,
                    self.context_manager
                )
                self.telegram_integration.start()
                info_print("✅ Interface Telegram intégrée")

                # ✅ Démarrer le monitoring système avec Telegram
                from system_monitor import SystemMonitor
                self.system_monitor = SystemMonitor(self.telegram_integration)
                self.system_monitor.start()
                info_print("🔍 Monitoring système démarré")

            except ImportError:
                debug_print("📱 Module Telegram non disponible")
            except Exception as e:
                error_print(f"Erreur intégration Telegram: {e}")
    
            # Mise à jour initiale de la base
            self.node_manager.update_node_database(self.interface)
            
            pub.subscribe(self.on_message, "meshtastic.receive")
            self.running = True
            
            # Démarrer le thread de mise à jour périodique
            self.update_thread = threading.Thread(target=self.periodic_update_thread, daemon=True)
            self.update_thread.start()
            info_print(f"⏰ Mise à jour périodique démarrée (toutes les {NODE_UPDATE_INTERVAL//60}min)")
            
            if DEBUG_MODE:
                info_print("🔧 MODE DEBUG avec architecture modulaire")
                print(f"Config: RSSI={SHOW_RSSI} SNR={SHOW_SNR} COLLECT={COLLECT_SIGNAL_METRICS}")
                print("\nCommandes: test, bot, power, rx, my, legend, help, sys, rebootg2, rebootpi, g2, echo, config, nodes, context, update, save, mem, quit")
                
                # Initialiser et démarrer l'interface debug
                self.debug_interface = DebugInterface(self)
                threading.Thread(target=self.debug_interface.interactive_loop, daemon=True).start()
            else:
                info_print("🚀 Bot en service - '/bot', '/power', '/rx', '/my', '/sys' et '/legend'")
            
            # Boucle principale avec nettoyage périodique
            cleanup_counter = 0
            while self.running:
                time.sleep(2)
                cleanup_counter += 1
                if cleanup_counter % 300 == 0:  # Toutes les 5 minutes
                    self.cleanup_cache()
                
        except Exception as e:
            error_print(f"Erreur: {e}")
            return False
    
    def stop(self):
        """Arrêt du bot"""
        info_print("Arrêt...")
        self.running = False
        
        # Sauvegarder avant fermeture
        if self.node_manager:
            self.node_manager.save_node_names(force=True)

        # ✅ Arrêter le monitoring système
        if hasattr(self, 'system_monitor') and self.system_monitor:
            self.system_monitor.stop() 

        # Arrêter l'intégration Telegram
        if self.telegram_integration:
            self.telegram_integration.stop()

        if self.interface:
            self.interface.close()
        gc.collect()
        info_print("Bot arrêté")
