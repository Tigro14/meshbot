#!/usr/bin/env python3
"""
Test du nouvel alias /hop
Vérifie que la commande /hop redirige correctement vers /stats hop
"""

import sys
import os
import tempfile
import time

# Ajouter le répertoire du projet au path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Créer un mock minimal de config
import types
config_mock = types.ModuleType('config')
config_mock.DEBUG_MODE = False
config_mock.NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
config_mock.MAX_RX_HISTORY = 100
config_mock.REBOOT_PASSWORD = 'test'
config_mock.REBOOT_AUTHORIZED_USERS = []
config_mock.DB_RESET_PASSWORD = 'test'
config_mock.DB_RESET_AUTHORIZED_USERS = []
sys.modules['config'] = config_mock

# Créer un mock minimal de utils
utils_mock = types.ModuleType('utils')
utils_mock.debug_print = lambda *args, **kwargs: None
utils_mock.info_print = print
utils_mock.error_print = print
utils_mock.clean_node_name = lambda name: name
sys.modules['utils'] = utils_mock

# Mock meshtastic module
meshtastic_mock = types.ModuleType('meshtastic')
meshtastic_mock.tcp_interface = types.ModuleType('tcp_interface')
meshtastic_mock.serial_interface = types.ModuleType('serial_interface')
sys.modules['meshtastic'] = meshtastic_mock
sys.modules['meshtastic.tcp_interface'] = meshtastic_mock.tcp_interface
sys.modules['meshtastic.serial_interface'] = meshtastic_mock.serial_interface

from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor
from node_manager import NodeManager
from handlers.command_handlers.utility_commands import UtilityCommands
from handlers.message_sender import MessageSender


def test_hop_alias():
    """Test que /hop fonctionne comme alias de /stats hop"""
    print("=" * 70)
    print("TEST: /hop alias command")
    print("=" * 70)
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer les composants nécessaires
        node_manager = NodeManager()
        traffic_monitor = TrafficMonitor(node_manager)
        traffic_monitor.persistence = TrafficPersistence(db_path=db_path)
        
        # Ajouter des nœuds de test avec différents hop_start
        test_packets = [
            {
                'timestamp': time.time(),
                'from_id': '305419896',
                'to_id': '0',
                'source': 'serial',
                'sender_name': 'Node1',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': 'Test',
                'rssi': -100,
                'snr': 5.5,
                'hops': 0,
                'hop_limit': 7,
                'hop_start': 7,
                'size': 50,
                'is_broadcast': True,
                'is_encrypted': False
            },
            {
                'timestamp': time.time(),
                'from_id': '305419897',
                'to_id': '0',
                'source': 'serial',
                'sender_name': 'Node2',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': 'Test',
                'rssi': -95,
                'snr': 6.0,
                'hops': 1,
                'hop_limit': 4,
                'hop_start': 5,
                'size': 50,
                'is_broadcast': True,
                'is_encrypted': False
            }
        ]
        
        # Sauvegarder les paquets
        for packet in test_packets:
            traffic_monitor.persistence.save_packet(packet)
        
        print(f"✓ {len(test_packets)} paquets de test sauvegardés\n")
        
        # Mock interface minimal
        class MockInterface:
            pass
        
        # Créer MessageSender
        sender = MessageSender(MockInterface(), node_manager)
        
        # Créer UtilityCommands
        utility = UtilityCommands(
            esphome_client=None,
            traffic_monitor=traffic_monitor,
            sender=sender,
            node_manager=node_manager,
            blitz_monitor=None,
            vigilance_monitor=None
        )
        
        # Mock sender pour capturer la sortie
        output_messages = []
        original_send = sender.send_single
        def mock_send(message, sender_id, sender_info):
            output_messages.append(message)
            print(f"Message capturé: {message[:100]}...")
        sender.send_single = mock_send
        
        # Tester la commande /hop
        print("📊 Test: /hop")
        utility.handle_hop("/hop", 123456, "TestUser")
        
        # Vérifications
        assert len(output_messages) > 0, "❌ Aucun message envoyé"
        
        response = output_messages[0]
        print(f"\n✅ Réponse reçue ({len(response)} caractères)")
        print("=" * 70)
        print(response)
        print("=" * 70)
        
        # Vérifier que la réponse contient les éléments attendus
        assert "Hop(" in response or "TOP 20 NŒUDS PAR HOP_START" in response, \
            "❌ Format de réponse incorrect"
        
        # Tester avec paramètre d'heures
        output_messages.clear()
        print("\n📊 Test: /hop 48")
        utility.handle_hop("/hop 48", 123456, "TestUser")
        
        assert len(output_messages) > 0, "❌ Aucun message envoyé pour /hop 48"
        response2 = output_messages[0]
        print(f"✅ Réponse reçue pour /hop 48 ({len(response2)} caractères)")
        
        print("\n" + "=" * 70)
        print("✅ TOUS LES TESTS SONT RÉUSSIS!")
        print("=" * 70)
        print("\n📋 Résumé:")
        print("  1. ✅ Commande /hop fonctionne")
        print("  2. ✅ Paramètre heures accepté (/hop 48)")
        print("  3. ✅ Format de réponse correct")
        print("\n💡 Utilisation:")
        print("  /hop      → Top 20 nœuds par hop_start (24h)")
        print("  /hop 48   → Top 20 nœuds par hop_start (48h)")
        print("  /hop 168  → Top 20 nœuds par hop_start (7 jours)")
        
        traffic_monitor.persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == '__main__':
    try:
        test_hop_alias()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ ÉCHEC DU TEST: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
