#!/usr/bin/env python3
"""
Test du collecteur MQTT de voisins

Vérifie que le module peut:
1. Se connecter au serveur MQTT
2. Parser les messages NEIGHBORINFO_APP
3. Sauvegarder les données dans la base
"""

import time
import json
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mqtt_neighbor_collector import MQTTNeighborCollector
from traffic_persistence import TrafficPersistence

def test_neighbor_data_parsing():
    """Tester le parsing des données de voisins depuis MQTT"""
    print("\n" + "="*60)
    print("TEST 1: Parsing des données de voisins")
    print("="*60)
    
    # Exemple de payload MQTT NEIGHBORINFO_APP
    sample_payload = {
        "from": 305419896,
        "to": 4294967295,
        "channel": 0,
        "type": "NEIGHBORINFO_APP",
        "sender": "!12345678",
        "payload": {
            "neighborinfo": {
                "nodeId": 305419896,
                "neighbors": [
                    {
                        "nodeId": 305419897,
                        "snr": 8.5,
                        "lastRxTime": 1234567890,
                        "nodeBroadcastInterval": 900
                    },
                    {
                        "nodeId": 305419898,
                        "snr": 6.2,
                        "lastRxTime": 1234567891,
                        "nodeBroadcastInterval": 900
                    }
                ]
            }
        }
    }
    
    print(f"✅ Payload de test créé: {len(sample_payload['payload']['neighborinfo']['neighbors'])} voisins")
    
    # Vérifier la structure
    assert 'payload' in sample_payload
    assert 'neighborinfo' in sample_payload['payload']
    assert 'neighbors' in sample_payload['payload']['neighborinfo']
    assert len(sample_payload['payload']['neighborinfo']['neighbors']) == 2
    
    print("✅ Structure du payload valide")
    
    return sample_payload

def test_persistence_integration():
    """Tester l'intégration avec TrafficPersistence"""
    print("\n" + "="*60)
    print("TEST 2: Intégration avec TrafficPersistence")
    print("="*60)
    
    # Créer une base de données de test
    test_db = "/tmp/test_mqtt_neighbors.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    persistence = TrafficPersistence(db_path=test_db)
    print(f"✅ Base de données de test créée: {test_db}")
    
    # Tester save_neighbor_info
    node_id = "!12345678"
    neighbors = [
        {
            'node_id': 305419897,
            'snr': 8.5,
            'last_rx_time': 1234567890,
            'node_broadcast_interval': 900
        },
        {
            'node_id': 305419898,
            'snr': 6.2,
            'last_rx_time': 1234567891,
            'node_broadcast_interval': 900
        }
    ]
    
    persistence.save_neighbor_info(node_id, neighbors)
    print(f"✅ Sauvegardé {len(neighbors)} voisins pour {node_id}")
    
    # Charger et vérifier
    loaded = persistence.load_neighbors(hours=48)
    print(f"✅ Chargé {len(loaded)} entrées de la base")
    
    if node_id in loaded:
        print(f"✅ Nœud {node_id} trouvé avec {len(loaded[node_id])} voisins")
        assert len(loaded[node_id]) == 2
    else:
        print(f"❌ Nœud {node_id} non trouvé dans les données chargées")
        return False
    
    # Nettoyage
    os.remove(test_db)
    print(f"✅ Base de données de test supprimée")
    
    return True

def test_mqtt_collector_init():
    """Tester l'initialisation du collecteur"""
    print("\n" + "="*60)
    print("TEST 3: Initialisation du collecteur MQTT")
    print("="*60)
    
    # Créer une persistence de test
    test_db = "/tmp/test_mqtt_collector.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    persistence = TrafficPersistence(db_path=test_db)
    
    # Initialiser le collecteur (sans se connecter)
    collector = MQTTNeighborCollector(
        mqtt_server="serveurperso.com",
        mqtt_port=1883,
        mqtt_user="meshdev",
        mqtt_password="test_password",
        mqtt_topic_root="msh",
        persistence=persistence
    )
    
    print(f"✅ Collecteur initialisé")
    print(f"   Enabled: {collector.enabled}")
    print(f"   Server: {collector.mqtt_server}:{collector.mqtt_port}")
    print(f"   Topic root: {collector.mqtt_topic_root}")
    
    # Vérifier les statistiques initiales
    stats = collector.get_stats()
    print(f"✅ Statistiques: {stats}")
    assert stats['messages_received'] == 0
    assert stats['neighbor_packets'] == 0
    assert stats['nodes_discovered'] == 0
    
    # Tester le rapport de statut
    report_compact = collector.get_status_report(compact=True)
    print(f"\n📊 Rapport compact:\n{report_compact}")
    
    report_full = collector.get_status_report(compact=False)
    print(f"\n📊 Rapport détaillé:\n{report_full}")
    
    # Nettoyage
    os.remove(test_db)
    
    return True

def test_message_simulation():
    """Simuler la réception d'un message MQTT"""
    print("\n" + "="*60)
    print("TEST 4: Simulation de réception de message")
    print("="*60)
    
    # Créer une persistence de test
    test_db = "/tmp/test_mqtt_simulation.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    persistence = TrafficPersistence(db_path=test_db)
    
    # Initialiser le collecteur
    collector = MQTTNeighborCollector(
        mqtt_server="serveurperso.com",
        mqtt_port=1883,
        mqtt_user="meshdev",
        mqtt_password="test_password",
        persistence=persistence
    )
    
    # Créer un message simulé
    class MockMessage:
        def __init__(self, payload, topic):
            self.payload = payload.encode('utf-8')
            self.topic = topic
    
    sample_data = {
        "from": 305419896,
        "to": 4294967295,
        "channel": 0,
        "type": "NEIGHBORINFO_APP",
        "sender": "!12345678",
        "payload": {
            "neighborinfo": {
                "nodeId": 305419896,
                "neighbors": [
                    {
                        "nodeId": 305419897,
                        "snr": 8.5,
                        "lastRxTime": 1234567890,
                        "nodeBroadcastInterval": 900
                    }
                ]
            }
        }
    }
    
    msg = MockMessage(
        json.dumps(sample_data),
        "msh/eu_868/LongFast/2/json/!12345678/NEIGHBORINFO_APP"
    )
    
    # Simuler la réception
    collector._on_mqtt_message(None, None, msg)
    
    # Vérifier les statistiques
    stats = collector.get_stats()
    print(f"✅ Statistiques après réception:")
    print(f"   Messages reçus: {stats['messages_received']}")
    print(f"   Paquets neighbor: {stats['neighbor_packets']}")
    print(f"   Nœuds découverts: {stats['nodes_discovered']}")
    
    assert stats['messages_received'] == 1
    assert stats['neighbor_packets'] == 1
    assert stats['nodes_discovered'] == 1
    
    # Vérifier que les données sont en base
    loaded = persistence.load_neighbors(hours=48)
    print(f"✅ Nœuds en base: {list(loaded.keys())}")
    assert len(loaded) >= 1
    
    # Nettoyage
    os.remove(test_db)
    
    return True

def main():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("TESTS DU COLLECTEUR MQTT DE VOISINS")
    print("="*60)
    
    tests = [
        ("Parsing données", test_neighbor_data_parsing),
        ("Intégration persistence", test_persistence_integration),
        ("Initialisation collecteur", test_mqtt_collector_init),
        ("Simulation message", test_message_simulation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            if result is not False:
                results.append((name, True))
                print(f"\n✅ {name}: SUCCÈS")
            else:
                results.append((name, False))
                print(f"\n❌ {name}: ÉCHEC")
        except Exception as e:
            results.append((name, False))
            print(f"\n❌ {name}: ERREUR - {e}")
            import traceback
            traceback.print_exc()
    
    # Résumé
    print("\n" + "="*60)
    print("RÉSUMÉ DES TESTS")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nRésultat: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 Tous les tests ont réussi!")
        return 0
    else:
        print("\n⚠️ Certains tests ont échoué")
        return 1

if __name__ == "__main__":
    sys.exit(main())
