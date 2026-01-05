#!/usr/bin/env python3
"""
Test: Vérifier que les broadcasts ne génèrent pas de logs en double

Contexte:
- Avant: log_conversation était appelé 2x (handler + _send_broadcast_via_tigrog2)
- Après: log_conversation appelé 1x seulement (dans le handler)

Test avec /weather broadcast:
- Vérifie qu'on a 1 seul log de conversation
- Vérifie que le broadcast est bien tracké
- Vérifie que le message est envoyé
"""

from unittest.mock import Mock, MagicMock, patch, call
import sys

def test_weather_broadcast_no_duplicate_logs():
    """Tester que /weather broadcast ne génère qu'UN log de conversation"""
    print("=" * 60)
    print("TEST: /weather broadcast - pas de logs en double")
    print("=" * 60)
    
    # Mock des dépendances
    mock_sender = Mock()
    mock_sender._get_interface = Mock(return_value=Mock())
    mock_sender.log_conversation = Mock()
    
    mock_traffic_monitor = Mock()
    mock_traffic_monitor.persistence = None
    
    mock_esphome_client = Mock()
    mock_node_manager = Mock()
    mock_broadcast_tracker = Mock()
    
    # Mock de get_weather_data pour éviter appel HTTP
    with patch('handlers.command_handlers.utility_commands.get_weather_data') as mock_weather:
        mock_weather.return_value = "📍 Paris, France\nNow: 🌨️ -2°C"
        
        # Créer le handler
        from handlers.command_handlers.utility_commands import UtilityCommands
        handler = UtilityCommands(
            mock_esphome_client,
            mock_traffic_monitor,
            mock_sender,
            mock_node_manager,
            None,  # blitz_monitor
            None,  # vigilance_monitor
            mock_broadcast_tracker
        )
        
        # Appeler handle_weather en mode broadcast
        handler.handle_weather(
            message="/weather",
            sender_id=0xa76f40da,
            sender_info="tigro",
            is_broadcast=True
        )
        
        # Vérifications
        print("\n✓ Vérification des appels...")
        
        # 1. log_conversation doit être appelé UNE SEULE FOIS
        assert mock_sender.log_conversation.call_count == 1, \
            f"❌ log_conversation appelé {mock_sender.log_conversation.call_count} fois (attendu: 1)"
        print(f"✅ log_conversation appelé 1 fois (OK)")
        
        # Vérifier les arguments du log
        call_args = mock_sender.log_conversation.call_args[0]
        assert call_args[0] == 0xa76f40da, "❌ Mauvais sender_id"
        assert call_args[1] == "tigro", "❌ Mauvais sender_info"
        assert call_args[2] == "/weather", "❌ Mauvais query"
        assert "📍 Paris, France" in call_args[3], "❌ Mauvaise response"
        print(f"✅ Arguments log corrects")
        
        # 2. broadcast_tracker doit être appelé
        assert mock_broadcast_tracker.call_count == 1, \
            f"❌ broadcast_tracker appelé {mock_broadcast_tracker.call_count} fois (attendu: 1)"
        print(f"✅ broadcast_tracker appelé 1 fois")
        
        # 3. Interface sendText doit être appelé
        mock_interface = mock_sender._get_interface.return_value
        assert mock_interface.sendText.call_count == 1, \
            f"❌ sendText appelé {mock_interface.sendText.call_count} fois (attendu: 1)"
        print(f"✅ sendText appelé 1 fois")
        
        print("\n" + "=" * 60)
        print("✅ TEST RÉUSSI: Pas de logs en double pour /weather broadcast")
        print("=" * 60)


def test_bot_broadcast_no_duplicate_logs():
    """Tester que /bot broadcast ne génère qu'UN log de conversation"""
    print("\n" + "=" * 60)
    print("TEST: /bot broadcast - pas de logs en double")
    print("=" * 60)
    
    # Mock des dépendances
    mock_sender = Mock()
    mock_sender._get_interface = Mock(return_value=Mock())
    mock_sender.log_conversation = Mock()
    
    mock_llama_client = Mock()
    mock_llama_client.query_llama_mesh = Mock(return_value="Il est 10h45")
    mock_llama_client.cleanup_cache = Mock()
    
    mock_broadcast_tracker = Mock()
    
    # Créer le handler
    from handlers.command_handlers.ai_commands import AICommands
    handler = AICommands(
        mock_llama_client,
        mock_sender,
        mock_broadcast_tracker
    )
    
    # Appeler handle_bot en mode broadcast
    handler.handle_bot(
        message="/bot quelle heure est-il?",
        sender_id=0xa76f40da,
        sender_info="tigro",
        is_broadcast=True
    )
    
    # Vérifications
    print("\n✓ Vérification des appels...")
    
    # 1. log_conversation doit être appelé UNE SEULE FOIS
    assert mock_sender.log_conversation.call_count == 1, \
        f"❌ log_conversation appelé {mock_sender.log_conversation.call_count} fois (attendu: 1)"
    print(f"✅ log_conversation appelé 1 fois (OK)")
    
    # Vérifier les arguments du log
    call_args = mock_sender.log_conversation.call_args[0]
    assert call_args[0] == 0xa76f40da, "❌ Mauvais sender_id"
    assert call_args[1] == "tigro", "❌ Mauvais sender_info"
    assert call_args[2] == "quelle heure est-il?", "❌ Mauvais query (prompt)"
    assert call_args[3] == "Il est 10h45", "❌ Mauvaise response"
    print(f"✅ Arguments log corrects (prompt + response)")
    
    # 2. broadcast_tracker doit être appelé
    assert mock_broadcast_tracker.call_count == 1, \
        f"❌ broadcast_tracker appelé {mock_broadcast_tracker.call_count} fois (attendu: 1)"
    print(f"✅ broadcast_tracker appelé 1 fois")
    
    # 3. Interface sendText doit être appelé
    mock_interface = mock_sender._get_interface.return_value
    assert mock_interface.sendText.call_count == 1, \
        f"❌ sendText appelé {mock_interface.sendText.call_count} fois (attendu: 1)"
    print(f"✅ sendText appelé 1 fois")
    
    print("\n" + "=" * 60)
    print("✅ TEST RÉUSSI: Pas de logs en double pour /bot broadcast")
    print("=" * 60)


def test_my_broadcast_has_logging():
    """Tester que /my broadcast a bien un log (ajouté dans le fix)"""
    print("\n" + "=" * 60)
    print("TEST: /my broadcast - log ajouté")
    print("=" * 60)
    
    # Mock des dépendances
    mock_sender = Mock()
    mock_sender._get_interface = Mock(return_value=Mock())
    mock_sender.log_conversation = Mock()
    
    mock_remote_nodes_client = Mock()
    mock_node_manager = Mock()
    mock_traffic_monitor = Mock()
    mock_interface = Mock()
    mock_broadcast_tracker = Mock()
    
    # Créer le handler
    from handlers.command_handlers.network_commands import NetworkCommands
    handler = NetworkCommands(
        mock_remote_nodes_client,
        mock_sender,
        mock_node_manager,
        mock_traffic_monitor,
        mock_interface,
        None,  # mesh_traceroute
        mock_broadcast_tracker
    )
    
    # Mock de get_remote_nodes
    mock_remote_nodes_client.get_remote_nodes = Mock(return_value=[
        {'id': 0xa76f40da, 'snr': 10.0, 'rssi': -80}
    ])
    
    # Appeler handle_my en mode broadcast
    handler.handle_my(
        sender_id=0xa76f40da,
        sender_info="tigro",
        is_broadcast=True
    )
    
    # Vérifications
    print("\n✓ Vérification des appels...")
    
    # log_conversation doit être appelé
    assert mock_sender.log_conversation.call_count == 1, \
        f"❌ log_conversation appelé {mock_sender.log_conversation.call_count} fois (attendu: 1)"
    print(f"✅ log_conversation appelé 1 fois (ajouté dans le fix)")
    
    print("\n" + "=" * 60)
    print("✅ TEST RÉUSSI: /my broadcast a maintenant un log")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_weather_broadcast_no_duplicate_logs()
        test_bot_broadcast_no_duplicate_logs()
        test_my_broadcast_has_logging()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("=" * 60)
        print("\nRésumé du fix:")
        print("- Suppression de log_conversation dans _send_broadcast_via_tigrog2")
        print("- Ajout de log_conversation dans handlers avant broadcast (où manquant)")
        print("- Résultat: 1 seul log par commande broadcast (pas de doublons)")
        
    except AssertionError as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
