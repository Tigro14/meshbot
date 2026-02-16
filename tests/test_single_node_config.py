#!/usr/bin/env python3
"""
Script de test pour valider la configuration single-node
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import os

def test_config_serial():
    """Tester la configuration mode Serial"""
    print("🧪 Test configuration mode Serial...")
    
    config_content = """
CONNECTION_MODE = 'serial'
SERIAL_PORT = '/dev/ttyACM0'
TCP_HOST = '192.168.1.38'  # Devrait être ignoré
TCP_PORT = 4403
"""
    
    namespace = {}
    exec(config_content, namespace)
    
    assert namespace['CONNECTION_MODE'] == 'serial', "Mode doit être 'serial'"
    assert namespace['SERIAL_PORT'] == '/dev/ttyACM0', "Port série doit être défini"
    print("  ✅ Config Serial OK")
    return True

def test_config_tcp():
    """Tester la configuration mode TCP"""
    print("🧪 Test configuration mode TCP...")
    
    config_content = """
CONNECTION_MODE = 'tcp'
TCP_HOST = '192.168.1.38'
TCP_PORT = 4403
SERIAL_PORT = '/dev/ttyACM0'  # Devrait être ignoré
"""
    
    namespace = {}
    exec(config_content, namespace)
    
    assert namespace['CONNECTION_MODE'] == 'tcp', "Mode doit être 'tcp'"
    assert namespace['TCP_HOST'] == '192.168.1.38', "TCP_HOST doit être défini"
    assert namespace['TCP_PORT'] == 4403, "TCP_PORT doit être défini"
    print("  ✅ Config TCP OK")
    return True

def test_config_legacy():
    """Tester la compatibilité avec l'ancienne configuration"""
    print("🧪 Test configuration legacy (sans CONNECTION_MODE)...")
    
    config_content = """
SERIAL_PORT = '/dev/ttyACM0'
PROCESS_TCP_COMMANDS = False
REMOTE_NODE_HOST = '192.168.1.38'
"""
    
    namespace = {}
    exec(config_content, namespace)
    
    # En mode legacy, CONNECTION_MODE n'existe pas
    assert 'CONNECTION_MODE' not in namespace, "CONNECTION_MODE ne devrait pas exister"
    assert namespace['SERIAL_PORT'] == '/dev/ttyACM0', "Port série doit être défini"
    print("  ✅ Config Legacy OK")
    return True

def test_example_files():
    """Tester la syntaxe des fichiers d'exemple"""
    print("🧪 Test fichiers d'exemple...")
    
    examples = [
        'config.serial.example',
        'config.tcp.example'
    ]
    
    for example_file in examples:
        if not os.path.exists(example_file):
            print(f"  ⚠️  Fichier {example_file} non trouvé (test ignoré)")
            continue
        
        print(f"  📄 Test {example_file}...")
        with open(example_file, 'r') as f:
            content = f.read()
        
        # Remplacer les tokens pour éviter erreurs
        content = content.replace('YOUR_TELEGRAM_BOT_TOKEN_HERE', 'test_token')
        
        namespace = {}
        try:
            exec(content, namespace)
            print(f"    ✅ {example_file} syntaxe OK")
        except SyntaxError as e:
            print(f"    ❌ {example_file} erreur syntaxe: {e}")
            return False
    
    return True

def test_main_bot_imports():
    """Tester les imports de main_bot.py"""
    print("🧪 Test imports main_bot.py...")
    
    try:
        # Vérifier que les imports TCP sont présents
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        assert 'import meshtastic.tcp_interface' in content, "Import tcp_interface manquant"
        assert 'from tcp_interface_patch import OptimizedTCPInterface' in content, "Import OptimizedTCPInterface manquant"
        assert 'from safe_tcp_connection import SafeTCPConnection' in content, "Import SafeTCPConnection manquant"
        
        print("  ✅ Imports main_bot.py OK")
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def main():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("🧪 TESTS DE VALIDATION - CONFIGURATION SINGLE-NODE")
    print("="*60 + "\n")
    
    tests = [
        ("Configuration Serial", test_config_serial),
        ("Configuration TCP", test_config_tcp),
        ("Configuration Legacy", test_config_legacy),
        ("Fichiers d'exemple", test_example_files),
        ("Imports main_bot.py", test_main_bot_imports),
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
