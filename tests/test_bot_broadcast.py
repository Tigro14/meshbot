#!/usr/bin/env python3
"""
Test pour la fonctionnalité broadcast de la commande /bot

Ce test vérifie que la commande /bot peut maintenant répondre
en mode broadcast sur le canal mesh (comme echo, weather, rain).
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config module before other imports
sys.modules['config'] = type(sys)('config')
sys.modules['config'].DEBUG_MODE = False
sys.modules['config'].MAX_MESSAGE_SIZE = 180
sys.modules['config'].REBOOT_PASSWORD = "test"
sys.modules['config'].REBOOT_AUTHORIZED_USERS = []
sys.modules['config'].MAX_COMMANDS_PER_WINDOW = 5
sys.modules['config'].COMMAND_WINDOW_SECONDS = 300

from unittest.mock import Mock, MagicMock, patch


def test_bot_broadcast_functionality():
    """
    Vérifier que /bot peut répondre en mode broadcast
    """
    print("🧪 Test: /bot peut répondre en broadcast\n")
    
    # Mock des dépendances
    mock_interface = Mock()
    mock_interface.sendText = Mock()
    
    mock_sender = Mock()
    mock_sender._get_interface = Mock(return_value=mock_interface)
    mock_sender.log_conversation = Mock()
    mock_sender.send_chunks = Mock()
    mock_sender.send_single = Mock()
    
    mock_llama_client = Mock()
    mock_llama_client.query_llama_mesh = Mock(return_value="Réponse de l'IA")
    mock_llama_client.cleanup_cache = Mock()
    
    mock_broadcast_tracker = Mock()
    
    # Créer une instance de AICommands avec broadcast_tracker
    from handlers.command_handlers.ai_commands import AICommands
    
    ai_commands = AICommands(
        llama_client=mock_llama_client,
        sender=mock_sender,
        broadcast_tracker=mock_broadcast_tracker
    )
    
    # Test 1: Vérifier que /bot en mode broadcast utilise l'interface partagée
    print("Test 1: /bot en mode broadcast")
    message = "/bot quelle heure est-il?"
    sender_id = 12345678
    sender_info = "TestUser"
    
    ai_commands.handle_bot(message, sender_id, sender_info, is_broadcast=True)
    
    # Vérifier que query_llama_mesh a été appelé
    assert mock_llama_client.query_llama_mesh.called, "❌ query_llama_mesh() devrait être appelé"
    assert mock_llama_client.query_llama_mesh.call_args[0][0] == "quelle heure est-il?", "❌ Prompt incorrect"
    print("✅ query_llama_mesh() appelé avec le bon prompt")
    
    # Vérifier que _get_interface() a été appelé (pour le broadcast)
    assert mock_sender._get_interface.called, "❌ _get_interface() devrait être appelé en mode broadcast"
    print("✅ _get_interface() appelé")
    
    # Vérifier que sendText a été appelé sur l'interface
    assert mock_interface.sendText.called, "❌ sendText() devrait être appelé en mode broadcast"
    assert mock_interface.sendText.call_args[0][0] == "Réponse de l'IA", "❌ Réponse incorrecte"
    print("✅ sendText() appelé avec la réponse de l'IA")
    
    # Vérifier que le broadcast a été tracké
    assert mock_broadcast_tracker.called, "❌ broadcast_tracker devrait être appelé"
    assert mock_broadcast_tracker.call_args[0][0] == "Réponse de l'IA", "❌ Réponse trackée incorrecte"
    print("✅ Broadcast tracké correctement")
    
    # Vérifier que send_chunks n'a PAS été appelé (mode broadcast utilise sendText)
    assert not mock_sender.send_chunks.called, "❌ send_chunks() ne devrait pas être appelé en mode broadcast"
    print("✅ send_chunks() non appelé en mode broadcast")
    
    # Vérifier que cleanup_cache a été appelé
    assert mock_llama_client.cleanup_cache.called, "❌ cleanup_cache() devrait être appelé"
    print("✅ cleanup_cache() appelé")
    
    print("\n" + "="*60)
    print("✅ Test 1 passé: /bot fonctionne en mode broadcast")
    print("="*60 + "\n")
    
    # Test 2: Vérifier que /bot en mode direct utilise send_chunks
    print("Test 2: /bot en mode direct (non-broadcast)")
    
    # Reset mocks
    mock_sender._get_interface.reset_mock()
    mock_sender.send_chunks.reset_mock()
    mock_interface.sendText.reset_mock()
    mock_broadcast_tracker.reset_mock()
    mock_llama_client.query_llama_mesh.reset_mock()
    mock_llama_client.cleanup_cache.reset_mock()
    
    ai_commands.handle_bot(message, sender_id, sender_info, is_broadcast=False)
    
    # Vérifier que query_llama_mesh a été appelé
    assert mock_llama_client.query_llama_mesh.called, "❌ query_llama_mesh() devrait être appelé"
    print("✅ query_llama_mesh() appelé")
    
    # Vérifier que send_chunks a été appelé (mode direct)
    assert mock_sender.send_chunks.called, "❌ send_chunks() devrait être appelé en mode direct"
    assert mock_sender.send_chunks.call_args[0][0] == "Réponse de l'IA", "❌ Réponse incorrecte"
    print("✅ send_chunks() appelé avec la réponse de l'IA")
    
    # Vérifier que sendText n'a PAS été appelé (mode direct utilise send_chunks)
    assert not mock_interface.sendText.called, "❌ sendText() ne devrait pas être appelé en mode direct"
    print("✅ sendText() non appelé en mode direct")
    
    # Vérifier que broadcast_tracker n'a PAS été appelé
    assert not mock_broadcast_tracker.called, "❌ broadcast_tracker ne devrait pas être appelé en mode direct"
    print("✅ Broadcast non tracké en mode direct")
    
    print("\n" + "="*60)
    print("✅ Test 2 passé: /bot fonctionne en mode direct")
    print("="*60 + "\n")
    
    # Test 3: Vérifier le message d'usage en mode broadcast
    print("Test 3: Message d'usage en mode broadcast")
    
    # Reset mocks
    mock_sender._get_interface.reset_mock()
    mock_sender.send_single.reset_mock()
    mock_interface.sendText.reset_mock()
    mock_broadcast_tracker.reset_mock()
    
    # Appeler /bot sans arguments
    ai_commands.handle_bot("/bot ", sender_id, sender_info, is_broadcast=True)
    
    # Vérifier que sendText a été appelé avec le message d'usage
    assert mock_interface.sendText.called, "❌ sendText() devrait être appelé pour le message d'usage"
    assert mock_interface.sendText.call_args[0][0] == "Usage: /bot <question>", "❌ Message d'usage incorrect"
    print("✅ Message d'usage envoyé en broadcast")
    
    # Vérifier que send_single n'a PAS été appelé
    assert not mock_sender.send_single.called, "❌ send_single() ne devrait pas être appelé en mode broadcast"
    print("✅ send_single() non appelé en mode broadcast")
    
    print("\n" + "="*60)
    print("✅ Test 3 passé: Message d'usage en broadcast")
    print("="*60 + "\n")


def test_message_router_bot_broadcast():
    """
    Vérifier que le message router traite /bot en mode broadcast
    """
    print("🧪 Test: MessageRouter traite /bot en broadcast\n")
    
    # Test: Vérifier que /bot est dans broadcast_commands
    print("Test: /bot est dans la liste broadcast_commands")
    
    # Lire le fichier source pour vérifier
    with open('handlers/message_router.py', 'r') as f:
        content = f.read()
    
    assert "'/bot '" in content, "❌ '/bot ' devrait être dans broadcast_commands"
    assert "broadcast_commands = ['/echo ', '/my', '/weather', '/rain', '/bot ']" in content, \
        "❌ Liste broadcast_commands incorrecte"
    print("✅ /bot présent dans broadcast_commands")
    
    # Vérifier que le handler est appelé avec is_broadcast
    assert "elif message.startswith('/bot '):" in content, "❌ Handler /bot manquant"
    assert "self.ai_handler.handle_bot(message, sender_id, sender_info, is_broadcast=is_broadcast)" in content, \
        "❌ Appel handle_bot avec is_broadcast manquant"
    print("✅ Handler /bot appelé avec is_broadcast")
    
    # Vérifier que broadcast_tracker est passé à AICommands
    assert "self.ai_handler = AICommands(llama_client, self.sender, broadcast_tracker=broadcast_tracker)" in content, \
        "❌ broadcast_tracker devrait être passé à AICommands"
    print("✅ broadcast_tracker passé à AICommands")
    
    print("\n" + "="*60)
    print("✅ Test passé: Router configuré pour /bot en broadcast")
    print("="*60 + "\n")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TEST: Fonctionnalité broadcast de /bot")
    print("="*70 + "\n")
    
    try:
        # Test 1: AICommands broadcast
        test_bot_broadcast_functionality()
        
        # Test 2: MessageRouter broadcast
        test_message_router_bot_broadcast()
        
        print("\n" + "="*70)
        print("✅ TOUS LES TESTS PASSÉS")
        print("="*70 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
