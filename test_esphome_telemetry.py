#!/usr/bin/env python3
"""
Test pour la fonctionnalité de télémétrie ESPHome

Ce test vérifie:
1. La méthode get_sensor_values() retourne les bonnes données
2. La conversion de pression hPa → Pa fonctionne
3. Le broadcast de télémétrie s'exécute sans erreur
"""

import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Créer un config minimal pour les tests
class MockConfig:
    ESPHOME_HOST = "192.168.1.27"
    ESPHOME_PORT = 80
    ESPHOME_TELEMETRY_ENABLED = True
    ESPHOME_TELEMETRY_INTERVAL = 3600
    DEBUG_MODE = True
    MAX_MESSAGE_SIZE = 180

# Injecter le config mock
sys.modules['config'] = MockConfig

def test_esphome_sensor_values():
    """Test de récupération des valeurs des capteurs ESPHome"""
    print("🧪 Test 1: Récupération valeurs capteurs ESPHome\n")
    print("=" * 60)
    
    # Mock des modules
    with patch.dict('sys.modules', {
        'meshtastic': MagicMock(),
        'meshtastic.protobuf': MagicMock(),
        'meshtastic.protobuf.portnums_pb2': MagicMock(),
        'meshtastic.protobuf.telemetry_pb2': MagicMock(),
        'utils': MagicMock(),
        'esphome_history': MagicMock(),
    }):
        # Mock utils functions
        sys.modules['utils'].lazy_import_requests = Mock()
        sys.modules['utils'].debug_print = Mock()
        sys.modules['utils'].error_print = Mock()
        sys.modules['utils'].truncate_text = lambda x, y: x
        
        from esphome_client import ESPHomeClient
        
        # Mock requests
        mock_responses = {
            'http://192.168.1.27/': Mock(status_code=200),
            'http://192.168.1.27/sensor/bme280_temperature': Mock(
                status_code=200,
                json=lambda: {'value': 21.5}
            ),
            'http://192.168.1.27/sensor/bme280_pressure': Mock(
                status_code=200,
                json=lambda: {'value': 1013.25}  # hPa
            ),
            'http://192.168.1.27/sensor/bme280_relative_humidity': Mock(
                status_code=200,
                json=lambda: {'value': 56.4}
            ),
            'http://192.168.1.27/sensor/battery_voltage': Mock(
                status_code=200,
                json=lambda: {'value': 12.8}
            )
        }
        
        def mock_get(url, timeout=5):
            response = mock_responses.get(url, Mock(status_code=404))
            response.close = Mock()
            return response
        
        with patch('esphome_client.lazy_import_requests') as mock_requests:
            mock_requests.return_value.get = mock_get
            
            client = ESPHomeClient()
            values = client.get_sensor_values()
            
            print("Valeurs retournées:")
            for key, value in values.items():
                print(f"  {key}: {value}")
            
            # Vérifications
            assert values is not None, "❌ get_sensor_values() retourne None"
            assert values['temperature'] == 21.5, f"❌ Température incorrecte: {values['temperature']}"
            assert values['pressure'] == 101325.0, f"❌ Pression incorrecte (devrait être convertie en Pa): {values['pressure']}"
            assert values['humidity'] == 56.4, f"❌ Humidité incorrecte: {values['humidity']}"
            assert values['battery_voltage'] == 12.8, f"❌ Tension batterie incorrecte: {values['battery_voltage']}"
            
            print("\n✅ Test 1 réussi: Valeurs correctes et pression convertie en Pa")


def test_telemetry_broadcast():
    """Test du broadcast de télémétrie"""
    print("\n🧪 Test 2: Broadcast télémétrie\n")
    print("=" * 60)
    
    with patch.dict('sys.modules', {
        'meshtastic': MagicMock(),
        'meshtastic.serial_interface': MagicMock(),
        'meshtastic.tcp_interface': MagicMock(),
        'meshtastic.protobuf': MagicMock(),
        'pubsub': MagicMock(),
        'utils': MagicMock(),
        'node_manager': MagicMock(),
        'context_manager': MagicMock(),
        'llama_client': MagicMock(),
        'esphome_client': MagicMock(),
        'esphome_history': MagicMock(),
        'remote_nodes_client': MagicMock(),
        'message_handler': MagicMock(),
        'traffic_monitor': MagicMock(),
        'system_monitor': MagicMock(),
        'safe_serial_connection': MagicMock(),
        'safe_tcp_connection': MagicMock(),
        'tcp_interface_patch': MagicMock(),
        'vigilance_monitor': MagicMock(),
        'blitz_monitor': MagicMock(),
        'mesh_traceroute_manager': MagicMock(),
        'platforms': MagicMock(),
        'platforms.telegram_platform': MagicMock(),
        'platforms.cli_server_platform': MagicMock(),
        'platform_config': MagicMock(),
    }):
        # Mock utils functions
        sys.modules['utils'].debug_print = Mock()
        sys.modules['utils'].error_print = Mock()
        sys.modules['utils'].info_print = Mock()
        
        # Mock platform_config
        sys.modules['platform_config'].get_enabled_platforms = Mock(return_value=[])
        
        # Import après mock
        from meshtastic.protobuf import portnums_pb2, telemetry_pb2
        
        # Mock telemetry structures
        mock_telemetry = MagicMock()
        mock_telemetry.time = 0
        mock_telemetry.environment_metrics = MagicMock()
        mock_telemetry.device_metrics = MagicMock()
        telemetry_pb2.Telemetry = Mock(return_value=mock_telemetry)
        
        # Mock portnums
        portnums_pb2.PortNum.TELEMETRY_APP = 67
        
        # Importer MeshBot après les mocks
        from main_bot import MeshBot
        
        # Créer instance du bot
        bot = MeshBot()
        
        # Mock interface
        bot.interface = Mock()
        bot.interface.sendData = Mock()
        
        # Mock ESPHomeClient pour retourner des valeurs
        bot.esphome_client.get_sensor_values = Mock(return_value={
            'temperature': 22.3,
            'pressure': 101325.0,  # Déjà en Pa
            'humidity': 58.2,
            'battery_voltage': 13.1
        })
        
        # Appeler send_esphome_telemetry
        print("Appel de send_esphome_telemetry()...")
        bot.send_esphome_telemetry()
        
        # Vérifications
        assert bot.interface.sendData.called, "❌ sendData() n'a pas été appelé"
        
        call_args = bot.interface.sendData.call_args
        print(f"\nsendData() appelé avec:")
        print(f"  destinationId: {call_args[1].get('destinationId', 'N/A')}")
        print(f"  portNum: {call_args[1].get('portNum', 'N/A')}")
        print(f"  wantResponse: {call_args[1].get('wantResponse', 'N/A')}")
        
        assert call_args[1]['destinationId'] == 0xFFFFFFFF, "❌ destinationId devrait être broadcast"
        assert call_args[1]['portNum'] == 67, "❌ portNum devrait être TELEMETRY_APP"
        assert call_args[1]['wantResponse'] == False, "❌ wantResponse devrait être False"
        
        # Vérifier que les valeurs ont été assignées
        telemetry_data = call_args[0][0]
        assert telemetry_data.environment_metrics.temperature == 22.3
        assert telemetry_data.environment_metrics.barometric_pressure == 101325.0
        assert telemetry_data.environment_metrics.relative_humidity == 58.2
        assert telemetry_data.device_metrics.voltage == 13.1
        
        print("\n✅ Test 2 réussi: Broadcast télémétrie fonctionne")


def test_missing_sensors():
    """Test avec capteurs manquants ou défaillants"""
    print("\n🧪 Test 3: Gestion capteurs manquants\n")
    print("=" * 60)
    
    with patch.dict('sys.modules', {
        'meshtastic': MagicMock(),
        'meshtastic.protobuf': MagicMock(),
        'meshtastic.protobuf.portnums_pb2': MagicMock(),
        'meshtastic.protobuf.telemetry_pb2': MagicMock(),
        'utils': MagicMock(),
        'esphome_history': MagicMock(),
    }):
        # Mock utils functions
        sys.modules['utils'].lazy_import_requests = Mock()
        sys.modules['utils'].debug_print = Mock()
        sys.modules['utils'].error_print = Mock()
        sys.modules['utils'].truncate_text = lambda x, y: x
        
        from esphome_client import ESPHomeClient
        
        # Simuler ESPHome inaccessible
        with patch('esphome_client.lazy_import_requests') as mock_requests:
            mock_requests.return_value.get = Mock(
                return_value=Mock(status_code=500)
            )
            
            client = ESPHomeClient()
            values = client.get_sensor_values()
            
            assert values is None, "❌ Devrait retourner None si ESPHome inaccessible"
            print("✅ Retourne None si ESPHome inaccessible")
        
        # Simuler certains capteurs manquants
        mock_responses = {
            'http://192.168.1.27/': Mock(status_code=200),
            'http://192.168.1.27/sensor/bme280_temperature': Mock(
                status_code=200,
                json=lambda: {'value': 21.0}
            ),
            'http://192.168.1.27/sensor/bme280_pressure': Mock(status_code=404),
            'http://192.168.1.27/sensor/bme280_relative_humidity': Mock(status_code=404),
            'http://192.168.1.27/sensor/battery_voltage': Mock(
                status_code=200,
                json=lambda: {'value': 12.5}
            )
        }
        
        def mock_get_partial(url, timeout=5):
            response = mock_responses.get(url, Mock(status_code=404))
            response.close = Mock()
            return response
        
        with patch('esphome_client.lazy_import_requests') as mock_requests:
            mock_requests.return_value.get = mock_get_partial
            
            client = ESPHomeClient()
            values = client.get_sensor_values()
            
            assert values is not None, "❌ Devrait retourner un dict même avec capteurs manquants"
            assert values['temperature'] == 21.0, "❌ Température devrait être présente"
            assert values['pressure'] is None, "❌ Pression devrait être None"
            assert values['humidity'] is None, "❌ Humidité devrait être None"
            assert values['battery_voltage'] == 12.5, "❌ Tension batterie devrait être présente"
            
            print("✅ Gère correctement les capteurs partiellement disponibles")
            print(f"   Valeurs: {values}")


def main():
    """Lancer tous les tests"""
    print("\n" + "=" * 60)
    print("    TESTS TÉLÉMÉTRIE ESPHOME")
    print("=" * 60 + "\n")
    
    try:
        test_esphome_sensor_values()
        test_telemetry_broadcast()
        test_missing_sensors()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("=" * 60 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ ÉCHEC DU TEST: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
