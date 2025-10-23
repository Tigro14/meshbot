#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire de connexion série Meshtastic avec reconnexion automatique

Ce module fournit:
1. SafeSerialConnection: Gestionnaire de connexion série avec auto-reconnexion
2. Protection contre les déconnexions/reconnexions USB
3. Retry automatique avec backoff exponentiel
4. Logging détaillé des événements de connexion

Exemples d'utilisation:
    # Initialisation
    serial_manager = SafeSerialConnection("/dev/ttyACM0")
    
    # Obtenir l'interface (reconnecte automatiquement si nécessaire)
    interface = serial_manager.get_interface()
    if interface:
        interface.sendText("Hello!")
    
    # Vérifier l'état
    if serial_manager.is_connected():
        print("Connecté!")
    
    # Fermeture propre
    serial_manager.close()
"""

import time
import threading
import meshtastic.serial_interface
from utils import debug_print, error_print, info_print


class SafeSerialConnection:
    """
    Gestionnaire de connexion série Meshtastic avec reconnexion automatique
    
    Gère automatiquement:
    - La connexion initiale avec retry
    - La détection de déconnexion
    - La reconnexion automatique
    - Le backoff exponentiel en cas d'échecs répétés
    - Le threading pour la surveillance
    
    Args:
        port (str): Port série (ex: "/dev/ttyACM0")
        max_retries (int): Nombre max de tentatives de connexion (défaut: 5)
        retry_delay (int): Délai initial entre tentatives en secondes (défaut: 5)
        max_retry_delay (int): Délai max entre tentatives (défaut: 60)
        auto_reconnect (bool): Activer la reconnexion automatique (défaut: True)
    """
    
    def __init__(self, port, max_retries=5, retry_delay=5, max_retry_delay=60, auto_reconnect=True):
        self.port = port
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay
        self.auto_reconnect = auto_reconnect
        
        self.interface = None
        self._connected = False
        self._lock = threading.Lock()
        self._reconnect_thread = None
        self._stop_reconnect = False
        self._connection_lost_time = None
        self._retry_count = 0
        
    def connect(self):
        """
        Établir la connexion série initiale
        
        Returns:
            bool: True si connexion réussie, False sinon
        """
        with self._lock:
            if self._connected and self.interface:
                debug_print("Déjà connecté")
                return True
            
            for attempt in range(1, self.max_retries + 1):
                try:
                    info_print(f"🔌 Tentative connexion série {attempt}/{self.max_retries}: {self.port}")
                    
                    # Fermer toute connexion existante
                    if self.interface:
                        try:
                            self.interface.close()
                        except:
                            pass
                        self.interface = None
                    
                    # Nouvelle connexion
                    self.interface = meshtastic.serial_interface.SerialInterface(self.port)
                    time.sleep(3)  # Attendre stabilisation
                    
                    # Vérifier que l'interface est fonctionnelle
                    if self.interface and hasattr(self.interface, 'myInfo'):
                        self._connected = True
                        self._retry_count = 0
                        info_print(f"✅ Connexion série établie: {self.port}")
                        
                        # Démarrer la surveillance si auto-reconnect activé
                        if self.auto_reconnect and not self._reconnect_thread:
                            self._start_monitor()
                        
                        return True
                    else:
                        info_print(f"Interface créée mais non fonctionnelle (tentative {attempt})")
                        
                except Exception as e:
                    error_print(f"❌ Échec connexion série (tentative {attempt}/{self.max_retries}): {e}")
                    self.interface = None
                    self._connected = False
                    
                    if attempt < self.max_retries:
                        delay = min(self.retry_delay * attempt, self.max_retry_delay)
                        info_print(f"⏱️  Nouvelle tentative dans {delay}s...")
                        time.sleep(delay)
            
            error_print(f"❌ Impossible de se connecter après {self.max_retries} tentatives")
            return False
    
    def get_interface(self):
        """
        Obtenir l'interface série (reconnecte si nécessaire)
        
        Returns:
            SerialInterface: Interface Meshtastic ou None si déconnecté
        """
        with self._lock:
            if not self._connected or not self.interface:
                info_print("Interface non connectée, tentative de reconnexion...")
                self.connect()
            
            return self.interface if self._connected else None
    
    def is_connected(self):
        """
        Vérifier si la connexion est active
        
        Returns:
            bool: True si connecté, False sinon
        """
        return self._connected and self.interface is not None
    
    def _start_monitor(self):
        """Démarrer le thread de surveillance de la connexion"""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        
        self._stop_reconnect = False
        self._reconnect_thread = threading.Thread(
            target=self._monitor_connection,
            daemon=True,
            name="SerialMonitor"
        )
        self._reconnect_thread.start()
        debug_print("🔍 Surveillance de connexion série démarrée")
    
    def _monitor_connection(self):
        """Thread de surveillance - détecte les déconnexions et reconnecte"""
        check_interval = 10  # Vérifier toutes les 10 secondes
        
        while not self._stop_reconnect:
            time.sleep(check_interval)
            
            try:
                with self._lock:
                    # Vérifier si la connexion est toujours active
                    if self._connected and self.interface:
                        try:
                            # Test simple: vérifier que l'interface répond
                            if not hasattr(self.interface, 'myInfo'):
                                raise Exception("Interface non fonctionnelle")
                        except Exception as e:
                            # Connexion perdue
                            error_print(f"⚠️  Connexion série perdue: {e}")
                            self._connected = False
                            self._connection_lost_time = time.time()
                            self._retry_count = 0
                    
                    # Tenter de reconnexion si déconnecté
                    if not self._connected and self.auto_reconnect:
                        self._retry_count += 1
                        info_print(f"🔄 Tentative de reconnexion #{self._retry_count}...")
                        
                        if self.connect():
                            if self._connection_lost_time:
                                downtime = time.time() - self._connection_lost_time
                                info_print(f"✅ Reconnexion réussie après {downtime:.1f}s d'interruption")
                                self._connection_lost_time = None
                        else:
                            # Backoff exponentiel
                            delay = min(self.retry_delay * (2 ** min(self._retry_count, 5)), self.max_retry_delay)
                            info_print(f"⏱️  Prochaine tentative dans {delay}s...")
                            time.sleep(delay - check_interval)  # Compenser le sleep du while
                            
            except Exception as e:
                error_print(f"Erreur dans le thread de surveillance: {e}")
    
    def close(self):
        """Fermer proprement la connexion série"""
        info_print("🔌 Fermeture connexion série...")
        
        # Arrêter la surveillance
        self._stop_reconnect = True
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=2)
        
        with self._lock:
            if self.interface:
                try:
                    self.interface.close()
                    info_print("✅ Connexion série fermée")
                except Exception as e:
                    error_print(f"Erreur fermeture connexion: {e}")
                finally:
                    self.interface = None
                    self._connected = False
    
    def __del__(self):
        """Destructeur - fermer la connexion si oubliée"""
        self.close()


# ========================================
# FONCTIONS HELPER
# ========================================

def test_serial_connection(port, timeout=10):
    """
    Tester rapidement une connexion série
    
    Args:
        port (str): Port série à tester
        timeout (int): Timeout en secondes
        
    Returns:
        tuple: (success: bool, message: str, elapsed: float)
    """
    start = time.time()
    try:
        info_print(f"🧪 Test connexion série: {port}")
        interface = meshtastic.serial_interface.SerialInterface(port)
        time.sleep(3)
        
        if hasattr(interface, 'myInfo'):
            elapsed = time.time() - start
            interface.close()
            return True, f"✅ Connexion OK ({elapsed:.2f}s)", elapsed
        else:
            elapsed = time.time() - start
            interface.close()
            return False, "❌ Interface non fonctionnelle", elapsed
            
    except Exception as e:
        elapsed = time.time() - start
        return False, f"❌ Erreur: {str(e)[:100]}", elapsed


if __name__ == "__main__":
    """Tests du module"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python safe_serial_connection.py <port>")
        print("Exemple: python safe_serial_connection.py /dev/ttyACM0")
        sys.exit(1)
    
    port = sys.argv[1]
    
    print(f"\n🧪 Test de connexion série sur {port}...\n")
    success, msg, elapsed = test_serial_connection(port)
    print(f"{msg}\n")
    
    if success:
        print("🔄 Test avec SafeSerialConnection...")
        manager = SafeSerialConnection(port)
        
        if manager.connect():
            print(f"✅ Connexion établie")
            print(f"État: {'Connecté' if manager.is_connected() else 'Déconnecté'}")
            
            print("\n⏱️  Attente 10s (déconnectez le câble pour tester)...")
            time.sleep(10)
            
            print(f"État après 10s: {'Connecté' if manager.is_connected() else 'Déconnecté'}")
            
            manager.close()
        else:
            print("❌ Échec de connexion")
