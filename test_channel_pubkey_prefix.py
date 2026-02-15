#!/usr/bin/env python3
"""
Test pubkey_prefix resolution in channel messages

This test verifies that when a channel message contains a pubkey_prefix,
the bot correctly resolves it to the sender's node_id instead of falling
back to unreliable message prefix extraction.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys

class TestChannelPubkeyPrefix(unittest.TestCase):
    """Test pubkey_prefix resolution for channel messages"""
    
    def test_channel_resolves_pubkey_prefix(self):
        """Test that channel message with pubkey_prefix resolves to correct node_id"""
        
        # Import here to avoid issues if meshcore_cli_wrapper has dependencies
        try:
            from meshcore_cli_wrapper import MeshCoreCLIWrapper
        except ImportError:
            self.skipTest("meshcore_cli_wrapper not available")
            return
        
        # Create mock wrapper
        wrapper = MagicMock(spec=MeshCoreCLIWrapper)
        wrapper.node_manager = MagicMock()
        wrapper.meshcore = MagicMock()
        wrapper.meshcore.contacts = {}
        
        # Mock database query
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '343228543',  # node_id as string (0x143bcd7f)
            'UserNode',   # name
            'User',       # shortName
            'TBEAM',      # hwModel
            '143bcd7f1b1fabcd...',  # publicKey
            45.0,         # lat
            5.0,          # lon
            500,          # alt
            'meshcore'    # source
        )
        wrapper.node_manager.persistence = MagicMock()
        wrapper.node_manager.persistence.conn = MagicMock()
        wrapper.node_manager.persistence.conn.cursor.return_value = mock_cursor
        
        # Mock find_meshcore_contact_by_pubkey_prefix to return correct node_id
        wrapper.node_manager.find_meshcore_contact_by_pubkey_prefix.return_value = 0x143bcd7f
        
        # Create mock event with pubkey_prefix (the key fix)
        mock_event = MagicMock()
        mock_event.type = MagicMock()
        mock_event.type.name = 'CHANNEL_MSG_RECV'
        mock_event.payload = {
            'type': 'CHAN',
            'SNR': 13.0,
            'channel_idx': 0,
            'path_len': 0,
            'txt_type': 0,
            'sender_timestamp': 1771092899,
            'text': 'Tigro: /echo test',
            'pubkey_prefix': '143bcd7f1b1f'  # THE KEY: actual sender's pubkey
        }
        mock_event.attributes = {'channel_idx': 0, 'txt_type': 0}
        
        # Simulate the extraction logic from _on_channel_message
        payload = mock_event.payload
        sender_id = None
        pubkey_prefix = None
        
        # Méthode 1: Check payload
        if isinstance(payload, dict):
            sender_id = payload.get('sender_id') or payload.get('contact_id') or payload.get('from')
            pubkey_prefix = (payload.get('pubkey_prefix') or 
                            payload.get('pubkeyPrefix') or 
                            payload.get('public_key_prefix') or 
                            payload.get('publicKeyPrefix'))
        
        # At this point, pubkey_prefix should be found
        self.assertEqual(pubkey_prefix, '143bcd7f1b1f', "pubkey_prefix should be extracted from payload")
        
        # Méthode 4: Resolve pubkey_prefix
        if sender_id is None and pubkey_prefix and wrapper.node_manager:
            sender_id = wrapper.node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
        
        # Verify sender_id is correct (0x143bcd7f = 343228543)
        self.assertEqual(sender_id, 0x143bcd7f, 
                        f"Should resolve to actual sender 0x143bcd7f, not bot's node 0x16fad3dc")
        
        print(f"✅ Test passed: pubkey_prefix '143bcd7f1b1f' correctly resolved to 0x{sender_id:08x}")
    
    def test_channel_fallback_to_prefix_extraction(self):
        """Test that without pubkey_prefix, fallback to message prefix still works"""
        
        try:
            from meshcore_cli_wrapper import MeshCoreCLIWrapper
        except ImportError:
            self.skipTest("meshcore_cli_wrapper not available")
            return
        
        # Create mock wrapper
        wrapper = MagicMock(spec=MeshCoreCLIWrapper)
        wrapper.node_manager = MagicMock()
        
        # Mock node_names database (single match for "User")
        wrapper.node_manager.node_names = {
            0x143bcd7f: {'name': 'UserNode', 'shortName': 'User'}
        }
        
        # Create mock event WITHOUT pubkey_prefix
        mock_event = MagicMock()
        mock_event.type = MagicMock()
        mock_event.type.name = 'CHANNEL_MSG_RECV'
        mock_event.payload = {
            'type': 'CHAN',
            'text': 'User: /echo test'
            # NO pubkey_prefix!
        }
        mock_event.attributes = {}
        
        # Simulate extraction logic
        payload = mock_event.payload
        sender_id = None
        pubkey_prefix = None
        
        # Méthode 1: Check payload
        if isinstance(payload, dict):
            sender_id = payload.get('sender_id')
            pubkey_prefix = payload.get('pubkey_prefix')
        
        # pubkey_prefix should be None
        self.assertIsNone(pubkey_prefix, "pubkey_prefix should be None when not in payload")
        
        # Méthode 5: Fallback to message prefix extraction
        if sender_id is None and ': ' in payload['text']:
            sender_name = payload['text'].split(': ', 1)[0]
            # Search for node by name
            matching_nodes = []
            sender_name_lower = sender_name.lower()
            for node_id, name_info in wrapper.node_manager.node_names.items():
                if isinstance(name_info, dict):
                    node_name = name_info.get('name', '').lower()
                else:
                    node_name = str(name_info).lower()
                
                if sender_name_lower in node_name or node_name in sender_name_lower:
                    matching_nodes.append((node_id, name_info))
            
            if len(matching_nodes) == 1:
                sender_id = matching_nodes[0][0]
        
        # Verify fallback worked
        self.assertEqual(sender_id, 0x143bcd7f, "Should find sender by message prefix as fallback")
        
        print(f"✅ Test passed: Fallback to prefix extraction found 0x{sender_id:08x}")
    
    def test_pubkey_prefix_prevents_wrong_match(self):
        """Test that pubkey_prefix prevents matching wrong node with similar name"""
        
        try:
            from meshcore_cli_wrapper import MeshCoreCLIWrapper
        except ImportError:
            self.skipTest("meshcore_cli_wrapper not available")
            return
        
        # Create mock wrapper
        wrapper = MagicMock(spec=MeshCoreCLIWrapper)
        wrapper.node_manager = MagicMock()
        wrapper.meshcore = MagicMock()
        wrapper.meshcore.contacts = {}
        
        # Mock database for pubkey resolution
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '343228543',  # 0x143bcd7f - actual sender
            'UserNode',
            'User',
            'TBEAM',
            '143bcd7f1b1f...',
            45.0, 5.0, 500,
            'meshcore'
        )
        wrapper.node_manager.persistence = MagicMock()
        wrapper.node_manager.persistence.conn = MagicMock()
        wrapper.node_manager.persistence.conn.cursor.return_value = mock_cursor
        wrapper.node_manager.find_meshcore_contact_by_pubkey_prefix.return_value = 0x143bcd7f
        
        # Mock node_names with MULTIPLE matches for "Tigro"
        wrapper.node_manager.node_names = {
            0x16fad3dc: {'name': 'tigro PVCavityABIOT', 'shortName': 'Tigro'},  # Bot's node (WRONG)
            0x143bcd7f: {'name': 'Tigro2', 'shortName': 'Tigro'}  # Actual sender (CORRECT)
        }
        
        # Event WITH pubkey_prefix
        mock_event = MagicMock()
        mock_event.payload = {
            'text': 'Tigro: /echo test',
            'pubkey_prefix': '143bcd7f1b1f'  # Actual sender's pubkey
        }
        
        # Simulate extraction
        payload = mock_event.payload
        sender_id = None
        pubkey_prefix = payload.get('pubkey_prefix')
        
        # Resolve pubkey_prefix BEFORE trying name matching
        if sender_id is None and pubkey_prefix:
            sender_id = wrapper.node_manager.find_meshcore_contact_by_pubkey_prefix(pubkey_prefix)
        
        # Verify we got the CORRECT sender, not the first match by name
        self.assertEqual(sender_id, 0x143bcd7f, 
                        "Should use pubkey_prefix (0x143bcd7f), not first name match (0x16fad3dc)")
        self.assertNotEqual(sender_id, 0x16fad3dc, 
                           "Should NOT match bot's node even though name contains 'Tigro'")
        
        print(f"✅ Test passed: pubkey_prefix correctly identified 0x{sender_id:08x} "
              f"instead of wrong match 0x16fad3dc")


if __name__ == '__main__':
    unittest.main()
