#!/usr/bin/env python3
"""
Démonstration de la commande /stats hop
Montre comment la commande affiche les nœuds triés par hop_start
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
from handlers.command_handlers.unified_stats import UnifiedStatsCommands


def create_demo_data():
    """Créer des données de démonstration réalistes"""
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    print("=" * 70)
    print("DÉMONSTRATION /stats hop - Analyse de la portée des nœuds")
    print("=" * 70)
    
    # Créer les composants
    node_manager = NodeManager()
    traffic_monitor = TrafficMonitor(node_manager)
    traffic_monitor.persistence = TrafficPersistence(db_path=db_path)
    
    # Simuler un réseau mesh réaliste avec différents types de nœuds
    nodes_data = [
        # (node_id_hex, name, hop_start, description)
        ('!16fad3dc', 'tigrog2', 7, 'Router principal (haute altitude)'),
        ('!12345678', 'tigrobot', 7, 'Bot principal avec antenne externe'),
        ('!a1b2c3d4', 'relay-nord', 6, 'Relais zone nord'),
        ('!e5f6a7b8', 'relay-sud', 6, 'Relais zone sud'),
        ('!11223344', 'mobile-1', 5, 'Nœud mobile avec bonne antenne'),
        ('!55667788', 'mobile-2', 5, 'Nœud mobile standard'),
        ('!99aabbcc', 'fixe-centre', 4, 'Nœud fixe centre-ville'),
        ('!ddeeff00', 'portable-1', 3, 'Appareil portable'),
        ('!11112222', 'portable-2', 3, 'Appareil portable'),
        ('!33334444', 'indoor-1', 2, 'Nœud intérieur (faible portée)'),
        ('!55556666', 'indoor-2', 2, 'Nœud intérieur (faible portée)'),
        ('!77778888', 'test-node', 1, 'Nœud de test (très faible portée)'),
    ]
    
    print("\n📡 Création de données de test réalistes...")
    print(f"   {len(nodes_data)} nœuds avec différentes portées\n")
    
    # Ajouter des paquets pour chaque nœud
    for node_hex, name, hop_start_value, description in nodes_data:
        # Convertir hex en decimal
        node_id = int(node_hex[1:], 16)
        
        # Simuler plusieurs paquets avec variations de hop_start
        # (réaliste: un nœud peut envoyer avec différents hop_start)
        num_packets = 5
        for i in range(num_packets):
            # Varier légèrement le hop_start pour simuler conditions réelles
            variation = 0 if i < 3 else -1  # Certains paquets avec hop_start réduit
            current_hop_start = max(1, hop_start_value + variation)
            
            packet = {
                'timestamp': time.time() - (i * 60),  # Espacer dans le temps
                'from_id': str(node_id),
                'to_id': '0',
                'source': 'serial',
                'sender_name': name,
                'packet_type': 'TEXT_MESSAGE_APP' if i % 2 == 0 else 'TELEMETRY_APP',
                'message': f'Message de {name}' if i % 2 == 0 else None,
                'rssi': -100 + (hop_start_value * 5),  # RSSI corrélé au hop_start
                'snr': float(hop_start_value),
                'hops': 0,
                'hop_limit': current_hop_start,
                'hop_start': current_hop_start,
                'size': 50,
                'is_broadcast': True,
                'is_encrypted': False
            }
            traffic_monitor.persistence.save_packet(packet)
        
        print(f"   ✓ {name:15s} - hop_start max: {hop_start_value} - {description}")
    
    print(f"\n✅ {len(nodes_data) * 5} paquets de test créés\n")
    
    return traffic_monitor, node_manager, db_path


def demo_mesh_output(unified_stats):
    """Démonstration de la sortie Mesh (compacte)"""
    print("=" * 70)
    print("1. FORMAT MESH (LoRa - 180 chars max)")
    print("=" * 70)
    print("\n📻 Commande: /stats hop\n")
    
    response = unified_stats.get_hop_stats(params=[], channel='mesh')
    print("Réponse:")
    print("-" * 70)
    print(response)
    print("-" * 70)
    print(f"Longueur: {len(response)} caractères")
    
    if len(response) <= 180:
        print("✅ Respecte la limite LoRa de 180 caractères")
    else:
        print(f"⚠️  Dépasse la limite LoRa ({len(response) - 180} chars en trop)")


def demo_telegram_output(unified_stats):
    """Démonstration de la sortie Telegram (détaillée)"""
    print("\n" + "=" * 70)
    print("2. FORMAT TELEGRAM (détaillé)")
    print("=" * 70)
    print("\n💬 Commande: /stats hop\n")
    
    response = unified_stats.get_hop_stats(params=[], channel='telegram')
    print("Réponse:")
    print("-" * 70)
    print(response)
    print("-" * 70)


def demo_with_time_filter(unified_stats):
    """Démonstration avec filtre temporel"""
    print("\n" + "=" * 70)
    print("3. FILTRE TEMPOREL")
    print("=" * 70)
    print("\n💬 Commande: /stats hop 1  (dernière heure)\n")
    
    response = unified_stats.get_hop_stats(params=['1'], channel='telegram')
    print("Réponse:")
    print("-" * 70)
    print(response)
    print("-" * 70)


def demo_help():
    """Démonstration de l'aide"""
    print("\n" + "=" * 70)
    print("4. AIDE DE LA COMMANDE")
    print("=" * 70)
    
    from handlers.command_handlers.unified_stats import UnifiedStatsCommands
    
    # Mock minimal
    class MockInterface:
        pass
    
    unified_stats = UnifiedStatsCommands(None, None, MockInterface())
    
    print("\n📻 Aide Mesh:")
    print("-" * 70)
    help_mesh = unified_stats.get_help(channel='mesh')
    print(help_mesh)
    print("-" * 70)
    
    print("\n💬 Aide Telegram:")
    print("-" * 70)
    help_telegram = unified_stats.get_help(channel='telegram')
    print(help_telegram)
    print("-" * 70)


def main():
    try:
        # Créer les données de démo
        traffic_monitor, node_manager, db_path = create_demo_data()
        
        # Créer UnifiedStatsCommands
        unified_stats = UnifiedStatsCommands(traffic_monitor, node_manager, None)
        
        # Démonstrations
        demo_mesh_output(unified_stats)
        demo_telegram_output(unified_stats)
        demo_with_time_filter(unified_stats)
        demo_help()
        
        # Nettoyage
        traffic_monitor.persistence.close()
        if os.path.exists(db_path):
            os.remove(db_path)
        
        print("\n" + "=" * 70)
        print("✅ DÉMONSTRATION TERMINÉE")
        print("=" * 70)
        print("\n📋 Fonctionnalités démontrées:")
        print("  1. ✅ Format compact pour Mesh (LoRa)")
        print("  2. ✅ Format détaillé pour Telegram")
        print("  3. ✅ Filtre temporel (hours)")
        print("  4. ✅ Aide intégrée")
        print("  5. ✅ Tri décroissant par hop_start")
        print("  6. ✅ Calcul du max hop_start par nœud")
        print("  7. ✅ Icônes indicateurs de portée")
        print("\n💡 La commande /stats hop permet d'analyser la portée maximale")
        print("   de chaque nœud sur le réseau mesh, utile pour:")
        print("   • Identifier les meilleurs relais")
        print("   • Optimiser le placement des nœuds")
        print("   • Analyser la couverture réseau")
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
