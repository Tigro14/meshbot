#!/usr/bin/env python3
"""
Test immediate public key synchronization to interface.nodes

This tests the fix for the issue where /keys shows 0 keys even though
public keys have been extracted and stored in node_names.json.

The fix: Immediately sync public keys to interface.nodes when extracted
from NODEINFO packets, instead of waiting for periodic sync.
"""

import sys
import os
import json
import tempfile
from unittest.mock import Mock, MagicMock

def test_immediate_sync_on_new_key():
    """Test that new public keys are immediately synced to interface.nodes"""
    print("\n" + "="*70)
    print("TEST: Immediate Sync on New Public Key")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    # Import after mocking config
    from node_manager import NodeManager
    
    # Create mock interface with nodes dict
    mock_interface = Mock()
    mock_interface.nodes = {}
    
    # Create node manager with interface
    nm = NodeManager(interface=mock_interface)
    
    print("1. Initial state:")
    print(f"   interface.nodes: {len(mock_interface.nodes)} nodes")
    print(f"   node_names: {len(nm.node_names)} nodes")
    
    # Simulate receiving NODEINFO packet with public key
    packet = {
        'from': 0x433e38ec,
        'decoded': {
            'portnum': 'NODEINFO_APP',
            'user': {
                'longName': '14FRS3278',
                'shortName': '38ec',
                'hwModel': 'HELTEC_V3',
                'publicKey': '899sCFPiZ4jW4fcz92UJbhwCYEnQK8Z2/tARhgV/ohY='
            }
        }
    }
    
    print("\n2. Processing NODEINFO packet with publicKey...")
    nm.update_node_from_packet(packet)
    
    print("\n3. After NODEINFO processing:")
    print(f"   node_names: {len(nm.node_names)} nodes")
    print(f"   interface.nodes: {len(mock_interface.nodes)} nodes")
    
    # Verify key is in node_names
    assert 0x433e38ec in nm.node_names, "Node should be in node_names"
    assert nm.node_names[0x433e38ec].get('publicKey'), "Node should have publicKey"
    print(f"   ✅ Key stored in node_names")
    
    # Verify key is IMMEDIATELY in interface.nodes (this is the fix!)
    assert len(mock_interface.nodes) > 0, "interface.nodes should NOT be empty"
    
    # Find the node in interface.nodes (could be stored with different key format)
    node_found = False
    key_found = False
    
    for key, node_info in mock_interface.nodes.items():
        if isinstance(node_info, dict):
            user_info = node_info.get('user', {})
            if isinstance(user_info, dict):
                if user_info.get('longName') == '14FRS3278':
                    node_found = True
                    if user_info.get('publicKey') or user_info.get('public_key'):
                        key_found = True
                        print(f"   ✅ Key IMMEDIATELY synced to interface.nodes")
                        print(f"      Node key format: {key}")
                        print(f"      Has publicKey: {'publicKey' in user_info}")
                        print(f"      Has public_key: {'public_key' in user_info}")
                        break
    
    assert node_found, "Node should be in interface.nodes"
    assert key_found, "Node should have public key in interface.nodes"
    
    print("\n4. Testing /keys command simulation:")
    # Simulate what /keys command does
    keys_count = 0
    for node_info in mock_interface.nodes.values():
        if isinstance(node_info, dict):
            user_info = node_info.get('user', {})
            if isinstance(user_info, dict):
                public_key = user_info.get('public_key') or user_info.get('publicKey')
                if public_key:
                    keys_count += 1
    
    print(f"   /keys would show: {keys_count} node keys")
    assert keys_count > 0, "/keys should show at least 1 key"
    print(f"   ✅ /keys shows keys immediately after NODEINFO")
    
    # Cleanup
    try:
        os.unlink(MockConfig.NODE_NAMES_FILE)
    except:
        pass
    
    print("\n" + "="*70)
    print("✅ TEST PASSED: Public keys are immediately synced to interface.nodes")
    print("="*70)


def test_immediate_sync_on_key_update():
    """Test that updated public keys are immediately synced to interface.nodes"""
    print("\n" + "="*70)
    print("TEST: Immediate Sync on Key Update")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    # Import after mocking config
    from node_manager import NodeManager
    
    # Create mock interface with existing node (but no key)
    mock_interface = Mock()
    mock_interface.nodes = {
        0x433e38ec: {
            'num': 0x433e38ec,
            'user': {
                'id': '!433e38ec',
                'longName': '14FRS3278',
                'shortName': '38ec'
                # No publicKey yet
            }
        }
    }
    
    # Create node manager with interface
    nm = NodeManager(interface=mock_interface)
    
    # Add existing node to node_names (without key)
    nm.node_names[0x433e38ec] = {
        'name': '14FRS3278',
        'shortName': '38ec',
        'hwModel': 'HELTEC_V3'
        # No publicKey yet
    }
    
    print("1. Initial state:")
    print(f"   Node exists in interface.nodes: YES")
    print(f"   Node has publicKey in interface.nodes: NO")
    
    # Verify no key initially
    user_info = mock_interface.nodes[0x433e38ec]['user']
    assert 'publicKey' not in user_info, "Should not have key initially"
    
    # Simulate receiving NODEINFO with NEW public key
    packet = {
        'from': 0x433e38ec,
        'decoded': {
            'portnum': 'NODEINFO_APP',
            'user': {
                'longName': '14FRS3278',
                'shortName': '38ec',
                'hwModel': 'HELTEC_V3',
                'publicKey': '899sCFPiZ4jW4fcz92UJbhwCYEnQK8Z2/tARhgV/ohY='
            }
        }
    }
    
    print("\n2. Processing NODEINFO with NEW publicKey...")
    nm.update_node_from_packet(packet)
    
    print("\n3. After NODEINFO processing:")
    # Verify key is IMMEDIATELY in interface.nodes
    user_info = mock_interface.nodes[0x433e38ec]['user']
    has_key = 'publicKey' in user_info or 'public_key' in user_info
    
    if has_key:
        print(f"   ✅ Key IMMEDIATELY synced to existing node")
        print(f"      Has publicKey: {'publicKey' in user_info}")
        print(f"      Has public_key: {'public_key' in user_info}")
    else:
        print(f"   ❌ Key NOT synced to interface.nodes")
    
    assert has_key, "Existing node should now have public key"
    
    # Cleanup
    try:
        os.unlink(MockConfig.NODE_NAMES_FILE)
    except:
        pass
    
    print("\n" + "="*70)
    print("✅ TEST PASSED: Key updates are immediately synced to interface.nodes")
    print("="*70)


if __name__ == '__main__':
    print("\n" + "="*70)
    print("IMMEDIATE PUBLIC KEY SYNC TEST SUITE")
    print("Testing fix for '/keys shows 0 nodes' issue")
    print("="*70)
    
    try:
        test_immediate_sync_on_new_key()
        test_immediate_sync_on_key_update()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nFix Summary:")
        print("• NODEINFO received → extract publicKey → store in node_names.json")
        print("• NEW: Immediately sync to interface.nodes (no wait for periodic sync)")
        print("• Result: /keys command shows keys immediately after NODEINFO")
        print("• Benefit: DM decryption available immediately")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
