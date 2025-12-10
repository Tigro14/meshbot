#!/usr/bin/env python3
"""
Test de la commande /propag - Liaisons radio les plus longues
"""

import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_traffic_persistence_method():
    """Test de la méthode load_radio_links_with_positions"""
    print("=" * 60)
    print("TEST 1: TrafficPersistence.load_radio_links_with_positions()")
    print("=" * 60)
    
    try:
        from traffic_persistence import TrafficPersistence
        
        # Créer instance (utilisera traffic_history.db s'il existe)
        persistence = TrafficPersistence("traffic_history.db")
        
        # Charger les liaisons des dernières 24h
        links = persistence.load_radio_links_with_positions(hours=24)
        
        print(f"✅ Méthode appelée avec succès")
        print(f"📊 Liaisons trouvées: {len(links)}")
        
        if links:
            print("\n🔍 Aperçu des 3 premières liaisons:")
            for i, link in enumerate(links[:3], 1):
                print(f"\n  Liaison {i}:")
                print(f"    From ID: {link.get('from_id')}")
                print(f"    To ID: {link.get('to_id')}")
                print(f"    SNR: {link.get('snr')}")
                print(f"    RSSI: {link.get('rssi')}")
                print(f"    Timestamp: {link.get('timestamp')}")
        else:
            print("⚠️  Aucune liaison trouvée (base de données vide ou récente)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_traffic_monitor_method():
    """Test de la méthode get_propagation_report"""
    print("\n" + "=" * 60)
    print("TEST 2: TrafficMonitor.get_propagation_report()")
    print("=" * 60)
    
    try:
        from traffic_monitor import TrafficMonitor
        from traffic_persistence import TrafficPersistence
        from node_manager import NodeManager
        
        # Créer instances
        node_manager = NodeManager()
        node_manager.load_node_names()
        
        traffic_monitor = TrafficMonitor(node_manager)
        
        print("✅ TrafficMonitor créé")
        
        # Tester format compact (LoRa)
        print("\n📡 Test format COMPACT (LoRa):")
        report_compact = traffic_monitor.get_propagation_report(
            hours=24,
            top_n=5,
            max_distance_km=100,
            compact=True
        )
        print(f"Longueur: {len(report_compact)} caractères")
        print(f"Contenu:\n{report_compact}")
        
        # Tester format détaillé (Telegram)
        print("\n📱 Test format DÉTAILLÉ (Telegram):")
        report_detailed = traffic_monitor.get_propagation_report(
            hours=24,
            top_n=5,
            max_distance_km=100,
            compact=False
        )
        print(f"Longueur: {len(report_detailed)} caractères")
        print(f"Contenu:\n{report_detailed}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_handler():
    """Test du handler de commande"""
    print("\n" + "=" * 60)
    print("TEST 3: NetworkCommands.handle_propag()")
    print("=" * 60)
    
    try:
        from handlers.command_handlers.network_commands import NetworkCommands
        from handlers.message_sender import MessageSender
        from node_manager import NodeManager
        from traffic_monitor import TrafficMonitor
        from remote_nodes_client import RemoteNodesClient
        
        # Créer instances mock
        node_manager = NodeManager()
        node_manager.load_node_names()
        
        traffic_monitor = TrafficMonitor(node_manager)
        
        # Interface mock (None pour le test)
        interface_mock = None
        
        # Créer sender mock
        sender = MessageSender(interface_mock, node_manager)
        
        # Créer remote_nodes_client mock
        remote_client = RemoteNodesClient()
        
        # Créer handler
        network_handler = NetworkCommands(
            remote_client,
            sender,
            node_manager,
            traffic_monitor=traffic_monitor,
            interface=interface_mock
        )
        
        print("✅ NetworkCommands créé")
        
        # Test avec arguments par défaut
        print("\n📝 Test: /propag")
        # Note: handle_propag essaiera d'envoyer un message, mais comme sender est mock,
        # on va juste vérifier qu'il ne crashe pas
        
        # On pourrait créer un vrai test unitaire ici, mais pour l'instant
        # on vérifie juste que la méthode existe
        assert hasattr(network_handler, 'handle_propag')
        print("✅ Méthode handle_propag existe")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_message_routing():
    """Test du routage de la commande"""
    print("\n" + "=" * 60)
    print("TEST 4: Routage /propag dans MessageRouter")
    print("=" * 60)
    
    try:
        # Vérifier que la commande est bien routée
        with open('handlers/message_router.py', 'r') as f:
            content = f.read()
            if '/propag' in content:
                print("✅ Commande /propag trouvée dans MessageRouter")
                if 'handle_propag' in content:
                    print("✅ Appel à handle_propag trouvé")
                    return True
                else:
                    print("❌ Appel à handle_propag non trouvé")
                    return False
            else:
                print("❌ Commande /propag non trouvée dans MessageRouter")
                return False
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_help_text():
    """Test de la présence dans le help"""
    print("\n" + "=" * 60)
    print("TEST 5: /propag dans le help text")
    print("=" * 60)
    
    try:
        # Vérifier que la commande est dans le help
        with open('handlers/command_handlers/utility_commands.py', 'r') as f:
            content = f.read()
            if '/propag' in content:
                print("✅ Commande /propag trouvée dans le help text")
                return True
            else:
                print("❌ Commande /propag non trouvée dans le help text")
                return False
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    """Exécuter tous les tests"""
    print("🧪 TESTS DE LA COMMANDE /PROPAG")
    print("=" * 60)
    
    results = {
        "TrafficPersistence": test_traffic_persistence_method(),
        "TrafficMonitor": test_traffic_monitor_method(),
        "CommandHandler": test_command_handler(),
        "MessageRouting": test_message_routing(),
        "HelpText": test_help_text()
    }
    
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20s} : {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 TOUS LES TESTS ONT RÉUSSI!")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
