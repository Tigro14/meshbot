#!/usr/bin/env python3
"""
Test: MeshCore DM Command Processing

PROBLEM:
- MeshCore DM arrives with correct sender_id (0x143bcd7f)
- Message logged: "MESSAGE REÇU de Node-143bcd7f: '/power'"
- But command NOT processed (filtered out)

ROOT CAUSE:
- handlers/message_router.py line 80: is_for_me = (to_id == my_id)
- MeshCore DM has to_id=0xfffffffe (bot's MeshCore address)
- my_id from Meshtastic localNode (different)
- Result: is_for_me = False → message filtered at line 124

SOLUTION:
- Check _meshcore_dm flag (set by wrapper)
- is_for_me = is_meshcore_dm OR (to_id == my_id)
- MeshCore DMs always "for us"

This test validates the fix works correctly.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


class TestMeshCoreDMCommandProcessing(unittest.TestCase):
    """Test MeshCore DM command processing"""
    
    def setUp(self):
        """Set up test fixtures"""
        print("\n" + "="*70)
        print("TEST: MeshCore DM Command Processing")
        print("="*70)
    
    def test_meshcore_dm_recognized_as_for_me(self):
        """Test that MeshCore DMs are recognized as 'for me' even with different to_id"""
        print("\n📋 Test: MeshCore DM recognized as 'for me'")
        
        from handlers.message_router import MessageRouter
        
        # Mock dependencies
        llama_client = MagicMock()
        esphome_client = MagicMock()
        remote_nodes_client = MagicMock()
        node_manager = MagicMock()
        context_manager = MagicMock()
        interface = MagicMock()
        
        # Setup interface with localNode
        interface.localNode = MagicMock()
        interface.localNode.nodeNum = 0x12345678  # Meshtastic node ID
        
        node_manager.get_node_name = MagicMock(return_value="Node-143bcd7f")
        
        # Create router
        router = MessageRouter(
            llama_client, esphome_client, remote_nodes_client,
            node_manager, context_manager, interface
        )
        
        # Mock the utility handler
        router.utility_handler.handle_power = MagicMock()
        
        # Test 1: Regular message (NOT MeshCore DM) - should be filtered if to_id != my_id
        print("   Test 1: Regular message (not MeshCore DM)")
        packet = {
            'from': 0x143bcd7f,
            'to': 0xfffffffe,  # Different from my_id
            '_meshcore_dm': False  # NOT a MeshCore DM
        }
        decoded = {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'/power'}
        message = '/power'
        
        router.process_text_message(packet, decoded, message)
        
        # Should NOT be processed (to_id != my_id and not MeshCore DM)
        self.assertFalse(router.utility_handler.handle_power.called,
                        "❌ Regular message should be filtered (to_id != my_id)")
        print("   ✅ Regular message correctly filtered")
        
        # Reset mock
        router.utility_handler.handle_power.reset_mock()
        
        # Test 2: MeshCore DM - should be processed even if to_id != my_id
        print("   Test 2: MeshCore DM (with _meshcore_dm flag)")
        packet = {
            'from': 0x143bcd7f,
            'to': 0xfffffffe,  # Different from my_id
            '_meshcore_dm': True  # MeshCore DM marker
        }
        decoded = {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'/power'}
        message = '/power'
        
        router.process_text_message(packet, decoded, message)
        
        # Should be processed (MeshCore DM is always "for us")
        self.assertTrue(router.utility_handler.handle_power.called,
                       "❌ MeshCore DM should be processed (marked with _meshcore_dm flag)")
        print("   ✅ MeshCore DM correctly processed")
    
    def test_meshcore_dm_with_matching_to_id(self):
        """Test MeshCore DM when to_id happens to match my_id"""
        print("\n📋 Test: MeshCore DM with matching to_id")
        
        from handlers.message_router import MessageRouter
        
        # Mock dependencies
        llama_client = MagicMock()
        esphome_client = MagicMock()
        remote_nodes_client = MagicMock()
        node_manager = MagicMock()
        context_manager = MagicMock()
        interface = MagicMock()
        
        # Setup interface with localNode
        interface.localNode = MagicMock()
        interface.localNode.nodeNum = 0xfffffffe  # Same as to_id
        
        node_manager.get_node_name = MagicMock(return_value="Node-143bcd7f")
        
        # Create router
        router = MessageRouter(
            llama_client, esphome_client, remote_nodes_client,
            node_manager, context_manager, interface
        )
        
        # Mock the utility handler
        router.utility_handler.handle_power = MagicMock()
        
        # MeshCore DM with matching to_id
        packet = {
            'from': 0x143bcd7f,
            'to': 0xfffffffe,  # Matches my_id
            '_meshcore_dm': True
        }
        decoded = {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'/power'}
        message = '/power'
        
        router.process_text_message(packet, decoded, message)
        
        # Should be processed (both conditions true)
        self.assertTrue(router.utility_handler.handle_power.called,
                       "❌ MeshCore DM should be processed")
        print("   ✅ MeshCore DM processed when to_id matches")
    
    def test_real_world_scenario(self):
        """Test real-world scenario from user logs"""
        print("\n📋 Test: Real-world scenario from logs")
        print("   Scenario:")
        print("   - MeshCore DM: from=0x143bcd7f, to=0xfffffffe")
        print("   - Message: '/power'")
        print("   - Expected: Command processed")
        
        from handlers.message_router import MessageRouter
        
        # Mock dependencies (realistic setup)
        llama_client = MagicMock()
        esphome_client = MagicMock()
        remote_nodes_client = MagicMock()
        node_manager = MagicMock()
        context_manager = MagicMock()
        interface = MagicMock()
        
        # Setup: Meshtastic node ID different from MeshCore address
        interface.localNode = MagicMock()
        interface.localNode.nodeNum = 0x87654321  # Different Meshtastic ID
        
        node_manager.get_node_name = MagicMock(return_value="Node-143bcd7f")
        
        # Create router
        router = MessageRouter(
            llama_client, esphome_client, remote_nodes_client,
            node_manager, context_manager, interface
        )
        
        # Mock the utility handler
        router.utility_handler.handle_power = MagicMock()
        
        # Real packet from logs
        packet = {
            'from': 0x143bcd7f,
            'to': 0xfffffffe,  # Bot's MeshCore address
            '_meshcore_dm': True,  # Marked by wrapper
            'decoded': {
                'portnum': 'TEXT_MESSAGE_APP',
                'payload': b'/power'
            }
        }
        decoded = packet['decoded']
        message = '/power'
        
        print(f"   Processing: from=0x{packet['from']:08x}, to=0x{packet['to']:08x}")
        print(f"   Message: {message}")
        print(f"   _meshcore_dm: {packet['_meshcore_dm']}")
        
        # Process the message
        router.process_text_message(packet, decoded, message)
        
        # Verify command was processed
        self.assertTrue(router.utility_handler.handle_power.called,
                       "❌ /power command should be processed")
        print("   ✅ Command processed successfully")
        
        # Verify called with correct parameters
        call_args = router.utility_handler.handle_power.call_args
        sender_id = call_args[0][0]
        sender_info = call_args[0][1]
        
        self.assertEqual(sender_id, 0x143bcd7f,
                        "❌ Wrong sender_id")
        self.assertEqual(sender_info, "Node-143bcd7f",
                        "❌ Wrong sender_info")
        print(f"   ✅ Correct parameters: sender_id=0x{sender_id:08x}, sender_info={sender_info}")


def run_tests():
    """Run all tests"""
    print("="*70)
    print("MESHCORE DM COMMAND PROCESSING - TEST SUITE")
    print("="*70)
    print()
    print("Issue: MeshCore DM logged but command not processed")
    print("Fix: Recognize _meshcore_dm flag as 'for us'")
    print()
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshCoreDMCommandProcessing)
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
        print("  1. ✅ MeshCore DMs recognized as 'for me'")
        print("  2. ✅ Commands processed even with different to_id")
        print("  3. ✅ Regular messages still filtered correctly")
        print("  4. ✅ Real-world scenario works")
        print()
        print("EXPECTED BEHAVIOR:")
        print("  Before fix:")
        print("    ✅ Message logged: 'MESSAGE REÇU de ...'")
        print("    ❌ Command NOT processed (filtered)")
        print()
        print("  After fix:")
        print("    ✅ Message logged: 'MESSAGE REÇU de ...'")
        print("    ✅ Command processed and response sent")
        return 0
    else:
        print()
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
