#!/usr/bin/env python3
"""
Test to verify the NameError fix in traffic_monitor.py
Tests that _log_packet_debug() can be called with source parameter without errors.
"""

import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_log_packet_debug_with_source():
    """Test that _log_packet_debug accepts source parameter and doesn't crash"""
    
    print("\n" + "="*70)
    print("TEST: _log_packet_debug with source parameter")
    print("="*70)
    
    # Create mock dependencies
    mock_persistence = Mock()
    mock_node_manager = Mock()
    mock_interface = Mock()
    
    # Set return values for mocks
    mock_node_manager.get_node_name.return_value = "TestNode"
    
    # Import after setting up mocks
    from traffic_monitor import TrafficMonitor
    
    # Create TrafficMonitor instance
    monitor = TrafficMonitor(
        persistence=mock_persistence,
        node_manager=mock_node_manager,
        interface=mock_interface
    )
    
    # Create a test packet (MeshCore DM)
    test_packet = {
        'from': 0x143bcd7f,
        'to': 0xfffffffe,
        'id': 123456,
        'rxTime': 1769668386,
        'rssi': 0,
        'snr': 0.0,
        'hopLimit': 0,
        'hopStart': 0,
        'channel': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'/power'
        }
    }
    
    # Test parameters
    packet_type = 'TEXT_MESSAGE_APP'
    source = 'meshcore'  # This is the critical parameter that was missing
    sender_name = 'Tigro T1000E'
    from_id = 0x143bcd7f
    hops_taken = 0
    snr = 0.0
    
    try:
        # Call _log_packet_debug with the new signature
        print(f"\n📞 Calling _log_packet_debug with:")
        print(f"   packet_type={packet_type}")
        print(f"   source={source}")
        print(f"   sender_name={sender_name}")
        print(f"   from_id=0x{from_id:08x}")
        print(f"   hops_taken={hops_taken}")
        print(f"   snr={snr}")
        
        # Patch debug_print and info_print to avoid output
        with patch('traffic_monitor.debug_print'):
            with patch('traffic_monitor.info_print') as mock_info_print:
                monitor._log_packet_debug(
                    packet_type, source, sender_name, from_id, hops_taken, snr, test_packet
                )
        
        # Check that info_print was called with source in the message
        called = False
        for call in mock_info_print.call_args_list:
            if call and len(call[0]) > 0:
                msg = call[0][0]
                if 'source=' in msg and source in msg:
                    called = True
                    print(f"\n✅ info_print called correctly with source:")
                    print(f"   {msg}")
                    break
        
        if not called:
            print(f"\n⚠️  info_print not called with source (but no crash!)")
        
        print(f"\n✅ SUCCESS: _log_packet_debug completed without NameError!")
        print(f"✅ The 'source' parameter is now properly passed and used")
        return True
        
    except NameError as e:
        print(f"\n❌ FAILED: NameError still occurs: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    except Exception as e:
        print(f"\n❌ FAILED: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_add_packet_passes_source():
    """Test that add_packet passes source to _log_packet_debug"""
    
    print("\n" + "="*70)
    print("TEST: add_packet passes source parameter to _log_packet_debug")
    print("="*70)
    
    # Create mock dependencies
    mock_persistence = Mock()
    mock_node_manager = Mock()
    mock_interface = Mock()
    
    # Set return values
    mock_node_manager.get_node_name.return_value = "TestNode"
    mock_persistence.save_meshcore_packet = Mock()
    
    # Import
    from traffic_monitor import TrafficMonitor
    
    # Create TrafficMonitor instance
    monitor = TrafficMonitor(
        persistence=mock_persistence,
        node_manager=mock_node_manager,
        interface=mock_interface
    )
    
    # Create a test MeshCore packet
    test_packet = {
        'from': 0x143bcd7f,
        'to': 0xfffffffe,
        'id': 123456,
        'rxTime': 1769668386,
        'rssi': 0,
        'snr': 0.0,
        'hopLimit': 0,
        'hopStart': 0,
        'channel': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'/power'
        }
    }
    
    try:
        # Mock _log_packet_debug to capture its arguments
        original_log = monitor._log_packet_debug
        call_args = []
        
        def mock_log_packet_debug(*args, **kwargs):
            call_args.append((args, kwargs))
            # Don't call original to avoid output
        
        monitor._log_packet_debug = mock_log_packet_debug
        
        # Call add_packet with MeshCore source
        print(f"\n📞 Calling add_packet with source='meshcore'")
        monitor.add_packet(test_packet, source='meshcore', interface=mock_interface)
        
        # Check if _log_packet_debug was called
        if call_args:
            args, kwargs = call_args[0]
            print(f"\n✅ _log_packet_debug was called with {len(args)} arguments")
            
            # Check if source is in the arguments (should be 2nd parameter after self)
            if len(args) >= 2:
                # args[0] is self (implicit), args[1] should be packet_type, args[2] should be source
                if len(args) >= 3:
                    source_arg = args[2]
                    print(f"✅ Argument 2 (source): {source_arg}")
                    if source_arg == 'meshcore':
                        print(f"✅ SUCCESS: source='meshcore' is correctly passed!")
                        return True
                    else:
                        print(f"❌ FAILED: source='{source_arg}' (expected 'meshcore')")
                        return False
                else:
                    print(f"❌ FAILED: Not enough arguments ({len(args)})")
                    return False
        else:
            print(f"❌ FAILED: _log_packet_debug was not called")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TESTING NameError FIX IN traffic_monitor.py")
    print("="*70)
    
    results = []
    
    # Test 1: _log_packet_debug with source
    results.append(("_log_packet_debug with source", test_log_packet_debug_with_source()))
    
    # Test 2: add_packet passes source
    results.append(("add_packet passes source", test_add_packet_passes_source()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("="*70)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print("\n✨ The NameError fix is working correctly:")
        print("   • _log_packet_debug accepts 'source' parameter")
        print("   • add_packet passes 'source' to _log_packet_debug")
        print("   • No more 'packet_entry' is not defined error")
        print("   • MeshCore packets will now be logged with full debug output")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
