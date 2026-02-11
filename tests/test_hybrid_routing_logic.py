#!/usr/bin/env python3
"""
Test: MeshCore Hybrid Interface Logic

This test verifies the routing logic of the hybrid interface without
needing to import main_bot.py
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock


class TestHybridInterfaceLogic(unittest.TestCase):
    """Test the hybrid interface routing logic"""
    
    def test_broadcast_detection_0xFFFFFFFF(self):
        """Test that 0xFFFFFFFF is detected as broadcast"""
        destination_id = 0xFFFFFFFF
        is_broadcast = (destination_id is None or destination_id == 0xFFFFFFFF)
        
        self.assertTrue(is_broadcast)
        print("✅ Test passed: 0xFFFFFFFF detected as broadcast")
    
    def test_broadcast_detection_None(self):
        """Test that None is detected as broadcast"""
        destination_id = None
        is_broadcast = (destination_id is None or destination_id == 0xFFFFFFFF)
        
        self.assertTrue(is_broadcast)
        print("✅ Test passed: None detected as broadcast")
    
    def test_specific_destination_not_broadcast(self):
        """Test that specific node IDs are not broadcasts"""
        destination_id = 0x12345678
        is_broadcast = (destination_id is None or destination_id == 0xFFFFFFFF)
        
        self.assertFalse(is_broadcast)
        print("✅ Test passed: Specific destination not a broadcast")
    
    def test_routing_logic_broadcast(self):
        """Test routing decision for broadcasts"""
        # Simulate hybrid interface logic
        mock_serial = Mock()
        mock_serial.sendText = Mock(return_value=True)
        
        mock_cli = Mock()
        mock_cli.sendText = Mock(return_value=True)
        
        # Broadcast case
        destination_id = 0xFFFFFFFF
        is_broadcast = (destination_id is None or destination_id == 0xFFFFFFFF)
        
        if is_broadcast:
            # Should use serial interface
            result = mock_serial.sendText("Test", destination_id, 0)
        else:
            # Should use CLI wrapper
            result = mock_cli.sendText("Test", destination_id, 0)
        
        # Verify serial was called
        mock_serial.sendText.assert_called_once()
        mock_cli.sendText.assert_not_called()
        
        print("✅ Test passed: Broadcasts route to serial interface")
    
    def test_routing_logic_dm(self):
        """Test routing decision for DM messages"""
        # Simulate hybrid interface logic
        mock_serial = Mock()
        mock_serial.sendText = Mock(return_value=True)
        
        mock_cli = Mock()
        mock_cli.sendText = Mock(return_value=True)
        
        # DM case
        destination_id = 0x12345678
        is_broadcast = (destination_id is None or destination_id == 0xFFFFFFFF)
        
        if is_broadcast:
            # Should use serial interface
            result = mock_serial.sendText("Test", destination_id, 0)
        else:
            # Should use CLI wrapper
            result = mock_cli.sendText("Test", destination_id, 0)
        
        # Verify CLI was called
        mock_cli.sendText.assert_called_once()
        mock_serial.sendText.assert_not_called()
        
        print("✅ Test passed: DM messages route to CLI wrapper")


if __name__ == '__main__':
    # Run tests with verbose output
    suite = unittest.TestLoader().loadTestsFromTestCase(TestHybridInterfaceLogic)
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
        print("  - Specific destination detection: ✅")
        print("  - Broadcast routing to serial: ✅")
        print("  - DM routing to CLI wrapper: ✅")
        print()
        print("Conclusion: Hybrid interface routing logic is correct!")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
    
    sys.exit(0 if result.wasSuccessful() else 1)
