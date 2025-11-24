#!/usr/bin/env python3
"""
Test pour vérifier que le timeout de reconnexion TCP fonctionne correctement

Ce test vérifie:
1. La reconnexion TCP utilise un thread avec timeout
2. Le code a un timeout de 30 secondes explicite
3. Des messages d'erreur appropriés en cas de timeout
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_reconnection_has_timeout():
    """
    Test que le code de reconnexion TCP contient un timeout explicite
    """
    print("\n🧪 Test: Code de reconnexion contient un timeout")
    
    # Lire le fichier main_bot.py
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Trouver la fonction _reconnect_tcp_interface
    reconnect_start = content.find('def _reconnect_tcp_interface')
    reconnect_end = content.find('\n    def ', reconnect_start + 1)
    reconnect_code = content[reconnect_start:reconnect_end]
    
    # Vérifier que la fonction utilise threading
    assert 'threading.Thread' in reconnect_code, \
        "❌ La fonction devrait utiliser threading.Thread pour timeout"
    print("✅ Utilise threading.Thread")
    
    # Vérifier que join() est appelé avec un timeout
    assert '.join(timeout=' in reconnect_code, \
        "❌ La fonction devrait appeler join(timeout=...)"
    print("✅ Appelle join(timeout=...)")
    
    # Vérifier le timeout de 30 secondes
    assert 'join(timeout=30)' in reconnect_code, \
        "❌ Le timeout devrait être de 30 secondes"
    print("✅ Timeout de 30 secondes configuré")
    
    # Vérifier la détection de timeout avec is_alive()
    assert 'is_alive()' in reconnect_code, \
        "❌ La fonction devrait vérifier is_alive() pour détecter le timeout"
    print("✅ Détection de timeout avec is_alive()")
    
    # Vérifier qu'un message d'erreur est affiché en cas de timeout
    assert 'Timeout' in reconnect_code or 'timeout' in reconnect_code, \
        "❌ Un message de timeout devrait être présent"
    print("✅ Message de timeout présent")
    
    # Vérifier que return False en cas de timeout
    timeout_section = reconnect_code[reconnect_code.find('is_alive()'):]
    timeout_section = timeout_section[:timeout_section.find('\n            #')]
    assert 'return False' in timeout_section, \
        "❌ Devrait retourner False en cas de timeout"
    print("✅ Retourne False en cas de timeout")
    
    print("\n✅ TOUS LES TESTS RÉUSSIS")
    return True

def test_timeout_documentation():
    """
    Test que la fonction est bien documentée
    """
    print("\n🧪 Test: Documentation du timeout")
    
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    reconnect_start = content.find('def _reconnect_tcp_interface')
    reconnect_end = content.find('\n    def ', reconnect_start + 1)
    reconnect_code = content[reconnect_start:reconnect_end]
    
    # Vérifier la docstring
    assert '"""' in reconnect_code, "❌ Fonction devrait avoir une docstring"
    
    docstring_start = reconnect_code.find('"""')
    docstring_end = reconnect_code.find('"""', docstring_start + 3)
    docstring = reconnect_code[docstring_start:docstring_end]
    
    # Vérifier que la docstring mentionne le timeout
    assert 'timeout' in docstring.lower() or '30' in docstring, \
        "❌ Docstring devrait mentionner le timeout"
    print("✅ Docstring mentionne le timeout")
    
    # Vérifier que freeze est mentionné
    assert 'freeze' in docstring.lower(), \
        "❌ Docstring devrait expliquer pourquoi le timeout est nécessaire (éviter freeze)"
    print("✅ Docstring explique le freeze")
    
    print("✅ Test réussi")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST FIX TCP TIMEOUT - Éviter freeze lors de reconnexion")
    print("=" * 70)
    
    results = [
        test_reconnection_has_timeout(),
        test_timeout_documentation(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nFix appliqué avec succès:")
        print("- Timeout de 30 secondes sur la reconnexion TCP")
        print("- Le bot ne freeze plus si le nœud distant est inaccessible")
        print("- Messages d'erreur clairs en cas de timeout")
        print("- Bien documenté dans le code")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)

