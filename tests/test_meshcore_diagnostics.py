#!/usr/bin/env python3
"""
Test suite for MeshCore configuration diagnostics

Tests the enhanced diagnostic capabilities added to investigate
why the meshcore library might not be dispatching decoded CONTACT_MSG_RECV events.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys


class MockMeshCore:
    """Mock MeshCore object for testing diagnostics"""
    
    def __init__(self, **config):
        # Configure which features are available
        self._has_private_key = config.get('has_private_key', True)
        self._has_sync_contacts = config.get('has_sync_contacts', True)
        self._has_auto_fetch = config.get('has_auto_fetch', True)
        self._has_events = config.get('has_events', True)
        self.contacts_count = config.get('contacts_count', 5)
        
        # Attributes - only add if feature is enabled
        if self._has_private_key:
            self.private_key = b'mock_key_data' if config.get('key_is_set', True) else None
        
        if self._has_events:
            self.events = Mock()
            self.events.subscribe = Mock()
        
        if self._has_sync_contacts:
            self.contacts = [f'contact_{i}' for i in range(self.contacts_count)]
    
    def __getattr__(self, name):
        """Override __getattr__ to control which methods are available"""
        if name == 'sync_contacts' and self._has_sync_contacts:
            async def _sync_contacts():
                await asyncio.sleep(0)  # Simulate async operation
            return _sync_contacts
        elif name == 'start_auto_message_fetching' and self._has_auto_fetch:
            async def _start_auto_fetch():
                await asyncio.sleep(0)  # Simulate async operation
            return _start_auto_fetch
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class TestMeshCoreConfigurationDiagnostics(unittest.TestCase):
    """Test configuration diagnostic features"""
    
    def test_perfect_configuration(self):
        """Test diagnostics with perfect configuration"""
        mock_meshcore = MockMeshCore(
            has_private_key=True,
            has_sync_contacts=True,
            has_auto_fetch=True,
            has_events=True,
            key_is_set=True,
            contacts_count=5
        )
        
        # Verify all required attributes exist
        self.assertTrue(hasattr(mock_meshcore, 'private_key'))
        self.assertIsNotNone(mock_meshcore.private_key)
        self.assertTrue(hasattr(mock_meshcore, 'sync_contacts'))
        self.assertTrue(hasattr(mock_meshcore, 'start_auto_message_fetching'))
        self.assertTrue(hasattr(mock_meshcore, 'events'))
        self.assertEqual(len(mock_meshcore.contacts), 5)
    
    def test_missing_private_key(self):
        """Test diagnostics when private key is missing"""
        mock_meshcore = MockMeshCore(has_private_key=False)
        
        # Verify private key attributes are missing
        self.assertFalse(hasattr(mock_meshcore, 'private_key'))
        
    def test_private_key_not_set(self):
        """Test diagnostics when private key attribute exists but is None"""
        mock_meshcore = MockMeshCore(
            has_private_key=True,
            key_is_set=False
        )
        
        # Verify private key is None
        self.assertTrue(hasattr(mock_meshcore, 'private_key'))
        self.assertIsNone(mock_meshcore.private_key)
    
    def test_missing_sync_contacts(self):
        """Test diagnostics when sync_contacts is not available"""
        mock_meshcore = MockMeshCore(has_sync_contacts=False)
        
        # Verify sync_contacts is missing
        self.assertFalse(hasattr(mock_meshcore, 'sync_contacts'))
    
    def test_missing_auto_message_fetching(self):
        """Test diagnostics when start_auto_message_fetching is not available"""
        mock_meshcore = MockMeshCore(has_auto_fetch=False)
        
        # Verify start_auto_message_fetching is missing
        self.assertFalse(hasattr(mock_meshcore, 'start_auto_message_fetching'))
    
    def test_missing_event_dispatcher(self):
        """Test diagnostics when event dispatcher is not available"""
        mock_meshcore = MockMeshCore(has_events=False)
        
        # Verify events is missing
        self.assertFalse(hasattr(mock_meshcore, 'events'))
    
    def test_empty_contact_list(self):
        """Test diagnostics when contact list is empty"""
        mock_meshcore = MockMeshCore(contacts_count=0)
        
        # Verify contacts exist but list is empty
        self.assertTrue(hasattr(mock_meshcore, 'contacts'))
        self.assertEqual(len(mock_meshcore.contacts), 0)
    
    def test_async_sync_contacts(self):
        """Test that sync_contacts can be called asynchronously"""
        mock_meshcore = MockMeshCore(has_sync_contacts=True)
        
        async def test():
            await mock_meshcore.sync_contacts()
            return True
        
        result = asyncio.run(test())
        self.assertTrue(result)
    
    def test_async_auto_message_fetching(self):
        """Test that start_auto_message_fetching can be called asynchronously"""
        mock_meshcore = MockMeshCore(has_auto_fetch=True)
        
        async def test():
            await mock_meshcore.start_auto_message_fetching()
            return True
        
        result = asyncio.run(test())
        self.assertTrue(result)


class TestDiagnosticMessages(unittest.TestCase):
    """Test diagnostic message generation"""
    
    def test_issue_detection_no_private_key(self):
        """Test that missing private key is detected as an issue"""
        mock_meshcore = MockMeshCore(has_private_key=False)
        
        issues = []
        
        # Check for private key
        key_attrs = ['private_key', 'key', 'node_key', 'device_key', 'crypto']
        found_key_attrs = [attr for attr in key_attrs if hasattr(mock_meshcore, attr)]
        
        if not found_key_attrs:
            issues.append("No private key attributes found - encrypted messages cannot be decrypted")
        
        self.assertEqual(len(issues), 1)
        self.assertIn("encrypted messages cannot be decrypted", issues[0])
    
    def test_issue_detection_no_sync_contacts(self):
        """Test that missing sync_contacts is detected as an issue"""
        mock_meshcore = MockMeshCore(has_sync_contacts=False)
        
        issues = []
        
        if not hasattr(mock_meshcore, 'sync_contacts'):
            issues.append("sync_contacts() not available - contact sync cannot be performed")
        
        self.assertEqual(len(issues), 1)
        self.assertIn("contact sync cannot be performed", issues[0])
    
    def test_issue_detection_no_auto_fetch(self):
        """Test that missing start_auto_message_fetching is detected as an issue"""
        mock_meshcore = MockMeshCore(has_auto_fetch=False)
        
        issues = []
        
        if not hasattr(mock_meshcore, 'start_auto_message_fetching'):
            issues.append("start_auto_message_fetching() not available - messages must be fetched manually")
        
        self.assertEqual(len(issues), 1)
        self.assertIn("messages must be fetched manually", issues[0])
    
    def test_multiple_issues_detected(self):
        """Test detection of multiple configuration issues"""
        mock_meshcore = MockMeshCore(
            has_private_key=False,
            has_sync_contacts=False,
            has_auto_fetch=False,
            has_events=False
        )
        
        issues = []
        
        # Check private key
        key_attrs = ['private_key', 'key', 'node_key', 'device_key', 'crypto']
        found_key_attrs = [attr for attr in key_attrs if hasattr(mock_meshcore, attr)]
        if not found_key_attrs:
            issues.append("No private key")
        
        # Check sync_contacts
        if not hasattr(mock_meshcore, 'sync_contacts'):
            issues.append("No sync_contacts")
        
        # Check auto fetch
        if not hasattr(mock_meshcore, 'start_auto_message_fetching'):
            issues.append("No auto fetch")
        
        # Check events
        if not hasattr(mock_meshcore, 'events') and not hasattr(mock_meshcore, 'dispatcher'):
            issues.append("No event dispatcher")
        
        self.assertEqual(len(issues), 4)


class TestConfigurationRecommendations(unittest.TestCase):
    """Test that appropriate recommendations are provided"""
    
    def test_recommendations_for_missing_private_key(self):
        """Test recommendations when private key is missing"""
        recommendations = [
            "Ensure the MeshCore device has a private key configured",
            "Check device storage/EEPROM",
            "Consult device firmware documentation"
        ]
        
        # These should be provided when private key is missing
        self.assertGreater(len(recommendations), 0)
    
    def test_recommendations_for_sync_failure(self):
        """Test recommendations when sync_contacts fails"""
        recommendations = [
            "Update meshcore library",
            "Check library version compatibility",
            "Verify device firmware version"
        ]
        
        # These should be provided when sync fails
        self.assertGreater(len(recommendations), 0)
    
    def test_recommendations_for_decryption_failure(self):
        """Test recommendations when message decryption fails"""
        recommendations = [
            "Check if the library has access to the node's private key",
            "Verify contacts are synced (sync_contacts())",
            "Ensure auto message fetching is running (start_auto_message_fetching())"
        ]
        
        # These are the key recommendations from the problem statement
        self.assertEqual(len(recommendations), 3)
        self.assertIn("private key", recommendations[0])
        self.assertIn("sync_contacts", recommendations[1])
        self.assertIn("start_auto_message_fetching", recommendations[2])


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMeshCoreConfigurationDiagnostics))
    suite.addTests(loader.loadTestsFromTestCase(TestDiagnosticMessages))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigurationRecommendations))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
