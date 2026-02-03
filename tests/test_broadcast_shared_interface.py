#!/usr/bin/env python3
"""
Test du fix pour les broadcasts via interface partagée

Ce test vérifie que les broadcasts utilisent l'interface existante
au lieu de créer de nouvelles connexions TCP.
"""

import sys
import time
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config module before other imports
sys.modules['config'] = type(sys)('config')
sys.modules['config'].DEBUG_MODE = False
sys.modules['config'].REMOTE_NODE_HOST = "192.168.1.38"
sys.modules['config'].REMOTE_NODE_NAME = "tigrog2"
sys.modules['config'].MESSAGE_DELAY_SECONDS = 0.5

from unittest.mock import Mock, MagicMock, patch, call

def test_broadcast_uses_shared_interface():
    """
    Vérifier que _send_broadcast_via_tigrog2 utilise l'interface partagée
    au lieu de créer une nouvelle connexion TCP
    """
    print("🧪 Test: Broadcast utilise interface partagée\n")
    
    # Mock des dépendances
    mock_interface = Mock()
    mock_interface.sendText = Mock()
    
    mock_sender = Mock()
    mock_sender._get_interface = Mock(return_value=mock_interface)
    mock_sender.log_conversation = Mock()
    
    mock_traffic_monitor = Mock()
    mock_broadcast_tracker = Mock()
    
    # Créer une instance de UtilityCommands
    from handlers.command_handlers.utility_commands import UtilityCommands
    
    utility_commands = UtilityCommands(
        esphome_client=Mock(),
        traffic_monitor=mock_traffic_monitor,
        sender=mock_sender,
        node_manager=Mock(),
        blitz_monitor=None,
        vigilance_monitor=None,
        broadcast_tracker=mock_broadcast_tracker
    )
    
    # Test 1: Vérifier que l'interface partagée est utilisée
    print("Test 1: Interface partagée est utilisée")
    message = "Test broadcast message"
    sender_id = 12345678
    sender_info = "TestUser"
    command = "/weather rain"
    
    utility_commands._send_broadcast_via_tigrog2(message, sender_id, sender_info, command)
    
    # Vérifier que _get_interface() a été appelé
    assert mock_sender._get_interface.called, "❌ _get_interface() devrait être appelé"
    print("✅ _get_interface() appelé")
    
    # Vérifier que sendText a été appelé sur l'interface
    assert mock_interface.sendText.called, "❌ sendText() devrait être appelé"
    assert mock_interface.sendText.call_args[0][0] == message, "❌ Message incorrect"
    print("✅ sendText() appelé avec le bon message")
    
    # Vérifier que le broadcast a été tracké
    assert mock_broadcast_tracker.called, "❌ broadcast_tracker devrait être appelé"
    assert mock_broadcast_tracker.call_args[0][0] == message, "❌ Message tracké incorrect"
    print("✅ Broadcast tracké correctement")
    
    # Vérifier que log_conversation a été appelé
    assert mock_sender.log_conversation.called, "❌ log_conversation devrait être appelé"
    print("✅ Conversation loggée")
    
    print("\n" + "="*60)
    print("✅ Test 1 passé: Interface partagée utilisée correctement")
    print("="*60 + "\n")
    
    # Test 2: Vérifier le comportement quand l'interface est None
    print("Test 2: Comportement avec interface=None")
    
    # Reset mocks
    mock_sender._get_interface.reset_mock()
    mock_sender._get_interface.return_value = None
    mock_interface.sendText.reset_mock()
    mock_broadcast_tracker.reset_mock()
    
    utility_commands._send_broadcast_via_tigrog2(message, sender_id, sender_info, command)
    
    # Vérifier que sendText n'a PAS été appelé
    assert not mock_interface.sendText.called, "❌ sendText() ne devrait pas être appelé quand interface=None"
    print("✅ sendText() non appelé quand interface=None")
    
    print("\n" + "="*60)
    print("✅ Test 2 passé: Gestion correcte de interface=None")
    print("="*60 + "\n")
    
    return True


def test_no_tcp_connection_import():
    """
    Vérifier que safe_tcp_connection.broadcast_message n'est plus utilisé
    """
    print("🧪 Test: Pas d'import de safe_tcp_connection.broadcast_message\n")
    
    # Lire le fichier source
    with open('handlers/command_handlers/utility_commands.py', 'r') as f:
        content = f.read()
    
    # Vérifier qu'il n'y a pas d'import de broadcast_message
    assert 'from safe_tcp_connection import broadcast_message' not in content, \
        "❌ Import de broadcast_message trouvé dans utility_commands.py"
    print("✅ Pas d'import de safe_tcp_connection.broadcast_message dans utility_commands.py")
    
    # Vérifier dans network_commands aussi
    with open('handlers/command_handlers/network_commands.py', 'r') as f:
        content = f.read()
    
    assert 'from safe_tcp_connection import broadcast_message' not in content, \
        "❌ Import de broadcast_message trouvé dans network_commands.py"
    print("✅ Pas d'import de safe_tcp_connection.broadcast_message dans network_commands.py")
    
    print("\n" + "="*60)
    print("✅ Test passé: Imports safe_tcp_connection retirés")
    print("="*60 + "\n")
    
    return True


def test_network_commands_broadcast():
    """
    Vérifier que NetworkCommands utilise aussi l'interface partagée
    """
    print("🧪 Test: NetworkCommands broadcast via interface partagée\n")
    
    # Mock des dépendances
    mock_interface = Mock()
    mock_interface.sendText = Mock()
    
    mock_sender = Mock()
    mock_sender._get_interface = Mock(return_value=mock_interface)
    mock_sender.log_conversation = Mock()
    
    mock_broadcast_tracker = Mock()
    
    # Créer une instance de NetworkCommands
    from handlers.command_handlers.network_commands import NetworkCommands
    
    network_commands = NetworkCommands(
        remote_nodes_client=Mock(),
        sender=mock_sender,
        node_manager=Mock(),
        traffic_monitor=Mock(),
        interface=mock_interface,
        mesh_traceroute=None,
        broadcast_tracker=mock_broadcast_tracker
    )
    
    # Tester _send_broadcast_via_tigrog2
    message = "Test network broadcast"
    sender_id = 87654321
    sender_info = "NetworkUser"
    command = "/my"
    
    network_commands._send_broadcast_via_tigrog2(message, sender_id, sender_info, command)
    
    # Vérifier que _get_interface() a été appelé
    assert mock_sender._get_interface.called, "❌ _get_interface() devrait être appelé"
    print("✅ _get_interface() appelé")
    
    # Vérifier que sendText a été appelé
    assert mock_interface.sendText.called, "❌ sendText() devrait être appelé"
    print("✅ sendText() appelé")
    
    # Vérifier que le broadcast a été tracké
    assert mock_broadcast_tracker.called, "❌ broadcast_tracker devrait être appelé"
    print("✅ Broadcast tracké")
    
    print("\n" + "="*60)
    print("✅ Test passé: NetworkCommands utilise interface partagée")
    print("="*60 + "\n")
    
    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TEST: Broadcast via Interface Partagée")
    print("="*60 + "\n")
    
    try:
        # Test 1
        if not test_broadcast_uses_shared_interface():
            print("❌ Test 1 échoué")
            sys.exit(1)
        
        # Test 2
        if not test_no_tcp_connection_import():
            print("❌ Test 2 échoué")
            sys.exit(1)
        
        # Test 3
        if not test_network_commands_broadcast():
            print("❌ Test 3 échoué")
            sys.exit(1)
        
        print("\n" + "="*60)
        print("✅ TOUS LES TESTS PASSÉS")
        print("="*60)
        print("\nRésumé des changements:")
        print("- ✅ Utilisation de l'interface partagée au lieu de nouvelles connexions TCP")
        print("- ✅ Retrait des imports safe_tcp_connection.broadcast_message")
        print("- ✅ Pas de threading inutile")
        print("- ✅ Gestion correcte des erreurs (interface=None)")
        print("\nImpact:")
        print("- 🔧 Plus de conflits de socket TCP")
        print("- 🔧 Plus de reconnexions intempestives")
        print("- 🔧 Meilleure stabilité de la connexion principale")
        print()
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
