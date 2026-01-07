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
import subprocess
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
from mqtt_neighbor_collector import MQTTNeighborCollector
from mesh_traceroute_manager import MeshTracerouteManager
from db_error_monitor import DBErrorMonitor
from reboot_semaphore import RebootSemaphore

# Import du nouveau gestionnaire multi-plateforme
from platforms import PlatformManager
from platforms.telegram_platform import TelegramPlatform
from platforms.cli_server_platform import CLIServerPlatform
from platform_config import get_enabled_platforms

class MeshBot:
    # Configuration pour la reconnexion TCP
    # ESP32 needs time to fully release the old connection before accepting a new one
    # The ESP32 may keep the connection in TIME_WAIT state for up to 2 minutes
    TCP_INTERFACE_CLEANUP_DELAY = 15  # Secondes à attendre après fermeture ancienne interface
    TCP_INTERFACE_STABILIZATION_DELAY = 3  # Secondes à attendre après création nouvelle interface (réduit car vérification socket directe)
    TCP_HEALTH_MONITOR_INITIAL_DELAY = 30  # Délai initial avant de démarrer le monitoring TCP
    TCP_PUBKEY_SYNC_DELAY = 30  # Délai après reconnexion avant de synchroniser les clés publiques (AUGMENTÉ à 30s pour ESP32 lents)
    TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT = True  # DEFAULT: Skip sync on reconnect to avoid overloading ESP32 (use periodic sync instead)
    
    def __init__(self):
        self.interface = None
        self.running = False
        
        self.start_time = time.time()
        
        # Load TCP configuration from config if available
        import config as cfg
        
        # TCP silent timeout - max time without packets before reconnection
        self.TCP_SILENT_TIMEOUT = getattr(cfg, 'TCP_SILENT_TIMEOUT', 120)
        debug_print(f"🔧 TCP_SILENT_TIMEOUT configuré: {self.TCP_SILENT_TIMEOUT}s")
        
        # TCP health check interval - frequency of health checks
        self.TCP_HEALTH_CHECK_INTERVAL = getattr(cfg, 'TCP_HEALTH_CHECK_INTERVAL', 30)
        debug_print(f"🔧 TCP_HEALTH_CHECK_INTERVAL configuré: {self.TCP_HEALTH_CHECK_INTERVAL}s")
        
        # Moniteur d'erreurs DB (initialisé avant TrafficMonitor pour callback)
        self.db_error_monitor = None
        self._init_db_error_monitor()
        
        # Initialisation des gestionnaires
        self.node_manager = NodeManager(self.interface)
        self.context_manager = ContextManager(self.node_manager)
        self.llama_client = LlamaClient(self.context_manager)
        self.esphome_client = ESPHomeClient()
        self.traffic_monitor = TrafficMonitor(self.node_manager)
        self.remote_nodes_client = RemoteNodesClient()
        self.remote_nodes_client.set_node_manager(self.node_manager)
        
        # Configurer le callback d'erreur DB dans traffic_monitor.persistence
        if self.db_error_monitor and self.traffic_monitor.persistence:
            self.traffic_monitor.persistence.error_callback = self.db_error_monitor.record_error
            debug_print("✅ Callback d'erreur DB configuré")

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

        # Collecteur de voisins MQTT (initialisé après traffic_monitor dans start())
        self.mqtt_neighbor_collector = None

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
        self._tcp_reconnection_attempts = 0  # Counter for backoff
        self._tcp_last_reconnection_attempt = 0  # Timestamp of last attempt
        
        # Détection silence TCP - si pas de paquet reçu depuis trop longtemps, forcer reconnexion
        self._last_packet_time = time.time()
        self._tcp_health_thread = None  # Thread de vérification santé TCP rapide
        
        # Packet reception tracking for diagnostics
        from collections import deque
        self._packet_timestamps = deque(maxlen=100)  # Keep last 100 packet times for rate analysis
        self._packets_this_session = 0  # Count packets per TCP session
        self._session_start_time = time.time()  # Session start for rate calculation
        
        # Timestamp pour synchronisation périodique des clés publiques
        self._last_pubkey_sync_time = 0  # Permettre sync immédiate au premier cycle
        
        # === DIAGNOSTIC CANAL - TEMPORAIRE ===
        #self._channel_analyzer = PacketChannelAnalyzer()
        #self._packets_analyzed = 0
        #self._channel_debug_active = True
        #info_print("🔍 Analyseur de canal activé - diagnostic en cours...")
        # === FIN DIAGNOSTIC ===

    def _is_tcp_mode(self):
        """
        Vérifie si le bot est en mode TCP
        
        Returns:
            bool: True si CONNECTION_MODE == 'tcp', False sinon
        """
        return globals().get('CONNECTION_MODE', 'serial').lower() == 'tcp'

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
        # ✅ CRITICAL: Update packet timestamp FIRST, before any early returns
        # This prevents false "silence" detections when packets arrive during reconnection
        # Even if we ignore the packet for processing, we need to record that we received it
        current_time = time.time()
        self._last_packet_time = current_time
        
        # Track packet reception for diagnostics
        self._packet_timestamps.append(current_time)
        self._packets_this_session += 1
        
        # Protection contre les traitements pendant la reconnexion TCP
        # Évite les race conditions et les messages provenant de l'ancienne interface
        if self._tcp_reconnection_in_progress:
            debug_print("⏸️ Message ignoré: reconnexion TCP en cours")
            return

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
            # En mode single-node, tous les paquets viennent de notre interface unique
            # Pas besoin de filtrage par source
            is_from_our_interface = (interface == self.interface)
            
            # Déterminer la source pour les logs et stats
            if self._is_tcp_mode():
                source = 'tcp'
            elif globals().get('CONNECTION_MODE', 'serial').lower() == 'serial':
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
                self.traffic_monitor.add_packet(packet, source=source, my_node_id=my_id, interface=self.interface)

            # ========================================
            # PHASE 2: FILTRAGE (SELON MODE)
            # ========================================
            # En mode single-node: tous les paquets de notre interface sont traités
            # En mode legacy: filtrer selon PROCESS_TCP_COMMANDS
            
            # Get connection mode from globals (set in run() method)
            connection_mode = globals().get('CONNECTION_MODE', 'serial').lower()
            
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
                info_print(f"🔍 Réponse TRACEROUTE_APP de 0x{from_id:08x}")
                
                # Traiter pour mesh traceroute (commandes /trace depuis mesh)
                mesh_handled = False
                if self.mesh_traceroute:
                    mesh_handled = self.mesh_traceroute.handle_traceroute_response(packet)
                    if mesh_handled:
                        info_print("✅ Réponse traceroute mesh traitée")
                
                # Également notifier les plateformes (Telegram /trace)
                if self.platform_manager:
                    self.platform_manager.handle_traceroute_response(packet, decoded)
                    info_print("✅ Réponse traceroute envoyée aux plateformes")
                
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
                            # Ajouter nos propres broadcasts (comme /echo) aux messages publics
                            if message:
                                self.traffic_monitor.add_public_message(packet, message, source='local')
                            return  # Ne pas traiter ce broadcast
                    except Exception as e:
                        # En cas d'erreur dans la déduplication, continuer quand même
                        # pour ne pas bloquer le traitement des messages
                        error_print(f"❌ Erreur déduplication broadcast: {e}")
                        import traceback
                        error_print(traceback.format_exc())
                        # Continuer avec le traitement normal
                
                debug_print(f"📨 MESSAGE REÇU De: 0x{from_id:08x} Contenu: {message[:50]}")
                
                # Gestion des traceroutes Telegram
                if self.telegram_integration and message:
                    try:
                        trace_handled = self.telegram_integration.handle_trace_response(
                            from_id,
                            message
                        )

                        if trace_handled:
                            debug_print("Message traité comme réponse de traceroute")
                            return

                    except Exception as trace_error:
                        error_print(f"❌ Erreur handle_trace_response: {trace_error}")
                        error_print(traceback.format_exc())

                # Enregistrer les messages publics
                if message and is_broadcast and not is_from_me:
                    self.traffic_monitor.add_public_message(packet, message, source='local')

                # Traiter les commandes
                if message and self.message_handler:
                    self.message_handler.process_text_message(packet, decoded, message)
        
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
        if not self._is_tcp_mode():
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
    
    def _send_tcp_disconnect_alert(self, tcp_host, tcp_port, error_message=None):
        """
        Envoyer une alerte Telegram quand la connexion TCP est définitivement perdue
        
        Args:
            tcp_host: Adresse du nœud TCP
            tcp_port: Port du nœud TCP
            error_message: Message d'erreur optionnel (cause de la déconnexion)
        """
        # Vérifier si les alertes TCP sont activées
        if not globals().get('TCP_DISCONNECT_ALERT_ENABLED', True):
            debug_print("⏸️ Alertes déconnexion TCP désactivées")
            return
        
        # Vérifier si Telegram est disponible
        if not self.telegram_integration:
            debug_print("⚠️ Pas de Telegram pour alerte déconnexion TCP")
            return
        
        try:
            # Construire le message d'alerte
            remote_name = globals().get('REMOTE_NODE_NAME', 'Meshtastic')
            
            message = (
                f"🔴 ALERTE: Connexion TCP perdue\n\n"
                f"📡 Nœud: {remote_name}\n"
                f"🌐 Host: {tcp_host}:{tcp_port}\n"
                f"⏱️ Heure: {time.strftime('%H:%M:%S')}\n"
            )
            
            if error_message:
                # Limiter la longueur de l'erreur
                error_short = str(error_message)[:100]
                message += f"❌ Erreur: {error_short}\n"
            
            message += (
                f"\n⚠️ Le bot ne peut plus communiquer avec le réseau Meshtastic.\n"
                f"🔄 Reconnexion automatique en échec après plusieurs tentatives.\n"
                f"💡 Action recommandée: Vérifier l'alimentation et le réseau du nœud."
            )
            
            self.telegram_integration.send_alert(message)
            info_print("📢 Alerte déconnexion TCP envoyée via Telegram")
            
        except Exception as e:
            error_print(f"⚠️ Erreur envoi alerte déconnexion TCP: {e}")
            error_print(traceback.format_exc())
    
    def _reboot_remote_node(self, tcp_host):
        """
        Redémarre le nœud Meshtastic distant via la commande CLI
        
        Args:
            tcp_host: Adresse IP du nœud à redémarrer
        
        Returns:
            bool: True si le reboot a été envoyé avec succès, False sinon
        """
        try:
            info_print(f"🔄 Tentative de redémarrage du nœud distant {tcp_host}...")
            
            # Utiliser python3 -m meshtastic pour assurer la disponibilité
            cmd = [
                sys.executable, "-m", "meshtastic",
                "--host", tcp_host,
                "--reboot"
            ]
            
            info_print(f"   Commande: {' '.join(cmd)}")
            
            # Exécuter la commande avec timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # Timeout de 30 secondes
            )
            
            if result.returncode == 0:
                info_print(f"✅ Commande de redémarrage envoyée au nœud {tcp_host}")
                if result.stdout:
                    debug_print(f"   Output: {result.stdout.strip()}")
                return True
            else:
                error_print(f"❌ Échec commande reboot (code {result.returncode})")
                if result.stderr:
                    error_print(f"   Erreur: {result.stderr.strip()}")
                return False
                
        except subprocess.TimeoutExpired:
            error_print(f"⏱️ Timeout lors du reboot du nœud {tcp_host}")
            return False
        except FileNotFoundError:
            error_print("❌ Module meshtastic non trouvé - impossible de rebooter")
            error_print("   Installer avec: pip install meshtastic")
            return False
        except Exception as e:
            error_print(f"❌ Erreur reboot nœud distant: {e}")
            error_print(traceback.format_exc())
            return False
    
    def _reconnect_tcp_interface(self):
        """
        Reconnecte l'interface TCP après une déconnexion
        
        Retourne False immédiatement et lance la reconnexion en arrière-plan
        
        IMPORTANT: Version NON-BLOQUANTE - ne bloque pas le thread appelant
        La reconnexion se fait dans un thread séparé pour ne pas freezer le bot
        
        Implements exponential backoff to avoid hammering the ESP32 with rapid
        reconnection attempts. ESP32 needs time to fully release old connections.
        """
        try:
            # Marquer la reconnexion comme en cours
            if self._tcp_reconnection_in_progress:
                debug_print("⏳ Reconnexion déjà en cours, ignorer")
                return False
            
            # Implement backoff: wait longer between reconnection attempts
            current_time = time.time()
            time_since_last = current_time - self._tcp_last_reconnection_attempt
            
            # Calculate backoff delay: 0, 5, 10, 20, 30, 30, 30... seconds
            backoff_delay = min(30, self._tcp_reconnection_attempts * 5)
            
            if time_since_last < backoff_delay:
                remaining = int(backoff_delay - time_since_last)
                debug_print(f"⏳ Backoff: attendre encore {remaining}s avant reconnexion (tentative {self._tcp_reconnection_attempts + 1})")
                return False
            
            self._tcp_reconnection_in_progress = True
            self._tcp_reconnection_attempts += 1
            self._tcp_last_reconnection_attempt = current_time
            
            # Pause callbacks on old interface to avoid spam during reconnection
            if self.interface and hasattr(self.interface, 'pause_dead_socket_callbacks'):
                self.interface.pause_dead_socket_callbacks()
            
            tcp_host = globals().get('TCP_HOST', '192.168.1.38')
            tcp_port = globals().get('TCP_PORT', 4403)
            
            info_print(f"🔄 Reconnexion TCP #{self._tcp_reconnection_attempts} à {tcp_host}:{tcp_port}...")
            
            def reconnect_background():
                """Fonction de reconnexion exécutée dans un thread séparé"""
                MAX_RETRIES = 3
                retry_delays = [15, 30, 60]  # Increasing delays between retries
                
                for retry in range(MAX_RETRIES):
                    try:
                        # Fermer l'ancienne interface si elle existe
                        old_interface = self.interface
                        if old_interface:
                            try:
                                debug_print("🔄 Fermeture ancienne interface TCP...")
                                old_interface.close()
                                debug_print("✅ Ancienne interface fermée")
                            except Exception as close_error:
                                debug_print(f"⚠️ Erreur fermeture ancienne interface: {close_error}")
                            
                            # IMPORTANT: Attendre que les threads de l'ancienne interface
                            # aient le temps de se terminer avant de créer la nouvelle
                            # Ceci évite les conflits de ressources et les doublons de messages
                            wait_time = self.TCP_INTERFACE_CLEANUP_DELAY if retry == 0 else retry_delays[retry]
                            debug_print(f"⏳ Attente nettoyage ({wait_time}s) - tentative {retry + 1}/{MAX_RETRIES}...")
                            time.sleep(wait_time)
                        
                        # Créer une nouvelle interface
                        # Le socket a un timeout de 5s, donc même si bloqué, ça timeout rapidement
                        debug_print("🔧 Création nouvelle interface TCP...")
                        new_interface = OptimizedTCPInterface(
                            hostname=tcp_host,
                            portNumber=tcp_port
                        )
                        
                        # Attendre la stabilisation de la nouvelle interface AVANT de configurer le callback
                        debug_print(f"⏳ Stabilisation nouvelle interface ({self.TCP_INTERFACE_STABILIZATION_DELAY}s)...")
                        time.sleep(self.TCP_INTERFACE_STABILIZATION_DELAY)
                        
                        # CRITIQUE: Vérifier que le socket est TOUJOURS connecté après stabilisation
                        # Le socket peut mourir pendant la stabilisation
                        socket_ok = False
                        if hasattr(new_interface, 'socket') and new_interface.socket:
                            try:
                                peer = new_interface.socket.getpeername()
                                debug_print(f"✅ Socket connecté à {peer}")
                                socket_ok = True
                            except Exception as e:
                                debug_print(f"⚠️ Socket mort pendant stabilisation: {e}")
                        
                        # Si le socket est mort, retry avec un délai plus long
                        if not socket_ok:
                            if retry < MAX_RETRIES - 1:
                                error_print(f"❌ Connexion échouée, nouvelle tentative dans {retry_delays[retry + 1]}s...")
                                try:
                                    new_interface.close()
                                except:
                                    pass
                                continue  # Retry
                            else:
                                error_print("❌ Reconnexion abandonnée après 3 tentatives")
                                # Envoyer alerte Telegram
                                self._send_tcp_disconnect_alert(tcp_host, tcp_port, "Socket mort après stabilisation")
                                self._tcp_reconnection_in_progress = False
                                return
                        
                        # Configurer le callback SEULEMENT après stabilisation réussie
                        if hasattr(new_interface, 'set_dead_socket_callback'):
                            debug_print("🔌 Configuration callback reconnexion sur nouvelle interface...")
                            new_interface.set_dead_socket_callback(self._reconnect_tcp_interface)
                        
                        # Mettre à jour les références
                        debug_print("🔄 Mise à jour références interface...")
                        self.interface = new_interface
                        self.node_manager.interface = self.interface
                        self.remote_nodes_client.interface = self.interface
                        if self.mesh_traceroute:
                            self.mesh_traceroute.interface = self.interface
                        
                        # CRITIQUE: Mettre à jour MessageHandler et MessageSender
                        # Sans cette mise à jour, les réponses sont envoyées vers l'ancienne
                        # interface morte et silencieusement ignorées
                        if self.message_handler:
                            self.message_handler.interface = self.interface
                            self.message_handler.router.interface = self.interface
                            self.message_handler.router.sender.interface_provider = self.interface
                            debug_print("✅ MessageHandler/Sender interfaces mises à jour")
                        
                        # NOTE: PAS de réabonnement ici ! L'abonnement initial à pub.subscribe()
                        # est déjà actif et fonctionne automatiquement avec la nouvelle interface.
                        # Réabonner causerait des duplications de messages et des freezes.
                        # Le système pubsub de Meshtastic route les messages de TOUTES les interfaces
                        # vers les callbacks enregistrés - pas besoin de re-subscribe.
                        debug_print("ℹ️ Pas de réabonnement nécessaire (pubsub global)")
                        
                        # Réinitialiser le timer de dernière réception pour permettre 
                        # au health monitor de détecter si la nouvelle interface fonctionne
                        self._last_packet_time = time.time()
                        debug_print("⏱️ Timer dernier paquet réinitialisé")
                        
                        # Reset backoff counter on successful reconnection
                        self._tcp_reconnection_attempts = 0
                        
                        # DEFERRED: Schedule public key sync after interface is fully stable
                        # Accessing interface.nodes immediately after reconnection can hang/block
                        # because the interface needs time to fully initialize its internal state.
                        # We defer this operation to run in background after TCP_PUBKEY_SYNC_DELAY.
                        # 
                        # OPTION: Can be disabled via TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT to rely
                        # entirely on periodic sync (every PUBKEY_SYNC_INTERVAL) if sync causes TCP disconnections.
                        if self.node_manager and not self.TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT:
                            info_print(f"🔑 Synchronisation clés publiques programmée dans {self.TCP_PUBKEY_SYNC_DELAY}s...")
                            
                            # Capture the interface reference at scheduling time to avoid race conditions
                            interface_ref = new_interface
                            
                            def deferred_pubkey_sync():
                                """Sync public keys after delay to avoid blocking reconnection"""
                                try:
                                    time.sleep(self.TCP_PUBKEY_SYNC_DELAY)
                                    
                                    # Check if interface is still valid and hasn't been replaced
                                    if interface_ref != self.interface:
                                        info_print("ℹ️ Interface changée pendant le délai, skip sync")
                                        return
                                    
                                    # Check if another reconnection is in progress
                                    if self._tcp_reconnection_in_progress:
                                        info_print("ℹ️ Reconnexion en cours, skip sync différé")
                                        return
                                    
                                    info_print("🔑 Démarrage synchronisation clés publiques différée...")
                                    injected = self.node_manager.sync_pubkeys_to_interface(interface_ref, force=True)
                                    if injected > 0:
                                        info_print(f"✅ {injected} clés publiques re-synchronisées")
                                    else:
                                        info_print("ℹ️ Aucune clé à re-synchroniser (aucune clé dans node_names.json)")
                                except Exception as sync_error:
                                    error_print(f"⚠️ Erreur re-sync clés après reconnexion: {sync_error}")
                                    error_print(traceback.format_exc())
                            
                            # Launch in daemon thread so it doesn't block shutdown
                            pubkey_thread = threading.Thread(
                                target=deferred_pubkey_sync,
                                daemon=True,
                                name="TCP-PubkeySync"
                            )
                            pubkey_thread.start()
                        elif self.TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT:
                            info_print("ℹ️ Synchronisation clés publiques skippée (TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT=True)")
                            info_print(f"   Prochaine sync au prochain cycle périodique ({PUBKEY_SYNC_INTERVAL//60}min)")
                        
                        # Reset session statistics for new connection
                        self._packets_this_session = 0
                        self._session_start_time = time.time()
                        self._packet_timestamps.clear()
                        debug_print("📊 Statistiques session réinitialisées")
                        
                        info_print("✅ Reconnexion TCP réussie (background)")
                        self._tcp_reconnection_in_progress = False
                        return  # Success - exit loop
                        
                    except Exception as e:
                        if retry < MAX_RETRIES - 1:
                            error_print(f"❌ Erreur reconnexion tentative {retry + 1}: {e}")
                            time.sleep(retry_delays[retry])
                        else:
                            error_print(f"❌ Échec reconnexion TCP après {MAX_RETRIES} tentatives: {e}")
                            error_print(traceback.format_exc())
                            # Envoyer alerte Telegram
                            self._send_tcp_disconnect_alert(tcp_host, tcp_port, str(e))
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
                if self._is_tcp_mode():
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

                # Nettoyage des anciennes données SQLite
                # Utilise NEIGHBOR_RETENTION_HOURS pour les voisins (config.py)
                retention_hours = globals().get('NEIGHBOR_RETENTION_HOURS', 48)
                self.traffic_monitor.cleanup_old_persisted_data(hours=retention_hours)

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

    def _get_packet_reception_rate(self, window_seconds=60):
        """
        Calculate packet reception rate over specified time window.
        
        Args:
            window_seconds: Time window in seconds (default: 60)
            
        Returns:
            float: Packets per minute, or None if insufficient data
        """
        if len(self._packet_timestamps) < 2:
            return None
            
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # Count packets in window
        recent_packets = [ts for ts in self._packet_timestamps if ts >= cutoff_time]
        
        if len(recent_packets) < 2:
            return None
            
        # Calculate rate (packets per minute)
        time_span = recent_packets[-1] - recent_packets[0]
        if time_span > 0:
            return (len(recent_packets) / time_span) * 60
        return None
    
    def _get_session_stats(self):
        """Get current TCP session statistics."""
        session_duration = time.time() - self._session_start_time
        if session_duration > 0:
            session_rate = (self._packets_this_session / session_duration) * 60
        else:
            session_rate = 0
        
        return {
            'packets': self._packets_this_session,
            'duration': session_duration,
            'rate': session_rate
        }

    def tcp_health_monitor_thread(self):
        """
        Thread de surveillance santé TCP (RAPIDE)
        
        Ce thread vérifie fréquemment (toutes les 30s) si:
        1. L'interface TCP est toujours connectée
        2. Des paquets sont reçus régulièrement
        
        Si aucun paquet n'est reçu depuis TCP_SILENT_TIMEOUT (120s),
        on force une reconnexion car l'interface est probablement morte
        même si le socket semble "vivant".
        
        C'est une protection contre les cas où:
        - Le thread __reader de meshtastic a crashé silencieusement
        - Le socket est half-open (TCP keepalive ne suffit pas)
        - Le nœud distant a redémarré sans fermer proprement
        """
        # Délai initial pour laisser le système démarrer
        time.sleep(self.TCP_HEALTH_MONITOR_INITIAL_DELAY)
        
        info_print(f"🔍 Moniteur santé TCP démarré (intervalle: {self.TCP_HEALTH_CHECK_INTERVAL}s, silence max: {self.TCP_SILENT_TIMEOUT}s)")
        
        while self.running:
            try:
                time.sleep(self.TCP_HEALTH_CHECK_INTERVAL)
                
                if not self.running:
                    break
                
                # Ne vérifier qu'en mode TCP (utiliser helper method)
                if not self._is_tcp_mode():
                    continue
                
                # Ne pas vérifier si reconnexion en cours
                if self._tcp_reconnection_in_progress:
                    debug_print("🔍 Health check: reconnexion en cours, skip")
                    continue
                
                # Vérifier le temps depuis le dernier paquet
                silence_duration = time.time() - self._last_packet_time
                
                if silence_duration > self.TCP_SILENT_TIMEOUT:
                    # Aucun paquet reçu depuis trop longtemps!
                    # L'interface est probablement morte
                    
                    # Get session stats for diagnostics
                    session_stats = self._get_session_stats()
                    
                    info_print(f"⚠️ SILENCE TCP: {silence_duration:.0f}s sans paquet (max: {self.TCP_SILENT_TIMEOUT}s)")
                    info_print(f"📊 Session stats: {session_stats['packets']} paquets en {session_stats['duration']:.0f}s ({session_stats['rate']:.1f} pkt/min)")
                    info_print("🔄 Forçage reconnexion TCP (silence détecté)...")
                    
                    # Forcer la reconnexion
                    self._reconnect_tcp_interface()
                    
                    # Réinitialiser le timer pour éviter les reconnexions en boucle
                    self._last_packet_time = time.time()
                else:
                    # Tout va bien - log rate for diagnostics
                    rate_1min = self._get_packet_reception_rate(60)
                    if rate_1min is not None:
                        debug_print(f"✅ Health TCP OK: dernier paquet il y a {silence_duration:.0f}s (débit: {rate_1min:.1f} pkt/min)")
                    else:
                        debug_print(f"✅ Health TCP OK: dernier paquet il y a {silence_duration:.0f}s")
                
            except Exception as e:
                error_print(f"Erreur thread health TCP: {e}")
                import traceback
                error_print(traceback.format_exc())

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
        
        # Synchroniser les clés publiques périodiquement (selon PUBKEY_SYNC_INTERVAL)
        # Sert de filet de sécurité en cas d'échec de sync immédiate ou corruption
        # Avec la logique intelligente, skip automatiquement si toutes les clés sont déjà présentes
        # Peut être désactivé via PUBKEY_SYNC_ENABLE pour tests
        if PUBKEY_SYNC_ENABLE and self.interface and self.node_manager:
            try:
                current_time = time.time()
                time_since_last_sync = current_time - self._last_pubkey_sync_time
                
                # Vérifier si assez de temps s'est écoulé depuis la dernière sync
                if time_since_last_sync >= PUBKEY_SYNC_INTERVAL:
                    injected = self.node_manager.sync_pubkeys_to_interface(self.interface, force=False)
                    if injected > 0:
                        debug_print(f"🔑 Synchronisation périodique: {injected} clés publiques mises à jour")
                    # Mettre à jour le timestamp de dernière sync
                    self._last_pubkey_sync_time = current_time
                    # Note: Si injected == 0, la méthode aura déjà loggé le skip en mode debug
                else:
                    debug_print(f"⏭️ Skip sync clés publiques: dernière sync il y a {time_since_last_sync:.0f}s (intervalle: {PUBKEY_SYNC_INTERVAL}s)")
            except Exception as e:
                debug_print(f"⚠️ Erreur sync périodique clés: {e}")
        elif not PUBKEY_SYNC_ENABLE:
            debug_print("⏭️ Sync clés publiques désactivée (PUBKEY_SYNC_ENABLE=False)")

        gc.collect()

    def _send_telemetry_packet(self, telemetry_data, packet_type):
        """
        Envoyer un paquet de télémétrie avec gestion robuste des erreurs réseau
        
        Args:
            telemetry_data: Données de télémétrie (protobuf Telemetry)
            packet_type: Type de paquet pour les logs ("environment_metrics", "device_metrics", ou "power_metrics")
        
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
        
        IMPORTANT: Meshtastic telemetry uses a 'oneof' field, so environment_metrics,
        device_metrics, and power_metrics must be sent in SEPARATE packets to comply
        with the TELEMETRY standard. This ensures all data is visible in node details.
        
        Sends up to 3 packets:
        1. Environment metrics (temperature, pressure, humidity)
        2. Device metrics (battery voltage, battery level percentage)
        3. Power metrics (ch1_voltage, ch1_current for detailed power monitoring)
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
                # La pression est en hPa (hectopascals) comme attendu par Meshtastic
                env_telemetry.environment_metrics.barometric_pressure = sensor_values['pressure']
                has_env_data = True
                debug_print(f"📊 pressure: {sensor_values['pressure']}")
            
            if sensor_values.get('humidity') is not None:
                env_telemetry.environment_metrics.relative_humidity = sensor_values['humidity']
                has_env_data = True
                debug_print(f"📊 humidity: {sensor_values['humidity']}")
            
            if has_env_data:
                info_print(f"📊 Télémétrie Env - Température: {sensor_values.get('temperature', 'N/A')}°C")
                info_print(f"📊 Télémétrie Env - Pression: {sensor_values.get('pressure', 0):.1f} hPa")
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
                    # Small delay between packets
                    time.sleep(0.5)
            
            # ===== PACKET 3: Power Metrics =====
            # Send detailed power data (voltage + current) for power monitoring
            has_power_data = False
            power_telemetry = telemetry_pb2.Telemetry()
            power_telemetry.time = current_time
            
            if sensor_values.get('battery_voltage') is not None or sensor_values.get('battery_current') is not None:
                # Use channel 1 for battery monitoring
                if sensor_values.get('battery_voltage') is not None:
                    power_telemetry.power_metrics.ch1_voltage = sensor_values['battery_voltage']
                    has_power_data = True
                    debug_print(f"📊 ch1_voltage: {sensor_values['battery_voltage']}")
                
                if sensor_values.get('battery_current') is not None:
                    power_telemetry.power_metrics.ch1_current = int(sensor_values['battery_current']*100)
                    has_power_data = True
                    debug_print(f"📊 ch1_current: {sensor_values['battery_current']}")
            
            if has_power_data:
                voltage_str = f"{sensor_values.get('battery_voltage', 'N/A'):.1f}V" if sensor_values.get('battery_voltage') is not None else "N/A"
                current_str = f"{sensor_values.get('battery_current', 'N/A'):.3f}A" if sensor_values.get('battery_current') is not None else "N/A"
                info_print(f"📊 Télémétrie Power - Batterie: {voltage_str} @ {current_str}")
                
                if self._send_telemetry_packet(power_telemetry, "power_metrics"):
                    packets_sent += 1
            
            if packets_sent == 0:
                debug_print("⚠️ Aucune donnée à envoyer en télémétrie")
            else:
                info_print(f"✅ Télémétrie ESPHome complète: {packets_sent} paquet(s) envoyé(s)")
                # Store the telemetry data in the database for this node
                self._store_sent_telemetry(sensor_values, battery_level if has_device_data else None)
            
        except Exception as e:
            # Erreur non-réseau (ex: problème protobuf, ESPHome indisponible)
            error_print(f"❌ Erreur préparation télémétrie ESPHome: {e}")
            error_print(traceback.format_exc())
    
    def _store_sent_telemetry(self, sensor_values, battery_level):
        """
        Store the telemetry data we just sent to the mesh in our local database.
        This ensures that our own node's telemetry appears in exports and maps.
        
        Args:
            sensor_values: Dictionary of sensor values from ESPHome
            battery_level: Calculated battery level percentage (0-100)
        """
        try:
            # Get our node ID
            my_node_id = getattr(self.interface.localNode, 'nodeNum', None)
            if not my_node_id:
                debug_print("⚠️ Cannot store telemetry: local node ID not available")
                return
            
            # Convert node ID to hex string format used in database
            node_id_hex = f"!{my_node_id:08x}"
            
            # Get or create stats for this node
            if hasattr(self, 'traffic_monitor') and self.traffic_monitor:
                # Use traffic_monitor's node_packet_stats structure
                if node_id_hex not in self.traffic_monitor.node_packet_stats:
                    self.traffic_monitor.node_packet_stats[node_id_hex] = {
                        'total_packets': 0,
                        'by_type': {},
                        'total_bytes': 0,
                        'first_seen': None,
                        'last_seen': None,
                        'hourly_activity': {},
                        'message_stats': {'count': 0, 'total_chars': 0, 'avg_length': 0},
                        'telemetry_stats': {'count': 0},
                        'position_stats': {'count': 0},
                        'routing_stats': {'count': 0, 'packets_relayed': 0, 'packets_originated': 0}
                    }
                
                # Update telemetry stats
                tel_stats = self.traffic_monitor.node_packet_stats[node_id_hex]['telemetry_stats']
                
                # Device metrics (battery)
                if battery_level is not None:
                    tel_stats['last_battery'] = battery_level
                if sensor_values.get('battery_voltage') is not None:
                    tel_stats['last_voltage'] = sensor_values['battery_voltage']
                
                # Environment metrics
                if sensor_values.get('temperature') is not None:
                    tel_stats['last_temperature'] = sensor_values['temperature']
                if sensor_values.get('humidity') is not None:
                    tel_stats['last_humidity'] = sensor_values['humidity']
                if sensor_values.get('pressure') is not None:
                    tel_stats['last_pressure'] = sensor_values['pressure']
                
                # Save to database
                self.traffic_monitor.persistence.save_node_stats(
                    {node_id_hex: self.traffic_monitor.node_packet_stats[node_id_hex]}
                )
                
                debug_print(f"💾 Télémétrie stockée en DB pour {node_id_hex}")
            else:
                debug_print("⚠️ TrafficMonitor not available, cannot store telemetry")
                
        except Exception as e:
            error_print(f"❌ Erreur stockage télémétrie en DB: {e}")
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
    
    def _init_db_error_monitor(self):
        """
        Initialise le moniteur d'erreurs de base de données avec auto-reboot.
        """
        try:
            # Récupérer la configuration
            enabled = globals().get('DB_AUTO_REBOOT_ENABLED', True)
            window_seconds = globals().get('DB_AUTO_REBOOT_WINDOW_SECONDS', 300)
            error_threshold = globals().get('DB_AUTO_REBOOT_ERROR_THRESHOLD', 10)
            
            if not enabled:
                debug_print("ℹ️ Moniteur d'erreurs DB désactivé (DB_AUTO_REBOOT_ENABLED=False)")
                return
            
            # Créer le callback de reboot
            def reboot_callback():
                """Callback pour déclencher le reboot de l'application."""
                try:
                    requester_info = {
                        'name': 'DBErrorMonitor',
                        'node_id': '0xDB_ERROR',
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    return RebootSemaphore.signal_reboot(requester_info)
                except Exception as e:
                    error_print(f"❌ Erreur callback reboot: {e}")
                    return False
            
            # Initialiser le moniteur
            self.db_error_monitor = DBErrorMonitor(
                window_seconds=window_seconds,
                error_threshold=error_threshold,
                enabled=enabled,
                reboot_callback=reboot_callback
            )
            
            info_print("✅ Moniteur d'erreurs DB initialisé avec auto-reboot")
            
        except Exception as e:
            error_print(f"❌ Erreur initialisation moniteur DB: {e}")
            error_print(traceback.format_exc())
            self.db_error_monitor = None
    
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
                auto_reboot = globals().get('TCP_AUTO_REBOOT_ON_FAILURE', True)
                reboot_wait_time = globals().get('TCP_REBOOT_WAIT_TIME', 45)
                
                info_print(f"🌐 Mode TCP: Connexion à {tcp_host}:{tcp_port}")
                
                # Tenter la connexion avec gestion d'erreurs et auto-reboot
                max_connection_attempts = 2  # Tentative initiale + 1 retry après reboot
                connection_successful = False
                
                for attempt in range(max_connection_attempts):
                    try:
                        # Utiliser OptimizedTCPInterface pour économiser CPU
                        info_print(f"🔧 Initialisation OptimizedTCPInterface pour {tcp_host}:{tcp_port}")
                        self.interface = OptimizedTCPInterface(
                            hostname=tcp_host,
                            portNumber=tcp_port
                        )
                        info_print("✅ Interface TCP créée")
                        connection_successful = True
                        break  # Connexion réussie, sortir de la boucle
                        
                    except OSError as e:
                        # Erreurs réseau courantes
                        error_print(f"❌ Erreur connexion TCP (tentative {attempt + 1}/{max_connection_attempts}): {e}")
                        
                        # Si c'est la première tentative ET que auto-reboot est activé
                        if attempt == 0 and auto_reboot:
                            import errno
                            # Erreurs qui justifient un reboot:
                            # - EHOSTUNREACH (113): No route to host
                            # - ETIMEDOUT (110): Connection timed out
                            # - ECONNREFUSED (111): Connection refused
                            # - ENETUNREACH (101): Network is unreachable
                            reboot_worthy_errors = (
                                errno.EHOSTUNREACH,  # 113
                                errno.ETIMEDOUT,     # 110
                                errno.ECONNREFUSED,  # 111
                                errno.ENETUNREACH,   # 101
                            )
                            
                            if hasattr(e, 'errno') and e.errno in reboot_worthy_errors:
                                info_print(f"🔄 Erreur réseau détectée (errno {e.errno})")
                                info_print(f"   → Tentative de redémarrage automatique du nœud...")
                                
                                # Tenter de redémarrer le nœud distant
                                if self._reboot_remote_node(tcp_host):
                                    info_print(f"⏳ Attente de {reboot_wait_time}s pour le redémarrage du nœud...")
                                    time.sleep(reboot_wait_time)
                                    info_print("🔄 Nouvelle tentative de connexion après reboot...")
                                    # La boucle continuera et retentera la connexion
                                else:
                                    error_print("❌ Échec du reboot automatique")
                                    break  # Pas de retry si le reboot a échoué
                            else:
                                # Autre erreur OSError, pas de retry
                                error_print(f"   Erreur non récupérable (errno {getattr(e, 'errno', 'unknown')})")
                                break
                        else:
                            # Deuxième tentative ou auto-reboot désactivé
                            if not auto_reboot:
                                error_print("   Auto-reboot désactivé (TCP_AUTO_REBOOT_ON_FAILURE=False)")
                            break  # Sortir de la boucle
                    
                    except Exception as e:
                        # Autres exceptions (non-OSError)
                        error_print(f"❌ Erreur inattendue lors de la connexion TCP: {e}")
                        error_print(traceback.format_exc())
                        break  # Pas de retry pour exceptions inattendues
                
                # Vérifier si la connexion a finalement réussi
                if not connection_successful:
                    error_print("❌ Impossible de se connecter au nœud TCP")
                    error_print("   Le bot ne peut pas démarrer sans connexion Meshtastic")
                    return False
                
                # Configurer le callback pour reconnexion immédiate quand le socket meurt
                # Cela permet de ne pas attendre le health monitor (120 secondes)
                # IMPORTANT: Utilise la méthode d'instance, pas de classe!
                # Ceci garantit que seule l'interface principale déclenche la reconnexion,
                # pas les connexions temporaires (SafeTCPConnection/RemoteNodesClient)
                # Note: Cette méthode est optionnelle, le health monitor gère aussi les morts
                if hasattr(self.interface, 'set_dead_socket_callback'):
                    self.interface.set_dead_socket_callback(self._reconnect_tcp_interface)
                
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
            # SYNCHRONISATION DES CLÉS PUBLIQUES
            # ========================================
            # Inject public keys from node_names.json into interface.nodes
            # This is critical for DM decryption in TCP mode where interface.nodes
            # starts empty. We restore keys from our persistent database without
            # violating ESP32 single-connection limitation.
            try:
                info_print("🔑 Synchronisation des clés publiques vers interface.nodes...")
                injected = self.node_manager.sync_pubkeys_to_interface(self.interface, force=True)
                if injected > 0:
                    info_print(f"✅ {injected} clés publiques restaurées pour déchiffrement DM")
                else:
                    info_print("ℹ️  Aucune clé publique à synchroniser (collection continue)")
            except Exception as e:
                error_print(f"⚠️  Erreur synchronisation clés publiques: {e}")
                error_print(traceback.format_exc())
                info_print("   → Déchiffrement DM limité jusqu'à réception NODEINFO")
            
            # Set interface reference in node_manager for get_node_name() calls
            self.node_manager.set_interface(self.interface)
            
            # ========================================
            # CHARGEMENT INITIAL DES VOISINS
            # ========================================
            # Populate neighbor database from interface at startup
            # This provides an initial complete view of the network topology
            # Passive collection will continue via NEIGHBORINFO_APP packets
            try:
                total_neighbors = self.traffic_monitor.populate_neighbors_from_interface(self.interface)
                if total_neighbors > 0:
                    info_print(f"👥 Base de voisinage initialisée avec {total_neighbors} relations")
                else:
                    info_print("ℹ️  Aucun voisin trouvé au démarrage (collection continue en tâche de fond)")
            except Exception as e:
                error_print(f"⚠️  Erreur lors du chargement initial des voisins: {e}")
                info_print("   → Collection continue via NEIGHBORINFO_APP packets")
            
            # ========================================
            # ABONNEMENT AUX MESSAGES (CRITIQUE!)
            # ========================================
            # DOIT être fait immédiatement après la création de l'interface
            # S'abonner aux différents types de messages Meshtastic
            # - meshtastic.receive.text : messages texte (TEXT_MESSAGE_APP)
            # - meshtastic.receive.data : messages de données
            # - meshtastic.receive : messages génériques (fallback)
            
            # S'abonner avec le callback principal
            # NOTE: Seulement "meshtastic.receive" pour éviter les duplications
            # (ce topic catch ALL messages: text, data, position, etc.)
            pub.subscribe(self.on_message, "meshtastic.receive")
            
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

            # Initialiser le collecteur MQTT de voisins (si activé)
            if globals().get('MQTT_NEIGHBOR_ENABLED', False):
                try:
                    info_print("👥 Initialisation du collecteur MQTT de voisins...")
                    
                    mqtt_server = globals().get('MQTT_NEIGHBOR_SERVER', 'serveurperso.com')
                    mqtt_port = globals().get('MQTT_NEIGHBOR_PORT', 1883)
                    mqtt_user = globals().get('MQTT_NEIGHBOR_USER')
                    mqtt_password = globals().get('MQTT_NEIGHBOR_PASSWORD')
                    mqtt_topic_root = globals().get('MQTT_NEIGHBOR_TOPIC_ROOT', 'msh')
                    mqtt_topic_pattern = globals().get('MQTT_NEIGHBOR_TOPIC_PATTERN')
                    
                    self.mqtt_neighbor_collector = MQTTNeighborCollector(
                        mqtt_server=mqtt_server,
                        mqtt_port=mqtt_port,
                        mqtt_user=mqtt_user,
                        mqtt_password=mqtt_password,
                        mqtt_topic_root=mqtt_topic_root,
                        mqtt_topic_pattern=mqtt_topic_pattern,
                        persistence=self.traffic_monitor.persistence,
                        node_manager=self.node_manager
                    )
                    
                    if self.mqtt_neighbor_collector.enabled:
                        info_print("✅ Collecteur MQTT de voisins initialisé")
                    else:
                        info_print("⚠️ Collecteur MQTT de voisins désactivé (erreur config)")
                except Exception as e:
                    error_print(f"Erreur initialisation MQTT neighbor collector: {e}")
                    error_print(traceback.format_exc())
                    self.mqtt_neighbor_collector = None
            else:
                debug_print("ℹ️ Collecteur MQTT de voisins désactivé (MQTT_NEIGHBOR_ENABLED=False)")

            # ========================================
            # SYNCHRONISATION CLÉS PKI
            # ========================================
            # Public keys are automatically synced from node_names.json to interface.nodes
            # This happens at startup (see line ~1401) and periodically (see periodic_cleanup ~line 957)
            # No separate KeySyncManager needed - NodeManager.sync_pubkeys_to_interface() handles it
            debug_print("ℹ️ Synchronisation clés PKI: Gérée par NodeManager.sync_pubkeys_to_interface()")

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
                broadcast_tracker=self._track_broadcast,  # Callback pour tracker les broadcasts
                mqtt_neighbor_collector=self.mqtt_neighbor_collector  # MQTT collector reference
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

                # Démarrer le collecteur MQTT de voisins (si activé)
                if self.mqtt_neighbor_collector and self.mqtt_neighbor_collector.enabled:
                    self.mqtt_neighbor_collector.start_monitoring()
                    info_print("👥 Collecteur MQTT de voisins démarré")

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
            
            # ========================================
            # THREAD MONITEUR SANTÉ TCP (RAPIDE)
            # ========================================
            # Ce thread vérifie fréquemment si l'interface TCP reçoit des paquets
            # Si silence > 120s, force une reconnexion (plus rapide que le health check normal)
            if self._is_tcp_mode():
                self._tcp_health_thread = threading.Thread(
                    target=self.tcp_health_monitor_thread,
                    daemon=True,
                    name="TCPHealthMonitor"
                )
                self._tcp_health_thread.start()
                info_print(f"🔍 Moniteur santé TCP démarré (check: {self.TCP_HEALTH_CHECK_INTERVAL}s, silence max: {self.TCP_SILENT_TIMEOUT}s)")
            
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
            
            # 3b. Arrêter le collecteur MQTT de voisins
            try:
                if self.mqtt_neighbor_collector and self.mqtt_neighbor_collector.enabled:
                    self.mqtt_neighbor_collector.stop_monitoring()
            except Exception as e:
                error_print(f"⚠️ Erreur arrêt mqtt_neighbor_collector: {e}")

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

