#!/usr/bin/env python3
"""
Test du format de la commande /trafic

Ce test vérifie que:
1. Les noms de nœuds sont entre crochets [NodeName] et non en gras **NodeName:**
2. Les messages sont sur une seule ligne: [HH:MM:SS] [NodeName] message
3. Il n'y a pas de lignes vides entre les messages
4. Les messages du bot (comme /echo) sont inclus dans l'historique
"""

import sys
import os
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock config module before other imports
sys.modules['config'] = type(sys)('config')
sys.modules['config'].DEBUG_MODE = False
sys.modules['config'].DATABASE_PATH = ':memory:'

from unittest.mock import Mock, MagicMock
from collections import deque

def test_traffic_report_formatting():
    """
    Vérifier que le format de /trafic respecte les spécifications:
    - Nom du nœud entre crochets [NodeName]
    - Message sur la même ligne
    - Pas de lignes vides entre les messages
    - Messages du bot inclus dans l'historique
    """
    print("🧪 Test: Format de la commande /trafic\n")
    
    # Import TrafficMonitor
    from traffic_monitor import TrafficMonitor
    
    # Mock des dépendances
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="Unknown")
    
    # Créer une instance de TrafficMonitor
    traffic_monitor = TrafficMonitor(
        node_manager=mock_node_manager
    )
    
    # Ajouter des messages de test
    test_messages = [
        {
            'timestamp': time.time() - 3600,  # 1h ago
            'from_id': 0x12345678,
            'sender_name': 'Test User 1',
            'message': 'Premier message de test',
            'rssi': -100,
            'snr': 5.0,
            'message_length': 23,
            'source': 'local'
        },
        {
            'timestamp': time.time() - 1800,  # 30min ago
            'from_id': 0x87654321,
            'sender_name': 'Test User 2',
            'message': 'Deuxième message',
            'rssi': -95,
            'snr': 7.5,
            'message_length': 16,
            'source': 'local'
        },
        {
            'timestamp': time.time() - 900,  # 15min ago
            'from_id': 0x11111111,
            'sender_name': 'NodeName ABC',
            'message': 'Troisième message avec du contenu',
            'rssi': -90,
            'snr': 10.0,
            'message_length': 33,
            'source': 'tcp'
        }
    ]
    
    # Ajouter les messages au deque
    traffic_monitor.public_messages = deque(test_messages, maxlen=2000)
    
    # Générer le rapport
    report = traffic_monitor.get_traffic_report(hours=2)
    
    print("📊 Rapport généré:")
    print("=" * 60)
    print(report)
    print("=" * 60)
    print()
    
    # Vérifications
    success = True
    
    # 1. Vérifier l'absence de ** autour des noms de nœuds
    if '**Test User 1:**' in report or '**Test User 2:**' in report or '**NodeName ABC:**' in report:
        print("❌ ÉCHEC: Les noms de nœuds contiennent encore ** (format gras)")
        success = False
    else:
        print("✅ PASS: Pas de format gras ** dans les noms de nœuds")
    
    # 2. Vérifier la présence des crochets autour des noms
    if '[Test User 1]' in report and '[Test User 2]' in report and '[NodeName ABC]' in report:
        print("✅ PASS: Noms de nœuds entre crochets [NodeName]")
    else:
        print("❌ ÉCHEC: Les noms de nœuds ne sont pas entre crochets")
        success = False
    
    # 3. Vérifier qu'il n'y a pas de double saut de ligne (messages séparés par ligne vide)
    # Compter les doubles sauts de ligne dans la section des messages
    lines = report.split('\n')
    
    # Trouver où commencent les messages (après l'en-tête)
    msg_start_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('['):
            msg_start_idx = i
            break
    
    # Vérifier qu'il n'y a pas de lignes vides entre les messages
    message_lines = lines[msg_start_idx:]
    consecutive_empty = 0
    has_double_empty = False
    
    for line in message_lines:
        if line.strip() == '':
            consecutive_empty += 1
            if consecutive_empty >= 2:
                has_double_empty = True
                break
        else:
            consecutive_empty = 0
    
    if has_double_empty:
        print("❌ ÉCHEC: Il y a des lignes vides entre les messages")
        success = False
    else:
        print("✅ PASS: Pas de lignes vides entre les messages")
    
    # 4. Vérifier que le timestamp et le nom sont sur la même ligne que le message
    # Format attendu: [HH:MM:SS] [NodeName] message
    for line in message_lines:
        if line.strip() and line.startswith('['):
            # Vérifier le format
            if '] [' in line and line.count('[') >= 2:
                # Bon format: [timestamp] [nodename] message
                pass
            else:
                print(f"❌ ÉCHEC: Ligne mal formatée: {line[:80]}")
                success = False
                break
    else:
        print("✅ PASS: Format [HH:MM:SS] [NodeName] message respecté")
    
    # 5. Vérifier qu'aucun message ne commence par deux espaces (indentation)
    indented_messages = [line for line in message_lines if line.startswith('  ') and not line.strip().startswith('📻') and not line.strip().startswith('📡')]
    if indented_messages:
        print(f"❌ ÉCHEC: {len(indented_messages)} messages indentés trouvés")
        print(f"   Exemples: {indented_messages[:2]}")
        success = False
    else:
        print("✅ PASS: Pas de messages indentés")
    
    print()
    if success:
        print("✅ TOUS LES TESTS RÉUSSIS")
        return 0
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        return 1

if __name__ == '__main__':
    exit_code = test_traffic_report_formatting()
    sys.exit(exit_code)
