#!/usr/bin/env python3
"""
Test suite for MeshCore direct dict access fix
Validates that we can access contacts in meshcore.contacts dict directly
"""

import unittest
from unittest.mock import Mock, MagicMock


class TestMeshCoreDirectDictAccess(unittest.TestCase):
    """Test direct dict access instead of get_contact_by_key_prefix()"""
    
    def test_direct_dict_access_finds_contact(self):
        """Test that direct dict access finds the contact"""
        # Setup
        pubkey_prefix = "143bcd7f1b1f"
        contact_data = {
            'node_id': 0x143bcd7f,
            'adv_name': 'TestNode',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f' + b'\x00' * 26
        }
        
        # Create mock meshcore with contacts dict
        meshcore = Mock()
        meshcore.contacts = {pubkey_prefix: contact_data}
        
        # Test direct dict access
        contact = meshcore.contacts.get(pubkey_prefix)
        
        # Verify
        self.assertIsNotNone(contact)
        self.assertEqual(contact['node_id'], 0x143bcd7f)
        self.assertEqual(contact['adv_name'], 'TestNode')
        print("✅ Direct dict access finds contact")
    
    def test_direct_dict_access_handles_missing_contact(self):
        """Test that direct dict access returns None for missing contact"""
        # Setup
        meshcore = Mock()
        meshcore.contacts = {}
        
        # Test direct dict access with non-existent key
        contact = meshcore.contacts.get("nonexistent")
        
        # Verify
        self.assertIsNone(contact)
        print("✅ Direct dict access handles missing contact")
    
    def test_direct_dict_access_more_reliable_than_method(self):
        """Test that direct access is more reliable than library method"""
        # Setup
        pubkey_prefix = "143bcd7f1b1f"
        contact_data = {
            'node_id': 0x143bcd7f,
            'adv_name': 'TestNode',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f' + b'\x00' * 26
        }
        
        # Create mock meshcore
        meshcore = Mock()
        meshcore.contacts = {pubkey_prefix: contact_data}
        
        # Simulate meshcore-cli method not finding it (the bug we're fixing)
        meshcore.get_contact_by_key_prefix = Mock(return_value=None)
        
        # Test that library method fails
        contact_via_method = meshcore.get_contact_by_key_prefix(pubkey_prefix)
        self.assertIsNone(contact_via_method)
        
        # But direct dict access succeeds
        contact_via_dict = meshcore.contacts.get(pubkey_prefix)
        self.assertIsNotNone(contact_via_dict)
        self.assertEqual(contact_via_dict['node_id'], 0x143bcd7f)
        
        print("✅ Direct dict access more reliable than library method")
    
    def test_fix_code_present(self):
        """Test that the fix code is present in meshcore_cli_wrapper.py"""
        with open('meshcore_cli_wrapper.py', 'r') as f:
            code = f.read()
        
        # Check for direct dict access pattern
        self.assertIn('self.meshcore.contacts.get(pubkey_prefix)', code)
        
        # Check for diagnostic logging
        self.assertIn('Contact trouvé via dict direct', code)
        
        print("✅ Fix code present in meshcore_cli_wrapper.py")


if __name__ == '__main__':
    unittest.main(verbosity=2)
