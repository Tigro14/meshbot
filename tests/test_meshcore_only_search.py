#!/usr/bin/env python3
"""
Test MeshCore-only pubkey search functionality

This tests that DM pubkey resolution searches ONLY meshcore_contacts,
not meshtastic_nodes.
"""

import unittest
import sqlite3
import tempfile
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simple mock config for tests
class Config:
    DEBUG_MODE = False

# Mock utils before importing traffic_persistence
import sys
sys.modules['config'] = Config

def debug_print(msg):
    pass

def info_print(msg):
    pass

def error_print(msg):
    pass

sys.modules['utils'] = sys.modules[__name__]

from traffic_persistence import TrafficPersistence


class TestMeshCoreOnlySearch(unittest.TestCase):
    def setUp(self):
        """Create temporary database for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.persistence = TrafficPersistence(self.db_path)
    
    def tearDown(self):
        """Clean up temporary database"""
        self.persistence.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_meshcore_only_search_finds_meshcore_contact(self):
        """Test that meshcore-only search finds contacts in meshcore_contacts table"""
        # Save a MeshCore contact with publicKey
        pubkey_bytes = bytes.fromhex('143bcd7f1b1f0000111122223333444455556666777788889999aaaabbbbcccc')
        node_data = {
            'node_id': '233238302',  # 0x0de3331e
            'name': 'MeshCoreContact',
            'publicKey': pubkey_bytes
        }
        self.persistence.save_meshcore_contact(node_data)
        
        # Search using meshcore-only method
        found_id = self.persistence.find_meshcore_contact_by_pubkey_prefix('143bcd7f1b1f')
        
        # Should find the contact
        self.assertIsNotNone(found_id)
        self.assertEqual(found_id, 233238302)
        print("✅ PASS: MeshCore-only search found contact in meshcore_contacts")
    
    def test_meshcore_only_search_ignores_meshtastic_nodes(self):
        """Test that meshcore-only search IGNORES nodes in meshtastic_nodes table"""
        # Save a Meshtastic node with the same publicKey
        pubkey_bytes = bytes.fromhex('143bcd7f1b1f0000111122223333444455556666777788889999aaaabbbbcccc')
        node_data = {
            'node_id': '305419896',  # 0x12345678 - different ID
            'name': 'MeshtasticNode',
            'publicKey': pubkey_bytes
        }
        self.persistence.save_meshtastic_node(node_data)
        
        # Search using meshcore-only method
        found_id = self.persistence.find_meshcore_contact_by_pubkey_prefix('143bcd7f1b1f')
        
        # Should NOT find the Meshtastic node
        self.assertIsNone(found_id)
        print("✅ PASS: MeshCore-only search ignored meshtastic_nodes table")
    
    def test_meshcore_only_search_empty_table(self):
        """Test meshcore-only search when meshcore_contacts is empty"""
        # Don't add any contacts
        
        # Search using meshcore-only method
        found_id = self.persistence.find_meshcore_contact_by_pubkey_prefix('143bcd7f1b1f')
        
        # Should return None
        self.assertIsNone(found_id)
        print("✅ PASS: MeshCore-only search returns None when table is empty")
    
    def test_meshcore_only_vs_both_tables_search(self):
        """Test difference between meshcore-only and both-tables search"""
        # Add a node to each table with different pubkey prefixes
        pubkey1 = bytes.fromhex('143bcd7f1b1f0000111122223333444455556666777788889999aaaabbbbcccc')
        pubkey2 = bytes.fromhex('a1b2c3d4e5f60000111122223333444455556666777788889999aaaabbbbcccc')
        
        # Meshtastic node with prefix '143bcd...'
        node_data1 = {
            'node_id': '305419896',
            'name': 'MeshtasticNode',
            'publicKey': pubkey1
        }
        self.persistence.save_meshtastic_node(node_data1)
        
        # MeshCore contact with prefix 'a1b2c3...'
        node_data2 = {
            'node_id': '233238302',
            'name': 'MeshCoreContact',
            'publicKey': pubkey2
        }
        self.persistence.save_meshcore_contact(node_data2)
        
        # Search for '143bcd...' prefix
        # meshcore-only should NOT find it (only in meshtastic_nodes)
        found_meshcore_only = self.persistence.find_meshcore_contact_by_pubkey_prefix('143bcd7f1b1f')
        self.assertIsNone(found_meshcore_only)
        print("✅ PASS: MeshCore-only search does NOT find meshtastic nodes")
        
        # both-tables search SHOULD find it
        found_both, source = self.persistence.find_node_by_pubkey_prefix('143bcd7f1b1f')
        self.assertIsNotNone(found_both)
        self.assertEqual(found_both, 305419896)
        self.assertEqual(source, 'meshtastic')
        print("✅ PASS: Both-tables search finds meshtastic nodes")
        
        # Search for 'a1b2c3...' prefix
        # meshcore-only SHOULD find it
        found_meshcore_only2 = self.persistence.find_meshcore_contact_by_pubkey_prefix('a1b2c3d4e5f6')
        self.assertIsNotNone(found_meshcore_only2)
        self.assertEqual(found_meshcore_only2, 233238302)
        print("✅ PASS: MeshCore-only search finds meshcore contacts")
        
        # both-tables search also finds it
        found_both2, source2 = self.persistence.find_node_by_pubkey_prefix('a1b2c3d4e5f6')
        self.assertIsNotNone(found_both2)
        self.assertEqual(found_both2, 233238302)
        self.assertEqual(source2, 'meshcore')
        print("✅ PASS: Both-tables search also finds meshcore contacts")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing MeshCore-Only Pubkey Search")
    print("=" * 60)
    print()
    
    # Run tests
    unittest.main(verbosity=2)
