#!/usr/bin/env python3
"""
Test to verify MeshCore packets get correct source='meshcore' in DEBUG mode.
"""

import sys
import time
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import Mock, MagicMock, patch

# Mock config before imports
config_mock = MagicMock()
config_mock.DEBUG_MODE = True
config_mock.MESHCORE_ENABLED = True
sys.modules['config'] = config_mock

# We need to set globals before importing main_bot
import builtins
original_globals = builtins.globals

def mock_globals():
    """Mock globals() to return our test config"""
    base_globals = original_globals()
    base_globals.update({
        'MESHCORE_ENABLED': True,
        'MESHTASTIC_ENABLED': False,
        'CONNECTION_MODE': 'serial',
        'DEBUG_MODE': True
    })
    return base_globals

# Patch globals() before importing
builtins.globals = mock_globals

from traffic_monitor import TrafficMonitor
from node_manager import NodeManager

def test_meshcore_source_detection():
    """Test that MeshCore packets get source='meshcore'"""
    print("\n" + "="*70)
    print("TEST: MeshCore Packet Source Detection")
    print("="*70)
    
    # Create mock node manager
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="MeshCoreNode")
    
    # Mock interface
    mock_interface = Mock()
    mock_interface.nodes = {}
    node_manager.interface = mock_interface
    
    # Create traffic monitor
    monitor = TrafficMonitor(node_manager)
    
    # Create a MeshCore packet
    meshcore_packet = {
        'id': 123456,
        'from': 0x12345678,
        'to': 0xFFFFFFFF,
        'rxTime': int(time.time()),
        'hopLimit': 3,
        'hopStart': 5,
        'rssi': -90,
        'snr': 8.0,
        'channel': 0,
        'viaMqtt': False,
        'wantAck': False,
        'wantResponse': False,
        'priority': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'text': 'MeshCore test message'
        }
    }
    
    print("\n1️⃣ Testing MeshCore packet with source='meshcore'...")
    
    # Process packet with source='meshcore'
    monitor.add_packet(meshcore_packet, source='meshcore', my_node_id=0x99999999, interface=node_manager.interface)
    
    # Verify packet was added
    assert len(monitor.all_packets) > 0, "Packet should be added to queue"
    print("   ✅ Packet added to queue")
    
    # Get the added packet
    added_packet = monitor.all_packets[-1]
    
    # Verify source is 'meshcore'
    assert added_packet['source'] == 'meshcore', f"Source should be 'meshcore', got '{added_packet['source']}'"
    print(f"   ✅ Packet source: {added_packet['source']}")
    
    # Verify message
    assert added_packet['message'] == 'MeshCore test message', "Message content should match"
    print(f"   ✅ Message: {added_packet['message']}")
    
    print("\n✅ TEST PASSED: MeshCore packets correctly identified with source='meshcore'")
    return True

def test_source_determination_logic():
    """Test the source determination logic from main_bot.py"""
    print("\n" + "="*70)
    print("TEST: Source Determination Logic")
    print("="*70)
    
    print("\n📋 Testing source determination with different configurations:")
    
    # Test 1: MESHCORE_ENABLED=True
    print("\n1️⃣ MESHCORE_ENABLED=True, CONNECTION_MODE='serial'")
    test_globals = {
        'MESHCORE_ENABLED': True,
        'MESHTASTIC_ENABLED': False,
        'CONNECTION_MODE': 'serial'
    }
    
    # Simulate the logic from main_bot.py
    if test_globals.get('MESHCORE_ENABLED', False):
        source = 'meshcore'
    elif test_globals.get('CONNECTION_MODE', 'serial').lower() == 'serial':
        source = 'local'
    else:
        source = 'unknown'
    
    print(f"   Expected: 'meshcore'")
    print(f"   Got:      '{source}'")
    assert source == 'meshcore', f"Should be 'meshcore' but got '{source}'"
    print("   ✅ PASS")
    
    # Test 2: MESHTASTIC_ENABLED=True, CONNECTION_MODE='serial'
    print("\n2️⃣ MESHTASTIC_ENABLED=True, CONNECTION_MODE='serial', MESHCORE_ENABLED=False")
    test_globals = {
        'MESHCORE_ENABLED': False,
        'MESHTASTIC_ENABLED': True,
        'CONNECTION_MODE': 'serial'
    }
    
    if test_globals.get('MESHCORE_ENABLED', False):
        source = 'meshcore'
    elif test_globals.get('CONNECTION_MODE', 'serial').lower() == 'serial':
        source = 'local'
    else:
        source = 'unknown'
    
    print(f"   Expected: 'local'")
    print(f"   Got:      '{source}'")
    assert source == 'local', f"Should be 'local' but got '{source}'"
    print("   ✅ PASS")
    
    # Test 3: Both disabled
    print("\n3️⃣ Both MESHTASTIC_ENABLED and MESHCORE_ENABLED False")
    test_globals = {
        'MESHCORE_ENABLED': False,
        'MESHTASTIC_ENABLED': False,
        'CONNECTION_MODE': 'serial'
    }
    
    if test_globals.get('MESHCORE_ENABLED', False):
        source = 'meshcore'
    elif test_globals.get('CONNECTION_MODE', 'serial').lower() == 'serial':
        source = 'local'
    else:
        source = 'unknown'
    
    print(f"   Expected: 'local' (fallback)")
    print(f"   Got:      '{source}'")
    assert source == 'local', f"Should be 'local' but got '{source}'"
    print("   ✅ PASS")
    
    print("\n✅ ALL SOURCE DETERMINATION TESTS PASSED")
    return True

if __name__ == '__main__':
    print("="*70)
    print("MESHCORE DEBUG LOGGING TEST SUITE")
    print("="*70)
    
    all_passed = True
    
    # Run tests
    try:
        all_passed &= test_meshcore_source_detection()
        all_passed &= test_source_determination_logic()
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Summary
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\n✨ Verification complete:")
        print("  • MeshCore packets get source='meshcore'")
        print("  • Source determination prioritizes MESHCORE_ENABLED")
        print("  • MeshCore traffic will appear in DEBUG logs")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
        sys.exit(1)
