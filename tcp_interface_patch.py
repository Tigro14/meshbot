"""
🔧 MESHTASTIC TCP INTERFACE WRAPPER
====================================

PURPOSE:
    Extended Meshtastic TCP interface for port 4403 connections to Meshtastic nodes.
    This module provides socket state monitoring and external notification callbacks
    to support reliable long-lived connections with fast dead socket detection.
    
    This module is SPECIFICALLY for Meshtastic protocol communication (port 4403).
    
    For other services, use their respective libraries:
    - ESPHome: requests library (esphome_client.py)
    - Weather: curl subprocess (utils_weather.py)  
    - Blitzortung: paho-mqtt library (blitz_monitor.py)

DESIGN PHILOSOPHY:
    After extensive testing documented in TCP_ARCHITECTURE.md, we found that
    ESP32-based Meshtastic nodes are extremely sensitive to socket modifications.
    ANY of the following changes cause connections to die within 2.5 minutes:
    - TCP keepalive options
    - Socket timeout changes
    - TCP_NODELAY setting
    - select() calls before recv()
    
    Therefore, this wrapper uses IDENTICAL socket behavior to the standard
    meshtastic.tcp_interface.TCPInterface. The ONLY additions are:
    1. Background monitoring thread to detect socket death via state change
    2. Callback mechanism to notify external code (main_bot.py) immediately
    3. Thread exception filter to suppress expected network errors from logs

DIVISION OF RESPONSIBILITY:
    ┌─────────────────────────────────────────────────────────────────────┐
    │  OptimizedTCPInterface (this file)                                  │
    │  ├── ROLE: Long-lived primary connections                           │
    │  ├── USED BY: main_bot.py (main interface)                          │
    │  ├── FEATURES:                                                      │
    │  │   ├── Socket state monitoring (every 500ms)                      │
    │  │   ├── Dead socket callback for fast notification                 │
    │  │   └── Clean shutdown with thread cleanup                         │
    │  └── DOES NOT MODIFY: Socket options, recv() behavior               │
    └─────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │  SafeTCPConnection (safe_tcp_connection.py)                         │
    │  ├── ROLE: Temporary/short-lived connections                        │
    │  ├── USED BY: remote_nodes_client.py                                │
    │  └── FEATURES: Context manager, automatic cleanup, helper functions │
    └─────────────────────────────────────────────────────────────────────┘

ARCHITECTURE:
    See TCP_ARCHITECTURE.md for full network stack documentation.

USAGE:
    # For long-lived connections (recommended in main_bot.py):
    from tcp_interface_patch import OptimizedTCPInterface
    interface = OptimizedTCPInterface(hostname='192.168.1.100')
    interface.set_dead_socket_callback(my_notification_function)
    
    # For temporary connections (use SafeTCPConnection instead):
    from safe_tcp_connection import SafeTCPConnection
    with SafeTCPConnection('192.168.1.100') as interface:
        interface.sendText("Hello")
"""

import socket
import time
import threading
import meshtastic.tcp_interface
from meshtastic.stream_interface import StreamInterface
from utils import info_print, error_print, debug_print


class OptimizedTCPInterface(meshtastic.tcp_interface.TCPInterface):
    """
    Meshtastic TCPInterface with dead socket callback for external notification.
    
    This class uses the EXACT same implementation as the standard TCPInterface.
    The only addition is a callback that gets triggered when socket death is
    detected, for external monitoring/logging purposes.
    
    IMPORTANT: We do NOT override _readBytes() because any modification causes
    ESP32-based Meshtastic nodes to close connections prematurely.
    
    The callback is triggered by a background thread that monitors socket state.
    """
    
    def __init__(self, hostname, portNumber=4403, **kwargs):
        info_print(f"🔧 Initialisation OptimizedTCPInterface pour {hostname}:{portNumber}")
        
        # Callback for dead socket detection - for external notification
        self._dead_socket_callback = None
        self._last_socket_state = None
        
        # Call the parent constructor - uses standard TCPInterface entirely
        super().__init__(hostname=hostname, portNumber=portNumber, **kwargs)
        
        # Start a background thread to monitor socket state for callback
        self._monitor_stop = threading.Event()
        self._monitor_thread = threading.Thread(
            target=self._monitor_socket_state,
            name="SocketMonitor",
            daemon=True
        )
        self._monitor_thread.start()
    
    def set_dead_socket_callback(self, callback):
        """
        Set a callback to be invoked when the socket is detected as dead.
        
        Args:
            callback: Function to call when socket dies (no arguments)
        """
        self._dead_socket_callback = callback
        debug_print("✅ Callback socket mort configuré")
    
    def _monitor_socket_state(self):
        """Background thread to monitor socket state and trigger callback."""
        while not self._monitor_stop.is_set():
            try:
                current_socket = self.socket
                
                # Detect transition from connected to disconnected
                if self._last_socket_state is not None and current_socket is None:
                    if self._dead_socket_callback:
                        info_print("🔌 Socket TCP mort: détecté par moniteur")
                        info_print("🔄 Déclenchement reconnexion immédiate via callback...")
                        try:
                            self._dead_socket_callback()
                        except Exception as e:
                            error_print(f"Erreur callback socket mort: {e}")
                
                self._last_socket_state = current_socket
                time.sleep(0.5)  # Check every 500ms
                
            except Exception:
                pass  # Ignore monitoring errors
    
    def close(self):
        """Fermeture propre avec logs"""
        try:
            info_print("Fermeture OptimizedTCPInterface...")
            self._monitor_stop.set()
            super().close()
            info_print("✅ OptimizedTCPInterface fermée")
        except Exception as e:
            error_print(f"Erreur fermeture: {e}")


def create_optimized_interface(hostname, port=4403, **kwargs):
    """
    Factory to create a TCPInterface with dead socket callback support.
    
    Args:
        hostname: IP of Meshtastic node
        port: TCP port (default 4403)
        **kwargs: Additional arguments passed to OptimizedTCPInterface
    
    Returns:
        OptimizedTCPInterface
    """
    return OptimizedTCPInterface(
        hostname=hostname,
        portNumber=port,
        **kwargs
    )


def install_threading_exception_filter():
    """
    Installe un filtre pour supprimer les tracebacks des erreurs réseau normales
    dans les threads Meshtastic.
    
    Problème:
    - Le thread de heartbeat Meshtastic génère des BrokenPipeError périodiques
    - Ces erreurs sont normales (déconnexions réseau) mais polluent les logs
    - On ne peut pas modifier le code du thread (bibliothèque externe)
    
    Solution:
    - Utiliser threading.excepthook (Python 3.8+) pour filtrer les tracebacks
    - Supprimer uniquement les erreurs réseau connues (BrokenPipe, ConnectionReset)
    - Logger en mode debug pour monitoring sans spam
    - Laisser passer toutes les autres exceptions (comportement normal)
    """
    import threading
    import sys
    
    # Sauvegarder le hook d'exception par défaut
    original_excepthook = threading.excepthook
    
    def custom_threading_excepthook(args):
        """
        Hook personnalisé pour filtrer les exceptions des threads
        
        Args:
            args: threading.ExceptHookArgs avec exc_type, exc_value, exc_traceback, thread
        """
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback
        thread = args.thread
        
        # Liste des erreurs réseau à filtrer (normales en TCP)
        network_errors = (
            BrokenPipeError,           # errno 32 - connexion cassée
            ConnectionResetError,      # errno 104 - connexion réinitialisée
            ConnectionRefusedError,    # errno 111 - connexion refusée
            ConnectionAbortedError,    # errno 103 - connexion abandonnée
        )
        
        # IMPORTANT: Ne filtrer que les threads de la bibliothèque Meshtastic
        # Les threads de notre bot (Telegram, CLI, etc.) doivent montrer leurs erreurs
        # pour qu'on puisse les déboguer.
        #
        # Threads à filtrer:
        # - Threads génériques Python (Thread-1, Thread-2, etc.) créés par Meshtastic
        # - Threads sans nom spécifique
        #
        # Threads à NE PAS filtrer:
        # - Nos threads nommés (TelegramBot, CLIServer, BlitzMQTT, etc.)
        # - Tout thread avec un nom descriptif
        
        thread_name = thread.name if thread else "Unknown"
        is_meshtastic_thread = (
            thread_name.startswith("Thread-") or  # Threads génériques Python
            thread_name == "MainThread" or         # Thread principal (heartbeat)
            thread_name.startswith("Dummy-")       # Threads dummy
        )
        
        # Ne filtrer que les erreurs réseau des threads Meshtastic
        if exc_type in network_errors and is_meshtastic_thread:
            # Logger en mode debug seulement
            if globals().get('DEBUG_MODE', False):
                debug_print(f"Thread {thread_name}: {exc_type.__name__} supprimé (thread Meshtastic)")
            # Ne PAS appeler le hook par défaut (pas de traceback)
            return
        
        # Pour toutes les autres exceptions ET tous les threads nommés, comportement normal
        original_excepthook(args)
    
    # Installer le hook personnalisé
    threading.excepthook = custom_threading_excepthook
    info_print("✅ Filtre d'exceptions threading installé (BrokenPipeError, ConnectionReset, etc.)")


# Installer automatiquement le filtre à l'import du module
install_threading_exception_filter()


if __name__ == "__main__":
    # Test du patch
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python tcp_interface_patch.py <hostname> [port]")
        sys.exit(1)
    
    hostname = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 4403
    
    info_print(f"🧪 Test OptimizedTCPInterface: {hostname}:{port}")
    
    try:
        interface = create_optimized_interface(hostname, port)
        info_print("✅ Interface créée")
        
        info_print("Attente 10 secondes...")
        time.sleep(10)
        
        interface.close()
        info_print("✅ Test terminé")
        
    except KeyboardInterrupt:
        info_print("\n🛑 Interruption utilisateur")
    except Exception as e:
        error_print(f"❌ Erreur test: {e}")
        import traceback
        error_print(traceback.format_exc())
