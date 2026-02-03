#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire de connexion série Meshtastic avec reconnexion automatique - VERSION 2.4.1
✅ Logs optimisés: Moins verbeux en production
✅ NOUVEAU v2.4.1: Correction du problème de self-locking

Améliorations v2.4.1:
- Détection et correction du self-locking (le bot se verrouille lui-même)
- Fermeture forcée de l'interface existante si on se bloque soi-même
- Délai de stabilisation après fermeture forcée

Améliorations v2.4.0:
- Vérification si le port est verrouillé par un autre processus
- Attente automatique de la libération du port
- Identification du processus bloquant pour diagnostic
- Correction de l'erreur "Resource temporarily unavailable"

Améliorations v2.3.1:
- Logs techniques en debug_print (visibles uniquement en mode DEBUG)
- Seuls les événements importants restent en info_print
"""

import os
import time
import fcntl
import threading
import errno
import meshtastic.serial_interface
from utils import debug_print, error_print, info_print, debug_print_mt, info_print_mt


class SafeSerialConnection:
    """
    Gestionnaire de connexion série Meshtastic avec reconnexion automatique v2.4.1
    
    v2.4.1: Correction du self-locking
    - Détection du verrouillage par le bot lui-même
    - Fermeture forcée de l'interface existante
    - Délai de stabilisation augmenté
    
    v2.4.0: Gestion du verrouillage du port
    - Vérification avant connexion
    - Attente automatique de libération
    - Diagnostic des processus bloquants
    
    v2.3.1: Logs optimisés pour production
    - info_print: Événements importants uniquement
    - debug_print: Détails techniques
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
        
        self._is_reconnecting = False
        self._subscribed_to_events = False
        self._last_connect_time = 0
        self._grace_period = 5.0
        
    def _on_meshtastic_connection_lost(self, interface, reason=None):
        if interface != self.interface:
            return  # Ignore si ce n'est pas NOTRE interface série
        """Callback appelé par Meshtastic quand la connexion est perdue"""
        if self._is_reconnecting:
            debug_print_mt(f"Événement de déconnexion ignoré (reconnexion en cours)")
            return
        
        time_since_connect = time.time() - self._last_connect_time
        if time_since_connect < self._grace_period:
            debug_print_mt(f"Événement de déconnexion ignoré (période de grâce: {time_since_connect:.1f}s/{self._grace_period}s)")
            return
        
        debug_print_mt(f"🔌 Meshtastic signale une déconnexion: {reason}")
        with self._lock:
            if self._connected:
                error_print("⚠️  Déconnexion série détectée")
                self._connected = False
                self._disconnect_detected = True
                self._connection_lost_time = time.time()
                self._retry_count = 0
    
    def _unsubscribe_events(self):
        """Désabonner proprement des événements"""
        if self._subscribed_to_events:
            try:
                from pubsub import pub
                pub.unsubscribe(self._on_meshtastic_connection_lost, "meshtastic.connection.lost")
                self._subscribed_to_events = False
                debug_print_mt("✅ Désabonné des événements Meshtastic")
            except Exception as e:
                debug_print_mt(f"⚠️  Erreur désabonnement: {e}")
    
    def _subscribe_events(self):
        """S'abonner aux événements de déconnexion"""
        if not self._subscribed_to_events:
            try:
                from pubsub import pub
                pub.subscribe(self._on_meshtastic_connection_lost, "meshtastic.connection.lost")
                self._subscribed_to_events = True
                debug_print_mt("✅ Abonné aux événements Meshtastic")
            except Exception as e:
                debug_print_mt(f"⚠️  Impossible de s'abonner: {e}")
    
    # ========================================
    # NOUVELLES MÉTHODES v2.4.0
    # ========================================
    
    def _is_port_locked(self):
        """
        Vérifier si le port série est verrouillé par un autre processus
        
        Returns:
            bool: True si le port est verrouillé, False sinon
        """
        # Vérifier d'abord si le port existe
        if not os.path.exists(self.port):
            debug_print_mt(f"Port {self.port} n'existe pas")
            return False
        
        try:
            # Essayer d'ouvrir le port en mode non-bloquant
            fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            
            try:
                # Essayer d'obtenir un verrou exclusif non-bloquant
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Si on arrive ici, le port n'était pas verrouillé
                fcntl.flock(fd, fcntl.LOCK_UN)  # Libérer le verrou
                os.close(fd)
                return False
                
            except BlockingIOError:
                # Le port est verrouillé par un autre processus
                os.close(fd)
                return True
                
            except Exception as e:
                debug_print_mt(f"Erreur lors du test de verrouillage: {e}")
                os.close(fd)
                return False
                
        except PermissionError:
            debug_print_mt(f"Pas de permissions pour accéder à {self.port}")
            return False
            
        except Exception as e:
            debug_print_mt(f"Erreur lors de l'ouverture du port: {e}")
            return False
    
    def _wait_for_port_available(self, max_wait=30, check_interval=1):
        """
        Attendre que le port série soit disponible (non verrouillé)
        
        Args:
            max_wait: Temps maximum d'attente en secondes (défaut: 30s)
            check_interval: Intervalle entre les vérifications en secondes (défaut: 1s)
        
        Returns:
            bool: True si le port est devenu disponible, False si timeout
        """
        start_time = time.time()
        first_check = True
        
        while time.time() - start_time < max_wait:
            if not self._is_port_locked():
                if not first_check:
                    elapsed = time.time() - start_time
                    info_print(f"✅ Port {self.port} disponible après {elapsed:.1f}s")
                return True
            
            if first_check:
                info_print(f"⏳ Port {self.port} verrouillé par un autre processus, attente de libération...")
                first_check = False
            else:
                elapsed = time.time() - start_time
                debug_print_mt(f"⏳ Attente libération du port... ({elapsed:.0f}s/{max_wait}s)")
            
            time.sleep(check_interval)
        
        error_print(f"❌ Timeout: port {self.port} toujours verrouillé après {max_wait}s")
        return False
    
    def _identify_locking_process(self):
        """
        Identifier le processus qui verrouille le port (pour diagnostic)
        
        Returns:
            str: Information sur le processus verrouillant ou None
        """
        try:
            import subprocess
            
            # Utiliser lsof pour identifier le processus
            result = subprocess.run(
                ['lsof', self.port],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    # La première ligne est le header, la deuxième contient les infos
                    process_info = ' '.join(lines[1].split()[:2])  # COMMAND PID
                    return process_info
                    
        except subprocess.TimeoutExpired:
            debug_print_mt("Timeout lors de l'identification du processus")
        except FileNotFoundError:
            debug_print_mt("lsof non disponible pour identifier le processus")
        except Exception as e:
            debug_print_mt(f"Erreur lors de l'identification du processus: {e}")
        
        return None
    
    def _is_self_locked(self):
        """
        Vérifier si le port est verrouillé par nous-mêmes
        
        Returns:
            bool: True si c'est notre propre processus qui verrouille le port
        """
        locking_process = self._identify_locking_process()
        if not locking_process:
            return False
        
        # Extraire le PID du processus bloquant
        try:
            parts = locking_process.split()
            if len(parts) >= 2:
                locking_pid = int(parts[1])
                our_pid = os.getpid()
                
                if locking_pid == our_pid:
                    debug_print_mt(f"⚠️  SELF-LOCKING détecté: PID {our_pid}")
                    return True
        except (ValueError, IndexError) as e:
            debug_print_mt(f"Erreur lors de la comparaison des PIDs: {e}")
        
        return False
    
    def _force_close_interface(self):
        """
        Fermer l'interface de force et libérer le port
        Utilisé en cas de self-locking
        """
        info_print("🔧 Fermeture forcée de l'interface existante...")
        
        # Désabonner des événements
        self._unsubscribe_events()
        
        # Marquer comme non connecté
        self._connected = False
        self._disconnect_detected = False
        
        # Fermer l'interface si elle existe
        if self.interface:
            try:
                # Essayer de fermer proprement
                self.interface.close()
                debug_print_mt("✅ Interface fermée proprement")
            except Exception as e:
                error_print(f"⚠️  Erreur lors de la fermeture propre: {e}")
                
                # Forcer la fermeture en mettant l'interface à None
                self.interface = None
                debug_print_mt("Interface forcée à None")
        
        # Attendre que le système libère le verrou
        info_print("⏳ Attente de libération du verrou système (3s)...")
        time.sleep(3)
        
        # Vérifier si le port est maintenant libre
        if self._is_port_locked():
            error_print("⚠️  Port toujours verrouillé après fermeture forcée")
            # Attendre encore un peu
            time.sleep(2)
        else:
            info_print("✅ Port libéré avec succès")

    
    # ========================================
    # MÉTHODES EXISTANTES (MODIFIÉES)
    # ========================================
    
    def _create_interface_with_eintr_retry(self, max_eintr_retries=3):
        """Créer l'interface série avec gestion spéciale de EINTR"""
        for eintr_attempt in range(1, max_eintr_retries + 1):
            try:
                debug_print_mt(f"Création interface série (tentative EINTR {eintr_attempt}/{max_eintr_retries})")
                interface = meshtastic.serial_interface.SerialInterface(self.port)
                debug_print_mt("Interface série créée avec succès")
                return interface
                
            except Exception as e:
                is_eintr = False
                
                if hasattr(e, 'errno') and e.errno == errno.EINTR:
                    is_eintr = True
                elif hasattr(e, 'args') and len(e.args) > 0:
                    if isinstance(e.args[0], int) and e.args[0] == 4:
                        is_eintr = True
                    elif isinstance(e.args, tuple) and e.args[0] == 4:
                        is_eintr = True
                
                if is_eintr:
                    if eintr_attempt < max_eintr_retries:
                        debug_print_mt(f"⚠️  EINTR détecté (tentative {eintr_attempt}/{max_eintr_retries}), retry...")
                        time.sleep(0.5)
                        continue
                    else:
                        error_print(f"❌ EINTR persistant après {max_eintr_retries} tentatives")
                        raise
                else:
                    raise
        
        raise Exception(f"Impossible de créer l'interface après {max_eintr_retries} tentatives EINTR")
        
    def connect(self):
        """
        Établir la connexion série initiale
        VERSION 2.4.0 avec vérification du verrouillage du port
        """
        connection_success = False
        
        self._is_reconnecting = True
        
        try:
            if not hasattr(self, '_first_connect_done'):
                debug_print_mt("⏳ Stabilisation du device série (2s)...")
                time.sleep(2)
                self._first_connect_done = True
            
            with self._lock:
                if self._connected and self.interface:
                    debug_print_mt("Déjà connecté")
                    return True
                
                # ✅ NOUVEAU v2.4.1: Vérifier et gérer le self-locking
                if self._is_port_locked():
                    locking_process = self._identify_locking_process()
                    if locking_process:
                        info_print(f"🔒 Port verrouillé par: {locking_process}")
                    
                    # Vérifier si c'est nous-mêmes qui bloquons le port
                    if self._is_self_locked():
                        error_print("⚠️  SELF-LOCKING détecté: le bot se verrouille lui-même!")
                        # Forcer la fermeture de l'interface existante
                        self._force_close_interface()
                        
                        # Vérifier si on a réussi à libérer
                        if self._is_port_locked():
                            error_print("❌ Impossible de libérer le port même après fermeture forcée")
                            return False
                        
                        info_print("✅ Self-locking résolu, poursuite de la connexion...")
                    else:
                        # Attendre jusqu'à 30 secondes que le port se libère
                        if not self._wait_for_port_available(max_wait=30):
                            error_print("❌ Impossible de se connecter: port toujours verrouillé")
                            return False
                
                for attempt in range(1, self.max_retries + 1):
                    try:
                        # ✅ NOUVEAU v2.4.0: Re-vérifier avant chaque tentative
                        if self._is_port_locked():
                            debug_print_mt(f"Port verrouillé avant tentative {attempt}, attente...")
                            
                            # ✅ NOUVEAU v2.4.1: Vérifier le self-locking avant chaque tentative
                            if self._is_self_locked():
                                error_print(f"⚠️  Self-locking détecté à la tentative {attempt}")
                                self._force_close_interface()
                            else:
                                if not self._wait_for_port_available(max_wait=10):
                                    continue
                        
                        debug_print_mt(f"🔌 Tentative connexion série {attempt}/{self.max_retries}: {self.port}")
                        
                        self._unsubscribe_events()
                        
                        # ✅ AMÉLIORÉ v2.4.1: Fermeture renforcée de l'interface existante
                        if self.interface:
                            try:
                                debug_print_mt("Fermeture de l'interface existante...")
                                self.interface.close()
                                debug_print_mt("✅ Interface fermée")
                            except Exception as e:
                                debug_print_mt(f"⚠️  Erreur fermeture: {e}")
                            finally:
                                self.interface = None
                            
                            # ✅ NOUVEAU v2.4.1: Délai de stabilisation après fermeture
                            debug_print_mt("⏳ Stabilisation après fermeture (1s)...")
                            time.sleep(1)
                        
                        # ✅ NOUVEAU v2.4.0: Petit délai pour s'assurer que le port est vraiment libre
                        time.sleep(0.5)
                        
                        self.interface = self._create_interface_with_eintr_retry(max_eintr_retries=3)
                        
                        debug_print_mt("⏳ Stabilisation de la connexion (3s)...")
                        time.sleep(3)
                        
                        if self._test_connection():
                            self._connected = True
                            self._disconnect_detected = False
                            self._retry_count = 0
                            self._last_connect_time = time.time()
                            info_print(f"✅ Connexion série établie: {self.port}")
                            connection_success = True
                            break
                        else:
                            debug_print_mt(f"Interface créée mais non fonctionnelle (tentative {attempt})")
                            
                    except Exception as e:
                        error_print(f"❌ Échec connexion série (tentative {attempt}/{self.max_retries}): {e}")
                        self.interface = None
                        self._connected = False
                        
                        if attempt < self.max_retries:
                            delay = min(self.retry_delay * attempt, self.max_retry_delay)
                            debug_print_mt(f"⏱️  Nouvelle tentative dans {delay}s...")
                            time.sleep(delay)
                
                if not connection_success:
                    error_print(f"❌ Impossible de se connecter après {self.max_retries} tentatives")
                    return False
        
        finally:
            self._is_reconnecting = False
        
        if connection_success:
            debug_print_mt(f"⏳ Période de grâce ({self._grace_period}s) avant activation de la surveillance...")
            time.sleep(self._grace_period)
            
            self._subscribe_events()
            
            if self.auto_reconnect and not self._reconnect_thread:
                self._start_monitor()
        
        return connection_success
    
    def _test_connection(self):
        """Tester si la connexion est vraiment fonctionnelle"""
        if not self.interface:
            return False
        
        try:
            if not hasattr(self.interface, 'myInfo'):
                return False
            
            if hasattr(self.interface, '_stream'):
                stream = self.interface._stream
                if hasattr(stream, 'is_open') and not stream.is_open:
                    return False
                
                if hasattr(stream, 'port'):
                    if not os.path.exists(stream.port):
                        return False
            
            if hasattr(self.interface, 'isConnected'):
                if callable(self.interface.isConnected):
                    return self.interface.isConnected()
                else:
                    return self.interface.isConnected
            
            return True
            
        except Exception as e:
            debug_print_mt(f"Test connexion échoué: {e}")
            return False
    
    def get_interface(self):
        """Obtenir l'interface série (reconnecte si nécessaire)"""
        with self._lock:
            if not self._connected or not self.interface or self._disconnect_detected:
                debug_print_mt("Interface non connectée, tentative de reconnexion...")
                self.connect()
            
            return self.interface if self._connected else None
    
    def is_connected(self):
        """Vérifier si la connexion est active"""
        with self._lock:
            if self._is_reconnecting:
                return False
            
            if not self._connected or not self.interface:
                return False
            
            if self._disconnect_detected:
                return False
            
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
        debug_print_mt("🔍 Surveillance de connexion série démarrée")
    
    def _monitor_connection(self):
        """Thread de surveillance - vérifie activement la connexion"""
        check_interval = 5
        
        while not self._stop_reconnect:
            time.sleep(check_interval)
            
            try:
                if self._is_reconnecting:
                    continue
                
                connected = self.is_connected()
                
                if not connected and self.auto_reconnect:
                    with self._lock:
                        if not self._connected or self._disconnect_detected:
                            self._retry_count += 1
                            
                            if self._retry_count == 1:
                                error_print("⚠️  Connexion série perdue")
                                if not self._connection_lost_time:
                                    self._connection_lost_time = time.time()
                    
                    info_print(f"🔄 Tentative de reconnexion #{self._retry_count}...")
                    
                    if self.connect():
                        if self._connection_lost_time:
                            downtime = time.time() - self._connection_lost_time
                            info_print(f"✅ Reconnexion réussie après {downtime:.1f}s d'interruption")
                            self._connection_lost_time = None
                            self._retry_count = 0
                    else:
                        delay = min(self.retry_delay * (2 ** min(self._retry_count, 5)), self.max_retry_delay)
                        debug_print_mt(f"⏱️  Prochaine tentative dans {delay}s...")
                        time.sleep(max(0, delay - check_interval))
                
            except Exception as e:
                error_print(f"Erreur dans le thread de surveillance: {e}")
    
    def close(self):
        """Fermer proprement la connexion série"""
        debug_print_mt("🔌 Fermeture connexion série...")
        
        self._stop_reconnect = True
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=2)
        
        self._unsubscribe_events()
        
        with self._lock:
            if self.interface:
                try:
                    self.interface.close()
                    debug_print_mt("✅ Connexion série fermée")
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
        debug_print_mt(f"🧪 Test connexion série: {port}")
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
    
    print(f"\n🧪 Test SafeSerialConnection v2.4.1 sur {port}...\n")
    
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
