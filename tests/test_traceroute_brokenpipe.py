#!/usr/bin/env python3
"""
Test pour vérifier que BrokenPipeError dans mesh_traceroute_manager est géré gracieusement

Ce test vérifie:
1. BrokenPipeError est loggé en debug (pas error) pour être cohérent avec le reste du code
2. Pas de traceback complet dans les logs
3. Message utilisateur approprié envoyé
"""

import sys
import os
import types
from unittest.mock import Mock, patch, MagicMock

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

# Créer un module config minimal
config_module = types.ModuleType('config')
config_module.DEBUG_MODE = False
sys.modules['config'] = config_module

def test_brokenpipe_graceful_handling():
    """
    Test que BrokenPipeError lors de l'envoi de traceroute est géré gracieusement
    
    Comportement attendu:
    - debug_print() appelé (pas error_print() avec traceback)
    - Message d'erreur envoyé à l'utilisateur
    - Cleanup effectué
    - Retourne False
    """
    print("\n🧪 Test: BrokenPipeError géré gracieusement dans mesh_traceroute_manager")
    
    # Mock des dépendances
    with patch('mesh_traceroute_manager.info_print') as info_print_mock, \
         patch('mesh_traceroute_manager.error_print') as error_print_mock, \
         patch('mesh_traceroute_manager.debug_print') as debug_print_mock:
        
        # Importer après avoir mocké les fonctions
        from mesh_traceroute_manager import MeshTracerouteManager
        
        # Créer des mocks pour NodeManager et MessageSender
        node_manager = Mock()
        node_manager.get_node_name.return_value = "TestNode"
        
        message_sender = Mock()
        
        # Créer le manager
        manager = MeshTracerouteManager(node_manager, message_sender)
        
        # Mock de l'interface qui lève BrokenPipeError
        interface = Mock()
        interface.sendData.side_effect = BrokenPipeError("[Errno 32] Broken pipe")
        
        # Appeler request_traceroute
        result = manager.request_traceroute(
            interface=interface,
            target_node_id=0x12345678,
            requester_id=0x87654321,
            requester_info={'name': 'RequesterNode'}
        )
        
        # Vérifier que la fonction retourne False
        assert result == False, "❌ request_traceroute devrait retourner False en cas de BrokenPipeError"
        print("✅ Retourne False en cas d'erreur")
        
        # Vérifier que debug_print est appelé (pas error_print avec traceback)
        debug_calls = [str(call) for call in debug_print_mock.call_args_list]
        
        # Vérifier qu'il y a au moins un appel à debug_print
        assert len(debug_calls) > 0, "❌ debug_print devrait être appelé"
        print(f"✅ debug_print appelé {len(debug_calls)} fois")
        
        # Vérifier que le message de déconnexion réseau est loggé en debug
        network_lost_logged = any("Connexion réseau perdue" in str(call) or "réseau perdue" in str(call) 
                                   for call in debug_calls)
        assert network_lost_logged, "❌ Le message 'Connexion réseau perdue' devrait être loggé en debug"
        print("✅ Message 'Connexion réseau perdue' loggé en debug")
        
        # Vérifier que error_print N'est PAS appelé avec traceback complet
        error_calls = [str(call) for call in error_print_mock.call_args_list]
        
        # Filtrer les appels qui ne sont pas des exceptions génériques
        brokenpipe_error_calls = [call for call in error_calls 
                                   if 'BrokenPipe' in call or 'Interface type' in call]
        
        assert len(brokenpipe_error_calls) == 0, \
            f"❌ error_print ne devrait PAS être appelé pour BrokenPipeError (trouvé: {brokenpipe_error_calls})"
        print("✅ Pas de error_print avec traceback pour BrokenPipeError")
        
        # Vérifier que le message utilisateur est envoyé
        message_sender.send_single.assert_called()
        call_args = message_sender.send_single.call_args
        message_text = call_args[0][0]
        
        assert "Interface Meshtastic déconnectée" in message_text or "déconnectée" in message_text, \
            "❌ Le message utilisateur devrait mentionner la déconnexion"
        print("✅ Message d'erreur approprié envoyé à l'utilisateur")
        
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        return True

def test_other_exceptions_still_logged():
    """
    Test que les autres exceptions (non-BrokenPipeError) sont toujours loggées normalement
    """
    print("\n🧪 Test: Autres exceptions loggées normalement")
    
    with patch('mesh_traceroute_manager.info_print') as info_print_mock, \
         patch('mesh_traceroute_manager.error_print') as error_print_mock, \
         patch('mesh_traceroute_manager.debug_print') as debug_print_mock:
        
        from mesh_traceroute_manager import MeshTracerouteManager
        
        node_manager = Mock()
        node_manager.get_node_name.return_value = "TestNode"
        message_sender = Mock()
        
        manager = MeshTracerouteManager(node_manager, message_sender)
        
        # Mock de l'interface qui lève une autre exception
        interface = Mock()
        interface.sendData.side_effect = RuntimeError("Test error")
        
        # Appeler request_traceroute
        result = manager.request_traceroute(
            interface=interface,
            target_node_id=0x12345678,
            requester_id=0x87654321,
            requester_info={'name': 'RequesterNode'}
        )
        
        # Vérifier que error_print est appelé pour les autres exceptions
        error_calls = [str(call) for call in error_print_mock.call_args_list]
        
        # Il devrait y avoir au moins un appel à error_print pour RuntimeError
        assert len(error_calls) > 0, "❌ error_print devrait être appelé pour RuntimeError"
        print(f"✅ error_print appelé pour RuntimeError: {len(error_calls)} fois")
        
        print("✅ Test réussi")
        return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST GESTION BROKENPIPEERROR - MESH_TRACEROUTE_MANAGER")
    print("=" * 70)
    
    results = [
        test_brokenpipe_graceful_handling(),
        test_other_exceptions_still_logged(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nBrokenPipeError est maintenant géré gracieusement:")
        print("- Loggé en DEBUG (pas ERROR)")
        print("- Pas de traceback complet dans les logs")
        print("- Message utilisateur approprié")
        print("- Cohérent avec le reste du code (main_bot.py)")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
