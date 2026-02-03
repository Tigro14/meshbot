#!/usr/bin/env python3
"""
Test de la commande /stats hop
Vérifie que les nœuds sont correctement triés par hop_start (décroissant)
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

# Mock meshtastic module to avoid import errors
meshtastic_mock = types.ModuleType('meshtastic')
meshtastic_mock.tcp_interface = types.ModuleType('tcp_interface')
meshtastic_mock.serial_interface = types.ModuleType('serial_interface')
sys.modules['meshtastic'] = meshtastic_mock
sys.modules['meshtastic.tcp_interface'] = meshtastic_mock.tcp_interface
sys.modules['meshtastic.serial_interface'] = meshtastic_mock.serial_interface

from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor
from node_manager import NodeManager
from handlers.command_handlers.unified_stats import UnifiedStatsCommands


def test_hop_stats_basic():
    """Test basique: vérifier que get_hop_stats retourne des données"""
    print("\n" + "=" * 60)
    print("TEST 1: Fonctionnalité de base")
    print("=" * 60)
    
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
                'from_id': '305419896',  # !12345678
                'to_id': '0',
                'source': 'serial',
                'sender_name': 'Node1',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': 'Test',
                'rssi': -100,
                'snr': 5.5,
                'hops': 0,
                'hop_limit': 7,
                'hop_start': 7,  # Hop start le plus élevé
                'size': 50,
                'is_broadcast': True,
                'is_encrypted': False
            },
            {
                'timestamp': time.time(),
                'from_id': '305419897',  # !12345679
                'to_id': '0',
                'source': 'serial',
                'sender_name': 'Node2',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': 'Test',
                'rssi': -95,
                'snr': 6.0,
                'hops': 1,
                'hop_limit': 4,
                'hop_start': 5,  # Hop start moyen
                'size': 50,
                'is_broadcast': True,
                'is_encrypted': False
            },
            {
                'timestamp': time.time(),
                'from_id': '305419898',  # !1234567a
                'to_id': '0',
                'source': 'serial',
                'sender_name': 'Node3',
                'packet_type': 'TELEMETRY_APP',
                'rssi': -90,
                'snr': 7.0,
                'hops': 2,
                'hop_limit': 1,
                'hop_start': 3,  # Hop start le plus bas
                'size': 50,
                'is_broadcast': False,
                'is_encrypted': False
            }
        ]
        
        # Sauvegarder les paquets
        for packet in test_packets:
            traffic_monitor.persistence.save_packet(packet)
        
        print(f"✓ {len(test_packets)} paquets de test sauvegardés")
        
        # Créer UnifiedStatsCommands
        unified_stats = UnifiedStatsCommands(traffic_monitor, node_manager, None)
        
        # Tester la commande pour Telegram (version détaillée)
        response = unified_stats.get_hop_stats(params=[], channel='telegram')
        
        print(f"\n📊 Réponse (Telegram):")
        print(response)
        
        # Vérifications
        assert "TOP 20 NŒUDS PAR HOP_START" in response, "❌ Titre manquant"
        assert "Node1" in response or "12345678" in response, "❌ Node1 manquant"
        assert "Node2" in response or "12345679" in response, "❌ Node2 manquant"
        assert "Node3" in response or "1234567a" in response, "❌ Node3 manquant"
        
        print("\n✅ Test de base réussi")
        
        # Tester la version Mesh (compacte)
        response_mesh = unified_stats.get_hop_stats(params=[], channel='mesh')
        
        print(f"\n📊 Réponse (Mesh):")
        print(response_mesh)
        
        assert "Hop(" in response_mesh, "❌ Format Mesh incorrect"
        
        print("\n✅ Test version Mesh réussi")
        
        traffic_monitor.persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_hop_stats_sorting():
    """Test du tri décroissant par hop_start"""
    print("\n" + "=" * 60)
    print("TEST 2: Tri décroissant par hop_start")
    print("=" * 60)
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer les composants
        node_manager = NodeManager()
        traffic_monitor = TrafficMonitor(node_manager)
        traffic_monitor.persistence = TrafficPersistence(db_path=db_path)
        
        # Créer plusieurs nœuds avec des hop_start différents
        # On s'attend à ce qu'ils soient triés dans cet ordre
        expected_order = [
            ('!aaaaaaaa', 7),  # Plus grand hop_start
            ('!bbbbbbbb', 5),
            ('!cccccccc', 3),
            ('!dddddddd', 3),  # Même hop_start que cccccccc
            ('!eeeeeeee', 1),  # Plus petit hop_start
        ]
        
        for node_hex, hop_start_value in expected_order:
            # Convertir le hex en decimal
            node_id = int(node_hex[1:], 16)
            
            packet = {
                'timestamp': time.time(),
                'from_id': str(node_id),
                'to_id': '0',
                'source': 'serial',
                'sender_name': f'Node-{node_hex}',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': 'Test',
                'rssi': -100,
                'snr': 5.5,
                'hops': 0,
                'hop_limit': 3,
                'hop_start': hop_start_value,
                'size': 50,
                'is_broadcast': False,
                'is_encrypted': False
            }
            traffic_monitor.persistence.save_packet(packet)
        
        print(f"✓ {len(expected_order)} nœuds de test créés avec hop_start variés")
        
        # Créer UnifiedStatsCommands
        unified_stats = UnifiedStatsCommands(traffic_monitor, node_manager, None)
        
        # Obtenir la réponse
        response = unified_stats.get_hop_stats(params=[], channel='telegram')
        
        print(f"\n📊 Réponse:")
        print(response)
        
        # Vérifier l'ordre (le nœud avec hop_start=7 devrait être en premier)
        lines = response.split('\n')
        
        # Trouver les lignes avec les nœuds
        node_lines = [line for line in lines if 'Hop start max:' in line]
        
        assert len(node_lines) >= 3, f"❌ Nombre de nœuds insuffisant: {len(node_lines)}"
        
        # Extraire les valeurs de hop_start de chaque ligne
        hop_values = []
        for line in node_lines:
            # Format attendu: "   Hop start max: **7** (1 paquets)"
            if 'Hop start max:' in line:
                parts = line.split('**')
                if len(parts) >= 3:
                    hop_values.append(int(parts[1]))
        
        print(f"\n📋 Valeurs hop_start extraites: {hop_values}")
        
        # Vérifier que les valeurs sont en ordre décroissant
        for i in range(len(hop_values) - 1):
            assert hop_values[i] >= hop_values[i+1], \
                f"❌ Ordre incorrect: {hop_values[i]} devrait être >= {hop_values[i+1]}"
        
        print("\n✅ Test de tri décroissant réussi")
        
        traffic_monitor.persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_hop_stats_max_hop_start():
    """Test que max_hop_start est correctement calculé pour chaque nœud"""
    print("\n" + "=" * 60)
    print("TEST 3: Calcul du max hop_start par nœud")
    print("=" * 60)
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer les composants
        node_manager = NodeManager()
        traffic_monitor = TrafficMonitor(node_manager)
        traffic_monitor.persistence = TrafficPersistence(db_path=db_path)
        
        # Créer plusieurs paquets du même nœud avec différents hop_start
        node_id = '305419896'
        hop_starts = [3, 7, 5, 4]  # Le max devrait être 7
        
        for hop_start_value in hop_starts:
            packet = {
                'timestamp': time.time(),
                'from_id': node_id,
                'to_id': '0',
                'source': 'serial',
                'sender_name': 'TestNode',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': 'Test',
                'rssi': -100,
                'snr': 5.5,
                'hops': 0,
                'hop_limit': 3,
                'hop_start': hop_start_value,
                'size': 50,
                'is_broadcast': False,
                'is_encrypted': False
            }
            traffic_monitor.persistence.save_packet(packet)
        
        print(f"✓ {len(hop_starts)} paquets du même nœud avec hop_start: {hop_starts}")
        print(f"  → Max attendu: 7")
        
        # Créer UnifiedStatsCommands
        unified_stats = UnifiedStatsCommands(traffic_monitor, node_manager, None)
        
        # Obtenir la réponse
        response = unified_stats.get_hop_stats(params=[], channel='telegram')
        
        print(f"\n📊 Réponse:")
        print(response)
        
        # Vérifier que le max hop_start est 7
        assert "Hop start max: **7**" in response, \
            f"❌ Max hop_start devrait être 7, mais pas trouvé dans la réponse"
        
        # Vérifier aussi le nombre de paquets
        assert f"({len(hop_starts)} paquets)" in response, \
            f"❌ Le nombre de paquets devrait être {len(hop_starts)}"
        
        print("\n✅ Test calcul max hop_start réussi")
        
        traffic_monitor.persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_hop_stats_limit_20():
    """Test que seuls les 20 premiers nœuds sont affichés"""
    print("\n" + "=" * 60)
    print("TEST 4: Limite de 20 nœuds")
    print("=" * 60)
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer les composants
        node_manager = NodeManager()
        traffic_monitor = TrafficMonitor(node_manager)
        traffic_monitor.persistence = TrafficPersistence(db_path=db_path)
        
        # Créer 25 nœuds différents
        num_nodes = 25
        for i in range(num_nodes):
            node_id = str(305419896 + i)
            packet = {
                'timestamp': time.time(),
                'from_id': node_id,
                'to_id': '0',
                'source': 'serial',
                'sender_name': f'Node{i}',
                'packet_type': 'TEXT_MESSAGE_APP',
                'message': 'Test',
                'rssi': -100,
                'snr': 5.5,
                'hops': 0,
                'hop_limit': 3,
                'hop_start': 7 - (i % 7),  # Varier les hop_start
                'size': 50,
                'is_broadcast': False,
                'is_encrypted': False
            }
            traffic_monitor.persistence.save_packet(packet)
        
        print(f"✓ {num_nodes} nœuds de test créés")
        
        # Créer UnifiedStatsCommands
        unified_stats = UnifiedStatsCommands(traffic_monitor, node_manager, None)
        
        # Obtenir la réponse
        response = unified_stats.get_hop_stats(params=[], channel='telegram')
        
        print(f"\n📊 Réponse:")
        print(response[:500] + "..." if len(response) > 500 else response)
        
        # Compter le nombre de nœuds dans la réponse
        node_count = response.count("Hop start max:")
        
        print(f"\n📊 Nœuds affichés: {node_count}")
        
        assert node_count == 20, f"❌ Devrait afficher exactement 20 nœuds, mais {node_count} trouvés"
        assert f"{num_nodes} nœuds actifs, top 20 affichés" in response, \
            "❌ Message de résumé incorrect"
        
        print("\n✅ Test limite 20 nœuds réussi")
        
        traffic_monitor.persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == '__main__':
    print("=" * 60)
    print("TESTS /stats hop")
    print("=" * 60)
    
    try:
        test_hop_stats_basic()
        test_hop_stats_sorting()
        test_hop_stats_max_hop_start()
        test_hop_stats_limit_20()
        
        print("\n" + "=" * 60)
        print("🎉 TOUS LES TESTS SONT RÉUSSIS!")
        print("=" * 60)
        print("\n📋 Résumé:")
        print("  1. ✅ Fonctionnalité de base")
        print("  2. ✅ Tri décroissant par hop_start")
        print("  3. ✅ Calcul du max hop_start par nœud")
        print("  4. ✅ Limite de 20 nœuds affichés")
        print("\n💡 Utilisation:")
        print("  Mesh:     /stats hop [hours]")
        print("  Telegram: /stats hop [hours]")
        print("  Exemple:  /stats hop 48  → Top 20 sur 48h")
        
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
