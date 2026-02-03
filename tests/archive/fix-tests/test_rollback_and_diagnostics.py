#!/usr/bin/env python3
"""
Test: Verify rollback to debug_print and new diagnostic logging
"""

import sys
import io
from unittest.mock import Mock, MagicMock
import time

# Mock config before importing
sys.modules['config'] = MagicMock()
sys.modules['config'].DEBUG_MODE = True  # User says they ARE in debug mode

# Capture output
captured_info = []
captured_debug = []

def mock_info_print(msg):
    captured_info.append(msg)
    print(f"[INFO] {msg}")

def mock_debug_print(msg):
    captured_debug.append(msg)
    print(f"[DEBUG] {msg}")

# Mock utils functions
sys.modules['utils'] = MagicMock()
sys.modules['utils'].info_print = mock_info_print
sys.modules['utils'].debug_print = mock_debug_print
sys.modules['utils'].error_print = mock_info_print

# Mock other dependencies
sys.modules['traffic_persistence'] = MagicMock()

# Import traffic_monitor
from traffic_monitor import TrafficMonitor

def test_diagnostic_logging():
    """Test that diagnostic entry points use info_print (always visible)"""
    print("\n" + "="*70)
    print("TEST: Diagnostic Entry Point Logging")
    print("="*70)
    
    captured_info.clear()
    captured_debug.clear()
    
    # Create mock interface and node_manager
    mock_interface = Mock()
    mock_interface.localNode = Mock()
    mock_interface.localNode.nodeNum = 0x87654321
    
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="TestNode")
    
    monitor = TrafficMonitor(node_manager=mock_node_manager)
    
    # Create a MeshCore test packet
    packet = {
        'from': 0x12345678,
        'to': 0x87654321,
        'id': 123456,
        'rxTime': int(time.time()),
        'rssi': 0,
        'snr': 0.0,
        'hopLimit': 0,
        'hopStart': 0,
        'channel': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'Test MeshCore message'
        }
    }
    
    # Call add_packet with meshcore source
    monitor.add_packet(packet, source='meshcore', my_node_id=0x87654321, interface=mock_interface)
    
    # Verify diagnostic entry points used info_print (ALWAYS visible)
    print("\n📋 Info logs (ALWAYS visible):")
    for msg in captured_info:
        print(f"  ✅ {msg}")
    
    print("\n📋 Debug logs (DEBUG_MODE only):")
    for msg in captured_debug[:5]:  # Show first 5
        print(f"  ✅ {msg}")
    
    # Check that diagnostic entry points are present
    entry_logs = [msg for msg in captured_info if 'add_packet ENTRY' in msg]
    comprehensive_entry = [msg for msg in captured_info if '_log_comprehensive_packet_debug CALLED' in msg]
    about_to_call = [msg for msg in captured_info if 'About to call' in msg]
    
    print("\n🔍 Diagnostic Checks:")
    print(f"  • add_packet ENTRY logs: {len(entry_logs)} (should be 1)")
    print(f"  • About to call comprehensive debug: {len(about_to_call)} (should be 1)")
    print(f"  • comprehensive debug CALLED: {len(comprehensive_entry)} (should be 1)")
    
    # Check that packet saved log uses debug_print (rollback from info_print)
    saved_logs = [msg for msg in captured_debug if 'Paquet enregistré' in msg]
    print(f"  • 'Paquet enregistré' in debug logs: {len(saved_logs)} (should be 1, rolled back from info_print)")
    
    # Verify meshcore source is visible in diagnostics
    meshcore_mentions = [msg for msg in captured_info if 'meshcore' in msg]
    print(f"  • 'meshcore' mentioned in diagnostics: {len(meshcore_mentions)} times")
    
    assert len(entry_logs) == 1, "Should have 1 add_packet ENTRY log"
    assert len(comprehensive_entry) == 1, "Should have 1 comprehensive debug CALLED log"
    assert len(about_to_call) == 1, "Should have 'About to call' log"
    assert len(saved_logs) >= 1, "Should have 'Paquet enregistré' in debug logs (rollback)"
    assert 'source=meshcore' in entry_logs[0], "Entry log should show source=meshcore"
    
    print("\n✅ TEST PASSED - Diagnostic entry points working correctly!")
    print("   - Entry points use info_print (ALWAYS visible)")
    print("   - Packet saved uses debug_print (rolled back)")
    print("   - MeshCore source clearly identified")

def test_comprehensive_debug_still_works():
    """Verify comprehensive debug output still appears in DEBUG_MODE"""
    print("\n" + "="*70)
    print("TEST: Comprehensive Debug Still Works (DEBUG_MODE=True)")
    print("="*70)
    
    captured_info.clear()
    captured_debug.clear()
    
    # Ensure DEBUG_MODE is True
    sys.modules['config'].DEBUG_MODE = True
    
    # Create mock
    mock_interface = Mock()
    mock_interface.localNode = Mock()
    mock_interface.localNode.nodeNum = 0x87654321
    
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="TestNode")
    
    monitor = TrafficMonitor(node_manager=mock_node_manager)
    
    # Create test packet
    packet = {
        'from': 0x12345678,
        'to': 0x87654321,
        'id': 654321,
        'rxTime': int(time.time()),
        'rssi': -85,
        'snr': 7.5,
        'hopLimit': 3,
        'hopStart': 5,
        'channel': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'Test comprehensive debug'
        }
    }
    
    # Call add_packet
    monitor.add_packet(packet, source='meshcore', my_node_id=0x87654321, interface=mock_interface)
    
    # Check for comprehensive debug box - now should say "MESHCORE PACKET DEBUG"
    box_start = [msg for msg in captured_debug if '╔═══' in msg]
    # Updated to check for either network type label
    box_content = [msg for msg in captured_debug if 'PACKET DEBUG' in msg]
    
    print(f"\n📦 Comprehensive debug box found: {len(box_start) > 0}")
    print(f"📦 Box content lines: {len(box_content)}")
    
    if box_start:
        print("\n📋 First few lines of comprehensive debug:")
        for msg in captured_debug[:15]:
            if '╔' in msg or '║' in msg or '╚' in msg:
                print(f"  {msg}")
    
    assert len(box_start) > 0, "Should have comprehensive debug box"
    assert len(box_content) > 0, "Should have packet debug content"
    
    print("\n✅ TEST PASSED - Comprehensive debug still works in DEBUG_MODE!")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("ROLLBACK AND DIAGNOSTICS TEST SUITE")
    print("="*70)
    print("Testing that:")
    print("  1. info_print changes were rolled back to debug_print")
    print("  2. New diagnostic entry points use info_print (ALWAYS visible)")
    print("  3. User can see where MeshCore packets are entering/flowing")
    print("  4. Comprehensive debug still works in DEBUG_MODE")
    
    test_diagnostic_logging()
    test_comprehensive_debug_still_works()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    print("\n✨ Summary:")
    print("  • Rollback complete: 'Paquet enregistré' uses debug_print")
    print("  • Diagnostic entry points use info_print (ALWAYS visible)")
    print("  • User can trace MeshCore packet flow even without DEBUG_MODE")
    print("  • Comprehensive debug works when DEBUG_MODE=True")
    print("\n💡 User should now see:")
    print("  🔵 add_packet ENTRY | source=meshcore")
    print("  🔍 About to call _log_comprehensive_packet_debug")
    print("  🔷 _log_comprehensive_packet_debug CALLED")
    print("  [DEBUG] ╔═══ PACKET DEBUG (if DEBUG_MODE=True)")
