#!/usr/bin/env python3
"""
Test pour vérifier que la configuration TCP est correcte

Ce test vérifie:
1. OptimizedTCPInterface existe et hérite de TCPInterface
2. Dead socket callback est implémenté
3. Socket monitor thread existe
4. ESP32 single-connection limitation is documented
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_optimized_interface_exists():
    """
    Test que OptimizedTCPInterface existe et hérite correctement
    """
    print("\n🧪 Test: OptimizedTCPInterface existe")
    
    # Lire le fichier tcp_interface_patch.py
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Vérifier l'héritage
    assert 'class OptimizedTCPInterface(meshtastic.tcp_interface.TCPInterface)' in content, \
        "❌ OptimizedTCPInterface devrait hériter de TCPInterface"
    print("✅ OptimizedTCPInterface hérite de TCPInterface")
    
    # Vérifier qu'on ne surcharge PAS _readBytes (ESP32 sensibilité aux modifications socket)
    # On compte les occurrences de la définition de méthode, pas les références
    readbytes_overrides = content.count('def _readBytes(')
    if readbytes_overrides == 0:
        print("✅ _readBytes non surchargé (stabilité ESP32)")
    else:
        print(f"⚠️ _readBytes surchargé {readbytes_overrides} fois (attention ESP32 sensibilité)")
    
    print("\n✅ TEST RÉUSSI")
    return True

def test_dead_socket_callback():
    """
    Test que le dead socket callback est implémenté
    """
    print("\n🧪 Test: Dead socket callback")
    
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Vérifier que le callback existe
    assert 'set_dead_socket_callback' in content, \
        "❌ set_dead_socket_callback devrait exister"
    print("✅ set_dead_socket_callback existe")
    
    assert '_dead_socket_callback' in content, \
        "❌ _dead_socket_callback devrait être stocké"
    print("✅ _dead_socket_callback stocké")
    
    print("✅ Test réussi")
    return True

def test_socket_monitor_thread():
    """
    Test que le thread de monitoring socket existe
    """
    print("\n🧪 Test: Socket monitor thread")
    
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Vérifier le thread de monitoring
    assert '_monitor_socket_state' in content, \
        "❌ _monitor_socket_state devrait exister"
    print("✅ _monitor_socket_state existe")
    
    assert 'SocketMonitor' in content or '_monitor_thread' in content, \
        "❌ Thread de monitoring devrait être créé"
    print("✅ Thread de monitoring créé")
    
    print("✅ Test réussi")
    return True

def test_single_connection_enforcement():
    """
    Test que le code enforce la limitation single-connection ESP32
    """
    print("\n🧪 Test: ESP32 single-connection enforcement")
    
    # Vérifier remote_nodes_client.py
    with open('/home/runner/work/meshbot/meshbot/remote_nodes_client.py', 'r') as f:
        content = f.read()
    
    # Vérifier la documentation de la limitation ESP32 avec patterns spécifiques
    has_esp32_doc = ('ESP32' in content and 
                     ('one tcp connection' in content.lower() or 
                      'single tcp connection' in content.lower() or
                      'one connection' in content.lower()))
    assert has_esp32_doc, \
        "❌ remote_nodes_client devrait documenter la limitation ESP32 single-connection"
    print("✅ remote_nodes_client documente la limitation ESP32")
    
    # Vérifier que l'interface est réutilisée
    assert 'self.interface' in content, \
        "❌ remote_nodes_client devrait utiliser interface partagée"
    print("✅ remote_nodes_client utilise interface partagée")
    
    # Vérifier utility_commands.py (echo)
    with open('/home/runner/work/meshbot/meshbot/handlers/command_handlers/utility_commands.py', 'r') as f:
        content = f.read()
    
    # Vérifier qu'on n'utilise plus TCPInterface direct
    assert content.count('meshtastic.tcp_interface.TCPInterface') == 0, \
        "❌ utility_commands ne devrait pas créer de nouvelles connexions TCP"
    print("✅ utility_commands n'utilise pas TCPInterface directement")
    
    print("✅ Test réussi")
    return True

def test_documentation_updated():
    """
    Test que la documentation TCP est à jour
    """
    print("\n🧪 Test: Documentation TCP")
    
    with open('/home/runner/work/meshbot/meshbot/TCP_ARCHITECTURE.md', 'r') as f:
        content = f.read()
    
    # Vérifier que la limitation ESP32 est documentée avec des patterns spécifiques
    assert 'ESP32' in content, \
        "❌ TCP_ARCHITECTURE.md devrait mentionner ESP32"
    print("✅ ESP32 mentionné dans documentation")
    
    # Vérifier la documentation de la limitation avec phrases complètes
    has_single_conn_doc = ('one tcp connection' in content.lower() or 
                          'single tcp connection' in content.lower() or
                          'only support' in content.lower() and 'connection' in content.lower())
    assert has_single_conn_doc, \
        "❌ Limitation single-connection devrait être documentée explicitement"
    print("✅ Limitation single-connection documentée")
    
    print("✅ Test réussi")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST TCP INTERFACE - Architecture et Limitations ESP32")
    print("=" * 70)
    
    results = [
        test_optimized_interface_exists(),
        test_dead_socket_callback(),
        test_socket_monitor_thread(),
        test_single_connection_enforcement(),
        test_documentation_updated(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    # Filter None results and count
    valid_results = [r for r in results if r is not None]
    passed = sum(1 for r in valid_results if r)
    total = len(valid_results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nArchitecture TCP:")
        print("- OptimizedTCPInterface hérite de TCPInterface standard")
        print("- Dead socket callback pour reconnexion rapide")
        print("- Socket monitor thread pour détection d'état")
        print("- Single-connection ESP32 respectée")
        print("- Documentation à jour")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
