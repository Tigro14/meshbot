#!/usr/bin/env python3
"""
Tests for broadcast diagnostic logging in MeshCore serial interface
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshcore_serial_interface import MeshCoreSerialInterface, CMD_SEND_CHANNEL_TXT_MSG


class TestBroadcastDiagnosticLogging(unittest.TestCase):
    """Test diagnostic logging for broadcast transmission"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.interface = MeshCoreSerialInterface('/dev/ttyUSB0', enable_read_loop=False)
        self.interface.serial = Mock()
        self.interface.serial.is_open = True
        self.interface.serial.writable = Mock(return_value=True)
        self.interface.serial.in_waiting = 0
        self.interface.serial.write = Mock(return_value=17)  # Returns bytes written
        self.interface.serial.flush = Mock()
    
    @patch('meshcore_serial_interface.debug_print')
    @patch('meshcore_serial_interface.info_print')
    def test_diagnostic_logs_port_state(self, mock_info, mock_debug):
        """Test that port state is logged before transmission"""
        result = self.interface.sendText("test", destinationId=0xFFFFFFFF, channelIndex=0)
        
        self.assertTrue(result)
        
        # Check that port state was logged
        debug_calls = [str(call) for call in mock_debug.call_args_list]
        port_state_logged = any('Port state' in call for call in debug_calls)
        self.assertTrue(port_state_logged, "Port state should be logged")
    
    @patch('meshcore_serial_interface.debug_print')
    @patch('meshcore_serial_interface.info_print')
    def test_diagnostic_logs_packet_hex(self, mock_info, mock_debug):
        """Test that packet hex dump is logged"""
        result = self.interface.sendText("test", destinationId=0xFFFFFFFF, channelIndex=0)
        
        self.assertTrue(result)
        
        # Check that packet hex was logged
        debug_calls = [str(call) for call in mock_debug.call_args_list]
        hex_logged = any('Packet hex' in call for call in debug_calls)
        self.assertTrue(hex_logged, "Packet hex should be logged")
    
    @patch('meshcore_serial_interface.debug_print')
    @patch('meshcore_serial_interface.info_print')
    def test_diagnostic_logs_bytes_written(self, mock_info, mock_debug):
        """Test that bytes written count is logged"""
        result = self.interface.sendText("test", destinationId=0xFFFFFFFF, channelIndex=0)
        
        self.assertTrue(result)
        
        # Check that bytes written was logged
        debug_calls = [str(call) for call in mock_debug.call_args_list]
        bytes_logged = any('Bytes written' in call for call in debug_calls)
        self.assertTrue(bytes_logged, "Bytes written should be logged")
    
    @patch('meshcore_serial_interface.debug_print')
    @patch('meshcore_serial_interface.info_print')
    @patch('meshcore_serial_interface.time.sleep')
    def test_diagnostic_checks_device_response(self, mock_sleep, mock_info, mock_debug):
        """Test that device response is checked after transmission"""
        # Simulate device response
        self.interface.serial.in_waiting = 5
        self.interface.serial.read = Mock(return_value=b'\x3E\x03\x00\x00\x06')
        
        result = self.interface.sendText("test", destinationId=0xFFFFFFFF, channelIndex=0)
        
        self.assertTrue(result)
        
        # Check that device response was logged
        debug_calls = [str(call) for call in mock_debug.call_args_list]
        response_logged = any('Device response' in call for call in debug_calls)
        self.assertTrue(response_logged, "Device response should be logged")
    
    @patch('meshcore_serial_interface.debug_print')
    @patch('meshcore_serial_interface.info_print')
    def test_diagnostic_logs_command_and_channel(self, mock_info, mock_debug):
        """Test that command code and channel are logged"""
        result = self.interface.sendText("hello", destinationId=0xFFFFFFFF, channelIndex=0)
        
        self.assertTrue(result)
        
        # Check that command and channel were logged
        debug_calls = [str(call) for call in mock_debug.call_args_list]
        command_logged = any(f'CMD_SEND_CHANNEL_TXT_MSG' in call for call in debug_calls)
        channel_logged = any('Channel:' in call for call in debug_calls)
        
        self.assertTrue(command_logged, "Command should be logged")
        self.assertTrue(channel_logged, "Channel should be logged")


if __name__ == '__main__':
    unittest.main()
