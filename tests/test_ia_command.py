#!/usr/bin/env python3
"""
Test de la commande /ia (alias français de /bot)
Vérifie que /ia fonctionne en mode companion et normal
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestIACommand(unittest.TestCase):
    """Tests pour la commande /ia"""
    
    def setUp(self):
        """Préparer l'environnement de test"""
        # Mock des imports Meshtastic pour éviter les dépendances
        self.meshtastic_mock = MagicMock()
        sys.modules['meshtastic'] = self.meshtastic_mock
        sys.modules['meshtastic.serial_interface'] = MagicMock()
        sys.modules['meshtastic.tcp_interface'] = MagicMock()
        sys.modules['meshtastic.protobuf'] = MagicMock()
        sys.modules['meshtastic.protobuf.portnums_pb2'] = MagicMock()
        sys.modules['meshtastic.protobuf.telemetry_pb2'] = MagicMock()
        sys.modules['meshtastic.protobuf.admin_pb2'] = MagicMock()
        
    def test_ia_command_in_companion_commands(self):
        """Test que /ia est dans la liste des commandes companion"""
        from handlers.message_router import MessageRouter
        
        # Mock des dépendances
        llama_client = Mock()
        esphome_client = Mock()
        remote_nodes_client = Mock()
        node_manager = Mock()
        context_manager = Mock()
        interface = Mock()
        traffic_monitor = Mock()
        
        # Créer un router en mode companion
        router = MessageRouter(
            llama_client=llama_client,
            esphome_client=esphome_client,
            remote_nodes_client=remote_nodes_client,
            node_manager=node_manager,
            context_manager=context_manager,
            interface=interface,
            traffic_monitor=traffic_monitor,
            companion_mode=True
        )
        
        # Vérifier que /ia est dans les commandes supportées
        self.assertIn('/ia', router.companion_commands)
        print("✅ /ia est bien dans companion_commands")
        
    def test_ia_command_in_broadcast_commands(self):
        """Test que /ia est dans la liste des broadcast commands"""
        from handlers.message_router import MessageRouter
        
        # Mock des dépendances
        llama_client = Mock()
        esphome_client = Mock()
        remote_nodes_client = Mock()
        node_manager = Mock()
        node_manager.get_node_name.return_value = "TestNode"
        context_manager = Mock()
        interface = Mock()
        interface.localNode = Mock(nodeNum=0x12345678)
        traffic_monitor = Mock()
        
        router = MessageRouter(
            llama_client=llama_client,
            esphome_client=esphome_client,
            remote_nodes_client=remote_nodes_client,
            node_manager=node_manager,
            context_manager=context_manager,
            interface=interface,
            traffic_monitor=traffic_monitor,
            companion_mode=False
        )
        
        # Créer un packet broadcast avec /ia
        packet = {
            'from': 0x87654321,
            'to': 0xFFFFFFFF,  # Broadcast
            'decoded': {'portnum': 'TEXT_MESSAGE_APP'}
        }
        
        decoded = {'portnum': 'TEXT_MESSAGE_APP'}
        message = "/ia Bonjour"
        
        # Mock de handle_bot pour vérifier qu'il est appelé
        router.ai_handler.handle_bot = Mock()
        
        # Traiter le message
        router.process_text_message(packet, decoded, message)
        
        # Vérifier que handle_bot a été appelé avec is_broadcast=True
        router.ai_handler.handle_bot.assert_called_once()
        args = router.ai_handler.handle_bot.call_args
        self.assertTrue(args[1]['is_broadcast'])
        print("✅ /ia déclenche bien handle_bot en mode broadcast")
        
    def test_ia_command_prompt_extraction(self):
        """Test que le prompt est correctement extrait de /ia"""
        from handlers.command_handlers.ai_commands import AICommands
        
        # Mock des dépendances
        llama_client = Mock()
        llama_client.query_llama_mesh.return_value = "Réponse de l'IA"
        llama_client.cleanup_cache = Mock()
        
        sender = Mock()
        sender.log_conversation = Mock()
        sender.send_chunks = Mock()
        
        ai_handler = AICommands(llama_client, sender)
        
        # Tester avec /ia
        message = "/ia Quelle est la météo?"
        ai_handler.handle_bot(message, 0x12345678, "TestNode", is_broadcast=False)
        
        # Vérifier que query_llama_mesh a été appelé avec le bon prompt
        llama_client.query_llama_mesh.assert_called_once()
        call_args = llama_client.query_llama_mesh.call_args
        prompt = call_args[0][0]
        self.assertEqual(prompt, "Quelle est la météo?")
        print(f"✅ Prompt correctement extrait: '{prompt}'")
        
    def test_ia_vs_bot_same_behavior(self):
        """Test que /ia et /bot ont le même comportement"""
        from handlers.command_handlers.ai_commands import AICommands
        
        # Mock des dépendances
        llama_client = Mock()
        llama_client.query_llama_mesh.return_value = "Réponse de l'IA"
        llama_client.cleanup_cache = Mock()
        
        sender = Mock()
        sender.log_conversation = Mock()
        sender.send_chunks = Mock()
        
        ai_handler = AICommands(llama_client, sender)
        
        # Tester /ia
        message_ia = "/ia Test question"
        ai_handler.handle_bot(message_ia, 0x12345678, "TestNode", is_broadcast=False)
        ia_prompt = llama_client.query_llama_mesh.call_args[0][0]
        
        # Reset mocks
        llama_client.reset_mock()
        sender.reset_mock()
        
        # Tester /bot
        message_bot = "/bot Test question"
        ai_handler.handle_bot(message_bot, 0x12345678, "TestNode", is_broadcast=False)
        bot_prompt = llama_client.query_llama_mesh.call_args[0][0]
        
        # Vérifier que les prompts sont identiques
        self.assertEqual(ia_prompt, bot_prompt)
        self.assertEqual(ia_prompt, "Test question")
        print(f"✅ /ia et /bot extraient le même prompt: '{ia_prompt}'")


if __name__ == '__main__':
    # Lancer les tests
    unittest.main(verbosity=2)
