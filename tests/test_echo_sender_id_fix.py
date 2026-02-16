#!/usr/bin/env python3
"""
Test pour vérifier que /echo affiche le bon sender ID pour les broadcasts MeshCore
Bug: Broadcast echo montre "ffff:" au lieu du vrai ID utilisateur
Fix: Remplace 0xFFFFFFFF par le node ID du bot lors du parsing
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import Mock, MagicMock, patch


class TestEchoSenderIdFix(unittest.TestCase):
    """Test que /echo broadcast affiche le bon sender ID"""
    
    def test_meshcore_serial_replaces_broadcast_sender_id(self):
        """Test que meshcore_serial_interface remplace 0xFFFFFFFF par le node ID du bot"""
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
        
        # Simulate receiving a broadcast echo: "DM:ffffffff:TestUser: test message"
        # This is what MeshCore returns when we send SEND_DM:ffffffff:message
        line = "DM:ffffffff:TestUser: test message"
        interface._process_meshcore_line(line)
        
        # Verify packet was created with correct sender ID
        self.assertIn('packet', captured_packet, "Packet should have been captured")
        packet = captured_packet['packet']
        
        # KEY FIX: sender ID should be bot's node ID, NOT 0xFFFFFFFF
        self.assertEqual(packet['from'], bot_node_id, 
                        f"Sender ID should be bot's ID (0x{bot_node_id:08x}), not broadcast address")
        self.assertNotEqual(packet['from'], 0xFFFFFFFF, 
                           "Sender ID should NOT be broadcast address")
        
        print("✅ Test MeshCore Serial: Broadcast sender ID correctement remplacé")
        print(f"   - Input: DM:ffffffff:message")
        print(f"   - Sender ID: 0x{packet['from']:08x} (bot's node ID)")
        print(f"   - NOT: 0xffffffff (broadcast address)")
    
    def test_meshcore_cli_replaces_broadcast_sender_id(self):
        """Test que meshcore_cli_wrapper remplace 0xFFFFFFFF par le node ID du bot"""
        # Skip this test if meshcore-cli is not available
        try:
            import meshcore
        except ImportError:
            print("⚠️  Skipping meshcore_cli_wrapper test (meshcore-cli not installed)")
            return
        
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create mock meshcore instance
        mock_meshcore = Mock()
        mock_meshcore.node_id = 0x87654321  # Bot's node ID
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper(port='/dev/null', debug=False)
        wrapper.meshcore = mock_meshcore
        wrapper.localNode.nodeNum = 0x87654321
        
        # Mock message callback to capture the packet
        captured_packet = {}
        def capture_callback(packet, iface):
            captured_packet['packet'] = packet
        
        wrapper.message_callback = capture_callback
        
        # Create mock channel message event with sender_id=0xFFFFFFFF
        mock_event = Mock()
        mock_event.payload = {
            'text': 'TestUser: broadcast message',
            'channel': 0
        }
        mock_event.sender_id = None  # Missing sender_id triggers 0xFFFFFFFF default
        
        # Process the channel message
        wrapper._on_channel_message(mock_event)
        
        # Verify packet was created with correct sender ID
        self.assertIn('packet', captured_packet, "Packet should have been captured")
        packet = captured_packet['packet']
        
        # KEY FIX: sender ID should be bot's node ID, NOT 0xFFFFFFFF
        self.assertEqual(packet['from'], 0x87654321, 
                        f"Sender ID should be bot's ID (0x87654321), not broadcast address")
        self.assertNotEqual(packet['from'], 0xFFFFFFFF, 
                           "Sender ID should NOT be broadcast address")
        
        print("✅ Test MeshCore CLI: Broadcast sender ID correctement remplacé")
        print(f"   - Input: CHANNEL_MSG_RECV with sender_id=None")
        print(f"   - Sender ID: 0x{packet['from']:08x} (bot's node ID)")
        print(f"   - NOT: 0xffffffff (broadcast address)")
    
    def test_direct_message_sender_id_unchanged(self):
        """Test que les messages directs (non-broadcast) gardent leur sender ID original"""
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
        
        # Simulate receiving a direct message from another node
        other_node_id = 0xABCDEF01
        line = f"DM:{other_node_id:08x}:Hello from another node"
        interface._process_meshcore_line(line)
        
        # Verify packet was created with ORIGINAL sender ID
        self.assertIn('packet', captured_packet, "Packet should have been captured")
        packet = captured_packet['packet']
        
        # Direct messages should keep their original sender ID
        self.assertEqual(packet['from'], other_node_id, 
                        f"Direct message sender ID should be original (0x{other_node_id:08x})")
        self.assertNotEqual(packet['from'], bot_node_id, 
                           "Direct message sender should NOT be replaced with bot's ID")
        
        print("✅ Test Messages Directs: Sender ID original préservé")
        print(f"   - Input: DM:{other_node_id:08x}:message")
        print(f"   - Sender ID: 0x{packet['from']:08x} (original sender)")
        print(f"   - NOT replaced with bot's ID")


if __name__ == '__main__':
    print("=" * 80)
    print("TEST: Fix sender ID pour broadcast /echo MeshCore")
    print("=" * 80)
    print("")
    print("Problème: /echo broadcast affiche 'ffff:' au lieu du vrai ID utilisateur")
    print("Solution: Remplacer 0xFFFFFFFF par le node ID du bot lors du parsing")
    print("")
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
