#!/usr/bin/env python3
"""
Test de régression: Simulation du scénario exact de l'erreur dans les logs

Ce test reproduit le scénario exact qui causait l'erreur:
"BlitzMonitor._on_mqtt_disconnect() takes from 4 to 5 positional arguments but 6 were given"

L'erreur se produisait lorsque paho-mqtt appelait le callback avec les 5 paramètres
de la VERSION2 API, mais notre callback n'en attendait que 4.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys

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
    sys.modules['pygeohash'] = Mock()


class TestMQTTDisconnectRegression(unittest.TestCase):
    """Test de régression pour l'erreur de signature MQTT disconnect"""
    
    @unittest.skipUnless(MQTT_AVAILABLE and PYGEOHASH_AVAILABLE, "Dependencies not available")
    def test_blitz_monitor_mqtt_disconnect_actual_call(self):
        """
        Reproduire l'appel exact que paho-mqtt fait au callback on_disconnect
        
        Avant le fix, cet test échouait avec:
        TypeError: _on_mqtt_disconnect() takes from 4 to 5 positional arguments but 6 were given
        
        Après le fix, cet test passe sans erreur.
        """
        from blitz_monitor import BlitzMonitor
        
        # Créer un moniteur
        monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
        monitor.connected = True
        
        # Créer un client MQTT VERSION2
        monitor.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        # Assigner le callback comme le fait start_monitoring()
        monitor.mqtt_client.on_disconnect = monitor._on_mqtt_disconnect
        
        # Simuler exactement ce que paho-mqtt VERSION2 fait lors d'une déconnexion
        # Paho-mqtt appelle: on_disconnect(client, userdata, disconnect_flags, reason_code, properties)
        # C'est 5 paramètres + self = 6 arguments totaux pour une méthode d'instance
        
        mock_client = Mock()
        mock_userdata = None
        mock_disconnect_flags = Mock()  # DisconnectFlags object
        mock_reason_code = 7  # MQTT_ERR_CONN_LOST
        mock_properties = None  # Properties can be None
        
        # Cet appel doit maintenant réussir sans TypeError
        try:
            # C'est EXACTEMENT comment paho-mqtt appelle le callback
            monitor.mqtt_client.on_disconnect(
                mock_client,
                mock_userdata,
                mock_disconnect_flags,
                mock_reason_code,
                mock_properties
            )
            
            print("✅ Callback appelé avec succès - FIX VÉRIFIÉ")
            print(f"   Callback reçu 5 arguments (+ self) sans erreur")
            
        except TypeError as e:
            self.fail(f"❌ RÉGRESSION: {e}")
        
        # Vérifier que le statut a été mis à jour
        self.assertFalse(monitor.connected, "Monitor should be disconnected")
    
    @unittest.skipUnless(MQTT_AVAILABLE and PYGEOHASH_AVAILABLE, "Dependencies not available")
    def test_mqtt_loop_disconnect_error_scenario(self):
        """
        Test du scénario complet: boucle MQTT → déconnexion → callback invoqué
        
        C'est le scénario qui causait l'erreur dans les logs:
        "Erreur boucle MQTT: BlitzMonitor._on_mqtt_disconnect() takes from 4 to 5 positional arguments but 6 were given"
        """
        from blitz_monitor import BlitzMonitor
        
        monitor = BlitzMonitor(lat=47.0, lon=6.0, radius_km=50)
        
        # Créer client VERSION2
        monitor.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        # Assigner les callbacks
        monitor.mqtt_client.on_connect = monitor._on_mqtt_connect
        monitor.mqtt_client.on_disconnect = monitor._on_mqtt_disconnect
        monitor.mqtt_client.on_message = monitor._on_mqtt_message
        
        # Simuler une connexion puis une déconnexion
        # Ceci teste que paho-mqtt peut appeler nos callbacks sans erreur
        
        print("\n=== Simulation de déconnexion MQTT ===")
        
        # Scénario 1: Connexion normale
        with patch('blitz_monitor.info_print'):
            monitor.mqtt_client.on_connect(
                Mock(),  # client
                None,    # userdata
                {},      # flags
                0,       # reason_code (success)
                None     # properties
            )
        
        self.assertTrue(monitor.connected, "Should be connected after successful connect")
        print("✅ Connexion réussie")
        
        # Scénario 2: Déconnexion avec erreur (comme dans les logs)
        with patch('blitz_monitor.error_print') as mock_error:
            monitor.mqtt_client.on_disconnect(
                Mock(),  # client
                None,    # userdata
                Mock(),  # disconnect_flags
                7,       # reason_code (MQTT_ERR_CONN_LOST)
                None     # properties
            )
        
        self.assertFalse(monitor.connected, "Should be disconnected")
        mock_error.assert_called_once()
        
        # Vérifier que le message d'erreur contient le code
        error_msg = mock_error.call_args[0][0]
        self.assertIn("7", error_msg)
        self.assertIn("inattendue", error_msg)
        
        print("✅ Déconnexion gérée correctement avec code d'erreur 7")
        print(f"   Message d'erreur: {error_msg}")
    
    @unittest.skipUnless(MQTT_AVAILABLE, "MQTT not available")
    def test_mqtt_neighbor_collector_disconnect_regression(self):
        """Test de régression pour MQTTNeighborCollector (même problème)"""
        from mqtt_neighbor_collector import MQTTNeighborCollector
        
        mock_persistence = Mock()
        collector = MQTTNeighborCollector(
            mqtt_server="test.example.com",
            mqtt_port=1883,
            persistence=mock_persistence
        )
        
        if not collector.enabled:
            self.skipTest("Collector disabled due to missing dependencies")
        
        # Créer client VERSION2
        collector.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        
        # Assigner callback
        collector.mqtt_client.on_disconnect = collector._on_mqtt_disconnect
        
        # Simuler appel VERSION2 (5 paramètres)
        try:
            collector.mqtt_client.on_disconnect(
                Mock(),  # client
                None,    # userdata
                Mock(),  # disconnect_flags
                0,       # reason_code
                None     # properties
            )
            
            print("✅ MQTTNeighborCollector callback appelé avec succès")
            
        except TypeError as e:
            self.fail(f"❌ RÉGRESSION MQTTNeighborCollector: {e}")
        
        self.assertFalse(collector.connected, "Should be disconnected")


if __name__ == '__main__':
    print("=" * 70)
    print("TEST DE RÉGRESSION: MQTT Disconnect Callback")
    print("=" * 70)
    print("\nCe test vérifie que l'erreur des logs est corrigée:")
    print("  'BlitzMonitor._on_mqtt_disconnect() takes from 4 to 5 positional")
    print("   arguments but 6 were given'")
    print("\nSi tous les tests passent, le fix est vérifié ✅")
    print("=" * 70)
    
    if MQTT_AVAILABLE:
        import paho.mqtt
        print(f"\npaho-mqtt version: {paho.mqtt.__version__}")
    
    unittest.main(verbosity=2)
