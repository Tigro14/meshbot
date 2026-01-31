#!/usr/bin/env python3
"""
Tests pour MeshAlertManager
Vérifie l'envoi d'alertes DM aux nœuds abonnés
"""

import sys
import time
from typing import Dict

# Mock config
class MockConfig:
    DEBUG_MODE = True
    MESH_ALERTS_ENABLED = True
    MESH_ALERT_SUBSCRIBED_NODES = [0x16fad3dc, 0x12345678]
    MESH_ALERT_THROTTLE_SECONDS = 10  # 10s pour les tests
    MAX_MESSAGE_SIZE = 180

sys.modules['config'] = MockConfig()

from mesh_alert_manager import MeshAlertManager


class MockMessageSender:
    """Mock MessageSender pour les tests"""
    def __init__(self):
        self.sent_messages = []  # Liste des messages envoyés
        
    def send_single(self, message, node_id, node_info):
        """Simuler l'envoi d'un message"""
        self.sent_messages.append({
            'message': message,
            'node_id': node_id,
            'node_info': node_info,
            'timestamp': time.time()
        })
        print(f"✅ Mock envoi à 0x{node_id:08x}: {message[:50]}...")


def test_initialization():
    """Test 1: Initialisation du gestionnaire"""
    print("\n=== Test 1: Initialisation ===")
    
    sender = MockMessageSender()
    nodes = [0x16fad3dc, 0x12345678]
    
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=nodes,
        throttle_seconds=10
    )
    
    assert manager.subscribed_nodes == nodes
    assert manager.throttle_seconds == 10
    assert manager.total_alerts_sent == 0
    assert manager.alerts_throttled == 0
    
    print("✅ Initialisation OK")


def test_send_alert_basic():
    """Test 2: Envoi d'alerte basique"""
    print("\n=== Test 2: Envoi d'alerte basique ===")
    
    sender = MockMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc, 0x12345678],
        throttle_seconds=10
    )
    
    sent_count = manager.send_alert(
        alert_type='vigilance',
        message='🟠 VIGILANCE ORANGE\nDept 25\nVent violent: Orange'
    )
    
    assert sent_count == 2  # 2 nœuds
    assert len(sender.sent_messages) == 2
    assert manager.total_alerts_sent == 2
    
    # Vérifier les destinataires
    sent_ids = [msg['node_id'] for msg in sender.sent_messages]
    assert 0x16fad3dc in sent_ids
    assert 0x12345678 in sent_ids
    
    print(f"✅ Alerte envoyée à {sent_count} nœuds")


def test_throttling():
    """Test 3: Throttling des alertes"""
    print("\n=== Test 3: Throttling ===")
    
    sender = MockMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc],
        throttle_seconds=5  # 5 secondes
    )
    
    # Premier envoi
    sent1 = manager.send_alert(
        alert_type='blitz',
        message='⚡ 5 éclairs (15min)\n+ proche: 12.3km'
    )
    assert sent1 == 1
    assert manager.total_alerts_sent == 1
    
    # Deuxième envoi immédiat (doit être throttlé)
    sent2 = manager.send_alert(
        alert_type='blitz',
        message='⚡ 7 éclairs (15min)\n+ proche: 10.5km'
    )
    assert sent2 == 0  # Throttlé
    assert manager.alerts_throttled == 1
    assert manager.total_alerts_sent == 1  # Pas augmenté
    
    print("✅ Throttling fonctionne")
    
    # Attendre et réessayer
    print("⏳ Attente 6 secondes pour expiration throttle...")
    time.sleep(6)
    
    sent3 = manager.send_alert(
        alert_type='blitz',
        message='⚡ 8 éclairs (15min)\n+ proche: 8.2km'
    )
    assert sent3 == 1  # Doit passer
    assert manager.total_alerts_sent == 2
    
    print("✅ Alerte envoyée après expiration throttle")


def test_different_alert_types():
    """Test 4: Types d'alertes différents (pas de throttling croisé)"""
    print("\n=== Test 4: Types d'alertes différents ===")
    
    sender = MockMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc],
        throttle_seconds=60
    )
    
    # Alerte vigilance
    sent1 = manager.send_alert(
        alert_type='vigilance',
        message='🟠 VIGILANCE ORANGE'
    )
    assert sent1 == 1
    
    # Alerte blitz immédiate (type différent = pas throttlé)
    sent2 = manager.send_alert(
        alert_type='blitz',
        message='⚡ 10 éclairs détectés'
    )
    assert sent2 == 1
    
    # Même type vigilance (doit être throttlé)
    sent3 = manager.send_alert(
        alert_type='vigilance',
        message='🔴 VIGILANCE ROUGE'
    )
    assert sent3 == 0  # Throttlé
    
    print("✅ Throttling par type d'alerte fonctionne")


def test_force_flag():
    """Test 5: Flag force pour ignorer throttling"""
    print("\n=== Test 5: Flag force ===")
    
    sender = MockMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc],
        throttle_seconds=60
    )
    
    # Premier envoi
    sent1 = manager.send_alert(
        alert_type='vigilance',
        message='🟠 VIGILANCE ORANGE'
    )
    assert sent1 == 1
    
    # Deuxième envoi avec force=True
    sent2 = manager.send_alert(
        alert_type='vigilance',
        message='🔴 VIGILANCE ROUGE (URGENT)',
        force=True
    )
    assert sent2 == 1  # Doit passer malgré throttling
    
    print("✅ Flag force ignore le throttling")


def test_multiple_nodes():
    """Test 6: Envoi à plusieurs nœuds"""
    print("\n=== Test 6: Plusieurs nœuds ===")
    
    sender = MockMessageSender()
    nodes = [0x16fad3dc, 0x12345678, 0xabcdef01, 0x99887766]
    
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=nodes,
        throttle_seconds=10
    )
    
    sent = manager.send_alert(
        alert_type='blitz',
        message='⚡ Orage violent détecté'
    )
    
    assert sent == len(nodes)
    assert len(sender.sent_messages) == len(nodes)
    
    # Vérifier tous les nœuds ont reçu
    sent_ids = [msg['node_id'] for msg in sender.sent_messages]
    for node_id in nodes:
        assert node_id in sent_ids
    
    print(f"✅ Alerte envoyée à {len(nodes)} nœuds")


def test_empty_nodes_list():
    """Test 7: Liste de nœuds vide"""
    print("\n=== Test 7: Liste vide ===")
    
    sender = MockMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[],
        throttle_seconds=10
    )
    
    sent = manager.send_alert(
        alert_type='vigilance',
        message='🟠 VIGILANCE ORANGE'
    )
    
    assert sent == 0
    assert len(sender.sent_messages) == 0
    
    print("✅ Aucune alerte envoyée (liste vide OK)")


def test_stats():
    """Test 8: Statistiques"""
    print("\n=== Test 8: Statistiques ===")
    
    sender = MockMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc, 0x12345678],
        throttle_seconds=5
    )
    
    # Envoyer quelques alertes
    manager.send_alert('vigilance', 'Alerte 1')
    manager.send_alert('blitz', 'Alerte 2')
    manager.send_alert('vigilance', 'Alerte 3')  # Throttlé
    
    stats = manager.get_stats()
    assert stats['subscribed_nodes'] == 2
    assert stats['total_alerts_sent'] == 4  # 2 types x 2 nœuds
    assert stats['alerts_throttled'] == 2  # 2 nœuds throttlés
    
    print(f"✅ Stats: {stats}")


def test_status_report():
    """Test 9: Rapport de statut"""
    print("\n=== Test 9: Rapport de statut ===")
    
    sender = MockMessageSender()
    manager = MeshAlertManager(
        message_sender=sender,
        subscribed_nodes=[0x16fad3dc, 0x12345678],
        throttle_seconds=10
    )
    
    # Envoyer une alerte
    manager.send_alert('vigilance', 'Test')
    
    # Rapport compact
    report_compact = manager.get_status_report(compact=True)
    assert '📢 Alertes Mesh' in report_compact
    assert '2 nœuds' in report_compact
    
    # Rapport détaillé
    report_full = manager.get_status_report(compact=False)
    assert '0x16fad3dc' in report_full
    assert '0x12345678' in report_full
    
    print("✅ Rapports générés:")
    print("\nCompact:")
    print(report_compact)
    print("\nDétaillé:")
    print(report_full)


def run_all_tests():
    """Exécuter tous les tests"""
    print("=" * 60)
    print("TESTS MESH ALERT MANAGER")
    print("=" * 60)
    
    try:
        test_initialization()
        test_send_alert_basic()
        test_throttling()
        test_different_alert_types()
        test_force_flag()
        test_multiple_nodes()
        test_empty_nodes_list()
        test_stats()
        test_status_report()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
