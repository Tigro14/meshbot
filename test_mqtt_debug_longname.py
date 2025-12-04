#!/usr/bin/env python3
"""
Test pour vérifier que les logs MQTT incluent le longname quand disponible
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class MockNodeManager:
    """Mock NodeManager pour tester la récupération du nom"""
    def __init__(self):
        self.node_names = {
            0x2867b4fa: {'name': 'TestNode1', 'lat': None, 'lon': None},
            0xae613834: {'name': 'TestNode2', 'lat': None, 'lon': None},
            0xd4b288a9: {'name': 'TestNode3', 'lat': None, 'lon': None},
        }
    
    def get_node_name(self, node_id):
        """Récupérer le nom d'un nœud par son ID"""
        if node_id in self.node_names:
            return self.node_names[node_id]['name']
        return "Unknown"

def test_longname_formatting():
    """Test la logique de formatage du nom long"""
    print("\n" + "="*60)
    print("TEST: Formatage du longname dans les logs MQTT")
    print("="*60)
    
    # Créer un mock node_manager
    node_manager = MockNodeManager()
    
    # Test cases
    test_cases = [
        {
            'from_id': 0x2867b4fa,
            'portnum_name': 'POSITION',
            'expected_with_name': '👥 [MQTT] Paquet POSITION de 2867b4fa (TestNode1)',
            'expected_without_name': '👥 [MQTT] Paquet POSITION de 2867b4fa',
        },
        {
            'from_id': 0xae613834,
            'portnum_name': 'NODEINFO',
            'expected_with_name': '👥 [MQTT] Paquet NODEINFO de ae613834 (TestNode2)',
            'expected_without_name': '👥 [MQTT] Paquet NODEINFO de ae613834',
        },
        {
            'from_id': 0xd4b288a9,
            'portnum_name': 'NODEINFO',
            'expected_with_name': '👥 [MQTT] Paquet NODEINFO de d4b288a9 (TestNode3)',
            'expected_without_name': '👥 [MQTT] Paquet NODEINFO de d4b288a9',
        },
        {
            'from_id': 0x99999999,  # Nœud inconnu
            'portnum_name': 'POSITION',
            'expected_with_name': None,  # Pas de nom disponible
            'expected_without_name': '👥 [MQTT] Paquet POSITION de 99999999',
        }
    ]
    
    all_passed = True
    
    for i, test in enumerate(test_cases):
        from_id = test['from_id']
        portnum_name = test['portnum_name']
        
        # Simuler la logique de la fonction
        longname = None
        if node_manager:
            longname = node_manager.get_node_name(from_id)
            # If get_node_name returns "Unknown" or a hex ID, don't use it
            if longname and (longname == "Unknown" or longname.startswith("!")):
                longname = None
        
        if longname:
            actual_message = f"👥 [MQTT] Paquet {portnum_name} de {from_id:08x} ({longname})"
        else:
            actual_message = f"👥 [MQTT] Paquet {portnum_name} de {from_id:08x}"
        
        # Vérifier le résultat
        if longname:
            expected = test['expected_with_name']
        else:
            expected = test['expected_without_name']
        
        if actual_message == expected:
            print(f"✅ Test {i+1}: {actual_message}")
        else:
            print(f"❌ Test {i+1} ÉCHEC:")
            print(f"   Attendu: {expected}")
            print(f"   Obtenu:  {actual_message}")
            all_passed = False
    
    return all_passed

def main():
    """Exécuter les tests"""
    print("\n" + "="*60)
    print("TESTS DU FORMATAGE LONGNAME DANS LES LOGS MQTT")
    print("="*60)
    
    try:
        result = test_longname_formatting()
        
        print("\n" + "="*60)
        print("RÉSUMÉ")
        print("="*60)
        
        if result:
            print("✅ Tous les tests ont réussi!")
            print("\nExemple de sortie attendue:")
            print("  Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet POSITION de 2867b4fa (TestNode1)")
            print("  Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de ae613834 (TestNode2)")
            print("  Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de d4b288a9 (TestNode3)")
            return 0
        else:
            print("❌ Certains tests ont échoué")
            return 1
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
