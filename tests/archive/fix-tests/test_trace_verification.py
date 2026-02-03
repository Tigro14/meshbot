#!/usr/bin/env python3
"""
Simple verification test for /trace fix

This verifies that the fixed code:
1. No longer imports SafeTCPConnection
2. No longer uses REMOTE_NODE_HOST
3. Uses interface.sendData() instead of sendText()
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports_removed():
    """Verify SafeTCPConnection import is removed"""
    print("\n🧪 Test: Vérification des imports")
    
    with open('telegram_bot/traceroute_manager.py', 'r') as f:
        content = f.read()
    
    # Vérifier que SafeTCPConnection n'est plus importé
    assert 'from safe_tcp_connection import SafeTCPConnection' not in content, \
        "❌ SafeTCPConnection ne devrait plus être importé"
    print("✅ SafeTCPConnection n'est plus importé")
    
    # Vérifier que REMOTE_NODE_HOST n'est plus importé
    assert 'from config import REMOTE_NODE_HOST' not in content, \
        "❌ REMOTE_NODE_HOST ne devrait plus être importé"
    print("✅ REMOTE_NODE_HOST n'est plus importé")
    
    return True

def test_sendtext_removed():
    """Verify sendText() is no longer used for traceroute"""
    print("\n🧪 Test: Vérification sendText() supprimé")
    
    with open('telegram_bot/traceroute_manager.py', 'r') as f:
        lines = f.readlines()
    
    # Chercher sendText() dans _execute_active_trace
    in_execute_active_trace = False
    sendtext_found = False
    
    for line in lines:
        if 'def _execute_active_trace(' in line:
            in_execute_active_trace = True
        elif in_execute_active_trace and line.strip().startswith('def '):
            # Nouvelle fonction, on sort de _execute_active_trace
            break
        elif in_execute_active_trace and 'sendText(' in line:
            sendtext_found = True
            break
    
    assert not sendtext_found, \
        "❌ sendText() ne devrait plus être utilisé dans _execute_active_trace"
    print("✅ sendText() n'est plus utilisé pour traceroute")
    
    return True

def test_senddata_present():
    """Verify sendData() with TRACEROUTE_APP is used"""
    print("\n🧪 Test: Vérification sendData() utilisé")
    
    with open('telegram_bot/traceroute_manager.py', 'r') as f:
        content = f.read()
    
    # Vérifier que sendData() est utilisé
    assert 'interface.sendData(' in content, \
        "❌ interface.sendData() devrait être utilisé"
    print("✅ interface.sendData() est utilisé")
    
    # Vérifier que TRACEROUTE_APP est spécifié
    assert "portNum='TRACEROUTE_APP'" in content, \
        "❌ portNum='TRACEROUTE_APP' devrait être spécifié"
    print("✅ portNum='TRACEROUTE_APP' est spécifié")
    
    # Vérifier que wantResponse=True
    assert "wantResponse=True" in content, \
        "❌ wantResponse=True devrait être spécifié"
    print("✅ wantResponse=True est spécifié")
    
    return True

def test_interface_check():
    """Verify interface availability check is present"""
    print("\n🧪 Test: Vérification check de l'interface")
    
    with open('telegram_bot/traceroute_manager.py', 'r') as f:
        content = f.read()
    
    # Vérifier qu'on récupère l'interface
    assert 'interface = self.telegram.message_handler.interface' in content, \
        "❌ Devrait récupérer l'interface du message_handler"
    print("✅ Interface récupérée depuis message_handler")
    
    # Vérifier qu'on check si l'interface est None
    assert 'if not interface:' in content, \
        "❌ Devrait vérifier si l'interface est None"
    print("✅ Check de disponibilité de l'interface présent")
    
    return True

def test_no_tcp_connection():
    """Verify no TCP connection is created"""
    print("\n🧪 Test: Vérification pas de nouvelle connexion TCP")
    
    with open('telegram_bot/traceroute_manager.py', 'r') as f:
        lines = f.readlines()
    
    # Chercher SafeTCPConnection dans _execute_active_trace
    in_execute_active_trace = False
    tcp_connection_found = False
    
    for line in lines:
        if 'def _execute_active_trace(' in line:
            in_execute_active_trace = True
        elif in_execute_active_trace and line.strip().startswith('def '):
            break
        elif in_execute_active_trace and 'SafeTCPConnection(' in line:
            tcp_connection_found = True
            break
    
    assert not tcp_connection_found, \
        "❌ SafeTCPConnection ne devrait plus être utilisé"
    print("✅ Pas de nouvelle connexion TCP créée")
    
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("VÉRIFICATION FIX /TRACE COMMAND")
    print("=" * 70)
    
    results = [
        test_imports_removed(),
        test_sendtext_removed(),
        test_senddata_present(),
        test_interface_check(),
        test_no_tcp_connection(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nLe fix est correct:")
        print("- SafeTCPConnection n'est plus importé ni utilisé")
        print("- REMOTE_NODE_HOST n'est plus requis")
        print("- sendText() n'est plus utilisé pour traceroute")
        print("- sendData() avec TRACEROUTE_APP est utilisé")
        print("- L'interface du bot est utilisée (pas de nouvelle TCP)")
        print("- Check de disponibilité de l'interface présent")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
