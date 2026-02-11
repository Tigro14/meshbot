#!/usr/bin/env python3
"""
Tests for MeshCore hybrid interface read loop fix

This verifies that when CLI wrapper is available, the serial interface's
read loop is disabled to avoid conflicts with binary protocol decoding.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestHybridReadLoopFix(unittest.TestCase):
    """Test suite for hybrid interface read loop control"""
    
    def test_serial_interface_read_loop_disabled_when_cli_available(self):
        """Test that serial interface read loop is disabled when CLI wrapper is available"""
        # Mock the imports
        with patch('meshcore_serial_interface.serial'):
            from meshcore_serial_interface import MeshCoreSerialInterface as MeshCoreSerialBase
            
            # Test with enable_read_loop=False
            interface = MeshCoreSerialBase('/dev/ttyUSB0', 115200, enable_read_loop=False)
            
            # Verify read loop is disabled
            self.assertFalse(interface.enable_read_loop, 
                           "Read loop should be disabled when enable_read_loop=False")
    
    def test_serial_interface_read_loop_enabled_by_default(self):
        """Test that serial interface read loop is enabled by default"""
        with patch('meshcore_serial_interface.serial'):
            from meshcore_serial_interface import MeshCoreSerialInterface as MeshCoreSerialBase
            
            # Test with default parameters
            interface = MeshCoreSerialBase('/dev/ttyUSB0', 115200)
            
            # Verify read loop is enabled by default
            self.assertTrue(interface.enable_read_loop, 
                          "Read loop should be enabled by default")
    
    def test_start_reading_skips_when_read_loop_disabled(self):
        """Test that start_reading() returns early when read loop is disabled"""
        with patch('meshcore_serial_interface.serial') as mock_serial:
            from meshcore_serial_interface import MeshCoreSerialInterface as MeshCoreSerialBase
            
            # Create interface with read loop disabled
            interface = MeshCoreSerialBase('/dev/ttyUSB0', 115200, enable_read_loop=False)
            
            # Mock serial connection
            interface.serial = MagicMock()
            interface.serial.is_open = True
            
            # Start reading
            result = interface.start_reading()
            
            # Should return True but not start thread
            self.assertTrue(result, "start_reading should return True")
            self.assertFalse(hasattr(interface, 'read_thread'), 
                           "Should not create read_thread when read loop disabled")
    
    def test_hybrid_interface_disables_serial_read_loop(self):
        """Test that hybrid interface disables serial read loop when CLI available"""
        # This test verifies the integration between hybrid interface and serial interface
        
        # Mock the CLI wrapper availability
        with patch('main_bot.MESHCORE_CLI_AVAILABLE', True), \
             patch('main_bot.MeshCoreCLIWrapper') as MockCLIWrapper, \
             patch('meshcore_serial_interface.serial'):
            
            # Import after patching
            from main_bot import MeshCoreHybridInterface
            
            # Create hybrid interface
            hybrid = MeshCoreHybridInterface('/dev/ttyUSB0', 115200)
            
            # Verify serial interface has read loop disabled
            self.assertFalse(hybrid.serial_interface.enable_read_loop,
                           "Serial interface read loop should be disabled in hybrid mode with CLI")
    
    def test_hybrid_interface_enables_serial_read_loop_when_cli_fails(self):
        """Test that serial read loop is re-enabled if CLI wrapper fails to initialize"""
        
        # Mock CLI wrapper to fail
        with patch('main_bot.MESHCORE_CLI_AVAILABLE', True), \
             patch('main_bot.MeshCoreCLIWrapper', side_effect=Exception("CLI init failed")), \
             patch('meshcore_serial_interface.serial'):
            
            # Import after patching
            from main_bot import MeshCoreHybridInterface
            
            # Create hybrid interface (CLI will fail)
            hybrid = MeshCoreHybridInterface('/dev/ttyUSB0', 115200)
            
            # Verify serial interface has read loop re-enabled as fallback
            self.assertTrue(hybrid.serial_interface.enable_read_loop,
                          "Serial interface read loop should be re-enabled when CLI fails")
            self.assertIsNone(hybrid.cli_wrapper,
                            "CLI wrapper should be None when initialization fails")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("Testing MeshCore Hybrid Interface Read Loop Fix")
    print("="*80 + "\n")
    
    # Run tests
    unittest.main(verbosity=2)
