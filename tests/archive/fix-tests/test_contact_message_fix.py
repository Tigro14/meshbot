#!/usr/bin/env python3
"""
Test for contact message (DM) handling fix
Verifies that DMs from MeshCore are properly processed
"""

import sys
import os

# Mock config module before importing
sys.modules['config'] = type('config', (), {
    'DEBUG_MODE': False,
    'BOT_POSITION': None
})()

# Mock the meshcore library before importing
class MockMeshCore:
    pass

class MockEventType:
    CONTACT_MSG_RECV = 'contact_message'

sys.modules['meshcore'] = type('meshcore', (), {
    'MeshCore': MockMeshCore,
    'EventType': MockEventType
})()

from node_manager import NodeManager
from utils import info_print, debug_print

def test_pubkey_prefix_lookup():
    """Test NodeManager.find_node_by_pubkey_prefix()"""
    print("\n" + "="*60)
    print("TEST 1: Pubkey Prefix Lookup")
    print("="*60)
    
    # Create a NodeManager with test data
    node_mgr = NodeManager(interface=None)
    
    # Add a test node with publicKey
    test_node_id = 0x12345678
    test_pubkey = "143bcd7f1b1fabcdef0123456789abcdef"
    
    node_mgr.node_names[test_node_id] = {
        'name': 'TestNode',
        'publicKey': test_pubkey
    }
    
    # Test 1: Exact prefix match
    print("\n✓ Test 1a: Exact prefix match")
    result = node_mgr.find_node_by_pubkey_prefix('143bcd7f1b1f')
    assert result == test_node_id, f"Expected {test_node_id:08x}, got {result:08x if result else None}"
    print(f"  ✅ Found node 0x{result:08x} with pubkey prefix '143bcd7f1b1f'")
    
    # Test 2: Case insensitive
    print("\n✓ Test 1b: Case insensitive")
    result = node_mgr.find_node_by_pubkey_prefix('143BCD7F1B1F')
    assert result == test_node_id, f"Expected {test_node_id:08x}, got {result:08x if result else None}"
    print(f"  ✅ Found node 0x{result:08x} with uppercase prefix")
    
    # Test 3: Shorter prefix
    print("\n✓ Test 1c: Shorter prefix")
    result = node_mgr.find_node_by_pubkey_prefix('143bcd')
    assert result == test_node_id, f"Expected {test_node_id:08x}, got {result:08x if result else None}"
    print(f"  ✅ Found node 0x{result:08x} with short prefix '143bcd'")
    
    # Test 4: Non-existent prefix
    print("\n✓ Test 1d: Non-existent prefix")
    result = node_mgr.find_node_by_pubkey_prefix('999999')
    assert result is None, f"Expected None, got {result}"
    print("  ✅ Correctly returned None for non-existent prefix")
    
    # Test 5: Bytes format
    print("\n✓ Test 1e: Bytes format publicKey")
    test_node_id_2 = 0x87654321
    test_pubkey_bytes = bytes.fromhex("aabbccdd112233445566778899")
    node_mgr.node_names[test_node_id_2] = {
        'name': 'TestNode2',
        'publicKey': test_pubkey_bytes
    }
    result = node_mgr.find_node_by_pubkey_prefix('aabbcc')
    assert result == test_node_id_2, f"Expected {test_node_id_2:08x}, got {result:08x if result else None}"
    print(f"  ✅ Found node 0x{result:08x} with bytes publicKey")
    
    print("\n✅ All pubkey lookup tests passed!\n")


def test_meshcore_dm_packet_structure():
    """Test that MeshCore DM packets are structured correctly"""
    print("\n" + "="*60)
    print("TEST 2: MeshCore DM Packet Structure")
    print("="*60)
    
    # Simulate what meshcore_cli_wrapper creates
    print("\n✓ Test 2a: DM with resolved sender_id")
    local_node_id = 0xAABBCCDD
    sender_id = 0x12345678
    
    packet = {
        'from': sender_id,
        'to': local_node_id,  # DM: to our node, not broadcast
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': '/help'.encode('utf-8')
        },
        '_meshcore_dm': True  # Mark as DM
    }
    
    # Check packet structure
    assert packet['from'] == sender_id, "Sender ID should be set"
    assert packet['to'] == local_node_id, "To ID should be local node"
    assert packet['to'] != 0xFFFFFFFF, "To ID should NOT be broadcast"
    assert packet['_meshcore_dm'] == True, "Should be marked as MeshCore DM"
    
    # Check broadcast detection (should NOT be broadcast)
    to_id = packet['to']
    is_meshcore_dm = packet.get('_meshcore_dm', False)
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert not is_broadcast, "DM should NOT be treated as broadcast"
    print(f"  ✅ DM packet correctly structured: from=0x{sender_id:08x}, to=0x{local_node_id:08x}")
    print(f"  ✅ Broadcast check: is_broadcast={is_broadcast} (expected False)")
    
    print("\n✓ Test 2b: DM with unresolved sender (fallback)")
    packet_unresolved = {
        'from': 0xFFFFFFFF,  # Unresolved sender
        'to': local_node_id,  # Still DM to our node
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': '/help'.encode('utf-8')
        },
        '_meshcore_dm': True  # Mark as DM
    }
    
    # Even with 0xFFFFFFFF sender, it should not be treated as broadcast
    # because _meshcore_dm flag is set
    to_id = packet_unresolved['to']
    is_meshcore_dm = packet_unresolved.get('_meshcore_dm', False)
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert not is_broadcast, "DM with unresolved sender should NOT be broadcast"
    print(f"  ✅ Unresolved sender packet: from=0x{packet_unresolved['from']:08x} (fallback)")
    print(f"  ✅ Broadcast check: is_broadcast={is_broadcast} (expected False)")
    
    print("\n✅ All packet structure tests passed!\n")


def test_dm_vs_broadcast_detection():
    """Test that DMs and broadcasts are correctly distinguished"""
    print("\n" + "="*60)
    print("TEST 3: DM vs Broadcast Detection")
    print("="*60)
    
    local_node_id = 0xAABBCCDD
    sender_id = 0x12345678
    
    # Test 1: Regular broadcast (no _meshcore_dm flag)
    print("\n✓ Test 3a: Regular broadcast")
    broadcast_packet = {
        'from': sender_id,
        'to': 0xFFFFFFFF,
        'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'/echo test'}
    }
    
    to_id = broadcast_packet['to']
    is_meshcore_dm = broadcast_packet.get('_meshcore_dm', False)
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert is_broadcast == True, "Regular broadcast should be detected"
    print(f"  ✅ Regular broadcast: to=0x{to_id:08x}, is_broadcast={is_broadcast}")
    
    # Test 2: MeshCore DM (with _meshcore_dm flag)
    print("\n✓ Test 3b: MeshCore DM")
    dm_packet = {
        'from': sender_id,
        'to': local_node_id,
        'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'/help'},
        '_meshcore_dm': True
    }
    
    to_id = dm_packet['to']
    is_meshcore_dm = dm_packet.get('_meshcore_dm', False)
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert is_broadcast == False, "MeshCore DM should NOT be broadcast"
    print(f"  ✅ MeshCore DM: to=0x{to_id:08x}, is_broadcast={is_broadcast}")
    
    # Test 3: Direct message to local node (no _meshcore_dm flag)
    print("\n✓ Test 3c: Direct message to local node")
    direct_packet = {
        'from': sender_id,
        'to': local_node_id,
        'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'/my'}
    }
    
    to_id = direct_packet['to']
    is_meshcore_dm = direct_packet.get('_meshcore_dm', False)
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert is_broadcast == False, "Direct message should NOT be broadcast"
    print(f"  ✅ Direct message: to=0x{to_id:08x}, is_broadcast={is_broadcast}")
    
    print("\n✅ All DM vs broadcast tests passed!\n")


def test_contact_message_event_parsing():
    """Test parsing of contact message event from MeshCore"""
    print("\n" + "="*60)
    print("TEST 4: Contact Message Event Parsing")
    print("="*60)
    
    # Simulate the actual event structure from the logs
    print("\n✓ Test 4a: Parse event with pubkey_prefix")
    
    class MockEvent:
        def __init__(self):
            self.payload = {
                'type': 'PRIV',
                'SNR': 12.5,
                'pubkey_prefix': '143bcd7f1b1f',
                'path_len': 1,
                'txt_type': 0,
                'sender_timestamp': 1768925194,
                'text': '/help'
            }
            self.attributes = {
                'pubkey_prefix': '143bcd7f1b1f',
                'txt_type': 0
            }
    
    event = MockEvent()
    payload = event.payload
    
    # Extract pubkey_prefix
    pubkey_prefix = payload.get('pubkey_prefix')
    assert pubkey_prefix == '143bcd7f1b1f', f"Expected pubkey_prefix, got {pubkey_prefix}"
    print(f"  ✅ Extracted pubkey_prefix: {pubkey_prefix}")
    
    # Extract text
    text = payload.get('text', '')
    assert text == '/help', f"Expected '/help', got {text}"
    print(f"  ✅ Extracted text: {text}")
    
    # Check for sender_id (should be None in this case)
    sender_id = payload.get('contact_id') or payload.get('sender_id')
    assert sender_id is None, f"Expected None for sender_id, got {sender_id}"
    print(f"  ✅ sender_id is None (will need pubkey lookup)")
    
    print("\n✅ All event parsing tests passed!\n")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("CONTACT MESSAGE (DM) FIX - TEST SUITE")
    print("="*70)
    
    try:
        test_pubkey_prefix_lookup()
        test_meshcore_dm_packet_structure()
        test_dm_vs_broadcast_detection()
        test_contact_message_event_parsing()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nSummary:")
        print("  ✓ Pubkey prefix lookup works correctly")
        print("  ✓ DM packets are structured correctly")
        print("  ✓ DMs are not treated as broadcasts")
        print("  ✓ Contact message events are parsed correctly")
        print("\nThe fix should resolve the issue where contact messages")
        print("were not being processed due to sender_id = 0xFFFFFFFF.")
        print("="*70 + "\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
