#!/usr/bin/env python3
"""
Check the structure of NODEINFO packets from interface.nodes
"""
import sys
sys.path.insert(0, '/home/runner/work/meshbot/meshbot')

# Mock minimal config
class MockConfig:
    NODE_NAMES_FILE = "test_node_names.json"
    MAX_RX_HISTORY = 100
    DEBUG_MODE = True

sys.modules['config'] = MockConfig()

from meshtastic.protobuf import mesh_pb2

# Check User protobuf structure
user = mesh_pb2.User()
print("User protobuf fields:")
for field in user.DESCRIPTOR.fields:
    print(f"  - {field.name}: {field.type}")
    
print("\nLooking for public key field...")
print(f"Has 'public_key': {hasattr(user, 'public_key')}")
print(f"Has 'publicKey': {hasattr(user, 'publicKey')}")

# List all attributes
attrs = [a for a in dir(user) if not a.startswith('_')]
print(f"\nAll attributes: {attrs}")
