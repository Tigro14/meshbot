#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du système de reboot automatique sur erreurs DB persistantes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import time
import tempfile
import os

# Créer un fichier config minimal pour les tests
if not os.path.exists('config.py'):
    with open('config.py', 'w') as f:
        f.write("DEBUG_MODE = False\n")

from db_error_monitor import DBErrorMonitor
from reboot_semaphore import RebootSemaphore


def test_error_tracking():
    """Test 1: Suivi des erreurs dans la fenêtre de temps"""
    print("=" * 60)
    print("Test 1: Suivi des erreurs")
    print("=" * 60)
    
    monitor = DBErrorMonitor(
        window_seconds=10,  # Petite fenêtre pour test rapide
        error_threshold=5,
        enabled=True,
        reboot_callback=None  # Pas de reboot pour ce test
    )
    
    # Ajouter quelques erreurs
    for i in range(3):
        error = Exception(f"Test error {i}")
        monitor.record_error(error, 'save_packet')
        time.sleep(0.5)
    
    stats = monitor.get_stats()
    assert stats['errors_in_window'] == 3, f"Expected 3 errors, got {stats['errors_in_window']}"
    assert stats['total_errors'] == 3, f"Expected 3 total errors, got {stats['total_errors']}"
    assert not stats['reboot_triggered'], "Reboot should not be triggered yet"
    
    print(f"✅ Erreurs enregistrées: {stats['errors_in_window']}/5")
    print(f"✅ Total erreurs: {stats['total_errors']}")
    print(f"✅ État reboot: {stats['reboot_triggered']}")
    
    return True


def test_threshold_trigger():
    """Test 2: Déclenchement au seuil"""
    print("\n" + "=" * 60)
    print("Test 2: Déclenchement au seuil")
    print("=" * 60)
    
    reboot_called = []
    
    def mock_reboot():
        reboot_called.append(True)
        print("🔄 Callback de reboot appelé (simulé)")
        return True
    
    monitor = DBErrorMonitor(
        window_seconds=10,
        error_threshold=5,
        enabled=True,
        reboot_callback=mock_reboot
    )
    
    # Ajouter 5 erreurs pour atteindre le seuil
    for i in range(5):
        error = Exception(f"Critical error {i}")
        monitor.record_error(error, 'save_packet')
        time.sleep(0.1)
    
    stats = monitor.get_stats()
    
    assert len(reboot_called) == 1, f"Expected 1 reboot call, got {len(reboot_called)}"
    assert stats['reboot_triggered'], "Reboot should be triggered"
    assert stats['total_reboots'] == 1, f"Expected 1 reboot, got {stats['total_reboots']}"
    
    print(f"✅ Seuil atteint: {stats['errors_in_window']}/{stats['error_threshold']}")
    print(f"✅ Reboot déclenché: {stats['reboot_triggered']}")
    print(f"✅ Callback appelé: {len(reboot_called)} fois")
    
    return True


def test_no_duplicate_reboot():
    """Test 3: Pas de reboot multiple"""
    print("\n" + "=" * 60)
    print("Test 3: Pas de reboot multiple")
    print("=" * 60)
    
    reboot_count = []
    
    def count_reboot():
        reboot_count.append(True)
        return True
    
    monitor = DBErrorMonitor(
        window_seconds=10,
        error_threshold=3,
        enabled=True,
        reboot_callback=count_reboot
    )
    
    # Ajouter 10 erreurs (bien au-dessus du seuil)
    for i in range(10):
        error = Exception(f"Error {i}")
        monitor.record_error(error, 'save_packet')
        time.sleep(0.1)
    
    # Vérifier qu'un seul reboot a été déclenché
    assert len(reboot_count) == 1, f"Expected 1 reboot, got {len(reboot_count)}"
    
    stats = monitor.get_stats()
    print(f"✅ Erreurs enregistrées: {stats['total_errors']}")
    print(f"✅ Reboots déclenchés: {len(reboot_count)} (attendu: 1)")
    print(f"✅ Protection contre reboots multiples OK")
    
    return True


def test_window_expiration():
    """Test 4: Expiration de la fenêtre de temps"""
    print("\n" + "=" * 60)
    print("Test 4: Expiration de la fenêtre")
    print("=" * 60)
    
    monitor = DBErrorMonitor(
        window_seconds=2,  # Fenêtre très courte
        error_threshold=5,
        enabled=True,
        reboot_callback=None
    )
    
    # Ajouter 3 erreurs
    for i in range(3):
        error = Exception(f"Error {i}")
        monitor.record_error(error, 'save_packet')
        time.sleep(0.2)
    
    stats1 = monitor.get_stats()
    print(f"✅ Erreurs initiales: {stats1['errors_in_window']}")
    
    # Attendre que la fenêtre expire
    print("⏳ Attente expiration fenêtre (3s)...")
    time.sleep(3)
    
    # Vérifier que les erreurs ont expiré
    stats2 = monitor.get_stats()
    assert stats2['errors_in_window'] == 0, f"Expected 0 errors after expiration, got {stats2['errors_in_window']}"
    
    print(f"✅ Erreurs après expiration: {stats2['errors_in_window']}")
    print(f"✅ Total conservé: {stats2['total_errors']}")
    
    return True


def test_disabled_monitor():
    """Test 5: Moniteur désactivé"""
    print("\n" + "=" * 60)
    print("Test 5: Moniteur désactivé")
    print("=" * 60)
    
    reboot_called = []
    
    def should_not_call():
        reboot_called.append(True)
        return True
    
    monitor = DBErrorMonitor(
        window_seconds=10,
        error_threshold=2,
        enabled=False,  # Désactivé
        reboot_callback=should_not_call
    )
    
    # Ajouter des erreurs
    for i in range(5):
        error = Exception(f"Error {i}")
        monitor.record_error(error, 'save_packet')
    
    stats = monitor.get_stats()
    
    assert not stats['enabled'], "Monitor should be disabled"
    assert len(reboot_called) == 0, f"Reboot should not be called when disabled, got {len(reboot_called)}"
    
    print(f"✅ Moniteur désactivé: {not stats['enabled']}")
    print(f"✅ Reboot non appelé: {len(reboot_called) == 0}")
    
    return True


def test_status_report():
    """Test 6: Génération du rapport d'état"""
    print("\n" + "=" * 60)
    print("Test 6: Rapport d'état")
    print("=" * 60)
    
    monitor = DBErrorMonitor(
        window_seconds=300,
        error_threshold=10,
        enabled=True,
        reboot_callback=None
    )
    
    # Ajouter quelques erreurs
    for i in range(5):
        monitor.record_error(Exception(f"Error {i}"), 'save_packet')
    
    # Rapport compact (LoRa)
    compact = monitor.get_status_report(compact=True)
    print("\nRapport compact (LoRa):")
    print(compact)
    assert len(compact) < 180, f"Compact report too long: {len(compact)} chars"
    print(f"✅ Longueur rapport compact: {len(compact)}/180 chars")
    
    # Rapport détaillé (Telegram/CLI)
    detailed = monitor.get_status_report(compact=False)
    print("\nRapport détaillé:")
    print(detailed)
    print(f"✅ Rapport détaillé: {len(detailed)} chars")
    
    return True


def test_reboot_semaphore_integration():
    """Test 7: Intégration avec RebootSemaphore"""
    print("\n" + "=" * 60)
    print("Test 7: Intégration RebootSemaphore")
    print("=" * 60)
    
    # Nettoyer d'abord tout sémaphore existant
    RebootSemaphore.clear_reboot_signal()
    
    def real_reboot():
        """Utilise le vrai système de sémaphore"""
        requester_info = {
            'name': 'DBErrorMonitor_Test',
            'node_id': '0xTEST',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        return RebootSemaphore.signal_reboot(requester_info)
    
    monitor = DBErrorMonitor(
        window_seconds=10,
        error_threshold=3,
        enabled=True,
        reboot_callback=real_reboot
    )
    
    # Déclencher le seuil
    for i in range(3):
        monitor.record_error(Exception(f"Error {i}"), 'save_packet')
    
    # Vérifier que le sémaphore a été activé
    semaphore_active = RebootSemaphore.check_reboot_signal()
    assert semaphore_active, "RebootSemaphore should be active"
    
    print(f"✅ Sémaphore activé: {semaphore_active}")
    
    # Lire les infos de reboot
    reboot_info = RebootSemaphore.get_reboot_info()
    print(f"✅ Info reboot:\n{reboot_info}")
    
    # Nettoyer pour éviter reboot réel
    RebootSemaphore.clear_reboot_signal()
    print("✅ Sémaphore nettoyé (reboot annulé)")
    
    return True


def main():
    """Exécute tous les tests"""
    print("🧪 Tests du système de reboot automatique sur erreurs DB")
    print()
    
    tests = [
        ("Suivi des erreurs", test_error_tracking),
        ("Déclenchement au seuil", test_threshold_trigger),
        ("Pas de reboot multiple", test_no_duplicate_reboot),
        ("Expiration fenêtre", test_window_expiration),
        ("Moniteur désactivé", test_disabled_monitor),
        ("Rapport d'état", test_status_report),
        ("Intégration sémaphore", test_reboot_semaphore_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"❌ ÉCHEC: {e}")
            import traceback
            traceback.print_exc()
    
    # Résumé
    print("\n" + "=" * 60)
    print("RÉSULTATS")
    print("=" * 60)
    
    passed_count = 0
    for test_name, passed, error in results:
        if passed:
            print(f"✅ {test_name}: PASS")
            passed_count += 1
        else:
            print(f"❌ {test_name}: FAIL")
            if error:
                print(f"   Erreur: {error}")
    
    print()
    print(f"Tests réussis: {passed_count}/{len(tests)}")
    
    if passed_count == len(tests):
        print("✅ Tous les tests passent")
        return 0
    else:
        print("❌ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
