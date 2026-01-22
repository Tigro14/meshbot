#!/usr/bin/env python3
"""
Test suite for node_names.json to SQLite migration
Tests that node data is properly stored and retrieved from SQLite
"""

import unittest
import tempfile
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from traffic_persistence import TrafficPersistence
from node_manager import NodeManager


class TestNodeSQLiteMigration(unittest.TestCase):
    """Test NodeManager SQLite integration"""
    
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
    
    def test_load_nodes_from_empty_sqlite(self):
        """Test loading nodes from empty SQLite database"""
        self.node_manager.load_nodes_from_sqlite()
        self.assertEqual(len(self.node_manager.node_names), 0, "Should have no nodes in empty database")
        print("✅ test_load_nodes_from_empty_sqlite")
    
    def test_save_and_load_node(self):
        """Test saving a node to SQLite and loading it back"""
        # Save a node directly to SQLite
        node_data = {
            'node_id': 0x0de3331e,
            'name': 'TestNode1',
            'shortName': 'TN1',
            'hwModel': 'TBEAM',
            'publicKey': b'\x14\x3b\xcd\x7f' * 8,  # 32 bytes
            'lat': 47.1234,
            'lon': 6.5678,
            'alt': 500
        }
        
        self.persistence.save_meshtastic_node(node_data)
        
        # Load nodes from SQLite
        self.node_manager.load_nodes_from_sqlite()
        
        # Check that the node was loaded
        self.assertIn(node_data['node_id'], self.node_manager.node_names)
        loaded_node = self.node_manager.node_names[node_data['node_id']]
        self.assertEqual(loaded_node['name'], 'TestNode1')
        self.assertEqual(loaded_node['shortName'], 'TN1')
        self.assertEqual(loaded_node['hwModel'], 'TBEAM')
        self.assertEqual(loaded_node['lat'], 47.1234)
        self.assertEqual(loaded_node['lon'], 6.5678)
        self.assertEqual(loaded_node['alt'], 500)
        print("✅ test_save_and_load_node")
    
    def test_get_node_name_from_sqlite(self):
        """Test getting node name from SQLite on cache miss"""
        # Save a node directly to SQLite (bypassing cache)
        node_data = {
            'node_id': 0x12345678,
            'name': 'CachedNode',
            'shortName': 'CN',
            'hwModel': 'HELTEC',
        }
        
        self.persistence.save_meshtastic_node(node_data)
        
        # Don't load nodes, so cache is empty
        # get_node_name should query SQLite
        name = self.node_manager.get_node_name(0x12345678)
        
        self.assertEqual(name, 'CachedNode')
        # Node should now be in cache
        self.assertIn(0x12345678, self.node_manager.node_names)
        print("✅ test_get_node_name_from_sqlite")
    
    def test_get_node_name_fallback(self):
        """Test fallback name generation for unknown nodes"""
        # Get name for non-existent node
        name = self.node_manager.get_node_name(0xABCDEF01)
        
        # Should return formatted hex name
        self.assertEqual(name, 'Node-abcdef01')
        print("✅ test_get_node_name_fallback")
    
    def test_multiple_nodes(self):
        """Test loading multiple nodes from SQLite"""
        # Save multiple nodes
        nodes = [
            {'node_id': 0x11111111, 'name': 'Node1', 'shortName': 'N1', 'hwModel': 'TBEAM'},
            {'node_id': 0x22222222, 'name': 'Node2', 'shortName': 'N2', 'hwModel': 'HELTEC'},
            {'node_id': 0x33333333, 'name': 'Node3', 'shortName': 'N3', 'hwModel': 'RAK'},
        ]
        
        for node_data in nodes:
            self.persistence.save_meshtastic_node(node_data)
        
        # Load nodes from SQLite
        self.node_manager.load_nodes_from_sqlite()
        
        # Verify all nodes were loaded
        self.assertEqual(len(self.node_manager.node_names), 3)
        for node_data in nodes:
            self.assertIn(node_data['node_id'], self.node_manager.node_names)
            loaded = self.node_manager.node_names[node_data['node_id']]
            self.assertEqual(loaded['name'], node_data['name'])
        
        print("✅ test_multiple_nodes")
    
    def test_get_node_by_id(self):
        """Test TrafficPersistence.get_node_by_id() method"""
        # Save a node
        node_data = {
            'node_id': 0xABCD1234,
            'name': 'DirectQueryNode',
            'shortName': 'DQN',
            'hwModel': 'RAK4631',
            'lat': 48.5,
            'lon': 7.5,
            'alt': 300
        }
        
        self.persistence.save_meshtastic_node(node_data)
        
        # Query directly via persistence
        result = self.persistence.get_node_by_id(0xABCD1234)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'DirectQueryNode')
        self.assertEqual(result['lat'], 48.5)
        print("✅ test_get_node_by_id")
    
    def test_get_all_meshtastic_nodes(self):
        """Test TrafficPersistence.get_all_meshtastic_nodes() method"""
        # Save multiple nodes
        nodes = [
            {'node_id': 0xAAA00001, 'name': 'AllNode1'},
            {'node_id': 0xAAA00002, 'name': 'AllNode2'},
            {'node_id': 0xAAA00003, 'name': 'AllNode3'},
        ]
        
        for node_data in nodes:
            self.persistence.save_meshtastic_node(node_data)
        
        # Get all nodes
        all_nodes = self.persistence.get_all_meshtastic_nodes()
        
        self.assertEqual(len(all_nodes), 3)
        for node_data in nodes:
            self.assertIn(node_data['node_id'], all_nodes)
        
        print("✅ test_get_all_meshtastic_nodes")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
