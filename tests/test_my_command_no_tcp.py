#!/usr/bin/env python3
"""
Test /my command NO TCP dependency
==================================

Verify that:
1. /my command uses local rx_history (no TCP)
2. /my works for both Meshtastic and MeshCore
3. /my is NOT in meshtastic_only_commands list
4. No dependency on REMOTE_NODE_HOST
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestMyCommandNoTCP(unittest.TestCase):
    
    def test_my_not_in_meshtastic_only_commands(self):
        """Test that /my is not blocked for MeshCore"""
        print("\n🧪 Test 1: Vérifier que /my n'est PAS dans meshtastic_only_commands")
        
        # Import message_router
        from handlers.message_router import MessageRouter
        
        # Create mock dependencies
        mock_sender = Mock()
        mock_handler = Mock()
        
        router = MessageRouter(
            ai_handler=mock_handler,
            network_handler=mock_handler,
            system_handler=mock_handler,
            stats_handler=mock_handler,
            mesh_handler=mock_handler,
            utility_handler=mock_handler,
            sender=mock_sender,
            context_manager=Mock(),
            node_manager=Mock()
        )
        
        # Read the source code to check
        import inspect
        source = inspect.getsource(router.process_text_message)
        
        # Find meshtastic_only_commands definition
        if 'meshtastic_only_commands' in source:
            # Extract the list
            start = source.find('meshtastic_only_commands = [')
            end = source.find(']', start)
            commands_line = source[start:end+1]
            
            print(f"  Commands line: {commands_line}")
            
            # Check /my is NOT in the list
            if "'/my'" not in commands_line and '"/my"' not in commands_line:
                print("  ✅ /my NOT in meshtastic_only_commands")
                print("  ✅ MeshCore can now use /my command")
            else:
                self.fail("❌ /my is still in meshtastic_only_commands list")
        else:
            self.fail("❌ meshtastic_only_commands not found in code")
    
    def test_my_command_uses_local_data(self):
        """Test that handle_my uses node_manager.rx_history (no TCP)"""
        print("\n🧪 Test 2: Vérifier que handle_my utilise rx_history local")
        
        from handlers.command_handlers.network_commands import NetworkCommands
        
        # Create mock dependencies
        mock_remote_client = Mock()
        mock_sender = Mock()
        mock_node_manager = Mock()
        
        # Setup rx_history with test data
        test_node_id = 0x12345678
        mock_node_manager.rx_history = {
            test_node_id: {
                'snr': 8.5,
                'last_time': 1234567890,
                'count': 5
            }
        }
        mock_node_manager.node_names = {}
        mock_node_manager.get_node_name = Mock(return_value="TestNode")
        mock_node_manager.get_node_distance = Mock(return_value=None)
        
        network_cmd = NetworkCommands(
            remote_nodes_client=mock_remote_client,
            sender=mock_sender,
            node_manager=mock_node_manager
        )
        
        # Read the source code
        import inspect
        source = inspect.getsource(network_cmd.handle_my)
        
        print("  Checking handle_my implementation:")
        
        # Check for local data usage
        checks = [
            ("rx_history" in source, "✅ Uses rx_history"),
            ("node_names" in source, "✅ Uses node_names"),
            ("get_remote_nodes" not in source, "✅ NO get_remote_nodes call"),
            ("REMOTE_NODE_HOST" not in source, "✅ NO REMOTE_NODE_HOST dependency"),
            ("Local" in source or "local" in source, "✅ Uses local data"),
        ]
        
        all_passed = True
        for check, msg in checks:
            if check:
                print(f"  {msg}")
            else:
                print(f"  ❌ Check failed: {msg}")
                all_passed = False
        
        self.assertTrue(all_passed, "Some checks failed")
    
    def test_my_command_works_without_tcp_config(self):
        """Test that /my works even without REMOTE_NODE_HOST configured"""
        print("\n🧪 Test 3: Vérifier que /my fonctionne sans REMOTE_NODE_HOST")
        
        from handlers.command_handlers.network_commands import NetworkCommands
        
        # Create network commands WITHOUT setting REMOTE_NODE_HOST
        mock_remote_client = Mock()
        mock_sender = Mock()
        mock_sender.send_single = Mock()
        mock_sender.log_conversation = Mock()
        
        mock_node_manager = Mock()
        test_node_id = 0xAABBCCDD
        mock_node_manager.rx_history = {
            test_node_id: {
                'snr': 12.0,
                'last_time': 1234567890,
                'count': 3
            }
        }
        mock_node_manager.node_names = {
            test_node_id: {
                'name': 'TestNode',
                'last_update': 1234567890
            }
        }
        mock_node_manager.get_node_name = Mock(return_value="TestNode")
        mock_node_manager.get_node_distance = Mock(return_value=None)
        
        network_cmd = NetworkCommands(
            remote_nodes_client=mock_remote_client,
            sender=mock_sender,
            node_manager=mock_node_manager
        )
        
        # Simulate /my command
        sender_info = {'name': 'TestNode'}
        
        # Call handle_my
        try:
            network_cmd.handle_my(test_node_id, sender_info, is_broadcast=False)
            
            # Give thread time to execute
            import time
            time.sleep(0.2)
            
            # Check that send_single was called (response sent)
            self.assertTrue(mock_sender.send_single.called, 
                          "send_single should be called")
            
            # Check that NO TCP connection was made
            self.assertFalse(mock_remote_client.get_remote_nodes.called,
                           "Should NOT call get_remote_nodes (TCP)")
            
            print("  ✅ /my command executed successfully")
            print("  ✅ NO TCP connection created")
            print("  ✅ Response sent via send_single")
            
        except Exception as e:
            self.fail(f"❌ /my command failed: {e}")
    
    def test_format_my_response_local(self):
        """Test that _format_my_response works with local data format"""
        print("\n🧪 Test 4: Vérifier que _format_my_response fonctionne avec données locales")
        
        from handlers.command_handlers.network_commands import NetworkCommands
        
        mock_node_manager = Mock()
        mock_node_manager.get_node_distance = Mock(return_value=None)
        
        network_cmd = NetworkCommands(
            remote_nodes_client=Mock(),
            sender=Mock(),
            node_manager=mock_node_manager
        )
        
        # Test data from rx_history format
        node_data = {
            'id': 0x12345678,
            'name': 'TestNode',
            'rssi': 0,
            'snr': 10.5,
            'last_heard': 1234567890
        }
        
        try:
            response = network_cmd._format_my_response(node_data)
            
            print(f"  Response: {response}")
            
            # Check response contains expected elements
            self.assertIn("SNR", response, "Response should contain SNR")
            self.assertIn("📶", response, "Response should contain signal icon")
            
            # Check it doesn't reference remote node
            self.assertNotIn("REMOTE_NODE", response, 
                           "Response should NOT reference REMOTE_NODE")
            self.assertNotIn("tigrog2", response.lower(), 
                           "Response should NOT reference tigrog2")
            
            print("  ✅ Response formatted correctly")
            print("  ✅ No REMOTE_NODE references")
            
        except Exception as e:
            self.fail(f"❌ Format failed: {e}")

def run_tests():
    """Run all tests"""
    print("="*60)
    print("TEST: /my command NO TCP dependency")
    print("="*60)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMyCommandNoTCP)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("="*60)
        print("\n📋 RÉSUMÉ:")
        print("  ✅ /my ne dépend plus de TCP")
        print("  ✅ /my fonctionne avec MT et MC")
        print("  ✅ /my utilise rx_history local")
        print("  ✅ Pas besoin de REMOTE_NODE_HOST")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("="*60)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
