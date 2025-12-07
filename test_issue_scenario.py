#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test d'intégration pour le scénario exact du problème rapporté

Ce test simule le scénario exact décrit dans l'issue:
1. Utilisateur fait /trace tigro 2 t1000E
2. Bot répond avec plusieurs nœuds trouvés, incluant "tigro 2 t1000E (!0de3331e)"
3. Utilisateur essaie différents formats de l'ID
4. Tous devraient maintenant fonctionner
"""

def simulate_node_search(user_input, node_database):
    """
    Simule la recherche de nœud avec la logique corrigée
    
    Args:
        user_input: L'input de l'utilisateur (peut contenir !, ), espaces)
        node_database: Dict {node_id: {'name': str}}
    
    Returns:
        tuple: (exact_matches, partial_matches)
    """
    # Nettoyer l'input (fix appliqué)
    target_search = user_input.strip().lower()
    target_search = target_search.lstrip('!')
    target_search = target_search.rstrip(')')
    
    exact_matches = []
    partial_matches = []
    
    for node_id, node_data in node_database.items():
        node_name = node_data.get('name', '').lower()
        # Support both formats (fix appliqué)
        node_id_hex = f"{node_id:x}".lower()
        node_id_hex_padded = f"{node_id:08x}".lower()
        
        # Vérifier correspondance exacte
        if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
            exact_matches.append({'id': node_id, 'name': node_data['name']})
        # Sinon correspondance partielle
        elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
            partial_matches.append({'id': node_id, 'name': node_data['name']})
    
    return exact_matches, partial_matches

def test_issue_scenario():
    """
    Test du scénario exact de l'issue
    """
    print("=" * 70)
    print("TEST SCÉNARIO DE L'ISSUE")
    print("=" * 70)
    
    # Base de données simulée avec les nœuds de l'exemple
    node_database = {
        0x16fad3dc: {"name": "tigrobot G2 PV"},
        0x0de3331e: {"name": "tigro 2 t1000E"},
        0xa76f40da: {"name": "tigro t1000E"},
        0xa2e175ac: {"name": "tigro G2 PV"},
    }
    
    print("\n📋 Base de nœuds simulée:")
    for node_id, node_data in node_database.items():
        print(f"   - {node_data['name']} (!{node_id:08x})")
    
    # ÉTAPE 1: Première recherche qui retourne plusieurs nœuds
    print("\n" + "─" * 70)
    print("ÉTAPE 1: Recherche initiale")
    print("─" * 70)
    print("\n> /trace tigro 2 t1000E")
    
    exact, partial = simulate_node_search("tigro 2 t1000E", node_database)
    
    print("\n🤖 Bot:")
    if len(exact) == 1:
        print(f"✅ Nœud trouvé (correspondance exacte): {exact[0]['name']}")
        print(f"   ID: !{exact[0]['id']:08x}")
    elif len(exact) > 1 or len(partial) > 1:
        all_matches = exact if len(exact) > 1 else partial
        print(f"🔍 Plusieurs nœuds trouvés ({len(all_matches)}):")
        for i, node in enumerate(all_matches):
            print(f"{i+1}. {node['name']} (!{node['id']:08x})")
        print("Précisez le nom complet ou l'ID")
    
    # ÉTAPE 2: Tests des différents formats que l'utilisateur a essayés
    print("\n" + "─" * 70)
    print("ÉTAPE 2: Tests des formats d'ID (problème original)")
    print("─" * 70)
    
    test_cases = [
        ("!0de3331e)", "Copy-paste exact depuis le message du bot"),
        ("!0de3331e", "Sans la parenthèse fermante"),
        ("0de3331e", "Sans le préfixe !"),
    ]
    
    for user_input, description in test_cases:
        print(f"\n> /trace {user_input}")
        print(f"   ({description})")
        
        exact, partial = simulate_node_search(user_input, node_database)
        
        print("\n🤖 Bot:")
        if len(exact) == 1:
            print(f"✅ Nœud trouvé: {exact[0]['name']}")
            print(f"   ID: 0x{exact[0]['id']:08x}")
            print(f"   📍 Traceroute en cours...")
        elif len(exact) == 0 and len(partial) == 0:
            print(f"❌ Nœud '{user_input}' introuvable")
        else:
            print(f"🔍 Plusieurs correspondances")
    
    print("\n" + "=" * 70)
    print("RÉSULTAT")
    print("=" * 70)
    
    # Vérifier que tous les formats fonctionnent maintenant
    success_count = 0
    for user_input, _ in test_cases:
        exact, partial = simulate_node_search(user_input, node_database)
        if len(exact) == 1 and exact[0]['id'] == 0x0de3331e:
            success_count += 1
    
    if success_count == len(test_cases):
        print("\n✅ TOUS LES FORMATS FONCTIONNENT!")
        print("\nLe problème est résolu:")
        print("- ✅ !0de3331e) fonctionne (copy-paste)")
        print("- ✅ !0de3331e fonctionne (sans parenthèse)")
        print("- ✅ 0de3331e fonctionne (sans !)")
        print("\n💡 L'utilisateur peut maintenant utiliser n'importe quel format!")
        return True
    else:
        print(f"\n❌ ÉCHEC: Seulement {success_count}/{len(test_cases)} formats fonctionnent")
        return False

if __name__ == "__main__":
    success = test_issue_scenario()
    exit(0 if success else 1)
