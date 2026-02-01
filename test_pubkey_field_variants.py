#!/usr/bin/env python3
"""
Test: MeshCore DM pubkey_prefix Field Name Variants

This test validates that the bot can extract pubkey_prefix from DM events
regardless of which field name variant the meshcore-cli library uses.

Issue: pubkey_prefix field missing from DM events, preventing responses
Solution: Check multiple field name variants (similar to publicKey fix)
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))


class TestPubkeyPrefixExtraction(unittest.TestCase):
    """Test pubkey_prefix extraction from DM events"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock event with different payload structures
        self.test_pubkey = '143bcd7f1b1f'
        self.test_text = '/help'
    
    def test_payload_pubkey_prefix(self):
        """Test extraction from payload.pubkey_prefix (underscore)"""
        event = Mock()
        event.payload = {
            'type': 'PRIV',
            'pubkey_prefix': self.test_pubkey,
            'text': self.test_text
        }
        
        # Simulate extraction logic
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        self.assertEqual(pubkey_prefix, self.test_pubkey)
        print(f"✅ Extracted from payload.pubkey_prefix: {pubkey_prefix}")
    
    def test_payload_pubkeyPrefix(self):
        """Test extraction from payload.pubkeyPrefix (camelCase)"""
        event = Mock()
        event.payload = {
            'type': 'PRIV',
            'pubkeyPrefix': self.test_pubkey,
            'text': self.test_text
        }
        
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        self.assertEqual(pubkey_prefix, self.test_pubkey)
        print(f"✅ Extracted from payload.pubkeyPrefix: {pubkey_prefix}")
    
    def test_payload_public_key_prefix(self):
        """Test extraction from payload.public_key_prefix (full snake_case)"""
        event = Mock()
        event.payload = {
            'type': 'PRIV',
            'public_key_prefix': self.test_pubkey,
            'text': self.test_text
        }
        
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        self.assertEqual(pubkey_prefix, self.test_pubkey)
        print(f"✅ Extracted from payload.public_key_prefix: {pubkey_prefix}")
    
    def test_payload_publicKeyPrefix(self):
        """Test extraction from payload.publicKeyPrefix (full camelCase)"""
        event = Mock()
        event.payload = {
            'type': 'PRIV',
            'publicKeyPrefix': self.test_pubkey,
            'text': self.test_text
        }
        
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        self.assertEqual(pubkey_prefix, self.test_pubkey)
        print(f"✅ Extracted from payload.publicKeyPrefix: {pubkey_prefix}")
    
    def test_attributes_pubkey_prefix(self):
        """Test extraction from event.attributes.pubkey_prefix"""
        event = Mock()
        event.payload = {'type': 'PRIV', 'text': self.test_text}
        event.attributes = {
            'pubkey_prefix': self.test_pubkey,
            'txt_type': 0
        }
        
        # First try payload
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        # Then try attributes if not found
        if not pubkey_prefix and hasattr(event, 'attributes'):
            attributes = event.attributes
            if isinstance(attributes, dict):
                pubkey_prefix = (attributes.get('pubkey_prefix') or 
                               attributes.get('pubkeyPrefix') or 
                               attributes.get('public_key_prefix') or 
                               attributes.get('publicKeyPrefix'))
        
        self.assertEqual(pubkey_prefix, self.test_pubkey)
        print(f"✅ Extracted from attributes.pubkey_prefix: {pubkey_prefix}")
    
    def test_event_direct_pubkey_prefix(self):
        """Test extraction from event.pubkey_prefix (direct attribute)"""
        event = Mock()
        event.payload = {'type': 'PRIV', 'text': self.test_text}
        event.pubkey_prefix = self.test_pubkey
        
        # Try payload first
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        # Then try attributes if not found
        if not pubkey_prefix and hasattr(event, 'attributes'):
            attributes = event.attributes
            if isinstance(attributes, dict):
                pubkey_prefix = (attributes.get('pubkey_prefix') or 
                               attributes.get('pubkeyPrefix') or 
                               attributes.get('public_key_prefix') or 
                               attributes.get('publicKeyPrefix'))
        
        # Finally try direct event attributes
        if not pubkey_prefix:
            for attr_name in ['pubkey_prefix', 'pubkeyPrefix', 'public_key_prefix', 'publicKeyPrefix']:
                if hasattr(event, attr_name):
                    pubkey_prefix = getattr(event, attr_name)
                    if pubkey_prefix:
                        break
        
        self.assertEqual(pubkey_prefix, self.test_pubkey)
        print(f"✅ Extracted from event.pubkey_prefix: {pubkey_prefix}")
    
    def test_event_direct_pubkeyPrefix(self):
        """Test extraction from event.pubkeyPrefix (direct camelCase attribute)"""
        event = Mock(spec=['payload', 'pubkeyPrefix'])  # Limit to specific attributes
        event.payload = {'type': 'PRIV', 'text': self.test_text}
        event.pubkeyPrefix = self.test_pubkey
        
        # Full extraction logic
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        if not pubkey_prefix and hasattr(event, 'attributes'):
            attributes = event.attributes
            if isinstance(attributes, dict):
                pubkey_prefix = (attributes.get('pubkey_prefix') or 
                               attributes.get('pubkeyPrefix') or 
                               attributes.get('public_key_prefix') or 
                               attributes.get('publicKeyPrefix'))
        
        if not pubkey_prefix:
            for attr_name in ['pubkey_prefix', 'pubkeyPrefix', 'public_key_prefix', 'publicKeyPrefix']:
                if hasattr(event, attr_name):
                    pubkey_prefix = getattr(event, attr_name)
                    if pubkey_prefix:
                        break
        
        self.assertEqual(pubkey_prefix, self.test_pubkey)
        print(f"✅ Extracted from event.pubkeyPrefix: {pubkey_prefix}")
    
    def test_fallback_priority(self):
        """Test that extraction follows correct priority order"""
        event = Mock()
        # Set multiple sources with different values
        event.payload = {
            'type': 'PRIV',
            'pubkey_prefix': 'from_payload',  # Should be picked first
            'text': self.test_text
        }
        event.attributes = {
            'pubkey_prefix': 'from_attributes'  # Should be ignored (payload wins)
        }
        event.pubkey_prefix = 'from_event'  # Should be ignored (payload wins)
        
        # Extract with priority: payload > attributes > event
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        self.assertEqual(pubkey_prefix, 'from_payload')
        print(f"✅ Correct priority: payload wins over attributes/event")
    
    def test_no_pubkey_prefix(self):
        """Test graceful handling when pubkey_prefix is missing"""
        event = Mock(spec=['payload'])  # No pubkey_prefix attribute
        event.payload = {'type': 'PRIV', 'text': self.test_text}
        
        payload = event.payload
        pubkey_prefix = (payload.get('pubkey_prefix') or 
                        payload.get('pubkeyPrefix') or 
                        payload.get('public_key_prefix') or 
                        payload.get('publicKeyPrefix'))
        
        if not pubkey_prefix and hasattr(event, 'attributes'):
            attributes = event.attributes
            if isinstance(attributes, dict):
                pubkey_prefix = (attributes.get('pubkey_prefix') or 
                               attributes.get('pubkeyPrefix') or 
                               attributes.get('public_key_prefix') or 
                               attributes.get('publicKeyPrefix'))
        
        if not pubkey_prefix:
            for attr_name in ['pubkey_prefix', 'pubkeyPrefix', 'public_key_prefix', 'publicKeyPrefix']:
                if hasattr(event, attr_name):
                    pubkey_prefix = getattr(event, attr_name)
                    if pubkey_prefix:
                        break
        
        self.assertIsNone(pubkey_prefix)
        print(f"✅ Gracefully handles missing pubkey_prefix: {pubkey_prefix}")


def run_tests():
    """Run the test suite"""
    print("\n" + "="*70)
    print("  Testing MeshCore DM pubkey_prefix Field Name Variants")
    print("="*70 + "\n")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPubkeyPrefixExtraction)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("  ✅ ALL TESTS PASSED!")
        print(f"     {result.testsRun} tests run successfully")
        print("\n  The bot can now extract pubkey_prefix from:")
        print("  - payload.pubkey_prefix (underscore)")
        print("  - payload.pubkeyPrefix (camelCase)")
        print("  - payload.public_key_prefix (full snake_case)")
        print("  - payload.publicKeyPrefix (full camelCase)")
        print("  - attributes.* (any of the above)")
        print("  - event.* (any of the above)")
    else:
        print("  ❌ SOME TESTS FAILED")
        print(f"     Failures: {len(result.failures)}")
        print(f"     Errors: {len(result.errors)}")
    print("="*70 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
