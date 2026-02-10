#!/usr/bin/env python3
"""
Test: MeshCore Hybrid Interface for Broadcast Support

This test verifies that the hybrid interface correctly routes:
- Broadcasts to MeshCoreSerialInterface (binary protocol)
- DM messages to MeshCoreCLIWrapper when available
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock, patch


class TestMeshCoreHybridInterface(unittest.TestCase):
    """Test the hybrid interface routing logic"""
    
    @patch('main_bot.MESHCORE_CLI_AVAILABLE', True)
    @patch('main_bot.MeshCoreCLIWrapper')
    @patch('main_bot.MeshCoreSerialBase')
    def test_hybrid_interface_broadcast_uses_serial(self, mock_serial_class, mock_cli_class):
        """Test that broadcasts use serial interface (binary protocol)"""
        from main_bot import MeshCoreHybridInterface
        
        # Create mocks
        mock_serial = Mock()
        mock_serial.connect = Mock(return_value=True)
        mock_serial.sendText = Mock(return_value=True)
        mock_serial.localNode = Mock()
        mock_serial.serial = Mock()
        mock_serial_class.return_value = mock_serial
        
        mock_cli = Mock()
        mock_cli.connect = Mock(return_value=True)
        mock_cli.sendText = Mock(return_value=True)
        mock_cli_class.return_value = mock_cli
        
        # Create hybrid interface
        hybrid = MeshCoreHybridInterface('/dev/null', 115200)
        hybrid.connect()
        
        # Send broadcast
        result = hybrid.sendText("Test broadcast", destinationId=0xFFFFFFFF, channelIndex=0)
        
        # Verify serial interface was used (not CLI)
        mock_serial.sendText.assert_called_once_with("Test broadcast", 0xFFFFFFFF, 0)
        mock_cli.sendText.assert_not_called()
        
        self.assertTrue(result)
        print("✅ Test passed: Broadcasts use serial interface")
    
    @patch('main_bot.MESHCORE_CLI_AVAILABLE', True)
    @patch('main_bot.MeshCoreCLIWrapper')
    @patch('main_bot.MeshCoreSerialBase')
    def test_hybrid_interface_dm_uses_cli(self, mock_serial_class, mock_cli_class):
        """Test that DM messages use CLI wrapper when available"""
        from main_bot import MeshCoreHybridInterface
        
        # Create mocks
        mock_serial = Mock()
        mock_serial.connect = Mock(return_value=True)
        mock_serial.sendText = Mock(return_value=True)
        mock_serial.localNode = Mock()
        mock_serial.serial = Mock()
        mock_serial_class.return_value = mock_serial
        
        mock_cli = Mock()
        mock_cli.connect = Mock(return_value=True)
        mock_cli.sendText = Mock(return_value=True)
        mock_cli_class.return_value = mock_cli
        
        # Create hybrid interface
        hybrid = MeshCoreHybridInterface('/dev/null', 115200)
        hybrid.connect()
        
        # Send DM
        result = hybrid.sendText("Test DM", destinationId=0x12345678, channelIndex=0)
        
        # Verify CLI wrapper was used (not serial)
        mock_cli.sendText.assert_called_once_with("Test DM", 0x12345678, 0)
        mock_serial.sendText.assert_not_called()
        
        self.assertTrue(result)
        print("✅ Test passed: DM messages use CLI wrapper")
    
    @patch('main_bot.MESHCORE_CLI_AVAILABLE', False)
    @patch('main_bot.MeshCoreCLIWrapper', None)
    @patch('main_bot.MeshCoreSerialBase')
    def test_hybrid_interface_fallback_to_serial(self, mock_serial_class):
        """Test that without CLI, both broadcasts and DMs use serial interface"""
        from main_bot import MeshCoreHybridInterface
        
        # Create mock
        mock_serial = Mock()
        mock_serial.connect = Mock(return_value=True)
        mock_serial.sendText = Mock(return_value=True)
        mock_serial.localNode = Mock()
        mock_serial.serial = Mock()
        mock_serial_class.return_value = mock_serial
        
        # Create hybrid interface (no CLI available)
        hybrid = MeshCoreHybridInterface('/dev/null', 115200)
        hybrid.connect()
        
        # Send broadcast
        hybrid.sendText("Broadcast", destinationId=0xFFFFFFFF, channelIndex=0)
        
        # Send DM
        hybrid.sendText("DM", destinationId=0x12345678, channelIndex=0)
        
        # Both should use serial interface
        self.assertEqual(mock_serial.sendText.call_count, 2)
        
        print("✅ Test passed: Without CLI, both use serial interface")
    
    @patch('main_bot.MESHCORE_CLI_AVAILABLE', True)
    @patch('main_bot.MeshCoreCLIWrapper')
    @patch('main_bot.MeshCoreSerialBase')
    def test_hybrid_interface_none_destination_is_broadcast(self, mock_serial_class, mock_cli_class):
        """Test that destinationId=None is treated as broadcast"""
        from main_bot import MeshCoreHybridInterface
        
        # Create mocks
        mock_serial = Mock()
        mock_serial.connect = Mock(return_value=True)
        mock_serial.sendText = Mock(return_value=True)
        mock_serial.localNode = Mock()
        mock_serial.serial = Mock()
        mock_serial_class.return_value = mock_serial
        
        mock_cli = Mock()
        mock_cli.connect = Mock(return_value=True)
        mock_cli_class.return_value = mock_cli
        
        # Create hybrid interface
        hybrid = MeshCoreHybridInterface('/dev/null', 115200)
        hybrid.connect()
        
        # Send with None destination (should be broadcast)
        hybrid.sendText("Test", destinationId=None, channelIndex=0)
        
        # Should use serial interface (broadcast)
        mock_serial.sendText.assert_called_once()
        mock_cli.sendText.assert_not_called()
        
        print("✅ Test passed: None destination treated as broadcast")


if __name__ == '__main__':
    # Run tests with verbose output
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshCoreHybridInterface)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSummary:")
        print("  - Broadcasts use serial interface: ✅")
        print("  - DM messages use CLI wrapper: ✅")
        print("  - Fallback to serial works: ✅")
        print("  - None destination = broadcast: ✅")
        print()
        print("Conclusion: Hybrid interface correctly routes messages!")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
    
    sys.exit(0 if result.wasSuccessful() else 1)
