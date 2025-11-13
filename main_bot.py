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

        # === DIAGNOSTIC CANAL - TEMPORAIRE ===
        #self._channel_analyzer = PacketChannelAnalyzer()
        #self._packets_analyzed = 0
        #self._channel_debug_active = True
        #info_print("🔍 Analyseur de canal activé - diagnostic en cours...")
        # === FIN DIAGNOSTIC ===

    def on_message(self, packet, interface):
        """
        Gestionnaire des messages reçus
        
        Architecture en 3 phases:
        1. Collecte de TOUS les paquets (serial + TCP)
        2. Filtrage selon la source
        3. Traitement des commandes (serial uniquement)
        """
        
        # === DEBUG CANAL - TEMPORAIRE ===
        if not hasattr(self, '_channel_analyzer'):
            from packet_channel_analyzer import PacketChannelAnalyzer
            self._channel_analyzer = PacketChannelAnalyzer()
            self._packets_analyzed = 0
        
        info = self._channel_analyzer.analyze_packet(packet)
        self._packets_analyzed += 1
        
        # Afficher le rapport après 100 paquets
        if self._packets_analyzed == 100:
            print(self._channel_analyzer.print_diagnostic_report())
        
        # Afficher chaque paquet avec canal détecté
        if info['channel_detected']:
            print(f"📡 PAQUET CANAL {info['channel_value']}: "
                  f"type={info['packet_type']}, "
                  f"décodé={info['has_decoded']}")
        # === FIN DEBUG ===
        # ========== TEST ==========
        if packet and 'decoded' in packet:
            decoded = packet.get('decoded', {})
            if decoded.get('portnum') == 'TEXT_MESSAGE_APP':
                payload = decoded.get('payload', b'')
                try:
                    msg = payload.decode('utf-8').strip()
                    if '/annonce' in msg:
                        info_print("🔴🔴🔴 /ANNONCE DÉTECTÉ 🔴🔴🔴")
                        info_print(f"Message: '{msg}'")
                        info_print(f"From: 0x{packet.get('from', 0):08x}")
                        info_print(f"To: 0x{packet.get('to', 0):08x}")
                except:
                    pass
        # ========== FIN TEST ==========

        try:
            # ========== TEST DÉTAILLÉ ==========
            # Validation basique
            if not packet or 'from' not in packet:
                return

            from_id = packet.get('from', 0)
            to_id = packet.get('to', 0)

            decoded = packet.get('decoded', {})
            if decoded.get('portnum') == 'TEXT_MESSAGE_APP':
                payload = decoded.get('payload', b'')
                try:
                    msg = payload.decode('utf-8').strip()
                    info_print(f"📨 MESSAGE BRUT: '{msg}' | from=0x{from_id:08x} | to=0x{to_id:08x} | broadcast={to_id in [0xFFFFFFFF, 0]}")
                except:
                    pass
            # ========== FIN TEST ==========


            # ========================================
            # PHASE 1: COLLECTE (TOUS LES PAQUETS)
            # ========================================
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
            
            # Enregistrer TOUS les paquets pour les statistiques
            if self.traffic_monitor:
                self.traffic_monitor.add_packet_to_history(packet)
                self.traffic_monitor.add_packet(packet, source=source)  
            
            # ========================================
            # PHASE 2: FILTRAGE
            # ========================================
            # Seuls les messages de l'interface série déclenchent des commandes
            if not is_from_serial:
                debug_print(f"📊 Paquet de {source} collecté pour stats")
                return
            
            # À partir d'ici, seuls les messages série sont traités
            
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
            
            # ========================================
            # PHASE 3: TRAITEMENT DES COMMANDES
            # ========================================
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
                                info_print("=" * 60)
                                return
                            else:
                                info_print("ℹ️ Message N'EST PAS une réponse de traceroute")

                        except Exception as trace_error:
                            error_print(f"❌ Erreur handle_trace_response: {trace_error}")
                            error_print(traceback.format_exc())

                # Traitement normal du message
                info_print("➡️ Traitement normal du message...")

                # Enregistrer les messages publics
                if message and is_broadcast and not is_from_me:
                    self.traffic_monitor.add_public_message(packet, message, source='local')

                # Traiter les commandes
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
        """Démarrage du bot - version simplifiée"""
        info_print("🤖 Bot Meshtastic-Llama avec architecture modulaire")
        
        # Charger la base de nœuds
        self.node_manager.load_node_names()
        
        # Nettoyage initial
        gc.collect()
        
        # Test llama
        if not self.llama_client.test_connection():
            error_print("llama.cpp requis")
            return False
       
        try:
            # ========================================
            # CONNEXION SÉRIE DIRECTE
            # ========================================
            info_print(f"🔌 Connexion série: {SERIAL_PORT}")
            self.interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
            info_print("✅ Interface série créée")
            
            # Stabilisation
            time.sleep(3)
            info_print("✅ Connexion stable")
            
            # ========================================
            # ABONNEMENT AUX MESSAGES (CRITIQUE!)
            # ========================================
            # DOIT être fait immédiatement après la création de l'interface
            pub.subscribe(self.on_message, "meshtastic.receive")
            info_print("✅ Abonné aux messages Meshtastic")
            self.running = True
            
            # ========================================
            # INITIALISATION DES GESTIONNAIRES
            # ========================================
            info_print("📦 Initialisation MessageHandler...")
            self.message_handler = MessageHandler(
                self.llama_client,
                self.esphome_client, 
                self.remote_nodes_client,
                self.node_manager,
                self.context_manager,
                self.interface,  # Interface directe
                self.traffic_monitor,
                self.start_time,
                packet_history=self.packet_history
            )
            info_print("✅ MessageHandler créé")
            
            # ========================================
            # INTÉGRATION TELEGRAM
            # ========================================
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
                time.sleep(5)
                self.telegram_integration.test_trace_system()

                # Démarrer le monitoring système
                from system_monitor import SystemMonitor
                self.system_monitor = SystemMonitor(self.telegram_integration)
                self.system_monitor.start()
                info_print("🔍 Monitoring système démarré")

            except ImportError:
                debug_print("📱 Module Telegram non disponible")
            except Exception as e:
                error_print(f"Erreur intégration Telegram: {e}")
            
            # ========================================
            # MISE À JOUR BASE DE NŒUDS
            # ========================================
            info_print("📊 Mise à jour base de nœuds...")
            self.node_manager.update_node_database(self.interface)
            info_print("✅ Base de nœuds mise à jour")
            
            # ========================================
            # THREAD DE MISE À JOUR PÉRIODIQUE
            # ========================================
            self.update_thread = threading.Thread(
                target=self.periodic_update_thread, 
                daemon=True
            )
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
                info_print("🚀 Bot en service- type /help")
            
            # ========================================
            # BOUCLE PRINCIPALE
            # ========================================
            cleanup_counter = 0
            while self.running:
                time.sleep(30)
                cleanup_counter += 1
                if cleanup_counter % 10 == 0:  # Toutes les 5 minutes
                    self.cleanup_cache()
                
        except Exception as e:
            error_print(f"Erreur: {e}")
            error_print(traceback.format_exc())
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
#        if self.serial_manager:
#            self.serial_manager.close()
#            self.serial_manager = None
        if hasattr(self, 'safe_serial') and self.safe_serial:
            self.safe_serial.close()

        self.interface = None

        gc.collect()
        info_print("Bot arrêté")


