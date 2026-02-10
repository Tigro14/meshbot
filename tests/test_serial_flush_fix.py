"""
Test that serial.flush() is called after write operations in MeshCoreSerialInterface.

This is CRITICAL for ensuring broadcast messages are actually transmitted to hardware
and not stuck in OS buffers.
"""

import unittest
from unittest.mock import Mock, MagicMock, call
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from meshcore_serial_interface import MeshCoreSerialInterface


class TestSerialFlushFix(unittest.TestCase):
    """Test that serial flush is called after write operations"""
    
    def setUp(self):
        """Set up mock serial interface"""
        # Create interface without actually opening serial port
        self.interface = MeshCoreSerialInterface('/dev/null', enable_read_loop=False)
        
        # Mock the serial object
        self.interface.serial = Mock()
        self.interface.serial.is_open = True
        self.interface.serial.write = Mock(return_value=10)
        self.interface.serial.flush = Mock()
    
    def test_broadcast_calls_flush_after_write(self):
        """Test that broadcast (0xFFFFFFFF) calls flush() after write()"""
        # Send a broadcast message
        result = self.interface.sendText("Test broadcast", destinationId=0xFFFFFFFF, channelIndex=0)
        
        # Verify success
        self.assertTrue(result, "sendText should return True for successful send")
        
        # Verify write was called
        self.interface.serial.write.assert_called_once()
        
        # Verify flush was called AFTER write
        self.interface.serial.flush.assert_called_once()
        
        # Verify call order: write BEFORE flush
        calls = self.interface.serial.method_calls
        write_call_index = None
        flush_call_index = None
        
        for i, call_obj in enumerate(calls):
            if call_obj[0] == 'write':
                write_call_index = i
            elif call_obj[0] == 'flush':
                flush_call_index = i
        
        self.assertIsNotNone(write_call_index, "write() should have been called")
        self.assertIsNotNone(flush_call_index, "flush() should have been called")
        self.assertLess(write_call_index, flush_call_index, "write() must be called BEFORE flush()")
    
    def test_broadcast_none_destination_calls_flush(self):
        """Test that broadcast (None destination) also calls flush()"""
        # Send broadcast with None destination
        result = self.interface.sendText("Test broadcast", destinationId=None, channelIndex=0)
        
        # Verify success
        self.assertTrue(result, "sendText should return True")
        
        # Verify flush was called
        self.interface.serial.flush.assert_called_once()
    
    def test_dm_calls_flush_after_write(self):
        """Test that DM messages also call flush() after write()"""
        # Send a DM message
        result = self.interface.sendText("Test DM", destinationId=0x12345678, channelIndex=0)
        
        # Verify success
        self.assertTrue(result, "sendText should return True for DM")
        
        # Verify write was called
        self.interface.serial.write.assert_called_once()
        
        # Verify flush was called
        self.interface.serial.flush.assert_called_once()
    
    def test_flush_not_called_when_serial_closed(self):
        """Test that flush is not called when serial port is closed"""
        # Close the serial port
        self.interface.serial.is_open = False
        
        # Try to send (should fail early)
        result = self.interface.sendText("Test", destinationId=0xFFFFFFFF, channelIndex=0)
        
        # Verify failure
        self.assertFalse(result, "sendText should return False when serial closed")
        
        # Verify flush was NOT called
        self.interface.serial.flush.assert_not_called()
    
    def test_flush_ensures_immediate_transmission(self):
        """
        Test documentation: Verify that flush() ensures immediate transmission.
        
        This is a documentation test confirming the fix for the issue where
        broadcast messages appeared to be sent (logs showed success) but weren't
        actually transmitted because data stayed in OS buffers.
        """
        # Send broadcast
        self.interface.sendText("Test", destinationId=0xFFFFFFFF, channelIndex=0)
        
        # The fix: flush() is called
        self.interface.serial.flush.assert_called_once()
        
        # This ensures:
        # 1. Data is not buffered in OS
        # 2. Immediate transmission to hardware
        # 3. Users receive messages on public channel
        # 4. No mysterious "sent but not received" issues


if __name__ == '__main__':
    unittest.main()
