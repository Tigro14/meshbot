#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier que l'alias /bot (sans argument) est correctement routé
"""

def test_bot_pattern_matching():
    """Vérifier que les patterns /bot matchent correctement"""
    print("🧪 Test: Patterns /bot\n")
    
    # Test les différents patterns
    test_cases = [
        ("/bot", "Alias sans argument"),
        ("/bot ", "Commande avec espace mais sans argument"),
        ("/bot hello", "Commande avec argument")
    ]
    
    # Pattern actuel problématique
    pattern_with_space = '/bot '
    print("❌ Pattern actuel: '/bot ' (avec espace)")
    for message, description in test_cases:
        matches = message.startswith(pattern_with_space)
        print(f"  {description}: '{message}' → {matches}")
    
    print()
    
    # Pattern corrigé
    pattern_without_space = '/bot'
    print("✅ Pattern corrigé: '/bot' (sans espace)")
    for message, description in test_cases:
        matches = message.startswith(pattern_without_space)
        print(f"  {description}: '{message}' → {matches}")
    
    print("\n📋 Résultat:")
    print("  Le pattern '/bot ' (avec espace) ne matche PAS l'alias '/bot'")
    print("  Le pattern '/bot' (sans espace) matche TOUS les cas")

def test_broadcast_commands_list():
    """Vérifier la cohérence de la liste broadcast_commands"""
    print("\n🧪 Test: Cohérence broadcast_commands\n")
    
    # Liste actuelle
    broadcast_commands = ['/echo ', '/my', '/weather', '/rain', '/bot ', '/info ', '/propag']
    
    print("Liste actuelle:")
    for cmd in broadcast_commands:
        has_space = cmd.endswith(' ')
        print(f"  {cmd!r:15} → {'avec espace' if has_space else 'sans espace'}")
    
    print("\n❌ Incohérence détectée:")
    print("  /my, /weather, /rain, /propag → SANS espace (✅)")
    print("  /echo, /bot, /info → AVEC espace (❌)")
    
    print("\n✅ Recommandation:")
    print("  Tous les patterns devraient être SANS espace pour matcher l'alias ET les arguments")

if __name__ == "__main__":
    test_bot_pattern_matching()
    test_broadcast_commands_list()
    
    print("\n" + "="*60)
    print("CONCLUSION:")
    print("  Les patterns avec espace empêchent le matching des alias")
    print("  Solution: Retirer l'espace dans broadcast_commands et _route_command")
    print("="*60)
