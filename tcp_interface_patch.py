"""
🔧 PATCH TCP INTERFACE - Dead Socket Callback for Fast Reconnection
====================================================================

PURPOSE:
    Wrapper for Meshtastic TCP connections (port 4403) that adds a dead socket
    callback for immediate reconnection notification.
    
    This module is SPECIFICALLY for Meshtastic protocol communication.
    
    For other services (HTTP, MQTT), use their respective libraries:
    - ESPHome: requests library (esphome_client.py)
    - Weather: curl subprocess (utils_weather.py)  
    - Blitzortung: paho-mqtt library (blitz_monitor.py)

PROBLEM:
    When the Meshtastic node closes the TCP connection, the standard TCPInterface
    takes ~60+ seconds (health monitor timeout) to detect and reconnect.

SOLUTION:
    We extend TCPInterface with a dead socket callback that triggers immediate
    reconnection when recv() returns empty bytes. This reduces downtime from
    ~75 seconds to ~10 seconds.

IMPORTANT - CPU USAGE NOTE:
    After extensive testing, we found that ANY modification to socket behavior
    (select(), timeouts, TCP_NODELAY, keepalive) causes the ESP32-based
    Meshtastic node to close connections prematurely.
    
    Therefore, this implementation uses the EXACT same blocking recv() approach
    as the standard TCPInterface. CPU usage may be higher, but stability is
    more important. If CPU becomes a problem, investigate upstream in the
    meshtastic library.

ARCHITECTURE:
    See TCP_ARCHITECTURE.md for full documentation on the network stack design.
    
    OptimizedTCPInterface (this file)
        └── Used directly for long-lived main connections (main_bot.py)
        └── Adds dead socket callback for immediate reconnection
        
    SafeTCPConnection (safe_tcp_connection.py)
        └── Context manager wrapper using OptimizedTCPInterface
        └── Used for temporary queries (remote_nodes_client.py)

USAGE:
    from tcp_interface_patch import OptimizedTCPInterface
    interface = OptimizedTCPInterface(hostname='192.168.1.100')
    interface.set_dead_socket_callback(my_reconnect_function)
    
    # Or via factory function:
    interface = create_optimized_interface(hostname='192.168.1.100')
"""

import socket
import time
import threading
import meshtastic.tcp_interface
from meshtastic.stream_interface import StreamInterface
from utils import info_print, error_print, debug_print


class OptimizedTCPInterface(meshtastic.tcp_interface.TCPInterface):
    """
    Meshtastic TCPInterface with dead socket callback for fast reconnection.
    
    This class is nearly IDENTICAL to the standard meshtastic.tcp_interface.TCPInterface.
    The ONLY addition is a dead socket callback that triggers immediate reconnection
    when the socket is detected as dead.
    
    IMPORTANT: After extensive testing, we found that ANY modification to socket
    behavior (select(), timeouts, TCP_NODELAY, keepalive) causes the ESP32-based
    Meshtastic node to close connections prematurely. Therefore, we use the
    EXACT same blocking recv() approach as the standard TCPInterface.
    
    ✅ What this class adds:
    - Dead socket callback for immediate reconnection notification
    
    ❌ What this class does NOT modify:
    - Socket configuration (timeout, TCP_NODELAY, keepalive)
    - The read approach (uses standard blocking recv())
    """
    
    def __init__(self, hostname, portNumber=4403, **kwargs):
        info_print(f"🔧 Initialisation OptimizedTCPInterface pour {hostname}:{portNumber}")
        
        # Callback for dead socket detection - allows immediate reconnection
        # instead of waiting for the health monitor to detect silence
        self._dead_socket_callback = None
        # Prevent multiple callback invocations for the same dead socket.
        # This flag is NOT reset because once a socket is dead, this interface
        # instance is replaced by a new one during reconnection.
        self._callback_triggered = False
        
        # Call the parent constructor - this creates the socket and connects
        # IMPORTANT: We do NOT modify the socket in any way after this
        super().__init__(hostname=hostname, portNumber=portNumber, **kwargs)
    
    def set_dead_socket_callback(self, callback):
        """
        Set a callback to be invoked when the socket is detected as dead.
        
        This allows the main bot to immediately trigger reconnection when
        recv() returns empty bytes (connection closed by server), instead of
        waiting for the health monitor to detect silence after 60s.
        
        Args:
            callback: Function to call when socket is dead (no arguments)
        """
        self._dead_socket_callback = callback
        debug_print("✅ Callback socket mort configuré")
    
    def _readBytes(self, length):
        """
        Read bytes from the TCP socket - MATCHES standard TCPInterface exactly.
        
        CRITICAL: After extensive testing, we found that ANY modification to socket
        behavior (select(), timeouts, TCP_NODELAY, keepalive) causes the ESP32-based
        Meshtastic node to close connections prematurely.
        
        This implementation is now IDENTICAL to the standard meshtastic.tcp_interface.TCPInterface._readBytes(),
        with one addition: a callback for immediate dead socket notification.
        
        The standard TCPInterface uses simple blocking recv() which works reliably.
        We keep only the dead socket callback for faster reconnection response.
        
        CPU Usage Note:
        The standard TCPInterface does have higher CPU usage due to blocking recv().
        However, stability is more important than CPU optimization. If CPU usage
        becomes a problem, the solution should be investigated upstream in the
        meshtastic library, not in a monkey-patch.
        """
        if self.socket is None:
            # No socket, break reader thread (matches standard behavior)
            self._wantExit = True
            return None
        
        try:
            # Simple blocking recv - EXACTLY like standard TCPInterface
            data = self.socket.recv(length)
            
            if data == b'':
                # Connection closed by server - empty bytes means dead socket
                # Log ONCE and trigger callback for immediate reconnection
                if not getattr(self, '_socket_dead_logged', False):
                    info_print("🔌 Socket TCP mort: recv() retourne vide (connexion fermée par le serveur)")
                    self._socket_dead_logged = True
                    
                    # Trigger callback for immediate reconnection
                    # This is the ONLY addition to standard behavior
                    if self._dead_socket_callback and not self._callback_triggered:
                        self._callback_triggered = True
                        info_print("🔄 Déclenchement reconnexion immédiate via callback...")
                        try:
                            # Call in a separate thread to avoid blocking the reader
                            threading.Thread(
                                target=self._dead_socket_callback,
                                name="DeadSocketCallback",
                                daemon=True
                            ).start()
                        except Exception as e:
                            error_print(f"Erreur callback socket mort: {e}")
                
                # Return None like the standard implementation does
                # The standard implementation also does reconnection logic here,
                # but we let the callback handle reconnection externally
                return None
            
            return data
            
        except socket.error as e:
            # Socket error - log only for non-common errors
            if hasattr(e, 'errno') and e.errno not in (104, 110, 111):  # Connection reset, timeout, refused
                error_print(f"Erreur socket lors de la lecture: {e}")
            return None
            
        except Exception as e:
            error_print(f"Erreur _readBytes: {e}")
            import traceback
            error_print(traceback.format_exc())
            return None
    
    def close(self):
        """Fermeture propre avec logs"""
        try:
            info_print("Fermeture OptimizedTCPInterface...")
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
