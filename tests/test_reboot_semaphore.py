#!/usr/bin/env python3
"""
Test script for semaphore-based reboot signaling
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import os
import time
from reboot_semaphore import RebootSemaphore, REBOOT_SEMAPHORE_FILE, REBOOT_INFO_FILE

def test_signal_reboot():
    """Test signaling a reboot"""
    print("=" * 60)
    print("Test 1: Signaler un redémarrage")
    print("=" * 60)
    
    # Clean up any existing signals
    RebootSemaphore.clear_reboot_signal()
    
    # Signal reboot
    requester_info = {
        'name': 'TestNode',
        'node_id': '0x12345678',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    result = RebootSemaphore.signal_reboot(requester_info)
    
    if result:
        print(f"✅ Sémaphore créé avec succès")
        print(f"   Fichier lock: {REBOOT_SEMAPHORE_FILE}")
        print(f"   Fichier info: {REBOOT_INFO_FILE}")
        
        # Check if files exist
        if os.path.exists(REBOOT_SEMAPHORE_FILE):
            print(f"✅ Lock file existe")
        else:
            print(f"❌ Lock file n'existe pas")
            return False
        
        if os.path.exists(REBOOT_INFO_FILE):
            print(f"✅ Info file existe")
        else:
            print(f"⚠️ Info file n'existe pas (non-critique)")
        
        return True
    else:
        print("❌ Échec création sémaphore")
        return False

def test_check_signal():
    """Test checking if reboot is signaled"""
    print("\n" + "=" * 60)
    print("Test 2: Vérifier le signal de redémarrage")
    print("=" * 60)
    
    # Check signal
    is_signaled = RebootSemaphore.check_reboot_signal()
    
    if is_signaled:
        print("✅ Signal de redémarrage détecté")
        return True
    else:
        print("❌ Aucun signal détecté (devrait en avoir un)")
        return False

def test_get_info():
    """Test getting reboot info"""
    print("\n" + "=" * 60)
    print("Test 3: Récupérer les informations de redémarrage")
    print("=" * 60)
    
    info = RebootSemaphore.get_reboot_info()
    
    if info:
        print("✅ Informations récupérées:")
        print(info)
        return True
    else:
        print("⚠️ Aucune information disponible (non-critique)")
        return True  # Still pass - info is optional

def test_clear_signal():
    """Test clearing the reboot signal"""
    print("\n" + "=" * 60)
    print("Test 4: Effacer le signal de redémarrage")
    print("=" * 60)
    
    result = RebootSemaphore.clear_reboot_signal()
    
    if result:
        print("✅ Signal effacé avec succès")
        
        # Verify cleared
        if not RebootSemaphore.check_reboot_signal():
            print("✅ Vérification: aucun signal détecté")
            return True
        else:
            print("❌ Signal encore présent après effacement")
            return False
    else:
        print("❌ Échec effacement signal")
        return False

def test_dev_shm_availability():
    """Test that /dev/shm is writable"""
    print("\n" + "=" * 60)
    print("Test 5: Vérifier accessibilité de /dev/shm")
    print("=" * 60)
    
    try:
        test_file = "/dev/shm/meshbot_test.tmp"
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Verify read
        with open(test_file, 'r') as f:
            content = f.read()
        
        # Clean up
        os.remove(test_file)
        
        if content == "test":
            print("✅ /dev/shm est accessible en lecture/écriture")
            print("✅ Idéal pour sémaphore (survit même si disque read-only)")
            return True
        else:
            print("❌ Problème lecture/écriture sur /dev/shm")
            return False
            
    except Exception as e:
        print(f"❌ /dev/shm non accessible: {e}")
        print("⚠️ Le système peut ne pas avoir /dev/shm monté")
        return False

def test_concurrent_signals():
    """Test that multiple signal attempts work correctly"""
    print("\n" + "=" * 60)
    print("Test 6: Signaux multiples (idempotence)")
    print("=" * 60)
    
    # Clean up
    RebootSemaphore.clear_reboot_signal()
    
    # First signal
    info1 = {'name': 'Node1', 'node_id': '0x1', 'timestamp': '2024-01-01 10:00:00'}
    result1 = RebootSemaphore.signal_reboot(info1)
    
    # Second signal (should still work - idempotent)
    info2 = {'name': 'Node2', 'node_id': '0x2', 'timestamp': '2024-01-01 10:01:00'}
    result2 = RebootSemaphore.signal_reboot(info2)
    
    if result1 and result2:
        print("✅ Signaux multiples gérés correctement (idempotent)")
        
        # Clean up
        RebootSemaphore.clear_reboot_signal()
        return True
    else:
        print("❌ Problème avec signaux multiples")
        return False

def main():
    """Run all tests"""
    print("🧪 Test du système de sémaphore pour redémarrage")
    print()
    
    results = []
    
    results.append(("Disponibilité /dev/shm", test_dev_shm_availability()))
    results.append(("Signaler redémarrage", test_signal_reboot()))
    results.append(("Vérifier signal", test_check_signal()))
    results.append(("Récupérer info", test_get_info()))
    results.append(("Effacer signal", test_clear_signal()))
    results.append(("Signaux multiples", test_concurrent_signals()))
    
    print("\n" + "=" * 60)
    print("RÉSULTATS")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    print("=" * 60)
    print("AVANTAGES DU SÉMAPHORE")
    print("=" * 60)
    print("✅ Utilise /dev/shm (tmpfs en RAM)")
    print("✅ Survit même si /tmp ou / deviennent read-only")
    print("✅ IPC propre via fcntl file locking")
    print("✅ Nettoyage automatique au redémarrage")
    print("✅ Compatible avec daemon Python ou shell script")
    
    print()
    if all_passed:
        print("✅ Tous les tests passent")
        return 0
    else:
        print("❌ Certains tests ont échoué")
        return 1

if __name__ == "__main__":
    sys.exit(main())
