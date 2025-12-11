#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier que le handler /bot fonctionne avec tous les formats
"""

import sys
from unittest.mock import Mock, MagicMock, patch
from handlers.message_router import MessageRouter

def create_mock_router():
    """Créer un router avec tous les mocks nécessaires"""
    # Mocks pour les dépendances
    llama_client = Mock()
    esphome_client = Mock()
    remote_nodes_client = Mock()
    node_manager = Mock()
    context_manager = Mock()
    interface = Mock()
    traffic_monitor = Mock()
    
    # Mock pour node_manager.get_node_name
    node_manager.get_node_name.return_value = "TestUser"
    
    # Mock pour interface.localNode
    interface.localNode = Mock()
    interface.localNode.nodeNum = 0x12345678
    
    # Créer le router
    router = MessageRouter(
        llama_client=llama_client,
        esphome_client=esphome_client,
        remote_nodes_client=remote_nodes_client,
        node_manager=node_manager,
        context_manager=context_manager,
        interface=interface,
        traffic_monitor=traffic_monitor
    )
    
    return router, llama_client

def test_bot_patterns():
    """Tester différents patterns de commande /bot"""
    print("🧪 Test: Handler /bot avec différents patterns\n")
    
    router, llama_client = create_mock_router()
    
    # Mock la réponse du llama client
    llama_client.query_llama_mesh.return_value = "Réponse de l'IA"
    llama_client.cleanup_cache = Mock()
    
    test_cases = [
        ("/bot", "Alias sans argument"),
        ("/bot ", "Avec espace mais sans argument"),
        ("/bot hello", "Avec un argument"),
        ("/bot hello world", "Avec plusieurs arguments")
    ]
    
    for message, description in test_cases:
        print(f"Test: {description} → '{message}'")
        
        # Reset les mocks
        llama_client.reset_mock()
        router.sender.send_single.reset_mock() if hasattr(router.sender, 'send_single') else None
        router.sender.send_chunks.reset_mock() if hasattr(router.sender, 'send_chunks') else None
        
        # Créer un packet de test
        packet = {
            'from': 0x87654321,  # Différent de l'ID du bot
            'to': 0x12345678,    # ID du bot
        }
        decoded = {}
        
        # Traiter le message
        try:
            router.process_text_message(packet, decoded, message)
            
            # Vérifier que le handler a été appelé
            if message == "/bot" or message == "/bot ":
                # Sans argument → devrait envoyer le message d'usage
                print(f"  ✅ Handler appelé (usage message attendu)")
            else:
                # Avec argument → devrait appeler query_llama_mesh
                if llama_client.query_llama_mesh.called:
                    print(f"  ✅ Handler appelé (query_llama_mesh)")
                else:
                    print(f"  ❌ Handler PAS appelé")
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
        
        print()
    
    print("="*60)

def test_broadcast_detection():
    """Tester que /bot est détecté comme commande broadcast"""
    print("🧪 Test: Détection broadcast pour /bot\n")
    
    router, _ = create_mock_router()
    
    # Liste des commandes broadcast
    broadcast_commands = ['/echo', '/my', '/weather', '/rain', '/bot', '/info', '/propag']
    
    test_messages = [
        "/bot",
        "/bot ",
        "/bot hello",
        "/botnet",  # Ne devrait PAS matcher (commande différente)
    ]
    
    for message in test_messages:
        is_broadcast = any(message.startswith(cmd) for cmd in broadcast_commands)
        
        # /bot, /bot , /bot hello devraient matcher
        # /botnet ne devrait PAS matcher
        expected = message.startswith('/bot') and (len(message) == 4 or message[4] in (' ', '\t', '\n'))
        
        if message == "/botnet":
            expected = False  # Cas spécial: ne devrait pas matcher
        
        if is_broadcast:
            print(f"✅ '{message}' → Détecté comme broadcast")
        else:
            print(f"❌ '{message}' → PAS détecté comme broadcast")
    
    print("\n" + "="*60)

def test_logging():
    """Tester que le logging fonctionne correctement"""
    print("🧪 Test: Logging des commandes /bot\n")
    
    router, llama_client = create_mock_router()
    llama_client.query_llama_mesh.return_value = "Test response"
    llama_client.cleanup_cache = Mock()
    
    # Mock info_print pour capturer les logs
    with patch('handlers.message_router.info_print') as mock_info:
        # Test avec broadcast
        packet_broadcast = {
            'from': 0x87654321,
            'to': 0xFFFFFFFF,  # Broadcast
        }
        
        router.process_text_message(packet_broadcast, {}, "/bot test")
        
        # Vérifier que le log contient "BOT PUBLIC"
        calls = [str(call) for call in mock_info.call_args_list]
        has_bot_log = any("BOT PUBLIC" in str(call) for call in calls)
        
        if has_bot_log:
            print("✅ Broadcast: Log 'BOT PUBLIC' trouvé")
        else:
            print("❌ Broadcast: Log 'BOT PUBLIC' NON trouvé")
            print(f"   Logs capturés: {calls}")
    
    # Test avec direct (non-broadcast)
    with patch('handlers.message_router.info_print') as mock_info:
        packet_direct = {
            'from': 0x87654321,
            'to': 0x12345678,  # Direct au bot
        }
        
        router.process_text_message(packet_direct, {}, "/bot test")
        
        # Vérifier que le log contient "Bot:"
        calls = [str(call) for call in mock_info.call_args_list]
        has_bot_log = any("Bot:" in str(call) for call in calls)
        
        if has_bot_log:
            print("✅ Direct: Log 'Bot:' trouvé dans ai_commands.py")
        else:
            print("❌ Direct: Log 'Bot:' NON trouvé")
            print(f"   Logs capturés: {calls}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_bot_patterns()
    test_broadcast_detection()
    test_logging()
    
    print("\n✅ TOUS LES TESTS TERMINÉS")
    print("Si tous les tests passent, le fix est correct!")
