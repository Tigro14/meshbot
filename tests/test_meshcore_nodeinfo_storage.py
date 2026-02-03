#!/usr/bin/env python3
"""
Test du stockage des contacts MeshCore dans SQLite (NODEINFO équivalent)
Vérifie que les contacts sont sauvegardés et récupérés correctement
"""

import sys
import os
import unittest
import tempfile
import sqlite3
from unittest.mock import Mock, MagicMock, patch

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestMeshCoreNodeInfoStorage(unittest.TestCase):
    """Tests pour le stockage des contacts MeshCore (NODEINFO)"""
    
    def setUp(self):
        """Préparer l'environnement de test"""
        # Mock des imports Meshtastic pour éviter les dépendances
        self.meshtastic_mock = MagicMock()
        sys.modules['meshtastic'] = self.meshtastic_mock
        sys.modules['meshtastic.serial_interface'] = MagicMock()
        sys.modules['meshtastic.tcp_interface'] = MagicMock()
        sys.modules['meshtastic.protobuf'] = MagicMock()
        sys.modules['meshtastic.protobuf.portnums_pb2'] = MagicMock()
        sys.modules['meshtastic.protobuf.telemetry_pb2'] = MagicMock()
        sys.modules['meshtastic.protobuf.admin_pb2'] = MagicMock()
        sys.modules['meshtastic.protobuf.mesh_pb2'] = MagicMock()
        
        # Créer une base de données temporaire
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        
    def tearDown(self):
        """Nettoyer après le test"""
        # Fermer et supprimer la base de données temporaire
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_save_meshcore_contact(self):
        """Test de sauvegarde d'un contact MeshCore"""
        from traffic_persistence import TrafficPersistence
        
        # Créer une instance de TrafficPersistence avec la DB temporaire
        persistence = TrafficPersistence(db_path=self.db_path)
        
        # Données de test
        contact_data = {
            'node_id': 0x12345678,
            'name': 'TestNode',
            'shortName': 'TEST',
            'hwModel': 'T-Beam',
            'publicKey': b'\x01\x02\x03\x04' * 8,  # 32 bytes
            'lat': 48.8566,
            'lon': 2.3522,
            'alt': 35,
            'source': 'meshcore'
        }
        
        # Sauvegarder le contact
        persistence.save_meshcore_contact(contact_data)
        
        # Vérifier que le contact est dans la base
        cursor = persistence.conn.cursor()
        cursor.execute('SELECT * FROM meshcore_contacts WHERE node_id = ?', 
                      (str(contact_data['node_id']),))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row, "Contact should be saved in database")
        self.assertEqual(row['name'], 'TestNode')
        self.assertEqual(row['shortName'], 'TEST')
        self.assertEqual(row['hwModel'], 'T-Beam')
        self.assertEqual(row['lat'], 48.8566)
        self.assertEqual(row['lon'], 2.3522)
        self.assertEqual(row['alt'], 35)
        self.assertEqual(row['source'], 'meshcore')
        
        print("✅ test_save_meshcore_contact passed")
    
    def test_get_meshcore_contacts_from_db(self):
        """Test de récupération des contacts MeshCore depuis la DB"""
        from traffic_persistence import TrafficPersistence
        from remote_nodes_client import RemoteNodesClient
        
        # Créer une instance de TrafficPersistence
        persistence = TrafficPersistence(db_path=self.db_path)
        
        # Sauvegarder plusieurs contacts
        contacts = [
            {
                'node_id': 0x12345678,
                'name': 'Node1',
                'shortName': 'N1',
                'hwModel': 'T-Beam',
                'publicKey': None,
                'lat': 48.8566,
                'lon': 2.3522,
                'alt': 35,
                'source': 'meshcore'
            },
            {
                'node_id': 0x87654321,
                'name': 'Node2',
                'shortName': 'N2',
                'hwModel': 'Heltec',
                'publicKey': None,
                'lat': 48.8606,
                'lon': 2.3376,
                'alt': 45,
                'source': 'meshcore'
            }
        ]
        
        for contact in contacts:
            persistence.save_meshcore_contact(contact)
        
        # Créer un RemoteNodesClient avec persistence
        client = RemoteNodesClient(persistence=persistence)
        
        # Récupérer les contacts
        retrieved_contacts = client.get_meshcore_contacts_from_db(days_filter=30)
        
        self.assertEqual(len(retrieved_contacts), 2, "Should retrieve 2 contacts")
        
        # Vérifier les données
        ids = [c['id'] for c in retrieved_contacts]
        self.assertIn(0x12345678, ids)
        self.assertIn(0x87654321, ids)
        
        print("✅ test_get_meshcore_contacts_from_db passed")
    
    def test_meshcore_paginated_display(self):
        """Test de l'affichage paginé des contacts MeshCore"""
        from traffic_persistence import TrafficPersistence
        from remote_nodes_client import RemoteNodesClient
        
        # Créer une instance de TrafficPersistence
        persistence = TrafficPersistence(db_path=self.db_path)
        
        # Sauvegarder plusieurs contacts (10 pour tester pagination)
        for i in range(10):
            contact = {
                'node_id': 0x10000000 + i,
                'name': f'Node{i}',
                'shortName': f'N{i}',
                'hwModel': 'T-Beam',
                'publicKey': None,
                'lat': 48.8566 + i * 0.01,
                'lon': 2.3522 + i * 0.01,
                'alt': 35 + i,
                'source': 'meshcore'
            }
            persistence.save_meshcore_contact(contact)
        
        # Créer un RemoteNodesClient avec persistence
        client = RemoteNodesClient(persistence=persistence)
        
        # Récupérer la première page
        result_page1 = client.get_meshcore_paginated(page=1, days_filter=30)
        
        self.assertIsInstance(result_page1, str, "Should return a formatted string")
        self.assertIn("Contacts MeshCore", result_page1, "Should have header")
        self.assertIn("(10)", result_page1, "Should show total count")
        
        # Vérifier qu'il y a une indication de pagination
        self.assertIn("1/2", result_page1, "Should show page numbers")
        
        print("✅ test_meshcore_paginated_display passed")
    
    def test_nodes_command_meshcore_mode(self):
        """Test de la commande /nodes en mode MeshCore"""
        from traffic_persistence import TrafficPersistence
        from remote_nodes_client import RemoteNodesClient
        from handlers.command_handlers.network_commands import NetworkCommands
        from handlers.message_sender import MessageSender
        from node_manager import NodeManager
        
        # Créer les dépendances
        persistence = TrafficPersistence(db_path=self.db_path)
        node_manager = NodeManager()
        
        # Mock de l'interface
        mock_interface = MagicMock()
        mock_interface.nodes = {}
        
        # Créer un RemoteNodesClient avec persistence
        remote_nodes_client = RemoteNodesClient(persistence=persistence)
        remote_nodes_client.set_node_manager(node_manager)
        
        # Créer un MessageSender mock
        mock_sender = MagicMock(spec=MessageSender)
        mock_sender.check_throttling = MagicMock(return_value=True)
        mock_sender.send_single = MagicMock()
        mock_sender.log_conversation = MagicMock()
        
        # Sauvegarder des contacts
        for i in range(3):
            contact = {
                'node_id': 0x20000000 + i,
                'name': f'TestNode{i}',
                'shortName': f'TN{i}',
                'hwModel': 'T-Beam',
                'publicKey': None,
                'lat': None,
                'lon': None,
                'alt': None,
                'source': 'meshcore'
            }
            persistence.save_meshcore_contact(contact)
        
        # Créer NetworkCommands
        network_commands = NetworkCommands(
            remote_nodes_client=remote_nodes_client,
            sender=mock_sender,
            node_manager=node_manager,
            interface=mock_interface
        )
        
        # Mock du config pour mode MeshCore
        import config
        with patch.object(config, 'CONNECTION_MODE', 'meshcore'):
            with patch.object(config, 'MESHCORE_ENABLED', True):
                # Exécuter la commande /nodes
                network_commands.handle_nodes('/nodes', 0x12345678, {'name': 'Sender'})
        
        # Vérifier que send_single a été appelé
        mock_sender.send_single.assert_called_once()
        
        # Récupérer l'argument passé à send_single
        call_args = mock_sender.send_single.call_args
        response_text = call_args[0][0]
        
        # Vérifier que la réponse contient "Contacts MeshCore"
        self.assertIn("Contacts MeshCore", response_text, 
                     "Response should indicate MeshCore mode")
        
        print("✅ test_nodes_command_meshcore_mode passed")
    
    def test_contact_update(self):
        """Test de mise à jour d'un contact existant"""
        from traffic_persistence import TrafficPersistence
        
        persistence = TrafficPersistence(db_path=self.db_path)
        
        # Sauvegarder un contact initial
        contact_v1 = {
            'node_id': 0x12345678,
            'name': 'OldName',
            'shortName': 'OLD',
            'hwModel': 'T-Beam',
            'publicKey': None,
            'lat': None,
            'lon': None,
            'alt': None,
            'source': 'meshcore'
        }
        persistence.save_meshcore_contact(contact_v1)
        
        # Mettre à jour le contact avec de nouvelles données
        contact_v2 = {
            'node_id': 0x12345678,
            'name': 'NewName',
            'shortName': 'NEW',
            'hwModel': 'T-Beam v1.1',
            'publicKey': None,
            'lat': 48.8566,
            'lon': 2.3522,
            'alt': 35,
            'source': 'meshcore'
        }
        persistence.save_meshcore_contact(contact_v2)
        
        # Vérifier que le contact a été mis à jour (pas dupliqué)
        cursor = persistence.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM meshcore_contacts WHERE node_id = ?',
                      (str(0x12345678),))
        count = cursor.fetchone()['count']
        
        self.assertEqual(count, 1, "Should have only one record (updated, not duplicated)")
        
        # Vérifier les nouvelles valeurs
        cursor.execute('SELECT * FROM meshcore_contacts WHERE node_id = ?',
                      (str(0x12345678),))
        row = cursor.fetchone()
        
        self.assertEqual(row['name'], 'NewName')
        self.assertEqual(row['shortName'], 'NEW')
        self.assertEqual(row['lat'], 48.8566)
        
        print("✅ test_contact_update passed")

if __name__ == '__main__':
    # Configurer les mocks avant d'importer les modules
    import sys
    from unittest.mock import MagicMock
    
    # Mock du module config
    mock_config = MagicMock()
    mock_config.CONNECTION_MODE = 'meshcore'
    mock_config.MESHCORE_ENABLED = True
    mock_config.DEBUG_MODE = False
    mock_config.NODE_NAMES_FILE = '/tmp/test_node_names.json'
    sys.modules['config'] = mock_config
    
    # Exécuter les tests
    unittest.main()
