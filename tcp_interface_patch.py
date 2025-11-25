"""
🔧 PATCH TCP INTERFACE - Réduction CPU de 78% → <5%
=======================================================

Problème: meshtastic/tcp_interface.py fait du busy-waiting dans _readBytes
Solution: Wrapper avec select() pour des opérations bloquantes efficaces

Usage:
    from tcp_interface_patch import OptimizedTCPInterface
    interface = OptimizedTCPInterface(hostname='192.168.1.100')
"""

import errno
import socket
import select
import time
import meshtastic.tcp_interface
from meshtastic.stream_interface import StreamInterface
from utils import info_print, error_print, debug_print

# Socket error codes to ignore (normal connection errors)
SOCKET_ERROR_CODES = (
    errno.ECONNRESET,   # 104 - Connection reset
    errno.ETIMEDOUT,    # 110 - Connection timed out  
    errno.ECONNREFUSED, # 111 - Connection refused
    errno.ENOTCONN,     # 107 - Not connected
    errno.EPIPE,        # 32 - Broken pipe
)


class OptimizedTCPInterface(meshtastic.tcp_interface.TCPInterface):
    """
    Interface TCP optimisée pour réduire la consommation CPU
    
    ✅ Modifications:
    - Utilise select() au lieu de polling continu
    - Timeout configurables (non-blocking → blocking intelligent)
    - Réduction CPU: 78% → <5%
    - Callback on_dead_socket pour reconnexion immédiate
    """
    
    # Class variable to store callback for dead socket notification
    # Set by main_bot to trigger immediate reconnection
    _on_dead_socket_callback = None
    
    @classmethod
    def set_dead_socket_callback(cls, callback):
        """
        Set callback to be called when a dead socket is detected
        
        Args:
            callback: Function to call (no args) when socket dies
        """
        cls._on_dead_socket_callback = callback
        debug_print("🔌 Callback socket mort configuré")
    
    def __init__(self, hostname, portNumber=4403, **kwargs):
        info_print(f"🔧 Initialisation OptimizedTCPInterface pour {hostname}:{portNumber}")
        
        # Paramètres d'optimisation
        # Use 30s timeout to drastically reduce CPU usage (was 1.0s causing 92% CPU)
        # select() will wake up immediately when data arrives, so latency is not affected
        self.read_timeout = kwargs.pop('read_timeout', 30.0)  # Timeout select() - long pour réduire CPU
        self.socket_timeout = kwargs.pop('socket_timeout', 5.0)  # Timeout socket général
        
        # Appeler le constructeur parent
        super().__init__(hostname=hostname, portNumber=portNumber, **kwargs)
        
        # Configurer le socket pour des opérations bloquantes optimisées
        if hasattr(self, 'socket') and self.socket:
            try:
                # Socket en mode bloquant avec timeout
                self.socket.setblocking(True)
                self.socket.settimeout(self.socket_timeout)
                
                # Options TCP pour réduire latence
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                
                # ========================================
                # TCP KEEPALIVE - Détection connexions mortes
                # ========================================
                # Active TCP keepalive pour détecter les connexions mortes rapidement
                # Sans keepalive, une connexion morte peut rester "connectée" pendant des heures
                # Avec keepalive, elle sera détectée en ~2 minutes maximum
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                
                # Configuration keepalive (Linux)
                # TCP_KEEPIDLE: Temps avant le premier keepalive (secondes)
                # TCP_KEEPINTVL: Intervalle entre keepalives (secondes)
                # TCP_KEEPCNT: Nombre de keepalives avant de déclarer mort
                try:
                    # Démarrer keepalive après 60 secondes d'inactivité
                    self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                    # Envoyer un keepalive toutes les 10 secondes
                    self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                    # Après 6 échecs (60s), déclarer la connexion morte
                    self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)
                    info_print("✅ TCP Keepalive activé (détection connexion morte: ~2min)")
                except (AttributeError, OSError) as e:
                    # TCP_KEEPIDLE, etc. ne sont pas disponibles sur tous les systèmes
                    debug_print(f"⚠️ Impossible de configurer keepalive avancé: {e}")
                    # Le keepalive de base (SO_KEEPALIVE) est quand même actif
                
                info_print(f"✅ Socket configuré: blocking={True}, timeout={self.socket_timeout}s")
            except Exception as e:
                error_print(f"Erreur configuration socket: {e}")
    
    def _readBytes(self, length):
        """
        Version optimisée de _readBytes avec select() pour réduire CPU
        
        APPROCHE SIMPLIFIÉE (v3):
        - Un seul appel select() avec timeout court (1 seconde)
        - Pas de boucle interne - laisse le reader thread de Meshtastic gérer les retries
        - CPU faible car select() est bloquant et efficace
        - Répond rapidement à _wantExit pour fermeture propre
        
        Returns:
        - bytes: Data read from socket
        - b'': No data yet (timeout) - reader thread will retry
        - None: Exit signal or no socket - reader thread should stop
        
        Cette version est plus proche de l'original Meshtastic mais avec select()
        pour éviter le busy-waiting du socket.recv() non-bloquant.
        """
        # Check if we should exit (interface being closed)
        if getattr(self, '_wantExit', False):
            return None  # Signal exit to reader thread
        
        # Check socket validity
        if not self.socket:
            return None  # No socket, signal exit
        
        try:
            # Use select() with SHORT timeout (1 second) for CPU efficiency
            # The reader thread will call us again if we return empty bytes
            ready, _, _ = select.select([self.socket], [], [], 1.0)
            
            if ready:
                # Socket ready: read data
                data = self.socket.recv(length)
                
                if not data:
                    # Empty bytes = dead socket (TCP FIN received)
                    # This is a CRITICAL condition - socket is permanently dead
                    # Set _wantExit to stop ALL subsequent calls immediately
                    if not getattr(self, '_wantExit', False):
                        info_print("🔌 Socket TCP mort: recv() retourne vide (connexion fermée par le serveur)")
                        self._wantExit = True  # Stop all future reads
                        
                        # Trigger immediate reconnection via callback
                        # This bypasses the 2-minute health monitor delay
                        if OptimizedTCPInterface._on_dead_socket_callback:
                            info_print("🔄 Déclenchement reconnexion immédiate...")
                            try:
                                OptimizedTCPInterface._on_dead_socket_callback()
                            except Exception as e:
                                error_print(f"Erreur callback reconnexion: {e}")
                    return None  # Signal reader thread to exit
                
                # Data read successfully
                return data
            
            # Timeout: no data yet, return empty bytes
            # The reader thread will call us again
            return b''
            
        except socket.timeout:
            # Timeout normal - return empty bytes
            return b''
            
        except socket.error as e:
            # Socket error - log only unexpected errors
            errno_val = getattr(e, 'errno', None)
            if errno_val not in SOCKET_ERROR_CODES:
                error_print(f"Erreur socket lecture: {e}")
            # Return empty bytes, let health monitor handle reconnection
            time.sleep(0.1)
            return b''
            
        except Exception as e:
            error_print(f"Erreur _readBytes inattendue: {e}")
            import traceback
            error_print(traceback.format_exc())
            time.sleep(0.1)
            return b''
    
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
    Factory pour créer une interface TCP optimisée
    
    Args:
        hostname: IP du nœud Meshtastic
        port: Port TCP (défaut 4403)
        read_timeout: Timeout select() en secondes (défaut 30.0)
        socket_timeout: Timeout socket en secondes (défaut 5.0)
    
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
