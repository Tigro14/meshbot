#!/usr/bin/env python3
"""
Test pour vérifier que la reconnexion TCP ne génère plus d'AttributeError

Ce test vérifie que:
1. self.mesh_traceroute_manager n'existe plus (ancien nom incorrect)
2. self.mesh_traceroute est bien utilisé
3. Le code de reconnexion TCP n'échoue pas avec AttributeError
"""

import sys
import os
import types
from unittest.mock import Mock, patch, MagicMock

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_tcp_reconnection_no_attribute_error():
    """
    Test que _reconnect_tcp_interface n'échoue pas avec AttributeError
    
    Ce test vérifie directement le code de reconnexion sans créer un bot complet
    """
    print("\n🧪 Test: TCP reconnection sans AttributeError")
    
    # Test simple: vérifier que le code utilise bien mesh_traceroute et non mesh_traceroute_manager
    # On lit le fichier pour vérifier que le fix est appliqué
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Vérifier que mesh_traceroute_manager n'apparaît pas dans _reconnect_tcp_interface
    reconnect_code = content[content.find('def _reconnect_tcp_interface'):content.find('def _reconnect_tcp_interface') + 2000]
    
    # Vérifier qu'on n'utilise plus mesh_traceroute_manager
    assert 'mesh_traceroute_manager' not in reconnect_code, \
        "❌ mesh_traceroute_manager ne devrait plus être utilisé dans _reconnect_tcp_interface"
    print("✅ mesh_traceroute_manager n'est plus utilisé dans _reconnect_tcp_interface")
    
    # Vérifier qu'on utilise mesh_traceroute
    assert 'if self.mesh_traceroute:' in reconnect_code, \
        "❌ mesh_traceroute devrait être utilisé dans _reconnect_tcp_interface"
    print("✅ mesh_traceroute est correctement utilisé")
    
    # Vérifier la syntaxe correcte
    assert 'self.mesh_traceroute.interface = self.interface' in reconnect_code, \
        "❌ mesh_traceroute.interface devrait être mis à jour"
    print("✅ mesh_traceroute.interface est correctement mis à jour")
    
    print("\n✅ TOUS LES TESTS RÉUSSIS")
    return True

def test_mesh_traceroute_consistency():
    """
    Test que mesh_traceroute est utilisé de manière cohérente dans tout le fichier
    """
    print("\n🧪 Test: Cohérence de l'utilisation de mesh_traceroute")
    
    # Lire le fichier main_bot.py
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Compter les occurrences de mesh_traceroute (correct)
    mesh_traceroute_count = content.count('self.mesh_traceroute')
    print(f"✅ self.mesh_traceroute utilisé {mesh_traceroute_count} fois")
    
    # Compter les occurrences de mesh_traceroute_manager (incorrect, devrait être 0)
    mesh_traceroute_manager_count = content.count('self.mesh_traceroute_manager')
    
    assert mesh_traceroute_manager_count == 0, \
        f"❌ self.mesh_traceroute_manager ne devrait plus être utilisé (trouvé {mesh_traceroute_manager_count} fois)"
    print("✅ self.mesh_traceroute_manager n'est plus utilisé")
    
    # Vérifier l'import
    assert 'from mesh_traceroute_manager import MeshTracerouteManager' in content, \
        "❌ L'import MeshTracerouteManager devrait être présent"
    print("✅ Import MeshTracerouteManager correct")
    
    print("✅ Test réussi")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST FIX TCP RECONNECTION - AttributeError mesh_traceroute_manager")
    print("=" * 70)
    
    results = [
        test_tcp_reconnection_no_attribute_error(),
        test_mesh_traceroute_consistency(),
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
        print("- self.mesh_traceroute_manager remplacé par self.mesh_traceroute")
        print("- Cohérent avec le reste du code")
        print("- Plus d'AttributeError lors de la reconnexion TCP")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
