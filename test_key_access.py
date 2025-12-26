#!/usr/bin/env python3
"""
Test both field name variants
"""

# Simulated packet structure (what we might actually receive)
packet_snake_case = {
    'from': 0x12345678,
    'decoded': {
        'portnum': 'NODEINFO_APP',
        'user': {
            'id': '!12345678',
            'longName': 'TestNode',
            'shortName': 'TEST',
            'hwModel': 'T1000E',
            'public_key': b'\x01\x02\x03\x04'  # underscore (protobuf style)
        }
    }
}

packet_camel_case = {
    'from': 0x12345678,
    'decoded': {
        'portnum': 'NODEINFO_APP',
        'user': {
            'id': '!12345678',
            'longName': 'TestNode',
            'shortName': 'TEST',
            'hwModel': 'T1000E',
            'publicKey': b'\x01\x02\x03\x04'  # camelCase (Python dict style)
        }
    }
}

print("Testing field access:")
print(f"  packet with 'public_key': {packet_snake_case['decoded']['user'].get('public_key')}")
print(f"  packet with 'public_key' using 'publicKey': {packet_snake_case['decoded']['user'].get('publicKey')}")
print(f"  packet with 'publicKey': {packet_camel_case['decoded']['user'].get('publicKey')}")
print(f"  packet with 'publicKey' using 'public_key': {packet_camel_case['decoded']['user'].get('public_key')}")

print("\n⚠️ We need to try BOTH field names!")
