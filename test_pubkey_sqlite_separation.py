#!/usr/bin/env python3
"""
Test suite for separate Meshtastic and MeshCore node tables in SQLite
"""

import unittest
import tempfile
import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from traffic_persistence import TrafficPersistence
from node_manager import NodeManager


class TestPubkeySQLiteSeparation(unittest.TestCase):
    """Test separation of Meshtastic and MeshCore nodes in SQLite"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.persistence = TrafficPersistence(self.db_path)
        self.node_manager = NodeManager()
        self.node_manager.persistence = self.persistence
    
    def tearDown(self):
        """Clean up temporary database"""
        if self.persistence:
            self.persistence.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_meshtastic_nodes_table_exists(self):
        """Test that meshtastic_nodes table exists"""
        cursor = self.persistence.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meshtastic_nodes'")
        result = cursor.fetchone()
        self.assertIsNotNone(result, "meshtastic_nodes table should exist")
        print("✅ test_meshtastic_nodes_table_exists")
    
    def test_meshcore_contacts_table_exists(self):
        """Test that meshcore_contacts table exists"""
        cursor = self.persistence.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meshcore_contacts'")
        result = cursor.fetchone()
        self.assertIsNotNone(result, "meshcore_contacts table should exist")
        print("✅ test_meshcore_contacts_table_exists")
    
    def test_save_meshtastic_node(self):
        """Test saving a Meshtastic node"""
        node_data = {
            'node_id': 0x0de3331e,
            'name': 'MeshtasticNode1',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f\x00\x00' * 4,  # 32 bytes
            'shortName': 'MN1',
            'hwModel': 'TBEAM',
            'source': 'radio'
        }
        
        self.persistence.save_meshtastic_node(node_data)
        
        # Verify it's in the database
        cursor = self.persistence.conn.cursor()
        cursor.execute("SELECT * FROM meshtastic_nodes WHERE node_id=?", (str(node_data['node_id']),))
        result = cursor.fetchone()
        
        self.assertIsNotNone(result, "Node should be saved")
        self.assertEqual(result['name'], 'MeshtasticNode1')
        print("✅ test_save_meshtastic_node")
    
    def test_save_meshcore_contact(self):
        """Test saving a MeshCore contact"""
        contact_data = {
            'node_id': 0x1234abcd,
            'name': 'MeshCoreContact1',
            'publicKey': b'\xa1\xb2\xc3\xd4\xe5\xf6\x00\x00' * 4,  # 32 bytes
            'shortName': 'MC1',
            'hwModel': 'RAK4631',
            'source': 'meshcore'
        }
        
        self.persistence.save_meshcore_contact(contact_data)
        
        # Verify it's in the database
        cursor = self.persistence.conn.cursor()
        cursor.execute("SELECT * FROM meshcore_contacts WHERE node_id=?", (str(contact_data['node_id']),))
        result = cursor.fetchone()
        
        self.assertIsNotNone(result, "Contact should be saved")
        self.assertEqual(result['name'], 'MeshCoreContact1')
        print("✅ test_save_meshcore_contact")
    
    def test_find_node_by_pubkey_in_meshtastic(self):
        """Test finding a node by pubkey in Meshtastic table"""
        # Save a Meshtastic node
        node_data = {
            'node_id': 0x0de3331e,
            'name': 'TestNode',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f\x00\x00' * 4,
            'source': 'radio'
        }
        self.persistence.save_meshtastic_node(node_data)
        
        # Search for it
        pubkey_prefix = '143bcd7f1b1f'
        found_id, source = self.node_manager.find_node_by_pubkey_prefix_in_db(pubkey_prefix)
        
        self.assertIsNotNone(found_id, "Node should be found")
        self.assertEqual(found_id, 0x0de3331e)
        self.assertEqual(source, 'meshtastic')
        print("✅ test_find_node_by_pubkey_in_meshtastic")
    
    def test_find_node_by_pubkey_in_meshcore(self):
        """Test finding a node by pubkey in MeshCore table"""
        # Save a MeshCore contact
        contact_data = {
            'node_id': 0x1234abcd,
            'name': 'TestContact',
            'publicKey': b'\xa1\xb2\xc3\xd4\xe5\xf6\x00\x00' * 4,
            'source': 'meshcore'
        }
        self.persistence.save_meshcore_contact(contact_data)
        
        # Search for it
        pubkey_prefix = 'a1b2c3d4e5f6'
        found_id, source = self.node_manager.find_node_by_pubkey_prefix_in_db(pubkey_prefix)
        
        self.assertIsNotNone(found_id, "Contact should be found")
        self.assertEqual(found_id, 0x1234abcd)
        self.assertEqual(source, 'meshcore')
        print("✅ test_find_node_by_pubkey_in_meshcore")
    
    def test_find_node_searches_both_tables(self):
        """Test that find_node_by_pubkey_prefix searches both tables"""
        # Save one in each table
        meshtastic_node = {
            'node_id': 0x0de3331e,
            'name': 'MeshtasticNode',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f\x00\x00' * 4,
            'source': 'radio'
        }
        self.persistence.save_meshtastic_node(meshtastic_node)
        
        meshcore_contact = {
            'node_id': 0x1234abcd,
            'name': 'MeshCoreContact',
            'publicKey': b'\xa1\xb2\xc3\xd4\xe5\xf6\x00\x00' * 4,
            'source': 'meshcore'
        }
        self.persistence.save_meshcore_contact(meshcore_contact)
        
        # Search for Meshtastic node
        found_id1, source1 = self.node_manager.find_node_by_pubkey_prefix_in_db('143bcd7f1b1f')
        self.assertEqual(found_id1, 0x0de3331e)
        self.assertEqual(source1, 'meshtastic')
        
        # Search for MeshCore contact
        found_id2, source2 = self.node_manager.find_node_by_pubkey_prefix_in_db('a1b2c3d4e5f6')
        self.assertEqual(found_id2, 0x1234abcd)
        self.assertEqual(source2, 'meshcore')
        
        print("✅ test_find_node_searches_both_tables")
    
    def test_no_cross_contamination(self):
        """Test that Meshtastic and MeshCore tables remain separate"""
        # Save nodes in both tables
        meshtastic_node = {
            'node_id': 0x0de3331e,
            'name': 'MeshtasticNode',
            'publicKey': b'\x14\x3b\xcd\x7f\x1b\x1f\x00\x00' * 4,
            'source': 'radio'
        }
        self.persistence.save_meshtastic_node(meshtastic_node)
        
        meshcore_contact = {
            'node_id': 0x1234abcd,
            'name': 'MeshCoreContact',
            'publicKey': b'\xa1\xb2\xc3\xd4\xe5\xf6\x00\x00' * 4,
            'source': 'meshcore'
        }
        self.persistence.save_meshcore_contact(meshcore_contact)
        
        # Verify Meshtastic table only has Meshtastic node
        cursor = self.persistence.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM meshtastic_nodes")
        meshtastic_count = cursor.fetchone()['count']
        self.assertEqual(meshtastic_count, 1)
        
        # Verify MeshCore table only has MeshCore contact
        cursor.execute("SELECT COUNT(*) as count FROM meshcore_contacts")
        meshcore_count = cursor.fetchone()['count']
        self.assertEqual(meshcore_count, 1)
        
        print("✅ test_no_cross_contamination")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing SQLite Separation: Meshtastic vs MeshCore Nodes")
    print("=" * 60)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPubkeySQLiteSeparation)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print(f"✅ ALL TESTS PASSED!")
        print(f"   {result.testsRun} tests run successfully")
    else:
        print(f"❌ SOME TESTS FAILED")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
    print("=" * 60)
    
    sys.exit(0 if result.wasSuccessful() else 1)
