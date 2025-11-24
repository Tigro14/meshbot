#!/usr/bin/env python3
"""
Main bot
"""

import time
import threading
import gc
import traceback
import signal
import sys
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
from pubsub import pub
from meshtastic.protobuf import portnums_pb2, telemetry_pb2, admin_pb2

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
                info_print("🌦️ Initialisation du moniteur de vigilance météo...")
                self.vigilance_monitor = VigilanceMonitor(
                    departement=globals().get('VIGILANCE_DEPARTEMENT', '75'),
                    check_interval=globals().get('VIGILANCE_CHECK_INTERVAL', 28800),
                    alert_throttle=globals().get('VIGILANCE_ALERT_THROTTLE', 3600),
                    alert_levels=globals().get('VIGILANCE_ALERT_LEVELS', ['Orange', 'Rouge'])
                )
            except Exception as e:
                error_print(f"Erreur initialisation vigilance monitor: {e}")
                error_print(traceback.format_exc())
                self.vigilance_monitor = None
        else:
            debug_print("ℹ️ Moniteur de vigilance météo désactivé (VIGILANCE_ENABLED=False)")

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
        
        # État de reconnexion TCP (pour éviter reconnexions multiples)
        self._tcp_reconnection_thread = None
        self._tcp_reconnection_in_progress = False
        
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
            # Broadcast can be to 0xFFFFFFFF or to 0 (both are broadcast addresses)
            is_broadcast = (to_id in [0xFFFFFFFF, 0])

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
                # DÉDUPLICATION BROADCASTS - Prévenir boucles infinies
                # ========================================
                # Filtrer nos propres broadcasts pour éviter de les retraiter
                # Vérifie: is_broadcast ET hash du contenu correspond à un envoi récent
                # Note: Ne filtre PAS les DMs (is_broadcast doit être True)
                
                if is_broadcast:
                    try:
                        if self._is_recent_broadcast(message):
                            debug_print(f"🔄 Broadcast ignoré (envoyé par nous): {message[:30]}")
                            # Comptabiliser quand même dans les stats
                            if message and not is_from_me:
                                self.traffic_monitor.add_public_message(packet, message, source='local')
                            return  # Ne pas traiter ce broadcast
                    except Exception as e:
                        # En cas d'erreur dans la déduplication, continuer quand même
                        # pour ne pas bloquer le traitement des messages
                        error_print(f"❌ Erreur déduplication broadcast: {e}")
                        import traceback
                        error_print(traceback.format_exc())
                        # Continuer avec le traitement normal
                
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
    
    def _check_and_reconnect_interface(self):
        """
        Vérifie la santé de l'interface TCP et reconnecte si nécessaire
        
        Retourne True si l'interface est opérationnelle, False sinon
        
        IMPORTANT: Version non-bloquante - ne bloque pas le thread périodique
        """
        # Seulement pour le mode TCP
        connection_mode = globals().get('CONNECTION_MODE', 'serial').lower()
        if connection_mode != 'tcp':
            return True
        
        # Vérifier si une reconnexion est déjà en cours
        if self._tcp_reconnection_in_progress:
            debug_print("⏳ Reconnexion TCP déjà en cours, skip health check")
            return False  # Pas OK mais reconnexion en cours
        
        try:
            # Vérifier si l'interface existe et si le socket est vivant
            if not self.interface or not hasattr(self.interface, 'socket'):
                info_print("⚠️ Interface manquante, tentative de reconnexion...")
                return self._reconnect_tcp_interface()
            
            # Vérifier si le socket existe
            if not self.interface.socket:
                info_print("⚠️ Socket TCP manquant, tentative de reconnexion...")
                return self._reconnect_tcp_interface()
            
            # Vérifier si le socket est fermé (méthode 1: fileno)
            try:
                fd = self.interface.socket.fileno()
                if fd == -1:
                    info_print("⚠️ Socket TCP fermé (fileno=-1), tentative de reconnexion...")
                    return self._reconnect_tcp_interface()
            except Exception as e:
                # Si fileno() lève une exception, le socket est invalide
                info_print(f"⚠️ Socket TCP invalide ({e}), tentative de reconnexion...")
                return self._reconnect_tcp_interface()
            
            # Vérifier si le socket est réellement connecté (méthode 2: getpeername)
            # getpeername() échoue si le socket n'est pas connecté
            try:
                self.interface.socket.getpeername()
            except AttributeError as e:
                # Pas d'attribut getpeername - socket invalide
                info_print(f"⚠️ Socket TCP invalide (pas de getpeername), tentative de reconnexion...")
                return self._reconnect_tcp_interface()
            except OSError as e:
                # Seulement reconnexion pour les erreurs qui indiquent vraiment une déconnexion
                # errno 107 (ENOTCONN): Transport endpoint is not connected
                # errno 9 (EBADF): Bad file descriptor
                # errno 57 (ENOTCONN sur macOS)
                import errno
                if e.errno in (errno.ENOTCONN, errno.EBADF, 57):
                    info_print(f"⚠️ Socket TCP déconnecté (errno {e.errno}: {e}), tentative de reconnexion...")
                    return self._reconnect_tcp_interface()
                else:
                    # Autre erreur OSError - ne pas reconnexion, juste logger
                    debug_print(f"⚠️ Erreur getpeername non-fatale (errno {e.errno}): {e}")
                    # Considérer le socket comme OK pour cette erreur
                    return True
            
            # Socket semble OK
            debug_print("✅ Vérification interface TCP: OK")
            return True
            
        except Exception as e:
            error_print(f"⚠️ Erreur vérification interface: {e}")
            # En cas d'erreur, tenter quand même une reconnexion
            return self._reconnect_tcp_interface()
    
    def _reconnect_tcp_interface(self):
        """
        Reconnecte l'interface TCP après une déconnexion
        
        Retourne False immédiatement et lance la reconnexion en arrière-plan
        
        IMPORTANT: Version NON-BLOQUANTE - ne bloque pas le thread appelant
        La reconnexion se fait dans un thread séparé pour ne pas freezer le bot
        """
        try:
            # Marquer la reconnexion comme en cours
            if self._tcp_reconnection_in_progress:
                debug_print("⏳ Reconnexion déjà en cours, ignorer")
                return False
            
            self._tcp_reconnection_in_progress = True
            
            tcp_host = globals().get('TCP_HOST', '192.168.1.38')
            tcp_port = globals().get('TCP_PORT', 4403)
            
            info_print(f"🔄 Lancement reconnexion TCP à {tcp_host}:{tcp_port} (en arrière-plan)...")
            
            def reconnect_background():
                """Fonction de reconnexion exécutée dans un thread séparé"""
                try:
                    # Fermer l'ancienne interface si elle existe
                    if self.interface:
                        try:
                            self.interface.close()
                        except:
                            pass
                    
                    # Créer une nouvelle interface
                    # Le socket a un timeout de 5s, donc même si bloqué, ça timeout rapidement
                    new_interface = OptimizedTCPInterface(
                        hostname=tcp_host,
                        portNumber=tcp_port
                    )
                    
                    # Attendre la stabilisation
                    time.sleep(5)
                    
                    # Mettre à jour les références
                    self.interface = new_interface
                    self.node_manager.interface = self.interface
                    self.remote_nodes_client.interface = self.interface
                    if self.mesh_traceroute:
                        self.mesh_traceroute.interface = self.interface
                    
                    # NOTE: PAS de réabonnement ici ! L'abonnement initial à pub.subscribe()
                    # est déjà actif et fonctionne automatiquement avec la nouvelle interface.
                    # Réabonner causerait des duplications de messages et des freezes.
                    
                    info_print("✅ Reconnexion TCP réussie (background)")
                    self._tcp_reconnection_in_progress = False
                    
                except Exception as e:
                    error_print(f"❌ Échec reconnexion TCP (background): {e}")
                    error_print(traceback.format_exc())
                    self._tcp_reconnection_in_progress = False
            
            # Lancer la reconnexion dans un thread daemon (ne bloque pas l'arrêt du bot)
            self._tcp_reconnection_thread = threading.Thread(
                target=reconnect_background,
                daemon=True,
                name="TCP-Reconnect"
            )
            self._tcp_reconnection_thread.start()
            
            # Retourner False immédiatement (reconnexion en cours)
            return False
            
        except Exception as e:
            error_print(f"❌ Erreur lancement reconnexion: {e}")
            error_print(traceback.format_exc())
            self._tcp_reconnection_in_progress = False
            return False
    
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
                
                # Vérifier la santé de l'interface TCP et reconnexion si nécessaire
                if globals().get('CONNECTION_MODE', 'serial').lower() == 'tcp':
                    debug_print("🔍 Vérification santé interface TCP...")
                    self._check_and_reconnect_interface()
                
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
                    try:
                        debug_print("🌦️ Vérification vigilance météo...")
                        self.vigilance_monitor.check_vigilance()
                    except Exception as e:
                        error_print(f"⚠️ Erreur check vigilance (non-bloquante): {e}")
                        error_print(traceback.format_exc())
                        # Continuer avec les autres tâches

                # Vérification éclairs (si activée)
                if self.blitz_monitor and self.blitz_monitor.enabled:
                    try:
                        self.blitz_monitor.check_and_report()
                    except Exception as e:
                        error_print(f"⚠️ Erreur check blitz (non-bloquante): {e}")
                        # Continuer avec les autres tâches

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

    def _send_telemetry_packet(self, telemetry_data, packet_type):
        """
        Envoyer un paquet de télémétrie avec gestion robuste des erreurs réseau
        
        Args:
            telemetry_data: Données de télémétrie (protobuf Telemetry)
            packet_type: Type de paquet pour les logs ("environment_metrics" ou "device_metrics")
        
        Returns:
            bool: True si envoyé avec succès, False sinon
        """
        try:
            info_print(f"📡 Envoi télémétrie ESPHome ({packet_type})...")
            self.interface.sendData(
                telemetry_data,
                destinationId=0xFFFFFFFF,  # Broadcast
                portNum=portnums_pb2.PortNum.TELEMETRY_APP,
                wantResponse=False
            )
            info_print(f"✅ Télémétrie {packet_type} envoyée")
            return True
            
        except BrokenPipeError as e:
            # Erreur réseau normale - connexion TCP temporairement cassée
            # Le bot vérifie périodiquement la connexion et reconnectera si nécessaire
            debug_print(f"⚠️ Connexion réseau perdue lors de l'envoi télémétrie ({packet_type}): {e}")
            debug_print("Le bot reconnectera automatiquement lors de la prochaine vérification périodique")
            return False
            
        except (ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError) as e:
            # Autres erreurs réseau normales
            debug_print(f"⚠️ Erreur réseau lors de l'envoi télémétrie ({packet_type}): {e}")
            debug_print("Le bot reconnectera automatiquement lors de la prochaine vérification périodique")
            return False
            
        except Exception as e:
            # Erreurs inattendues - logger complètement pour debug
            error_print(f"❌ Erreur inattendue lors de l'envoi télémétrie ({packet_type}): {e}")
            error_print(traceback.format_exc())
            return False
    
    def send_esphome_telemetry(self):
        """
        Envoyer les données ESPHome comme télémétrie broadcast sur le mesh
        
        IMPORTANT: Meshtastic telemetry uses a 'oneof' field, so environment_metrics
        and device_metrics must be sent in SEPARATE packets to comply with the
        TELEMETRY standard. This ensures all data is visible in node details.
        
        Sends up to 2 packets:
        1. Environment metrics (temperature, pressure, humidity)
        2. Device metrics (battery voltage, battery level)
        """
        try:
            # Vérifier que la télémétrie est activée
            if not globals().get('ESPHOME_TELEMETRY_ENABLED', True):
                return
            
            # Récupérer les valeurs des capteurs
            debug_print("Récupération capteurs ESPHome pour télémétrie...")
            sensor_values = self.esphome_client.get_sensor_values()
            
            if not sensor_values:
                debug_print("⚠️ Pas de données ESPHome disponibles pour télémétrie")
                return
            
            current_time = int(time.time())
            packets_sent = 0
            
            # ===== PACKET 1: Environment Metrics =====
            # Send environment data (temperature, pressure, humidity) in first packet
            has_env_data = False
            env_telemetry = telemetry_pb2.Telemetry()
            env_telemetry.time = current_time
            
            if sensor_values.get('temperature') is not None:
                env_telemetry.environment_metrics.temperature = sensor_values['temperature']
                has_env_data = True
                debug_print(f"📊 temperature: {sensor_values['temperature']}")
            
            if sensor_values.get('pressure') is not None:
                # La pression est déjà en Pascals (converti dans get_sensor_values)
                env_telemetry.environment_metrics.barometric_pressure = sensor_values['pressure']
                has_env_data = True
                debug_print(f"📊 pressure: {sensor_values['pressure']}")
            
            if sensor_values.get('humidity') is not None:
                env_telemetry.environment_metrics.relative_humidity = sensor_values['humidity']
                has_env_data = True
                debug_print(f"📊 humidity: {sensor_values['humidity']}")
            
            if has_env_data:
                info_print(f"📊 Télémétrie Env - Température: {sensor_values.get('temperature', 'N/A')}°C")
                info_print(f"📊 Télémétrie Env - Pression: {sensor_values.get('pressure', 0):.0f} Pa")
                info_print(f"📊 Télémétrie Env - Humidité: {sensor_values.get('humidity', 'N/A')}%")
                
                if self._send_telemetry_packet(env_telemetry, "environment_metrics"):
                    packets_sent += 1
                    # Small delay between packets to avoid overwhelming the mesh
                    time.sleep(0.5)
            
            # ===== PACKET 2: Device Metrics =====
            # Send battery data in separate packet (required by Meshtastic protobuf 'oneof')
            has_device_data = False
            device_telemetry = telemetry_pb2.Telemetry()
            device_telemetry.time = current_time
            
            if sensor_values.get('battery_voltage') is not None:
                # Calculer le niveau de batterie en % (11V = 0%, 13.8V = 100%)
                battery_level = min(100, max(0, int((sensor_values['battery_voltage'] - 11.0) / (13.8 - 11.0) * 100)))
                device_telemetry.device_metrics.battery_level = battery_level
                device_telemetry.device_metrics.voltage = sensor_values['battery_voltage']
                has_device_data = True
                debug_print(f"📊 battery_voltage: {sensor_values['battery_voltage']}")
            
            if has_device_data:
                info_print(f"📊 Télémétrie Device - Batterie: {sensor_values['battery_voltage']:.1f}V ({battery_level}%)")
                
                if self._send_telemetry_packet(device_telemetry, "device_metrics"):
                    packets_sent += 1
            
            if packets_sent == 0:
                debug_print("⚠️ Aucune donnée à envoyer en télémétrie")
            else:
                info_print(f"✅ Télémétrie ESPHome complète: {packets_sent} paquet(s) envoyé(s)")
            
        except Exception as e:
            # Erreur non-réseau (ex: problème protobuf, ESPHome indisponible)
            error_print(f"❌ Erreur préparation télémétrie ESPHome: {e}")
            error_print(traceback.format_exc())
    
    def _signal_handler(self, signum, frame):
        """
        Gestionnaire de signaux pour arrêt propre
        
        Gère SIGTERM (systemd stop) et SIGINT (Ctrl+C) pour arrêter proprement le bot
        au lieu de l'interrompre brutalement.
        """
        signal_name = signal.Signals(signum).name
        info_print(f"🛑 Signal {signal_name} reçu - arrêt propre du bot...")
        self.running = False
    
    def start(self):
        """Démarrage du bot - version simplifiée avec support TCP/Serial"""
        info_print("🤖 Bot Meshtastic-Llama avec architecture modulaire")
        
        # ========================================
        # INSTALLATION GESTIONNAIRES DE SIGNAUX
        # ========================================
        # Configurer les gestionnaires pour arrêt propre
        signal.signal(signal.SIGTERM, self._signal_handler)  # systemd stop
        signal.signal(signal.SIGINT, self._signal_handler)   # Ctrl+C
        info_print("✅ Gestionnaires de signaux installés (SIGTERM, SIGINT)")
        
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
            
            # S'abonner avec le callback principal
            # NOTE: Seulement "meshtastic.receive" pour éviter les duplications
            # (ce topic catch ALL messages: text, data, position, etc.)
            pub.subscribe(self.on_message, "meshtastic.receive")
            
            # Debug callback seulement si DEBUG_MODE
            if globals().get('DEBUG_MODE', False):
                pub.subscribe(debug_callback, "meshtastic.receive")
            
            info_print("✅ Abonné aux messages Meshtastic (receive)")
            self.running = True

            # ========================================
            # CONFIGURATION TÉLÉMÉTRIE EMBARQUÉE
            # ========================================
            # Désactiver la télémétrie embarquée du device si ESPHome est activé
            # pour éviter le bruit mesh avec des paquets redondants
            if globals().get('ESPHOME_TELEMETRY_ENABLED', False):
                try:
                    info_print("📊 ESPHome télémétrie activée - désactivation télémétrie embarquée...")
                    
                    # Attendre que le node local soit prêt
                    time.sleep(2)
                    
                    if hasattr(self.interface, 'localNode') and self.interface.localNode:
                        local_node = self.interface.localNode
                        
                        # Vérifier que moduleConfig est disponible
                        if hasattr(local_node, 'moduleConfig') and local_node.moduleConfig:
                            # Configurer device_update_interval à 0 pour désactiver
                            current_interval = local_node.moduleConfig.telemetry.device_update_interval
                            info_print(f"   Intervalle actuel: {current_interval}s")
                            
                            if current_interval != 0:
                                local_node.moduleConfig.telemetry.device_update_interval = 0
                                
                                # Écrire la configuration
                                local_node.writeConfig('telemetry')
                                info_print("✅ Télémétrie embarquée désactivée (device_update_interval = 0)")
                            else:
                                info_print("✅ Télémétrie embarquée déjà désactivée")
                        else:
                            info_print("⚠️ moduleConfig non disponible - télémétrie embarquée non modifiée")
                    else:
                        info_print("⚠️ localNode non disponible - télémétrie embarquée non modifiée")
                        
                except Exception as e:
                    error_print(f"⚠️ Erreur lors de la désactivation télémétrie embarquée: {e}")
                    error_print(traceback.format_exc())
                    info_print("   → Continuer avec configuration actuelle")
            else:
                info_print("📊 ESPHome télémétrie désactivée - télémétrie embarquée inchangée")

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
                try:
                    time.sleep(30)
                    cleanup_counter += 1
                    if cleanup_counter % 10 == 0:  # Toutes les 5 minutes
                        self.cleanup_cache()
                except Exception as loop_error:
                    # Erreur dans la boucle principale - logger mais continuer
                    error_print(f"⚠️ Erreur dans la boucle principale: {loop_error}")
                    error_print(traceback.format_exc())
                    # Continuer le fonctionnement malgré l'erreur
                    time.sleep(5)  # Pause courte avant de continuer
            
            # Si nous sortons de la boucle normalement (self.running = False)
            # c'est un arrêt intentionnel, retourner True
            info_print("🛑 Sortie de la boucle principale (arrêt intentionnel)")
            return True
                
        except Exception as e:
            error_print(f"Erreur: {e}")
            error_print(traceback.format_exc())
            return False

    def stop(self):
        """
        Arrêt du bot avec timeout global
        
        Version améliorée avec protection contre les blocages:
        - Timeout global de 8 secondes pour tout le shutdown
        - Exception handling sur chaque composant
        - Continue même si un composant bloque
        """
        info_print("Arrêt...")
        self.running = False
        
        # Timeout global pour éviter les blocages infinis
        import concurrent.futures
        shutdown_timeout = 8  # secondes (systemd DefaultTimeoutStopSec est souvent 90s)
        
        def _perform_shutdown():
            """Shutdown complet avec gestion d'erreurs par composant"""
            # 1. Sauvegarder avant fermeture (critique, mais rapide)
            try:
                if self.node_manager:
                    self.node_manager.save_node_names(force=True)
            except Exception as e:
                error_print(f"⚠️ Erreur sauvegarde node_manager: {e}")

            # 2. Arrêter le monitoring système (peut prendre jusqu'à 3s)
            try:
                if hasattr(self, 'system_monitor') and self.system_monitor:
                    self.system_monitor.stop()
            except Exception as e:
                error_print(f"⚠️ Erreur arrêt system_monitor: {e}")

            # 3. Arrêter le monitoring éclairs
            try:
                if self.blitz_monitor and self.blitz_monitor.enabled:
                    self.blitz_monitor.stop_monitoring()
            except Exception as e:
                error_print(f"⚠️ Erreur arrêt blitz_monitor: {e}")

            # 4. Arrêter toutes les plateformes (peut bloquer sur Telegram asyncio)
            try:
                if self.platform_manager:
                    self.platform_manager.stop_all()
            except Exception as e:
                error_print(f"⚠️ Erreur arrêt platform_manager: {e}")

            # 5. Compatibilité ancienne méthode (DEPRECATED)
            try:
                if self.telegram_integration and not self.platform_manager:
                    self.telegram_integration.stop()
            except Exception as e:
                error_print(f"⚠️ Erreur arrêt telegram_integration: {e}")

            # 6. Fermer connexions série/TCP
            try:
                if hasattr(self, 'safe_serial') and self.safe_serial:
                    self.safe_serial.close()
            except Exception as e:
                error_print(f"⚠️ Erreur fermeture safe_serial: {e}")

            # 7. Nettoyage final
            try:
                self.interface = None
                gc.collect()
            except Exception as e:
                error_print(f"⚠️ Erreur nettoyage final: {e}")
        
        # Exécuter le shutdown avec timeout
        # Note: On ne peut pas vraiment tuer les threads en Python,
        # mais on peut limiter le temps d'attente du processus principal
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(_perform_shutdown)
            future.result(timeout=shutdown_timeout)
            info_print("✅ Bot arrêté proprement")
        except concurrent.futures.TimeoutError:
            error_print(f"⚠️ Timeout shutdown ({shutdown_timeout}s) - forçage arrêt")
            # Ne pas attendre l'executor - laisser les threads mourir avec le processus
            info_print("⚠️ Bot arrêté (timeout)")
        finally:
            # Forcer la fermeture sans attendre les threads
            executor.shutdown(wait=False)

