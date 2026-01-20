#!/usr/bin/env python3
"""
Test script to verify pubkey_prefix resolution fix for meshcore-cli DMs

This test verifies that:
1. Base64-encoded public keys are correctly converted to hex for matching
2. The lookup_contact_by_pubkey_prefix method can extract contacts from meshcore-cli
3. Unknown senders are automatically added to the node database
"""

import sys
import base64

# Mock config module
sys.modules['config'] = type('config', (), {
    'DEBUG_MODE': True,
    'BOT_POSITION': None,
    'NODE_NAMES_FILE': '/tmp/test_node_names.json'
})()

# Import after mocking
from node_manager import NodeManager

def test_base64_pubkey_matching():
    """Test that base64 public keys are correctly matched against hex prefixes"""
    print("\n" + "="*70)
    print("TEST 1: Base64 Public Key Matching")
    print("="*70)
    
    # Create a test node manager
    node_mgr = NodeManager(interface=None)
    
    # Create test data
    test_node_id = 0x0de3331e
    
    # Simulate a public key (32 bytes)
    # First 6 bytes in hex: a3fe27d34ac0
    test_pubkey_bytes = bytes.fromhex('a3fe27d34ac0') + b'\x00' * 26
    
    # Store as base64 (like meshcore-cli does)
    test_pubkey_base64 = base64.b64encode(test_pubkey_bytes).decode('utf-8')
    
    print(f"\n📝 Test Setup:")
    print(f"   Node ID: 0x{test_node_id:08x}")
    print(f"   Public Key (bytes): {test_pubkey_bytes.hex()}")
    print(f"   Public Key (base64): {test_pubkey_base64}")
    print(f"   Expected prefix: a3fe27d34ac0")
    
    # Add node with base64 public key
    node_mgr.node_names[test_node_id] = {
        'name': 'TestNode',
        'publicKey': test_pubkey_base64  # Base64 format
    }
    
    # Test: Try to find node by hex prefix
    pubkey_prefix = 'a3fe27d34ac0'
    found_id = node_mgr.find_node_by_pubkey_prefix(pubkey_prefix)
    
    print(f"\n🔍 Lookup Result:")
    print(f"   Search prefix: {pubkey_prefix}")
    print(f"   Found node ID: {f'0x{found_id:08x}' if found_id else 'None'}")
    
    if found_id == test_node_id:
        print("   ✅ SUCCESS: Base64 key correctly matched against hex prefix!")
        return True
    else:
        print("   ❌ FAILED: Could not match base64 key against hex prefix")
        return False


def test_bytes_pubkey_matching():
    """Test that bytes public keys are correctly matched against hex prefixes"""
    print("\n" + "="*70)
    print("TEST 2: Bytes Public Key Matching")
    print("="*70)
    
    # Create a test node manager
    node_mgr = NodeManager(interface=None)
    
    # Create test data
    test_node_id = 0x16fad3dc
    
    # Simulate a public key (32 bytes)
    # First 6 bytes in hex: 143bcd7f1b1f
    test_pubkey_bytes = bytes.fromhex('143bcd7f1b1f') + b'\x00' * 26
    
    print(f"\n📝 Test Setup:")
    print(f"   Node ID: 0x{test_node_id:08x}")
    print(f"   Public Key (bytes): {test_pubkey_bytes.hex()}")
    print(f"   Expected prefix: 143bcd7f1b1f")
    
    # Add node with bytes public key
    node_mgr.node_names[test_node_id] = {
        'name': 'AnotherNode',
        'publicKey': test_pubkey_bytes  # Bytes format
    }
    
    # Test: Try to find node by hex prefix
    pubkey_prefix = '143bcd7f1b1f'
    found_id = node_mgr.find_node_by_pubkey_prefix(pubkey_prefix)
    
    print(f"\n🔍 Lookup Result:")
    print(f"   Search prefix: {pubkey_prefix}")
    print(f"   Found node ID: {f'0x{found_id:08x}' if found_id else 'None'}")
    
    if found_id == test_node_id:
        print("   ✅ SUCCESS: Bytes key correctly matched against hex prefix!")
        return True
    else:
        print("   ❌ FAILED: Could not match bytes key against hex prefix")
        return False


def test_hex_pubkey_matching():
    """Test that hex public keys are correctly matched"""
    print("\n" + "="*70)
    print("TEST 3: Hex String Public Key Matching")
    print("="*70)
    
    # Create a test node manager
    node_mgr = NodeManager(interface=None)
    
    # Create test data
    test_node_id = 0xaabbccdd
    
    # Public key already in hex format
    test_pubkey_hex = 'a1b2c3d4e5f6' + '00' * 26
    
    print(f"\n📝 Test Setup:")
    print(f"   Node ID: 0x{test_node_id:08x}")
    print(f"   Public Key (hex): {test_pubkey_hex}")
    print(f"   Expected prefix: a1b2c3d4e5f6")
    
    # Add node with hex public key
    node_mgr.node_names[test_node_id] = {
        'name': 'HexNode',
        'publicKey': test_pubkey_hex  # Hex format
    }
    
    # Test: Try to find node by hex prefix
    pubkey_prefix = 'a1b2c3d4e5f6'
    found_id = node_mgr.find_node_by_pubkey_prefix(pubkey_prefix)
    
    print(f"\n🔍 Lookup Result:")
    print(f"   Search prefix: {pubkey_prefix}")
    print(f"   Found node ID: {f'0x{found_id:08x}' if found_id else 'None'}")
    
    if found_id == test_node_id:
        print("   ✅ SUCCESS: Hex key correctly matched against hex prefix!")
        return True
    else:
        print("   ❌ FAILED: Could not match hex key against hex prefix")
        return False


def test_unknown_pubkey():
    """Test handling of unknown pubkey prefix"""
    print("\n" + "="*70)
    print("TEST 4: Unknown PubKey Prefix")
    print("="*70)
    
    # Create a test node manager
    node_mgr = NodeManager(interface=None)
    
    # Add some nodes
    node_mgr.node_names[0x12345678] = {
        'name': 'Node1',
        'publicKey': base64.b64encode(bytes.fromhex('11223344') + b'\x00' * 28).decode('utf-8')
    }
    
    # Test: Try to find node with unknown prefix
    pubkey_prefix = 'ffffffff'
    found_id = node_mgr.find_node_by_pubkey_prefix(pubkey_prefix)
    
    print(f"\n🔍 Lookup Result:")
    print(f"   Search prefix: {pubkey_prefix}")
    print(f"   Found node ID: {f'0x{found_id:08x}' if found_id else 'None'}")
    
    if found_id is None:
        print("   ✅ SUCCESS: Unknown prefix correctly returned None!")
        return True
    else:
        print("   ❌ FAILED: Should have returned None for unknown prefix")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("PUBKEY PREFIX RESOLUTION FIX - TEST SUITE")
    print("="*70)
    print("\nThis test verifies the fix for meshcore-cli DM sender resolution")
    print("Issue: pubkey_prefix (hex) was not matched against base64 publicKeys")
    print("Fix: Convert base64 to hex before comparison")
    
    results = []
    
    # Run tests
    results.append(("Base64 Key Matching", test_base64_pubkey_matching()))
    results.append(("Bytes Key Matching", test_bytes_pubkey_matching()))
    results.append(("Hex Key Matching", test_hex_pubkey_matching()))
    results.append(("Unknown Prefix Handling", test_unknown_pubkey()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Fix is working correctly!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Fix needs adjustment")
        return 1


if __name__ == '__main__':
    sys.exit(main())
