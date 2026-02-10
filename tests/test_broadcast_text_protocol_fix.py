#!/usr/bin/env python3
"""
Test suite for broadcast text protocol fix.

Tests that broadcasts use text protocol (SEND_DM:ffffffff:message)
instead of binary protocol which is not supported by MeshCore devices.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from meshcore_serial_interface import MeshCoreSerialInterface


class TestBroadcastTextProtocolFix(unittest.TestCase):
    """Test that broadcasts use text protocol instead of binary"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock serial port
        self.mock_serial = Mock()
        self.mock_serial.is_open = True
        self.mock_serial.writable = Mock(return_value=True)
        self.mock_serial.in_waiting = 0
        self.mock_serial.write = Mock(return_value=20)  # Mock bytes written
        self.mock_serial.flush = Mock()
        
        # Create interface with mock serial
        self.interface = MeshCoreSerialInterface('/dev/ttyACM1', 115200, enable_read_loop=False)
        self.interface.serial = self.mock_serial
    
    def test_broadcast_uses_text_protocol(self):
        """Test that broadcast uses SEND_DM:ffffffff:message format"""
        message = "cd7f: hello"
        
        # Send broadcast
        result = self.interface.sendText(message, destinationId=0xFFFFFFFF, channelIndex=0)
        
        # Verify success
        self.assertTrue(result)
        
        # Verify write was called
        self.mock_serial.write.assert_called_once()
        
        # Get the actual command sent
        call_args = self.mock_serial.write.call_args[0][0]
        command_sent = call_args.decode('utf-8')
        
        # Verify it's text protocol with broadcast address
        self.assertIn("SEND_DM:ffffffff:", command_sent)
        self.assertIn(message, command_sent)
        self.assertTrue(command_sent.endswith('\n'))
        
        print(f"✅ Broadcast uses text protocol: {repr(command_sent)}")
    
    def test_broadcast_none_destination_uses_text(self):
        """Test that broadcast with None destination also uses text protocol"""
        message = "test broadcast"
        
        # Send broadcast with None
        result = self.interface.sendText(message, destinationId=None, channelIndex=0)
        
        # Verify success
        self.assertTrue(result)
        
        # Verify uses text protocol
        call_args = self.mock_serial.write.call_args[0][0]
        command_sent = call_args.decode('utf-8')
        
        self.assertIn("SEND_DM:ffffffff:", command_sent)
        
        print(f"✅ None destination uses text protocol: {repr(command_sent)}")
    
    def test_flush_called_after_broadcast(self):
        """Test that flush is called after writing broadcast"""
        message = "test"
        
        # Send broadcast
        self.interface.sendText(message, destinationId=0xFFFFFFFF)
        
        # Verify flush was called
        self.mock_serial.flush.assert_called_once()
        
        print("✅ Flush called after broadcast")
    
    def test_dm_still_uses_text_protocol(self):
        """Test that DM messages still use SEND_DM with specific address"""
        message = "direct message"
        dest_id = 0x12345678
        
        # Send DM
        result = self.interface.sendText(message, destinationId=dest_id)
        
        # Verify success
        self.assertTrue(result)
        
        # Get command sent
        call_args = self.mock_serial.write.call_args[0][0]
        command_sent = call_args.decode('utf-8')
        
        # Verify it uses specific destination, not broadcast
        self.assertIn("SEND_DM:12345678:", command_sent)
        self.assertNotIn("ffffffff", command_sent)
        
        print(f"✅ DM uses specific destination: {repr(command_sent)}")
    
    def test_text_protocol_format_correct(self):
        """Test that text protocol format is correct"""
        message = "test message"
        
        # Send broadcast
        self.interface.sendText(message, destinationId=0xFFFFFFFF)
        
        # Get command
        call_args = self.mock_serial.write.call_args[0][0]
        command_sent = call_args.decode('utf-8')
        
        # Verify format: SEND_DM:ffffffff:message\n
        expected = f"SEND_DM:ffffffff:{message}\n"
        self.assertEqual(command_sent, expected)
        
        print(f"✅ Text protocol format correct: {repr(command_sent)}")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("Testing Broadcast Text Protocol Fix")
    print("="*70 + "\n")
    
    # Run tests
    unittest.main(verbosity=2)
