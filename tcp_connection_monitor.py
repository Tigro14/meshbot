#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP Connection Monitor et Killer
Surveille et tue les threads TCP zombies de meshtastic
"""

import threading
import time
import psutil
import os
from utils import info_print, debug_print, error_print

class TCPConnectionMonitor:
    """
    Moniteur pour détecter et tuer les threads TCP qui fuient
    """
    def __init__(self):
        self.running = False
        self.monitor_thread = None
        self.known_threads = set()
        self.tcp_thread_pattern = ["_readBytes", "__reader", "TCPInterface"]
        
    def start(self):
        """Démarrer le monitoring des threads TCP"""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="TCPMonitor"
        )
        self.monitor_thread.start()
        info_print("🔍 TCP Connection Monitor démarré")
        
    def stop(self):
        """Arrêter le monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        info_print("🛑 TCP Connection Monitor arrêté")
        
    def _monitor_loop(self):
        """Boucle de monitoring principale"""
        # Délai initial
        time.sleep(30)
        
        while self.running:
            try:
                self._check_tcp_threads()
                time.sleep(60)  # Vérifier toutes les minutes
            except Exception as e:
                error_print(f"Erreur monitoring TCP: {e}")
                time.sleep(60)
                
    def _check_tcp_threads(self):
        """Vérifier et nettoyer les threads TCP zombies"""
        try:
            # Obtenir tous les threads
            all_threads = threading.enumerate()
            tcp_threads = []
            
            for thread in all_threads:
                thread_name = thread.name
                # Détecter les threads TCP suspects
                if any(pattern in thread_name for pattern in self.tcp_thread_pattern):
                    tcp_threads.append(thread)
                    
            # Si trop de threads TCP (plus de 3), il y a un problème
            if len(tcp_threads) > 3:
                info_print(f"⚠️ {len(tcp_threads)} threads TCP détectés (limite: 3)")
                
                # Identifier les threads zombies (ceux qui tournent depuis trop longtemps)
                current_time = time.time()
                for thread in tcp_threads:
                    if hasattr(thread, '_started_at'):
                        age = current_time - thread._started_at
                        if age > 3600:  # Plus d'une heure
                            info_print(f"🧟 Thread zombie détecté: {thread.name} (age: {age/3600:.1f}h)")
                            # Marquer pour nettoyage
                            self._kill_zombie_thread(thread)
        except Exception as e:
            error_print(f"Erreur check TCP threads: {e}")
                            
    def _kill_zombie_thread(self, thread):
        """Tenter de tuer un thread zombie"""
        try:
            # Python ne permet pas de tuer directement un thread
            # Mais on peut essayer de fermer ses ressources
            if hasattr(thread, '_target'):
                target = thread._target
                if hasattr(target, '__self__'):
                    # C'est une méthode d'instance
                    instance = target.__self__
                    if hasattr(instance, 'close'):
                        info_print(f"💀 Fermeture forcée de {thread.name}")
                        instance.close()
                    elif hasattr(instance, '_close'):
                        instance._close()
                        
        except Exception as e:
            debug_print(f"Impossible de tuer {thread.name}: {e}")
            
    def get_tcp_stats(self):
        """Obtenir les statistiques des connexions TCP"""
        stats = {
            'total_threads': len(threading.enumerate()),
            'tcp_threads': 0,
            'zombie_threads': 0,
            'connections': []
        }
        
        try:
            # Compter les threads TCP
            for thread in threading.enumerate():
                if any(p in thread.name for p in self.tcp_thread_pattern):
                    stats['tcp_threads'] += 1
                    
                    # Vérifier si c'est un zombie
                    if hasattr(thread, '_started_at'):
                        age = time.time() - thread._started_at
                        if age > 3600:
                            stats['zombie_threads'] += 1
                            
            # Obtenir les connexions réseau
            try:
                process = psutil.Process(os.getpid())
                connections = process.connections(kind='tcp')
                for conn in connections:
                    if conn.status == 'ESTABLISHED':
                        stats['connections'].append({
                            'remote': f"{conn.raddr[0]}:{conn.raddr[1]}" if conn.raddr else "N/A",
                            'status': conn.status
                        })
            except Exception as e:
                pass
                
        except Exception as e:
            debug_print(f"Erreur stats TCP: {e}")
            
        return stats


# Instance globale
tcp_monitor = TCPConnectionMonitor()


def cleanup_tcp_connections():
    """
    Fonction utilitaire pour forcer le nettoyage des connexions TCP
    À appeler périodiquement ou en cas de problème
    """
    info_print("🧹 Nettoyage forcé des connexions TCP...")
    
    try:
        # 1. Fermer toutes les connexions SafeTCPConnection
        try:
            from safe_tcp_connection import SafeTCPConnection
            SafeTCPConnection.cleanup_all()
        except Exception as e:
            pass
            
        # 2. Identifier et fermer les threads meshtastic orphelins
        threads_to_close = []
        for thread in threading.enumerate():
            if "TCPInterface" in thread.name or "_readBytes" in thread.name:
                threads_to_close.append(thread)
                
        for thread in threads_to_close:
            info_print(f"  Tentative fermeture: {thread.name}")
            try:
                # Essayer d'accéder à l'objet TCPInterface
                if hasattr(thread, '_target') and hasattr(thread._target, '__self__'):
                    interface = thread._target.__self__
                    if hasattr(interface, 'close'):
                        interface.close()
            except Exception as e:
                pass
                
        # 3. Forcer un garbage collection
        import gc
        gc.collect()
        
        info_print(f"✅ Nettoyage terminé - {len(threads_to_close)} threads traités")
        
    except Exception as e:
        error_print(f"Erreur nettoyage TCP: {e}")


def monitor_tcp_health():
    """
    Vérifier la santé des connexions TCP
    Retourne True si tout va bien, False sinon
    """
    try:
        stats = tcp_monitor.get_tcp_stats()
        
        # Critères de santé
        healthy = True
        issues = []
        
        if stats['tcp_threads'] > 5:
            healthy = False
            issues.append(f"Trop de threads TCP: {stats['tcp_threads']}")
            
        if stats['zombie_threads'] > 0:
            healthy = False
            issues.append(f"Threads zombies: {stats['zombie_threads']}")
            
        if len(stats['connections']) > 3:
            healthy = False
            issues.append(f"Trop de connexions: {len(stats['connections'])}")
            
        if not healthy:
            info_print(f"❌ Santé TCP dégradée: {', '.join(issues)}")
            # Déclencher un nettoyage automatique
            cleanup_tcp_connections()
        else:
            debug_print(f"✅ Santé TCP OK - {stats['tcp_threads']} threads, {len(stats['connections'])} connexions")
            
        return healthy
        
    except Exception as e:
        error_print(f"Erreur monitoring santé TCP: {e}")
        return False


# Script de test direct
if __name__ == "__main__":
    print("🔍 Test du TCP Connection Monitor")
    print("-" * 40)
    
    # Afficher les stats actuelles
    stats = tcp_monitor.get_tcp_stats()
    print(f"📊 Statistiques TCP:")
    print(f"  - Threads totaux: {stats['total_threads']}")
    print(f"  - Threads TCP: {stats['tcp_threads']}")
    print(f"  - Threads zombies: {stats['zombie_threads']}")
    print(f"  - Connexions TCP: {len(stats['connections'])}")
    
    if stats['connections']:
        print(f"\n📡 Connexions actives:")
        for conn in stats['connections']:
            print(f"  - {conn['remote']} ({conn['status']})")
    
    # Tester le nettoyage
    print(f"\n🧹 Test de nettoyage...")
    cleanup_tcp_connections()
    
    # Vérifier la santé
    print(f"\n💊 Test de santé...")
    if monitor_tcp_health():
        print("✅ Santé TCP OK")
    else:
        print("❌ Problèmes TCP détectés")
