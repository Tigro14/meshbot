#!/usr/bin/env python3
"""
Test des nouvelles commandes echo (/echo, /echomt, /echomc)
Vérifie que les commandes utilisent l'interface partagée et ne nécessitent plus REMOTE_NODE_HOST
"""

import sys
import os

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio


class TestEchoCommands(unittest.TestCase):
    """Tests pour les commandes echo"""

    def setUp(self):
        """Configuration initiale pour chaque test"""
        # Mock de la config pour éviter les imports
        self.config_patcher = patch.dict('sys.modules', {
            'config': MagicMock(
                TELEGRAM_AUTHORIZED_USERS=[],
                MAX_MESSAGE_SIZE=180,
                MAX_COMMANDS_PER_WINDOW=5,
                COMMAND_WINDOW_SECONDS=300,
            ),
            'config_priv': MagicMock(
                TELEGRAM_BOT_TOKEN="test_token",
                TELEGRAM_AUTHORIZED_USERS=[],
                TELEGRAM_ALERT_USERS=[],
                TELEGRAM_TO_MESH_MAPPING={},
            )
        })
        self.config_patcher.start()

    def tearDown(self):
        """Nettoyage après chaque test"""
        self.config_patcher.stop()

    def test_echo_command_uses_shared_interface(self):
        """Test que /echo utilise l'interface partagée du bot"""
        from telegram_bot.commands.mesh_commands import MeshCommands
        
        # Mock du telegram_integration
        mock_telegram = Mock()
        mock_telegram.message_handler = Mock()
        mock_telegram.message_handler.interface = Mock()
        mock_telegram.node_manager = Mock()
        mock_telegram.context_manager = Mock()
        mock_telegram.message_handler.traffic_monitor = Mock()
        mock_telegram.loop = asyncio.get_event_loop()
        
        # Mock de l'interface Meshtastic
        mock_interface = Mock()
        mock_interface.__class__.__name__ = "SerialInterface"
        mock_interface.sendText = Mock()
        mock_telegram.message_handler.interface = mock_interface
        
        # Créer l'instance de MeshCommands
        mesh_commands = MeshCommands(mock_telegram)
        
        # Vérifier que l'interface est accessible
        self.assertIsNotNone(mesh_commands.interface)
        self.assertEqual(mesh_commands.interface, mock_interface)
        
        # Test _send_echo_to_network
        result = mesh_commands._send_echo_to_network("Test: message")
        
        # Vérifier que sendText a été appelé sur l'interface partagée
        mock_interface.sendText.assert_called_once()
        args = mock_interface.sendText.call_args
        self.assertIn("Test: message", args[0])
        
        # Vérifier que le résultat indique un succès
        self.assertIn("✅", result)
        print("✅ Test passed: /echo uses shared interface")

    def test_echo_command_detects_meshcore(self):
        """Test que /echo détecte correctement une interface MeshCore"""
        from telegram_bot.commands.mesh_commands import MeshCommands
        
        # Mock du telegram_integration avec interface MeshCore
        mock_telegram = Mock()
        mock_telegram.message_handler = Mock()
        mock_telegram.node_manager = Mock()
        mock_telegram.context_manager = Mock()
        mock_telegram.message_handler.traffic_monitor = Mock()
        
        # Mock d'une interface MeshCore
        mock_interface = Mock()
        mock_interface.__class__.__name__ = "MeshCoreSerialInterface"
        mock_interface.sendText = Mock()
        mock_telegram.message_handler.interface = mock_interface
        
        # Créer l'instance de MeshCommands
        mesh_commands = MeshCommands(mock_telegram)
        
        # Test _send_echo_to_network
        result = mesh_commands._send_echo_to_network("Test: message")
        
        # Vérifier que sendText a été appelé avec les paramètres MeshCore
        mock_interface.sendText.assert_called_once()
        args, kwargs = mock_interface.sendText.call_args
        
        # MeshCore doit avoir destinationId=0xFFFFFFFF pour broadcast
        self.assertEqual(kwargs.get('destinationId'), 0xFFFFFFFF)
        self.assertEqual(kwargs.get('channelIndex'), 0)
        
        # Vérifier que le résultat mentionne MeshCore
        self.assertIn("MeshCore", result)
        print("✅ Test passed: /echo detects MeshCore interface")

    def test_echo_command_no_remote_node_host_required(self):
        """Test que /echo ne nécessite plus REMOTE_NODE_HOST"""
        from telegram_bot.commands.mesh_commands import MeshCommands
        
        # Mock sans REMOTE_NODE_HOST (devrait quand même fonctionner)
        mock_telegram = Mock()
        mock_telegram.message_handler = Mock()
        mock_telegram.node_manager = Mock()
        mock_telegram.context_manager = Mock()
        mock_telegram.message_handler.traffic_monitor = Mock()
        
        # Interface disponible
        mock_interface = Mock()
        mock_interface.__class__.__name__ = "SerialInterface"
        mock_interface.sendText = Mock()
        mock_telegram.message_handler.interface = mock_interface
        
        # Créer l'instance de MeshCommands
        mesh_commands = MeshCommands(mock_telegram)
        
        # Test _send_echo_to_network - devrait fonctionner sans REMOTE_NODE_HOST
        result = mesh_commands._send_echo_to_network("Test: message")
        
        # Vérifier que ça fonctionne
        mock_interface.sendText.assert_called_once()
        self.assertIn("✅", result)
        self.assertNotIn("REMOTE_NODE_HOST", result)
        print("✅ Test passed: /echo works without REMOTE_NODE_HOST")

    def test_echomt_targets_meshtastic_in_dual_mode(self):
        """Test que /echomt cible spécifiquement Meshtastic en mode dual"""
        from telegram_bot.commands.mesh_commands import MeshCommands
        from dual_interface_manager import DualInterfaceManager, NetworkSource
        
        # Mock du telegram_integration avec dual mode
        mock_telegram = Mock()
        mock_telegram.message_handler = Mock()
        mock_telegram.node_manager = Mock()
        mock_telegram.context_manager = Mock()
        mock_telegram.message_handler.traffic_monitor = Mock()
        
        # Mock de l'interface principale
        mock_interface = Mock()
        mock_interface.__class__.__name__ = "SerialInterface"
        mock_telegram.message_handler.interface = mock_interface
        
        # Mock du dual interface manager
        mock_dual_interface = Mock(spec=DualInterfaceManager)
        mock_dual_interface.is_dual_mode.return_value = True
        mock_dual_interface.has_meshtastic.return_value = True
        mock_dual_interface.send_message = Mock(return_value=True)
        mock_telegram.message_handler.dual_interface = mock_dual_interface
        
        # Créer l'instance de MeshCommands
        mesh_commands = MeshCommands(mock_telegram)
        
        # Vérifier que dual_interface est accessible
        self.assertIsNotNone(mesh_commands.dual_interface)
        
        # Test _send_echo_to_network avec network_type='meshtastic'
        result = mesh_commands._send_echo_to_network("Test: message", network_type='meshtastic')
        
        # Vérifier que send_message a été appelé sur dual_interface
        mock_dual_interface.send_message.assert_called_once()
        args = mock_dual_interface.send_message.call_args[0]
        
        # Vérifier les paramètres: message, destination (broadcast), network source
        self.assertEqual(args[0], "Test: message")
        self.assertEqual(args[1], 0xFFFFFFFF)  # Broadcast
        self.assertEqual(args[2], NetworkSource.MESHTASTIC)
        
        # Vérifier le résultat
        self.assertIn("✅", result)
        self.assertIn("Meshtastic", result)
        print("✅ Test passed: /echomt targets Meshtastic in dual mode")

    def test_echomc_targets_meshcore_in_dual_mode(self):
        """Test que /echomc cible spécifiquement MeshCore en mode dual"""
        from telegram_bot.commands.mesh_commands import MeshCommands
        from dual_interface_manager import DualInterfaceManager, NetworkSource
        
        # Mock du telegram_integration avec dual mode
        mock_telegram = Mock()
        mock_telegram.message_handler = Mock()
        mock_telegram.node_manager = Mock()
        mock_telegram.context_manager = Mock()
        mock_telegram.message_handler.traffic_monitor = Mock()
        
        # Mock de l'interface principale
        mock_interface = Mock()
        mock_interface.__class__.__name__ = "SerialInterface"
        mock_telegram.message_handler.interface = mock_interface
        
        # Mock du dual interface manager
        mock_dual_interface = Mock(spec=DualInterfaceManager)
        mock_dual_interface.is_dual_mode.return_value = True
        mock_dual_interface.has_meshcore.return_value = True
        mock_dual_interface.send_message = Mock(return_value=True)
        mock_telegram.message_handler.dual_interface = mock_dual_interface
        
        # Créer l'instance de MeshCommands
        mesh_commands = MeshCommands(mock_telegram)
        
        # Test _send_echo_to_network avec network_type='meshcore'
        result = mesh_commands._send_echo_to_network("Test: message", network_type='meshcore')
        
        # Vérifier que send_message a été appelé sur dual_interface
        mock_dual_interface.send_message.assert_called_once()
        args = mock_dual_interface.send_message.call_args[0]
        
        # Vérifier les paramètres
        self.assertEqual(args[0], "Test: message")
        self.assertEqual(args[1], 0xFFFFFFFF)  # Broadcast
        self.assertEqual(args[2], NetworkSource.MESHCORE)
        
        # Vérifier le résultat
        self.assertIn("✅", result)
        self.assertIn("MeshCore", result)
        print("✅ Test passed: /echomc targets MeshCore in dual mode")

    def test_echo_handles_missing_interface_gracefully(self):
        """Test que /echo gère l'absence d'interface de manière appropriée"""
        from telegram_bot.commands.mesh_commands import MeshCommands
        
        # Mock sans interface disponible
        mock_telegram = Mock()
        mock_telegram.message_handler = Mock()
        mock_telegram.message_handler.interface = None  # Pas d'interface
        mock_telegram.node_manager = Mock()
        mock_telegram.context_manager = Mock()
        mock_telegram.message_handler.traffic_monitor = Mock()
        
        # Créer l'instance de MeshCommands
        mesh_commands = MeshCommands(mock_telegram)
        
        # Test _send_echo_to_network
        result = mesh_commands._send_echo_to_network("Test: message")
        
        # Vérifier que le résultat indique une erreur appropriée
        self.assertIn("❌", result)
        self.assertIn("Interface", result.lower())
        print("✅ Test passed: /echo handles missing interface gracefully")


def run_tests():
    """Exécuter tous les tests"""
    print("=" * 80)
    print("🧪 TESTS DES COMMANDES ECHO")
    print("=" * 80)
    print()
    
    # Créer la suite de tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEchoCommands)
    
    # Exécuter avec un runner verbeux
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 80)
    if result.wasSuccessful():
        print("✅ TOUS LES TESTS ONT RÉUSSI!")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        if result.failures:
            print(f"   Échecs: {len(result.failures)}")
        if result.errors:
            print(f"   Erreurs: {len(result.errors)}")
    print("=" * 80)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
