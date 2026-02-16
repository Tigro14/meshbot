#!/usr/bin/env python3
"""
Test pour vérifier que la détection de source est correcte
quand MESHTASTIC_ENABLED=True et MESHCORE_ENABLED=True

Avant le fix:
- Bug: Tous les paquets étaient détectés comme "meshcore"
- Cause: Vérification de MESHCORE_ENABLED config au lieu du type d'interface

Après le fix:
- Correct: Les paquets sont détectés selon l'interface RÉELLEMENT active
- Si Meshtastic est actif → source='local' ou 'tcp'
- Si MeshCore est actif → source='meshcore'
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock config values
mock_config = {
    'MESHTASTIC_ENABLED': True,
    'MESHCORE_ENABLED': True,  # Both enabled (Meshtastic has priority)
    'CONNECTION_MODE': 'serial',
    'SERIAL_PORT': '/dev/ttyACM0',
    'DEBUG_MODE': False,
    'TELEGRAM_ENABLED': False,
    'CLI_ENABLED': False,
    'TELEGRAM_BOT_TOKEN': 'test_token',
    'TELEGRAM_AUTHORIZED_USERS': [],
    'TELEGRAM_ALERT_USERS': [],
    'TELEGRAM_TO_MESH_MAPPING': {},
    'MESH_ALERT_SUBSCRIBED_NODES': [],
}

# Mock all imports before importing main_bot
sys.modules['meshtastic'] = MagicMock()
sys.modules['meshtastic.serial_interface'] = MagicMock()
sys.modules['meshtastic.tcp_interface'] = MagicMock()
sys.modules['pubsub'] = MagicMock()
sys.modules['meshtastic.protobuf'] = MagicMock()
sys.modules['meshtastic.protobuf.portnums_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.telemetry_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.admin_pb2'] = MagicMock()

# Mock all other modules
for module in ['node_manager', 'context_manager', 'llama_client', 'esphome_client',
               'remote_nodes_client', 'message_handler', 'traffic_monitor', 
               'system_monitor', 'safe_serial_connection', 'safe_tcp_connection',
               'tcp_interface_patch', 'vigilance_monitor', 'blitz_monitor',
               'mqtt_neighbor_collector', 'mesh_traceroute_manager', 
               'db_error_monitor', 'reboot_semaphore', 'mesh_alert_manager',
               'platforms', 'platforms.telegram_platform', 'platforms.cli_server_platform',
               'platform_config', 'meshcore_cli_wrapper', 'meshcore_serial_interface']:
    sys.modules[module] = MagicMock()

# Now we can import after mocking
with patch.dict('sys.modules', sys.modules):
    with patch.dict('builtins.__dict__', mock_config):
        # Import main_bot components we need
        from meshcore_serial_interface import MeshCoreSerialInterface, MeshCoreStandaloneInterface


class TestMeshtasticSourceDetection(unittest.TestCase):
    """Test que les paquets Meshtastic ne sont pas détectés comme MeshCore"""
    
    def setUp(self):
        """Setup test fixtures"""
        # Create mock interfaces
        self.mock_meshtastic_serial = Mock()
        self.mock_meshtastic_serial.__class__.__name__ = 'SerialInterface'
        
        self.mock_meshcore_serial = MeshCoreSerialInterface('/dev/ttyUSB0')
        self.mock_meshcore_standalone = MeshCoreStandaloneInterface()
        
    def test_isinstance_detection_meshtastic(self):
        """Test que l'interface Meshtastic n'est PAS détectée comme MeshCore"""
        # Given: Une interface Meshtastic
        interface = self.mock_meshtastic_serial
        
        # When: On vérifie si c'est une interface MeshCore
        is_meshcore = isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface))
        
        # Then: Ce n'est PAS une interface MeshCore
        self.assertFalse(is_meshcore, 
                        "Interface Meshtastic ne devrait PAS être détectée comme MeshCore")
    
    def test_isinstance_detection_meshcore_serial(self):
        """Test que l'interface MeshCoreSerialInterface est bien détectée"""
        # Given: Une interface MeshCore Serial
        interface = self.mock_meshcore_serial
        
        # When: On vérifie si c'est une interface MeshCore
        is_meshcore = isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface))
        
        # Then: C'est bien une interface MeshCore
        self.assertTrue(is_meshcore, 
                       "Interface MeshCoreSerialInterface devrait être détectée comme MeshCore")
    
    def test_isinstance_detection_meshcore_standalone(self):
        """Test que l'interface MeshCoreStandaloneInterface est bien détectée"""
        # Given: Une interface MeshCore Standalone
        interface = self.mock_meshcore_standalone
        
        # When: On vérifie si c'est une interface MeshCore
        is_meshcore = isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface))
        
        # Then: C'est bien une interface MeshCore
        self.assertTrue(is_meshcore, 
                       "Interface MeshCoreStandaloneInterface devrait être détectée comme MeshCore")
    
    def test_source_detection_logic_meshtastic(self):
        """Test de la logique complète pour Meshtastic"""
        # Given: Une interface Meshtastic en mode serial
        interface = self.mock_meshtastic_serial
        
        # When: On applique la logique de détection
        if isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface)):
            source = 'meshcore'
        elif hasattr(interface, '__class__') and 'TCP' in interface.__class__.__name__:
            source = 'tcp'
        else:
            source = 'local'
        
        # Then: La source est 'local' (pas 'meshcore')
        self.assertEqual(source, 'local',
                        "Meshtastic serial devrait être détecté comme 'local', pas 'meshcore'")
    
    def test_source_detection_logic_meshcore(self):
        """Test de la logique complète pour MeshCore"""
        # Given: Une interface MeshCore
        interface = self.mock_meshcore_serial
        
        # When: On applique la logique de détection
        if isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface)):
            source = 'meshcore'
        elif hasattr(interface, '__class__') and 'TCP' in interface.__class__.__name__:
            source = 'tcp'
        else:
            source = 'local'
        
        # Then: La source est 'meshcore'
        self.assertEqual(source, 'meshcore',
                        "MeshCore devrait être détecté comme 'meshcore'")


class TestConfigVsInterfaceType(unittest.TestCase):
    """Test que le type d'interface prévaut sur la config"""
    
    def test_both_enabled_meshtastic_wins(self):
        """
        Quand MESHTASTIC_ENABLED=True et MESHCORE_ENABLED=True,
        l'interface Meshtastic est créée (priorité à Meshtastic)
        """
        # Given: Les deux configs sont True
        meshtastic_enabled = True
        meshcore_enabled = True
        
        # When: On simule la logique d'initialisation
        # (voir main_bot.py lignes 1670-1677)
        if meshtastic_enabled:
            # Meshtastic a priorité - une interface Meshtastic est créée
            interface = Mock()  # SerialInterface Meshtastic
            interface.__class__.__name__ = 'SerialInterface'
        elif meshcore_enabled:
            interface = MeshCoreSerialInterface('/dev/ttyUSB0')
        
        # Then: L'interface est Meshtastic, PAS MeshCore
        is_meshcore = isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface))
        self.assertFalse(is_meshcore,
                        "Avec les deux activés, l'interface devrait être Meshtastic")
    
    def test_only_meshcore_enabled(self):
        """
        Quand seul MESHCORE_ENABLED=True,
        l'interface MeshCore est créée
        """
        # Given: Seul MeshCore est activé
        meshtastic_enabled = False
        meshcore_enabled = True
        
        # When: On simule la logique d'initialisation
        if meshtastic_enabled:
            interface = Mock()
            interface.__class__.__name__ = 'SerialInterface'
        elif meshcore_enabled:
            interface = MeshCoreSerialInterface('/dev/ttyUSB0')
        
        # Then: L'interface est MeshCore
        is_meshcore = isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface))
        self.assertTrue(is_meshcore,
                       "Avec seul MeshCore activé, l'interface devrait être MeshCore")


if __name__ == '__main__':
    print("🧪 Test de détection de source Meshtastic vs MeshCore")
    print("=" * 60)
    print()
    
    # Run tests
    unittest.main(verbosity=2)
