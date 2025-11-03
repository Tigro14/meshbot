#!/usr/bin/env python3
"""
Main bot
"""

import time
import threading
import gc
import traceback
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
from packet_history import PacketHistory
from safe_serial_connection import SafeSerialConnection

class MeshBot:
    def __init__(self):
        self.interface = None
        self.serial_manager = None 
        self.running = False
        
        self.start_time = time.time()
        # Initialisation des gestionnaires
        self.node_manager = NodeManager(self.interface)
        self.context_manager = ContextManager(self.node_manager)
        self.llama_client = LlamaClient(self.context_manager)
        self.esphome_client = ESPHomeClient()
        self.traffic_monitor = TrafficMonitor(self.node_manager)
        self.packet_history = PacketHistory()
        self.remote_nodes_client = RemoteNodesClient()
        self.remote_nodes_client.set_node_manager(self.node_manager)

        # Gestionnaire de messages (initialisé après interface)
        self.message_handler = None
        # Interface de debug
        self.debug_interface = None
        # Thread de mise à jour
        self.update_thread = None
        self.telegram_integration = None

    def on_message(self, packet, interface):
        """Gestionnaire des messages - version corrigée pour collecte complète"""
        try:
            # Vérifier l'état de la connexion série
            if not self.serial_manager or not self.serial_manager.is_connected():
                info_print("⚠️  Connexion série instable, message ignoré")
                return

            # Mettre à jour l'interface si reconnectée
            if self.serial_manager.is_connected():
                self.interface = self.serial_manager.get_interface()

            # ========================================================
            # SECTION 1: COLLECTE DES STATS (TOUS LES PAQUETS)
            # ========================================================
            # Déterminer la source du paquet
            is_from_serial = (interface == self.interface)
            source = 'local' if is_from_serial else 'tigrog2'
            
            # Mise à jour de la base de nœuds depuis TOUS les packets
            self.node_manager.update_node_from_packet(packet)
            self.node_manager.update_rx_history(packet)
            self.node_manager.track_packet_type(packet)
            
            if 'decoded' in packet:
                portnum = packet['decoded'].get('portnum', 'UNKNOWN_APP')
                self.packet_history.add_packet(portnum)

            # Mise à jour de l'historique RX pour tous les packets
            self.node_manager.update_rx_history(packet)
            
            # Enregistrer TOUS les paquets pour l'histogramme
            if self.traffic_monitor:
                self.traffic_monitor.add_packet_to_history(packet)
                self.traffic_monitor.add_packet(packet)
            
            # ========================================================
            # SECTION 2: TRAITEMENT DES COMMANDES (SERIAL UNIQUEMENT)
            # ========================================================
            # Seuls les messages de l'interface locale déclenchent des commandes
            if not is_from_serial:
                debug_print(f"📊 Paquet de {source} collecté pour stats, mais non traité comme commande")
                return
            
            # À partir d'ici, seuls les messages de l'interface série sont traités
            
            # Vérifier le type de message
            to_id = packet.get('to', 0)
            if not to_id:
                return
            from_id = packet.get('from', 0)
            if not from_id:
                return
            my_id = None
            
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)
            
            is_for_me = (to_id == my_id) if my_id else False
            is_from_me = (from_id == my_id) if my_id else False
            is_broadcast = (to_id == 0xFFFFFFFF)
            
            # Filtrer les messages auto-générés
            if is_from_me:
                return
            
            decoded = packet.get('decoded', {})
            portnum = decoded.get('portnum', '')
            
            if portnum == 'TEXT_MESSAGE_APP':
                payload = decoded.get('payload', b'')
                
                try:
                    message = payload.decode('utf-8').strip()
                except:
                    return
                
                if not message:
                    return
                
                info_print("=" * 60)
                info_print(f"📨 MESSAGE REÇU")
                info_print(f"De: 0x{from_id:08x} ({self.node_manager.get_node_name(from_id)})")
                info_print(f"Pour: {'broadcast' if is_broadcast else f'0x{to_id:08x}'}")
                info_print(f"Contenu: {message[:50]}")
                
                # Gestion des traceroutes Telegram
                if self.telegram_integration:
                    if message:
                        info_print(f"✅ Message présent: '{message[:30]}'")
                        info_print(f"   Traces en attente: {len(self.telegram_integration.pending_traces)}")

                        try:
                            trace_handled = self.telegram_integration.handle_trace_response(
                                from_id,
                                message
                            )

                            if trace_handled:
                                info_print("✅ Message traité comme réponse de traceroute")
                                info_print("   Arrêt du traitement (pas de forward au message_handler)")
                                info_print("=" * 60)
                                return
                            else:
                                info_print("ℹ️ Message N'EST PAS une réponse de traceroute")
                                info_print("   Traitement normal continue...")

                        except Exception as trace_error:
                            error_print(f"❌ ERREUR dans handle_trace_response: {trace_error}")
                            error_print(traceback.format_exc())
                    else:
                        if not message:
                            info_print("⚠️ Message vide, pas de vérification traceroute")
                        if not self.telegram_integration:
                            info_print("⚠️ telegram_integration absent, pas de vérification traceroute")

                # Traitement normal du message
                info_print("➡️ Traitement normal du message...")

                if message and is_broadcast and not is_from_me:
                    self.traffic_monitor.add_public_message(packet, message, source='local')

                if message and self.message_handler:
                    self.message_handler.process_text_message(packet, decoded, message)

                info_print("=" * 60)
        
        except Exception as e:
            error_print(f"Erreur on_message: {e}")
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
                self.packet_history.cleanup_old_data() 
                self.packet_history.save_history()
                
                debug_print("✅ Mise à jour périodique terminée")
                
            except Exception as e:
                error_print(f"Erreur thread mise à jour: {e}")

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
            # ✅ NOUVEAU: Utiliser SafeSerialConnection avec auto-reconnexion
            info_print(f"🔌 Initialisation connexion série: {SERIAL_PORT}")
            self.serial_manager = SafeSerialConnection(
                port=SERIAL_PORT,
                max_retries=5,
                retry_delay=5,
                max_retry_delay=60,
                auto_reconnect=True  # Active la reconnexion automatique
            )

            if not self.serial_manager.connect():
                error_print("❌ Impossible d'établir la connexion série")
                return False

            self.interface = self.serial_manager.get_interface()
            info_print("✅ Interface Meshtastic OK avec auto-reconnexion activée")
            
            # Initialiser le gestionnaire de messages maintenant que l'interface existe
            self.message_handler = MessageHandler(
                self.llama_client,
                self.esphome_client, 
                self.remote_nodes_client,
                self.node_manager,
                self.context_manager,
                self.serial_manager, 
                self.traffic_monitor,
                self.start_time,
                packet_history=self.packet_history
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
                # Test du système
                time.sleep(5)  # Attendre que Telegram démarre
                self.telegram_integration.test_trace_system()

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
                time.sleep(30)  # CPU fix: 10s → 30s
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

        # ✅ NOUVEAU: Utiliser le gestionnaire pour fermer proprement
        if self.serial_manager:
            self.serial_manager.close()
            self.serial_manager = None

        self.interface = None

        gc.collect()
        info_print("Bot arrêté")
