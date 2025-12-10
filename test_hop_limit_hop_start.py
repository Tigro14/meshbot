#!/usr/bin/env python3
"""
Test que hop_limit et hop_start sont correctement sauvegardés dans la base de données.
"""

import os
import sqlite3
import tempfile
import time
from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor
from node_manager import NodeManager


def test_hop_limit_hop_start_columns_exist():
    """Test que les colonnes hop_limit et hop_start existent dans la table packets."""
    print("\n=== Test 1: Vérification existence des colonnes hop_limit et hop_start ===")
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer une instance TrafficPersistence
        persistence = TrafficPersistence(db_path=db_path)
        
        # Vérifier que les colonnes existent
        cursor = persistence.conn.cursor()
        cursor.execute("PRAGMA table_info(packets)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Colonnes de la table packets: {columns}")
        
        assert 'hop_limit' in columns, "La colonne hop_limit n'existe pas"
        assert 'hop_start' in columns, "La colonne hop_start n'existe pas"
        
        print("✅ Les colonnes hop_limit et hop_start existent")
        
        persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_migration_existing_database():
    """Test que la migration fonctionne sur une base existante."""
    print("\n=== Test 2: Vérification migration base existante ===")
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer une base de données avec l'ancien schéma (sans hop_limit/hop_start)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                from_id TEXT NOT NULL,
                to_id TEXT,
                source TEXT,
                sender_name TEXT,
                packet_type TEXT NOT NULL,
                message TEXT,
                rssi INTEGER,
                snr REAL,
                hops INTEGER,
                size INTEGER,
                is_broadcast INTEGER,
                is_encrypted INTEGER DEFAULT 0,
                telemetry TEXT,
                position TEXT
            )
        ''')
        conn.commit()
        conn.close()
        
        print("Base de données créée avec ancien schéma")
        
        # Ouvrir avec TrafficPersistence (devrait déclencher la migration)
        persistence = TrafficPersistence(db_path=db_path)
        
        # Vérifier que les colonnes ont été ajoutées
        cursor = persistence.conn.cursor()
        cursor.execute("PRAGMA table_info(packets)")
        columns = [row[1] for row in cursor.fetchall()]
        
        assert 'hop_limit' in columns, "La migration n'a pas ajouté hop_limit"
        assert 'hop_start' in columns, "La migration n'a pas ajouté hop_start"
        
        print("✅ Migration réussie - colonnes ajoutées")
        
        persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_save_and_load_hop_data():
    """Test que hop_limit et hop_start sont correctement sauvegardés et chargés."""
    print("\n=== Test 3: Sauvegarde et chargement de hop_limit/hop_start ===")
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer une instance TrafficPersistence
        persistence = TrafficPersistence(db_path=db_path)
        
        # Créer un paquet de test avec hop_limit et hop_start
        test_packet = {
            'timestamp': time.time(),
            'from_id': '!12345678',
            'to_id': '!87654321',
            'source': 'serial',
            'sender_name': 'TestNode',
            'packet_type': 'TEXT_MESSAGE_APP',
            'message': 'Test message',
            'rssi': -100,
            'snr': 5.5,
            'hops': 2,
            'hop_limit': 1,
            'hop_start': 3,
            'size': 50,
            'is_broadcast': False,
            'is_encrypted': False
        }
        
        # Sauvegarder le paquet
        persistence.save_packet(test_packet)
        print("Paquet sauvegardé avec hop_limit=1, hop_start=3")
        
        # Charger le paquet
        packets = persistence.load_packets(hours=1)
        
        assert len(packets) == 1, f"Attendu 1 paquet, reçu {len(packets)}"
        
        loaded_packet = packets[0]
        
        # Vérifier que hop_limit et hop_start sont présents et corrects
        assert 'hop_limit' in loaded_packet, "hop_limit manquant dans le paquet chargé"
        assert 'hop_start' in loaded_packet, "hop_start manquant dans le paquet chargé"
        assert loaded_packet['hop_limit'] == 1, f"hop_limit incorrect: {loaded_packet['hop_limit']}"
        assert loaded_packet['hop_start'] == 3, f"hop_start incorrect: {loaded_packet['hop_start']}"
        assert loaded_packet['hops'] == 2, f"hops incorrect: {loaded_packet['hops']}"
        
        print(f"✅ Paquet chargé correctement:")
        print(f"   hop_limit: {loaded_packet['hop_limit']}")
        print(f"   hop_start: {loaded_packet['hop_start']}")
        print(f"   hops: {loaded_packet['hops']}")
        
        persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_traffic_monitor_integration():
    """Test que TrafficMonitor inclut hop_limit et hop_start dans packet_entry."""
    print("\n=== Test 4: Intégration TrafficMonitor ===")
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Créer un NodeManager temporaire
        node_manager = NodeManager()
        
        # Créer TrafficMonitor avec une base temporaire
        original_db_path = None
        if hasattr(TrafficMonitor, 'persistence'):
            original_db_path = TrafficMonitor.persistence.db_path
        
        traffic_monitor = TrafficMonitor(node_manager)
        # Remplacer la persistence avec notre DB temporaire
        traffic_monitor.persistence = TrafficPersistence(db_path=db_path)
        
        # Créer un paquet Meshtastic simulé
        test_packet = {
            'id': 123456789,
            'from': 305419896,  # 0x12345678
            'to': 2271560481,   # 0x87654321
            'hopLimit': 1,
            'hopStart': 3,
            'rxRssi': -100,
            'rxSnr': 5.5,
            'decoded': {
                'portnum': 'TEXT_MESSAGE_APP',
                'payload': b'Test message'
            }
        }
        
        # Ajouter le paquet
        traffic_monitor.add_packet(test_packet, source='serial')
        print("Paquet ajouté via TrafficMonitor")
        
        # Vérifier que le paquet a été sauvegardé avec hop_limit et hop_start
        packets = traffic_monitor.persistence.load_packets(hours=1)
        
        assert len(packets) >= 1, f"Attendu au moins 1 paquet, reçu {len(packets)}"
        
        # Trouver notre paquet
        loaded_packet = None
        for p in packets:
            if p['from_id'] == '305419896':
                loaded_packet = p
                break
        
        assert loaded_packet is not None, "Paquet test non trouvé"
        assert 'hop_limit' in loaded_packet, "hop_limit manquant"
        assert 'hop_start' in loaded_packet, "hop_start manquant"
        assert loaded_packet['hop_limit'] == 1, f"hop_limit incorrect: {loaded_packet['hop_limit']}"
        assert loaded_packet['hop_start'] == 3, f"hop_start incorrect: {loaded_packet['hop_start']}"
        
        print(f"✅ TrafficMonitor sauvegarde correctement:")
        print(f"   hop_limit: {loaded_packet['hop_limit']}")
        print(f"   hop_start: {loaded_packet['hop_start']}")
        print(f"   hops: {loaded_packet['hops']}")
        
        traffic_monitor.persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_null_hop_values():
    """Test que les paquets sans hop_limit/hop_start sont gérés correctement."""
    print("\n=== Test 5: Gestion valeurs hop manquantes ===")
    
    # Créer une base temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        db_path = tmp_file.name
    
    try:
        persistence = TrafficPersistence(db_path=db_path)
        
        # Paquet sans hop_limit/hop_start
        test_packet = {
            'timestamp': time.time(),
            'from_id': '!12345678',
            'to_id': '!87654321',
            'source': 'serial',
            'sender_name': 'TestNode',
            'packet_type': 'TEXT_MESSAGE_APP',
            'message': 'Test message',
            'rssi': -100,
            'snr': 5.5,
            'hops': 0,
            'size': 50,
            'is_broadcast': False,
            'is_encrypted': False
            # hop_limit et hop_start absents
        }
        
        # Sauvegarder le paquet (ne devrait pas planter)
        persistence.save_packet(test_packet)
        print("Paquet sans hop_limit/hop_start sauvegardé")
        
        # Charger le paquet
        packets = persistence.load_packets(hours=1)
        assert len(packets) == 1, f"Attendu 1 paquet, reçu {len(packets)}"
        
        loaded_packet = packets[0]
        
        # Les valeurs peuvent être None ou 0
        print(f"   hop_limit: {loaded_packet.get('hop_limit')} (None est OK)")
        print(f"   hop_start: {loaded_packet.get('hop_start')} (None est OK)")
        print("✅ Paquets sans valeurs hop gérés correctement")
        
        persistence.close()
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == '__main__':
    print("=== Tests hop_limit et hop_start ===\n")
    
    try:
        test_hop_limit_hop_start_columns_exist()
        test_migration_existing_database()
        test_save_and_load_hop_data()
        test_traffic_monitor_integration()
        test_null_hop_values()
        
        print("\n" + "="*70)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
