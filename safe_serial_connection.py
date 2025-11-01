#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire de connexion série Meshtastic avec reconnexion automatique - VERSION 2.1
✅ CORRECTIF DEADLOCK: Thread monitoring démarré après libération du lock

Version améliorée qui:
- Surveille activement l'état du port série
- S'abonne aux événements Meshtastic
- Détecte les exceptions lors de l'envoi
- Vérifie périodiquement la santé de la connexion
- ✅ FIX: Pas de deadlock au démarrage
"""

import time
import threading
import meshtastic.serial_interface
from utils import debug_print, error_print, info_print


class SafeSerialConnection:
    """
    Gestionnaire de connexion série Meshtastic avec reconnexion automatique v2.1
    
    Améliorations par rapport à v2:
    - ✅ CORRECTIF DEADLOCK: Le thread de monitoring démarre après libération du lock
    - Détection active des déconnexions (teste le port série)
    - Surveillance plus fréquente
    - Meilleure gestion des erreurs d'envoi
    - Abonnement aux événements Meshtastic
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
        self._disconnect_detected = False
        
    def _on_meshtastic_connection_lost(self, interface, reason=None):
        """Callback appelé par Meshtastic quand la connexion est perdue"""
        info_print(f"🔌 Meshtastic signale une déconnexion: {reason}")
        with self._lock:
            if self._connected:
                error_print("⚠️  Déconnexion détectée par Meshtastic")
                self._connected = False
                self._disconnect_detected = True
                self._connection_lost_time = time.time()
                self._retry_count = 0
        
    def connect(self):
        """Établir la connexion série initiale - ✅ VERSION CORRIGÉE"""
        connection_success = False
        
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
                    
                    # S'abonner aux événements de déconnexion
                    try:
                        from pubsub import pub
                        pub.subscribe(self._on_meshtastic_connection_lost, "meshtastic.connection.lost")
                        debug_print("✅ Abonné aux événements Meshtastic")
                    except Exception as e:
                        debug_print(f"⚠️  Impossible de s'abonner: {e}")
                    
                    # Vérifier que l'interface est fonctionnelle
                    if self._test_connection():
                        self._connected = True
                        self._disconnect_detected = False
                        self._retry_count = 0
                        info_print(f"✅ Connexion série établie: {self.port}")
                        connection_success = True
                        break  # ✅ Sortir de la boucle de tentatives
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
            
            if not connection_success:
                error_print(f"❌ Impossible de se connecter après {self.max_retries} tentatives")
                return False
        
        # ✅ CRITIQUE: Démarrer la surveillance APRÈS avoir relâché le lock
        # Cela évite le deadlock car le thread de monitoring peut maintenant
        # appeler is_connected() sans conflit de lock
        if connection_success and self.auto_reconnect and not self._reconnect_thread:
            self._start_monitor()
        
        return connection_success
    
    def _test_connection(self):
        """Tester si la connexion est vraiment fonctionnelle"""
        if not self.interface:
            return False
        
        try:
            # Test 1: Attributs de base
            if not hasattr(self.interface, 'myInfo'):
                return False
            
            # Test 2: Port série sous-jacent
            if hasattr(self.interface, '_stream'):
                stream = self.interface._stream
                if hasattr(stream, 'is_open') and not stream.is_open:
                    return False
                
                # Vérifier que le port existe
                if hasattr(stream, 'port'):
                    import os
                    if not os.path.exists(stream.port):
                        return False
            
            # Test 3: Méthode isConnected si disponible
            if hasattr(self.interface, 'isConnected'):
                if callable(self.interface.isConnected):
                    return self.interface.isConnected()
                else:
                    return self.interface.isConnected
            
            return True
            
        except Exception as e:
            debug_print(f"Test connexion échoué: {e}")
            return False
    
    def get_interface(self):
        """Obtenir l'interface série (reconnecte si nécessaire)"""
        with self._lock:
            if not self._connected or not self.interface or self._disconnect_detected:
                info_print("Interface non connectée, tentative de reconnexion...")
                self.connect()
            
            return self.interface if self._connected else None
    
    def is_connected(self):
        """Vérifier si la connexion est active"""
        with self._lock:
            # Vérification rapide de l'état
            if not self._connected or not self.interface:
                return False
            
            # Si déconnexion détectée, retourner False
            if self._disconnect_detected:
                return False
            
            # Test périodique (max 1x par seconde)
            current_time = time.time()
            if not hasattr(self, '_last_test_time'):
                self._last_test_time = 0
            
            if current_time - self._last_test_time > 1.0:
                self._last_test_time = current_time
                if not self._test_connection():
                    self._connected = False
                    self._disconnect_detected = True
                    return False
            
            return True
    
    def _start_monitor(self):
        """Démarrer le thread de surveillance"""
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
        """Thread de surveillance - vérifie activement la connexion"""
        check_interval = 2  # Vérifier toutes les 2 secondes
        
        while not self._stop_reconnect:
            time.sleep(check_interval)
            
            try:
                # Vérifier l'état de la connexion
                connected = self.is_connected()
                
                # Si déconnecté et auto-reconnect activé
                if not connected and self.auto_reconnect:
                    with self._lock:
                        if not self._connected or self._disconnect_detected:
                            self._retry_count += 1
                            
                            if self._retry_count == 1:
                                error_print("⚠️  Connexion série perdue détectée par le moniteur")
                                if not self._connection_lost_time:
                                    self._connection_lost_time = time.time()
                    
                    info_print(f"🔄 Tentative de reconnexion #{self._retry_count}...")
                    
                    # Relâcher le lock pendant la reconnexion
                    if self.connect():
                        if self._connection_lost_time:
                            downtime = time.time() - self._connection_lost_time
                            info_print(f"✅ Reconnexion réussie après {downtime:.1f}s d'interruption")
                            self._connection_lost_time = None
                    else:
                        # Backoff exponentiel
                        delay = min(self.retry_delay * (2 ** min(self._retry_count, 5)), self.max_retry_delay)
                        info_print(f"⏱️  Prochaine tentative dans {delay}s...")
                        time.sleep(delay - check_interval)
                
            except Exception as e:
                error_print(f"Erreur dans le thread de surveillance: {e}")
    
    def close(self):
        """Fermer proprement la connexion série"""
        info_print("🔌 Fermeture connexion série...")
        
        # Arrêter la surveillance
        self._stop_reconnect = True
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=2)
        
        # Se désabonner des événements
        try:
            from pubsub import pub
            pub.unsubscribe(self._on_meshtastic_connection_lost, "meshtastic.connection.lost")
        except:
            pass
        
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
        """Destructeur"""
        self.close()


# ========================================
# FONCTIONS HELPER
# ========================================

def test_serial_connection(port, timeout=10):
    """Tester rapidement une connexion série"""
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
        print("Usage: python3 safe_serial_connection.py <port>")
        print("Exemple: python3 safe_serial_connection.py /dev/ttyACM0")
        sys.exit(1)
    
    port = sys.argv[1]
    
    print(f"\n🧪 Test SafeSerialConnection v2.1 sur {port}...\n")
    
    manager = SafeSerialConnection(port, auto_reconnect=True)
    
    if manager.connect():
        print(f"✅ Connexion établie")
        print(f"État: {'Connecté' if manager.is_connected() else 'Déconnecté'}")
        
        print("\n⏱️  Surveillance active pendant 60s...")
        print("💡 Débranchez/rebranchez le câble pour tester la reconnexion\n")
        
        for i in range(60):
            time.sleep(1)
            status = "🟢 Connecté" if manager.is_connected() else "🔴 Déconnecté"
            print(f"[{i+1:2d}/60] {status}", end='\r')
        
        print(f"\n\nTest terminé")
        manager.close()
    else:
        print("❌ Échec de connexion")
