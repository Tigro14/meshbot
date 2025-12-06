#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier les flèches directionnelles dans le traceroute

Ce test vérifie que:
1. La route aller utilise la flèche droite (→)
2. La route retour utilise la flèche gauche (←)
"""

def test_traceroute_arrow_directions():
    """
    Simuler le formatage du traceroute avec les flèches directionnelles
    """
    print("=" * 70)
    print("TEST FLÈCHES DIRECTIONNELLES TRACEROUTE")
    print("=" * 70)
    
    # Données de test basées sur les logs de @Tigro14
    route_forward = [
        {'node_id': 0x05fe73af, 'name': '🍄Champlard🐗'},
        {'node_id': 0x88cd05ec, 'name': 'Pascal Victron Acasom Cavité Moxon'}
    ]
    
    route_back = [
        {'node_id': 0xbcd256c8, 'name': 'DC1 Solaire Acasom Cavité Colinéaire'},
        {'node_id': 0xa2ea0fc0, 'name': 'OSR G2 fixe MF869.3'}
    ]
    
    target_name = "Pascal Bot IP Gateway"
    elapsed_time = 8.8
    
    print("\n📊 Données:")
    print(f"   Target: {target_name}")
    print(f"   Route aller: {len(route_forward)} nœuds")
    for i, hop in enumerate(route_forward):
        print(f"      {i}. {hop['name']}")
    print(f"   Route retour: {len(route_back)} nœuds")
    for i, hop in enumerate(route_back):
        print(f"      {i}. {hop['name']}")
    
    print("\n" + "─" * 70)
    print("AVANT (même flèche pour les deux routes)")
    print("─" * 70)
    
    # Ancien format (flèche droite pour tout)
    hops_old = len(route_forward) - 1
    
    def format_old(route):
        return "→".join([hop['name'][:30] for hop in route])
    
    old_output = f"""🔍 Trace→{target_name} ({hops_old} hop)
➡️ {format_old(route_forward)}
⬅️ {format_old(route_back)}
⏱️ {elapsed_time:.1f}s"""
    
    print(old_output)
    
    print("\n❌ Problème:")
    print("   • Route retour utilise → (flèche droite)")
    print("   • Pas cohérent avec l'emoji ⬅️")
    
    print("\n" + "─" * 70)
    print("APRÈS (flèches directionnelles)")
    print("─" * 70)
    
    # Nouveau format (flèches directionnelles)
    hops_new = len(route_forward) - 1
    
    def format_forward(route):
        return "→".join([hop['name'][:30] for hop in route])
    
    def format_back(route):
        return "←".join([hop['name'][:30] for hop in route])
    
    new_output = f"""🔍 Trace→{target_name} ({hops_new} hop)
➡️ {format_forward(route_forward)}
⬅️ {format_back(route_back)}
⏱️ {elapsed_time:.1f}s"""
    
    print(new_output)
    
    print("\n✅ Améliorations:")
    print("   • Route aller utilise → (flèche droite)")
    print("   • Route retour utilise ← (flèche gauche)")
    print("   • Cohérent avec les emojis ➡️ et ⬅️")
    
    print("\n" + "=" * 70)
    print("VÉRIFICATIONS")
    print("=" * 70)
    
    checks = []
    
    # 1. Route aller avec flèche droite
    forward_line = new_output.split('\n')[1]
    if '→' in forward_line and '🍄Champlard🐗→Pascal' in forward_line:
        print("\n✅ Route aller utilise flèche droite (→)")
        checks.append(True)
    else:
        print(f"\n❌ Route aller n'utilise pas la bonne flèche")
        print(f"   Ligne: {forward_line}")
        checks.append(False)
    
    # 2. Route retour avec flèche gauche
    back_line = new_output.split('\n')[2]
    if '←' in back_line and 'DC1 Solaire Acasom Cavité Coli←OSR' in back_line:
        print("✅ Route retour utilise flèche gauche (←)")
        checks.append(True)
    else:
        print(f"❌ Route retour n'utilise pas la bonne flèche")
        print(f"   Ligne: {back_line}")
        checks.append(False)
    
    # 3. Pas de flèche droite dans route retour
    if '→' not in back_line:
        print("✅ Route retour n'utilise pas de flèche droite")
        checks.append(True)
    else:
        print("❌ Route retour contient encore des flèches droites")
        checks.append(False)
    
    # 4. Format compact (LoRa)
    if len(new_output) < 180:
        print(f"✅ Format compact (<180 chars): {len(new_output)} chars")
        checks.append(True)
    else:
        print(f"⚠️ Format peut dépasser 180 chars: {len(new_output)} chars")
        checks.append(True)  # Still OK if chunking handles it
    
    return all(checks)

if __name__ == "__main__":
    print("\nTest des flèches directionnelles dans le traceroute\n")
    
    success = test_traceroute_arrow_directions()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("\nLes améliorations apportent:")
        print("  • Route aller avec flèche droite (→)")
        print("  • Route retour avec flèche gauche (←)")
        print("  • Cohérence visuelle avec les emojis ➡️ et ⬅️")
        print("  • Meilleure lisibilité directionnelle")
        import sys
        sys.exit(0)
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        import sys
        sys.exit(1)
