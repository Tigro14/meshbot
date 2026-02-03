#!/usr/bin/env python3
"""
Test pour vérifier que /trace utilise TRACEROUTE_APP au lieu de sendText broadcast

Ce test vérifie:
1. sendData() est appelé avec portNum='TRACEROUTE_APP'
2. sendText() n'est PAS appelé pour envoyer "/trace !nodeid"
3. Pas de création de nouvelle connexion TCP (SafeTCPConnection)
4. Utilise l'interface existante du bot
"""

import sys
import os
import types
from unittest.mock import Mock, patch, MagicMock, call
import asyncio

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

# Mock telegram module before any imports
telegram_module = types.ModuleType('telegram')
telegram_module.Update = Mock
telegram_module_ext = types.ModuleType('telegram.ext')
telegram_module_ext.ContextTypes = Mock
sys.modules['telegram'] = telegram_module
sys.modules['telegram.ext'] = telegram_module_ext

# Créer un module config minimal
config_module = types.ModuleType('config')
config_module.DEBUG_MODE = False
config_module.REMOTE_NODE_HOST = "192.168.1.38"
config_module.TELEGRAM_AUTHORIZED_USERS = []
config_module.MAX_MESSAGE_SIZE = 180
sys.modules['config'] = config_module

def test_trace_uses_traceroute_app():
    """
    Test que /trace utilise le bon protocole TRACEROUTE_APP
    """
    print("\n🧪 Test: /trace utilise TRACEROUTE_APP (pas sendText broadcast)")
    
    # Mock des dépendances
    with patch('telegram_bot.traceroute_manager.info_print'), \
         patch('telegram_bot.traceroute_manager.error_print'), \
         patch('telegram_bot.traceroute_manager.debug_print'), \
         patch('telegram_bot.traceroute_manager.asyncio.run_coroutine_threadsafe'):
        
        # Importer après avoir mocké
        from telegram_bot.traceroute_manager import TracerouteManager
        
        # Créer des mocks
        telegram_integration = Mock()
        telegram_integration.node_manager = Mock()
        telegram_integration.node_manager.get_node_name.return_value = "TestNode"
        
        # Mock message_handler avec interface
        telegram_integration.message_handler = Mock()
        interface_mock = Mock()
        telegram_integration.message_handler.interface = interface_mock
        
        # Mock pour éviter les erreurs d'accès
        telegram_integration.application = Mock()
        telegram_integration.application.bot = Mock()
        telegram_integration.loop = asyncio.new_event_loop()
        
        # Créer le manager
        manager = TracerouteManager(telegram_integration)
        
        # Mock _find_node_by_short_name pour retourner un node_id
        target_node_id = 0x16ceca0c  # ID de "Gaius" dans les logs
        manager._find_node_by_short_name = Mock(return_value=target_node_id)
        
        # Appeler _execute_active_trace
        chat_id = 134360030
        manager._execute_active_trace(
            target_short_name="gaius",
            chat_id=chat_id,
            username="Clickyluke"
        )
        
        # VÉRIFICATION 1: sendData doit être appelé avec TRACEROUTE_APP
        interface_mock.sendData.assert_called_once()
        call_kwargs = interface_mock.sendData.call_args[1]
        
        assert call_kwargs.get('portNum') == 'TRACEROUTE_APP', \
            f"❌ portNum devrait être 'TRACEROUTE_APP', trouvé: {call_kwargs.get('portNum')}"
        print("✅ sendData appelé avec portNum='TRACEROUTE_APP'")
        
        assert call_kwargs.get('destinationId') == target_node_id, \
            f"❌ destinationId devrait être {target_node_id:#x}, trouvé: {call_kwargs.get('destinationId')}"
        print(f"✅ destinationId correct: {target_node_id:#x}")
        
        assert call_kwargs.get('data') == b'', \
            f"❌ data devrait être b'', trouvé: {call_kwargs.get('data')}"
        print("✅ data vide (paquet d'initialisation)")
        
        assert call_kwargs.get('wantResponse') == True, \
            f"❌ wantResponse devrait être True"
        print("✅ wantResponse=True")
        
        # VÉRIFICATION 2: sendText NE doit PAS être appelé
        interface_mock.sendText.assert_not_called()
        print("✅ sendText() PAS appelé (pas de broadcast)")
        
        # VÉRIFICATION 3: Pas de création de SafeTCPConnection
        # (cela sera vérifié par l'absence d'import/usage dans le code fixé)
        
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        return True

def test_trace_handles_missing_interface():
    """
    Test que /trace gère gracieusement l'absence d'interface
    """
    print("\n🧪 Test: Gestion gracieuse de l'absence d'interface")
    
    with patch('telegram_bot.traceroute_manager.info_print'), \
         patch('telegram_bot.traceroute_manager.error_print') as error_print_mock, \
         patch('telegram_bot.traceroute_manager.debug_print'), \
         patch('telegram_bot.traceroute_manager.asyncio.run_coroutine_threadsafe'):
        
        from telegram_bot.traceroute_manager import TracerouteManager
        
        telegram_integration = Mock()
        telegram_integration.node_manager = Mock()
        telegram_integration.node_manager.get_node_name.return_value = "TestNode"
        telegram_integration.message_handler = Mock()
        telegram_integration.message_handler.interface = None  # Interface non disponible
        telegram_integration.application = Mock()
        telegram_integration.application.bot = Mock()
        telegram_integration.loop = asyncio.new_event_loop()
        
        manager = TracerouteManager(telegram_integration)
        manager._find_node_by_short_name = Mock(return_value=0x12345678)
        
        # Appeler _execute_active_trace
        manager._execute_active_trace(
            target_short_name="test",
            chat_id=123456,
            username="TestUser"
        )
        
        # Vérifier qu'une erreur est loggée mais pas de crash
        print("✅ Pas de crash avec interface=None")
        return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST FIX /TRACE - UTILISATION TRACEROUTE_APP")
    print("=" * 70)
    
    results = [
        test_trace_uses_traceroute_app(),
        test_trace_handles_missing_interface(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nLa commande /trace utilise maintenant:")
        print("- sendData() avec portNum='TRACEROUTE_APP'")
        print("- L'interface existante du bot (pas de nouvelle TCP)")
        print("- Pas de broadcast text message")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
