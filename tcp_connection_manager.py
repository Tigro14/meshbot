iimport time
import threading
import meshtastic.tcp_interface
from contextlib import contextmanager
from utils import debug_print, error_print

class TCPConnectionManager:
    def __init__(self):
        self.active_connections = []
        self.lock = threading.Lock()
    
    @contextmanager
    def get_connection(self, hostname, port=4403, timeout=30):
        """Context manager pour connexion TCP avec timeout et nettoyage garanti"""
        connection = None
        timer = None
        
        try:
            debug_print(f"Ouverture connexion TCP vers {hostname}:{port}")
            
            # Créer la connexion
            connection = meshtastic.tcp_interface.TCPInterface(
                hostname=hostname,
                portNumber=port
            )
            
            # Ajouter à la liste des connexions actives
            with self.lock:
                self.active_connections.append(connection)
            
            # Timer de timeout pour forcer la fermeture
            def force_close():
                if connection in self.active_connections:
                    error_print(f"⚠️ Timeout connexion {hostname} - fermeture forcée")
                    try:
                        connection.close()
                    except:
                        pass
            
            timer = threading.Timer(timeout, force_close)
            timer.start()
            
            # Attendre l'initialisation
            time.sleep(2)
            
            yield connection
            
        except Exception as e:
            error_print(f"Erreur connexion TCP {hostname}: {e}")
            raise
        finally:
            # Annuler le timer
            if timer:
                timer.cancel()
            
            # Fermer la connexion
            if connection:
                try:
                    debug_print(f"Fermeture connexion {hostname}")
                    connection.close()
                except Exception as e:
                    error_print(f"Erreur fermeture: {e}")
                
                # Retirer de la liste
                with self.lock:
                    if connection in self.active_connections:
                        self.active_connections.remove(connection)
    
    def cleanup_all(self):
        """Fermer toutes les connexions actives"""
        with self.lock:
            for conn in self.active_connections[:]:
                try:
                    conn.close()
                except:
                    pass
            self.active_connections.clear()

# Instance globale
tcp_manager = TCPConnectionManager()
