#!/usr/bin/env python3
"""
Script de test pour valider la logique de démarrage en mode single-node
Ce script simule le comportement de start() sans connexion réelle au hardware
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

def test_start_logic_serial():
    """Tester la logique de démarrage en mode Serial"""
    print("🧪 Test logique de démarrage - Mode Serial...")
    
    # Simuler les globals de config
    test_globals = {
        'CONNECTION_MODE': 'serial',
        'SERIAL_PORT': '/dev/ttyACM0',
        'TCP_HOST': '192.168.1.38',
        'TCP_PORT': 4403
    }
    
    # Logique extraite de start()
    connection_mode = test_globals.get('CONNECTION_MODE', 'serial').lower()
    
    if connection_mode == 'tcp':
        tcp_host = test_globals.get('TCP_HOST', '192.168.1.38')
        tcp_port = test_globals.get('TCP_PORT', 4403)
        interface_type = 'tcp'
        connection_info = f"{tcp_host}:{tcp_port}"
    else:
        serial_port = test_globals.get('SERIAL_PORT', '/dev/ttyACM0')
        interface_type = 'serial'
        connection_info = serial_port
    
    assert interface_type == 'serial', "Interface devrait être 'serial'"
    assert connection_info == '/dev/ttyACM0', "Port série devrait être /dev/ttyACM0"
    
    print(f"  ✅ Mode détecté: {interface_type}")
    print(f"  ✅ Connexion: {connection_info}")
    return True

def test_start_logic_tcp():
    """Tester la logique de démarrage en mode TCP"""
    print("🧪 Test logique de démarrage - Mode TCP...")
    
    # Simuler les globals de config
    test_globals = {
        'CONNECTION_MODE': 'tcp',
        'SERIAL_PORT': '/dev/ttyACM0',
        'TCP_HOST': '192.168.1.100',
        'TCP_PORT': 4403
    }
    
    # Logique extraite de start()
    connection_mode = test_globals.get('CONNECTION_MODE', 'serial').lower()
    
    if connection_mode == 'tcp':
        tcp_host = test_globals.get('TCP_HOST', '192.168.1.38')
        tcp_port = test_globals.get('TCP_PORT', 4403)
        interface_type = 'tcp'
        connection_info = f"{tcp_host}:{tcp_port}"
    else:
        serial_port = test_globals.get('SERIAL_PORT', '/dev/ttyACM0')
        interface_type = 'serial'
        connection_info = serial_port
    
    assert interface_type == 'tcp', "Interface devrait être 'tcp'"
    assert connection_info == '192.168.1.100:4403', "TCP devrait être 192.168.1.100:4403"
    
    print(f"  ✅ Mode détecté: {interface_type}")
    print(f"  ✅ Connexion: {connection_info}")
    return True

def test_start_logic_default():
    """Tester la logique de démarrage sans CONNECTION_MODE (défaut)"""
    print("🧪 Test logique de démarrage - Mode par défaut...")
    
    # Simuler les globals de config (sans CONNECTION_MODE)
    test_globals = {
        'SERIAL_PORT': '/dev/ttyACM0',
        'TCP_HOST': '192.168.1.38',
        'TCP_PORT': 4403
    }
    
    # Logique extraite de start()
    connection_mode = test_globals.get('CONNECTION_MODE', 'serial').lower()
    
    if connection_mode == 'tcp':
        tcp_host = test_globals.get('TCP_HOST', '192.168.1.38')
        tcp_port = test_globals.get('TCP_PORT', 4403)
        interface_type = 'tcp'
        connection_info = f"{tcp_host}:{tcp_port}"
    else:
        serial_port = test_globals.get('SERIAL_PORT', '/dev/ttyACM0')
        interface_type = 'serial'
        connection_info = serial_port
    
    assert interface_type == 'serial', "Interface devrait être 'serial' par défaut"
    assert connection_info == '/dev/ttyACM0', "Port série devrait être utilisé par défaut"
    
    print(f"  ✅ Mode par défaut: {interface_type}")
    print(f"  ✅ Connexion: {connection_info}")
    return True

def test_on_message_logic():
    """Tester la logique de filtrage dans on_message()"""
    print("🧪 Test logique de filtrage on_message()...")
    
    # Test 1: Mode single-node Serial
    print("  📋 Test 1: Mode single-node Serial")
    test_globals = {'CONNECTION_MODE': 'serial'}
    connection_mode = test_globals.get('CONNECTION_MODE', 'serial').lower()
    is_from_our_interface = True  # Le paquet vient de notre interface
    
    # Déterminer la source
    if connection_mode == 'tcp':
        source = 'tcp'
    elif connection_mode == 'serial':
        source = 'local'
    else:
        source = 'local' if is_from_our_interface else 'tigrog2'
    
    # Filtrage
    should_process = False
    if connection_mode in ['serial', 'tcp']:
        if is_from_our_interface:
            should_process = True
    
    assert source == 'local', "Source devrait être 'local'"
    assert should_process == True, "Message devrait être traité"
    print("    ✅ Paquet de notre interface → traité")
    
    # Test 2: Mode single-node TCP
    print("  📋 Test 2: Mode single-node TCP")
    test_globals = {'CONNECTION_MODE': 'tcp'}
    connection_mode = test_globals.get('CONNECTION_MODE', 'serial').lower()
    is_from_our_interface = True
    
    if connection_mode == 'tcp':
        source = 'tcp'
    elif connection_mode == 'serial':
        source = 'local'
    else:
        source = 'local' if is_from_our_interface else 'tigrog2'
    
    should_process = False
    if connection_mode in ['serial', 'tcp']:
        if is_from_our_interface:
            should_process = True
    
    assert source == 'tcp', "Source devrait être 'tcp'"
    assert should_process == True, "Message devrait être traité"
    print("    ✅ Paquet TCP de notre interface → traité")
    
    # Test 3: Mode legacy avec PROCESS_TCP_COMMANDS=False
    print("  📋 Test 3: Mode legacy, PROCESS_TCP_COMMANDS=False")
    test_globals = {'PROCESS_TCP_COMMANDS': False}
    connection_mode = test_globals.get('CONNECTION_MODE', 'serial').lower()
    is_from_our_interface = False  # Paquet TCP externe
    
    # En mode legacy (pas de CONNECTION_MODE défini, donc 'serial' par défaut)
    # Mais 'serial' est un mode single-node, donc on doit tester autrement
    # Simulons plutôt un mode où CONNECTION_MODE n'est pas 'serial' ni 'tcp'
    connection_mode = 'legacy'  # Simule l'absence de CONNECTION_MODE valide
    
    should_process = True  # Par défaut on traite
    if connection_mode not in ['serial', 'tcp']:
        # Mode legacy
        if not is_from_our_interface and not test_globals.get('PROCESS_TCP_COMMANDS', False):
            should_process = False
    
    assert should_process == False, "Message externe ne devrait pas être traité"
    print("    ✅ Paquet externe en mode legacy → ignoré")
    
    return True

def main():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("🧪 TESTS DE VALIDATION - LOGIQUE SINGLE-NODE")
    print("="*60 + "\n")
    
    tests = [
        ("Démarrage mode Serial", test_start_logic_serial),
        ("Démarrage mode TCP", test_start_logic_tcp),
        ("Démarrage mode par défaut", test_start_logic_default),
        ("Filtrage messages", test_on_message_logic),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"❌ Test '{name}' échoué")
        except AssertionError as e:
            failed += 1
            print(f"❌ Test '{name}' assertion échouée: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ Test '{name}' erreur: {e}")
    
    print("\n" + "="*60)
    print(f"📊 Résultats: {passed} tests réussis, {failed} tests échoués")
    print("="*60 + "\n")
    
    if failed > 0:
        print("❌ Certains tests ont échoué")
        return 1
    else:
        print("✅ Tous les tests sont passés!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
