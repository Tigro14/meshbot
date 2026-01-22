#!/usr/bin/env python3
"""
Test de la commande /rebootpi en mode companion
Vérifie que /rebootpi fonctionne en mode companion
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestRebootpiCompanion(unittest.TestCase):
    """Tests pour la commande /rebootpi en mode companion"""
    
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
        
    def test_rebootpi_in_companion_commands(self):
        """Test que /rebootpi est dans la liste des commandes companion"""
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
        
        # Vérifier que /rebootpi est dans les commandes supportées
        self.assertIn('/rebootpi', router.companion_commands)
        print("✅ /rebootpi est bien dans companion_commands")
        
    def test_rebootpi_not_filtered_in_companion_mode(self):
        """Test que /rebootpi n'est PAS filtré en mode companion"""
        from handlers.message_router import MessageRouter
        
        # Mock des dépendances
        llama_client = Mock()
        esphome_client = Mock()
        remote_nodes_client = Mock()
        node_manager = Mock()
        node_manager.get_node_name.return_value = "TestNode"
        context_manager = Mock()
        interface = Mock()
        interface.localNode = Mock(nodeNum=0xFFFFFFFF)
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
        
        # Mock du sender pour capturer les messages
        sent_messages = []
        original_send = router.sender.send_single
        def mock_send(message, sender_id, sender_info):
            sent_messages.append(message)
        router.sender.send_single = mock_send
        
        # Mock du system_handler pour éviter l'exécution réelle
        router.system_handler.handle_reboot_command = Mock(return_value="✅ Test reboot")
        
        # Tester la commande /rebootpi
        packet = {
            'from': 0x12345678,
            'to': 0xFFFFFFFF,
            'decoded': {}
        }
        
        message = "/rebootpi testpassword"
        router._route_command(message, 0x12345678, "TestNode", packet)
        
        # Vérifier qu'aucun message d'erreur "désactivée" n'a été envoyé
        for msg in sent_messages:
            self.assertNotIn("désactivée", msg, 
                           "La commande /rebootpi ne devrait PAS être désactivée en mode companion")
            self.assertNotIn("mode companion", msg,
                           "La commande /rebootpi ne devrait PAS être filtrée en mode companion")
        
        # Vérifier que handle_reboot_command a été appelé
        router.system_handler.handle_reboot_command.assert_called_once()
        print("✅ /rebootpi n'est PAS filtrée en mode companion")


if __name__ == '__main__':
    # Lancer les tests
    unittest.main(verbosity=2)
