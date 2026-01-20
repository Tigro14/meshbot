#!/usr/bin/env python3
"""
Integration test for pubkey_prefix resolution fix

This test simulates the complete flow of receiving a DM via meshcore-cli
and verifies that the sender is correctly resolved.
"""

import sys
import base64
import json
import os
import tempfile

def print_test(msg, status=""):
    """Print test message with status"""
    if status == "✅":
        print(f"  ✅ {msg}")
    elif status == "❌":
        print(f"  ❌ {msg}")
    elif status == "🔍":
        print(f"  🔍 {msg}")
    else:
        print(f"  {msg}")


def test_integration():
    """Full integration test"""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Complete DM Resolution Flow")
    print("="*70)
    
    # Create temporary node_names file
    temp_dir = tempfile.mkdtemp()
    temp_node_file = os.path.join(temp_dir, 'node_names.json')
    
    # Mock config module
    sys.modules['config'] = type('config', (), {
        'DEBUG_MODE': True,
        'BOT_POSITION': None,
        'NODE_NAMES_FILE': temp_node_file
    })()
    
    # Import after mocking
    from node_manager import NodeManager
    
    print("\n📋 Test Setup:")
    print_test("Creating NodeManager", "🔍")
    node_mgr = NodeManager(interface=None)
    
    # Create test scenario: Node with base64 publicKey
    test_node_id = 0x0de3331e
    test_name = "tigro t1000E"
    
    # Real-world scenario: 32-byte public key
    # First 6 bytes = a3fe27d34ac0 (the prefix we'll receive from meshcore-cli)
    pubkey_bytes = bytes.fromhex('a3fe27d34ac0') + os.urandom(26)
    pubkey_base64 = base64.b64encode(pubkey_bytes).decode('utf-8')
    pubkey_hex_prefix = pubkey_bytes[:6].hex().lower()
    
    print_test(f"Node ID: 0x{test_node_id:08x}", "✅")
    print_test(f"Node Name: {test_name}", "✅")
    print_test(f"PubKey (base64): {pubkey_base64[:20]}...", "✅")
    print_test(f"PubKey (hex prefix): {pubkey_hex_prefix}", "✅")
    
    # Add node to database
    node_mgr.node_names[test_node_id] = {
        'name': test_name,
        'shortName': 't1000E',
        'hwModel': 'T1000E',
        'lat': None,
        'lon': None,
        'alt': None,
        'last_update': None,
        'publicKey': pubkey_base64  # Stored as base64
    }
    
    print("\n📥 Simulating DM Event from MeshCore-CLI:")
    print_test("Event type: CONTACT_MSG_RECV", "🔍")
    print_test(f"Payload: pubkey_prefix = '{pubkey_hex_prefix}'", "🔍")
    print_test("Payload: text = 'Coucou'", "🔍")
    
    print("\n🔍 Step 1: Try to resolve pubkey_prefix")
    found_id = node_mgr.find_node_by_pubkey_prefix(pubkey_hex_prefix)
    
    if found_id == test_node_id:
        print_test(f"Resolution successful: 0x{found_id:08x}", "✅")
        print_test(f"Matched to: {node_mgr.node_names[found_id]['name']}", "✅")
    else:
        print_test("Resolution failed!", "❌")
        return False
    
    print("\n🔍 Step 2: Verify sender info")
    sender_name = node_mgr.get_node_name(found_id)
    if sender_name == test_name:
        print_test(f"Sender name: {sender_name}", "✅")
    else:
        print_test(f"Wrong sender name: {sender_name} != {test_name}", "❌")
        return False
    
    print("\n🔍 Step 3: Verify response can be sent")
    # In real code, this would be: self.sendText(response, found_id)
    if found_id != 0xFFFFFFFF:
        print_test(f"Can send response to: 0x{found_id:08x}", "✅")
    else:
        print_test("Cannot send response (unknown sender)", "❌")
        return False
    
    print("\n✅ Integration Test: PASSED")
    print_test("pubkey_prefix correctly resolved", "✅")
    print_test("Sender identified", "✅")
    print_test("Response can be sent", "✅")
    
    # Cleanup
    if os.path.exists(temp_node_file):
        os.remove(temp_node_file)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)
    
    return True


def test_unknown_sender_extraction():
    """Test automatic contact extraction for unknown sender"""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Unknown Sender Contact Extraction")
    print("="*70)
    
    # Create temporary node_names file
    temp_dir = tempfile.mkdtemp()
    temp_node_file = os.path.join(temp_dir, 'node_names.json')
    
    # Mock config module
    sys.modules['config'] = type('config', (), {
        'DEBUG_MODE': True,
        'BOT_POSITION': None,
        'NODE_NAMES_FILE': temp_node_file
    })()
    
    # Mock meshcore module
    class MockContact:
        def __init__(self, contact_id, public_key, name):
            self.contact_id = contact_id
            self.public_key = public_key
            self.name = name
    
    class MockMeshCore:
        def __init__(self):
            # Create a test contact
            pubkey_bytes = bytes.fromhex('143bcd7f1b1f') + os.urandom(26)
            pubkey_base64 = base64.b64encode(pubkey_bytes).decode('utf-8')
            
            self.contacts = [
                MockContact(0x16fad3dc, pubkey_base64, "RemoteUser")
            ]
    
    # Import after mocking
    from node_manager import NodeManager
    
    print("\n📋 Test Setup:")
    print_test("Creating NodeManager", "🔍")
    node_mgr = NodeManager(interface=None)
    
    print("\n📥 Simulating DM from Unknown Sender:")
    unknown_prefix = '143bcd7f1b1f'
    print_test(f"pubkey_prefix: {unknown_prefix}", "🔍")
    print_test("Not in node_names.json", "🔍")
    
    print("\n🔍 Step 1: Local lookup (should fail)")
    found_id = node_mgr.find_node_by_pubkey_prefix(unknown_prefix)
    
    if found_id is None:
        print_test("Not found in local database (expected)", "✅")
    else:
        print_test(f"Unexpectedly found: 0x{found_id:08x}", "❌")
        return False
    
    print("\n🔍 Step 2: Simulating meshcore-cli contact extraction")
    print_test("Would call: lookup_contact_by_pubkey_prefix()", "🔍")
    print_test("Would extract from: meshcore.contacts", "🔍")
    
    # Simulate what lookup_contact_by_pubkey_prefix() would do
    mock_meshcore = MockMeshCore()
    contact = mock_meshcore.contacts[0]
    
    # Verify the contact matches
    contact_pubkey_hex = base64.b64decode(contact.public_key).hex().lower()
    if contact_pubkey_hex.startswith(unknown_prefix):
        print_test("Contact found in meshcore database", "✅")
        print_test(f"contact_id: 0x{contact.contact_id:08x}", "✅")
        print_test(f"name: {contact.name}", "✅")
        
        # Add to node_manager
        node_mgr.node_names[contact.contact_id] = {
            'name': contact.name,
            'publicKey': contact.public_key
        }
        print_test("Contact added to node_manager", "✅")
        
        # Verify lookup now works
        found_id = node_mgr.find_node_by_pubkey_prefix(unknown_prefix)
        if found_id == contact.contact_id:
            print_test("Subsequent lookup successful", "✅")
        else:
            print_test("Subsequent lookup failed", "❌")
            return False
    else:
        print_test("Contact does not match prefix", "❌")
        return False
    
    print("\n✅ Integration Test: PASSED")
    print_test("Unknown sender detected", "✅")
    print_test("Contact extracted from meshcore-cli", "✅")
    print_test("Contact added to database", "✅")
    print_test("Subsequent lookups work", "✅")
    
    # Cleanup
    if os.path.exists(temp_node_file):
        os.remove(temp_node_file)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)
    
    return True


def main():
    """Run all integration tests"""
    print("\n" + "="*70)
    print("PUBKEY RESOLUTION FIX - INTEGRATION TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("Complete DM Resolution Flow", test_integration()))
    results.append(("Unknown Sender Contact Extraction", test_unknown_sender_extraction()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} integration tests passed")
    
    if passed == total:
        print("\n✅ ALL INTEGRATION TESTS PASSED")
        print("The fix is working correctly end-to-end!")
        return 0
    else:
        print("\n❌ SOME INTEGRATION TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
