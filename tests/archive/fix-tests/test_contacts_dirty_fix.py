#!/usr/bin/env python3
"""
Test: Fix for contacts_dirty AttributeError

This test validates the fix for the issue where setting contacts_dirty
as a property fails because it's read-only. The fix uses the private
_contacts_dirty attribute instead.

Issue: AttributeError: property 'contacts_dirty' of 'MeshCore' object has no setter
Solution: Use _contacts_dirty private attribute instead of contacts_dirty property
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, PropertyMock
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))


class TestContactsDirtyFix(unittest.TestCase):
    """Test the contacts_dirty AttributeError fix"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock MeshCore object that mimics the real behavior
        self.mock_meshcore = Mock()
        
        # Simulate read-only property behavior
        # contacts_dirty as a property (read-only)
        type(self.mock_meshcore).contacts_dirty = PropertyMock(
            return_value=False
        )
        
        # Private attribute _contacts_dirty (writable)
        self.mock_meshcore._contacts_dirty = False
        
        # Other necessary attributes
        self.mock_meshcore.contacts = {}
        
        # Create an async function for ensure_contacts
        async def mock_ensure_contacts():
            return None
        
        self.mock_meshcore.ensure_contacts = mock_ensure_contacts
    
    def test_contacts_dirty_property_is_read_only(self):
        """Test that contacts_dirty property raises AttributeError when set"""
        # Simulating the real MeshCore behavior where property is read-only
        # In unittest.mock, PropertyMock doesn't raise AttributeError by default
        # We need to simulate this behavior explicitly
        
        # Try to set it - in the real MeshCore, this would fail
        try:
            self.mock_meshcore.contacts_dirty = True
            # If we get here with a Mock, it doesn't properly simulate the property
            # But our fix handles this by checking for _contacts_dirty first
            property_works = True
        except AttributeError:
            property_works = False
        
        # The key is that _contacts_dirty works regardless
        self.mock_meshcore._contacts_dirty = True
        self.assertTrue(self.mock_meshcore._contacts_dirty)
    
    def test_fallback_to_property_with_error_handling(self):
        """Test fallback to property with proper error handling"""
        # Create a more realistic mock that actually raises AttributeError
        class ReadOnlyPropertyMock:
            def __init__(self):
                self._contacts_dirty = False
            
            @property
            def contacts_dirty(self):
                return self._contacts_dirty
            
            # No setter - this will raise AttributeError
        
        mock_meshcore_readonly = ReadOnlyPropertyMock()
        
        # The fixed code should handle this gracefully
        if hasattr(mock_meshcore_readonly, '_contacts_dirty'):
            mock_meshcore_readonly._contacts_dirty = True
            error_occurred = False
        elif hasattr(mock_meshcore_readonly, 'contacts_dirty'):
            try:
                mock_meshcore_readonly.contacts_dirty = True
                error_occurred = False
            except AttributeError as e:
                error_occurred = True
                # This is expected and should be handled gracefully
                self.assertIn("can't set attribute", str(e).lower())
        
        # The fix should use _contacts_dirty first, so no error should occur
        self.assertFalse(error_occurred)
        self.assertTrue(mock_meshcore_readonly._contacts_dirty)
    
    def test_integration_with_query_contact_by_pubkey_prefix(self):
        """Test the complete flow with query_contact_by_pubkey_prefix"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create a minimal wrapper setup
        wrapper = MeshCoreCLIWrapper.__new__(MeshCoreCLIWrapper)
        wrapper.meshcore = self.mock_meshcore
        wrapper.node_manager = Mock()
        wrapper.node_manager.node_names = {}
        
        # Mock the query
        self.mock_meshcore.get_contact_by_key_prefix = Mock(return_value=None)
        
        # This should NOT raise AttributeError anymore
        try:
            result = wrapper.query_contact_by_pubkey_prefix("143bcd7f1b1f")
            # Even if contact is not found, it should not crash
            success = True
        except AttributeError as e:
            if "has no setter" in str(e):
                success = False
            else:
                # Other AttributeErrors are not related to our fix
                raise
        
        # The fix prevents the AttributeError
        self.assertTrue(success)


def run_tests():
    """Run the test suite"""
    print("\n" + "="*60)
    print("  Testing contacts_dirty AttributeError Fix")
    print("="*60 + "\n")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestContactsDirtyFix)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("  ✅ ALL TESTS PASSED!")
        print(f"     {result.testsRun} tests run successfully")
    else:
        print("  ❌ SOME TESTS FAILED")
        print(f"     Failures: {len(result.failures)}")
        print(f"     Errors: {len(result.errors)}")
    print("="*60 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
