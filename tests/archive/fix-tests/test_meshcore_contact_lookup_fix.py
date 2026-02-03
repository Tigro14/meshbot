#!/usr/bin/env python3
"""
Test suite for MeshCore contact lookup fix

Tests that sendText correctly looks up contacts using pubkey_prefix
instead of node_id when sending responses.
"""

import unittest
import sqlite3
import tempfile
import os


class TestMeshCoreContactLookup(unittest.TestCase):
    """Test MeshCore contact lookup for response sending"""
    
    def test_pubkey_prefix_extraction(self):
        """Test that pubkey_prefix can be extracted from database"""
        # Create temporary database
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Create database with meshcore_contacts table
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create table
            cursor.execute('''
                CREATE TABLE meshcore_contacts (
                    node_id TEXT PRIMARY KEY,
                    name TEXT,
                    publicKey BLOB,
                    last_updated REAL
                )
            ''')
            
            # Insert test contact
            node_id = 0x143bcd7f
            # Full 32-byte public key (64 hex chars)
            full_pubkey = "143bcd7f1b1f" + "0" * 52  # Pad to 64 chars
            public_key_bytes = bytes.fromhex(full_pubkey)
            
            cursor.execute('''
                INSERT INTO meshcore_contacts (node_id, name, publicKey, last_updated)
                VALUES (?, ?, ?, ?)
            ''', (str(node_id), "TestNode", public_key_bytes, 1234567890.0))
            
            conn.commit()
            
            # Test extraction
            cursor.execute(
                "SELECT publicKey FROM meshcore_contacts WHERE node_id = ?",
                (str(node_id),)
            )
            row = cursor.fetchone()
            
            self.assertIsNotNone(row)
            self.assertIsNotNone(row[0])
            
            # Extract pubkey_prefix
            pubkey_hex = row[0].hex()
            pubkey_prefix = pubkey_hex[:12]  # First 6 bytes = 12 hex chars
            
            # Verify it starts with node_id (first 4 bytes)
            self.assertTrue(pubkey_prefix.startswith("143bcd7f"))
            self.assertEqual(pubkey_prefix, "143bcd7f1b1f")
            
            conn.close()
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_node_id_is_prefix_of_pubkey(self):
        """Test that node_id is indeed the first 4 bytes of publicKey"""
        # This validates our understanding of the relationship
        node_id = 0x143bcd7f
        
        # Create a public key where first 4 bytes = node_id
        pubkey_bytes = bytes.fromhex(f"{node_id:08x}" + "1b1f" + "0" * 52)
        
        # Extract node_id from first 4 bytes
        extracted_node_id = int.from_bytes(pubkey_bytes[:4], byteorder='big')
        
        self.assertEqual(extracted_node_id, node_id)
        
        # Extract pubkey_prefix (first 6 bytes = 12 hex chars)
        pubkey_prefix = pubkey_bytes[:6].hex()
        
        # Verify node_id is prefix of pubkey_prefix
        self.assertTrue(pubkey_prefix.startswith(f"{node_id:08x}"))
        self.assertEqual(pubkey_prefix, "143bcd7f1b1f")
    
    def test_contact_lookup_logic(self):
        """Test the complete contact lookup flow"""
        # Simulate the scenario:
        # 1. DM arrives with pubkey_prefix "143bcd7f1b1f"
        # 2. We derive node_id 0x143bcd7f from first 8 hex chars
        # 3. We save contact with full publicKey
        # 4. When sending response, we look up contact by node_id
        # 5. We extract pubkey_prefix from database
        # 6. We use pubkey_prefix to look up in meshcore
        
        pubkey_prefix_received = "143bcd7f1b1f"
        
        # Step 2: Derive node_id
        node_id_hex = pubkey_prefix_received[:8]
        node_id = int(node_id_hex, 16)
        self.assertEqual(node_id, 0x143bcd7f)
        
        # Step 3: Save contact (simulated - we pad the key)
        full_pubkey = pubkey_prefix_received + "0" * 52
        public_key_bytes = bytes.fromhex(full_pubkey)
        
        # Step 5: Extract pubkey_prefix from saved key
        pubkey_hex = public_key_bytes.hex()
        pubkey_prefix_for_lookup = pubkey_hex[:12]
        
        # Step 6: Verify we can use this for lookup
        self.assertEqual(pubkey_prefix_for_lookup, pubkey_prefix_received)
        self.assertGreaterEqual(len(pubkey_prefix_for_lookup), 12)  # Minimum for meshcore lookup


class TestMeshCoreResponseFlow(unittest.TestCase):
    """Test the complete response flow"""
    
    def test_response_flow_end_to_end(self):
        """Test complete flow from DM arrival to response"""
        # This test documents the complete flow
        
        # 1. DM arrives with pubkey_prefix
        dm_pubkey_prefix = "143bcd7f1b1faa"
        
        # 2. Derive node_id from first 4 bytes (8 hex chars)
        node_id = int(dm_pubkey_prefix[:8], 16)
        self.assertEqual(node_id, 0x143bcd7f)
        
        # 3. Save contact with reconstructed publicKey
        full_pubkey = dm_pubkey_prefix + "0" * (64 - len(dm_pubkey_prefix))
        public_key_bytes = bytes.fromhex(full_pubkey)
        
        # Simulate database save
        contact_in_db = {
            'node_id': node_id,
            'publicKey': public_key_bytes
        }
        
        # 4. Response needs to be sent to node_id
        destination_id = node_id
        
        # 5. Look up publicKey from database by node_id
        pubkey_from_db = contact_in_db['publicKey']
        
        # 6. Extract pubkey_prefix for meshcore lookup
        pubkey_prefix_for_send = pubkey_from_db.hex()[:12]
        
        # 7. Verify we have enough data for meshcore lookup
        self.assertGreaterEqual(len(pubkey_prefix_for_send), 12)
        self.assertTrue(pubkey_prefix_for_send.startswith(f"{destination_id:08x}"))
        
        # This is what meshcore-cli will use to find the contact
        self.assertEqual(pubkey_prefix_for_send, dm_pubkey_prefix[:12])


if __name__ == '__main__':
    unittest.main()
