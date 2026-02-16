#!/usr/bin/env python3
"""
Test that contacts are added to meshcore.contacts dict at all save locations

This test validates that _add_contact_to_meshcore() is called alongside
save_meshcore_contact() at all 3 locations in the code.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import re


class TestContactAdditionLocations(unittest.TestCase):
    """Test that all save locations also add to meshcore.contacts dict"""
    
    def test_all_save_locations_have_add_to_dict(self):
        """Verify all save_meshcore_contact calls are followed by _add_contact_to_meshcore"""
        
        # Read the source file
        with open('/home/runner/work/meshbot/meshbot/meshcore_cli_wrapper.py', 'r') as f:
            source = f.read()
        
        # Find all save_meshcore_contact calls
        save_pattern = r'self\.node_manager\.persistence\.save_meshcore_contact\(contact_data\)'
        save_matches = list(re.finditer(save_pattern, source))
        
        print(f"Found {len(save_matches)} save_meshcore_contact() calls")
        
        # For each save, check if it's followed by _add_contact_to_meshcore
        add_pattern = r'self\._add_contact_to_meshcore\(contact_data\)'
        
        for i, save_match in enumerate(save_matches):
            # Get the next 200 characters after the save
            start = save_match.end()
            end = min(start + 200, len(source))
            following_text = source[start:end]
            
            # Check if _add_contact_to_meshcore is in the following lines
            if re.search(add_pattern, following_text):
                print(f"✅ Location {i+1}: save + add to dict")
            else:
                print(f"❌ Location {i+1}: save WITHOUT add to dict")
                # Get context for debugging
                context_start = max(0, save_match.start() - 200)
                context_end = min(len(source), save_match.end() + 200)
                context = source[context_start:context_end]
                print(f"   Context: ...{context}...")
                self.fail(f"save_meshcore_contact at location {i+1} not followed by _add_contact_to_meshcore")
        
        # We expect exactly 3 save locations
        self.assertEqual(len(save_matches), 3, 
                        f"Expected 3 save locations, found {len(save_matches)}")
        
        print("\n✅ All 3 save_meshcore_contact() calls are followed by _add_contact_to_meshcore()")
    
    def test_add_contact_to_meshcore_exists(self):
        """Verify _add_contact_to_meshcore method exists"""
        with open('/home/runner/work/meshbot/meshbot/meshcore_cli_wrapper.py', 'r') as f:
            source = f.read()
        
        # Check if the method is defined
        self.assertIn('def _add_contact_to_meshcore(self, contact_data)', source)
        print("✅ _add_contact_to_meshcore method exists")
    
    def test_method_adds_to_dict(self):
        """Verify _add_contact_to_meshcore actually adds to meshcore.contacts"""
        with open('/home/runner/work/meshbot/meshbot/meshcore_cli_wrapper.py', 'r') as f:
            source = f.read()
        
        # Find the method and check it manipulates meshcore.contacts
        method_pattern = r'def _add_contact_to_meshcore\(self, contact_data\):.*?(?=\n    def |\nclass |\Z)'
        match = re.search(method_pattern, source, re.DOTALL)
        
        self.assertIsNotNone(match, "_add_contact_to_meshcore method not found")
        
        method_body = match.group(0)
        
        # Check that it adds to meshcore.contacts
        self.assertIn('self.meshcore.contacts[', method_body)
        self.assertIn('pubkey_prefix', method_body)
        
        print("✅ _add_contact_to_meshcore modifies meshcore.contacts dict")


if __name__ == '__main__':
    print("Running code structure tests...")
    unittest.main(verbosity=2)

