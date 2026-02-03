#!/usr/bin/env python3
"""
Test: MeshCore Response Routing

PROBLEM:
- MeshCore DM arrives and is processed successfully
- Response is generated
- But response sent via wrong interface (Meshtastic instead of MeshCore)
- Client node doesn't receive response

ROOT CAUSE:
- MessageSender initialized without dual_interface_manager
- self.dual_interface is None
- Dual mode routing check fails
- Falls back to single mode (Meshtastic interface)

SOLUTION:
- Pass dual_interface_manager through initialization chain:
  main_bot → MessageHandler → MessageRouter → MessageSender
- MessageSender can now route responses to correct network

This test validates the fix works correctly.
"""

import unittest
from unittest.mock import MagicMock, patch


class TestMeshCoreResponseRouting(unittest.TestCase):
    """Test MeshCore response routing in dual mode"""
    
    def setUp(self):
        """Set up test fixtures"""
        print("\n" + "="*70)
        print("TEST: MeshCore Response Routing")
        print("="*70)
    
    def test_message_sender_receives_dual_interface(self):
        """Test that MessageSender receives dual_interface_manager"""
        print("\n📋 Test: MessageSender receives dual_interface_manager")
        
        from handlers.message_sender import MessageSender
        
        # Mock dependencies
        interface = MagicMock()
        node_manager = MagicMock()
        dual_interface_manager = MagicMock()
        dual_interface_manager.is_dual_mode = MagicMock(return_value=True)
        
        # Create MessageSender with dual_interface_manager
        sender = MessageSender(interface, node_manager, dual_interface_manager)
        
        # Verify dual_interface is set
        self.assertIsNotNone(sender.dual_interface,
                            "❌ MessageSender should have dual_interface set")
        self.assertEqual(sender.dual_interface, dual_interface_manager,
                        "❌ dual_interface should be the passed manager")
        print("   ✅ MessageSender has dual_interface reference")
    
    def test_dual_mode_routing_activated(self):
        """Test that dual mode routing is activated when dual_interface is present"""
        print("\n📋 Test: Dual mode routing activated")
        
        from handlers.message_sender import MessageSender
        
        # Mock dependencies
        interface = MagicMock()
        node_manager = MagicMock()
        node_manager.get_node_name = MagicMock(return_value="Node-143bcd7f")
        
        dual_interface_manager = MagicMock()
        dual_interface_manager.is_dual_mode = MagicMock(return_value=True)
        dual_interface_manager.send_message = MagicMock(return_value=True)
        
        # Create MessageSender with dual_interface
        sender = MessageSender(interface, node_manager, dual_interface_manager)
        
        # Track sender network (meshcore)
        sender_id = 0x143bcd7f
        from dual_interface_manager import NetworkSource
        sender.set_sender_network(sender_id, NetworkSource.MESHCORE)
        
        # Try to send message
        message = "Test response"
        sender.send_single(message, sender_id, "Node-143bcd7f")
        
        # Verify dual_interface.send_message was called
        self.assertTrue(dual_interface_manager.send_message.called,
                       "❌ dual_interface.send_message should be called")
        
        # Verify it was called with correct network source
        call_args = dual_interface_manager.send_message.call_args
        self.assertEqual(call_args[0][0], message,
                        "❌ Wrong message")
        self.assertEqual(call_args[0][1], sender_id,
                        "❌ Wrong sender_id")
        self.assertEqual(call_args[0][2], NetworkSource.MESHCORE,
                        "❌ Wrong network_source - should be MESHCORE")
        
        print("   ✅ Dual mode routing activated correctly")
        print(f"   ✅ Message routed to MESHCORE network")
    
    def test_without_dual_interface_uses_single_mode(self):
        """Test that without dual_interface, it falls back to single mode"""
        print("\n📋 Test: Without dual_interface, uses single mode")
        
        from handlers.message_sender import MessageSender
        
        # Mock dependencies
        interface = MagicMock()
        interface.sendText = MagicMock()
        node_manager = MagicMock()
        node_manager.get_node_name = MagicMock(return_value="Node-test")
        
        # Create MessageSender WITHOUT dual_interface (None)
        sender = MessageSender(interface, node_manager, None)
        
        # Verify dual_interface is None
        self.assertIsNone(sender.dual_interface,
                         "❌ dual_interface should be None")
        
        # Try to send message
        sender_id = 0x12345678
        message = "Test message"
        sender.send_single(message, sender_id, "Node-test")
        
        # Verify interface.sendText was called (single mode)
        self.assertTrue(interface.sendText.called,
                       "❌ interface.sendText should be called in single mode")
        
        call_args = interface.sendText.call_args
        self.assertEqual(call_args[0][0], message,
                        "❌ Wrong message")
        self.assertEqual(call_args[1]['destinationId'], sender_id,
                        "❌ Wrong destinationId")
        
        print("   ✅ Single mode fallback works correctly")
    
    def test_real_world_scenario(self):
        """Test real-world scenario from user logs"""
        print("\n📋 Test: Real-world scenario")
        print("   Scenario:")
        print("   - MeshCore DM arrives: from=0x143bcd7f")
        print("   - Network tracked: meshcore")
        print("   - Response generated: weather data")
        print("   - Expected: Response sent via MeshCore")
        
        from handlers.message_sender import MessageSender
        from dual_interface_manager import NetworkSource
        
        # Mock dependencies
        interface = MagicMock()
        node_manager = MagicMock()
        node_manager.get_node_name = MagicMock(return_value="Node-143bcd7f")
        
        dual_interface_manager = MagicMock()
        dual_interface_manager.is_dual_mode = MagicMock(return_value=True)
        dual_interface_manager.send_message = MagicMock(return_value=True)
        
        # Create MessageSender with dual_interface (THE FIX)
        sender = MessageSender(interface, node_manager, dual_interface_manager)
        
        # Simulate network tracking (done by main_bot.py)
        sender_id = 0x143bcd7f
        sender.set_sender_network(sender_id, NetworkSource.MESHCORE)
        print(f"   Network tracked: 0x{sender_id:08x} → MESHCORE")
        
        # Simulate response sending
        response = "📍 Paris, France\nNow: 🌧️ 8°C 14km/h 0.3mm 93%"
        sender.send_single(response, sender_id, "Node-143bcd7f")
        
        # Verify dual_interface.send_message was called
        self.assertTrue(dual_interface_manager.send_message.called,
                       "❌ Response should be sent via dual_interface")
        
        # Verify correct network (MESHCORE, not Meshtastic)
        call_args = dual_interface_manager.send_message.call_args
        network_used = call_args[0][2]
        self.assertEqual(network_used, NetworkSource.MESHCORE,
                        "❌ Response should be sent via MESHCORE, not Meshtastic")
        
        print(f"   ✅ Response sent via {network_used}")
        print("   ✅ Client will receive response")


def run_tests():
    """Run all tests"""
    print("="*70)
    print("MESHCORE RESPONSE ROUTING - TEST SUITE")
    print("="*70)
    print()
    print("Issue: MeshCore DM processed but response sent via wrong interface")
    print("Fix: Pass dual_interface_manager through initialization chain")
    print()
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshCoreResponseRouting)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print()
        print("✅ ALL TESTS PASSED")
        print()
        print("KEY CHANGES VALIDATED:")
        print("  1. ✅ MessageSender receives dual_interface_manager")
        print("  2. ✅ Dual mode routing activated correctly")
        print("  3. ✅ Responses routed to correct network (MESHCORE)")
        print("  4. ✅ Single mode fallback still works")
        print()
        print("EXPECTED BEHAVIOR:")
        print("  Before fix:")
        print("    [DEBUG] Interface: SerialInterface (Meshtastic)")
        print("    ❌ Client doesn't receive response")
        print()
        print("  After fix:")
        print("    [DEBUG] [DUAL MODE] Routing reply to meshcore network")
        print("    [INFO] ✅ Message envoyé via meshcore → Node-143bcd7f")
        print("    ✅ Client receives response")
        return 0
    else:
        print()
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_tests())
