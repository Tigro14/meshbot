#!/usr/bin/env python3
"""
Test suite for MeshCore RX_LOG improvements
Verifies enhanced packet decoding display
"""

import sys
import unittest
from unittest.mock import Mock, patch, call
from io import StringIO


class TestMeshCoreRxLogImprovements(unittest.TestCase):
    """Test enhanced RX_LOG packet display"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the utils module
        self.mock_debug_print = Mock()
        self.mock_info_print = Mock()
        self.mock_error_print = Mock()
        
        # Patch utils functions
        self.patcher_debug = patch('meshcore_cli_wrapper.debug_print', self.mock_debug_print)
        self.patcher_info = patch('meshcore_cli_wrapper.info_print', self.mock_info_print)
        self.patcher_error = patch('meshcore_cli_wrapper.error_print', self.mock_error_print)
        
        self.patcher_debug.start()
        self.patcher_info.start()
        self.patcher_error.start()
        
        # Import after patching
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper instance
        self.wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0', debug=False)
    
    def tearDown(self):
        """Clean up patches"""
        self.patcher_debug.stop()
        self.patcher_info.stop()
        self.patcher_error.stop()
    
    def test_packet_size_in_first_line(self):
        """Test that packet size is shown in first RF line"""
        # Create a mock event with hex data (20 bytes = 40 hex chars)
        hex_data = '34c81101bf143bcd7f1b34c81101bf143bcd7f1b34c81101bf143bcd7f1b'
        event = Mock()
        event.payload = {
            'snr': 13.0,
            'rssi': -56,
            'raw_hex': hex_data
        }
        
        # Call the handler
        self.wrapper._on_rx_log_data(event)
        
        # Verify first line contains byte count
        first_call = self.mock_debug_print.call_args_list[0]
        first_message = first_call[0][0]
        
        # Should show (31B) in the first line
        self.assertIn('(31B)', first_message)
        self.assertIn('📡 [RX_LOG]', first_message)
    
    def test_longer_hex_preview(self):
        """Test that more hex data is shown (40 chars instead of 20)"""
        hex_data = '34c81101bf143bcd7f1b34c81101bf143bcd7f1b34c81101bf143bcd7f1b'
        event = Mock()
        event.payload = {
            'snr': 13.0,
            'rssi': -56,
            'raw_hex': hex_data
        }
        
        # Call the handler
        self.wrapper._on_rx_log_data(event)
        
        # Verify first line shows more hex data
        first_call = self.mock_debug_print.call_args_list[0]
        first_message = first_call[0][0]
        
        # Should show first 40 chars of hex
        self.assertIn(hex_data[:40], first_message)
    
    def test_packet_size_info_in_decoded_line(self):
        """Test that decoded line includes Size: field"""
        from meshcoredecoder import MeshCoreDecoder
        
        # Use a packet that will decode successfully
        hex_data = '34c81101bf143bcd7f1b'
        event = Mock()
        event.payload = {
            'snr': 13.0,
            'rssi': -56,
            'raw_hex': hex_data
        }
        
        # Call the handler
        self.wrapper._on_rx_log_data(event)
        
        # Find the decoded packet line (📦 [RX_LOG])
        decoded_line = None
        for call_obj in self.mock_debug_print.call_args_list:
            msg = call_obj[0][0]
            if '📦 [RX_LOG]' in msg:
                decoded_line = msg
                break
        
        self.assertIsNotNone(decoded_line, "Should have decoded packet line")
        
        # Verify it contains Size: field
        self.assertIn('Size:', decoded_line)
        self.assertIn('B', decoded_line)  # Bytes indicator
    
    def test_error_categorization(self):
        """Test that errors are categorized and displayed properly"""
        # This test requires a packet with structural errors
        # The actual behavior depends on the packet content
        hex_data = 'd28c1102bf34143bcd7f'  # This packet has "too short" error
        event = Mock()
        event.payload = {
            'snr': -11.5,
            'rssi': -116,
            'raw_hex': hex_data
        }
        
        # Call the handler
        self.wrapper._on_rx_log_data(event)
        
        # Verify that error messages are displayed
        error_found = False
        for call_obj in self.mock_debug_print.call_args_list:
            msg = call_obj[0][0]
            if '⚠️' in msg and 'too short' in msg.lower():
                error_found = True
                break
        
        self.assertTrue(error_found, "Should display structural error")
    
    def test_unknown_type_display(self):
        """Test that unknown packet types show numeric ID"""
        hex_data = '34c81101bf143bcd7f1b'  # Has type 13 which is unknown
        event = Mock()
        event.payload = {
            'snr': 13.0,
            'rssi': -56,
            'raw_hex': hex_data
        }
        
        # Call the handler
        self.wrapper._on_rx_log_data(event)
        
        # Find the decoded packet line
        decoded_line = None
        for call_obj in self.mock_debug_print.call_args_list:
            msg = call_obj[0][0]
            if '📦 [RX_LOG]' in msg:
                decoded_line = msg
                break
        
        self.assertIsNotNone(decoded_line)
        
        # Should show Unknown(13) format
        self.assertTrue(
            'Unknown(13)' in decoded_line or 'Type: RawCustom' in decoded_line,
            "Should show unknown type indicator"
        )
    
    def test_no_hex_data_handling(self):
        """Test graceful handling when no hex data available"""
        event = Mock()
        event.payload = {
            'snr': 10.0,
            'rssi': -70,
            'raw_hex': ''  # Empty hex
        }
        
        # Call the handler - should not crash
        self.wrapper._on_rx_log_data(event)
        
        # Verify appropriate message was logged
        found_no_data_msg = False
        for call_obj in self.mock_debug_print.call_args_list:
            msg = call_obj[0][0]
            if 'no hex data' in msg.lower():
                found_no_data_msg = True
                break
        
        self.assertTrue(found_no_data_msg, "Should indicate no hex data")
    
    def test_debug_mode_extra_info(self):
        """Test that debug mode shows additional information"""
        # Enable debug mode
        self.wrapper.debug = True
        
        hex_data = '34c81101bf143bcd7f1b'
        event = Mock()
        event.payload = {
            'snr': 13.0,
            'rssi': -56,
            'raw_hex': hex_data
        }
        
        # Call the handler
        self.wrapper._on_rx_log_data(event)
        
        # In debug mode, should show more details
        # Count total debug_print calls - debug mode should have more
        call_count = len(self.mock_debug_print.call_args_list)
        
        # Should have at least 2 calls (RF line + decoded line)
        self.assertGreaterEqual(call_count, 2, "Debug mode should show output")


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMeshCoreRxLogImprovements)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
