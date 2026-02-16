#!/usr/bin/env python3
"""
Test d'intégration pour vérifier que les callbacks MQTT fonctionnent
correctement avec paho-mqtt 2.x CallbackAPIVersion.VERSION2
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import time
from unittest.mock import Mock, patch
import sys

# Imports conditionnels
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

try:
    import pygeohash
    PYGEOHASH_AVAILABLE = True
except ImportError:
    PYGEOHASH_AVAILABLE = False
    # Mock pygeohash pour les tests
    sys.modules['pygeohash'] = Mock()


class TestMQTTIntegration(unittest.TestCase):
    """Tests d'intégration pour les callbacks MQTT"""
    
    @unittest.skipUnless(MQTT_AVAILABLE and PYGEOHASH_AVAILABLE, "Dependencies not available")
    def test_blitz_monitor_mqtt_client_creation(self):
        """Test que BlitzMonitor peut créer un client MQTT VERSION2 sans erreur"""
        from blitz_monitor import BlitzMonitor
        
        monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
        
        # Créer le client MQTT comme le fait start_monitoring()
        monitor.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        # Assigner les callbacks - ne devrait pas lever d'exception
        monitor.mqtt_client.on_connect = monitor._on_mqtt_connect
        monitor.mqtt_client.on_disconnect = monitor._on_mqtt_disconnect
        monitor.mqtt_client.on_message = monitor._on_mqtt_message
        
        # Vérifier que les callbacks sont assignés
        self.assertIsNotNone(monitor.mqtt_client.on_connect)
        self.assertIsNotNone(monitor.mqtt_client.on_disconnect)
        self.assertIsNotNone(monitor.mqtt_client.on_message)
        
        print("✅ BlitzMonitor peut créer un client MQTT VERSION2")
    
    @unittest.skipUnless(MQTT_AVAILABLE, "MQTT not available")
    def test_mqtt_neighbor_collector_mqtt_client_creation(self):
        """Test que MQTTNeighborCollector peut créer un client MQTT VERSION2 sans erreur"""
        from mqtt_neighbor_collector import MQTTNeighborCollector
        
        mock_persistence = Mock()
        collector = MQTTNeighborCollector(
            mqtt_server="test.example.com",
            mqtt_port=1883,
            persistence=mock_persistence
        )
        
        # Si enabled est False, skip le test (dépendances manquantes)
        if not collector.enabled:
            self.skipTest("MQTTNeighborCollector disabled due to missing dependencies")
        
        # Créer le client MQTT comme le fait start_monitoring()
        collector.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        # Assigner les callbacks - ne devrait pas lever d'exception
        collector.mqtt_client.on_connect = collector._on_mqtt_connect
        collector.mqtt_client.on_disconnect = collector._on_mqtt_disconnect
        collector.mqtt_client.on_message = collector._on_mqtt_message
        
        # Vérifier que les callbacks sont assignés
        self.assertIsNotNone(collector.mqtt_client.on_connect)
        self.assertIsNotNone(collector.mqtt_client.on_disconnect)
        self.assertIsNotNone(collector.mqtt_client.on_message)
        
        print("✅ MQTTNeighborCollector peut créer un client MQTT VERSION2")
    
    @unittest.skipUnless(MQTT_AVAILABLE and PYGEOHASH_AVAILABLE, "Dependencies not available")
    def test_blitz_monitor_disconnect_callback_invocation(self):
        """Test que le callback disconnect peut être invoqué correctement"""
        from blitz_monitor import BlitzMonitor
        
        monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
        monitor.connected = True  # Simuler connexion
        
        # Créer client
        monitor.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        # Assigner callback
        monitor.mqtt_client.on_disconnect = monitor._on_mqtt_disconnect
        
        # Simuler un appel du callback par paho-mqtt
        # Pour VERSION2, paho appelle:
        # on_disconnect(client, userdata, disconnect_flags, reason_code, properties)
        mock_client = Mock()
        mock_userdata = None
        mock_disconnect_flags = Mock()
        mock_reason_code = 0  # Normal disconnect
        mock_properties = None
        
        # Invoquer le callback
        monitor.mqtt_client.on_disconnect(
            mock_client,
            mock_userdata,
            mock_disconnect_flags,
            mock_reason_code,
            mock_properties
        )
        
        # Vérifier que le statut a été mis à jour
        self.assertFalse(monitor.connected, "Monitor should be disconnected")
        
        print("✅ Callback disconnect peut être invoqué sans erreur")
    
    @unittest.skipUnless(MQTT_AVAILABLE and PYGEOHASH_AVAILABLE, "Dependencies not available")
    def test_blitz_monitor_disconnect_with_error_code(self):
        """Test que le callback disconnect gère les codes d'erreur"""
        from blitz_monitor import BlitzMonitor
        
        monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
        monitor.connected = True
        
        # Créer client
        monitor.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        monitor.mqtt_client.on_disconnect = monitor._on_mqtt_disconnect
        
        # Simuler une déconnexion avec erreur
        mock_client = Mock()
        mock_disconnect_flags = Mock()
        mock_reason_code = 7  # Connection lost
        
        # Capturer les erreurs imprimées
        with patch('blitz_monitor.error_print') as mock_error:
            monitor.mqtt_client.on_disconnect(
                mock_client,
                None,
                mock_disconnect_flags,
                mock_reason_code,
                None
            )
            
            # Vérifier qu'une erreur a été logguée
            mock_error.assert_called_once()
            call_args = mock_error.call_args[0][0]
            self.assertIn("inattendue", call_args)
            self.assertIn(str(mock_reason_code), call_args)
        
        # Vérifier que le statut a été mis à jour
        self.assertFalse(monitor.connected)
        
        print("✅ Callback disconnect gère les codes d'erreur correctement")


if __name__ == '__main__':
    print("=" * 70)
    print("Test d'intégration MQTT disconnect callback")
    print("=" * 70)
    
    if MQTT_AVAILABLE:
        import paho.mqtt
        print(f"paho-mqtt version: {paho.mqtt.__version__}")
    
    unittest.main(verbosity=2)
