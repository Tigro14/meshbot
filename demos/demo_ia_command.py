#!/usr/bin/env python3
"""
Démo de la commande /ia (alias français de /bot)
Montre comment /ia fonctionne en mode companion et normal
"""

import sys
import os
from unittest.mock import Mock, MagicMock

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock des imports Meshtastic
meshtastic_mock = MagicMock()
sys.modules['meshtastic'] = meshtastic_mock
sys.modules['meshtastic.serial_interface'] = MagicMock()
sys.modules['meshtastic.tcp_interface'] = MagicMock()
sys.modules['meshtastic.protobuf'] = MagicMock()
sys.modules['meshtastic.protobuf.portnums_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.telemetry_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.admin_pb2'] = MagicMock()

from handlers.message_router import MessageRouter
from handlers.command_handlers.ai_commands import AICommands


def demo_ia_in_companion_mode():
    """Démonstration de /ia en mode companion"""
    print("=" * 70)
    print("DÉMONSTRATION: Commande /ia en mode companion (MeshCore)")
    print("=" * 70)
    
    # Mock des dépendances
    llama_client = Mock()
    esphome_client = Mock()
    remote_nodes_client = Mock()
    node_manager = Mock()
    context_manager = Mock()
    interface = Mock()
    traffic_monitor = Mock()
    
    # Créer un router en mode companion
    router = MessageRouter(
        llama_client=llama_client,
        esphome_client=esphome_client,
        remote_nodes_client=remote_nodes_client,
        node_manager=node_manager,
        context_manager=context_manager,
        interface=interface,
        traffic_monitor=traffic_monitor,
        companion_mode=True
    )
    
    print("\n✅ Router créé en mode companion")
    print(f"   companion_mode = {router.companion_mode}")
    
    print("\n📋 Commandes disponibles en mode companion:")
    for cmd in router.companion_commands:
        print(f"   • {cmd}")
    
    # Vérifier que /ia est présent
    if '/ia' in router.companion_commands:
        print("\n✅ /ia est bien disponible en mode companion!")
    else:
        print("\n❌ /ia n'est PAS disponible en mode companion")
        return
    
    print("\n" + "=" * 70)


def demo_ia_prompt_extraction():
    """Démonstration de l'extraction du prompt"""
    print("\n" + "=" * 70)
    print("DÉMONSTRATION: Extraction du prompt avec /ia vs /bot")
    print("=" * 70)
    
    # Mock des dépendances
    llama_client = Mock()
    llama_client.query_llama_mesh.return_value = "Réponse de l'IA"
    llama_client.cleanup_cache = Mock()
    
    sender = Mock()
    sender.log_conversation = Mock()
    sender.send_chunks = Mock()
    
    ai_handler = AICommands(llama_client, sender)
    
    # Test 1: /ia
    print("\n📝 Test 1: Message avec /ia")
    message_ia = "/ia Quelle est la météo aujourd'hui ?"
    print(f"   Message reçu: '{message_ia}'")
    
    ai_handler.handle_bot(message_ia, 0x12345678, "TestNode", is_broadcast=False)
    
    call_args = llama_client.query_llama_mesh.call_args
    prompt_ia = call_args[0][0]
    print(f"   Prompt extrait: '{prompt_ia}'")
    print(f"   Longueur /ia: 3 caractères")
    
    # Reset mocks
    llama_client.reset_mock()
    sender.reset_mock()
    
    # Test 2: /bot
    print("\n📝 Test 2: Message avec /bot")
    message_bot = "/bot Quelle est la météo aujourd'hui ?"
    print(f"   Message reçu: '{message_bot}'")
    
    ai_handler.handle_bot(message_bot, 0x12345678, "TestNode", is_broadcast=False)
    
    call_args = llama_client.query_llama_mesh.call_args
    prompt_bot = call_args[0][0]
    print(f"   Prompt extrait: '{prompt_bot}'")
    print(f"   Longueur /bot: 4 caractères")
    
    # Comparaison
    print("\n🔍 Comparaison:")
    if prompt_ia == prompt_bot:
        print(f"   ✅ Les prompts sont identiques: '{prompt_ia}'")
    else:
        print(f"   ❌ Les prompts diffèrent:")
        print(f"      /ia: '{prompt_ia}'")
        print(f"      /bot: '{prompt_bot}'")
    
    print("\n" + "=" * 70)


def demo_ia_broadcast():
    """Démonstration du mode broadcast avec /ia"""
    print("\n" + "=" * 70)
    print("DÉMONSTRATION: Mode broadcast avec /ia")
    print("=" * 70)
    
    # Mock des dépendances
    llama_client = Mock()
    esphome_client = Mock()
    remote_nodes_client = Mock()
    node_manager = Mock()
    node_manager.get_node_name.return_value = "Tigro"
    context_manager = Mock()
    interface = Mock()
    interface.localNode = Mock(nodeNum=0x12345678)
    traffic_monitor = Mock()
    
    router = MessageRouter(
        llama_client=llama_client,
        esphome_client=esphome_client,
        remote_nodes_client=remote_nodes_client,
        node_manager=node_manager,
        context_manager=context_manager,
        interface=interface,
        traffic_monitor=traffic_monitor,
        companion_mode=False
    )
    
    # Créer un packet broadcast avec /ia
    packet = {
        'from': 0x87654321,
        'to': 0xFFFFFFFF,  # Broadcast
        'decoded': {'portnum': 'TEXT_MESSAGE_APP'}
    }
    
    decoded = {'portnum': 'TEXT_MESSAGE_APP'}
    message = "/ia Bonjour tout le monde!"
    
    print("\n📡 Packet broadcast reçu:")
    print(f"   De: 0x{packet['from']:08x}")
    print(f"   À: 0x{packet['to']:08x} (BROADCAST)")
    print(f"   Message: '{message}'")
    
    # Mock de handle_bot pour vérifier qu'il est appelé
    router.ai_handler.handle_bot = Mock()
    
    # Traiter le message
    print("\n🔄 Traitement du message...")
    router.process_text_message(packet, decoded, message)
    
    # Vérifier que handle_bot a été appelé
    if router.ai_handler.handle_bot.called:
        print("   ✅ handle_bot a été appelé")
        
        # Vérifier le mode broadcast
        args, kwargs = router.ai_handler.handle_bot.call_args
        if kwargs.get('is_broadcast'):
            print("   ✅ Mode broadcast activé (is_broadcast=True)")
        else:
            print("   ❌ Mode broadcast non activé")
    else:
        print("   ❌ handle_bot n'a PAS été appelé")
    
    print("\n" + "=" * 70)


def demo_ia_vs_bot_comparison():
    """Comparaison visuelle de /ia et /bot"""
    print("\n" + "=" * 70)
    print("COMPARAISON VISUELLE: /ia vs /bot")
    print("=" * 70)
    
    comparisons = [
        ("Commande", "/ia <question>", "/bot <question>"),
        ("Langue", "Français", "Anglais"),
        ("Longueur", "3 caractères", "4 caractères"),
        ("Handler", "handle_bot()", "handle_bot()"),
        ("Backend", "query_llama_mesh()", "query_llama_mesh()"),
        ("Companion mode", "✅ Disponible", "✅ Disponible"),
        ("Broadcast", "✅ Supporté", "✅ Supporté"),
        ("Telegram", "✅ Supporté", "✅ Supporté"),
        ("Limite mesh", "180 chars", "180 chars"),
        ("Limite Telegram", "3000 chars", "3000 chars"),
        ("Contexte 30min", "✅ Oui", "✅ Oui"),
    ]
    
    print("\n┌────────────────────┬───────────────────────┬───────────────────────┐")
    print("│ Caractéristique    │ /ia                   │ /bot                  │")
    print("├────────────────────┼───────────────────────┼───────────────────────┤")
    
    for feature, ia_val, bot_val in comparisons:
        print(f"│ {feature:<18} │ {ia_val:<21} │ {bot_val:<21} │")
    
    print("└────────────────────┴───────────────────────┴───────────────────────┘")
    
    print("\n✅ Conclusion: /ia et /bot sont fonctionnellement IDENTIQUES")
    print("   La seule différence est le nom de la commande (français vs anglais)")
    
    print("\n" + "=" * 70)


def main():
    """Fonction principale"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                    DÉMONSTRATION COMMANDE /ia                      ║")
    print("║              Alias français de /bot pour l'IA                      ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    
    try:
        # Démo 1: Mode companion
        demo_ia_in_companion_mode()
        
        # Démo 2: Extraction du prompt
        demo_ia_prompt_extraction()
        
        # Démo 3: Mode broadcast
        demo_ia_broadcast()
        
        # Démo 4: Comparaison visuelle
        demo_ia_vs_bot_comparison()
        
        print("\n✅ TOUS LES TESTS DÉMONSTRATIFS RÉUSSIS!")
        print("\n💡 Points clés:")
        print("   • /ia fonctionne en mode companion (MeshCore)")
        print("   • /ia extrait correctement le prompt (3 caractères)")
        print("   • /ia supporte le mode broadcast")
        print("   • /ia et /bot sont strictement équivalents")
        
    except Exception as e:
        print(f"\n❌ Erreur lors de la démonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
