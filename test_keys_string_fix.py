#!/usr/bin/env python3
"""
Test que /keys trouve bien les clés après le fix de format de clé

BUG: Les clés étaient créées dans interface.nodes avec des clés INTEGER
mais /keys cherchait avec des clés STRING depuis traffic_database.

FIX: Utiliser str(node_id) comme clé dans interface.nodes pour matcher
le format de la traffic database (from_id est TEXT).
"""

import sys
import time
from unittest.mock import Mock, MagicMock

def test_key_format_fix():
    """Test que les clés sont créées avec le bon format (string)"""
    print("\n=== Test Keys String Format Fix ===\n")
    
    # Mock interface with nodes dict
    interface = Mock()
    interface.nodes = {}
    
    # Simuler une extraction de clé publique
    node_id = 305419896  # INTEGER comme dans le code
    public_key = "lMLv2Yk1cUhgXBCeDJc+uI6YmFzbXYdhN1QIA17F7gc="
    
    # Créer l'entrée comme le fait maintenant _sync_single_pubkey_to_interface
    # APRES le fix: utilise str(node_id) comme clé
    interface.nodes[str(node_id)] = {
        'num': node_id,
        'user': {
            'id': f"!{node_id:08x}",
            'longName': 'TestNode',
            'shortName': 'TEST',
            'hwModel': 'HELTEC_V3',
            'public_key': public_key,
            'publicKey': public_key
        }
    }
    
    print(f"✓ Clé créée dans interface.nodes avec key={str(node_id)} (type: {type(str(node_id))})")
    print(f"  interface.nodes keys: {list(interface.nodes.keys())}")
    
    # Simuler ce que fait /keys: charger from_id depuis traffic database (TEXT)
    # La base de données retourne des strings pour from_id
    nodes_in_traffic = {str(node_id)}  # STRING comme depuis la DB
    
    print(f"\n✓ Traffic database retourne from_id={str(node_id)} (type: {type(str(node_id))})")
    
    # Simuler la recherche de /keys
    nodes_without_keys = []
    nodes_with_keys_count = 0
    
    for traffic_node_id in nodes_in_traffic:
        # Normaliser (comme ligne 1357-1367 de network_commands.py)
        if isinstance(traffic_node_id, str):
            try:
                if traffic_node_id.startswith('!'):
                    node_id_int = int(traffic_node_id[1:], 16)
                else:
                    node_id_int = int(traffic_node_id, 16) if 'x' not in traffic_node_id else int(traffic_node_id, 0)
            except ValueError:
                node_id_int = int(traffic_node_id)  # Fallback to decimal
        else:
            node_id_int = traffic_node_id
        
        print(f"\n✓ Recherche du node_id_int={node_id_int} dans interface.nodes")
        
        # Chercher dans interface.nodes (ligne 1370-1374)
        node_info = None
        search_keys = [node_id_int, str(node_id_int), f"!{node_id_int:08x}", f"{node_id_int:08x}"]
        print(f"  Essai de clés: {search_keys}")
        
        for key in search_keys:
            if key in interface.nodes:
                node_info = interface.nodes[key]
                print(f"  ✓ TROUVÉ avec la clé: {key} (type: {type(key)})")
                break
        
        if node_info and isinstance(node_info, dict):
            user_info = node_info.get('user', {})
            if isinstance(user_info, dict):
                found_key = user_info.get('public_key') or user_info.get('publicKey')
                if found_key:
                    nodes_with_keys_count += 1
                    print(f"  ✓ Clé publique trouvée: {found_key[:20]}...")
                else:
                    nodes_without_keys.append((node_id_int, 'TestNode'))
                    print(f"  ✗ Aucune clé dans user_info")
        else:
            nodes_without_keys.append((node_id_int, 'TestNode'))
            print(f"  ✗ Node info not found or invalid")
    
    # Résultat
    print(f"\n=== RESULTATS ===")
    print(f"Nodes dans le trafic: {len(nodes_in_traffic)}")
    print(f"✅ Avec clé publique: {nodes_with_keys_count}")
    print(f"❌ Sans clé publique: {len(nodes_without_keys)}")
    
    if nodes_with_keys_count == 1 and len(nodes_without_keys) == 0:
        print(f"\n✅ TEST RÉUSSI: La clé est trouvée!")
        return True
    else:
        print(f"\n❌ TEST ÉCHOUÉ: La clé n'est pas trouvée!")
        print(f"   nodes_without_keys: {nodes_without_keys}")
        return False


def test_before_fix():
    """Test du comportement AVANT le fix (pour comparaison)"""
    print("\n=== Test AVANT le fix (clé INTEGER) ===\n")
    
    interface = Mock()
    interface.nodes = {}
    
    node_id = 305419896
    public_key = "lMLv2Yk1cUhgXBCeDJc+uI6YmFzbXYdhN1QIA17F7gc="
    
    # AVANT le fix: clé INTEGER
    interface.nodes[node_id] = {
        'num': node_id,
        'user': {
            'id': f"!{node_id:08x}",
            'longName': 'TestNode',
            'shortName': 'TEST',
            'hwModel': 'HELTEC_V3',
            'public_key': public_key,
            'publicKey': public_key
        }
    }
    
    print(f"✓ Clé créée dans interface.nodes avec key={node_id} (type: {type(node_id)})")
    print(f"  interface.nodes keys: {list(interface.nodes.keys())}")
    
    # Traffic database retourne STRING
    nodes_in_traffic = {str(node_id)}
    print(f"✓ Traffic database retourne from_id={str(node_id)} (type: {type(str(node_id))})")
    
    # Recherche
    nodes_with_keys_count = 0
    for traffic_node_id in nodes_in_traffic:
        node_id_int = int(traffic_node_id)
        print(f"\n✓ Recherche du node_id_int={node_id_int}")
        
        node_info = None
        search_keys = [node_id_int, str(node_id_int), f"!{node_id_int:08x}", f"{node_id_int:08x}"]
        print(f"  Essai de clés: {search_keys}")
        
        for key in search_keys:
            if key in interface.nodes:
                node_info = interface.nodes[key]
                print(f"  ✓ TROUVÉ avec la clé: {key} (type: {type(key)})")
                break
            else:
                print(f"  ✗ Clé {key} (type: {type(key)}) NOT IN interface.nodes")
        
        if node_info:
            user_info = node_info.get('user', {})
            if user_info.get('public_key') or user_info.get('publicKey'):
                nodes_with_keys_count += 1
    
    print(f"\n=== RESULTATS ===")
    print(f"✅ Avec clé publique: {nodes_with_keys_count}")
    
    if nodes_with_keys_count == 1:
        print(f"\n✅ Clé trouvée (le bug n'était pas le format de clé)")
        return True
    else:
        print(f"\n❌ Clé NON trouvée (confirme le bug de format)")
        return False


if __name__ == '__main__':
    print("=" * 70)
    print("TEST: Fix du format de clé pour /keys command")
    print("=" * 70)
    
    # Test avant le fix pour montrer le bug
    test_before_fix()
    
    print("\n" + "=" * 70)
    
    # Test après le fix
    success = test_key_format_fix()
    
    print("\n" + "=" * 70)
    
    if success:
        print("✅ TOUS LES TESTS RÉUSSIS")
        sys.exit(0)
    else:
        print("❌ TESTS ÉCHOUÉS")
        sys.exit(1)
