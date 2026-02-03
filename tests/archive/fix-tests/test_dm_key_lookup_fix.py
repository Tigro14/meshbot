#!/usr/bin/env python3
"""
Test to verify that DM decryption key lookup works with multiple key formats.

This test verifies the fix for the issue where the bot has public keys in the
database (verified by /keys command) but DM decryption still fails with
"❌ Missing public key" error.

The root cause was that interface.nodes can use different key formats:
- Integer: 2812625114
- String: "2812625114"
- Hex with prefix: "!a76f40da"
- Hex without prefix: "a76f40da"

The old code only tried `nodes.get(from_id)` which failed if the key format
didn't match. The fix implements multi-format search logic.
"""

import sys
from unittest.mock import Mock, MagicMock

# Mock config before importing traffic_monitor
sys.modules['config'] = Mock()

from traffic_monitor import TrafficMonitor

def test_find_node_in_interface_multiple_formats():
    """Test that _find_node_in_interface finds nodes with different key formats"""
    
    # Create mock node_manager
    node_manager = Mock()
    monitor = TrafficMonitor(node_manager)
    
    # Node ID we're looking for
    test_node_id = 0xa76f40da  # 2812625114 in decimal
    
    # Mock node info with public key
    mock_node_info = {
        'user': {
            'longName': 'Test Node',
            'publicKey': 'KzIbS2tRqpaFe45u...'  # Sample key
        }
    }
    
    # Test cases: different key formats that interface.nodes might use
    test_cases = [
        {
            'name': 'Integer key format',
            'key_format': test_node_id,  # 2812625114
            'should_find': True
        },
        {
            'name': 'String decimal key format',
            'key_format': str(test_node_id),  # "2812625114"
            'should_find': True
        },
        {
            'name': 'Hex with ! prefix',
            'key_format': f"!{test_node_id:08x}",  # "!a76f40da"
            'should_find': True
        },
        {
            'name': 'Hex without prefix',
            'key_format': f"{test_node_id:08x}",  # "a76f40da"
            'should_find': True
        }
    ]
    
    print("=" * 70)
    print("Testing _find_node_in_interface with multiple key formats")
    print("=" * 70)
    
    for test_case in test_cases:
        print(f"\n📋 Test: {test_case['name']}")
        print(f"   Key format: {test_case['key_format']} (type: {type(test_case['key_format']).__name__})")
        
        # Create mock interface with nodes dict using this key format
        mock_interface = Mock()
        mock_interface.nodes = {test_case['key_format']: mock_node_info}
        
        # Try to find the node
        found_info, matched_key = monitor._find_node_in_interface(test_node_id, mock_interface)
        
        if test_case['should_find']:
            if found_info:
                print(f"   ✅ PASS: Found node with matched_key={matched_key}")
                assert found_info == mock_node_info, "Node info doesn't match"
                assert matched_key == test_case['key_format'], "Matched key doesn't match"
            else:
                print(f"   ❌ FAIL: Expected to find node but got None")
                assert False, f"Should have found node with key format {test_case['key_format']}"
        else:
            if found_info:
                print(f"   ❌ FAIL: Found node but shouldn't have")
                assert False, "Should not have found node"
            else:
                print(f"   ✅ PASS: Correctly didn't find node")

def test_dm_encryption_check_scenario():
    """Test the exact scenario from the problem statement"""
    
    print("\n" + "=" * 70)
    print("Testing real-world scenario from problem statement")
    print("=" * 70)
    
    # Create mock node_manager
    node_manager = Mock()
    node_manager.get_node_name = Mock(return_value="tigro t1000E")
    
    # Create monitor
    monitor = TrafficMonitor(node_manager)
    
    # Node ID from problem statement: 0xa76f40da
    from_id = 0xa76f40da
    
    # Simulate interface.nodes with hex string format (common in TCP mode)
    mock_node_info = {
        'user': {
            'longName': 'tigro t1000E',
            'publicKey': 'KzIbS2tRqpaFe45u...',  # Sample key
            'shortName': 't10E'
        }
    }
    
    mock_interface = Mock()
    # Store with hex format (which was failing before)
    mock_interface.nodes = {
        f"!{from_id:08x}": mock_node_info  # "!a76f40da"
    }
    
    node_manager.interface = mock_interface
    
    print(f"\n📊 Setup:")
    print(f"   Node ID: 0x{from_id:08x}")
    print(f"   Interface.nodes key: !{from_id:08x}")
    print(f"   Public key: {mock_node_info['user']['publicKey']}")
    
    # Test the lookup
    found_info, matched_key = monitor._find_node_in_interface(from_id, mock_interface)
    
    print(f"\n🔍 Result:")
    if found_info:
        print(f"   ✅ Node found with key format: {matched_key}")
        print(f"   Public key retrieved: {found_info['user']['publicKey']}")
        
        # Verify it matches
        assert found_info == mock_node_info
        assert matched_key == f"!{from_id:08x}"
        print("\n✅ TEST PASSED: Key lookup works correctly!")
    else:
        print(f"   ❌ Node NOT found - this would cause the bug!")
        assert False, "Node should have been found with multi-format search"

def test_backward_compatibility():
    """Test that old integer-based keys still work"""
    
    print("\n" + "=" * 70)
    print("Testing backward compatibility with integer keys")
    print("=" * 70)
    
    node_manager = Mock()
    monitor = TrafficMonitor(node_manager)
    
    from_id = 0xa76f40da
    
    mock_node_info = {
        'user': {
            'publicKey': 'TestKey123'
        }
    }
    
    mock_interface = Mock()
    # Old-style integer key (should still work as first priority)
    mock_interface.nodes = {from_id: mock_node_info}
    
    found_info, matched_key = monitor._find_node_in_interface(from_id, mock_interface)
    
    if found_info:
        print(f"   ✅ Integer key format still works")
        print(f"   Matched key: {matched_key} (type: {type(matched_key).__name__})")
        assert found_info == mock_node_info
        assert matched_key == from_id
    else:
        print(f"   ❌ FAIL: Integer key lookup broken")
        assert False, "Should find node with integer key"

if __name__ == '__main__':
    print("\n🔐 DM Key Lookup Fix - Test Suite")
    print("Testing multi-format key search in interface.nodes")
    print()
    
    try:
        test_find_node_in_interface_multiple_formats()
        test_dm_encryption_check_scenario()
        test_backward_compatibility()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("Summary:")
        print("  • Multi-format key search works correctly")
        print("  • Real-world scenario from problem statement fixed")
        print("  • Backward compatibility maintained")
        print()
        print("This fix ensures that public keys are found regardless of")
        print("how interface.nodes stores them (int, str, hex, etc.)")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
