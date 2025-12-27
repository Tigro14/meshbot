#!/usr/bin/env python3
"""
Debug script to check what fields are actually present in NODEINFO packets
"""

print("="*70)
print("NODEINFO Packet Field Investigation")
print("="*70)

# According to Meshtastic mesh.proto:
print("\n1. Protobuf Definition (mesh.proto):")
print("   message User {")
print("     string id = 1;")
print("     string long_name = 2;")
print("     string short_name = 3;")
print("     bytes macaddr = 4;")
print("     HardwareModel hw_model = 5;")
print("     Role role = 6;")
print("     bytes public_key = 7;  // ← PKI public key")
print("   }")

print("\n2. When Does public_key Get Populated?")
print("   • Only in Meshtastic firmware 2.5.0+")
print("   • Only if PKI is enabled (default in 2.5.0+)")
print("   • Only if node has generated/received its key pair")
print("   • Key exchange happens automatically between nodes")

print("\n3. Checking Current Firmware Versions:")
print("   ⚠️ CRITICAL: Nodes must be running firmware 2.5.0+ for PKI!")
print("   • Firmware < 2.5.0: No public_key field in NODEINFO")
print("   • Firmware 2.5.0+: public_key field present and populated")

print("\n4. How to Verify Firmware Version:")
print("   a) Via meshtastic CLI:")
print("      meshtastic --host <ip> --info | grep firmware")
print("   b) Check interface.nodes:")
print("      interface.nodes[node_id]['user']['hwModel']")
print("      interface.nodes[node_id]['deviceMetrics']['firmwareVersion']")

print("\n5. Possible Causes of Missing Keys:")
print("   ❌ Nodes running firmware < 2.5.0 (no PKI support)")
print("   ❌ PKI not enabled in node settings")
print("   ❌ Key exchange not completed yet")
print("   ❌ NODEINFO packets not including public_key field")

print("\n6. Verification Steps:")
print("   1. Check bot's own node firmware version")
print("   2. Check a few sample nodes' firmware versions")
print("   3. Inspect actual NODEINFO packet structure")
print("   4. Add logging to see if public_key field exists (even if empty)")

print("\n7. Recommended Next Step:")
print("   Add debug logging to node_manager.py to inspect actual packet:")
print("   ")
print("   def update_node_from_packet(self, packet):")
print("       if 'decoded' in packet and packet['decoded'].get('portnum') == 'NODEINFO_APP':")
print("           user_info = packet['decoded']['user']")
print("           debug_print(f'🔍 NODEINFO user_info keys: {list(user_info.keys())}')")
print("           debug_print(f'🔍 Has public_key: {\"public_key\" in user_info}')")
print("           debug_print(f'🔍 Has publicKey: {\"publicKey\" in user_info}')")

print("\n" + "="*70)
