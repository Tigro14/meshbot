#!/usr/bin/env python3
"""
Diagnostic script to understand why /keys reports "sans clés" when keys exist

This helps debug the mismatch between:
1. Keys present in interface.nodes (shown in sync logs)
2. /keys reporting nodes as "without keys"
"""

import sys

# Mock the scenario from the logs
print("="*70)
print("DIAGNOSTIC: Why does /keys report '155 sans clés'?")
print("="*70)
print()

# Simulate interface.nodes with keys (as shown in logs)
interface_nodes = {
    '!db295204': {  # CHATO PCS1
        'num': 0xdb295204,
        'user': {
            'id': '!db295204',
            'longName': 'CHATO PCS1',
            'publicKey': 'key123=='  # Has key
        }
    },
    '!a0cb18b4': {  # 😼Kat Mobile
        'num': 0xa0cb18b4,
        'user': {
            'id': '!a0cb18b4',
            'longName': '😼Kat Mobile',
            'publicKey': 'key456=='  # Has key
        }
    }
}

# Simulate nodes seen in traffic (last 48h)
# These are the node IDs that /keys command gets from traffic_monitor
nodes_in_traffic = {
    0xdb295204,  # CHATO PCS1
    0xa0cb18b4,  # 😼Kat Mobile
    0x12345678,  # Some other node NOT in interface.nodes
}

print("1. interface.nodes (keys present):")
for key, info in interface_nodes.items():
    user = info.get('user', {})
    has_key = 'publicKey' in user or 'public_key' in user
    print(f"   {key}: {user.get('longName')} - Has key: {has_key}")

print()
print("2. Nodes seen in traffic (last 48h):")
for node_id in nodes_in_traffic:
    print(f"   0x{node_id:08x}")

print()
print("3. /keys command logic simulation:")
print()

nodes_with_keys_count = 0
nodes_without_keys = []

for node_id in nodes_in_traffic:
    node_id_int = node_id
    
    # Try to find node in interface.nodes with multiple key formats
    # This is what /keys command does (line 1357)
    node_info = None
    possible_keys = [
        node_id_int,           # As integer
        str(node_id_int),      # As string
        f"!{node_id_int:08x}", # As !hex
        f"{node_id_int:08x}"   # As hex
    ]
    
    print(f"   Node 0x{node_id_int:08x}:")
    print(f"      Trying keys: {possible_keys}")
    
    for key in possible_keys:
        if key in interface_nodes:
            node_info = interface_nodes[key]
            print(f"      ✓ Found with key format: {key}")
            break
    else:
        print(f"      ✗ NOT FOUND in interface.nodes")
    
    if node_info and isinstance(node_info, dict):
        user_info = node_info.get('user', {})
        if isinstance(user_info, dict):
            public_key = user_info.get('public_key') or user_info.get('publicKey')
            
            if public_key:
                nodes_with_keys_count += 1
                print(f"      ✓ Has public key")
            else:
                nodes_without_keys.append((node_id_int, "Unknown"))
                print(f"      ✗ NO public key in user_info")
        else:
            nodes_without_keys.append((node_id_int, "Unknown"))
            print(f"      ✗ user_info malformed")
    else:
        nodes_without_keys.append((node_id_int, "Unknown"))
        print(f"      ✗ Counted as 'without key' (not in interface.nodes)")
    
    print()

total_seen = len(nodes_in_traffic)

print("="*70)
print("RESULT:")
print(f"  Total nodes in traffic: {total_seen}")
print(f"  Nodes WITH keys: {nodes_with_keys_count}")
print(f"  Nodes WITHOUT keys: {len(nodes_without_keys)}")
print()

if nodes_without_keys:
    print("  Nodes without keys:")
    for node_id, name in nodes_without_keys:
        print(f"    • 0x{node_id:08x}")
    print()
    print("  Why do we have nodes without keys?")
    print("  → They are in traffic (sent packets)")
    print("  → But NOT in interface.nodes")
    print("  → Could be:")
    print("     - Never sent NODEINFO (so not in SQLite DB)")
    print("     - NODEINFO not processed yet")
    print("     - Node ID format mismatch")

print("="*70)
