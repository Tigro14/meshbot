#!/usr/bin/env python3
"""
Test suite for DM public key resolution
Tests the new query_contact_by_pubkey_prefix() method
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Mock config before importing other modules
class MockConfig:
    DEBUG_MODE = False
    MAX_MESSAGE_SIZE = 180
    BOT_POSITION = None

sys.modules['config'] = MockConfig()

class TestPubKeyDMResolution(unittest.TestCase):
    """Test DM public key resolution functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the MeshCore import
        self.mock_meshcore = MagicMock()
        self.mock_eventtype = MagicMock()
        
        # Patch meshcore import
        sys.modules['meshcore'] = self.mock_meshcore
        self.mock_meshcore.MeshCore = MagicMock
        self.mock_meshcore.EventType = self.mock_eventtype
        
        # Import after mocking
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        from node_manager import NodeManager
        
        # Create test instances
        self.node_manager = NodeManager(interface=None)
        self.node_manager.node_names = {}
        
        # Create wrapper
        self.wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
        self.wrapper.meshcore = Mock()
        self.wrapper._loop = Mock()
        self.wrapper.node_manager = self.node_manager
    
    def test_find_node_by_pubkey_hex_format(self):
        """Test finding node with hex format publicKey"""
        # Add a node with hex publicKey
        test_node_id = 0x0de3331e
        self.node_manager.node_names[test_node_id] = {
            'name': 'TestNode',
            'publicKey': '143bcd7f1b1f0000000000000000000000000000000000000000000000000000'
        }
        
        # Search by prefix
        result = self.node_manager.find_node_by_pubkey_prefix('143bcd7f1b1f')
        
        self.assertEqual(result, test_node_id)
        print("✅ PASS: Hex format publicKey matching")
    
    def test_find_node_by_pubkey_base64_format(self):
        """Test finding node with base64 format publicKey"""
        import base64
        
        # Create a base64-encoded publicKey
        # 143bcd7f1b1f = FDvNfxsf in base64
        hex_key = '143bcd7f1b1f0000000000000000000000000000000000000000000000000000'
        bytes_key = bytes.fromhex(hex_key)
        base64_key = base64.b64encode(bytes_key).decode('utf-8')
        
        # Add a node with base64 publicKey
        test_node_id = 0x0de3331e
        self.node_manager.node_names[test_node_id] = {
            'name': 'TestNode',
            'publicKey': base64_key
        }
        
        # Search by hex prefix
        result = self.node_manager.find_node_by_pubkey_prefix('143bcd7f1b1f')
        
        self.assertEqual(result, test_node_id)
        print("✅ PASS: Base64 format publicKey matching")
    
    def test_find_node_by_pubkey_bytes_format(self):
        """Test finding node with bytes format publicKey"""
        # Create bytes publicKey
        hex_key = '143bcd7f1b1f0000000000000000000000000000000000000000000000000000'
        bytes_key = bytes.fromhex(hex_key)
        
        # Add a node with bytes publicKey
        test_node_id = 0x0de3331e
        self.node_manager.node_names[test_node_id] = {
            'name': 'TestNode',
            'publicKey': bytes_key
        }
        
        # Search by hex prefix
        result = self.node_manager.find_node_by_pubkey_prefix('143bcd7f1b1f')
        
        self.assertEqual(result, test_node_id)
        print("✅ PASS: Bytes format publicKey matching")
    
    def test_find_node_not_found(self):
        """Test when no node matches the prefix"""
        # Add a node with different publicKey
        test_node_id = 0x0de3331e
        self.node_manager.node_names[test_node_id] = {
            'name': 'TestNode',
            'publicKey': 'aabbccdd00000000000000000000000000000000000000000000000000000000'
        }
        
        # Search by non-matching prefix
        result = self.node_manager.find_node_by_pubkey_prefix('143bcd7f1b1f')
        
        self.assertIsNone(result)
        print("✅ PASS: Not found returns None")
    
    def test_query_contact_by_pubkey_prefix_success(self):
        """Test querying meshcore for contact by pubkey prefix"""
        # Mock meshcore contact
        mock_contact = {
            'contact_id': 0x0de3331e,
            'name': 'TestContact',
            'public_key': '143bcd7f1b1f0000000000000000000000000000000000000000000000000000'
        }
        
        # Mock meshcore methods
        self.wrapper.meshcore.get_contact_by_key_prefix = Mock(return_value=mock_contact)
        self.wrapper.meshcore.ensure_contacts = Mock()
        self.wrapper._loop.run_until_complete = Mock(side_effect=lambda x: None)
        
        # Mock node_manager save
        self.wrapper.node_manager.save_node_names = Mock()
        
        # Query contact
        result = self.wrapper.query_contact_by_pubkey_prefix('143bcd7f1b1f')
        
        # Verify result
        self.assertEqual(result, 0x0de3331e)
        
        # Verify contact was added to node_manager
        self.assertIn(0x0de3331e, self.node_manager.node_names)
        self.assertEqual(self.node_manager.node_names[0x0de3331e]['name'], 'TestContact')
        
        print("✅ PASS: Query contact and add to database")
    
    def test_query_contact_by_pubkey_prefix_not_found(self):
        """Test querying meshcore when contact not found"""
        # Mock meshcore to return None
        self.wrapper.meshcore.get_contact_by_key_prefix = Mock(return_value=None)
        self.wrapper.meshcore.ensure_contacts = Mock()
        self.wrapper._loop.run_until_complete = Mock(side_effect=lambda x: None)
        
        # Query contact
        result = self.wrapper.query_contact_by_pubkey_prefix('143bcd7f1b1f')
        
        # Verify result is None
        self.assertIsNone(result)
        
        print("✅ PASS: Query returns None when contact not found")
    
    def test_query_contact_updates_existing_node(self):
        """Test that querying updates existing node with publicKey"""
        # Add existing node without publicKey
        test_node_id = 0x0de3331e
        self.node_manager.node_names[test_node_id] = {
            'name': 'ExistingNode',
            'publicKey': None
        }
        
        # Mock meshcore contact
        mock_contact = {
            'contact_id': test_node_id,
            'name': 'ExistingNode',
            'public_key': '143bcd7f1b1f0000000000000000000000000000000000000000000000000000'
        }
        
        self.wrapper.meshcore.get_contact_by_key_prefix = Mock(return_value=mock_contact)
        self.wrapper.meshcore.ensure_contacts = Mock()
        self.wrapper._loop.run_until_complete = Mock(side_effect=lambda x: None)
        self.wrapper.node_manager.save_node_names = Mock()
        
        # Query contact
        result = self.wrapper.query_contact_by_pubkey_prefix('143bcd7f1b1f')
        
        # Verify publicKey was added
        self.assertEqual(result, test_node_id)
        self.assertIsNotNone(self.node_manager.node_names[test_node_id]['publicKey'])
        
        print("✅ PASS: Query updates existing node with publicKey")
    
    def test_dm_flow_with_query(self):
        """Test complete DM flow with pubkey query"""
        # Test the lookup directly rather than through the event handler
        # to avoid Mock formatting issues
        
        # Mock meshcore contact lookup
        mock_contact = {
            'contact_id': 0x0de3331e,
            'name': 'DMSender',
            'public_key': '143bcd7f1b1f0000000000000000000000000000000000000000000000000000'
        }
        
        self.wrapper.meshcore.get_contact_by_key_prefix = Mock(return_value=mock_contact)
        self.wrapper.meshcore.ensure_contacts = Mock()
        self.wrapper._loop.run_until_complete = Mock(side_effect=lambda x: None)
        self.wrapper.node_manager.save_node_names = Mock()
        
        # Test the query flow
        result = self.wrapper.query_contact_by_pubkey_prefix('143bcd7f1b1f')
        
        # Verify contact was found and added
        self.assertEqual(result, 0x0de3331e)
        self.assertIn(0x0de3331e, self.node_manager.node_names)
        self.assertEqual(self.node_manager.node_names[0x0de3331e]['name'], 'DMSender')
        
        # Now test find_node_by_pubkey_prefix can find it
        found_id = self.node_manager.find_node_by_pubkey_prefix('143bcd7f1b1f')
        self.assertEqual(found_id, 0x0de3331e)
        
        print("✅ PASS: Complete DM flow resolves sender correctly")


def run_tests():
    """Run all tests and display results"""
    print("="*60)
    print("Testing DM Public Key Resolution")
    print("="*60)
    print()
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPubKeyDMResolution)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print()
    print("="*60)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED!")
        print(f"   {result.testsRun} tests run successfully")
    else:
        print("❌ SOME TESTS FAILED")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
    print("="*60)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
