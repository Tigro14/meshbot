#!/usr/bin/env python3
"""
Test pour vérifier que /echo fonctionne avec MeshCore
Vérifie que le fix pour destinationId=0xFFFFFFFF fonctionne
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch, call


class TestEchoMeshCoreFix(unittest.TestCase):
    """Test que la commande /echo fonctionne avec MeshCore"""
    
    def setUp(self):
        """Setup test environment"""
        # Mock modules
        self.mock_traffic_monitor = Mock()
        self.mock_node_manager = Mock()
        self.mock_node_manager.get_short_name.return_value = "TestUser"
        
    def test_echo_with_meshtastic_interface(self):
        """Test /echo avec interface Meshtastic (broadcast sans destination)"""
        from handlers.command_handlers.utility_commands import UtilityCommands
        from handlers.message_sender import MessageSender
        
        # Create mock Meshtastic interface
        mock_interface = Mock()
        mock_interface.__class__.__name__ = 'SerialInterface'  # Meshtastic
        mock_interface.localNode = Mock()
        mock_interface.localNode.shortName = "TestBot"
        mock_interface.sendText = Mock()
        
        # Create mock sender
        mock_sender = Mock(spec=MessageSender)
        mock_sender._get_interface.return_value = mock_interface
        mock_sender.get_short_name.return_value = "TestUser"
        mock_sender.send_single = Mock()
        mock_sender.log_conversation = Mock()
        mock_sender._last_echo_id = None
        
        # Create utility handler
        util_handler = UtilityCommands(
            esphome_client=None,
            traffic_monitor=self.mock_traffic_monitor,
            sender=mock_sender,
            node_manager=self.mock_node_manager,
            blitz_monitor=None,
            vigilance_monitor=None
        )
        
        # Call handle_echo
        packet = {'from': 0x12345678, 'to': 0xFFFFFFFF}
        util_handler.handle_echo("/echo test message", 0x12345678, "TestUser", packet)
        
        # Verify sendText was called WITHOUT destinationId (Meshtastic style)
        mock_interface.sendText.assert_called_once()
        call_args = mock_interface.sendText.call_args
        
        # Check that text and channelIndex were passed
        self.assertEqual(len(call_args[0]), 1)  # Only one positional arg (text)
        self.assertIn("test message", call_args[0][0])
        self.assertEqual(call_args[1].get('channelIndex'), 0)  # Public channel
        
        print("✅ Test Meshtastic: sendText appelé avec channelIndex=0 (canal public)")
    
    def test_echo_with_meshcore_interface(self):
        """Test /echo avec interface MeshCore (broadcast avec destinationId=0xFFFFFFFF)"""
        from handlers.command_handlers.utility_commands import UtilityCommands
        from handlers.message_sender import MessageSender
        
        # Create mock MeshCore interface
        mock_interface = Mock()
        mock_interface.__class__.__name__ = 'MeshCoreCLIWrapper'  # MeshCore
        mock_interface.localNode = Mock()
        mock_interface.localNode.nodeNum = 0xFFFFFFFE
        mock_interface.sendText = Mock()
        
        # Create mock sender
        mock_sender = Mock(spec=MessageSender)
        mock_sender._get_interface.return_value = mock_interface
        mock_sender.get_short_name.return_value = "TestUser"
        mock_sender.send_single = Mock()
        mock_sender.log_conversation = Mock()
        mock_sender._last_echo_id = None
        
        # Create utility handler
        util_handler = UtilityCommands(
            esphome_client=None,
            traffic_monitor=self.mock_traffic_monitor,
            sender=mock_sender,
            node_manager=self.mock_node_manager,
            blitz_monitor=None,
            vigilance_monitor=None
        )
        
        # Call handle_echo
        packet = {'from': 0x12345678, 'to': 0xFFFFFFFE}
        util_handler.handle_echo("/echo test message", 0x12345678, "TestUser", packet)
        
        # Verify sendText was called WITH destinationId=0xFFFFFFFF (MeshCore style)
        mock_interface.sendText.assert_called_once()
        call_args = mock_interface.sendText.call_args
        
        # Check that text, destinationId and channelIndex were passed
        self.assertEqual(len(call_args[0]), 1)  # text as positional
        self.assertIn("test message", call_args[0][0])
        self.assertEqual(call_args[1]['destinationId'], 0xFFFFFFFF)  # Broadcast
        self.assertEqual(call_args[1].get('channelIndex'), 0)  # Public channel
        
        print("✅ Test MeshCore: sendText appelé avec destinationId=0xFFFFFFFF, channelIndex=0")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("TEST: Fix /echo pour MeshCore")
    print("="*60 + "\n")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEchoMeshCoreFix)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("\nLe fix permet maintenant:")
        print("  • Meshtastic: sendText(text, channelIndex=0) - broadcast sur canal public")
        print("  • MeshCore: sendText(text, destinationId=0xFFFFFFFF, channelIndex=0) - broadcast sur canal public")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
    print("="*60 + "\n")
