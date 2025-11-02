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
        self.remote_nodes_client.set_node_manager(self.node_manager)
        self.context_manager = ContextManager(self.node_manager)
        self.llama_client = LlamaClient(self.context_manager)
        self.esphome_client = ESPHomeClient()
        self.remote_nodes_client = RemoteNodesClient()
        self.traffic_monitor = TrafficMonitor(self.node_manager)
        self.packet_history = PacketHistory()
        
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
            # ✅ NOUVEAU: Vérifier l'état de la connexion
            if not self.serial_manager or not self.serial_manager.is_connected():
                info_print("⚠️  Connexion série instable, message ignoré")
                return

            # Mettre à jour l'interface si reconnectée
            if self.serial_manager.is_connected():
                self.interface = self.serial_manager.get_interface()

            # ✅ CRITIQUE : Filtrer seulement les messages de NOTRE interface locale
            if interface != self.interface:
                return  # Ignorer les messages du bridge tigrog2

            # Mise à jour de la base de nœuds depuis les packets NodeInfo
            self.node_manager.update_node_from_packet(packet)
            self.node_manager.update_rx_history(packet)
            self.node_manager.track_packet_type(packet) 
            
            if 'decoded' in packet:
                portnum = packet['decoded'].get('portnum', 'UNKNOWN_APP')
                self.packet_history.add_packet(portnum)

            # Mise à jour de l'historique RX pour tous les packets
            self.node_manager.update_rx_history(packet)
            
            # === NOUVEAU: Enregistrer TOUS les paquets pour l'histogramme ===
            if self.traffic_monitor:
                self.traffic_monitor.add_packet_to_history(packet)
                self.traffic_monitor.add_packet(packet)  # ← Pour alimenter all_packets et le /top
            
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
            is_broadcast = to_id in [0xFFFFFFFF, 0]
            
            if not (is_for_me or is_from_me or is_broadcast):
                return
            
            if 'decoded' not in packet:
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
            
            # === Traitement des TRACEROUTE_APP ===
            if portnum == 'TRACEROUTE_APP':
                info_print("=" * 60)
                info_print(f"📥 TRACEROUTE_APP reçu de {self.node_manager.get_node_name(from_id)}")
                info_print("=" * 60)
                
                if self.telegram_integration:
                    try:
                        self.telegram_integration.handle_traceroute_response(packet, decoded)
                    except Exception as trace_error:
                        error_print(f"❌ Erreur handle_traceroute_response: {trace_error}")
                        error_print(traceback.format_exc())
                
                return  # Pas de traitement supplémentaire

            # Traitement des messages texte
            if portnum == 'TEXT_MESSAGE_APP':
                from_id = packet.get('from', 0)
                sender_name = self.node_manager.get_node_name(from_id, self.interface)

                info_print("=" * 60)
                info_print(f"📥 MESSAGE TEXTE REÇU")
                info_print(f"   From: {sender_name} (0x{from_id:08x})")
                info_print("=" * 60)

                message = self._extract_message_text(decoded)

                if message:
                    info_print(f"   Message: {message[:100]}...")

                # === HOOK TRACEROUTE - VERSION DEBUG ===
                if message and self.telegram_integration:
                    info_print("🔍 Vérification si réponse de traceroute...")
                    info_print(f"   telegram_integration présent: {self.telegram_integration is not None}")
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
                            return  # Ne pas traiter plus loin
                        else:
                            info_print("ℹ️ Message N'EST PAS une réponse de traceroute")
                            info_print("   Traitement normal continue...")

                    except Exception as trace_error:
                        error_print(f"❌ ERREUR dans handle_trace_response: {trace_error}")
                        error_print(traceback.format_exc())
                        # Continuer le traitement normal en cas d'erreur
                else:
                    if not message:
                        info_print("⚠️ Message vide, pas de vérification traceroute")
                    if not self.telegram_integration:
                        info_print("⚠️ telegram_integration absent, pas de vérification traceroute")

                # === TRAITEMENT NORMAL ===
                info_print("➡️ Traitement normal du message...")

                if message and is_broadcast and not is_from_me:
                    self.traffic_monitor.add_public_message(packet, message)

                if message and self.message_handler:
                    self.message_handler.process_text_message(packet, decoded, message)

                info_print("=" * 60)
            #else:
                # Autres types de packets (télémétrie, etc.) - juste pour debug
                #if DEBUG_MODE and portnum in ['TELEMETRY_APP', 'NODEINFO_APP', 'POSITION_APP']:
                #    debug_print(f"Packet {portnum} de {self.node_manager.get_node_name(from_id, self.interface)}")
            
        except Exception as e:
#            error_print(f"Erreur traitement: {e}")
#            error_print(traceback.format_exc())
            # ✅ AMÉLIORATION : Logging détaillé
            error_print(f"❌ EXCEPTION dans on_message:")
            error_print(f"   Type: {type(e).__name__}")
            error_print(f"   Message: {str(e)}")
            error_print(f"   Packet from: {packet.get('from', 'unknown')}")
            error_print(f"   Packet type: {packet.get('decoded', {}).get('portnum', 'unknown')}")
            import traceback
            error_print(f"   Traceback complet:")
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
                self.interface,
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
