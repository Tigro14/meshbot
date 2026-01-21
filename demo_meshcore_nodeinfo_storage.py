#!/usr/bin/env python3
"""
Démonstration du stockage NODEINFO pour MeshCore
Montre comment les contacts MeshCore sont sauvegardés et récupérés
"""

import sys
import os
import tempfile

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock des imports Meshtastic
from unittest.mock import MagicMock
sys.modules['meshtastic'] = MagicMock()
sys.modules['meshtastic.serial_interface'] = MagicMock()
sys.modules['meshtastic.tcp_interface'] = MagicMock()
sys.modules['meshtastic.protobuf'] = MagicMock()
sys.modules['meshtastic.protobuf.portnums_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.telemetry_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.admin_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.mesh_pb2'] = MagicMock()

# Mock du module config
mock_config = MagicMock()
mock_config.CONNECTION_MODE = 'meshcore'
mock_config.MESHCORE_ENABLED = True
mock_config.DEBUG_MODE = False
mock_config.NODE_NAMES_FILE = '/tmp/demo_node_names.json'
mock_config.COLLECT_SIGNAL_METRICS = True
sys.modules['config'] = mock_config

from traffic_persistence import TrafficPersistence
from remote_nodes_client import RemoteNodesClient

def demo_meshcore_nodeinfo_storage():
    """
    Démonstration du système de stockage NODEINFO pour MeshCore
    """
    print("="*70)
    print("DÉMONSTRATION: Stockage NODEINFO pour MeshCore dans SQLite")
    print("="*70)
    print()
    
    # Créer une base de données temporaire
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    try:
        # 1. Créer une instance de TrafficPersistence
        print("1️⃣  Création de la base de données SQLite...")
        persistence = TrafficPersistence(db_path=db_path)
        print(f"   ✅ Base créée: {db_path}")
        print()
        
        # 2. Simuler la sauvegarde de contacts MeshCore (comme fait par meshcore_cli_wrapper)
        print("2️⃣  Simulation de la synchronisation des contacts MeshCore...")
        sample_contacts = [
            {
                'node_id': 0x12345678,
                'name': 'Node-Alpha',
                'shortName': 'ALPH',
                'hwModel': 'T-Beam',
                'publicKey': b'\x01\x02\x03\x04' * 8,
                'lat': 48.8566,
                'lon': 2.3522,
                'alt': 35,
                'source': 'meshcore'
            },
            {
                'node_id': 0x87654321,
                'name': 'Node-Bravo',
                'shortName': 'BRVO',
                'hwModel': 'Heltec V3',
                'publicKey': b'\x05\x06\x07\x08' * 8,
                'lat': 48.8606,
                'lon': 2.3376,
                'alt': 45,
                'source': 'meshcore'
            },
            {
                'node_id': 0xABCDEF00,
                'name': 'Node-Charlie',
                'shortName': 'CHRL',
                'hwModel': 'RAK WisBlock',
                'publicKey': None,
                'lat': None,
                'lon': None,
                'alt': None,
                'source': 'meshcore'
            }
        ]
        
        for contact in sample_contacts:
            persistence.save_meshcore_contact(contact)
            print(f"   💾 Sauvegardé: {contact['name']} (0x{contact['node_id']:08x})")
        
        print(f"   ✅ {len(sample_contacts)} contacts sauvegardés")
        print()
        
        # 3. Créer un RemoteNodesClient et récupérer les contacts
        print("3️⃣  Récupération des contacts depuis la base de données...")
        client = RemoteNodesClient(persistence=persistence)
        
        retrieved_contacts = client.get_meshcore_contacts_from_db(days_filter=30)
        print(f"   ✅ {len(retrieved_contacts)} contacts récupérés")
        print()
        
        # 4. Afficher les détails des contacts
        print("4️⃣  Détails des contacts récupérés:")
        for i, contact in enumerate(retrieved_contacts, 1):
            print(f"\n   Contact {i}:")
            print(f"      • ID:        0x{contact['id']:08x}")
            print(f"      • Nom:       {contact['name']}")
            print(f"      • ShortName: {contact['shortName']}")
            print(f"      • Hardware:  {contact['hwModel']}")
            if contact['latitude']:
                print(f"      • Position:  {contact['latitude']:.4f}, {contact['longitude']:.4f}")
            else:
                print(f"      • Position:  Non disponible")
        print()
        
        # 5. Démontrer l'affichage paginé (comme dans /nodes)
        print("5️⃣  Affichage paginé (simulant la commande /nodes):")
        print("-" * 70)
        paginated_output = client.get_meshcore_paginated(page=1, days_filter=30)
        print(paginated_output)
        print("-" * 70)
        print()
        
        # 6. Tester la mise à jour d'un contact
        print("6️⃣  Test de mise à jour d'un contact existant...")
        updated_contact = {
            'node_id': 0x12345678,
            'name': 'Node-Alpha-Updated',
            'shortName': 'ALPH2',
            'hwModel': 'T-Beam v1.1',
            'publicKey': b'\x01\x02\x03\x04' * 8,
            'lat': 48.8570,  # Position mise à jour
            'lon': 2.3530,
            'alt': 40,
            'source': 'meshcore'
        }
        persistence.save_meshcore_contact(updated_contact)
        print(f"   ✅ Contact mis à jour: {updated_contact['name']}")
        
        # Vérifier qu'il n'y a pas de doublon
        cursor = persistence.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM meshcore_contacts WHERE node_id = ?',
                      (str(0x12345678),))
        count = cursor.fetchone()['count']
        print(f"   ✅ Vérification: {count} enregistrement(s) pour ce node_id (pas de doublon)")
        print()
        
        # 7. Résumé
        print("="*70)
        print("✅ DÉMONSTRATION TERMINÉE AVEC SUCCÈS")
        print("="*70)
        print()
        print("Ce système permet:")
        print("  • Sauvegarde automatique des contacts MeshCore après sync_contacts()")
        print("  • Récupération des contacts depuis SQLite pour la commande /nodes")
        print("  • Affichage paginé compatible avec le format Meshtastic")
        print("  • Mise à jour sans doublon (UPSERT)")
        print("  • Séparation des données MeshCore et Meshtastic")
        print()
        
    finally:
        # Nettoyer
        os.close(db_fd)
        if os.path.exists(db_path):
            os.unlink(db_path)

if __name__ == '__main__':
    demo_meshcore_nodeinfo_storage()
