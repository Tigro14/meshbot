#!/usr/bin/env python3
"""
Test script to verify packet debug labels correctly identify network source
"""

import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io
from contextlib import redirect_stdout, redirect_stderr
from traffic_monitor import TrafficMonitor
from node_manager import NodeManager

def capture_debug_output(func):
    """Capture debug output from a function"""
    captured_output = []
    
    # Mock debug_print to capture output
    import utils
    original_debug = utils.debug_print
    original_info = utils.info_print
    
    def mock_debug(msg):
        captured_output.append(msg)
        
    def mock_info(msg):
        captured_output.append(msg)
    
    utils.debug_print = mock_debug
    utils.info_print = mock_info
    
    try:
        func()
    finally:
        utils.debug_print = original_debug
        utils.info_print = original_info
    
    return captured_output

def test_meshtastic_label():
    """Test that Meshtastic packets are labeled correctly"""
    print("\n" + "="*60)
    print("TEST 1: Meshtastic Packet Label")
    print("="*60)
    
    # Create mock objects
    class MockInterface:
        def __init__(self):
            self.nodes = {}
            self.localNode = None
    
    class MockNodeManager:
        def __init__(self):
            self.nodes = {}
            self.interface = MockInterface()
        
        def get_node_name(self, node_id):
            return f"Node_{node_id:08x}"
    
    node_manager = MockNodeManager()
    monitor = TrafficMonitor(node_manager)
    
    # Create a test packet
    packet = {
        'from': 0x7c5b0738,
        'to': 0xFFFFFFFF,
        'id': 12345,
        'rxTime': 1769971476,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'Test message from Meshtastic'
        }
    }
    
    # Capture output
    def add_meshtastic_packet():
        monitor.add_packet(packet, source='meshtastic', my_node_id=0x12345678, interface=MockInterface())
    
    output = capture_debug_output(add_meshtastic_packet)
    
    # Check for correct label - look in the full output string
    full_output = '\n'.join(output)
    has_meshtastic = 'MESHTASTIC PACKET DEBUG' in full_output
    has_meshcore = 'MESHCORE PACKET DEBUG' in full_output and 'MESHTASTIC PACKET DEBUG' not in full_output
    
    print(f"\n✓ Contains 'MESHTASTIC PACKET DEBUG': {has_meshtastic}")
    print(f"✓ Contains only 'MESHCORE PACKET DEBUG': {has_meshcore}")
    
    # Show sample of the label
    for line in output:
        if 'PACKET DEBUG' in line:
            print(f"\n📋 Found label line:")
            print(f"   {line}")
            break
    
    assert has_meshtastic, "❌ No MESHTASTIC PACKET DEBUG label found!"
    assert not has_meshcore, "❌ Found incorrect MESHCORE label for Meshtastic packet!"
    
    print("\n✅ TEST 1 PASSED: Meshtastic packets correctly labeled")
    return True

def test_meshcore_label():
    """Test that MeshCore packets are labeled correctly"""
    print("\n" + "="*60)
    print("TEST 2: MeshCore Packet Label")
    print("="*60)
    
    # Create mock objects
    class MockInterface:
        def __init__(self):
            self.nodes = {}
            self.localNode = None
    
    class MockNodeManager:
        def __init__(self):
            self.nodes = {}
            self.interface = MockInterface()
        
        def get_node_name(self, node_id):
            return f"MeshCore_{node_id:08x}"
    
    node_manager = MockNodeManager()
    monitor = TrafficMonitor(node_manager)
    
    # Create a test packet
    packet = {
        'from': 0xabcd1234,
        'to': 0xFFFFFFFF,
        'id': 67890,
        'rxTime': 1769971500,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'Test message from MeshCore'
        }
    }
    
    # Capture output
    def add_meshcore_packet():
        monitor.add_packet(packet, source='meshcore', my_node_id=0x12345678, interface=MockInterface())
    
    output = capture_debug_output(add_meshcore_packet)
    
    # Check for correct label - look in the full output string
    full_output = '\n'.join(output)
    has_meshcore = 'MESHCORE PACKET DEBUG' in full_output
    has_meshtastic = 'MESHTASTIC PACKET DEBUG' in full_output
    
    print(f"\n✓ Contains 'MESHCORE PACKET DEBUG': {has_meshcore}")
    print(f"✓ Contains 'MESHTASTIC PACKET DEBUG': {has_meshtastic}")
    
    # Show sample of the label
    for line in output:
        if 'PACKET DEBUG' in line:
            print(f"\n📋 Found label line:")
            print(f"   {line}")
            break
    
    assert has_meshcore, "❌ No MESHCORE PACKET DEBUG label found!"
    assert not has_meshtastic, "❌ Found incorrect MESHTASTIC label for MeshCore packet!"
    
    print("\n✅ TEST 2 PASSED: MeshCore packets correctly labeled")
    return True

def test_tcp_label():
    """Test that TCP (Meshtastic via TCP) packets are labeled as Meshtastic"""
    print("\n" + "="*60)
    print("TEST 3: TCP/Meshtastic Packet Label")
    print("="*60)
    
    # Create mock objects
    class MockInterface:
        def __init__(self):
            self.nodes = {}
            self.localNode = None
    
    class MockNodeManager:
        def __init__(self):
            self.nodes = {}
            self.interface = MockInterface()
        
        def get_node_name(self, node_id):
            return f"TCP_Node_{node_id:08x}"
    
    node_manager = MockNodeManager()
    monitor = TrafficMonitor(node_manager)
    
    # Create a test packet
    packet = {
        'from': 0x11223344,
        'to': 0xFFFFFFFF,
        'id': 11111,
        'rxTime': 1769971600,
        'decoded': {
            'portnum': 'POSITION_APP',
            'payload': b'Position data'
        }
    }
    
    # Capture output
    def add_tcp_packet():
        monitor.add_packet(packet, source='tcp', my_node_id=0x12345678, interface=MockInterface())
    
    output = capture_debug_output(add_tcp_packet)
    
    # Check for correct label (TCP should be labeled as MESHTASTIC)
    full_output = '\n'.join(output)
    has_meshtastic = 'MESHTASTIC PACKET DEBUG' in full_output
    has_meshcore = 'MESHCORE PACKET DEBUG' in full_output and 'MESHTASTIC PACKET DEBUG' not in full_output
    
    print(f"\n✓ Contains 'MESHTASTIC PACKET DEBUG': {has_meshtastic}")
    print(f"✓ Contains only 'MESHCORE PACKET DEBUG': {has_meshcore}")
    
    # Show sample of the label
    for line in output:
        if 'PACKET DEBUG' in line:
            print(f"\n📋 Found label line:")
            print(f"   {line}")
            break
    
    assert has_meshtastic, "❌ No MESHTASTIC PACKET DEBUG label found for TCP source!"
    assert not has_meshcore, "❌ Found incorrect MESHCORE label for TCP packet!"
    
    print("\n✅ TEST 3 PASSED: TCP packets correctly labeled as Meshtastic")
    return True

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("PACKET LABEL VERIFICATION TEST SUITE")
    print("="*60)
    
    tests = [
        test_meshtastic_label,
        test_meshcore_label,
        test_tcp_label,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
