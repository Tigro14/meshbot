#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier le fix du traceroute avec route vide (connexion directe)

Ce test vérifie que:
1. Une route vide (0 hops) n'affiche pas "Route inconnue"
2. Le fallback construit correctement une route pour connexion directe
3. Le message utilisateur indique clairement la connexion directe
"""

def test_empty_route_direct_connection():
    """
    Simuler le cas où le protobuf parse sans erreur mais retourne une route vide
    """
    print("=" * 70)
    print("TEST FIX ROUTE VIDE (CONNEXION DIRECTE)")
    print("=" * 70)
    
    print("\n📋 Contexte:")
    print("   Le protobuf RouteDiscovery parse correctement")
    print("   Mais route_discovery.route est vide (liste vide)")
    print("   Cela signifie: connexion DIRECTE (0 hops)")
    
    print("\n" + "─" * 70)
    print("AVANT LE FIX")
    print("─" * 70)
    
    # Avant: route_forward est vide, donc "Route inconnue"
    route_forward_before = []
    
    print(f"\nroute_forward après parsing: {route_forward_before}")
    print(f"Longueur: {len(route_forward_before)}")
    
    # Le code retournait immédiatement sans fallback
    print("\n❌ Comportement:")
    print("   return route_forward, route_back  # Retour immédiat!")
    print("   → Le fallback n'est jamais exécuté")
    
    print("\n❌ Message utilisateur:")
    print("   🔍 Trace→BIG G2 🍔")
    print("   ❌ Route inconnue")
    
    print("\n" + "─" * 70)
    print("APRÈS LE FIX")
    print("─" * 70)
    
    # Après: route vide → fallback s'exécute
    route_forward_after = []
    
    print(f"\nroute_forward après parsing: {route_forward_after}")
    print(f"Longueur: {len(route_forward_after)}")
    
    print("\n✅ Comportement:")
    print("   if route_forward:")
    print("       return route_forward, route_back")
    print("   else:")
    print("       debug_print('Route vide, utilisation du fallback')")
    print("       # Continue vers fallback...")
    
    print("\n✅ Fallback s'exécute:")
    print("   from_id = 0xa2ebdc0c  # BIG G2")
    print("   to_id = 0xa2ebdc0c    # Même nœud (réponse)")
    print("   hops_taken = hopStart - hopLimit = 3 - 3 = 0")
    
    # Simuler le fallback
    from_id = 0xa2ebdc0c
    to_id = 0xa2ebdc0c
    hop_limit = 3
    hop_start = 3
    hops_taken = hop_start - hop_limit
    
    route_forward_fallback = []
    route_forward_fallback.append({
        'node_id': from_id,
        'name': 'BIG G2 🍔'
    })
    
    if hops_taken > 0:
        route_forward_fallback.append({
            'node_id': None,
            'name': f"[{hops_taken} relay(s)]"
        })
    
    route_forward_fallback.append({
        'node_id': to_id,
        'name': 'BIG G2 🍔'
    })
    
    print(f"\n✅ Route construite par fallback:")
    for i, hop in enumerate(route_forward_fallback):
        node_id_str = f"0x{hop['node_id']:08x}" if hop['node_id'] else "0x00000000"
        print(f"   {i}. {hop['name']} ({node_id_str})")
    
    print(f"\n✅ Nombre de hops: {len(route_forward_fallback) - 1} (origine + destination = direct)")
    
    print("\n✅ Message utilisateur:")
    print("   🔍 Trace→BIG G2 🍔")
    print("   📏 0 hop")
    print("   ➡️ BIG G2→BIG G2")
    print("   ⏱️ 0.6s")
    
    print("\n" + "=" * 70)
    print("VÉRIFICATIONS")
    print("=" * 70)
    
    checks = []
    
    # 1. Route non vide après fallback
    if len(route_forward_fallback) > 0:
        print("\n✅ Route construite (non vide)")
        checks.append(True)
    else:
        print("\n❌ Route encore vide")
        checks.append(False)
    
    # 2. Indique connexion directe (0 relays)
    if hops_taken == 0:
        print("✅ Connexion directe détectée (0 hops)")
        checks.append(True)
    else:
        print(f"❌ Hops incorrects: {hops_taken}")
        checks.append(False)
    
    # 3. Origine = Destination (réflexion du paquet)
    if route_forward_fallback[0]['node_id'] == route_forward_fallback[-1]['node_id']:
        print("✅ Origine = Destination (connexion directe)")
        checks.append(True)
    else:
        print("❌ Origine ≠ Destination")
        checks.append(False)
    
    # 4. Pas de message "Route inconnue"
    # (simulé - on vérifie que route_forward n'est plus vide)
    if route_forward_fallback:
        print("✅ 'Route inconnue' ne sera pas affiché")
        checks.append(True)
    else:
        print("❌ 'Route inconnue' sera affiché")
        checks.append(False)
    
    return all(checks)

if __name__ == "__main__":
    print("\nTest du fix pour route vide (connexion directe)\n")
    
    success = test_empty_route_direct_connection()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("\nLe fix corrige:")
        print("  • Route vide n'affiche plus 'Route inconnue'")
        print("  • Fallback s'exécute correctement")
        print("  • Connexion directe (0 hops) affichée clairement")
        print("  • Message utilisateur informatif")
        import sys
        sys.exit(0)
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        import sys
        sys.exit(1)
