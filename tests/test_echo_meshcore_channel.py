#!/usr/bin/env python3
"""
Test pour vérifier que /echo fonctionne avec MeshCore sur canal public (broadcast)
Vérifie que le fix pour destinationId=0xFFFFFFFF + channelIndex=0 fonctionne
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import struct


class TestEchoMeshCoreChannel(unittest.TestCase):
    """Test que la commande /echo fonctionne avec MeshCore sur canal public"""
    
    def setUp(self):
        """Setup test environment"""
        # Mock modules
        self.mock_traffic_monitor = Mock()
        self.mock_node_manager = Mock()
        self.mock_node_manager.get_short_name.return_value = "TestUser"
        
    def test_echo_meshcore_channel_broadcast(self):
        """Test /echo avec MeshCore envoie broadcast sur canal public (channelIndex=0)"""
        # This test verifies that utility_commands.py calls sendText with correct parameters
        # We test the interface directly instead of going through the full import chain
        
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Create mock serial port
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.write = Mock()
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = mock_serial
        interface.running = True
        
        # Simulate what utility_commands.py does:
        # interface.sendText(echo_response, destinationId=0xFFFFFFFF, channelIndex=0)
        result = interface.sendText("TestUser: test broadcast", destinationId=0xFFFFFFFF, channelIndex=0)
        
        # Verify success
        self.assertTrue(result)
        
        # Verify it was sent as a channel broadcast (binary format)
        mock_serial.write.assert_called_once()
        written_data = mock_serial.write.call_args[0][0]
        
        # Should be binary packet, not text
        self.assertEqual(written_data[0], 0x3C, "Should use binary protocol for broadcast")
        
        print("✅ Test MeshCore echo: Broadcast utilise le protocole binaire (CMD_SEND_CHANNEL_TXT_MSG)")

        
    def test_meshcore_sendtext_broadcast_format(self):
        """Test que MeshCoreSerialInterface.sendText() construit correctement le paquet binaire"""
        from meshcore_serial_interface import MeshCoreSerialInterface, CMD_SEND_CHANNEL_TXT_MSG
        
        # Create mock serial port
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.write = Mock()
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = mock_serial
        interface.running = True
        
        # Send broadcast message
        result = interface.sendText("test message", destinationId=0xFFFFFFFF, channelIndex=0)
        
        # Verify success
        self.assertTrue(result)
        
        # Verify serial.write was called
        mock_serial.write.assert_called_once()
        
        # Extract the packet that was written
        written_data = mock_serial.write.call_args[0][0]
        
        # Verify packet structure:
        # - First byte: 0x3C ('<') - start marker for app->radio
        self.assertEqual(written_data[0], 0x3C, "Start marker should be 0x3C")
        
        # - Next 2 bytes: length (little-endian)
        length = struct.unpack('<H', written_data[1:3])[0]
        
        # - Next byte: command code (CMD_SEND_CHANNEL_TXT_MSG = 3)
        command = written_data[3]
        self.assertEqual(command, CMD_SEND_CHANNEL_TXT_MSG, "Command should be CMD_SEND_CHANNEL_TXT_MSG (3)")
        
        # - Next byte: channel index (0 for public)
        channel = written_data[4]
        self.assertEqual(channel, 0, "Channel index should be 0 (public)")
        
        # - Remaining bytes: UTF-8 encoded message
        message_bytes = written_data[5:]
        message_text = message_bytes.decode('utf-8')
        self.assertEqual(message_text, "test message")
        
        # Verify payload length matches
        expected_payload_length = 1 + 1 + len("test message".encode('utf-8'))  # cmd + channel + message
        self.assertEqual(length, expected_payload_length, f"Payload length should be {expected_payload_length}")
        
        print("✅ Test paquet binaire: Structure correcte pour broadcast sur canal public")
        print(f"   - Start marker: 0x{written_data[0]:02x}")
        print(f"   - Length: {length}")
        print(f"   - Command: {command} (CMD_SEND_CHANNEL_TXT_MSG)")
        print(f"   - Channel: {channel} (public)")
        print(f"   - Message: '{message_text}'")
        
    def test_meshcore_sendtext_dm_still_works(self):
        """Test que les DM directs (non-broadcast) fonctionnent toujours"""
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Create mock serial port
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial.write = Mock()
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = mock_serial
        interface.running = True
        
        # Send DM to specific node
        result = interface.sendText("direct message", destinationId=0x12345678, channelIndex=0)
        
        # Verify success
        self.assertTrue(result)
        
        # Verify serial.write was called
        mock_serial.write.assert_called_once()
        
        # Extract what was written (should be text format for DM)
        written_data = mock_serial.write.call_args[0][0]
        written_text = written_data.decode('utf-8')
        
        # Verify it's in DM format (not binary channel format)
        self.assertIn("SEND_DM:", written_text, "DM should use text format")
        self.assertIn("12345678", written_text, "DM should contain destination ID")
        self.assertIn("direct message", written_text, "DM should contain message")
        
        print("✅ Test DM: Format texte préservé pour messages directs")
        print(f"   - Format: {written_text.strip()}")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
