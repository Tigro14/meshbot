#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du fix pour le parsing de traceroute
Vérifie que route_back est utilisé quand route est vide
"""

from meshtastic import mesh_pb2


def test_parse_route_back():
    """
    Tester le parsing avec le payload réel du log:
    1201121a045e7a568d22022a05
    
    Résultat attendu:
    - route: []
    - snr_towards: [18]
    - route_back: [0x8d567a5e]
    - snr_back: [42, 5]
    """
    # Payload from logs
    payload_hex = "1201121a045e7a568d22022a05"
    payload = bytes.fromhex(payload_hex)
    
    print("=" * 60)
    print("TEST: Parse traceroute avec route_back")
    print("=" * 60)
    print(f"Payload hex: {payload_hex}")
    print(f"Payload bytes: {payload}")
    print(f"Payload length: {len(payload)}")
    print()
    
    # Parse as RouteDiscovery
    route_discovery = mesh_pb2.RouteDiscovery()
    route_discovery.ParseFromString(payload)
    
    print("Parsed fields:")
    print(f"  route (forward): {list(route_discovery.route)}")
    print(f"  snr_towards: {list(route_discovery.snr_towards)}")
    print(f"  route_back: {[hex(n) for n in route_discovery.route_back]}")
    print(f"  snr_back: {list(route_discovery.snr_back)}")
    print()
    
    # Simulate the fix logic
    route = []
    
    if route_discovery.route:
        print("✅ Using route (forward)")
        for i, node_id in enumerate(route_discovery.route):
            route.append({
                'node_id': node_id,
                'name': f"Node_{node_id:08x}",
                'position': i
            })
    elif route_discovery.route_back:
        print("✅ Using route_back (forward empty)")
        for i, node_id in enumerate(route_discovery.route_back):
            route.append({
                'node_id': node_id,
                'name': f"Node_{node_id:08x}",
                'position': i
            })
    else:
        print("❌ No route available (neither forward nor back)")
    
    print()
    print("Extracted route:")
    for hop in route:
        print(f"  {hop['position']}. {hop['name']} (0x{hop['node_id']:08x})")
    
    # Verify
    assert len(route) == 1, f"Expected 1 hop, got {len(route)}"
    assert route[0]['node_id'] == 0x8d567a5e, f"Expected 0x8d567a5e, got 0x{route[0]['node_id']:08x}"
    
    print()
    print("=" * 60)
    print("✅ TEST PASSED: route_back correctly extracted")
    print("=" * 60)


def test_both_routes():
    """
    Tester un cas où les deux routes sont présentes
    """
    print()
    print("=" * 60)
    print("TEST: Parse traceroute avec route et route_back")
    print("=" * 60)
    
    route_discovery = mesh_pb2.RouteDiscovery()
    
    # Ajouter des nodes dans les deux routes
    route_discovery.route.append(0x12345678)
    route_discovery.route.append(0xabcdef00)
    route_discovery.route_back.append(0xabcdef00)
    route_discovery.route_back.append(0x12345678)
    
    # Serialize
    payload = route_discovery.SerializeToString()
    print(f"Payload hex: {payload.hex()}")
    print(f"Payload length: {len(payload)}")
    print()
    
    # Parse back
    route_discovery2 = mesh_pb2.RouteDiscovery()
    route_discovery2.ParseFromString(payload)
    
    print("Parsed fields:")
    print(f"  route (forward): {[hex(n) for n in route_discovery2.route]}")
    print(f"  route_back: {[hex(n) for n in route_discovery2.route_back]}")
    print()
    
    # Simulate the fix logic (should use route, not route_back)
    route = []
    
    if route_discovery2.route:
        print("✅ Using route (forward) - preferred")
        for i, node_id in enumerate(route_discovery2.route):
            route.append({
                'node_id': node_id,
                'name': f"Node_{node_id:08x}",
                'position': i
            })
    elif route_discovery2.route_back:
        print("✅ Using route_back (forward empty)")
        for i, node_id in enumerate(route_discovery2.route_back):
            route.append({
                'node_id': node_id,
                'name': f"Node_{node_id:08x}",
                'position': i
            })
    
    print()
    print("Extracted route:")
    for hop in route:
        print(f"  {hop['position']}. {hop['name']} (0x{hop['node_id']:08x})")
    
    # Verify - should use forward route (route field), not route_back
    assert len(route) == 2, f"Expected 2 hops, got {len(route)}"
    assert route[0]['node_id'] == 0x12345678
    assert route[1]['node_id'] == 0xabcdef00
    
    print()
    print("=" * 60)
    print("✅ TEST PASSED: route (forward) preferred over route_back")
    print("=" * 60)


if __name__ == '__main__':
    test_parse_route_back()
    test_both_routes()
    print()
    print("=" * 60)
    print("🎉 ALL TESTS PASSED")
    print("=" * 60)
