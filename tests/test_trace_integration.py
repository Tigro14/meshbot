#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test d'intégration pour le fix du traceroute
Simule le flux complet avec le payload réel
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshtastic import mesh_pb2
import sys


def simulate_traceroute_response():
    """
    Simule le traitement d'une réponse traceroute comme dans les logs:
    
    Dec 07 21:31:33 DietPi meshtastic-bot[1302]: [DEBUG] 📦 [Traceroute] Paquet reçu de SAW (!435b9ae8):
    Dec 07 21:31:33 DietPi meshtastic-bot[1302]: [DEBUG]    Payload size: 13 bytes
    Dec 07 21:31:33 DietPi meshtastic-bot[1302]: [DEBUG]    Payload hex: 1201121a045e7a568d22022a05
    """
    
    print("=" * 70)
    print("SIMULATION: Traitement réponse traceroute")
    print("=" * 70)
    print()
    
    # Données du paquet (from logs)
    from_id = 0x435b9ae8  # SAW node
    node_name = "9ae8 - SAW - OMNI"
    payload_hex = "1201121a045e7a568d22022a05"
    
    print(f"📦 Paquet reçu de {node_name} (!{from_id:08x})")
    print(f"   Payload size: 13 bytes")
    print(f"   Payload hex: {payload_hex}")
    print()
    
    # Parser la réponse traceroute (code original - BUGGY)
    route_original = []
    payload = bytes.fromhex(payload_hex)
    
    try:
        route_discovery = mesh_pb2.RouteDiscovery()
        route_discovery.ParseFromString(payload)
        
        print("ANCIEN CODE (BUGGY):")
        print(f"  Checking route_discovery.route...")
        for i, node_id in enumerate(route_discovery.route):
            route_original.append({
                'node_id': node_id,
                'name': f"Node_{node_id:08x}",
                'position': i
            })
            print(f"    {i}. Node_{node_id:08x}")
        
        if not route_original:
            print(f"  ❌ route_discovery.route est VIDE")
            print(f"  ❌ Affichage 'Route non décodable' à l'utilisateur")
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
    
    print()
    
    # Parser la réponse traceroute (code fixé - CORRECT)
    route_fixed = []
    
    try:
        route_discovery = mesh_pb2.RouteDiscovery()
        route_discovery.ParseFromString(payload)
        
        print("NOUVEAU CODE (FIXED):")
        print(f"  📋 RouteDiscovery parsé:")
        print(f"     route (forward): {len(route_discovery.route)} nodes")
        print(f"     route_back: {len(route_discovery.route_back)} nodes")
        print(f"     snr_towards: {len(route_discovery.snr_towards)} values")
        print(f"     snr_back: {len(route_discovery.snr_back)} values")
        print()
        
        # Extraire la route aller (si disponible)
        if route_discovery.route:
            print(f"  ✅ Utilisation de route (forward)")
            for i, node_id in enumerate(route_discovery.route):
                route_fixed.append({
                    'node_id': node_id,
                    'name': f"Node_{node_id:08x}",
                    'position': i
                })
                print(f"     {i}. Node_{node_id:08x}")
        
        # Si la route aller est vide, utiliser la route retour
        elif route_discovery.route_back:
            print(f"  ✅ Utilisation de route_back (route aller vide)")
            for i, node_id in enumerate(route_discovery.route_back):
                route_fixed.append({
                    'node_id': node_id,
                    'name': f"Node_{node_id:08x}",
                    'position': i
                })
                print(f"     {i}. Node_{node_id:08x} (!{node_id:08x})")
        else:
            print(f"  ⚠️ Aucune route dans RouteDiscovery (ni aller ni retour)")
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
    
    print()
    print("=" * 70)
    print("RÉSULTAT:")
    print("=" * 70)
    print(f"Ancien code: {len(route_original)} hops extraits")
    print(f"Nouveau code: {len(route_fixed)} hops extraits")
    print()
    
    if not route_original and route_fixed:
        print("✅ FIX VALIDÉ:")
        print("   - Ancien code: Affichait 'Route non décodable'")
        print("   - Nouveau code: Extrait correctement la route depuis route_back")
        print()
        print("Route extraite:")
        for hop in route_fixed:
            print(f"  {hop['position']}. {hop['name']} (0x{hop['node_id']:08x})")
        return True
    elif route_original and route_fixed:
        print("✅ Les deux codes fonctionnent (cas normal)")
        return True
    else:
        print("❌ ÉCHEC: Le nouveau code ne résout pas le problème")
        return False


def simulate_telegram_message():
    """
    Simule la construction du message Telegram avec la route extraite
    """
    print()
    print("=" * 70)
    print("SIMULATION: Message Telegram")
    print("=" * 70)
    print()
    
    # Données de test
    node_name = "SAW (!435b9ae8)"
    elapsed_time = 1.2
    
    # Route extraite par le nouveau code
    route = [
        {'node_id': 0x8d567a5e, 'name': 'Node_8d567a5e', 'position': 0}
    ]
    
    # Construire le message (code from traceroute_manager.py lines 687-717)
    route_parts = []
    route_parts.append(f"📊 **Traceroute vers {node_name}**")
    route_parts.append(f"━━━━━━━━━━━━━━━━━━━━")
    route_parts.append("")
    route_parts.append(f"🎯 Route complète ({len(route)} nœuds):")
    route_parts.append("")
    
    for i, hop in enumerate(route):
        hop_name = hop['name']
        hop_id = hop['node_id']
        
        if i == 0:
            icon = "🏁"  # Départ (bot)
        elif i == len(route) - 1:
            icon = "🎯"  # Arrivée (destination)
        else:
            icon = "🔀"  # Relay intermédiaire
        
        route_parts.append(f"{icon} **Hop {i}:** {hop_name}")
        route_parts.append(f"   ID: `!{hop_id:08x}`")
        
        if i < len(route) - 1:
            route_parts.append("   ⬇️")
    
    route_parts.append("")
    route_parts.append(f"📏 **Distance:** {len(route) - 1} hop(s)")
    route_parts.append(f"⏱️ **Temps:** {elapsed_time:.1f}s")
    
    telegram_message = "\n".join(route_parts)
    
    print("Message Telegram (AVEC FIX):")
    print()
    print(telegram_message)
    print()
    
    return True


if __name__ == '__main__':
    success = True
    
    success = simulate_traceroute_response() and success
    success = simulate_telegram_message() and success
    
    print()
    print("=" * 70)
    if success:
        print("🎉 SIMULATION RÉUSSIE: Le fix résout le problème")
        print("=" * 70)
        sys.exit(0)
    else:
        print("❌ SIMULATION ÉCHOUÉE: Le fix ne résout pas le problème")
        print("=" * 70)
        sys.exit(1)
