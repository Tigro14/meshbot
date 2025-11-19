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
import meshtastic.tcp_interface
from pubsub import pub
from meshtastic.protobuf import portnums_pb2, telemetry_pb2

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
from safe_tcp_connection import SafeTCPConnection
from tcp_interface_patch import OptimizedTCPInterface
from vigilance_monitor import VigilanceMonitor
from blitz_monitor import BlitzMonitor
from mesh_traceroute_manager import MeshTracerouteManager

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
        if globals().get('VIGILANCE_ENABLED', False):
            try:
                self.vigilance_monitor = VigilanceMonitor(
                    departement=globals().get('VIGILANCE_DEPARTEMENT', '75'),
                    check_interval=globals().get('VIGILANCE_CHECK_INTERVAL', 900),
                    alert_throttle=globals().get('VIGILANCE_ALERT_THROTTLE', 3600),
                    alert_levels=globals().get('VIGILANCE_ALERT_LEVELS', ['Orange', 'Rouge'])
                )
            except Exception as e:
                error_print(f"Erreur initialisation vigilance monitor: {e}")
                self.vigilance_monitor = None

        # Moniteur d'éclairs Blitzortung (initialisé après interface dans start())
        self.blitz_monitor = None

        # Gestionnaire de traceroute mesh (initialisé après message_handler dans start())
        self.mesh_traceroute = None

        # Gestionnaire de messages (initialisé après interface)
        self.message_handler = None
        # Thread de mise à jour
        self.update_thread = None
        self.telegram_integration = None  # DEPRECATED: Utiliser platform_manager
        self.platform_manager = None  # Gestionnaire multi-plateforme

        # Déduplication des broadcasts: éviter de traiter nos propres messages diffusés
        # Format: {message_hash: timestamp}
        self._recent_broadcasts = {}
        self._broadcast_dedup_window = 60  # Fenêtre de 60 secondes
        
        # Timer pour télémétrie ESPHome
        self._last_telemetry_broadcast = 0
        
        # === DIAGNOSTIC CANAL - TEMPORAIRE ===
        #self._channel_analyzer = PacketChannelAnalyzer()
        #self._packets_analyzed = 0
        #self._channel_debug_active = True
        #info_print("🔍 Analyseur de canal activé - diagnostic en cours...")
        # === FIN DIAGNOSTIC ===

    def _track_broadcast(self, message):
        """
        Enregistrer un broadcast que nous venons d'envoyer
        
        Args:
            message: Contenu du message diffusé
        """
        try:
            import hashlib
            # Créer un hash du message pour identification
            msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
            current_time = time.time()
            
            # Nettoyer les anciens broadcasts (> window)
            self._recent_broadcasts = {
                h: t for h, t in self._recent_broadcasts.items()
                if current_time - t < self._broadcast_dedup_window
            }
            
            # Enregistrer ce broadcast
            self._recent_broadcasts[msg_hash] = current_time
            debug_print(f"🔖 Broadcast tracké: {msg_hash[:8]}... | msg: '{message[:50]}' | actifs: {len(self._recent_broadcasts)}")
        except Exception as e:
            error_print(f"❌ Erreur dans _track_broadcast: {e}")
            import traceback
            error_print(traceback.format_exc())
    
    def _is_recent_broadcast(self, message):
        """
        Vérifier si ce message est un de nos broadcasts récents
        
        Args:
            message: Contenu du message à vérifier
            
        Returns:
            bool: True si c'est un broadcast récent que nous avons envoyé
        """
        import hashlib
        try:
            msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
            current_time = time.time()
            
            # Vérifier si le hash existe et est récent
            if msg_hash in self._recent_broadcasts:
                age = current_time - self._recent_broadcasts[msg_hash]
                if age < self._broadcast_dedup_window:
                    debug_print(f"🔍 Broadcast reconnu ({age:.1f}s): {msg_hash[:8]}... | msg: '{message[:50]}'")
                    return True
                else:
                    # Hash existe mais est expiré, le nettoyer
                    debug_print(f"🧹 Broadcast expiré ({age:.1f}s): {msg_hash[:8]}...")
                    del self._recent_broadcasts[msg_hash]
            
            # Debug: afficher l'état des broadcasts trackés
            if DEBUG_MODE and len(self._recent_broadcasts) > 0:
                debug_print(f"📊 Broadcasts trackés: {len(self._recent_broadcasts)} actifs")
            
            return False
        except Exception as e:
            error_print(f"Erreur dans _is_recent_broadcast: {e}")
            import traceback
            error_print(traceback.format_exc())
            return False  # En cas d'erreur, ne pas filtrer

    def on_message(self, packet, interface=None):
        """
        Gestionnaire des messages reçus
        
        En mode single-node (CONNECTION_MODE):
        - Tous les paquets viennent de la même interface (serial OU tcp)
        - Tous les messages sont traités directement
        
        En mode legacy (multi-nodes):
        - Architecture en 3 phases pour distinguer serial/TCP
        - Filtrage selon PROCESS_TCP_COMMANDS
        
        Args:
            packet: Packet Meshtastic reçu
            interface: Interface source (peut être None pour messages publiés à meshtastic.receive.text)
        """

        # Debug: Tracer TOUS les appels à on_message
        debug_print(f"🔍 on_message APPELÉ - packet keys: {list(packet.keys()) if packet else 'None'}, interface: {interface is not None}")

        try:
            # Si pas d'interface fournie, utiliser l'interface principale
            if interface is None:
                interface = self.interface
                debug_print(f"🔍 Interface était None, utilisation de self.interface")
                
            # ========== VALIDATION BASIQUE ==========
            if not packet or 'from' not in packet:
                debug_print(f"🔍 Validation échouée: packet={packet is not None}, has_from={'from' in packet if packet else False}")
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
            # ========== FIN VALIDATION ==========


            # ========================================
            # DÉTERMINER LE MODE DE FONCTIONNEMENT
            # ========================================
            connection_mode = globals().get('CONNECTION_MODE', 'serial').lower()
            
            # En mode single-node, tous les paquets viennent de notre interface unique
            # Pas besoin de filtrage par source
            is_from_our_interface = (interface == self.interface)
            
            # Déterminer la source pour les logs et stats
            if connection_mode == 'tcp':
                source = 'tcp'
            elif connection_mode == 'serial':
                source = 'local'
            else:
                # Mode legacy: distinguer serial vs TCP externe
                source = 'local' if is_from_our_interface else 'tigrog2'

            # Obtenir l'ID du nœud local pour filtrage
            my_id = None
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)

            # ========================================
            # PHASE 1: COLLECTE (TOUS LES PAQUETS)
            # ========================================
            # Mise à jour de la base de nœuds depuis TOUS les packets
            self.node_manager.update_node_from_packet(packet)
            self.node_manager.update_rx_history(packet)
            self.node_manager.track_packet_type(packet)

            # Enregistrer TOUS les paquets pour les statistiques
            if self.traffic_monitor:
                self.traffic_monitor.add_packet(packet, source=source, my_node_id=my_id)

            # ========================================
            # PHASE 2: FILTRAGE (SELON MODE)
            # ========================================
            # En mode single-node: tous les paquets de notre interface sont traités
            # En mode legacy: filtrer selon PROCESS_TCP_COMMANDS
            
            if connection_mode in ['serial', 'tcp']:
                # MODE SINGLE-NODE: Traiter tous les messages de notre interface unique
                if not is_from_our_interface:
                    debug_print(f"📊 Paquet externe ignoré en mode single-node")
                    return
                # Continuer le traitement normalement
                
            else:
                # MODE LEGACY: Appliquer le filtrage historique
                # Si PROCESS_TCP_COMMANDS=False, seuls les messages série déclenchent des commandes
                # Si PROCESS_TCP_COMMANDS=True, les messages TCP (tigrog2) sont aussi traités
                if not is_from_our_interface and not globals().get('PROCESS_TCP_COMMANDS', False):
                    debug_print(f"📊 Paquet de {source} collecté pour stats uniquement")
                    return
            
            # À partir d'ici, les messages sont traités pour les commandes
            
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

            # Traiter les réponses TRACEROUTE_APP (avant TEXT_MESSAGE_APP)
            if portnum == 'TRACEROUTE_APP':
                if self.mesh_traceroute:
                    info_print(f"🔍 Réponse TRACEROUTE_APP de 0x{from_id:08x}")
                    handled = self.mesh_traceroute.handle_traceroute_response(packet)
                    if handled:
                        info_print("✅ Réponse traceroute traitée")
                        return
                return  # Ne pas traiter comme TEXT_MESSAGE

            if portnum == 'TEXT_MESSAGE_APP':
                payload = decoded.get('payload', b'')
                
                try:
                    message = payload.decode('utf-8').strip()
                except:
                    return
                
                if not message:
                    return
                
                # ========================================
                # DÉDUPLICATION BROADCASTS - TEMPORAIREMENT DÉSACTIVÉE
                # ========================================
                # TODO: Réactiver après investigation du problème "deaf"
                # La logique de déduplication cause un problème où le bot devient
                # "sourd" aux commandes. Désactivée temporairement pour diagnostic.
                #
                # Code original (désactivé):
                # if is_broadcast and self._is_recent_broadcast(message):
                #     debug_print(f"🔄 Broadcast ignoré (envoyé par nous): {message[:30]}")
                #     if message and not is_from_me:
                #         self.traffic_monitor.add_public_message(packet, message, source='local')
                #     return
                
                # Pour le moment, on log juste pour diagnostiquer
                if is_broadcast and len(self._recent_broadcasts) > 0:
                    try:
                        if self._is_recent_broadcast(message):
                            info_print(f"⚠️ DEDUP: Broadcast qui serait filtré: '{message[:50]}'")
                            info_print(f"⚠️ DEDUP: Mais on le traite quand même pour diagnostic")
                    except Exception as e:
                        error_print(f"Erreur check dedup: {e}")
                
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

                # ========================================
                # BROADCAST TÉLÉMÉTRIE ESPHOME
                # ========================================
                # Vérifier si il est temps d'envoyer la télémétrie
                telemetry_enabled = globals().get('ESPHOME_TELEMETRY_ENABLED', True)
                telemetry_interval = globals().get('ESPHOME_TELEMETRY_INTERVAL', 3600)
                
                if telemetry_enabled and self.interface:
                    current_time = time.time()
                    time_since_last = current_time - self._last_telemetry_broadcast
                    
                    if time_since_last >= telemetry_interval:
                        debug_print(f"⏰ Broadcast télémétrie ESPHome (intervalle: {telemetry_interval}s)")
                        self.send_esphome_telemetry()
                        self._last_telemetry_broadcast = current_time

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

        # Cleanup des traceroutes expirés
        if self.mesh_traceroute:
            try:
                self.mesh_traceroute.cleanup_expired_traces()
            except Exception as e:
                debug_print(f"Erreur cleanup traceroutes: {e}")

        gc.collect()

    def send_esphome_telemetry(self):
        """
        Envoyer les données ESPHome comme télémétrie broadcast sur le mesh
        
        Broadcast les capteurs ESPHome (température, pression, humidité, batterie)
        au réseau mesh via TELEMETRY_APP pour que tous les nodes puissent voir
        les conditions environnementales du node bot.
        """
        try:
            # Vérifier que la télémétrie est activée
            if not globals().get('ESPHOME_TELEMETRY_ENABLED', True):
                return
            
            # Récupérer les valeurs des capteurs
            sensor_values = self.esphome_client.get_sensor_values()
            
            if not sensor_values:
                debug_print("⚠️ Pas de données ESPHome disponibles pour télémétrie")
                return
            
            # Créer le message de télémétrie
            telemetry_data = telemetry_pb2.Telemetry()
            telemetry_data.time = int(time.time())
            
            # Ajouter les métriques environnementales
            has_data = False
            
            if sensor_values.get('temperature') is not None:
                telemetry_data.environment_metrics.temperature = sensor_values['temperature']
                has_data = True
                info_print(f"📊 Télémétrie - Température: {sensor_values['temperature']:.1f}°C")
            
            if sensor_values.get('pressure') is not None:
                # La pression est déjà en Pascals (converti dans get_sensor_values)
                telemetry_data.environment_metrics.barometric_pressure = sensor_values['pressure']
                has_data = True
                info_print(f"📊 Télémétrie - Pression: {sensor_values['pressure']:.0f} Pa")
            
            if sensor_values.get('humidity') is not None:
                telemetry_data.environment_metrics.relative_humidity = sensor_values['humidity']
                has_data = True
                info_print(f"📊 Télémétrie - Humidité: {sensor_values['humidity']:.1f}%")
            
            # Pour la tension batterie, utiliser device_metrics
            if sensor_values.get('battery_voltage') is not None:
                # Calculer le niveau de batterie en % (11V = 0%, 13.8V = 100%)
                battery_level = min(100, max(0, int((sensor_values['battery_voltage'] - 11.0) / (13.8 - 11.0) * 100)))
                telemetry_data.device_metrics.battery_level = battery_level
                telemetry_data.device_metrics.voltage = sensor_values['battery_voltage']
                has_data = True
                info_print(f"📊 Télémétrie - Batterie: {sensor_values['battery_voltage']:.1f}V ({battery_level}%)")
            
            if not has_data:
                debug_print("⚠️ Aucune donnée à envoyer en télémétrie")
                return
            
            # Envoyer en broadcast via TELEMETRY_APP
            info_print("📡 Envoi télémétrie ESPHome en broadcast...")
            self.interface.sendData(
                telemetry_data,
                destinationId=0xFFFFFFFF,  # Broadcast
                portNum=portnums_pb2.PortNum.TELEMETRY_APP,
                wantResponse=False
            )
            
            info_print("✅ Télémétrie ESPHome envoyée avec succès")
            
        except Exception as e:
            error_print(f"Erreur envoi télémétrie ESPHome: {e}")
            error_print(traceback.format_exc())
    
    def start(self):
        """Démarrage du bot - version simplifiée avec support TCP/Serial"""
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
            # DÉTECTION DU MODE DE CONNEXION
            # ========================================
            connection_mode = globals().get('CONNECTION_MODE', 'serial').lower()
            
            if connection_mode == 'tcp':
                # ========================================
                # MODE TCP - Connexion réseau
                # ========================================
                tcp_host = globals().get('TCP_HOST', '192.168.1.38')
                tcp_port = globals().get('TCP_PORT', 4403)
                
                info_print(f"🌐 Mode TCP: Connexion à {tcp_host}:{tcp_port}")
                
                # Utiliser OptimizedTCPInterface pour économiser CPU
                self.interface = OptimizedTCPInterface(
                    hostname=tcp_host,
                    portNumber=tcp_port
                )
                info_print("✅ Interface TCP créée")
                
                # Stabilisation plus longue pour TCP
                time.sleep(5)
                info_print("✅ Connexion TCP stable")
                
            else:
                # ========================================
                # MODE SERIAL - Connexion série (défaut)
                # ========================================
                serial_port = globals().get('SERIAL_PORT', '/dev/ttyACM0')
                
                info_print(f"🔌 Mode Serial: Connexion série {serial_port}")
                self.interface = meshtastic.serial_interface.SerialInterface(serial_port)
                info_print("✅ Interface série créée")
                
                # Stabilisation
                time.sleep(3)
                info_print("✅ Connexion série stable")
            
            # ========================================
            # RÉUTILISATION DE L'INTERFACE PRINCIPALE
            # ========================================
            # Partager l'interface avec RemoteNodesClient pour éviter
            # de créer des connexions TCP supplémentaires
            self.remote_nodes_client.interface = self.interface
            info_print("♻️ Interface partagée avec RemoteNodesClient")
            
            # ========================================
            # ABONNEMENT AUX MESSAGES (CRITIQUE!)
            # ========================================
            # DOIT être fait immédiatement après la création de l'interface
            # S'abonner aux différents types de messages Meshtastic
            # - meshtastic.receive.text : messages texte (TEXT_MESSAGE_APP)
            # - meshtastic.receive.data : messages de données
            # - meshtastic.receive : messages génériques (fallback)
            
            # Debug: Créer un callback de débogage pour voir ce qui est reçu
            def debug_callback(**kwargs):
                """Callback de debug pour tracer tous les messages pubsub"""
                debug_print(f"🔍 DEBUG PUBSUB - Reçu avec args: {list(kwargs.keys())}")
                if 'packet' in kwargs:
                    pkt = kwargs['packet']
                    from_id = pkt.get('from', 'N/A')
                    to_id = pkt.get('to', 'N/A')
                    decoded = pkt.get('decoded', {})
                    portnum = decoded.get('portnum', 'N/A')
                    debug_print(f"🔍 DEBUG PUBSUB - from={from_id}, to={to_id}, portnum={portnum}")
            
            # S'abonner avec le callback principal ET le callback de debug
            pub.subscribe(self.on_message, "meshtastic.receive.text")
            pub.subscribe(debug_callback, "meshtastic.receive.text")
            pub.subscribe(self.on_message, "meshtastic.receive.data")
            pub.subscribe(self.on_message, "meshtastic.receive")
            info_print("✅ Abonné aux messages Meshtastic (text, data, all)")
            self.running = True

            # ========================================
            # MONITORING ÉCLAIRS BLITZORTUNG
            # ========================================
            if globals().get('BLITZ_ENABLED', False):
                try:
                    info_print("⚡ Initialisation Blitz monitor...")
                    # Utiliser les coordonnées explicites si fournies, sinon auto-detect depuis interface
                    blitz_lat = globals().get('BLITZ_LATITUDE', 0.0)
                    blitz_lon = globals().get('BLITZ_LONGITUDE', 0.0)
                    lat = blitz_lat if blitz_lat != 0.0 else None
                    lon = blitz_lon if blitz_lon != 0.0 else None

                    self.blitz_monitor = BlitzMonitor(
                        lat=lat,
                        lon=lon,
                        radius_km=globals().get('BLITZ_RADIUS_KM', 50),
                        check_interval=globals().get('BLITZ_CHECK_INTERVAL', 900),
                        window_minutes=globals().get('BLITZ_WINDOW_MINUTES', 15),
                        interface=self.interface
                    )

                    if self.blitz_monitor.enabled:
                        info_print("✅ Blitz monitor initialisé")
                    else:
                        info_print("⚠️ Blitz monitor désactivé (position GPS non disponible)")
                except Exception as e:
                    error_print(f"Erreur initialisation blitz monitor: {e}")
                    self.blitz_monitor = None

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
                self.blitz_monitor,
                self.vigilance_monitor,
                broadcast_tracker=self._track_broadcast  # Callback pour tracker les broadcasts
            )

            # Initialiser le gestionnaire de traceroute mesh (après message_handler)
            info_print("📦 Initialisation MeshTracerouteManager...")
            self.mesh_traceroute = MeshTracerouteManager(
                node_manager=self.node_manager,
                message_sender=self.message_handler.router.sender
            )
            # Rendre disponible au router et au network_handler pour handle_trace
            self.message_handler.router.mesh_traceroute = self.mesh_traceroute
            self.message_handler.router.network_handler.mesh_traceroute = self.mesh_traceroute
            info_print("✅ MessageHandler créé")

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
                daemon=True,
                name="PeriodicUpdate"
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


