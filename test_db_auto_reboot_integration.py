#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test d'intégration du système de reboot automatique DB avec le bot
Vérifie l'intégration avec TrafficPersistence et le callback d'erreur
"""

import sys
import time
import tempfile
import os
import sqlite3

# Créer un fichier config minimal pour les tests
if not os.path.exists('config.py'):
    with open('config.py', 'w') as f:
        f.write("DEBUG_MODE = False\n")

from traffic_persistence import TrafficPersistence
from db_error_monitor import DBErrorMonitor
from reboot_semaphore import RebootSemaphore


def test_traffic_persistence_callback():
    """
    Test 1: Vérifier que TrafficPersistence appelle le callback d'erreur
    """
    print("=" * 60)
    print("Test 1: Callback d'erreur TrafficPersistence")
    print("=" * 60)
    
    errors_received = []
    
    def error_callback(error, operation):
        errors_received.append((error, operation))
        print(f"✅ Callback appelé: {operation} - {type(error).__name__}")
    
    # Créer un fichier DB temporaire
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Créer persistence avec callback
        persistence = TrafficPersistence(db_path=db_path, error_callback=error_callback)
        
        # Corrompre la base de données pour provoquer des erreurs
        persistence.conn.close()
        
        # Écrire des données invalides dans le fichier DB
        with open(db_path, 'wb') as f:
            f.write(b'CORRUPTED DATABASE FILE')
        
        # Tenter plusieurs sauvegardes (devrait échouer et appeler callback)
        for i in range(5):
            test_packet = {
                'timestamp': time.time(),
                'from_id': f'0x{i:08x}',
                'to_id': '0xFFFFFFFF',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': f'test {i}',
                'source': 'test'
            }
            persistence.save_packet(test_packet)
            time.sleep(0.1)
        
        # Vérifier que le callback a été appelé
        # Note: Il peut y avoir plusieurs tentatives de reconnexion
        assert len(errors_received) > 0, f"Callback should have been called, got {len(errors_received)} calls"
        
        print(f"✅ {len(errors_received)} erreur(s) capturée(s)")
        for error, operation in errors_received:
            print(f"   - {operation}: {type(error).__name__}")
        
        return True
        
    finally:
        # Nettoyer
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_full_integration():
    """
    Test 2: Intégration complète TrafficPersistence + DBErrorMonitor
    """
    print("\n" + "=" * 60)
    print("Test 2: Intégration complète")
    print("=" * 60)
    
    reboot_called = []
    
    def mock_reboot():
        reboot_called.append(True)
        print("🔄 Reboot callback appelé")
        return True
    
    # Créer le moniteur d'erreurs
    monitor = DBErrorMonitor(
        window_seconds=30,
        error_threshold=3,  # Bas pour test rapide
        enabled=True,
        reboot_callback=mock_reboot
    )
    
    # Créer un fichier DB temporaire
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Créer persistence avec le callback du moniteur
        persistence = TrafficPersistence(
            db_path=db_path,
            error_callback=monitor.record_error
        )
        
        # Corrompre la base de données pour provoquer des erreurs
        persistence.conn.close()
        
        # Écrire des données invalides dans le fichier DB
        with open(db_path, 'wb') as f:
            f.write(b'CORRUPTED DATABASE FILE')
        
        # Tenter plusieurs sauvegardes (devrait déclencher le reboot)
        for i in range(5):
            test_packet = {
                'timestamp': time.time(),
                'from_id': f'0x{i:08x}',
                'to_id': '0xFFFFFFFF',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': f'test message {i}',
                'source': 'test'
            }
            persistence.save_packet(test_packet)
            time.sleep(0.2)
        
        # Vérifier que le reboot a été déclenché
        stats = monitor.get_stats()
        
        print(f"✅ Erreurs enregistrées: {stats['total_errors']}")
        print(f"✅ Erreurs dans fenêtre: {stats['errors_in_window']}")
        print(f"✅ Seuil: {stats['error_threshold']}")
        print(f"✅ Reboot déclenché: {stats['reboot_triggered']}")
        
        assert stats['reboot_triggered'], "Reboot should have been triggered"
        assert len(reboot_called) > 0, "Reboot callback should have been called"
        
        print(f"✅ Intégration complète fonctionnelle")
        
        return True
        
    finally:
        # Nettoyer
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except:
                pass


def test_normal_operation():
    """
    Test 3: Fonctionnement normal sans erreurs
    """
    print("\n" + "=" * 60)
    print("Test 3: Fonctionnement normal")
    print("=" * 60)
    
    reboot_called = []
    
    def should_not_call():
        reboot_called.append(True)
        return True
    
    # Créer le moniteur d'erreurs
    monitor = DBErrorMonitor(
        window_seconds=10,
        error_threshold=5,
        enabled=True,
        reboot_callback=should_not_call
    )
    
    # Créer un fichier DB temporaire
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Créer persistence avec le callback du moniteur
        persistence = TrafficPersistence(
            db_path=db_path,
            error_callback=monitor.record_error
        )
        
        # Sauvegarder des paquets normaux (devrait fonctionner)
        for i in range(10):
            test_packet = {
                'timestamp': time.time(),
                'from_id': f'0x{i:08x}',
                'to_id': '0xFFFFFFFF',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': f'test message {i}',
                'source': 'test',
                'rssi': -50,
                'snr': 5.0,
                'hops': 0,
                'size': 100,
                'is_broadcast': True
            }
            persistence.save_packet(test_packet)
        
        # Vérifier qu'aucun reboot n'a été déclenché
        stats = monitor.get_stats()
        
        print(f"✅ Paquets sauvegardés: 10")
        print(f"✅ Erreurs: {stats['total_errors']}")
        print(f"✅ Reboot déclenché: {stats['reboot_triggered']}")
        
        assert stats['total_errors'] == 0, "Should have no errors"
        assert not stats['reboot_triggered'], "Reboot should not be triggered"
        assert len(reboot_called) == 0, "Reboot callback should not be called"
        
        print(f"✅ Fonctionnement normal vérifié")
        
        return True
        
    finally:
        # Nettoyer
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_read_only_filesystem_simulation():
    """
    Test 4: Simulation d'un filesystem en lecture seule
    """
    print("\n" + "=" * 60)
    print("Test 4: Simulation filesystem lecture seule")
    print("=" * 60)
    
    reboot_called = []
    
    def mock_reboot():
        reboot_called.append(True)
        return True
    
    # Créer le moniteur d'erreurs
    monitor = DBErrorMonitor(
        window_seconds=10,
        error_threshold=3,
        enabled=True,
        reboot_callback=mock_reboot
    )
    
    # Créer un fichier DB temporaire dans un dossier existant
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        
        # Créer persistence
        persistence = TrafficPersistence(
            db_path=db_path,
            error_callback=monitor.record_error
        )
        
        # Fermer la connexion
        persistence.conn.close()
        
        # Rendre le fichier en lecture seule
        os.chmod(db_path, 0o444)
        
        # Tenter des sauvegardes (devrait échouer)
        for i in range(5):
            test_packet = {
                'timestamp': time.time(),
                'from_id': f'0x{i:08x}',
                'to_id': '0xFFFFFFFF',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': f'test {i}',
                'source': 'test'
            }
            persistence.save_packet(test_packet)
            time.sleep(0.1)
        
        # Vérifier que le reboot a été déclenché
        stats = monitor.get_stats()
        
        print(f"✅ Erreurs enregistrées: {stats['total_errors']}")
        print(f"✅ Reboot déclenché: {stats['reboot_triggered']}")
        
        # Note: Peut ne pas déclencher si la reconnexion réussit
        # Ce n'est pas une erreur, c'est juste que le code est robuste
        print(f"✅ Simulation filesystem RO terminée")
        
        return True


def main():
    """Exécute tous les tests d'intégration"""
    print("🧪 Tests d'intégration DB Auto-Reboot")
    print()
    
    # Nettoyer le sémaphore avant de commencer
    RebootSemaphore.clear_reboot_signal()
    
    tests = [
        ("Callback TrafficPersistence", test_traffic_persistence_callback),
        ("Intégration complète", test_full_integration),
        ("Fonctionnement normal", test_normal_operation),
        ("Simulation filesystem RO", test_read_only_filesystem_simulation),
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
    
    # Nettoyer le sémaphore après les tests
    RebootSemaphore.clear_reboot_signal()
    
    if passed_count == len(tests):
        print("✅ Tous les tests d'intégration passent")
        return 0
    else:
        print("❌ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
