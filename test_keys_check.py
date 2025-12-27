#!/usr/bin/env python3
"""
Test to understand why /keys might return 0 nodes
"""

# Simulate the /keys command logic

# Scenario 1: Node has key in node_names.json but not yet synced to interface.nodes
print("="*70)
print("SCENARIO 1: Key in node_names, not in interface.nodes")
print("="*70)

node_names = {
    0x433e38ec: {
        'name': '14FRS3278',
        'publicKey': '899sCFPiZ4jW4fcz92UJbhwCYEnQK8Z2/tARhgV/ohY='
    }
}

interface_nodes = {}  # Empty (TCP mode before sync)

print(f"node_names has {len(node_names)} nodes")
print(f"interface.nodes has {len(interface_nodes)} nodes")
print(f"Keys in node_names: {sum(1 for n in node_names.values() if n.get('publicKey'))}")
print(f"Keys in interface.nodes: {sum(1 for n in interface_nodes.values() if n.get('user', {}).get('publicKey'))}")
print()

# The /keys command checks interface.nodes, not node_names!
# So if sync hasn't happened yet, it will show 0 keys
print("❌ /keys would show: 0 node keys (checks interface.nodes only)")
print()

# Scenario 2: After sync_pubkeys_to_interface()
print("="*70)
print("SCENARIO 2: After sync_pubkeys_to_interface()")
print("="*70)

# Simulate the sync
for node_id, node_data in node_names.items():
    public_key = node_data.get('publicKey')
    if public_key:
        interface_nodes[node_id] = {
            'num': node_id,
            'user': {
                'id': f"!{node_id:08x}",
                'longName': node_data['name'],
                'publicKey': public_key,  # Dict style
                'public_key': public_key  # Protobuf style
            }
        }
        print(f"✅ Synced {node_data['name']} to interface.nodes")

print()
print(f"interface.nodes now has {len(interface_nodes)} nodes")
print(f"Keys in interface.nodes: {sum(1 for n in interface_nodes.values() if n.get('user', {}).get('publicKey'))}")
print()
print("✅ /keys would now show: 1 node keys")
