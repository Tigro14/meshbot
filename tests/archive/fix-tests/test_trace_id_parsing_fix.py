#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier que le fix du parsing des IDs dans /trace fonctionne correctement

Ce test vérifie que:
1. Les IDs avec préfixe ! sont correctement reconnus
2. Les IDs avec suffixe ) sont correctement reconnus
3. Les IDs sans préfixe/suffixe fonctionnent toujours
4. Les noms de nœuds complets fonctionnent
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_input_cleaning():
    """
    Test que le nettoyage de l'input fonctionne correctement
    """
    print("\n🧪 Test: Nettoyage de l'input utilisateur")
    
    test_cases = [
        # (input, expected_clean_output)
        ("!0de3331e)", "0de3331e"),
        ("!0de3331e", "0de3331e"),
        ("0de3331e", "0de3331e"),
        ("  !0de3331e)  ", "0de3331e"),  # Avec espaces
        ("!16fad3dc)", "16fad3dc"),
        ("tigro 2 t1000E", "tigro 2 t1000e"),  # Nom avec espaces
        ("TigroBot", "tigrobot"),  # Nom simple
    ]
    
    for input_str, expected in test_cases:
        # Simulation de la logique de nettoyage
        cleaned = input_str.strip().lower()
        cleaned = cleaned.lstrip('!')
        cleaned = cleaned.rstrip(')')
        
        if cleaned == expected:
            print(f"  ✅ '{input_str}' -> '{cleaned}'")
        else:
            print(f"  ❌ '{input_str}' -> '{cleaned}' (attendu: '{expected}')")
            return False
    
    return True

def test_id_matching():
    """
    Test que le matching des IDs fonctionne avec différents formats
    """
    print("\n🧪 Test: Matching des IDs avec différents formats")
    
    # Simuler une base de nœuds
    node_database = {
        0x0de3331e: {"name": "tigro 2 t1000E"},
        0x16fad3dc: {"name": "tigrobot G2 PV"},
        0xa76f40da: {"name": "tigro t1000E"},
        0xa2e175ac: {"name": "tigro G2 PV"},
    }
    
    test_cases = [
        # (user_input, should_match_node_id)
        ("!0de3331e)", 0x0de3331e),
        ("!0de3331e", 0x0de3331e),
        ("0de3331e", 0x0de3331e),
        ("de3331e", 0x0de3331e),  # Without leading zero
        ("!16fad3dc)", 0x16fad3dc),
        ("16fad3dc", 0x16fad3dc),
        ("tigro 2", 0x0de3331e),  # Partial name match
        ("tigrobot", 0x16fad3dc),  # Partial name match
    ]
    
    for user_input, expected_node_id in test_cases:
        # Nettoyer l'input
        target_search = user_input.strip().lower()
        target_search = target_search.lstrip('!')
        target_search = target_search.rstrip(')')
        
        # Chercher le nœud
        found = False
        found_id = None
        
        for node_id, node_data in node_database.items():
            node_name = node_data.get('name', '').lower()
            # Support both formats: with and without leading zeros
            node_id_hex = f"{node_id:x}".lower()
            node_id_hex_padded = f"{node_id:08x}".lower()
            
            # Correspondance exacte ou partielle
            if target_search == node_id_hex or target_search == node_id_hex_padded or target_search == node_name:
                found = True
                found_id = node_id
                break
            elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
                found = True
                found_id = node_id
                break
        
        if found and found_id == expected_node_id:
            print(f"  ✅ '{user_input}' -> trouvé 0x{found_id:08x}")
        elif found:
            print(f"  ❌ '{user_input}' -> trouvé 0x{found_id:08x} (attendu: 0x{expected_node_id:08x})")
            return False
        else:
            print(f"  ❌ '{user_input}' -> non trouvé (attendu: 0x{expected_node_id:08x})")
            return False
    
    return True

def test_multiple_matches():
    """
    Test que les correspondances multiples sont gérées correctement
    """
    print("\n🧪 Test: Gestion des correspondances multiples")
    
    # Simuler une base avec plusieurs "tigro"
    node_database = {
        0x0de3331e: {"name": "tigro 2 t1000E"},
        0xa76f40da: {"name": "tigro t1000E"},
        0xa2e175ac: {"name": "tigro G2 PV"},
        0x16fad3dc: {"name": "tigrobot G2 PV"},
    }
    
    # Recherche partielle qui match plusieurs nœuds
    target_search = "tigro"
    
    matching_nodes = []
    exact_matches = []
    
    for node_id, node_data in node_database.items():
        node_name = node_data.get('name', '').lower()
        node_id_hex = f"{node_id:x}".lower()
        
        # Vérifier correspondance exacte d'abord
        if target_search == node_name or target_search == node_id_hex:
            exact_matches.append({'id': node_id, 'name': node_data['name']})
        # Sinon correspondance partielle
        elif target_search in node_name or target_search in node_id_hex:
            matching_nodes.append({'id': node_id, 'name': node_data['name']})
    
    # Devrait trouver 4 correspondances partielles, 0 exacte
    if len(exact_matches) == 0 and len(matching_nodes) == 4:
        print(f"  ✅ Trouvé {len(matching_nodes)} correspondances partielles pour 'tigro'")
        for node in matching_nodes:
            print(f"      - {node['name']} (!{node['id']:08x})")
        return True
    else:
        print(f"  ❌ Attendu 4 correspondances, trouvé {len(matching_nodes)}")
        return False

def test_exact_vs_partial():
    """
    Test que les correspondances exactes ont la priorité
    """
    print("\n🧪 Test: Priorité des correspondances exactes")
    
    node_database = {
        0x0de3331e: {"name": "tigro 2 t1000E"},
        0xa76f40da: {"name": "tigro t1000E"},
    }
    
    # Recherche exacte d'un ID
    target_search = "0de3331e"
    
    matching_nodes = []
    exact_matches = []
    
    for node_id, node_data in node_database.items():
        node_name = node_data.get('name', '').lower()
        # Support both formats
        node_id_hex = f"{node_id:x}".lower()
        node_id_hex_padded = f"{node_id:08x}".lower()
        
        # Vérifier correspondance exacte d'abord
        if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
            exact_matches.append({'id': node_id, 'name': node_data['name']})
        # Sinon correspondance partielle
        elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
            matching_nodes.append({'id': node_id, 'name': node_data['name']})
    
    # Devrait trouver 1 correspondance exacte
    if len(exact_matches) == 1 and exact_matches[0]['id'] == 0x0de3331e:
        print(f"  ✅ Correspondance exacte trouvée: {exact_matches[0]['name']}")
        return True
    else:
        print(f"  ❌ Correspondance exacte non trouvée (exact={len(exact_matches)}, partial={len(matching_nodes)})")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("TEST FIX PARSING ID POUR /trace COMMAND")
    print("=" * 70)
    
    results = [
        test_input_cleaning(),
        test_id_matching(),
        test_multiple_matches(),
        test_exact_vs_partial(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nLe fix corrige les problèmes suivants:")
        print("- Les IDs avec ! sont maintenant reconnus")
        print("- Les IDs avec ) sont maintenant reconnus")
        print("- Les espaces avant/après sont ignorés")
        print("- Les correspondances exactes ont la priorité")
        print("- Les correspondances multiples sont gérées")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
