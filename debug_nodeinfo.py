#!/usr/bin/env python3
"""
Debug script to check how NODEINFO packets are structured
"""

# Example of what interface.nodes looks like based on Meshtastic docs
example_interface_nodes = {
    305419896: {
        'num': 305419896,
        'user': {
            'id': '!12345678',
            'longName': 'TestNode',
            'shortName': 'TEST',
            'macaddr': 'AABBCCDD',
            'hwModel': 'TBEAM',
            'role': 'CLIENT',
            'public_key': b'\x01\x02\x03...'  # Note: underscore, not camelCase!
        },
        'position': {
            'latitude': 47.123,
            'longitude': 6.456
        },
        'snr': 12.5,
        'lastHeard': 1234567890
    }
}

print("Checking interface.nodes structure...")
print("\nExpected 'user' dict keys:")
for key in example_interface_nodes[305419896]['user'].keys():
    print(f"  - {key}")

print("\n⚠️ IMPORTANT: The field is 'public_key' (underscore), not 'publicKey' (camelCase)!")
print("\nWhen packet is decoded, it has 'user' dict with:")
print("  - id, longName, shortName, macaddr, hwModel, role")
print("  - public_key (bytes)")
