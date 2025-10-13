import time
import threading
import meshtastic.tcp_interface
from config import *
from utils import *

class TigroG2TrafficBridge:
    """
    Bridge corrigé avec gestion CPU optimisée
    
    ✅ FIX : tcp_interface initialisé dans __init__
    ✅ FIX : Sleep 500ms entre lectures
    ✅ FIX : Gestion propre des erreurs
    """
    
    def __init__(self, traffic_monitor=None, node_manager=None, **kwargs):
        """Initialisation avec TOUS les attributs"""
        self.traffic_monitor = traffic_monitor
        self.node_manager = node_manager
        self.running = False
        self.thread = None
        self.tcp_interface = None  # ✅ FIX CRITIQUE
        
        # Configuration CPU-friendly
        self.read_interval = 0.5  # 500ms entre lectures
        self.reconnect_delay = 30  # 30s avant reconnexion
        self.connection_timeout = 10
        
        # Stats
        self.packets_received = 0
        self.last_packet_time = 0
        self.connection_errors = 0
        
        info_print("✅ TigroG2TrafficBridge initialisé")
    
    def start(self):
        """Démarrer le bridge"""
        if self.running:
            debug_print("⚠️ Bridge déjà démarré")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._bridge_loop, daemon=True)
        self.thread.start()
        info_print("🔗 Bridge tigrog2 démarré")
    
    def stop(self):
        """Arrêter le bridge"""
        info_print("🛑 Arrêt du bridge...")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        if self.tcp_interface:  # ✅ Vérifier avant d'utiliser
            try:
                self.tcp_interface.close()
            except:
                pass
            self.tcp_interface = None
        
        info_print("✅ Bridge arrêté")
    
    def _bridge_loop(self):
        """
        Boucle principale CORRIGÉE
        
        ✅ FIX : Vérification de tcp_interface avant utilisation
        ✅ FIX : Sleep 500ms pour éviter 400% CPU
        """
        while self.running:
            try:
                # Connexion si nécessaire
                if self.tcp_interface is None:  # ✅ Vérification explicite
                    self._connect()
                
                # ✅ CRITIQUE : Sleep pour éviter CPU infini
                time.sleep(self.read_interval)
                
                if not self.running:
                    break
                
                # Traiter les packets
                if self.tcp_interface is not None:  # ✅ Vérifier avant d'utiliser
                    self._process_packets()
                
            except KeyboardInterrupt:
                break
                
            except Exception as e:
                error_print(f"❌ Erreur bridge loop: {e}")
                import traceback
                error_print(traceback.format_exc())
                
                self.connection_errors += 1
                
                # Cleanup
                self._disconnect()
                
                # ✅ Attendre avant de réessayer
                if self.running:
                    debug_print(f"⏳ Attente {self.reconnect_delay}s...")
                    time.sleep(self.reconnect_delay)
        
        # Cleanup final
        self._disconnect()
    
    def _connect(self):
        """Établir la connexion TCP"""
        try:
            debug_print(f"🔌 Connexion à {REMOTE_NODE_HOST}...")
            
            # ✅ Créer la connexion
            self.tcp_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )
            
            # Laisser le temps de s'initialiser
            time.sleep(3)
            
            info_print(f"✅ Connecté à {REMOTE_NODE_HOST}")
            self.connection_errors = 0
            
        except Exception as e:
            error_print(f"❌ Erreur connexion: {e}")
            self.tcp_interface = None  # ✅ Reset en cas d'erreur
            raise
    
    def _disconnect(self):
        """Déconnecter proprement"""
        if self.tcp_interface is not None:  # ✅ Vérifier avant
            try:
                self.tcp_interface.close()
                debug_print("🔌 Déconnecté")
            except Exception as e:
                debug_print(f"Erreur fermeture: {e}")
            finally:
                self.tcp_interface = None  # ✅ Toujours reset
    
    def _process_packets(self):
        """Traiter les packets reçus"""
        if self.tcp_interface is None:  # ✅ Vérification de sécurité
            return
        
        try:
            # Votre logique de traitement ici
            # Exemple simple : compter les nœuds
            if hasattr(self.tcp_interface, 'nodes'):
                node_count = len(self.tcp_interface.nodes)
                
                # Log périodique
                if self.packets_received % 100 == 0:
                    debug_print(f"📊 Bridge: {node_count} nœuds, {self.packets_received} packets")
            
            self.packets_received += 1
            self.last_packet_time = time.time()
            
        except Exception as e:
            debug_print(f"Erreur traitement: {e}")
    
    def get_stats(self):
        """Stats du bridge"""
        return {
            'running': self.running,
            'connected': self.tcp_interface is not None,
            'packets': self.packets_received,
            'errors': self.connection_errors
        }

