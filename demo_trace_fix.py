#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Démonstration du fix du parsing des IDs dans /trace

Ce script montre comment les différents formats d'ID sont maintenant acceptés.
"""

def demonstrate_fix():
    """Démonstration interactive du fix"""
    
    print("=" * 70)
    print("DÉMONSTRATION DU FIX /trace COMMAND")
    print("=" * 70)
    
    # Simuler un nœud de la base de données
    node_id = 0x0de3331e
    node_name = "tigro 2 t1000E"
    
    print(f"\n📡 Nœud exemple:")
    print(f"   ID: 0x{node_id:08x}")
    print(f"   Nom: {node_name}")
    
    print(f"\n📋 Format suggéré par le bot:")
    print(f"   {node_name} (!{node_id:08x})")
    print(f"                  ↑         ↑")
    print(f"                  !    parenthèse fermante")
    
    # Différents formats que l'utilisateur peut essayer
    test_inputs = [
        "!0de3331e)",  # Copy-paste exact depuis le bot
        "!0de3331e",   # Sans la parenthèse
        "0de3331e",    # Sans le !
        "de3331e",     # Format court (sans zéro de tête)
        "tigro 2",     # Nom partiel
    ]
    
    print("\n" + "=" * 70)
    print("TEST DES DIFFÉRENTS FORMATS")
    print("=" * 70)
    
    for user_input in test_inputs:
        print(f"\n📝 Input utilisateur: '{user_input}'")
        
        # Étape 1: Nettoyage
        cleaned = user_input.strip().lower()
        cleaned = cleaned.lstrip('!')
        cleaned = cleaned.rstrip(')')
        print(f"   ➜ Après nettoyage: '{cleaned}'")
        
        # Étape 2: Génération des formats de comparaison
        node_id_hex = f"{node_id:x}".lower()  # Sans padding
        node_id_hex_padded = f"{node_id:08x}".lower()  # Avec padding
        node_name_lower = node_name.lower()
        
        print(f"   ➜ Formats testés:")
        print(f"      - Nom: '{node_name_lower}'")
        print(f"      - ID court: '{node_id_hex}'")
        print(f"      - ID complet: '{node_id_hex_padded}'")
        
        # Étape 3: Test de correspondance
        match_type = None
        if cleaned == node_name_lower:
            match_type = "correspondance exacte (nom)"
        elif cleaned == node_id_hex:
            match_type = "correspondance exacte (ID court)"
        elif cleaned == node_id_hex_padded:
            match_type = "correspondance exacte (ID complet)"
        elif cleaned in node_name_lower:
            match_type = "correspondance partielle (nom)"
        elif cleaned in node_id_hex or cleaned in node_id_hex_padded:
            match_type = "correspondance partielle (ID)"
        
        if match_type:
            print(f"   ✅ TROUVÉ: {match_type}")
        else:
            print(f"   ❌ NON TROUVÉ")
    
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("\n✅ Tous les formats courants sont maintenant acceptés:")
    print("   - Avec ou sans le préfixe !")
    print("   - Avec ou sans la parenthèse fermante )")
    print("   - Format court (sans zéros de tête) ou complet (8 chiffres)")
    print("   - Nom complet ou partiel")
    print("\n💡 L'utilisateur peut maintenant copier-coller directement depuis")
    print("   les suggestions du bot sans modification!")
    print("=" * 70)

if __name__ == "__main__":
    demonstrate_fix()
