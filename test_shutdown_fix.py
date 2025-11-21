#!/usr/bin/env python3
"""
Test de la robustesse du shutdown
Vérifie que le bot s'arrête proprement même avec des composants qui bloquent
"""

import time
import signal
import sys
import threading
from unittest.mock import Mock, patch
import concurrent.futures

# Test 1: Vérifier le timeout global du shutdown
def test_shutdown_timeout():
    """Test que le shutdown ne bloque pas plus de 9 secondes (8s timeout + 1s marge)"""
    print("\n=== Test 1: Timeout global du shutdown ===")
    
    # Simuler un composant qui bloque
    class BlockingComponent:
        def stop(self):
            print("  [BlockingComponent] Blocage pendant 20 secondes...")
            time.sleep(20)
    
    start = time.time()
    
    # Code identique à MeshBot.stop()
    def shutdown_with_timeout():
        component = BlockingComponent()
        
        def _perform_shutdown():
            try:
                component.stop()
            except Exception as e:
                print(f"  Erreur: {e}")
        
        shutdown_timeout = 8
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(_perform_shutdown)
            future.result(timeout=shutdown_timeout)
            print("  ✅ Shutdown terminé normalement")
        except concurrent.futures.TimeoutError:
            print(f"  ⚠️ Timeout shutdown ({shutdown_timeout}s) - forçage arrêt")
        finally:
            executor.shutdown(wait=False)
    
    shutdown_with_timeout()
    elapsed = time.time() - start
    
    print(f"  Temps écoulé: {elapsed:.2f}s")
    # Avec shutdown(wait=False), on ne devrait attendre que le timeout
    assert elapsed < 9, f"Shutdown a pris {elapsed:.2f}s (devrait être < 9s)"
    print("  ✅ Test réussi: shutdown limité par timeout")
    print("  ℹ️ Note: executor.shutdown(wait=False) évite d'attendre les threads bloqués")


# Test 2: Vérifier le timeout par plateforme
def test_platform_timeout():
    """Test que chaque plateforme a un timeout de 3 secondes"""
    print("\n=== Test 2: Timeout par plateforme ===")
    
    class SlowPlatform:
        def __init__(self, name, delay):
            self.name = name
            self.delay = delay
        
        def stop(self):
            print(f"  [{self.name}] Arrêt avec délai de {self.delay}s...")
            time.sleep(self.delay)
    
    platforms = {
        'fast': SlowPlatform('FastPlatform', 0.5),
        'slow': SlowPlatform('SlowPlatform', 10),
    }
    
    start = time.time()
    
    # Code identique à PlatformManager.stop_all()
    for platform_name, platform in platforms.items():
        executor = None
        try:
            print(f"  Arrêt {platform_name}...")
            
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(platform.stop)
            try:
                future.result(timeout=3)
                print(f"  ✅ {platform_name} arrêté proprement")
            except concurrent.futures.TimeoutError:
                print(f"  ⚠️ Timeout arrêt {platform_name} (3s) - abandon")
        except Exception as e:
            print(f"  ❌ Erreur arrêt {platform_name}: {e}")
        finally:
            if executor:
                executor.shutdown(wait=False)
    
    elapsed = time.time() - start
    print(f"  Temps total: {elapsed:.2f}s")
    # Fast: 0.5s + Slow: 3s (timeout) = ~3.5s total
    assert elapsed < 5, f"Arrêt plateformes a pris {elapsed:.2f}s (devrait être < 5s)"
    print("  ✅ Test réussi: timeouts par plateforme respectés")


# Test 3: Vérifier que le monitoring système s'arrête
def test_system_monitor_stop():
    """Test que le monitoring système s'arrête avec timeout"""
    print("\n=== Test 3: Arrêt monitoring système ===")
    
    class MockSystemMonitor:
        def __init__(self):
            self.running = True
            self.monitor_thread = None
        
        def start_long_task(self):
            """Simuler une tâche longue"""
            def long_task():
                while self.running:
                    time.sleep(0.1)
            
            self.monitor_thread = threading.Thread(target=long_task)
            self.monitor_thread.start()
        
        def stop(self):
            """Arrêt avec timeout"""
            self.running = False
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=3)
                if self.monitor_thread.is_alive():
                    print("  ⚠️ Thread monitoring système n'a pas terminé (timeout 3s)")
                else:
                    print("  🛑 Monitoring système arrêté")
            else:
                print("  🛑 Monitoring système arrêté")
    
    monitor = MockSystemMonitor()
    monitor.start_long_task()
    time.sleep(0.2)  # Laisser le thread démarrer
    
    start = time.time()
    monitor.stop()
    elapsed = time.time() - start
    
    print(f"  Temps d'arrêt: {elapsed:.2f}s")
    assert elapsed < 4, f"Arrêt monitoring a pris {elapsed:.2f}s (devrait être < 4s)"
    print("  ✅ Test réussi: monitoring arrêté rapidement")


# Test 4: Test complet du shutdown
def test_complete_shutdown():
    """Test un shutdown complet avec plusieurs composants"""
    print("\n=== Test 4: Shutdown complet ===")
    
    class MockBot:
        def __init__(self):
            self.running = True
            self.node_manager = Mock()
            self.system_monitor = Mock()
            self.blitz_monitor = None
            self.platform_manager = Mock()
            self.telegram_integration = None
            self.safe_serial = None
            self.interface = None
        
        def stop(self):
            """Version identique du shutdown avec timeout"""
            print("  Arrêt du bot...")
            self.running = False
            
            shutdown_timeout = 8
            
            def _perform_shutdown():
                # Sauvegarder
                if self.node_manager:
                    self.node_manager.save_node_names(force=True)
                
                # Arrêter monitoring
                if self.system_monitor:
                    self.system_monitor.stop()
                
                # Arrêter plateformes
                if self.platform_manager:
                    self.platform_manager.stop_all()
            
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(_perform_shutdown)
                future.result(timeout=shutdown_timeout)
                print("  ✅ Bot arrêté proprement")
                return True
            except concurrent.futures.TimeoutError:
                print(f"  ⚠️ Timeout shutdown ({shutdown_timeout}s) - forçage arrêt")
                return False
            finally:
                executor.shutdown(wait=False)
    
    bot = MockBot()
    start = time.time()
    success = bot.stop()
    elapsed = time.time() - start
    
    print(f"  Temps total: {elapsed:.2f}s")
    assert elapsed < 10, f"Shutdown complet a pris {elapsed:.2f}s (devrait être < 10s)"
    print("  ✅ Test réussi: shutdown complet terminé")


if __name__ == '__main__':
    print("=" * 60)
    print("Tests de robustesse du shutdown")
    print("=" * 60)
    
    try:
        test_shutdown_timeout()
        test_platform_timeout()
        test_system_monitor_stop()
        test_complete_shutdown()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST ÉCHOUÉ: {e}")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)
