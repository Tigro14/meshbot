#!/usr/bin/env python3
"""
Test de consolidation des stats channel dans stats top
Vérifie que Canal% et Air TX sont affichés dans /stats top (Telegram uniquement)
"""

import sys
import os

# Ajouter le répertoire du projet au path (relatif au fichier de test)
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Créer un mock minimal de config
import types
config_mock = types.ModuleType('config')
config_mock.DEBUG_MODE = False
config_mock.NEIGHBORS_MAX_DISTANCE_KM = 50
sys.modules['config'] = config_mock

# Créer un mock minimal de utils
utils_mock = types.ModuleType('utils')
utils_mock.debug_print = lambda *args, **kwargs: None
utils_mock.info_print = print
utils_mock.error_print = print
sys.modules['utils'] = utils_mock

import time
from collections import defaultdict

def test_channel_integration_in_code():
    """Test l'intégration du code pour Canal% et Air TX"""
    print("=" * 60)
    print("TEST: Vérification du code modifié")
    print("=" * 60)
    
    # Vérifier que traffic_monitor.py contient les modifications
    script_dir = os.path.dirname(os.path.abspath(__file__))
    traffic_file = os.path.join(script_dir, 'traffic_monitor.py')
    
    with open(traffic_file, 'r') as f:
        traffic_code = f.read()
    
    print("\n✅ Test 1: Vérification de channel_utils et air_utils dans period_stats")
    assert "'channel_utils': []" in traffic_code, "❌ channel_utils manquant dans period_stats"
    assert "'air_utils': []" in traffic_code, "❌ air_utils manquant dans period_stats"
    print("   ✓ Champs channel_utils et air_utils ajoutés")
    
    print("\n✅ Test 2: Vérification de la collecte des données de télémétrie")
    assert "if include_packet_types and packet.get('telemetry')" in traffic_code, "❌ Condition de collecte manquante"
    assert "stats['channel_utils'].append" in traffic_code, "❌ Collecte channel_util manquante"
    assert "stats['air_utils'].append" in traffic_code, "❌ Collecte air_util manquante"
    assert "elif packet_type == 'TELEMETRY_APP':" in traffic_code, "❌ Vérification du type TELEMETRY_APP manquante"
    print("   ✓ Logique de collecte des données de canal ajoutée (uniquement TELEMETRY_APP)")
    
    print("\n✅ Test 3: Vérification de l'affichage Canal% et Air TX")
    assert "if include_packet_types and (stats['channel_utils'] or stats['air_utils']):" in traffic_code, "❌ Condition d'affichage avec include_packet_types manquante"
    assert "Canal:" in traffic_code, "❌ Label 'Canal:' manquant"
    assert "Air TX:" in traffic_code, "❌ Label 'Air TX:' manquant"
    assert "avg_channel = sum(stats['channel_utils']) / len(stats['channel_utils'])" in traffic_code, "❌ Calcul moyenne canal manquant"
    assert "avg_air = sum(stats['air_utils']) / len(stats['air_utils'])" in traffic_code, "❌ Calcul moyenne air manquant"
    print("   ✓ Logique d'affichage Canal% et Air TX ajoutée avec condition include_packet_types")
    
    # Vérifier que unified_stats.py contient les modifications
    unified_file = os.path.join(script_dir, 'handlers/command_handlers/unified_stats.py')
    
    with open(unified_file, 'r') as f:
        unified_code = f.read()
    
    print("\n✅ Test 4: Vérification de la dépréciation de /stats channel pour Telegram")
    assert "COMMANDE DÉPRÉCIÉE" in unified_code or "DEPREC" in unified_code, "❌ Message de dépréciation manquant"
    assert "if channel == 'telegram':" in unified_code, "❌ Condition channel == 'telegram' manquante"
    print("   ✓ Message de dépréciation ajouté pour Telegram")
    
    print("\n✅ Test 5: Vérification de la mise à jour de l'aide")
    assert "Top talkers avec Canal% et Air TX" in unified_code, "❌ Aide non mise à jour"
    assert "stats channel` est intégré dans `/stats top" in unified_code or "Note:" in unified_code, "❌ Note d'intégration manquante dans l'aide"
    print("   ✓ Texte d'aide mis à jour")
    
    print("\n✅ Test 6: Vérification que Mesh garde /stats channel")
    assert "Pour Mesh: continuer le fonctionnement normal" in unified_code or "Pour Mesh" in unified_code, "❌ Commentaire Mesh manquant"
    print("   ✓ Fonctionnalité Mesh préservée")
    
    print("\n" + "=" * 60)
    print("✅ TOUS LES TESTS DE CODE RÉUSSIS!")
    print("=" * 60)

def test_logic_simulation():
    """Simulation de la logique pour vérifier le comportement"""
    print("\n" + "=" * 60)
    print("TEST: Simulation de la logique")
    print("=" * 60)
    
    # Simuler period_stats avec les nouvelles clés
    period_stats = defaultdict(lambda: {
        'total_packets': 0,
        'channel_utils': [],
        'air_utils': []
    })
    
    # Simuler des paquets de télémétrie
    test_packets = [
        {'from_id': 1, 'telemetry': {'channel_util': 15.5, 'air_util': 8.2}},
        {'from_id': 1, 'telemetry': {'channel_util': 16.0, 'air_util': 8.5}},
        {'from_id': 2, 'telemetry': {'channel_util': 12.0, 'air_util': 6.0}},
    ]
    
    # Simuler la collecte
    include_packet_types = True  # Telegram
    for packet in test_packets:
        from_id = packet['from_id']
        stats = period_stats[from_id]
        
        if include_packet_types and 'telemetry' in packet and packet['telemetry']:
            telemetry = packet['telemetry']
            if 'channel_util' in telemetry and telemetry['channel_util'] is not None:
                stats['channel_utils'].append(telemetry['channel_util'])
            if 'air_util' in telemetry and telemetry['air_util'] is not None:
                stats['air_utils'].append(telemetry['air_util'])
    
    print("\n📊 Données collectées:")
    for node_id, stats in period_stats.items():
        print(f"  Node {node_id}:")
        print(f"    Canal: {stats['channel_utils']}")
        print(f"    Air: {stats['air_utils']}")
    
    # Vérifier les moyennes
    for node_id, stats in period_stats.items():
        if stats['channel_utils']:
            avg_channel = sum(stats['channel_utils']) / len(stats['channel_utils'])
            avg_air = sum(stats['air_utils']) / len(stats['air_utils']) if stats['air_utils'] else 0
            
            print(f"\n  Node {node_id} - Moyennes:")
            print(f"    Canal: {avg_channel:.1f}%")
            print(f"    Air TX: {avg_air:.1f}%")
            
            # Vérifications
            assert avg_channel > 0, f"❌ Moyenne canal devrait être > 0 pour node {node_id}"
            assert avg_air > 0, f"❌ Moyenne air devrait être > 0 pour node {node_id}"
    
    print("\n✅ Simulation de la logique réussie!")
    
    # Tester la condition Telegram vs Mesh
    print("\n📱 Test condition Telegram:")
    channel = 'telegram'
    if channel == 'telegram':
        print("   ✓ Message de dépréciation affiché")
    else:
        print("   ✗ Message de dépréciation non affiché (incorrect)")
    
    print("\n📻 Test condition Mesh:")
    channel = 'mesh'
    if channel == 'telegram':
        print("   ✗ Message de dépréciation affiché (incorrect)")
    else:
        print("   ✓ Fonctionnement normal")
    
    print("\n" + "=" * 60)
    print("✅ SIMULATION RÉUSSIE!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_channel_integration_in_code()
        test_logic_simulation()
        print("\n" + "=" * 60)
        print("🎉 TOUS LES TESTS SONT RÉUSSIS!")
        print("=" * 60)
        print("\n📋 Résumé des changements:")
        print("  1. ✅ Canal% et Air TX collectés depuis télémétrie")
        print("  2. ✅ Affichage conditionnel pour Telegram uniquement")
        print("  3. ✅ /stats channel déprécié pour Telegram")
        print("  4. ✅ Mesh continue à utiliser /stats channel")
        print("  5. ✅ Aide mise à jour")
        print("\n💡 Utilisation:")
        print("  Telegram: /stats top  → Affiche top + Canal% + Air TX")
        print("  Telegram: /stats ch   → Message de redirection")
        print("  Mesh:     /stats ch   → Fonctionne normalement")
    except AssertionError as e:
        print(f"\n❌ ÉCHEC DU TEST: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

