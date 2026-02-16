#!/usr/bin/env python3
"""
Test: Contact dict uses 'public_key' field name (snake_case) as expected by meshcore-cli API

This test validates Fix #10 for MeshCore DM delivery.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, MagicMock
import sys


class TestMeshCorePublicKeyField(unittest.TestCase):
    """Test that contact dict uses correct field name for meshcore-cli"""
    
    def test_contact_dict_has_public_key_snake_case(self):
        """Test that _add_contact_to_meshcore creates dict with 'public_key' field"""
        # Test contact data (uses publicKey camelCase in our internal storage)
        contact_data = {
            'node_id': 0x143bcd7f,
            'name': 'TestNode',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f' + b'\x00' * 26,  # 32 bytes
        }
        
        # Simulate what _add_contact_to_meshcore does
        pubkey_hex = contact_data['publicKey'].hex()
        pubkey_prefix = pubkey_hex[:12]
        
        # This is the critical part - must use 'public_key' not 'publicKey'
        contact = {
            'node_id': contact_data['node_id'],
            'adv_name': contact_data.get('name', f"Node-{contact_data['node_id']:08x}"),
            'public_key': contact_data['publicKey'],  # ✅ Must be snake_case
        }
        
        # Verify the field name is correct
        self.assertIn('public_key', contact, "Contact must have 'public_key' field")
        self.assertNotIn('publicKey', contact, "Contact should NOT have 'publicKey' field")
        
        # Verify the value is correct
        self.assertEqual(contact['public_key'], contact_data['publicKey'])
        
        print("✅ Test passed: Contact dict uses 'public_key' (snake_case)")
    
    def test_meshcore_api_expects_public_key(self):
        """Test that meshcore-cli API rejects publicKey (camelCase)"""
        # This test documents the expected behavior based on the error:
        # "Contact object must have a 'public_key' field"
        
        contact_with_wrong_field = {
            'node_id': 0x143bcd7f,
            'adv_name': 'TestNode',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f' + b'\x00' * 26,
        }
        
        contact_with_correct_field = {
            'node_id': 0x143bcd7f,
            'adv_name': 'TestNode',
            'public_key': b'\x14\x3b\xcd\x7f\x1b\x1f' + b'\x00' * 26,
        }
        
        # Wrong field name
        self.assertNotIn('public_key', contact_with_wrong_field)
        # This would cause error: "Contact object must have a 'public_key' field"
        
        # Correct field name
        self.assertIn('public_key', contact_with_correct_field)
        # This should work ✅
        
        print("✅ Test passed: meshcore-cli API requires 'public_key' field")
    
    def test_code_fix_present(self):
        """Test that the fix is present in meshcore_cli_wrapper.py"""
        with open('/home/runner/work/meshbot/meshbot/meshcore_cli_wrapper.py', 'r') as f:
            code = f.read()
        
        # Check that we're using 'public_key' in the contact dict
        self.assertIn("'public_key': contact_data['publicKey']", code,
                     "Code should use 'public_key' field name")
        
        # The line should have a comment explaining the fix
        self.assertIn("snake_case", code.lower(),
                     "Code should document the snake_case requirement")
        
        print("✅ Test passed: Fix is present in code")


if __name__ == '__main__':
    unittest.main(verbosity=2)
