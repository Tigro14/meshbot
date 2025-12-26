#!/usr/bin/env python3
"""
Test to determine the correct field name for public key
Based on Meshtastic Python library code inspection
"""

# From Meshtastic protobuf definition (mesh.proto):
# message User {
#   string id = 1;
#   string long_name = 2;
#   string short_name = 3;
#   bytes macaddr = 4;
#   HardwareModel hw_model = 5;
#   Role role = 6;
#   bytes public_key = 7;  // <-- Note: underscore in protobuf
# }

# When protobuf is converted to dict/object in Python, the field names are:
# - Protobuf uses snake_case: public_key
# - But when accessed as dict from interface.nodes, it might be camelCase or snake_case

print("According to Meshtastic mesh.proto:")
print("  - Protobuf field: public_key (bytes)")
print("  - Python dict key: Could be 'public_key' or 'publicKey'")
print()
print("Need to check actual runtime behavior:")
print("  interface.nodes[node_id]['user']['public_key']  (underscore)")
print("  OR")
print("  interface.nodes[node_id]['user']['publicKey']   (camelCase)")
