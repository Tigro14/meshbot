#!/usr/bin/env python3
"""
Test to verify /echo command works on MeshCore public channel (broadcast)

This test validates that:
1. /echo sent as BROADCAST on public channel works in companion mode
2. /echo sent as DM is blocked in companion mode (expected behavior)
3. Broadcast filtering happens BEFORE companion mode filtering
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

class TestEchoPublicChannelMeshCore(unittest.TestCase):
    """Test /echo command on MeshCore public channel"""
    
    def setUp(self):
        """Setup test environment"""
        self.mock_interface = Mock()
        self.mock_interface.localNode = Mock()
        self.mock_interface.localNode.nodeNum = 0x12345678
        
    def test_echo_broadcast_in_companion_mode(self):
        """Test /echo as BROADCAST in companion mode - SHOULD WORK"""
        from handlers.message_router import MessageRouter
        from handlers.message_sender import MessageSender
        
        # Mock dependencies
        mock_llama = Mock()
        mock_esphome = Mock()
        mock_remote = Mock()
        mock_node_mgr = Mock()
        mock_node_mgr.get_node_name.return_value = "TestUser"
        mock_context = Mock()
        mock_traffic = Mock()
        
        # Create router in companion mode
        router = MessageRouter(
            llama_client=mock_llama,
            esphome_client=mock_esphome,
            remote_nodes_client=mock_remote,
            node_manager=mock_node_mgr,
            context_manager=mock_context,
            interface=self.mock_interface,
            traffic_monitor=mock_traffic,
            companion_mode=True  # MeshCore companion mode
        )
        
        # Mock utility handler handle_echo
        router.utility_handler.handle_echo = Mock()
        
        # Create BROADCAST packet (public channel)
        packet = {
            'from': 0xABCDEF01,
            'to': 0xFFFFFFFF,  # BROADCAST
            '_meshcore_dm': False  # NOT a DM
        }
        decoded = {'portnum': 'TEXT_MESSAGE_APP'}
        message = '/echo Hello mesh!'
        
        # Process message
        router.process_text_message(packet, decoded, message)
        
        # Verify handle_echo was called (broadcast commands bypass companion filtering)
        router.utility_handler.handle_echo.assert_called_once()
        call_args = router.utility_handler.handle_echo.call_args
        self.assertEqual(call_args[0][0], message)
        self.assertEqual(call_args[0][1], 0xABCDEF01)
        
        print("✅ /echo BROADCAST works in companion mode (as expected)")
    
    def test_echo_dm_in_companion_mode(self):
        """Test /echo as DM in companion mode - SHOULD BE BLOCKED"""
        from handlers.message_router import MessageRouter
        
        # Mock dependencies
        mock_llama = Mock()
        mock_esphome = Mock()
        mock_remote = Mock()
        mock_node_mgr = Mock()
        mock_node_mgr.get_node_name.return_value = "TestUser"
        mock_context = Mock()
        mock_traffic = Mock()
        
        # Create router in companion mode
        router = MessageRouter(
            llama_client=mock_llama,
            esphome_client=mock_esphome,
            remote_nodes_client=mock_remote,
            node_manager=mock_node_mgr,
            context_manager=mock_context,
            interface=self.mock_interface,
            traffic_monitor=mock_traffic,
            companion_mode=True  # MeshCore companion mode
        )
        
        # Mock sender to capture the "not supported" message
        router.sender.send_single = Mock()
        router.utility_handler.handle_echo = Mock()
        
        # Create DM packet (direct message)
        packet = {
            'from': 0xABCDEF01,
            'to': 0x12345678,  # Direct to our node
            '_meshcore_dm': False
        }
        decoded = {'portnum': 'TEXT_MESSAGE_APP'}
        message = '/echo Hello DM'
        
        # Process message
        router.process_text_message(packet, decoded, message)
        
        # Verify handle_echo was NOT called (filtered by companion mode)
        router.utility_handler.handle_echo.assert_not_called()
        
        # Verify "not supported" message was sent
        router.sender.send_single.assert_called()
        error_msg = router.sender.send_single.call_args[0][0]
        self.assertIn("non supportée", error_msg.lower())
        
        print("✅ /echo DM blocked in companion mode (as expected)")
    
    def test_echo_broadcast_not_in_companion_commands(self):
        """Verify /echo is NOT in companion_commands list"""
        from handlers.message_router import MessageRouter
        
        # Create minimal router
        router = MessageRouter(
            llama_client=Mock(),
            esphome_client=Mock(),
            remote_nodes_client=Mock(),
            node_manager=Mock(),
            context_manager=Mock(),
            interface=self.mock_interface,
            companion_mode=True
        )
        
        # Verify /echo is not in companion_commands
        self.assertNotIn('/echo', router.companion_commands)
        
        print("✅ /echo is NOT in companion_commands (by design)")
        print("   This is OK because broadcasts bypass companion filtering")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TEST: /echo Command on MeshCore Public Channel")
    print("="*70 + "\n")
    
    print("Testing that /echo works for BROADCASTS but not DMs in companion mode")
    print("-" * 70 + "\n")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEchoPublicChannelMeshCore)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        print("\nConclusion:")
        print("  ✅ /echo on PUBLIC CHANNEL (broadcast) works in companion mode")
        print("  ✅ /echo as DM is blocked in companion mode (expected)")
        print("  ✅ Broadcast commands bypass companion filtering (by design)")
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    print("="*70 + "\n")
