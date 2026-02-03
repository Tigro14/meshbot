#!/usr/bin/env python3
"""
Test du mode MeshCore companion
Vérifie que le bot peut démarrer sans connexion Meshtastic
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestMeshCoreCompanionMode(unittest.TestCase):
    """Tests pour le mode MeshCore companion"""
    
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
        
    def test_meshcore_interface_creation(self):
        """Test de création de l'interface MeshCore"""
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Créer une interface MeshCore avec un port fictif
        interface = MeshCoreSerialInterface('/dev/ttyUSB0')
        
        # Vérifier les attributs
        self.assertEqual(interface.port, '/dev/ttyUSB0')
        self.assertEqual(interface.baudrate, 115200)
        self.assertIsNotNone(interface.localNode)
        self.assertEqual(interface.localNode.nodeNum, 0xFFFFFFFF)
        self.assertFalse(interface.running)
        
    def test_standalone_interface_creation(self):
        """Test de création de l'interface standalone"""
        from meshcore_serial_interface import MeshCoreStandaloneInterface
        
        interface = MeshCoreStandaloneInterface()
        
        # Vérifier les attributs
        self.assertIsNotNone(interface.localNode)
        self.assertEqual(interface.localNode.nodeNum, 0xFFFFFFFF)
        
        # Tester sendText (doit retourner False)
        result = interface.sendText("test message", 0x12345678)
        self.assertFalse(result)
        
    def test_message_router_companion_mode(self):
        """Test du filtrage des commandes en mode companion"""
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
        
        # Vérifier le mode companion
        self.assertTrue(router.companion_mode)
        
        # Vérifier les commandes supportées
        self.assertIn('/bot', router.companion_commands)
        self.assertIn('/ia', router.companion_commands)
        self.assertIn('/weather', router.companion_commands)
        self.assertIn('/power', router.companion_commands)
        self.assertIn('/sys', router.companion_commands)
        self.assertIn('/help', router.companion_commands)
        self.assertIn('/rebootpi', router.companion_commands)
        
    @patch('config.MESHTASTIC_ENABLED', False)
    @patch('config.MESHCORE_ENABLED', True)
    def test_config_meshcore_mode(self):
        """Test de configuration en mode MeshCore"""
        import config
        
        # Vérifier que la configuration est correcte
        self.assertFalse(getattr(config, 'MESHTASTIC_ENABLED', True))
        self.assertTrue(getattr(config, 'MESHCORE_ENABLED', False))
        
    def test_meshcore_message_parsing(self):
        """Test du parsing des messages MeshCore"""
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        interface = MeshCoreSerialInterface('/dev/ttyUSB0')
        
        # Mock du callback
        received_packets = []
        def test_callback(packet, interface):
            received_packets.append(packet)
        
        interface.set_message_callback(test_callback)
        
        # Simuler la réception d'un message
        test_line = "DM:12345678:/bot hello"
        interface._process_meshcore_line(test_line)
        
        # Vérifier qu'un packet a été créé
        self.assertEqual(len(received_packets), 1)
        packet = received_packets[0]
        
        # Vérifier le contenu du packet
        self.assertEqual(packet['from'], 0x12345678)
        self.assertEqual(packet['to'], interface.localNode.nodeNum)
        self.assertIn('decoded', packet)
        self.assertEqual(packet['decoded']['portnum'], 'TEXT_MESSAGE_APP')
        
    def test_companion_commands_filtering(self):
        """Test du filtrage des commandes Meshtastic en mode companion"""
        from handlers.message_router import MessageRouter
        from handlers.message_sender import MessageSender
        
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
        
        # Tester une commande NON supportée (ex: /nodes)
        packet = {
            'from': 0x12345678,
            'to': 0xFFFFFFFF,
            'decoded': {}
        }
        
        router._route_command("/nodes", 0x12345678, "TestNode", packet)
        
        # Vérifier qu'un message d'erreur a été envoyé
        self.assertEqual(len(sent_messages), 1)
        self.assertIn("désactivée", sent_messages[0])
        self.assertIn("mode companion", sent_messages[0])


if __name__ == '__main__':
    # Lancer les tests
    unittest.main(verbosity=2)
