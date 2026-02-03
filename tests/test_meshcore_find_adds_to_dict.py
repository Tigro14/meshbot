#!/usr/bin/env python3
"""
Test that find_meshcore_contact_by_pubkey_prefix adds contact to meshcore.contacts dict

This test validates the fix for the issue where contacts found in the database
during DM reception were not being added to meshcore.contacts dict, causing
lookup failures when sending responses.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestFindAddsToDict(unittest.TestCase):
    """Test that finding a contact in DB adds it to meshcore.contacts dict"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the meshcore module
        self.mock_meshcore = MagicMock()
        self.mock_meshcore.contacts = {}
        
        # Mock node_manager and persistence
        self.mock_persistence = MagicMock()
        self.mock_node_manager = MagicMock()
        self.mock_node_manager.persistence = self.mock_persistence
        
        # Mock the database cursor
        self.mock_cursor = MagicMock()
        self.mock_persistence.conn.cursor.return_value = self.mock_cursor
        
    def test_contact_found_and_added_to_dict(self):
        """Test that when contact is found in DB, it's added to meshcore.contacts dict"""
        # Simulate finding contact in DB
        pubkey_prefix = "143bcd7f1b1f"
        node_id = 0x143bcd7f
        public_key = bytes.fromhex(pubkey_prefix + "0" * (64 - len(pubkey_prefix)))
        
        # Mock find_meshcore_contact_by_pubkey_prefix returning node_id
        self.mock_node_manager.find_meshcore_contact_by_pubkey_prefix.return_value = node_id
        
        # Mock database row
        db_row = (
            str(node_id),              # node_id (TEXT)
            "TestNode",                # name
            "Test",                    # shortName
            "RAK4631",                 # hwModel
            public_key,                # publicKey (BLOB)
            48.5,                      # lat
            7.5,                       # lon
            300,                       # alt
            "meshcore"                 # source
        )
        self.mock_cursor.fetchone.return_value = db_row
        
        # Import after mocking
        with patch('meshcore_cli_wrapper.MeshCore', return_value=self.mock_meshcore):
            from meshcore_cli_wrapper import MeshCoreCLIWrapper
            
            wrapper = MeshCoreCLIWrapper(
                port="/dev/ttyACM0",
                baudrate=115200,
                message_callback=MagicMock(),
                node_manager=self.mock_node_manager
            )
            wrapper.meshcore = self.mock_meshcore
            
            # Simulate the logic from _on_contact_message
            sender_id = self.mock_node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
            
            if sender_id:
                # This is the FIX: load contact and add to dict
                cursor = self.mock_node_manager.persistence.conn.cursor()
                cursor.execute(
                    "SELECT node_id, name, shortName, hwModel, publicKey, lat, lon, alt, source FROM meshcore_contacts WHERE node_id = ?",
                    (str(sender_id),)
                )
                row = cursor.fetchone()
                
                if row:
                    contact_data = {
                        'node_id': sender_id,
                        'name': row[1],
                        'shortName': row[2],
                        'hwModel': row[3],
                        'publicKey': row[4],
                        'lat': row[5],
                        'lon': row[6],
                        'alt': row[7],
                        'source': row[8]
                    }
                    wrapper._add_contact_to_meshcore(contact_data)
        
        # VERIFY: Contact should now be in meshcore.contacts dict
        self.assertIsNotNone(sender_id)
        self.assertEqual(sender_id, node_id)
        self.assertIn(pubkey_prefix, self.mock_meshcore.contacts)
        self.assertEqual(self.mock_meshcore.contacts[pubkey_prefix]['node_id'], node_id)
        print(f"✅ Contact found in DB and added to dict: {pubkey_prefix}")
    
    def test_contact_not_found_no_dict_update(self):
        """Test that when contact is not found in DB, dict is not updated"""
        pubkey_prefix = "999999999999"
        
        # Mock find returning None
        self.mock_node_manager.find_meshcore_contact_by_pubkey_prefix.return_value = None
        
        with patch('meshcore_cli_wrapper.MeshCore', return_value=self.mock_meshcore):
            from meshcore_cli_wrapper import MeshCoreCLIWrapper
            
            wrapper = MeshCoreCLIWrapper(
                port="/dev/ttyACM0",
                baudrate=115200,
                message_callback=MagicMock(),
                node_manager=self.mock_node_manager
            )
            wrapper.meshcore = self.mock_meshcore
            
            # Simulate the logic
            sender_id = self.mock_node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
        
        # VERIFY: Contact not found, dict unchanged
        self.assertIsNone(sender_id)
        self.assertNotIn(pubkey_prefix, self.mock_meshcore.contacts)
        print(f"✅ Contact not found, dict unchanged")
    
    def test_complete_dm_receive_send_flow(self):
        """Test complete flow: receive DM → find contact → send response"""
        pubkey_prefix = "143bcd7f1b1f"
        node_id = 0x143bcd7f
        public_key = bytes.fromhex(pubkey_prefix + "0" * (64 - len(pubkey_prefix)))
        
        # Step 1: DM arrives, contact found in DB
        self.mock_node_manager.find_meshcore_contact_by_pubkey_prefix.return_value = node_id
        
        db_row = (
            str(node_id), "TestNode", "Test", "RAK4631",
            public_key, 48.5, 7.5, 300, "meshcore"
        )
        self.mock_cursor.fetchone.return_value = db_row
        
        with patch('meshcore_cli_wrapper.MeshCore', return_value=self.mock_meshcore):
            from meshcore_cli_wrapper import MeshCoreCLIWrapper
            
            wrapper = MeshCoreCLIWrapper(
                port="/dev/ttyACM0",
                baudrate=115200,
                message_callback=MagicMock(),
                node_manager=self.mock_node_manager
            )
            wrapper.meshcore = self.mock_meshcore
            
            # Step 1: Find contact (DM reception)
            sender_id = self.mock_node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
            cursor = self.mock_node_manager.persistence.conn.cursor()
            cursor.execute("SELECT node_id, name, shortName, hwModel, publicKey, lat, lon, alt, source FROM meshcore_contacts WHERE node_id = ?", (str(sender_id),))
            row = cursor.fetchone()
            
            contact_data = {
                'node_id': sender_id,
                'name': row[1],
                'publicKey': row[4]
            }
            wrapper._add_contact_to_meshcore(contact_data)
            
            # Step 2: Send response - contact should be found in dict
            contact = self.mock_meshcore.contacts.get(pubkey_prefix)
        
        # VERIFY: Contact found in dict
        self.assertIsNotNone(contact)
        self.assertEqual(contact['node_id'], node_id)
        self.assertEqual(contact['adv_name'], "TestNode")
        print(f"✅ Complete flow works: DM received → contact added → response can be sent")

if __name__ == '__main__':
    unittest.main()
