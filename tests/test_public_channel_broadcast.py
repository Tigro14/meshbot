#!/usr/bin/env python3
"""
Test: Verify Public Channel Broadcast Support

This test verifies that MeshCoreSerialInterface correctly supports
sending messages to the public channel via broadcast.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock, patch
import struct


class TestPublicChannelBroadcast(unittest.TestCase):
    """Test that public channel broadcasts work correctly"""
    
    def test_meshcore_serial_supports_broadcast(self):
        """Test that MeshCoreSerialInterface supports broadcast to public channel"""
        from meshcore_serial_interface import MeshCoreSerialInterface, CMD_SEND_CHANNEL_TXT_MSG
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = Mock()
        interface.serial.is_open = True
        
        # Track what was written
        written_data = []
        interface.serial.write = lambda data: written_data.append(data)
        
        # Send broadcast on public channel
        result = interface.sendText(
            message="Test broadcast",
            destinationId=0xFFFFFFFF,  # Broadcast
            channelIndex=0             # Public channel
        )
        
        # Verify success
        self.assertTrue(result, "Broadcast should succeed")
        
        # Verify binary packet was written
        self.assertEqual(len(written_data), 1, "Should write one packet")
        packet = written_data[0]
        
        # Verify packet structure
        self.assertEqual(packet[0], 0x3C, "Start marker should be 0x3C")
        
        # Parse length
        length = struct.unpack('<H', packet[1:3])[0]
        self.assertGreater(length, 0, "Length should be > 0")
        
        # Parse command
        command = packet[3]
        self.assertEqual(command, CMD_SEND_CHANNEL_TXT_MSG, 
                        f"Command should be CMD_SEND_CHANNEL_TXT_MSG (0x03), got {command}")
        
        # Parse channel
        channel = packet[4]
        self.assertEqual(channel, 0, "Channel should be 0 (public)")
        
        # Parse message
        message = packet[5:].decode('utf-8')
        self.assertEqual(message, "Test broadcast", "Message should match")
        
        print("✅ Test passed: MeshCoreSerialInterface supports public channel broadcast")
    
    def test_broadcast_with_none_destination(self):
        """Test that destinationId=None is also treated as broadcast"""
        from meshcore_serial_interface import MeshCoreSerialInterface, CMD_SEND_CHANNEL_TXT_MSG
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = Mock()
        interface.serial.is_open = True
        
        # Track what was written
        written_data = []
        interface.serial.write = lambda data: written_data.append(data)
        
        # Send with None destination (should be broadcast)
        result = interface.sendText(
            message="Test",
            destinationId=None,  # Also means broadcast
            channelIndex=0
        )
        
        # Verify success
        self.assertTrue(result, "Broadcast with None should succeed")
        
        # Verify binary packet (not text)
        packet = written_data[0]
        self.assertEqual(packet[0], 0x3C, "Should use binary format for broadcast")
        self.assertEqual(packet[3], CMD_SEND_CHANNEL_TXT_MSG, "Should use channel message command")
        
        print("✅ Test passed: destinationId=None also triggers broadcast")
    
    def test_dm_uses_text_format(self):
        """Test that DM messages use text format, not binary"""
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = Mock()
        interface.serial.is_open = True
        
        # Track what was written
        written_data = []
        interface.serial.write = lambda data: written_data.append(data)
        
        # Send DM to specific node
        result = interface.sendText(
            message="Private message",
            destinationId=0x12345678,  # Specific node
            channelIndex=0
        )
        
        # Verify success
        self.assertTrue(result, "DM should succeed")
        
        # Verify text format (not binary)
        data = written_data[0]
        text = data.decode('utf-8')
        
        # Should be in format: SEND_DM:12345678:Private message\n
        self.assertTrue(text.startswith('SEND_DM:'), "DM should use text format")
        self.assertIn('12345678', text, "Should include destination ID")
        self.assertIn('Private message', text, "Should include message")
        
        print("✅ Test passed: DM messages use text format")
    
    def test_different_channel_indexes(self):
        """Test that different channel indexes are correctly encoded"""
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = Mock()
        interface.serial.is_open = True
        
        for channel_idx in [0, 1, 2, 5]:
            # Track what was written
            written_data = []
            interface.serial.write = lambda data: written_data.append(data)
            
            # Send broadcast on specific channel
            result = interface.sendText(
                message=f"Test channel {channel_idx}",
                destinationId=0xFFFFFFFF,
                channelIndex=channel_idx
            )
            
            # Verify success
            self.assertTrue(result, f"Broadcast on channel {channel_idx} should succeed")
            
            # Verify channel index in packet
            packet = written_data[0]
            encoded_channel = packet[4]
            self.assertEqual(encoded_channel, channel_idx, 
                           f"Channel index should be {channel_idx}")
        
        print("✅ Test passed: Different channel indexes are correctly encoded")
    
    def test_binary_packet_structure(self):
        """Test complete binary packet structure for public channel"""
        from meshcore_serial_interface import MeshCoreSerialInterface, CMD_SEND_CHANNEL_TXT_MSG
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200)
        interface.serial = Mock()
        interface.serial.is_open = True
        
        # Track what was written
        written_data = []
        interface.serial.write = lambda data: written_data.append(data)
        
        # Send known message
        test_message = "Hello"
        result = interface.sendText(
            message=test_message,
            destinationId=0xFFFFFFFF,
            channelIndex=0
        )
        
        self.assertTrue(result)
        
        # Verify complete packet structure
        packet = written_data[0]
        
        # Expected structure:
        # 0x3C + length(2B LE) + CMD(1B) + channel(1B) + message(UTF-8)
        # For "Hello": 0x3C + 0x0700 + 0x03 + 0x00 + "Hello"
        
        message_bytes = test_message.encode('utf-8')
        expected_length = 1 + 1 + len(message_bytes)  # CMD + channel + message
        
        self.assertEqual(packet[0], 0x3C)  # Start marker
        actual_length = struct.unpack('<H', packet[1:3])[0]
        self.assertEqual(actual_length, expected_length)  # Length
        self.assertEqual(packet[3], CMD_SEND_CHANNEL_TXT_MSG)  # Command
        self.assertEqual(packet[4], 0)  # Channel 0
        self.assertEqual(packet[5:], message_bytes)  # Message
        
        print("✅ Test passed: Binary packet structure is correct")


if __name__ == '__main__':
    # Run tests with verbose output
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPublicChannelBroadcast)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSummary:")
        print("  - MeshCoreSerialInterface supports broadcast: ✅")
        print("  - destinationId=None treated as broadcast: ✅")
        print("  - DM messages use text format: ✅")
        print("  - Different channel indexes work: ✅")
        print("  - Binary packet structure correct: ✅")
        print()
        print("Conclusion: Public channel broadcast is FULLY SUPPORTED!")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
    
    sys.exit(0 if result.wasSuccessful() else 1)
