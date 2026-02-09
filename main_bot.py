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
import serial
import serial.serialutil
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
from mesh_alert_manager import MeshAlertManager

# Import du nouveau gestionnaire multi-plateforme
from platforms import PlatformManager
from platforms.telegram_platform import TelegramPlatform
from platforms.cli_server_platform import CLIServerPlatform
from platform_config import get_enabled_platforms

# Import du gestionnaire dual interface (Meshtastic + MeshCore simultanément)
from dual_interface_manager import DualInterfaceManager, NetworkSource

# Import du détecteur de ports USB automatique
from usb_port_detector import USBPortDetector

# Import de l'interface MeshCore (mode companion)
# Tente d'utiliser meshcore-cli library si disponible, sinon fallback vers impl basique
try:
    from meshcore_cli_wrapper import MeshCoreCLIWrapper as MeshCoreSerialInterface
    from meshcore_serial_interface import MeshCoreStandaloneInterface
    info_print_mc("=" * 80)
    info_print_mc("✅ MESHCORE: Using meshcore-cli library (FULL SUPPORT)")
    info_print_mc("=" * 80)
    info_print_mc("   ✅ Binary protocol supported")
    info_print_mc("   ✅ DM messages will be logged with [DEBUG][MC]")
    info_print_mc("   ✅ Complete MeshCore API available")
    info_print_mc("=" * 80)
    MESHCORE_FULL_SUPPORT = True
except ImportError:
    from meshcore_serial_interface import MeshCoreSerialInterface, MeshCoreStandaloneInterface
    info_print_mc("=" * 80)
    info_print_mc("⚠️  MESHCORE: Using BASIC implementation (LIMITED)")
    info_print_mc("=" * 80)
    info_print_mc("   ❌ Binary protocol NOT supported")
    info_print_mc("   ❌ DM messages will NOT be logged or processed")
    info_print_mc("   ❌ Only text format DM:<sender_id>:<message> supported")
    info_print_mc("")
    info_print_mc("   📋 SYMPTOM: No logs when sending DM to MeshCore")
    info_print_mc("   🔧 SOLUTION: Install meshcore-cli library")
    info_print_mc("      $ pip install meshcore meshcoredecoder")
    info_print_mc("      $ sudo systemctl restart meshtastic-bot")
    info_print_mc("=" * 80)
    MESHCORE_FULL_SUPPORT = False

def _create_serial_interface_with_timeout(serial_port, timeout=10):
    """
    Create Meshtastic SerialInterface with timeout to prevent freeze.
    
    The SerialInterface constructor can block indefinitely if the device
    doesn't respond properly (waiting for node info, syncing state, etc.).
    This wrapper adds a timeout mechanism using threading.
    
    Args:
        serial_port: Serial port path (e.g., /dev/ttyACM0)
        timeout: Maximum seconds to wait (default: 10)
    
    Returns:
        SerialInterface object if successful, None if timeout
    """
    result = {'interface': None, 'error': None}
    
    def create_interface():
        try:
            result['interface'] = meshtastic.serial_interface.SerialInterface(serial_port)
        except Exception as e:
            result['error'] = e
    
    thread = threading.Thread(target=create_interface, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        # Thread still running = timeout occurred
        error_print("=" * 80)
        error_print(f"⏱️  TIMEOUT: Meshtastic SerialInterface creation exceeded {timeout}s")
        error_print("=" * 80)
        error_print(f"   Port: {serial_port}")
        error_print("   → Device detected but not responding")
        error_print("   → May be in wrong state, bootloader mode, or hung")
        error_print("")
        error_print("   💡 SOLUTIONS:")
        error_print("      1. Power cycle the device (unplug power)")
        error_print("      2. Unplug and replug USB cable")
        error_print("      3. Press reset button on device")
        error_print("      4. Check device is not in bootloader mode")
        error_print("=" * 80)
        return None
    
    if result['error']:
        raise result['error']
    
    return result['interface']


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
        
        # Dual interface manager for Meshtastic + MeshCore simultaneous connection
        # Only used when DUAL_NETWORK_MODE = True
        self.dual_interface = None
        self._dual_mode_active = False
        
        # === STARTUP DIAGNOSTIC LOGS ===
        # These logs appear IMMEDIATELY on bot startup, confirming new code is deployed
        info_print("=" * 80)
        info_print("🚀 MESHBOT STARTUP")
        info_print("=" * 80)
        info_print(f"📅 Startup time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Log git commit info if available
        try:
            import subprocess
            git_commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], 
                                                stderr=subprocess.DEVNULL).decode().strip()
            info_print(f"📦 Git commit: {git_commit}")
        except:
            info_print("📦 Git commit: Unable to determine")
        
        # Log DEBUG_MODE status
        debug_mode_status = "ENABLED ✅" if DEBUG_MODE else "DISABLED ❌"
        info_print(f"🔍 DEBUG_MODE: {debug_mode_status}")
        
        # Removed SOURCE-DEBUG logging as requested
        
        info_print("=" * 80)
        # === END STARTUP DIAGNOSTIC LOGS ===
        
        # Load TCP configuration from config if available
        import config as cfg
        
        # TCP silent timeout - max time without packets before reconnection
        self.TCP_SILENT_TIMEOUT = getattr(cfg, 'TCP_SILENT_TIMEOUT', 120)
        debug_print(f"🔧 TCP_SILENT_TIMEOUT configuré: {self.TCP_SILENT_TIMEOUT}s")
        
        # TCP health check interval - frequency of health checks
        self.TCP_HEALTH_CHECK_INTERVAL = getattr(cfg, 'TCP_HEALTH_CHECK_INTERVAL', 30)
        debug_print(f"🔧 TCP_HEALTH_CHECK_INTERVAL configuré: {self.TCP_HEALTH_CHECK_INTERVAL}s")
        
        # TCP force reconnect interval - scheduled reconnection (0 = disabled)
        self.TCP_FORCE_RECONNECT_INTERVAL = getattr(cfg, 'TCP_FORCE_RECONNECT_INTERVAL', 0)
        if self.TCP_FORCE_RECONNECT_INTERVAL > 0:
            info_print(f"🔧 TCP_FORCE_RECONNECT_INTERVAL configuré: {self.TCP_FORCE_RECONNECT_INTERVAL}s (reconnexion programmée activée)")
        else:
            debug_print("🔧 TCP_FORCE_RECONNECT_INTERVAL: désactivé (0)")
        
        # Validate TCP configuration to avoid false alarms
        self._validate_tcp_health_config()
        
        # Moniteur d'erreurs DB (initialisé avant TrafficMonitor pour callback)
        self.db_error_monitor = None
        self._init_db_error_monitor()
        
        # Initialisation des gestionnaires
        self.node_manager = NodeManager(self.interface)
        self.context_manager = ContextManager(self.node_manager)
        self.llama_client = LlamaClient(self.context_manager)
        self.esphome_client = ESPHomeClient()
        self.traffic_monitor = TrafficMonitor(self.node_manager)
        self.remote_nodes_client = RemoteNodesClient(persistence=self.traffic_monitor.persistence)
        self.remote_nodes_client.set_node_manager(self.node_manager)
        
        # Connect node_manager to persistence for SQLite storage
        self.node_manager.persistence = self.traffic_monitor.persistence
        debug_print("✅ NodeManager connected to SQLite persistence")
        
        # Load nodes from SQLite database
        self.node_manager.load_nodes_from_sqlite()
        
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
                    alert_levels=globals().get('VIGILANCE_ALERT_LEVELS', ['Orange', 'Rouge']),
                    mesh_alert_manager=None  # Sera mis à jour dans start() après init
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
        self._last_packet_count = 0  # Track if packets are still arriving
        self._last_packet_time = time.time()  # When last packet arrived
        
        # Scheduled reconnection tracking (for TCP_FORCE_RECONNECT_INTERVAL)
        self._last_forced_reconnect = time.time()  # Track last scheduled reconnection
        
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

    def _validate_tcp_health_config(self):
        """
        Validate TCP health check configuration to prevent false alarms.
        
        The health check monitors silence duration with this logic:
            if (time.time() - last_packet_time) > TCP_SILENT_TIMEOUT:
                # Trigger reconnection
        
        Problem: Checks run at fixed intervals, but packets arrive at random times.
        
        Worst-case scenario:
        - Packet arrives at T+0.1s (just after a check at T+0)
        - Timeout set to 90s
        - Checks at: T+15, T+30, T+45, T+60, T+75, T+90, T+105...
        - At T+90: silence=89.9s, 89.9>90 is FALSE → OK
        - At T+105: silence=104.9s, 104.9>90 is TRUE → FALSE ALARM!
        
        The timeout triggered 14.9s "late" because the check interval is 15s.
        
        Safe configuration requires avoiding this off-by-one-interval issue:
        1. TIMEOUT should allow the check that occurs at floor(TIMEOUT/INTERVAL)×INTERVAL to pass
        2. This means we need: floor(TIMEOUT/INTERVAL)×INTERVAL ≤ TIMEOUT (always true)
        3. But next check at [floor(TIMEOUT/INTERVAL)+1]×INTERVAL should fail
        4. For clean detection: TIMEOUT + INTERVAL should be > TIMEOUT (obviously true)
        
        The issue occurs when TIMEOUT is "close to" but not exactly at a multiple of INTERVAL.
        
        Pragmatic rule: TIMEOUT should either be:
        - A clean multiple of INTERVAL (e.g., 90s with 15s → 6×15=90s)
        - OR have at least 0.5×INTERVAL margin above a multiple
        
        Example:
        - INTERVAL=15s, TIMEOUT=90s: 90/15=6.0 → at boundary, will trigger at 105s (15s late)
        - INTERVAL=15s, TIMEOUT=98s: 98/15=6.5 → safe margin, will trigger at 105s (7s late)
        - INTERVAL=15s, TIMEOUT=105s: 105/15=7.0 → at boundary, will trigger at 120s (15s late)
        - INTERVAL=15s, TIMEOUT=112s: 112/15=7.5 → safe margin, will trigger at 120s (8s late)
        
        Recommendation: TIMEOUT ≥ (floor(DESIRED_TIMEOUT/INTERVAL) + 0.5) × INTERVAL
        Or simpler: Add 0.5×INTERVAL as safety margin to your desired timeout.
        """
        # Configuration validation constants
        FRACTIONAL_RATIO_THRESHOLD = 0.3  # Threshold for "close to integer" detection
        FAST_INTERVAL_THRESHOLD = 20      # seconds - intervals below this are considered "fast"
        MEDIUM_INTERVAL_THRESHOLD = 30    # seconds - intervals below this are considered "medium"
        
        interval = self.TCP_HEALTH_CHECK_INTERVAL
        timeout = self.TCP_SILENT_TIMEOUT
        
        if interval <= 0 or timeout <= 0:
            return  # Invalid config, will fail elsewhere
        
        # Calculate the ratio and check if it's too close to an integer
        ratio = timeout / interval
        ratio_fractional = ratio - int(ratio)
        
        # Calculate detection latency
        checks_before_timeout = int(ratio)
        detection_time = (checks_before_timeout + 1) * interval
        detection_latency = detection_time - timeout
        
        # Determine if configuration is risky:
        # - Fractional part close to 0 (< FRACTIONAL_RATIO_THRESHOLD) means integer ratio → full interval latency
        # - For small intervals (<FAST_INTERVAL_THRESHOLD), this latency is problematic
        # - For large intervals (≥MEDIUM_INTERVAL_THRESHOLD), we're more tolerant: latency should be < interval
        #
        # Example: 15s interval, 90s timeout → 6.0× ratio → 15s latency → RISKY
        # Example: 30s interval, 120s timeout → 4.0× ratio → 30s latency → OK (large interval)
        # Example: 60s interval, 240s timeout → 4.0× ratio → 60s latency → OK (large interval)
        
        if ratio_fractional < FRACTIONAL_RATIO_THRESHOLD:
            # Integer or near-integer ratio
            if interval < FAST_INTERVAL_THRESHOLD:
                # For fast checks (<20s), any full-interval latency is bad
                is_risky = True
            elif interval < MEDIUM_INTERVAL_THRESHOLD:
                # For medium checks (20-30s), latency should be < interval
                is_risky = detection_latency >= interval
            else:
                # For slow checks (≥30s), we're more tolerant
                # Latency is expected to be ~interval, which is acceptable
                is_risky = False
        else:
            # Fractional ratio is good (≥0.3), latency will be < full interval
            is_risky = False
        
        if is_risky:
            # Configuration will cause false alarms or very late detection
            error_print("=" * 80)
            error_print("⚠️  ATTENTION: CONFIGURATION TCP NON-OPTIMALE DÉTECTÉE")
            error_print("=" * 80)
            error_print(f"")
            error_print(f"Votre configuration actuelle peut causer des problèmes:")
            error_print(f"")
            error_print(f"  TCP_HEALTH_CHECK_INTERVAL = {interval}s")
            error_print(f"  TCP_SILENT_TIMEOUT        = {timeout}s")
            error_print(f"  Ratio: {ratio:.2f}× (fractional part: {ratio_fractional:.2f})")
            error_print(f"")
            error_print(f"Problème: Le timeout ({timeout}s) est trop proche d'un multiple")
            error_print(f"de l'intervalle ({checks_before_timeout}×{interval}s = {checks_before_timeout*interval}s).")
            error_print(f"")
            error_print(f"Impact: La détection du timeout sera retardée de ~{detection_latency:.0f}s")
            error_print(f"  • Timeout configuré: {timeout}s")
            error_print(f"  • Détection réelle:  {detection_time}s (au prochain check)")
            error_print(f"  • Retard:            {detection_latency:.0f}s")
            error_print(f"")
            
            # Show realistic timeline
            error_print(f"Exemple: Si paquet arrive juste après un check (T+0.1s):")
            packet_time = 0.1
            for i in range(1, checks_before_timeout + 3):
                check_time = i * interval
                silence = check_time - packet_time
                status = "OK" if silence <= timeout else "TIMEOUT"
                symbol = "✅" if silence <= timeout else "⚠️ "
                error_print(f"  T+{check_time:3d}s: check trouve {silence:5.1f}s silence → {symbol} {status}")
                if silence > timeout:
                    # Show additional context if latency is significantly high
                    SIGNIFICANT_LATENCY_THRESHOLD = 10  # seconds
                    if silence > timeout + SIGNIFICANT_LATENCY_THRESHOLD:
                        error_print(f"           Reconnexion {detection_latency:.0f}s après le timeout!")
                    break
            
            error_print(f"")
            error_print(f"Solutions recommandées:")
            error_print(f"")
            
            # Suggest adding margin
            suggested_timeout = int((checks_before_timeout + 0.6) * interval)
            error_print(f"  Option 1 (RECOMMANDÉE): Ajouter une marge de sécurité")
            error_print(f"    TCP_SILENT_TIMEOUT = {suggested_timeout}  # Ajoute ~{suggested_timeout-timeout}s de marge")
            
            # Suggest nicer round numbers
            nice_timeouts = [120, 150, 180, 240, 300]
            recommended = next((t for t in nice_timeouts if t >= suggested_timeout), suggested_timeout)
            if recommended > suggested_timeout:
                error_print(f"    TCP_SILENT_TIMEOUT = {recommended}  # Valeur arrondie (encore mieux)")
            
            error_print(f"")
            error_print(f"  Option 2: Réduire l'intervalle de vérification")
            # Aim for ~8 checks before timeout to provide good balance
            MIN_INTERVAL = 10  # Minimum practical check interval (seconds)
            TARGET_CHECKS_BEFORE_TIMEOUT = 8
            new_interval = max(MIN_INTERVAL, int(timeout / TARGET_CHECKS_BEFORE_TIMEOUT))
            error_print(f"    TCP_HEALTH_CHECK_INTERVAL = {new_interval}  # Détection plus fréquente")
            error_print(f"")
            error_print(f"  Option 3: Utiliser les valeurs par défaut")
            error_print(f"    TCP_HEALTH_CHECK_INTERVAL = 30")
            error_print(f"    TCP_SILENT_TIMEOUT = 120  # Ratio 4.0×, pas de retard excessif")
            error_print(f"")
            error_print("=" * 80)
            error_print("")
            
            # Don't crash, just warn
            info_print(f"⚠️  Le bot continuera, mais la détection de silence aura {detection_latency:.0f}s")
            info_print(f"    de retard, ce qui peut causer des reconnexions tardives ou fausses.")
        else:
            # Config is OK
            debug_print(f"✅ Configuration TCP validée: timeout {timeout}s (ratio {ratio:.2f}×, latence détection: ~{detection_latency:.0f}s)")

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

    def on_message(self, packet, interface=None, network_source=None):
        """
        Gestionnaire des messages reçus
        
        En mode single-node (CONNECTION_MODE):
        - Tous les paquets viennent de la même interface (serial OU tcp)
        - Tous les messages sont traités directement
        
        En mode dual (DUAL_NETWORK_MODE=True):
        - Les paquets peuvent venir de Meshtastic OU MeshCore
        - network_source indique l'origine (NetworkSource.MESHTASTIC ou NetworkSource.MESHCORE)
        - Les réponses sont routées vers le réseau source
        
        En mode legacy (multi-nodes):
        - Architecture en 3 phases pour distinguer serial/TCP
        - Filtrage selon PROCESS_TCP_COMMANDS
        
        Args:
            packet: Packet Meshtastic ou MeshCore reçu
            interface: Interface source (peut être None pour messages publiés à meshtastic.receive.text)
            network_source: NetworkSource enum (Meshtastic/MeshCore) si en mode dual
        """
        # Removed noisy diagnostic logging per user request
        
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
                return

            from_id = packet.get('from', 0)
            to_id = packet.get('to', 0)
            info_print(f"   → from_id: 0x{from_id:08x}")
            info_print(f"   → to_id: 0x{to_id:08x}")

            decoded = packet.get('decoded', {})
            info_print(f"🔍 [DECODED] Checking for TEXT_MESSAGE_APP")
            info_print(f"   → decoded exists: {bool(decoded)}")
            info_print(f"   → portnum: {decoded.get('portnum', 'MISSING') if decoded else 'NO DECODED'}")
            
            if decoded.get('portnum') == 'TEXT_MESSAGE_APP':
                payload = decoded.get('payload', b'')
                try:
                    msg = payload.decode('utf-8').strip()
                    info_print(f"📨 MESSAGE BRUT: '{msg}' | from=0x{from_id:08x} | to=0x{to_id:08x} | broadcast={to_id in [0xFFFFFFFF, 0]}")
                except:
                    pass
            else:
                info_print(f"ℹ️  [DECODED] Not TEXT_MESSAGE_APP, portnum={decoded.get('portnum', 'MISSING') if decoded else 'NO DECODED'}")
            # ========== FIN VALIDATION ==========


            # ========================================
            # DÉTERMINER LE MODE DE FONCTIONNEMENT
            # ========================================
            # En mode single-node, tous les paquets viennent de notre interface unique
            # En mode dual, les paquets viennent de Meshtastic OU MeshCore (via network_source)
            # FIX: In dual mode, check if interface is EITHER meshtastic OR meshcore
            if self._dual_mode_active and self.dual_interface:
                is_from_our_interface = (
                    interface == self.interface or 
                    interface == self.dual_interface.meshcore_interface
                )
                # DEBUG: Log interface comparison
                #debug_print(f"🔍 [DUAL-MODE] interface={type(interface).__name__ if interface else 'None'}")
                #debug_print(f"🔍 [DUAL-MODE] self.interface={type(self.interface).__name__ if self.interface else 'None'}")
                #debug_print(f"🔍 [DUAL-MODE] meshcore_interface={type(self.dual_interface.meshcore_interface).__name__ if self.dual_interface.meshcore_interface else 'None'}")
                #debug_print(f"🔍 [DUAL-MODE] is_from_our_interface={is_from_our_interface}")
            else:
                is_from_our_interface = (interface == self.interface)
            
            # Déterminer la source pour les logs et stats
            # IMPORTANT: Vérifier le mode dual EN PREMIER
            
            if self._dual_mode_active and network_source:
                # Mode dual: utiliser le network_source fourni
                if network_source == NetworkSource.MESHTASTIC:
                    source = 'meshtastic'
                    debug_print("🔍 Source détectée: Meshtastic (dual mode)")
                elif network_source == NetworkSource.MESHCORE:
                    source = 'meshcore'
                    debug_print("🔍 Source détectée: MeshCore (dual mode)")
                    # MC DEBUG: Ultra-visible source detection
                    info_print_mc("🔗 MC DEBUG: Source détectée comme MeshCore (dual mode)")
                    info_print_mc(f"🔗 MC DEBUG: → Packet sera traité avec source='meshcore'")
                else:
                    source = 'unknown'
                    debug_print(f"🔍 Source détectée: Unknown ({network_source})")
            elif globals().get('MESHCORE_ENABLED', False) and not self._dual_mode_active:
                # Mode MeshCore companion (sans dual mode) - tous les paquets viennent de MeshCore
                source = 'meshcore'
                debug_print("🔍 Source détectée: MeshCore (MESHCORE_ENABLED=True, single mode)")
                # MC DEBUG: Ultra-visible source detection
                info_print_mc("🔗 MC DEBUG: Source détectée comme MeshCore (single mode)")
                info_print_mc(f"🔗 MC DEBUG: → MESHCORE_ENABLED=True, dual_mode=False")
            elif self._is_tcp_mode():
                source = 'tcp'
                debug_print("🔍 Source détectée: TCP mode")
            elif globals().get('CONNECTION_MODE', 'serial').lower() == 'serial':
                source = 'local'
                debug_print("🔍 Source détectée: Serial/local mode")
            else:
                # Mode legacy: distinguer serial vs TCP externe
                source = 'local' if is_from_our_interface else 'tigrog2'
                debug_print(f"🔍 Source détectée: Legacy mode ({'local' if is_from_our_interface else 'tigrog2'})")
            
            # Log final source determination

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
            # En mode dual: tous les paquets de n'importe quelle interface sont traités
            # En mode legacy: filtrer selon PROCESS_TCP_COMMANDS
            
            # Get connection mode from globals (set in run() method)
            connection_mode = globals().get('CONNECTION_MODE', 'serial').lower()
            
            # DEBUG: Log connection mode and filtering decision
            debug_print(f"🔍 [FILTER] connection_mode={connection_mode} | is_from_our_interface={is_from_our_interface} | source={source} | dual_mode_active={self._dual_mode_active}")
            
            # FIX: En mode dual, ne PAS filtrer par interface car les deux interfaces sont "les nôtres"
            if self._dual_mode_active:
                # MODE DUAL: Tous les paquets des deux interfaces sont traités
                debug_print(f"✅ [DUAL-MODE] Packet accepté (dual mode actif)")
                # Continuer le traitement normalement
            elif connection_mode in ['serial', 'tcp']:
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
            
            # Check if this is a MeshCore DM (marked by wrapper)
            is_meshcore_dm = packet.get('_meshcore_dm', False)
            
            # DEBUG: Log MeshCore DM flag
            if is_meshcore_dm:
                info_print(f"🔍 [DEBUG] _meshcore_dm flag présent dans packet | from=0x{from_id:08x} | to=0x{to_id:08x}")
                # MC DEBUG: Ultra-visible DM detection
                info_print_mc("=" * 80)
                info_print_mc("💌 MC DEBUG: MESHCORE DM DETECTED")
                info_print_mc("=" * 80)
                info_print_mc(f"📍 Location: main_bot.py::on_message() - DM detection")
                info_print_mc(f"📦 From: 0x{from_id:08x}")
                info_print_mc(f"📬 To: 0x{to_id:08x}")
                info_print_mc(f"🏷️  _meshcore_dm flag: True")
                info_print_mc("=" * 80)
            
            # Broadcast can be to 0xFFFFFFFF or to 0 (both are broadcast addresses)
            # BUT: MeshCore DMs are NOT broadcasts even if to_id looks like broadcast
            is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm

            # Filtrer les messages auto-générés
            if is_from_me:
                return
            
            decoded = packet.get('decoded', {})
            portnum = decoded.get('portnum', '')

            # ========================================
            # PHASE 3: TRAITEMENT DES COMMANDES
            # ========================================
            
            # Track network source for reply routing (dual mode)
            if self._dual_mode_active and network_source and self.message_handler:
                # Store which network this sender came from
                # This allows MessageSender to route replies back to the correct network
                if hasattr(self.message_handler.router, 'sender'):
                    self.message_handler.router.sender.set_sender_network(from_id, network_source)
                    debug_print(f"📍 Tracked sender network: 0x{from_id:08x} → {network_source}")

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
                
                # MC DEBUG: Log TEXT_MESSAGE_APP from MeshCore
                if source == 'meshcore':
                    info_print_mc("=" * 80)
                    info_print_mc("📨 MC DEBUG: TEXT_MESSAGE_APP FROM MESHCORE")
                    info_print_mc("=" * 80)
                    info_print_mc(f"📍 Location: main_bot.py::on_message() - TEXT_MESSAGE_APP processing")
                    info_print_mc(f"📦 From: 0x{from_id:08x}")
                    info_print_mc(f"📬 To: 0x{to_id:08x}")
                    info_print_mc(f"💬 Message: {message[:80]}{'...' if len(message) > 80 else ''}")
                    info_print_mc(f"📢 Is broadcast: {is_broadcast}")
                    info_print_mc(f"💌 Is DM: {not is_broadcast}")
                    info_print_mc(f"🏷️  _meshcore_dm flag: {is_meshcore_dm}")
                    info_print_mc(f"➡️  Continuing with message processing")
                    info_print_mc("=" * 80)
                
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
                    # DEBUG: Log avant appel process_text_message
                    info_print(f"📞 [DEBUG] Appel process_text_message | message='{message}' | _meshcore_dm={packet.get('_meshcore_dm', False)}")
                    
                    # MC DEBUG: Log command processing call
                    if source == 'meshcore':
                        info_print_mc("=" * 80)
                        info_print_mc("🎯 MC DEBUG: CALLING process_text_message() FOR MESHCORE")
                        info_print_mc("=" * 80)
                        info_print_mc(f"📍 Location: main_bot.py::on_message() - before process_text_message()")
                        info_print_mc(f"💬 Message: {message[:80]}{'...' if len(message) > 80 else ''}")
                        info_print_mc(f"📦 From: 0x{from_id:08x}")
                        info_print_mc(f"➡️  Calling: self.message_handler.process_text_message()")
                        info_print_mc("=" * 80)
                    
                    self.message_handler.process_text_message(packet, decoded, message)
                    
                    # MC DEBUG: Log command processing completion
                    if source == 'meshcore':
                        info_print_mc("✅ MC DEBUG: process_text_message() returned")
        
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
                                        info_print("ℹ️ Aucune clé à re-synchroniser (aucune clé dans SQLite DB)")
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
                        self._last_forced_reconnect = time.time()  # Reset scheduled reconnection timer
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
                
                # === SCHEDULED RECONNECTION (if enabled) ===
                # Force reconnection at regular intervals to work around firmware bugs
                if self.TCP_FORCE_RECONNECT_INTERVAL > 0:
                    time_since_last_forced = time.time() - self._last_forced_reconnect
                    
                    if time_since_last_forced >= self.TCP_FORCE_RECONNECT_INTERVAL:
                        # Time for scheduled reconnection
                        session_stats = self._get_session_stats()
                        
                        info_print(f"🔄 Reconnexion TCP programmée (intervalle: {self.TCP_FORCE_RECONNECT_INTERVAL}s)")
                        info_print(f"📊 Session stats: {session_stats['packets']} paquets en {session_stats['duration']:.0f}s ({session_stats['rate']:.1f} pkt/min)")
                        
                        # Trigger reconnection
                        self._reconnect_tcp_interface()
                        self._last_forced_reconnect = time.time()
                        
                        # Skip silence check after scheduled reconnection
                        continue
                
                # === SILENCE DETECTION (existing logic) ===
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
        # Check if interface supports sendData() (MeshCoreCLIWrapper doesn't have this method)
        if not hasattr(self.interface, 'sendData'):
            debug_print(f"⚠️ Interface type {type(self.interface).__name__} ne supporte pas sendData()")
            debug_print("   Télémétrie broadcast désactivée pour ce type d'interface")
            return False
        
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
        """Démarrage du bot - version simplifiée avec support TCP/Serial/MeshCore"""
        info_print("🤖 Bot Meshtastic-Llama avec architecture modulaire")
        
        # ========================================
        # INSTALLATION GESTIONNAIRES DE SIGNAUX
        # ========================================
        # Configurer les gestionnaires pour arrêt propre
        signal.signal(signal.SIGTERM, self._signal_handler)  # systemd stop
        signal.signal(signal.SIGINT, self._signal_handler)   # Ctrl+C
        info_print("✅ Gestionnaires de signaux installés (SIGTERM, SIGINT)")
        
        # Load nodes from SQLite database (already done in __init__)
        # self.node_manager.load_nodes_from_sqlite() - already called in __init__
        
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
            meshtastic_enabled = globals().get('MESHTASTIC_ENABLED', True)
            meshcore_enabled = globals().get('MESHCORE_ENABLED', False)
            dual_mode = globals().get('DUAL_NETWORK_MODE', False)
            connection_mode = globals().get('CONNECTION_MODE', 'serial').lower()
            
            # Priority order:
            # 1. Dual mode (if DUAL_NETWORK_MODE=True) - Both Meshtastic AND MeshCore
            # 2. Meshtastic (if enabled) - Full mesh capabilities
            # 3. MeshCore (if Meshtastic disabled) - Companion mode for DMs only
            # 4. Standalone (neither enabled) - Test mode
            
            # ========================================
            # VALIDATION: PORT CONFLICT DETECTION
            # ========================================
            # Prevent serial port conflicts in dual mode or when both are serial
            if dual_mode and meshtastic_enabled and meshcore_enabled:
                # Check if both are using serial connections
                if connection_mode == 'serial':
                    serial_port = globals().get('SERIAL_PORT', '/dev/ttyACM0')
                    meshcore_port = globals().get('MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
                    
                    # Normalize paths for comparison
                    import os
                    serial_port_abs = os.path.abspath(serial_port) if serial_port else None
                    meshcore_port_abs = os.path.abspath(meshcore_port) if meshcore_port else None
                    
                    if serial_port_abs and meshcore_port_abs and serial_port_abs == meshcore_port_abs:
                        error_print("❌ ERREUR FATALE: Conflit de port série détecté!")
                        error_print(f"   SERIAL_PORT = {serial_port}")
                        error_print(f"   MESHCORE_SERIAL_PORT = {meshcore_port}")
                        error_print("")
                        error_print("   Les deux interfaces tentent d'utiliser le MÊME port série.")
                        error_print("   Cela causera une erreur '[Errno 11] Could not exclusively lock port'.")
                        error_print("")
                        error_print("   📝 SOLUTION: Utiliser deux ports série différents")
                        error_print("")
                        error_print("   Exemple de configuration:")
                        error_print("     DUAL_NETWORK_MODE = True")
                        error_print("     MESHTASTIC_ENABLED = True")
                        error_print("     MESHCORE_ENABLED = True")
                        error_print("     CONNECTION_MODE = 'serial'")
                        error_print("     SERIAL_PORT = '/dev/ttyACM0'        # Radio Meshtastic")
                        error_print("     MESHCORE_SERIAL_PORT = '/dev/ttyUSB0'  # Radio MeshCore")
                        error_print("")
                        error_print("   Ou en mode simple (un seul réseau):")
                        error_print("     DUAL_NETWORK_MODE = False")
                        error_print("     MESHTASTIC_ENABLED = True")
                        error_print("     MESHCORE_ENABLED = False")
                        error_print("")
                        return False
            
            if dual_mode and meshtastic_enabled and meshcore_enabled:
                # ========================================
                # MODE DUAL - Meshtastic + MeshCore simultanément
                # ========================================
                info_print("🔄 MODE DUAL: Connexion simultanée Meshtastic + MeshCore")
                
                self._dual_mode_active = True
                
                # Initialize dual interface manager
                self.dual_interface = DualInterfaceManager(message_callback=self.on_message)
                
                # Setup Meshtastic interface
                info_print("🌐 Configuration interface Meshtastic...")
                if connection_mode == 'tcp':
                    tcp_host = globals().get('TCP_HOST', '192.168.1.38')
                    tcp_port = globals().get('TCP_PORT', 4403)
                    meshtastic_interface = OptimizedTCPInterface(hostname=tcp_host, portNumber=tcp_port)
                    info_print(f"✅ Meshtastic TCP: {tcp_host}:{tcp_port}")
                else:
                    serial_port = globals().get('SERIAL_PORT', '/dev/ttyACM0')
                    
                    # Auto-detect USB port if configured
                    serial_port = USBPortDetector.resolve_port(serial_port, "Meshtastic")
                    
                    # Retry logic for serial port
                    max_retries = globals().get('SERIAL_PORT_RETRIES', 3)
                    retry_delay = globals().get('SERIAL_PORT_RETRY_DELAY', 2)
                    
                    meshtastic_interface = None
                    last_error = None
                    
                    for attempt in range(max_retries):
                        try:
                            info_print(f"🔍 Creating Meshtastic SerialInterface (attempt {attempt + 1}/{max_retries})...")
                            meshtastic_interface = _create_serial_interface_with_timeout(serial_port, timeout=10)
                            
                            if not meshtastic_interface:
                                # Timeout occurred
                                error_print(f"❌ Timeout creating Meshtastic interface (attempt {attempt + 1}/{max_retries})")
                                if attempt < max_retries - 1:
                                    info_print(f"   ⏳ Retrying in {retry_delay} seconds...")
                                    time.sleep(retry_delay)
                                else:
                                    error_print("❌ All retries exhausted - Mode dual désactivé")
                                continue
                            
                            info_print(f"✅ Meshtastic Serial: {serial_port}")
                            
                            # Display node name for wiring verification (if available)
                            if hasattr(meshtastic_interface, 'localNode') and meshtastic_interface.localNode:
                                try:
                                    node_info = meshtastic_interface.localNode
                                    if hasattr(node_info, 'user') and node_info.user:
                                        long_name = getattr(node_info.user, 'longName', None)
                                        if long_name:
                                            info_print_mt(f"📡 Node Name: {long_name}")
                                        # Node name not yet populated - this is normal during initialization
                                    # User info not yet populated - this is normal during initialization
                                except Exception as e:
                                    # Silently ignore - node name display is optional
                                    pass
                            
                            break
                        except serial.serialutil.SerialException as e:
                            last_error = e
                            error_msg = str(e)
                            
                            if "exclusively lock" in error_msg or "Resource temporarily unavailable" in error_msg:
                                error_print(f"❌ Port Meshtastic verrouillé (tentative {attempt + 1}/{max_retries}): {serial_port}")
                                
                                if attempt < max_retries - 1:
                                    info_print(f"   ⏳ Nouvelle tentative dans {retry_delay} secondes...")
                                    time.sleep(retry_delay)
                                else:
                                    error_print("")
                                    error_print("   ❌ Impossible d'ouvrir le port Meshtastic après plusieurs tentatives")
                                    error_print("   → Mode dual désactivé, vérifier la configuration")
                            else:
                                error_print(f"❌ Erreur série Meshtastic: {e}")
                                break
                        except Exception as e:
                            last_error = e
                            error_print(f"❌ Erreur inattendue Meshtastic: {e}")
                            break
                    
                    if not meshtastic_interface:
                        error_print("❌ Échec création interface Meshtastic - Mode dual désactivé")
                        self._dual_mode_active = False
                        # Will continue to setup MeshCore below
                
                if meshtastic_interface:
                    self.dual_interface.set_meshtastic_interface(meshtastic_interface)
                
                # Setup MeshCore interface
                meshcore_port = globals().get('MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
                
                # Auto-detect USB port if configured
                meshcore_port = USBPortDetector.resolve_port(meshcore_port, "MeshCore")
                
                info_print("=" * 80)
                info_print("🔗 MESHCORE DUAL MODE INITIALIZATION")
                info_print("=" * 80)
                info_print(f"📍 MeshCore port: {meshcore_port}")
                info_print(f"🔧 Interface class: {MeshCoreSerialInterface.__name__}")
                info_print("🔍 Creating MeshCore interface...")
                
                meshcore_interface = MeshCoreSerialInterface(meshcore_port)
                info_print(f"✅ Interface object created: {type(meshcore_interface).__name__}")
                
                info_print("🔍 Attempting connection...")
                if not meshcore_interface.connect():
                    error_print("=" * 80)
                    error_print("❌ MESHCORE CONNECTION FAILED - Dual mode désactivé")
                    error_print("=" * 80)
                    error_print(f"   Port: {meshcore_port}")
                    error_print("   → Check serial port exists and is accessible")
                    error_print("   → Check no other process is using the port")
                    error_print(f"   → Try: ls -la {meshcore_port}")
                    error_print(f"   → Try: sudo lsof {meshcore_port}")
                    error_print("=" * 80)
                    self._dual_mode_active = False
                    self.interface = meshtastic_interface
                    
                    # CRITICAL FIX: Configure callback when falling back to Meshtastic-only
                    info_print("🔍 Configuring Meshtastic callback (dual mode failed)...")
                    if hasattr(self.interface, 'set_message_callback'):
                        self.interface.set_message_callback(self.on_message)
                        info_print("✅ Meshtastic callback configured")
                        info_print("✅ Meshtastic interface active (fallback from dual mode)")
                    else:
                        error_print("⚠️ Interface doesn't support set_message_callback")
                else:
                    info_print("✅ MeshCore connection successful")
                    
                    # Display node info for wiring verification
                    if hasattr(meshcore_interface, 'meshcore') and meshcore_interface.meshcore:
                        try:
                            if hasattr(meshcore_interface.meshcore, 'node_id'):
                                node_id = meshcore_interface.meshcore.node_id
                                info_print_mc(f"📡 Node ID: 0x{node_id:08x}")
                            else:
                                debug_print_mc("⚠️ MeshCore object exists but no node_id available")
                        except Exception as e:
                            debug_print_mc(f"⚠️ Error getting MeshCore node info: {e}")
                    elif hasattr(meshcore_interface, 'localNode') and meshcore_interface.localNode:
                        try:
                            node_id = meshcore_interface.localNode.nodeNum
                            if node_id and node_id != 0xFFFFFFFE:  # Don't show unknown node ID
                                info_print_mc(f"📡 Node ID: 0x{node_id:08x}")
                        except Exception as e:
                            debug_print_mc(f"⚠️ Error getting localNode info: {e}")
                    
                    # Configure node_manager for pubkey lookups
                    if hasattr(meshcore_interface, 'set_node_manager'):
                        meshcore_interface.set_node_manager(self.node_manager)
                        info_print("✅ Node manager configured for pubkey lookups")
                    
                    info_print("🔍 Starting MeshCore serial reading thread...")
                    if not meshcore_interface.start_reading():
                        error_print("=" * 80)
                        error_print("❌ MESHCORE START_READING FAILED - Dual mode désactivé")
                        error_print("=" * 80)
                        error_print("   → MeshCore serial thread did not start")
                        error_print("   → Check logs above for thread creation errors")
                        error_print("=" * 80)
                        self._dual_mode_active = False
                        self.interface = meshtastic_interface
                        
                        # CRITICAL FIX: Configure callback when falling back to Meshtastic-only
                        info_print("🔍 Configuring Meshtastic callback (dual mode failed)...")
                        if hasattr(self.interface, 'set_message_callback'):
                            self.interface.set_message_callback(self.on_message)
                            info_print("✅ Meshtastic callback configured")
                            info_print("✅ Meshtastic interface active (fallback from dual mode)")
                        else:
                            error_print("⚠️ Interface doesn't support set_message_callback")
                    else:
                        info_print("✅ MeshCore reading thread started")
                        
                        info_print("🔍 Configuring dual interface manager...")
                        self.dual_interface.set_meshcore_interface(meshcore_interface)
                        info_print("✅ MeshCore interface set in dual manager")
                        
                        # Setup callbacks for both interfaces
                        info_print("🔍 Setting up message callbacks...")
                        self.dual_interface.setup_message_callbacks()
                        info_print("✅ Message callbacks configured")
                        
                        # Set primary interface for compatibility (use Meshtastic for full features)
                        self.interface = self.dual_interface.get_primary_interface()
                        info_print(f"✅ Primary interface: {type(self.interface).__name__}")
                        
                        info_print("=" * 80)
                        info_print("✅ MESHCORE DUAL MODE INITIALIZATION COMPLETE")
                        info_print("=" * 80)
                        info_print(f"   → Meshtastic: {type(meshtastic_interface).__name__}")
                        info_print(f"   → MeshCore: {type(meshcore_interface).__name__}")
                        info_print("   → Bot will receive packets from BOTH networks")
                        info_print("   → Meshtastic packets: [DEBUG][MT]")
                        info_print("   → MeshCore packets: [DEBUG][MC]")
                        info_print("=" * 80)
                
                # Stabilization
                time.sleep(3)
                
            elif not meshtastic_enabled and not meshcore_enabled:
                # Mode standalone - aucune connexion radio
                info_print("⚠️ Mode STANDALONE: Aucune connexion Meshtastic ni MeshCore")
                self.interface = MeshCoreStandaloneInterface()
                
            elif meshtastic_enabled and meshcore_enabled and not dual_mode:
                # Both enabled but dual mode NOT enabled - warn user and prioritize Meshtastic
                info_print("⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés")
                # Continue to Meshtastic connection (next if blocks)
                
            elif meshtastic_enabled and connection_mode == 'tcp':
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
                
            elif meshtastic_enabled:
                # ========================================
                # MODE SERIAL - Connexion série Meshtastic (défaut)
                # ========================================
                serial_port = globals().get('SERIAL_PORT', '/dev/ttyACM0')
                
                # Auto-detect USB port if configured
                serial_port = USBPortDetector.resolve_port(serial_port, "Meshtastic")
                
                info_print(f"🔌 Mode SERIAL MESHTASTIC: Connexion série {serial_port}")
                
                # Retry logic for serial port with better error handling
                max_retries = globals().get('SERIAL_PORT_RETRIES', 3)
                retry_delay = globals().get('SERIAL_PORT_RETRY_DELAY', 2)  # seconds
                
                serial_opened = False
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        info_print(f"🔍 Creating Meshtastic SerialInterface (attempt {attempt + 1}/{max_retries})...")
                        self.interface = _create_serial_interface_with_timeout(serial_port, timeout=10)
                        
                        if not self.interface:
                            # Timeout occurred
                            error_print(f"❌ Timeout creating Meshtastic interface (attempt {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                info_print(f"   ⏳ Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                            else:
                                error_print("❌ All retries exhausted")
                            continue
                        
                        serial_opened = True
                        info_print("✅ Interface série créée")
                        
                        # Display node name for wiring verification (if available)
                        if hasattr(self.interface, 'localNode') and self.interface.localNode:
                            try:
                                node_info = self.interface.localNode
                                if hasattr(node_info, 'user') and node_info.user:
                                    long_name = getattr(node_info.user, 'longName', None)
                                    if long_name:
                                        info_print_mt(f"📡 Node Name: {long_name}")
                                    # Node name not yet populated - this is normal during initialization
                                # User info not yet populated - this is normal during initialization
                            except Exception as e:
                                # Silently ignore - node name display is optional
                                pass
                        
                        break
                    except serial.serialutil.SerialException as e:
                        last_error = e
                        error_msg = str(e)
                        
                        # Check for common error cases
                        if "exclusively lock" in error_msg or "Resource temporarily unavailable" in error_msg:
                            error_print(f"❌ Port série verrouillé (tentative {attempt + 1}/{max_retries}): {serial_port}")
                            error_print(f"   Erreur: {error_msg}")
                            
                            if attempt == 0:
                                # On first attempt, provide diagnostic information
                                error_print("")
                                error_print("   📝 DIAGNOSTIC: Le port série est déjà utilisé par un autre processus")
                                error_print("")
                                error_print("   Causes possibles:")
                                error_print("   1. Une autre instance du bot est en cours d'exécution")
                                error_print("   2. MeshCore a déjà ouvert ce port (vérifier MESHCORE_SERIAL_PORT)")
                                error_print("   3. Un autre programme utilise le port (ex: minicom, screen)")
                                error_print("")
                                error_print("   Commandes de diagnostic:")
                                error_print(f"     sudo lsof {serial_port}  # Voir quel processus utilise le port")
                                error_print(f"     sudo fuser {serial_port} # Alternative pour voir les processus")
                                error_print("     ps aux | grep meshbot    # Voir les instances du bot")
                                error_print("")
                            
                            if attempt < max_retries - 1:
                                info_print(f"   ⏳ Nouvelle tentative dans {retry_delay} secondes...")
                                time.sleep(retry_delay)
                            else:
                                error_print("")
                                error_print("   ❌ Impossible d'ouvrir le port série après plusieurs tentatives")
                                error_print("   → Vérifier qu'aucun autre processus n'utilise le port")
                                error_print("   → Vérifier la configuration (SERIAL_PORT vs MESHCORE_SERIAL_PORT)")
                        else:
                            # Other serial errors (permission, doesn't exist, etc.)
                            error_print(f"❌ Erreur série (tentative {attempt + 1}/{max_retries}): {e}")
                            if "Permission denied" in error_msg:
                                error_print("   → Permissions insuffisantes. Ajouter l'utilisateur au groupe 'dialout':")
                                error_print(f"     sudo usermod -a -G dialout $USER")
                                error_print("     (puis se reconnecter)")
                            elif "No such file" in error_msg or "does not exist" in error_msg:
                                error_print(f"   → Le port {serial_port} n'existe pas")
                                error_print("   → Vérifier les ports disponibles avec: ls -la /dev/tty*")
                            
                            # For non-lock errors, fail fast (don't retry)
                            break
                    except Exception as e:
                        last_error = e
                        error_print(f"❌ Erreur inattendue lors de l'ouverture du port série: {e}")
                        error_print(traceback.format_exc())
                        break
                
                if not serial_opened:
                    error_print("❌ Impossible d'ouvrir le port série Meshtastic")
                    if last_error:
                        error_print(f"   Dernière erreur: {last_error}")
                    error_print("   Le bot ne peut pas démarrer sans connexion Meshtastic")
                    return False
                
                # Stabilisation
                time.sleep(3)
                info_print("✅ Connexion série stable")
                
            elif meshcore_enabled and not meshtastic_enabled:
                # ========================================
                # MODE MESHCORE COMPANION - Connexion série MeshCore
                # ========================================
                meshcore_port = globals().get('MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
                
                # Auto-detect USB port if configured
                meshcore_port = USBPortDetector.resolve_port(meshcore_port, "MeshCore")
                
                # DEFENSIVE CHECK: This block should NEVER run if meshtastic_enabled is True
                # Log comprehensive state for debugging configuration conflicts
                if meshtastic_enabled:
                    error_print("❌ FATAL ERROR: MeshCore initialization attempted with MESHTASTIC_ENABLED=True")
                    error_print(f"   meshtastic_enabled = {meshtastic_enabled}")
                    error_print(f"   meshcore_enabled = {meshcore_enabled}")
                    error_print(f"   connection_mode = {connection_mode}")
                    error_print("   → This should NEVER happen - check code logic")
                    return False
                
                info_print(f"🔗 Mode MESHCORE COMPANION: Connexion série {meshcore_port}")
                info_print("   → Fonctionnalités disponibles: /bot, /weather, /power, /sys, /help")
                info_print("   → Fonctionnalités désactivées: /nodes, /my, /trace, /stats (Meshtastic requis)")
                
                self.interface = MeshCoreSerialInterface(meshcore_port)
                
                if not self.interface.connect():
                    error_print("❌ Échec connexion série MeshCore")
                    return False
                
                info_print_mc("✅ MeshCore standalone connection successful")
                
                # Display node info for wiring verification
                if hasattr(self.interface, 'meshcore') and self.interface.meshcore:
                    try:
                        if hasattr(self.interface.meshcore, 'node_id'):
                            node_id = self.interface.meshcore.node_id
                            info_print_mc(f"📡 Node ID: 0x{node_id:08x}")
                        else:
                            debug_print_mc("⚠️ MeshCore object exists but no node_id available")
                    except Exception as e:
                        debug_print_mc(f"⚠️ Error getting MeshCore node info: {e}")
                elif hasattr(self.interface, 'localNode') and self.interface.localNode:
                    try:
                        node_id = self.interface.localNode.nodeNum
                        if node_id and node_id != 0xFFFFFFFE:  # Don't show unknown node ID
                            info_print_mc(f"📡 Node ID: 0x{node_id:08x}")
                    except Exception as e:
                        debug_print_mc(f"⚠️ Error getting localNode info: {e}")
                
                # Configure node_manager for pubkey lookups
                if hasattr(self.interface, 'set_node_manager'):
                    self.interface.set_node_manager(self.node_manager)
                
                # Démarrer la lecture des messages
                if not self.interface.start_reading():
                    error_print("❌ Échec démarrage lecture MeshCore")
                    return False
                
                # Configurer le callback pour les messages reçus
                self.interface.set_message_callback(self.on_message)
                info_print_mc(f"✅ Callback MeshCore configuré: {self.on_message}")
                info_print_mc(f"   Interface type: {type(self.interface).__name__}")
                info_print_mc(f"   Callback set to: on_message method")
                info_print_mc("✅ Connexion MeshCore établie")
            
            # ========================================
            # RÉUTILISATION DE L'INTERFACE PRINCIPALE
            # ========================================
            # Partager l'interface avec RemoteNodesClient pour éviter
            # de créer des connexions TCP supplémentaires
            # (Uniquement si Meshtastic est actif)
            if meshtastic_enabled:
                self.remote_nodes_client.interface = self.interface
                info_print("♻️ Interface partagée avec RemoteNodesClient")
            
            # ========================================
            # SYNCHRONISATION DES CLÉS PUBLIQUES (Meshtastic uniquement)
            # ========================================
            # Inject public keys from node_names.json into interface.nodes
            # This is critical for DM decryption in TCP mode where interface.nodes
            # starts empty. We restore keys from our persistent database without
            # violating ESP32 single-connection limitation.
            if meshtastic_enabled:
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
            # CHARGEMENT INITIAL DES VOISINS (Meshtastic uniquement)
            # ========================================
            # Populate neighbor database from interface at startup
            # This provides an initial complete view of the network topology
            # Passive collection will continue via NEIGHBORINFO_APP packets
            if meshtastic_enabled:
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
            # ABONNEMENT AUX MESSAGES
            # ========================================
            # En mode Meshtastic: S'abonner aux messages via pubsub
            # En mode MeshCore: Le callback est déjà configuré
            
            # === ULTRA-VISIBLE DIAGNOSTIC BANNER ===
            info_print("=" * 80)
            info_print("🔔 SUBSCRIPTION SETUP - CRITICAL FOR PACKET RECEPTION")
            info_print("=" * 80)
            info_print(f"   meshtastic_enabled = {meshtastic_enabled}")
            info_print(f"   meshcore_enabled = {meshcore_enabled}")
            info_print(f"   dual_mode (config) = {dual_mode}")
            info_print(f"   dual_mode (active) = {self._dual_mode_active}")
            info_print(f"   connection_mode = {connection_mode}")
            info_print(f"   interface type = {type(self.interface).__name__ if hasattr(self, 'interface') and self.interface else 'None'}")
            
            # CRITICAL: Warn if dual mode config is True but active is False
            if dual_mode and not self._dual_mode_active:
                error_print("=" * 80)
                error_print("⚠️  DUAL MODE MISMATCH DETECTED!")
                error_print("=" * 80)
                error_print(f"   Config: DUAL_NETWORK_MODE = True")
                error_print(f"   Runtime: dual_mode_active = False")
                error_print("")
                error_print("   ❌ Dual mode initialization FAILED during startup")
                error_print("   → Check logs above for error messages:")
                error_print("      - 'Échec création interface Meshtastic'")
                error_print("      - 'MESHCORE CONNECTION FAILED'")
                error_print("      - 'MESHCORE START_READING FAILED'")
                error_print("")
                error_print("   📋 Bot running in FALLBACK mode:")
                if hasattr(self, 'interface') and self.interface:
                    interface_name = type(self.interface).__name__
                    if 'MeshCore' in interface_name:
                        error_print("      → Using MeshCore ONLY (Meshtastic failed)")
                    else:
                        error_print("      → Using Meshtastic ONLY (MeshCore failed)")
                error_print("=" * 80)
            
            # Show which packet sources are active
            if self._dual_mode_active:
                info_print("   📡 ACTIVE NETWORKS:")
                info_print("      ✅ Meshtastic (via primary interface)")
                info_print("      ✅ MeshCore (via dual interface)")
                info_print("      → Will see [DEBUG][MT] AND [DEBUG][MC] packets")
            elif meshtastic_enabled and not meshcore_enabled:
                info_print("   📡 ACTIVE NETWORK:")
                info_print("      ✅ Meshtastic ONLY")
                info_print("      → Will see [DEBUG][MT] packets only")
            elif meshcore_enabled and not meshtastic_enabled:
                info_print("   📡 ACTIVE NETWORK:")
                info_print("      ✅ MeshCore ONLY")
                info_print("      → Will see [DEBUG][MC] packets only")
            elif meshtastic_enabled and meshcore_enabled and not dual_mode:
                info_print("   📡 ACTIVE NETWORK:")
                info_print("      ✅ Meshtastic ONLY (MeshCore ignored)")
                info_print("      ⚠️  Both enabled but DUAL_NETWORK_MODE=False")
                info_print("      → Will see [DEBUG][MT] packets only")
                info_print("      → To enable MeshCore: Set DUAL_NETWORK_MODE=True")
            
            # Add post-initialization diagnostic if config doesn't match reality
            if dual_mode and meshtastic_enabled and meshcore_enabled:
                if not self._dual_mode_active:
                    error_print("=" * 80)
                    error_print("⚠️  DUAL MODE INITIALIZATION FAILED!")
                    error_print("=" * 80)
                    error_print("   CONFIG: DUAL_NETWORK_MODE=True")
                    error_print("   REALITY: Running in Meshtastic-only mode")
                    error_print("")
                    error_print("   POSSIBLE CAUSES:")
                    error_print("   1. Meshtastic port creation failed")
                    error_print("   2. MeshCore port connection failed")
                    error_print("   3. MeshCore start_reading failed")
                    error_print("")
                    error_print("   CHECK LOGS ABOVE for error messages:")
                    error_print("   - Look for '❌ Échec création interface Meshtastic'")
                    error_print("   - Look for '❌ Échec connexion MeshCore'")
                    error_print("   - Look for '❌ Échec démarrage lecture MeshCore'")
                    error_print("")
                    error_print("   VERIFY:")
                    error_print(f"   - SERIAL_PORT exists and accessible")
                    error_print(f"   - MESHCORE_SERIAL_PORT exists and accessible")
                    error_print(f"   - Both ports are different")
                    error_print(f"   - meshcore/meshcoredecoder libraries installed")
                    error_print("=" * 80)
            
            info_print("=" * 80)
            
            if meshtastic_enabled:
                # DOIT être fait immédiatement après la création de l'interface
                # S'abonner aux différents types de messages Meshtastic
                # - meshtastic.receive.text : messages texte (TEXT_MESSAGE_APP)
                # - meshtastic.receive.data : messages de données
                # - meshtastic.receive : messages génériques (fallback)
                
                info_print_mt("📡 Subscribing to Meshtastic messages via pubsub...")
                
                # S'abonner avec le callback principal
                # NOTE: Seulement "meshtastic.receive" pour éviter les duplications
                # (ce topic catch ALL messages: text, data, position, etc.)
                pub.subscribe(self.on_message, "meshtastic.receive")
                
                info_print_mt("✅ ✅ ✅ SUBSCRIBED TO meshtastic.receive ✅ ✅ ✅")
                info_print_mt(f"   Callback: {self.on_message}")
                info_print_mt(f"   Topic: 'meshtastic.receive'")
                info_print_mt("   → Meshtastic interface should now publish packets to this callback")
                info_print_mt("   → You should see '🔔 on_message CALLED' when packets arrive")
            else:
                info_print_mc("ℹ️  ℹ️  ℹ️  Mode companion: Messages gérés par interface MeshCore")
                info_print_mc("   → MeshCore callback already configured")
                info_print_mc("   → Packets will arrive via MeshCore, not pubsub")
            
            info_print("=" * 80)
            
            # === TEST PUBSUB AFTER SUBSCRIPTION ===
            if meshtastic_enabled:
                info_print("🧪 Testing pubsub mechanism...")
                try:
                    # Try to send a test message through pubsub to verify it works
                    # Note: pub is already imported at module level (line 18)
                    
                    # Check if we're subscribed
                    subscribers = pub.getDefaultTopicMgr().getTopic("meshtastic.receive").getListeners()
                    info_print(f"   Subscribers to 'meshtastic.receive': {len(subscribers)}")
                    for i, sub in enumerate(subscribers):
                        info_print(f"     [{i}] {sub}")
                    
                    if len(subscribers) > 0:
                        info_print("   ✅ Subscription verified - at least one listener registered")
                    else:
                        info_print("   ⚠️  WARNING: No subscribers found! Subscription may have failed")
                        
                except Exception as e:
                    info_print(f"   ⚠️  Could not verify subscription: {e}")
            
            info_print("=" * 80)
            
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

            # NOTE: Gestionnaire d'alertes Mesh initialisé plus tard après MessageHandler
            # (voir section après MeshTracerouteManager)
            self.mesh_alert_manager = None

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
                    
                    mesh_alert_threshold = globals().get('BLITZ_MESH_ALERT_THRESHOLD', 5)

                    self.blitz_monitor = BlitzMonitor(
                        lat=lat,
                        lon=lon,
                        radius_km=globals().get('BLITZ_RADIUS_KM', 50),
                        check_interval=globals().get('BLITZ_CHECK_INTERVAL', 900),
                        window_minutes=globals().get('BLITZ_WINDOW_MINUTES', 15),
                        interface=self.interface,
                        mesh_alert_manager=None,  # Sera mis à jour après MessageHandler init
                        mesh_alert_threshold=mesh_alert_threshold
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
                mqtt_neighbor_collector=self.mqtt_neighbor_collector,  # MQTT collector reference
                companion_mode=(meshcore_enabled or not meshtastic_enabled),  # Mode companion si pas Meshtastic
                dual_interface_manager=self.dual_interface  # Pass dual interface for routing
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
            # GESTIONNAIRE D'ALERTES MESH
            # ========================================
            # Initialiser le gestionnaire d'alertes Mesh (après message_handler)
            if globals().get('MESH_ALERTS_ENABLED', False):
                try:
                    info_print("📢 Initialisation du gestionnaire d'alertes Mesh...")
                    subscribed_nodes = globals().get('MESH_ALERT_SUBSCRIBED_NODES', [])
                    throttle_seconds = globals().get('MESH_ALERT_THROTTLE_SECONDS', 1800)
                    
                    # Convertir les IDs en int si nécessaire (support hex strings)
                    normalized_nodes = []
                    for node in subscribed_nodes:
                        if isinstance(node, str):
                            # Convertir hex string vers int
                            if node.startswith('0x'):
                                normalized_nodes.append(int(node, 16))
                            else:
                                normalized_nodes.append(int(node))
                        else:
                            normalized_nodes.append(node)
                    
                    if normalized_nodes:
                        self.mesh_alert_manager = MeshAlertManager(
                            message_sender=self.message_handler.router.sender,
                            subscribed_nodes=normalized_nodes,
                            throttle_seconds=throttle_seconds
                        )
                        info_print("✅ Gestionnaire d'alertes Mesh initialisé")
                    else:
                        info_print("ℹ️ Alertes Mesh activées mais aucun nœud abonné")
                except Exception as e:
                    error_print(f"Erreur initialisation mesh alert manager: {e}")
                    error_print(traceback.format_exc())
                    self.mesh_alert_manager = None
            else:
                debug_print("ℹ️ Alertes Mesh désactivées (MESH_ALERTS_ENABLED=False)")
            
            # Mettre à jour le mesh_alert_manager dans vigilance_monitor et blitz_monitor
            if self.vigilance_monitor and self.mesh_alert_manager:
                self.vigilance_monitor.mesh_alert_manager = self.mesh_alert_manager
                info_print("✅ Vigilance monitor connecté aux alertes Mesh")
            
            if self.blitz_monitor and self.mesh_alert_manager:
                self.blitz_monitor.mesh_alert_manager = self.mesh_alert_manager
                info_print("✅ Blitz monitor connecté aux alertes Mesh")

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
            status_log_counter = 0  # Counter for periodic status logging
            
            while self.running:
                try:
                    time.sleep(30)
                    cleanup_counter += 1
                    status_log_counter += 1
                    
                    # Periodic status logging (every 2 minutes = 4 x 30s)
                    if status_log_counter % 4 == 0:
                        uptime = time.time() - self.start_time
                        uptime_str = f"{int(uptime/60)}m {int(uptime%60)}s"
                        
                        # Log packet reception status
                        info_print("=" * 80)
                        info_print(f"📊 BOT STATUS - Uptime: {uptime_str}")
                        info_print(f"📦 Packets this session: {self._packets_this_session}")
                        info_print(f"🔍 SOURCE-DEBUG: {'Active (logs on packet reception)' if DEBUG_MODE else 'Inactive (DEBUG_MODE=False)'}")
                        
                        if self._packets_this_session == 0:
                            info_print("⚠️  WARNING: No packets received yet!")
                            info_print("   → Check Meshtastic connection if packets expected")
                        else:
                            info_print(f"✅ Packets flowing normally ({self._packets_this_session} total)")
                        
                        info_print("=" * 80)
                    
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
                    # Nodes are automatically saved to SQLite via persistence
                    debug_print("ℹ️ Nodes persisted to SQLite")
            except Exception as e:
                error_print(f"⚠️ Erreur node_manager cleanup: {e}")

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

            # 6. Fermer dual interface manager (si utilisé)
            try:
                if hasattr(self, 'dual_interface') and self.dual_interface:
                    self.dual_interface.close()
                    self.dual_interface = None
                    debug_print("✅ Dual interface fermée")
            except Exception as e:
                error_print(f"⚠️ Erreur fermeture dual_interface: {e}")

            # 7. Fermer l'interface principale (Meshtastic/MeshCore)
            try:
                if self.interface:
                    # Close the interface properly to stop internal threads and callbacks
                    if hasattr(self.interface, 'close'):
                        self.interface.close()
                        debug_print("✅ Interface principale fermée")
                    self.interface = None
            except Exception as e:
                error_print(f"⚠️ Erreur fermeture interface: {e}")

            # 8. Fermer connexions série/TCP (wrapper)
            try:
                if hasattr(self, 'safe_serial') and self.safe_serial:
                    self.safe_serial.close()
            except Exception as e:
                error_print(f"⚠️ Erreur fermeture safe_serial: {e}")

            # 9. Nettoyage final
            try:
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

