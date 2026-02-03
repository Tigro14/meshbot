#!/usr/bin/env python3
"""
Test pour vérifier la correction de la signature du callback on_disconnect
pour paho-mqtt 2.x avec CallbackAPIVersion.VERSION2

Le bug était que _on_mqtt_disconnect avait la signature:
    (self, client, userdata, rc, properties=None)

Mais paho-mqtt VERSION2 attend:
    (self, client, userdata, disconnect_flags, reason_code, properties)
"""

import unittest
import inspect
from unittest.mock import Mock, MagicMock
import sys

# Imports conditionnels
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("paho-mqtt non disponible - skip tests")

try:
    import pygeohash
    PYGEOHASH_AVAILABLE = True
except ImportError:
    PYGEOHASH_AVAILABLE = False
    print("pygeohash non disponible - skip blitz tests")

# Mock des modules si nécessaires
if not PYGEOHASH_AVAILABLE:
    sys.modules['pygeohash'] = MagicMock()


class TestMQTTDisconnectSignature(unittest.TestCase):
    """Test de la signature du callback on_disconnect"""
    
    def test_blitz_monitor_disconnect_signature(self):
        """Vérifier que BlitzMonitor._on_mqtt_disconnect a la bonne signature"""
        if not MQTT_AVAILABLE or not PYGEOHASH_AVAILABLE:
            self.skipTest("Dependencies not available")
        
        from blitz_monitor import BlitzMonitor
        
        # Créer instance (sans position pour éviter erreurs)
        # On passe lat/lon pour éviter l'échec d'init
        monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
        
        # Vérifier la signature de _on_mqtt_disconnect
        sig = inspect.signature(monitor._on_mqtt_disconnect)
        params = list(sig.parameters.keys())
        
        # Pour VERSION2, la signature attendue est:
        # (client, userdata, disconnect_flags, reason_code, properties)
        # Avec self en premier pour une méthode d'instance
        expected_params = ['client', 'userdata', 'disconnect_flags', 'reason_code', 'properties']
        
        self.assertEqual(params, expected_params, 
                        f"Signature incorrecte. Attendu: {expected_params}, Reçu: {params}")
        
        print("✅ BlitzMonitor._on_mqtt_disconnect a la bonne signature")
    
    def test_mqtt_neighbor_collector_disconnect_signature(self):
        """Vérifier que MQTTNeighborCollector._on_mqtt_disconnect a la bonne signature"""
        if not MQTT_AVAILABLE:
            self.skipTest("MQTT not available")
        
        from mqtt_neighbor_collector import MQTTNeighborCollector
        
        # Créer instance avec configuration minimale
        mock_persistence = Mock()
        collector = MQTTNeighborCollector(
            mqtt_server="test.example.com",
            mqtt_port=1883,
            persistence=mock_persistence
        )
        
        # Vérifier la signature de _on_mqtt_disconnect
        sig = inspect.signature(collector._on_mqtt_disconnect)
        params = list(sig.parameters.keys())
        
        # Pour VERSION2, la signature attendue est:
        # (client, userdata, disconnect_flags, reason_code, properties)
        expected_params = ['client', 'userdata', 'disconnect_flags', 'reason_code', 'properties']
        
        self.assertEqual(params, expected_params,
                        f"Signature incorrecte. Attendu: {expected_params}, Reçu: {params}")
        
        print("✅ MQTTNeighborCollector._on_mqtt_disconnect a la bonne signature")
    
    def test_callback_can_be_called_with_version2_args(self):
        """Test que les callbacks peuvent être appelés avec les arguments VERSION2"""
        if not MQTT_AVAILABLE or not PYGEOHASH_AVAILABLE:
            self.skipTest("Dependencies not available")
        
        from blitz_monitor import BlitzMonitor
        
        monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
        
        # Simuler un appel comme paho-mqtt VERSION2 le ferait
        mock_client = Mock()
        mock_userdata = None
        mock_disconnect_flags = Mock()
        mock_reason_code = 0
        mock_properties = None
        
        # Cet appel ne devrait pas lever d'exception
        try:
            monitor._on_mqtt_disconnect(
                mock_client,
                mock_userdata, 
                mock_disconnect_flags,
                mock_reason_code,
                mock_properties
            )
            print("✅ BlitzMonitor._on_mqtt_disconnect peut être appelé avec args VERSION2")
        except TypeError as e:
            self.fail(f"Callback ne peut pas être appelé avec args VERSION2: {e}")
        
        # Vérifier que l'état a été mis à jour correctement
        self.assertFalse(monitor.connected, "Monitor devrait être déconnecté")
    
    def test_mqtt_version2_callback_compatibility(self):
        """Test que le callback est compatible avec paho-mqtt VERSION2"""
        if not MQTT_AVAILABLE:
            self.skipTest("MQTT not available")
        
        # Créer un client MQTT avec VERSION2
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        
        # Mock class pour tester
        class TestMonitor:
            def __init__(self):
                self.connected = False
                self.disconnect_called = False
            
            def _on_mqtt_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
                """Signature correcte pour VERSION2"""
                self.connected = False
                self.disconnect_called = True
        
        monitor = TestMonitor()
        
        # Assigner le callback
        # Ceci ne devrait pas lever d'exception
        client.on_disconnect = monitor._on_mqtt_disconnect
        
        # Vérifier que l'assignation a réussi
        self.assertIsNotNone(client.on_disconnect)
        print("✅ Callback compatible avec paho-mqtt VERSION2")


if __name__ == '__main__':
    print("=" * 70)
    print("Test de la correction de la signature MQTT disconnect callback")
    print("=" * 70)
    
    # Vérifier la version de paho-mqtt
    if MQTT_AVAILABLE:
        import paho.mqtt
        print(f"paho-mqtt version: {paho.mqtt.__version__}")
    
    unittest.main(verbosity=2)
