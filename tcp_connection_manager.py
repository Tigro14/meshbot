# tcp_connection_manager.py - Version améliorée
import queue
import time

class TCPConnectionPool:
    """Pool de connexions réutilisables pour éviter les reconnexions"""
    
    def __init__(self, hostname, port=4403, max_connections=3):
        self.hostname = hostname
        self.port = port
        self.max_connections = max_connections
        self.pool = queue.Queue(maxsize=max_connections)
        self.active_count = 0
        self.lock = threading.Lock()
        
    def get_connection(self, timeout=30):
        """Obtenir une connexion du pool"""
        try:
            # Essayer de récupérer une connexion existante
            conn, created_at = self.pool.get_nowait()
            
            # Vérifier qu'elle n'est pas trop vieille (max 5 min)
            if time.time() - created_at > 300:
                try:
                    conn.close()
                except:
                    pass
                raise queue.Empty()
                
            return conn
            
        except queue.Empty:
            # Créer une nouvelle connexion
            with self.lock:
                if self.active_count >= self.max_connections:
                    raise Exception("Pool de connexions saturé")
                self.active_count += 1
            
            conn = meshtastic.tcp_interface.TCPInterface(
                hostname=self.hostname,
                portNumber=self.port
            )
            time.sleep(2)
            return conn
    
    def return_connection(self, conn):
        """Remettre une connexion dans le pool"""
        try:
            self.pool.put_nowait((conn, time.time()))
        except queue.Full:
            # Pool plein, fermer la connexion
            try:
                conn.close()
            except:
                pass
        finally:
            with self.lock:
                self.active_count -= 1
    
    def close_all(self):
        """Fermer toutes les connexions"""
        while not self.pool.empty():
            try:
                conn, _ = self.pool.get_nowait()
                conn.close()
            except:
                pass
        self.active_count = 0

# Pool global pour tigrog2
tigrog2_pool = TCPConnectionPool(REMOTE_NODE_HOST)
