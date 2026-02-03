#!/usr/bin/env python3
"""
Test pour la gestion des erreurs réseau dans la télémétrie ESPHome

Ce test vérifie:
1. BrokenPipeError est géré gracieusement (pas de traceback complet)
2. Les autres erreurs réseau (ConnectionReset, etc.) sont gérées
3. Les erreurs non-réseau continuent d'être loggées complètement
"""

import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch, call

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def test_broken_pipe_error_handling():
    """Test que BrokenPipeError est géré gracieusement"""
    print("🧪 Test 1: Gestion BrokenPipeError\n")
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
        debug_print_mock = Mock()
        error_print_mock = Mock()
        info_print_mock = Mock()
        
        sys.modules['utils'].debug_print = debug_print_mock
        sys.modules['utils'].error_print = error_print_mock
        sys.modules['utils'].info_print = info_print_mock
        
        # Mock platform_config
        sys.modules['platform_config'].get_enabled_platforms = Mock(return_value=[])
        
        # Import après mock
        from meshtastic.protobuf import portnums_pb2, telemetry_pb2
        
        # Mock telemetry structures
        def create_mock_telemetry():
            mock = MagicMock()
            mock.time = 0
            mock.environment_metrics = MagicMock()
            mock.device_metrics = MagicMock()
            return mock
        
        telemetry_pb2.Telemetry = Mock(side_effect=create_mock_telemetry)
        portnums_pb2.PortNum.TELEMETRY_APP = 67
        
        # Importer MeshBot après les mocks
        from main_bot import MeshBot
        
        # Créer instance du bot
        bot = MeshBot()
        
        # Mock interface pour lever BrokenPipeError
        bot.interface = Mock()
        bot.interface.sendData = Mock(side_effect=BrokenPipeError("Broken pipe"))
        
        # Mock ESPHomeClient pour retourner des valeurs
        bot.esphome_client.get_sensor_values = Mock(return_value={
            'temperature': 22.3,
            'pressure': 101325.0,
            'humidity': 58.2,
            'battery_voltage': 13.1
        })
        
        # Appeler send_esphome_telemetry
        print("Appel de send_esphome_telemetry() avec BrokenPipeError...")
        bot.send_esphome_telemetry()
        
        # Vérifier que sendData a été appelé
        assert bot.interface.sendData.called, "❌ sendData() devrait avoir été appelé"
        
        # Vérifier que debug_print a été appelé (pas error_print)
        assert debug_print_mock.called, "❌ debug_print() devrait avoir été appelé"
        
        # Vérifier qu'error_print n'a PAS été appelé pour BrokenPipeError
        error_calls = [call for call in error_print_mock.call_args_list 
                      if "BrokenPipeError" in str(call) or "Broken pipe" in str(call)]
        
        # On accepte que error_print soit appelé pour "Erreur préparation télémétrie"
        # mais pas pour le traceback complet du BrokenPipeError
        full_traceback_calls = [call for call in error_calls 
                               if "Traceback" in str(call)]
        
        print(f"\ndebug_print appelé {debug_print_mock.call_count} fois")
        print(f"error_print appelé {error_print_mock.call_count} fois")
        print(f"Appels error_print avec BrokenPipeError: {len(error_calls)}")
        print(f"Appels error_print avec traceback complet: {len(full_traceback_calls)}")
        
        # Le traceback complet NE devrait PAS être loggé
        assert len(full_traceback_calls) == 0, \
            "❌ Le traceback complet de BrokenPipeError ne devrait pas être loggé"
        
        # debug_print devrait avoir été appelé avec le message d'erreur réseau
        debug_calls_str = [str(call) for call in debug_print_mock.call_args_list]
        network_error_logged = any("Connexion réseau perdue" in s or "réseau perdue" in s 
                                   for s in debug_calls_str)
        assert network_error_logged, "❌ Le message d'erreur réseau devrait être loggé en debug"
        
        print("\n✅ Test 1 réussi: BrokenPipeError géré gracieusement")


def test_other_network_errors():
    """Test que les autres erreurs réseau sont aussi gérées"""
    print("\n🧪 Test 2: Gestion autres erreurs réseau\n")
    print("=" * 60)
    
    network_errors = [
        (ConnectionResetError, "Connection reset by peer"),
        (ConnectionRefusedError, "Connection refused"),
        (ConnectionAbortedError, "Connection aborted"),
    ]
    
    for error_class, error_msg in network_errors:
        print(f"\nTest avec {error_class.__name__}...")
        
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
            debug_print_mock = Mock()
            error_print_mock = Mock()
            info_print_mock = Mock()
            
            sys.modules['utils'].debug_print = debug_print_mock
            sys.modules['utils'].error_print = error_print_mock
            sys.modules['utils'].info_print = info_print_mock
            
            # Mock platform_config
            sys.modules['platform_config'].get_enabled_platforms = Mock(return_value=[])
            
            # Import après mock
            from meshtastic.protobuf import portnums_pb2, telemetry_pb2
            
            # Mock telemetry structures
            def create_mock_telemetry():
                mock = MagicMock()
                mock.time = 0
                mock.environment_metrics = MagicMock()
                mock.device_metrics = MagicMock()
                return mock
            
            telemetry_pb2.Telemetry = Mock(side_effect=create_mock_telemetry)
            portnums_pb2.PortNum.TELEMETRY_APP = 67
            
            # Importer MeshBot après les mocks
            from main_bot import MeshBot
            
            # Créer instance du bot
            bot = MeshBot()
            
            # Mock interface pour lever l'erreur réseau
            bot.interface = Mock()
            bot.interface.sendData = Mock(side_effect=error_class(error_msg))
            
            # Mock ESPHomeClient
            bot.esphome_client.get_sensor_values = Mock(return_value={
                'temperature': 22.3,
                'pressure': 101325.0,
                'humidity': 58.2,
                'battery_voltage': 13.1
            })
            
            # Appeler send_esphome_telemetry
            bot.send_esphome_telemetry()
            
            # Vérifier que debug_print a été appelé
            assert debug_print_mock.called, f"❌ debug_print() devrait avoir été appelé pour {error_class.__name__}"
            
            # Vérifier qu'aucun traceback complet n'est loggé
            error_calls_str = [str(call) for call in error_print_mock.call_args_list]
            full_traceback = any("Traceback" in s for s in error_calls_str)
            
            assert not full_traceback, \
                f"❌ Le traceback complet de {error_class.__name__} ne devrait pas être loggé"
            
            print(f"  ✓ {error_class.__name__} géré gracieusement")
    
    print("\n✅ Test 2 réussi: Toutes les erreurs réseau gérées gracieusement")


def test_unexpected_errors_still_logged():
    """Test que les erreurs non-réseau sont toujours loggées complètement"""
    print("\n🧪 Test 3: Erreurs non-réseau toujours loggées\n")
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
        debug_print_mock = Mock()
        error_print_mock = Mock()
        info_print_mock = Mock()
        
        sys.modules['utils'].debug_print = debug_print_mock
        sys.modules['utils'].error_print = error_print_mock
        sys.modules['utils'].info_print = info_print_mock
        
        # Mock platform_config
        sys.modules['platform_config'].get_enabled_platforms = Mock(return_value=[])
        
        # Import après mock
        from meshtastic.protobuf import portnums_pb2, telemetry_pb2
        
        # Mock telemetry structures
        def create_mock_telemetry():
            mock = MagicMock()
            mock.time = 0
            mock.environment_metrics = MagicMock()
            mock.device_metrics = MagicMock()
            return mock
        
        telemetry_pb2.Telemetry = Mock(side_effect=create_mock_telemetry)
        portnums_pb2.PortNum.TELEMETRY_APP = 67
        
        # Importer MeshBot après les mocks
        from main_bot import MeshBot
        
        # Créer instance du bot
        bot = MeshBot()
        
        # Mock interface pour lever une erreur non-réseau
        bot.interface = Mock()
        bot.interface.sendData = Mock(side_effect=ValueError("Invalid telemetry data"))
        
        # Mock ESPHomeClient
        bot.esphome_client.get_sensor_values = Mock(return_value={
            'temperature': 22.3,
            'pressure': 101325.0,
            'humidity': 58.2,
            'battery_voltage': 13.1
        })
        
        # Appeler send_esphome_telemetry
        print("Appel de send_esphome_telemetry() avec ValueError...")
        bot.send_esphome_telemetry()
        
        # Vérifier que error_print a été appelé
        assert error_print_mock.called, "❌ error_print() devrait avoir été appelé"
        
        # Vérifier qu'un traceback complet est loggé pour ValueError
        error_calls_str = [str(call) for call in error_print_mock.call_args_list]
        has_traceback = any("Traceback" in s for s in error_calls_str)
        has_error_msg = any("Invalid telemetry data" in s or "ValueError" in s 
                           for s in error_calls_str)
        
        print(f"\nerror_print appelé {error_print_mock.call_count} fois")
        print(f"Traceback présent: {has_traceback}")
        print(f"Message d'erreur présent: {has_error_msg}")
        
        assert has_traceback or has_error_msg, \
            "❌ Les erreurs non-réseau devraient être loggées avec traceback"
        
        print("\n✅ Test 3 réussi: Erreurs non-réseau toujours loggées complètement")


def main():
    """Lancer tous les tests"""
    print("\n" + "=" * 60)
    print("    TESTS GESTION ERREURS RÉSEAU TÉLÉMÉTRIE")
    print("=" * 60 + "\n")
    
    try:
        test_broken_pipe_error_handling()
        test_other_network_errors()
        test_unexpected_errors_still_logged()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("=" * 60 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ ÉCHEC DU TEST: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
