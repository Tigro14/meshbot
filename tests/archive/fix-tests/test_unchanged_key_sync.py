#!/usr/bin/env python3
"""
Test that unchanged public keys are still synced to interface.nodes

This tests the fix for the issue where keys stored in node_names.json
are not synced to interface.nodes when a NODEINFO packet arrives with
an unchanged key (common after bot restart).
"""

import sys
import os
import tempfile
from unittest.mock import Mock

def test_unchanged_key_still_synced():
    """Test that unchanged keys are still synced to interface.nodes"""
    print("\n" + "="*70)
    print("TEST: Unchanged Key Still Synced to interface.nodes")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    # Import after mocking config
    from node_manager import NodeManager
    
    # Create mock interface with empty nodes dict
    mock_interface = Mock()
    mock_interface.nodes = {}
    
    # Create node manager with interface
    nm = NodeManager(interface=mock_interface)
    
    # Pre-populate node_names with a node that already has a key
    # (simulates bot restart where JSON file has keys but interface.nodes is empty)
    nm.node_names[0x16ced5f8] = {
        'name': 'guilhembarpilotio - 🏢📡',
        'shortName': '🚢',
        'hwModel': 'STATION_G2',
        'publicKey': '/egCGEvYW20g2sW+wzTW+mnD2kOl+bLhADAb2rCYU30='
    }
    
    print("1. Initial state (simulating bot restart):")
    print(f"   node_names has key: YES")
    print(f"   interface.nodes has key: NO (empty after restart)")
    
    # Verify initial state
    assert nm.node_names[0x16ced5f8].get('publicKey'), "Node should have key in node_names"
    assert len(mock_interface.nodes) == 0, "interface.nodes should be empty"
    
    # Now simulate receiving NODEINFO with SAME key (unchanged)
    packet = {
        'from': 0x16ced5f8,
        'decoded': {
            'portnum': 'NODEINFO_APP',
            'user': {
                'longName': 'guilhembarpilotio - 🏢📡',
                'shortName': '🚢',
                'hwModel': 'STATION_G2',
                'publicKey': '/egCGEvYW20g2sW+wzTW+mnD2kOl+bLhADAb2rCYU30='  # SAME key
            }
        }
    }
    
    print("\n2. Processing NODEINFO with UNCHANGED key...")
    nm.update_node_from_packet(packet)
    
    print("\n3. After NODEINFO processing:")
    print(f"   node_names has key: YES")
    print(f"   interface.nodes has {len(mock_interface.nodes)} nodes")
    
    # CRITICAL TEST: Even though key is unchanged, it should be synced to interface.nodes
    assert len(mock_interface.nodes) > 0, "interface.nodes should NOT be empty after NODEINFO"
    
    # Find the node in interface.nodes
    node_found = False
    key_found = False
    
    for key, node_info in mock_interface.nodes.items():
        if isinstance(node_info, dict):
            user_info = node_info.get('user', {})
            if isinstance(user_info, dict):
                if 'guilhem' in user_info.get('longName', ''):
                    node_found = True
                    if user_info.get('publicKey') or user_info.get('public_key'):
                        key_found = True
                        print(f"   ✅ Key synced to interface.nodes (despite being unchanged)")
                        break
    
    assert node_found, "Node should be in interface.nodes"
    assert key_found, "Node should have public key in interface.nodes"
    
    print("\n4. Testing /keys command simulation:")
    # Simulate what /keys command does - check interface.nodes
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
    print(f"   ✅ /keys correctly shows key (not '153 sans clés')")
    
    # Cleanup
    try:
        os.unlink(MockConfig.NODE_NAMES_FILE)
    except:
        pass
    
    print("\n" + "="*70)
    print("✅ TEST PASSED: Unchanged keys ARE synced to interface.nodes")
    print("="*70)


def test_bot_restart_scenario():
    """
    Test the exact scenario from the bug report:
    1. Bot has keys in node_names.json (from previous run)
    2. Bot restarts, interface.nodes is empty
    3. NODEINFO arrives with unchanged key
    4. Key should be synced to interface.nodes
    5. /keys should show keys, not "153 sans clés"
    """
    print("\n" + "="*70)
    print("TEST: Bot Restart Scenario (Bug #3694064324)")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    from node_manager import NodeManager
    
    # Create node manager
    nm = NodeManager()
    
    # Simulate: Bot already has 153 nodes with keys in node_names.json
    for i in range(153):
        node_id = 0x10000000 + i
        nm.node_names[node_id] = {
            'name': f'Node-{i}',
            'publicKey': f'key_{i}_base64=='
        }
    
    print(f"1. After bot restart simulation:")
    print(f"   node_names.json has {len(nm.node_names)} nodes with keys")
    
    # Now attach interface (simulating bot startup)
    mock_interface = Mock()
    mock_interface.nodes = {}
    nm.interface = mock_interface
    
    print(f"   interface.nodes has {len(mock_interface.nodes)} nodes (empty after restart)")
    
    # Simulate 10 NODEINFO packets arriving with unchanged keys
    print(f"\n2. Simulating 10 NODEINFO packets with unchanged keys...")
    for i in range(10):
        node_id = 0x10000000 + i
        packet = {
            'from': node_id,
            'decoded': {
                'portnum': 'NODEINFO_APP',
                'user': {
                    'longName': f'Node-{i}',
                    'publicKey': f'key_{i}_base64=='  # UNCHANGED key
                }
            }
        }
        nm.update_node_from_packet(packet)
    
    print(f"\n3. After processing 10 NODEINFO packets:")
    print(f"   interface.nodes now has {len(mock_interface.nodes)} nodes")
    
    # Count keys in interface.nodes
    keys_in_interface = 0
    for node_info in mock_interface.nodes.values():
        if isinstance(node_info, dict):
            user_info = node_info.get('user', {})
            if isinstance(user_info, dict):
                if user_info.get('publicKey') or user_info.get('public_key'):
                    keys_in_interface += 1
    
    print(f"   Keys in interface.nodes: {keys_in_interface}")
    
    assert keys_in_interface == 10, f"Should have 10 keys in interface.nodes, got {keys_in_interface}"
    print(f"   ✅ All 10 unchanged keys were synced to interface.nodes")
    
    print(f"\n4. /keys command would show:")
    print(f"   ✅ {keys_in_interface} nodes with keys")
    print(f"   ❌ NOT '153 sans clés' (the bug is fixed)")
    
    # Cleanup
    try:
        os.unlink(MockConfig.NODE_NAMES_FILE)
    except:
        pass
    
    print("\n" + "="*70)
    print("✅ TEST PASSED: Bot restart scenario works correctly")
    print("="*70)


if __name__ == '__main__':
    print("\n" + "="*70)
    print("UNCHANGED KEY SYNC TEST SUITE")
    print("Testing fix for bug #3694064324: '153 sans clés' after bot restart")
    print("="*70)
    
    try:
        test_unchanged_key_still_synced()
        test_bot_restart_scenario()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nFix Summary:")
        print("• NODEINFO with unchanged key → still sync to interface.nodes")
        print("• After bot restart → keys in JSON get synced on first NODEINFO")
        print("• /keys command → shows keys correctly (not '153 sans clés')")
        print("• Critical for: Bot restarts, TCP mode, long-running bots")
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
