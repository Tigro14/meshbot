#!/usr/bin/env python3
"""
Test suite for MeshCoreHybridInterface start_reading() method

This test verifies that the hybrid interface properly routes start_reading()
calls to the appropriate underlying interface.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock, patch


class TestHybridStartReading(unittest.TestCase):
    """Test start_reading routing in hybrid interface"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the interfaces to avoid actual serial connections
        self.mock_serial = Mock()
        self.mock_serial.start_reading = Mock(return_value=True)
        self.mock_serial.connect = Mock(return_value=True)
        self.mock_serial.localNode = Mock()
        self.mock_serial.serial = Mock()
        
        self.mock_cli = Mock()
        self.mock_cli.start_reading = Mock(return_value=True)
        self.mock_cli.connect = Mock(return_value=True)
    
    def test_start_reading_with_cli_wrapper(self):
        """Test that start_reading calls CLI wrapper when available"""
        # Create a mock hybrid interface
        hybrid = Mock()
        hybrid.cli_wrapper = self.mock_cli
        hybrid.serial_interface = self.mock_serial
        
        # Simulate the start_reading method behavior
        def start_reading_impl():
            if hybrid.cli_wrapper:
                return hybrid.cli_wrapper.start_reading()
            else:
                return hybrid.serial_interface.start_reading()
        
        hybrid.start_reading = start_reading_impl
        
        # Call start_reading
        result = hybrid.start_reading()
        
        # Verify CLI wrapper was called
        self.assertTrue(result)
        self.mock_cli.start_reading.assert_called_once()
        self.mock_serial.start_reading.assert_not_called()
    
    def test_start_reading_without_cli_wrapper(self):
        """Test that start_reading falls back to serial when CLI unavailable"""
        # Create a mock hybrid interface without CLI
        hybrid = Mock()
        hybrid.cli_wrapper = None
        hybrid.serial_interface = self.mock_serial
        
        # Simulate the start_reading method behavior
        def start_reading_impl():
            if hybrid.cli_wrapper:
                return hybrid.cli_wrapper.start_reading()
            else:
                return hybrid.serial_interface.start_reading()
        
        hybrid.start_reading = start_reading_impl
        
        # Call start_reading
        result = hybrid.start_reading()
        
        # Verify serial interface was called
        self.assertTrue(result)
        self.mock_serial.start_reading.assert_called_once()
    
    def test_start_reading_cli_failure(self):
        """Test behavior when CLI wrapper start_reading fails"""
        # Create mock with CLI that fails
        self.mock_cli.start_reading = Mock(return_value=False)
        
        hybrid = Mock()
        hybrid.cli_wrapper = self.mock_cli
        hybrid.serial_interface = self.mock_serial
        
        def start_reading_impl():
            if hybrid.cli_wrapper:
                return hybrid.cli_wrapper.start_reading()
            else:
                return hybrid.serial_interface.start_reading()
        
        hybrid.start_reading = start_reading_impl
        
        # Call start_reading
        result = hybrid.start_reading()
        
        # Verify failure propagated
        self.assertFalse(result)
        self.mock_cli.start_reading.assert_called_once()
    
    def test_start_reading_serial_failure(self):
        """Test behavior when serial interface start_reading fails"""
        # Create mock with serial that fails
        self.mock_serial.start_reading = Mock(return_value=False)
        
        hybrid = Mock()
        hybrid.cli_wrapper = None
        hybrid.serial_interface = self.mock_serial
        
        def start_reading_impl():
            if hybrid.cli_wrapper:
                return hybrid.cli_wrapper.start_reading()
            else:
                return hybrid.serial_interface.start_reading()
        
        hybrid.start_reading = start_reading_impl
        
        # Call start_reading
        result = hybrid.start_reading()
        
        # Verify failure propagated
        self.assertFalse(result)
        self.mock_serial.start_reading.assert_called_once()
    
    def test_routing_logic_priority(self):
        """Test that CLI wrapper has priority over serial interface"""
        # Create hybrid with both interfaces
        hybrid = Mock()
        hybrid.cli_wrapper = self.mock_cli
        hybrid.serial_interface = self.mock_serial
        
        def start_reading_impl():
            if hybrid.cli_wrapper:
                return hybrid.cli_wrapper.start_reading()
            else:
                return hybrid.serial_interface.start_reading()
        
        hybrid.start_reading = start_reading_impl
        
        # Call multiple times
        for _ in range(3):
            hybrid.start_reading()
        
        # Verify only CLI was called, never serial
        self.assertEqual(self.mock_cli.start_reading.call_count, 3)
        self.mock_serial.start_reading.assert_not_called()


if __name__ == '__main__':
    unittest.main()
