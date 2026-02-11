#!/usr/bin/env python3
"""
Test for MeshCore broadcast detection fix
Verifies that sendText properly rejects broadcast messages
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock


class TestMeshCoreBroadcastFix(unittest.TestCase):
    """Test that MeshCore CLI wrapper properly rejects broadcast messages"""
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCore', MagicMock())
    def test_broadcast_detection_0xFFFFFFFF(self):
        """Test that destinationId=0xFFFFFFFF is detected as broadcast"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper with mock meshcore (skip the import check)
        with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True):
            wrapper = MeshCoreCLIWrapper(port='/dev/null', baudrate=115200)
            wrapper.meshcore = Mock()
            wrapper.meshcore.commands = Mock()
            
            # Try to send broadcast
            result = wrapper.sendText("test message", destinationId=0xFFFFFFFF, channelIndex=0)
            
            # Should return False (broadcast not supported)
            self.assertFalse(result, "Broadcast should return False")
            
            # Verify send_msg was NOT called
            wrapper.meshcore.commands.send_msg.assert_not_called()
        
        print("✅ Test passed: Broadcast 0xFFFFFFFF is properly rejected")
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCore', MagicMock())
    def test_broadcast_detection_None(self):
        """Test that destinationId=None is detected as broadcast"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper with mock meshcore
        with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True):
            wrapper = MeshCoreCLIWrapper(port='/dev/null', baudrate=115200)
            wrapper.meshcore = Mock()
            wrapper.meshcore.commands = Mock()
            
            # Try to send broadcast with None
            result = wrapper.sendText("test message", destinationId=None, channelIndex=0)
            
            # Should return False (broadcast not supported)
            self.assertFalse(result, "Broadcast with None should return False")
            
            # Verify send_msg was NOT called
            wrapper.meshcore.commands.send_msg.assert_not_called()
        
        print("✅ Test passed: Broadcast None is properly rejected")
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCore', MagicMock())
    def test_dm_still_works(self):
        """Test that DM messages (specific node IDs) still work"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper with mock meshcore
        with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True):
            wrapper = MeshCoreCLIWrapper(port='/dev/null', baudrate=115200)
            wrapper.meshcore = Mock()
            wrapper.meshcore.commands = Mock()
            wrapper.meshcore.contacts = {}
            wrapper._loop = Mock()
            wrapper._loop.is_running = Mock(return_value=True)
            wrapper.node_manager = Mock()
            wrapper.node_manager.persistence = Mock()
            
            # Mock the pubkey lookup to return None (will use ID directly)
            with patch.object(wrapper, '_get_pubkey_prefix_for_node', return_value=None):
                # Mock asyncio.run_coroutine_threadsafe
                with patch('meshcore_cli_wrapper.asyncio.run_coroutine_threadsafe') as mock_run:
                    mock_future = Mock()
                    mock_run.return_value = mock_future
                    
                    # Try to send DM to specific node
                    result = wrapper.sendText("test message", destinationId=0x12345678, channelIndex=0)
                    
                    # Should return True (DM accepted)
                    self.assertTrue(result, "DM to specific node should return True")
                    
                    # Verify send_msg WAS called
                    mock_run.assert_called_once()
        
        print("✅ Test passed: DM messages still work correctly")
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCore', MagicMock())
    def test_broadcast_with_channel_index(self):
        """Test that broadcast with channelIndex is still rejected"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper with mock meshcore
        with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True):
            wrapper = MeshCoreCLIWrapper(port='/dev/null', baudrate=115200)
            wrapper.meshcore = Mock()
            wrapper.meshcore.commands = Mock()
            
            # Try to send broadcast on channel 1
            result = wrapper.sendText("test message", destinationId=0xFFFFFFFF, channelIndex=1)
            
            # Should return False (broadcast not supported)
            self.assertFalse(result, "Broadcast on channel 1 should return False")
            
            # Verify send_msg was NOT called
            wrapper.meshcore.commands.send_msg.assert_not_called()
        
        print("✅ Test passed: Broadcast on specific channel is properly rejected")


if __name__ == '__main__':
    # Run tests with verbose output
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshCoreBroadcastFix)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSummary:")
        print("  - Broadcast detection (0xFFFFFFFF): ✅")
        print("  - Broadcast detection (None): ✅")
        print("  - DM messages still work: ✅")
        print("  - Channel-specific broadcasts rejected: ✅")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
    
    sys.exit(0 if result.wasSuccessful() else 1)
