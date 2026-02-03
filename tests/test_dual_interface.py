#!/usr/bin/env python3
"""
Test script for Dual Interface Manager

This script tests the dual network mode functionality without requiring
actual hardware connections.
"""

import sys
import time
from dual_interface_manager import DualInterfaceManager, NetworkSource


class MockInterface:
    """Mock interface for testing"""
    def __init__(self, name):
        self.name = name
        self.messages_sent = []
        self.localNode = None
    
    def sendText(self, text, destinationId):
        """Mock send function"""
        self.messages_sent.append({
            'text': text,
            'destination': destinationId,
            'time': time.time()
        })
        print(f"[{self.name}] Mock send: '{text}' to 0x{destinationId:08x}")
        return True


def test_dual_interface_initialization():
    """Test 1: Basic initialization"""
    print("\n" + "="*60)
    print("TEST 1: Dual Interface Initialization")
    print("="*60)
    
    manager = DualInterfaceManager()
    
    assert not manager.has_meshtastic(), "Should not have Meshtastic initially"
    assert not manager.has_meshcore(), "Should not have MeshCore initially"
    assert not manager.is_dual_mode(), "Should not be in dual mode initially"
    
    print("✅ Initialization test passed")
    return True


def test_interface_setup():
    """Test 2: Setting up interfaces"""
    print("\n" + "="*60)
    print("TEST 2: Interface Setup")
    print("="*60)
    
    manager = DualInterfaceManager()
    
    # Create mock interfaces
    meshtastic_interface = MockInterface("Meshtastic")
    meshcore_interface = MockInterface("MeshCore")
    
    # Set interfaces
    manager.set_meshtastic_interface(meshtastic_interface)
    manager.set_meshcore_interface(meshcore_interface)
    
    assert manager.has_meshtastic(), "Should have Meshtastic"
    assert manager.has_meshcore(), "Should have MeshCore"
    assert manager.is_dual_mode(), "Should be in dual mode"
    
    # Test primary interface selection (should prefer Meshtastic)
    primary = manager.get_primary_interface()
    assert primary == meshtastic_interface, "Primary should be Meshtastic"
    
    print("✅ Interface setup test passed")
    return True


def test_message_routing():
    """Test 3: Message routing to correct network"""
    print("\n" + "="*60)
    print("TEST 3: Message Routing")
    print("="*60)
    
    manager = DualInterfaceManager()
    
    # Create mock interfaces
    meshtastic_interface = MockInterface("Meshtastic")
    meshcore_interface = MockInterface("MeshCore")
    
    manager.set_meshtastic_interface(meshtastic_interface)
    manager.set_meshcore_interface(meshcore_interface)
    
    # Test sending to Meshtastic network
    print("\n→ Testing Meshtastic route...")
    success = manager.send_message(
        "Test message to Meshtastic",
        0x12345678,
        NetworkSource.MESHTASTIC
    )
    assert success, "Should send to Meshtastic successfully"
    assert len(meshtastic_interface.messages_sent) == 1, "Meshtastic should have 1 message"
    assert len(meshcore_interface.messages_sent) == 0, "MeshCore should have 0 messages"
    
    # Test sending to MeshCore network
    print("\n→ Testing MeshCore route...")
    success = manager.send_message(
        "Test message to MeshCore",
        0x87654321,
        NetworkSource.MESHCORE
    )
    assert success, "Should send to MeshCore successfully"
    assert len(meshtastic_interface.messages_sent) == 1, "Meshtastic should still have 1 message"
    assert len(meshcore_interface.messages_sent) == 1, "MeshCore should have 1 message"
    
    # Test auto-routing (should use primary = Meshtastic)
    print("\n→ Testing auto-routing (no network specified)...")
    success = manager.send_message(
        "Test auto-route message",
        0xABCDEF00,
        None  # No network specified
    )
    assert success, "Should send successfully"
    assert len(meshtastic_interface.messages_sent) == 2, "Should route to primary (Meshtastic)"
    
    print("✅ Message routing test passed")
    return True


def test_statistics():
    """Test 4: Statistics tracking"""
    print("\n" + "="*60)
    print("TEST 4: Statistics Tracking")
    print("="*60)
    
    manager = DualInterfaceManager()
    
    # Create mock interfaces
    meshtastic_interface = MockInterface("Meshtastic")
    meshcore_interface = MockInterface("MeshCore")
    
    manager.set_meshtastic_interface(meshtastic_interface)
    manager.set_meshcore_interface(meshcore_interface)
    
    # Simulate receiving packets
    print("\n→ Simulating Meshtastic packet...")
    manager.on_meshtastic_message({'from': 0x11111111, 'to': 0x22222222}, meshtastic_interface)
    
    print("\n→ Simulating MeshCore packet...")
    manager.on_meshcore_message({'from': 0x33333333, 'to': 0x44444444}, meshcore_interface)
    
    # Get statistics
    stats = manager.get_statistics()
    
    assert stats['dual_mode'], "Should be in dual mode"
    assert stats['meshtastic']['packets'] == 1, "Should have 1 Meshtastic packet"
    assert stats['meshcore']['packets'] == 1, "Should have 1 MeshCore packet"
    assert stats['total_packets'] == 2, "Should have 2 total packets"
    
    # Test status report
    print("\n→ Generating status report...")
    report_compact = manager.get_status_report(compact=True)
    print(f"Compact: {report_compact}")
    
    report_detailed = manager.get_status_report(compact=False)
    print(f"Detailed:\n{report_detailed}")
    
    assert "🌐M:" in report_compact, "Compact report should mention Meshtastic"
    assert "🔗C:" in report_compact, "Compact report should mention MeshCore"
    assert "Meshtastic Network" in report_detailed, "Detailed report should have section header"
    
    print("✅ Statistics test passed")
    return True


def test_single_interface_mode():
    """Test 5: Single interface mode (only one network)"""
    print("\n" + "="*60)
    print("TEST 5: Single Interface Mode")
    print("="*60)
    
    # Test with only Meshtastic
    print("\n→ Testing Meshtastic-only mode...")
    manager1 = DualInterfaceManager()
    meshtastic = MockInterface("Meshtastic")
    manager1.set_meshtastic_interface(meshtastic)
    
    assert manager1.has_meshtastic(), "Should have Meshtastic"
    assert not manager1.has_meshcore(), "Should not have MeshCore"
    assert not manager1.is_dual_mode(), "Should not be in dual mode"
    
    primary = manager1.get_primary_interface()
    assert primary == meshtastic, "Primary should be Meshtastic"
    
    # Test with only MeshCore
    print("\n→ Testing MeshCore-only mode...")
    manager2 = DualInterfaceManager()
    meshcore = MockInterface("MeshCore")
    manager2.set_meshcore_interface(meshcore)
    
    assert not manager2.has_meshtastic(), "Should not have Meshtastic"
    assert manager2.has_meshcore(), "Should have MeshCore"
    assert not manager2.is_dual_mode(), "Should not be in dual mode"
    
    primary = manager2.get_primary_interface()
    assert primary == meshcore, "Primary should be MeshCore (only option)"
    
    print("✅ Single interface mode test passed")
    return True


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("DUAL INTERFACE MANAGER TEST SUITE")
    print("="*60)
    
    tests = [
        test_dual_interface_initialization,
        test_interface_setup,
        test_message_routing,
        test_statistics,
        test_single_interface_mode,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ TEST ERROR: {e}")
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
