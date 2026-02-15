#!/usr/bin/env python3
"""
Test pour vérifier l'extraction du sender ID depuis le préfixe du message
Bug: Messages d'autres utilisateurs étaient attribués au bot (0xFFFFFFFE)
Fix: Extrait le nom de l'utilisateur du préfixe et cherche son node ID
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import Mock, MagicMock, patch


class TestPublicChannelSenderExtraction(unittest.TestCase):
    """Test que les messages du canal public sont attribués au bon utilisateur"""
    
    def test_extract_sender_from_message_prefix(self):
        """Test extraction du nom d'utilisateur depuis le préfixe du message"""
        # Skip if meshcore-cli not available
        try:
            import meshcore
        except ImportError:
            print("⚠️  Skipping test (meshcore-cli not installed)")
            return
        
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        from node_manager import NodeManager
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper(port='/dev/null', debug=False)
        wrapper.meshcore = Mock()
        wrapper.meshcore.node_id = 0x87654321  # Bot's node ID
        wrapper.localNode.nodeNum = 0x87654321
        
        # Create mock node_manager with known nodes
        wrapper.node_manager = Mock()
        wrapper.node_manager.node_names = {
            0x12345678: {'name': 'Tigro'},      # User "Tigro"
            0x87654321: {'name': 'MyBot'},      # The bot itself
            0xABCDEF01: {'name': 'OtherUser'}   # Another user
        }
        
        # Mock message callback to capture the packet
        captured_packet = {}
        def capture_callback(packet, iface):
            captured_packet['packet'] = packet
        
        wrapper.message_callback = capture_callback
        
        # Create mock channel message event from user "Tigro"
        mock_event = Mock()
        mock_event.payload = {
            'type': 'CHAN',
            'text': 'Tigro: /echo qui est ce ?',  # Message from Tigro
            'channel_idx': 0
        }
        mock_event.sender_id = None  # Missing sender_id (typical for public channel)
        mock_event.attributes = {'channel_idx': 0}
        
        # Process the channel message
        wrapper._on_channel_message(mock_event)
        
        # Verify packet was created with correct sender ID
        self.assertIn('packet', captured_packet, "Packet should have been captured")
        packet = captured_packet['packet']
        
        # KEY FIX: sender ID should be Tigro's node ID (0x12345678), NOT bot's ID
        self.assertEqual(packet['from'], 0x12345678, 
                        f"Sender ID should be Tigro's ID (0x12345678), not bot's ID")
        self.assertNotEqual(packet['from'], 0x87654321, 
                           "Sender ID should NOT be bot's ID")
        self.assertNotEqual(packet['from'], 0xFFFFFFFF, 
                           "Sender ID should NOT be broadcast address")
        
        print("✅ Test Extraction Sender: Nom correctement extrait et résolu")
        print(f"   - Input: 'Tigro: /echo qui est ce ?'")
        print(f"   - Extracted: 'Tigro'")
        print(f"   - Resolved: 0x{packet['from']:08x} (Tigro's node ID)")
        print(f"   - NOT: 0x87654321 (bot's node ID)")
    
    def test_sender_not_in_database_uses_broadcast(self):
        """Test qu'un sender inconnu garde l'adresse broadcast"""
        # Skip if meshcore-cli not available
        try:
            import meshcore
        except ImportError:
            print("⚠️  Skipping test (meshcore-cli not installed)")
            return
        
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper(port='/dev/null', debug=False)
        wrapper.meshcore = Mock()
        wrapper.meshcore.node_id = 0x87654321
        wrapper.localNode.nodeNum = 0x87654321
        
        # Create mock node_manager with NO matching nodes
        wrapper.node_manager = Mock()
        wrapper.node_manager.node_names = {
            0x12345678: {'name': 'DifferentUser'},
            0x87654321: {'name': 'MyBot'}
        }
        
        # Mock message callback to capture the packet
        captured_packet = {}
        def capture_callback(packet, iface):
            captured_packet['packet'] = packet
        
        wrapper.message_callback = capture_callback
        
        # Create mock channel message event from unknown user
        mock_event = Mock()
        mock_event.payload = {
            'type': 'CHAN',
            'text': 'UnknownUser: /test message',  # User not in database
            'channel_idx': 0
        }
        mock_event.sender_id = None
        mock_event.attributes = {'channel_idx': 0}
        
        # Process the channel message
        wrapper._on_channel_message(mock_event)
        
        # Verify packet uses broadcast address for unknown sender
        self.assertIn('packet', captured_packet, "Packet should have been captured")
        packet = captured_packet['packet']
        
        # Unknown sender should keep broadcast address
        self.assertEqual(packet['from'], 0xFFFFFFFF, 
                        f"Unknown sender should use broadcast address (0xFFFFFFFF)")
        
        print("✅ Test Sender Inconnu: Broadcast address conservée")
        print(f"   - Input: 'UnknownUser: /test message'")
        print(f"   - Extracted: 'UnknownUser'")
        print(f"   - Not found in database")
        print(f"   - Result: 0xffffffff (broadcast address kept)")
    
    def test_bot_own_message_without_prefix(self):
        """Test que les propres messages du bot (sans préfixe) ne sont pas traités"""
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Create mock serial port
        mock_serial = Mock()
        mock_serial.is_open = True
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200, enable_read_loop=False)
        interface.serial = mock_serial
        interface.running = True
        
        # Set bot's node ID
        bot_node_id = 0x12345678
        interface.localNode.nodeNum = bot_node_id
        
        # Mock message callback to capture the packet
        captured_packet = {}
        def capture_callback(packet, iface):
            captured_packet['packet'] = packet
        
        interface.message_callback = capture_callback
        
        # Simulate receiving bot's own broadcast echo WITHOUT sender prefix
        # Bot sends: "test message" (no "Name: " prefix)
        # This should be attributed to the bot
        line = "DM:ffffffff:test message without prefix"
        interface._process_meshcore_line(line)
        
        # Verify packet was created with bot's node ID
        self.assertIn('packet', captured_packet, "Packet should have been captured")
        packet = captured_packet['packet']
        
        # Bot's own message (no prefix) should use bot's node ID
        self.assertEqual(packet['from'], bot_node_id, 
                        f"Bot's message should use bot's ID (0x{bot_node_id:08x})")
        
        print("✅ Test Message du Bot: Node ID du bot utilisé")
        print(f"   - Input: DM:ffffffff:test message without prefix")
        print(f"   - No sender prefix detected")
        print(f"   - Result: 0x{packet['from']:08x} (bot's node ID)")
    
    def test_other_user_message_with_prefix(self):
        """Test qu'un message d'autre utilisateur (avec préfixe) garde broadcast"""
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Create mock serial port
        mock_serial = Mock()
        mock_serial.is_open = True
        
        # Create interface with mock serial
        interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200, enable_read_loop=False)
        interface.serial = mock_serial
        interface.running = True
        
        # Set bot's node ID
        bot_node_id = 0x12345678
        interface.localNode.nodeNum = bot_node_id
        
        # Mock message callback to capture the packet
        captured_packet = {}
        def capture_callback(packet, iface):
            captured_packet['packet'] = packet
        
        interface.message_callback = capture_callback
        
        # Simulate receiving other user's message WITH sender prefix
        # Message: "OtherUser: /command" should keep broadcast address
        # The router will extract the real sender later
        line = "DM:ffffffff:OtherUser: /command"
        interface._process_meshcore_line(line)
        
        # Verify packet keeps broadcast address
        self.assertIn('packet', captured_packet, "Packet should have been captured")
        packet = captured_packet['packet']
        
        # Message with sender prefix should keep broadcast (for router to handle)
        self.assertEqual(packet['from'], 0xFFFFFFFF, 
                        f"Message with prefix should keep broadcast address")
        
        print("✅ Test Message Autre Utilisateur: Broadcast address conservée")
        print(f"   - Input: DM:ffffffff:OtherUser: /command")
        print(f"   - Sender prefix detected: 'OtherUser: '")
        print(f"   - Result: 0xffffffff (broadcast for router to handle)")


if __name__ == '__main__':
    print("=" * 80)
    print("TEST: Extraction du Sender ID depuis le préfixe du message")
    print("=" * 80)
    print("")
    print("Problème: Messages d'autres utilisateurs attribués au bot (0xFFFFFFFE)")
    print("Solution: Extraire nom depuis préfixe et chercher node ID dans la base")
    print("")
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
