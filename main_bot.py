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
from traffic_monitor import TrafficMonitor
from system_monitor import SystemMonitor
from safe_serial_connection import SafeSerialConnection
from vigilance_monitor import VigilanceMonitor
from blitz_monitor import BlitzMonitor

# Import du nouveau gestionnaire multi-plateforme
from platforms import PlatformManager
from platforms.telegram_platform import TelegramPlatform
from platforms.cli_server_platform import CLIServerPlatform
from platform_config import get_enabled_platforms

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
        self.remote_nodes_client = RemoteNodesClient()
        self.remote_nodes_client.set_node_manager(self.node_manager)

        # Moniteur de vigilance météo (si activé)
        self.vigilance_monitor = None
        if VIGILANCE_ENABLED:
            self.vigilance_monitor = VigilanceMonitor(
                departement=VIGILANCE_DEPARTEMENT,
                check_interval=VIGILANCE_CHECK_INTERVAL,
                alert_throttle=VIGILANCE_ALERT_THROTTLE,
                alert_levels=VIGILANCE_ALERT_LEVELS
            )

        # Moniteur d'éclairs Blitzortung (initialisé après interface dans start())
        self.blitz_monitor = None

        # Gestionnaire de messages (initialisé après interface)
        self.message_handler = None
        # Thread de mise à jour
        self.update_thread = None
        self.telegram_integration = None  # DEPRECATED: Utiliser platform_manager
        self.platform_manager = None  # Gestionnaire multi-plateforme

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

            # Obtenir l'ID du nœud local pour filtrage
            my_id = None
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)

            # Mise à jour de la base de nœuds depuis TOUS les packets
            self.node_manager.update_node_from_packet(packet)
            self.node_manager.update_rx_history(packet)
            self.node_manager.track_packet_type(packet)

            # Enregistrer TOUS les paquets pour les statistiques
            if self.traffic_monitor:
                self.traffic_monitor.add_packet(packet, source=source, my_node_id=my_id)

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

                        try:
                            # Vérifier que pending_traces existe avant de l'utiliser
                            if hasattr(self.telegram_integration, 'pending_traces'):
                                info_print(f"   Traces en attente: {len(self.telegram_integration.pending_traces)}")

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

                # Sauvegarde des statistiques dans SQLite
                debug_print("💾 Sauvegarde des statistiques...")
                self.traffic_monitor.save_statistics()

                # Nettoyage des anciennes données SQLite (> 48h)
                self.traffic_monitor.cleanup_old_persisted_data(hours=48)

                # Vérification vigilance météo (si activée)
                if self.vigilance_monitor:
                    self.vigilance_monitor.check_vigilance()

                # Vérification éclairs (si activée)
                if self.blitz_monitor and self.blitz_monitor.enabled:
                    self.blitz_monitor.check_and_report()

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
                self.start_time
            )
            info_print("✅ MessageHandler créé")

            # ========================================
            # MONITORING ÉCLAIRS BLITZORTUNG
            # ========================================
            if BLITZ_ENABLED:
                info_print("⚡ Initialisation Blitz monitor...")
                # Utiliser les coordonnées explicites si fournies, sinon auto-detect depuis interface
                lat = BLITZ_LATITUDE if BLITZ_LATITUDE != 0.0 else None
                lon = BLITZ_LONGITUDE if BLITZ_LONGITUDE != 0.0 else None

                self.blitz_monitor = BlitzMonitor(
                    lat=lat,
                    lon=lon,
                    radius_km=BLITZ_RADIUS_KM,
                    check_interval=BLITZ_CHECK_INTERVAL,
                    window_minutes=BLITZ_WINDOW_MINUTES,
                    interface=self.interface
                )

                if self.blitz_monitor.enabled:
                    info_print("✅ Blitz monitor initialisé")
                else:
                    info_print("⚠️ Blitz monitor désactivé (position GPS non disponible)")

            # ========================================
            # INTÉGRATION PLATEFORMES MESSAGERIE
            # ========================================
            try:
                info_print("🌐 Initialisation gestionnaire de plateformes...")
                self.platform_manager = PlatformManager()

                # Enregistrer toutes les plateformes activées
                for platform_config in get_enabled_platforms():
                    info_print(f"📱 Configuration plateforme: {platform_config.platform_name}")

                    if platform_config.platform_name == 'telegram':
                        telegram_platform = TelegramPlatform(
                            platform_config,
                            self.message_handler,
                            self.node_manager,
                            self.context_manager
                        )
                        self.platform_manager.register_platform(telegram_platform)

                        # Garder la référence pour compatibilité (DEPRECATED)
                        self.telegram_integration = telegram_platform.telegram_integration

                    elif platform_config.platform_name == 'cli_server':
                        info_print("🖥️  Configuration serveur CLI...")
                        cli_server_platform = CLIServerPlatform(
                            platform_config,
                            self.message_handler,
                            self.node_manager,
                            self.context_manager
                        )
                        self.platform_manager.register_platform(cli_server_platform)

                    # TODO: Ajouter Discord quand implémenté
                    # elif platform_config.platform_name == 'discord':
                    #     discord_platform = DiscordPlatform(...)
                    #     self.platform_manager.register_platform(discord_platform)

                # Démarrer toutes les plateformes
                self.platform_manager.start_all()

                active_platforms = self.platform_manager.get_active_platforms()
                if active_platforms:
                    info_print(f"✅ Plateformes actives: {', '.join(active_platforms)}")
                else:
                    info_print("⏸️ Aucune plateforme messagerie active")

                # Test Telegram si actif
                if self.telegram_integration:
                    time.sleep(5)
                    try:
                        self.telegram_integration.test_trace_system()
                    except AttributeError:
                        pass  # test_trace_system n'existe peut-être pas

                # Démarrer le monitoring système (si Telegram actif)
                if self.telegram_integration:
                    from system_monitor import SystemMonitor
                    self.system_monitor = SystemMonitor(self.telegram_integration)
                    self.system_monitor.start()
                    info_print("🔍 Monitoring système démarré")

                # Démarrer le monitoring éclairs (si activé)
                if self.blitz_monitor and self.blitz_monitor.enabled:
                    self.blitz_monitor.start_monitoring()
                    info_print("⚡ Monitoring éclairs démarré (MQTT)")

            except ImportError as e:
                info_print(f"📱 Plateformes messagerie non disponibles: {e}")
            except Exception as e:
                error_print(f"Erreur intégration plateformes: {e}")
                error_print(traceback.format_exc())
            
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
                info_print("🔧 MODE DEBUG activé")
                print(f"Config: RSSI={SHOW_RSSI} SNR={SHOW_SNR} COLLECT={COLLECT_SIGNAL_METRICS}")
                print("Debug via logs et commandes /stats, /db, etc.")
            else:
                info_print("🚀 Bot en service - type /help")
            
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

        # Arrêter le monitoring éclairs
        if self.blitz_monitor and self.blitz_monitor.enabled:
            self.blitz_monitor.stop_monitoring()

        # Arrêter l'intégration Telegram
        # Arrêter toutes les plateformes
        if self.platform_manager:
            self.platform_manager.stop_all()

        # Compatibilité ancienne méthode (DEPRECATED)
        if self.telegram_integration and not self.platform_manager:
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


