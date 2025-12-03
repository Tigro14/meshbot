#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour la commande /mqtt Telegram
Vérifie la logique de get_directly_heard_nodes
"""

import sys
import time
from collections import defaultdict


class MockNodeManager:
    """Mock du NodeManager pour les tests"""
    
    def __init__(self):
        self.nodes = {
            0x12345678: "TigroBot",
            0x87654321: "RemoteNode",
            0xabcdef01: "MeshGateway",
            0x16fad3dc: "TestNode"
        }
    
    def get_node_name(self, node_id):
        """Retourner le nom du nœud ou l'ID si inconnu"""
        if isinstance(node_id, str):
            if node_id.startswith('!'):
                node_id = int(node_id[1:], 16)
        
        return self.nodes.get(node_id, f"!{node_id:08x}")


class MockPersistence:
    """Mock de TrafficPersistence pour les tests"""
    
    def __init__(self):
        # Simuler des données de voisinage
        # Format: {node_id: [liste de voisins avec timestamp]}
        current_time = time.time()
        
        self.neighbors_data = {
            "!12345678": [  # TigroBot
                {"node_id": "!87654321", "snr": 10.5, "timestamp": current_time - 300},  # 5 min ago
                {"node_id": "!abcdef01", "snr": 8.2, "timestamp": current_time - 300}
            ],
            "!87654321": [  # RemoteNode
                {"node_id": "!12345678", "snr": 9.8, "timestamp": current_time - 3600},  # 1h ago
                {"node_id": "!16fad3dc", "snr": 7.5, "timestamp": current_time - 3600}
            ],
            "!abcdef01": [  # MeshGateway
                {"node_id": "!12345678", "snr": 8.0, "timestamp": current_time - 86400}  # 24h ago
            ],
            "!16fad3dc": [  # TestNode - 30h ago (safely within 48h window)
                {"node_id": "!87654321", "snr": 6.5, "timestamp": current_time - 108000}
            ]
        }
    
    def load_neighbors(self, hours=48):
        """Simuler le chargement des voisins"""
        cutoff = time.time() - (hours * 3600)
        
        # Filtrer par timestamp
        filtered = {}
        for node_id, neighbors in self.neighbors_data.items():
            valid_neighbors = [n for n in neighbors if n['timestamp'] >= cutoff]
            if valid_neighbors:
                filtered[node_id] = valid_neighbors
        
        return filtered


class MockMQTTCollector:
    """Mock minimal du MQTTNeighborCollector pour tester get_directly_heard_nodes"""
    
    def __init__(self, persistence, node_manager):
        self.persistence = persistence
        self.node_manager = node_manager
        self.enabled = True
        self.connected = True
    
    def get_directly_heard_nodes(self, hours=48):
        """
        Version de test de get_directly_heard_nodes
        (copie de la méthode réelle)
        """
        if not self.persistence:
            return []
        
        try:
            # Récupérer les données de voisinage depuis la persistance
            neighbors_data = self.persistence.load_neighbors(hours=hours)
            
            if not neighbors_data:
                return []
            
            # Créer un dictionnaire pour suivre le last_heard de chaque nœud
            nodes_heard = {}
            
            for node_id, neighbors_list in neighbors_data.items():
                # Le node_id est celui qui a envoyé le NEIGHBORINFO
                # Trouver le timestamp le plus récent parmi ses voisins
                if neighbors_list:
                    latest_timestamp = max(n.get('timestamp', 0) for n in neighbors_list)
                    
                    # Mettre à jour ou ajouter le nœud
                    if node_id not in nodes_heard or latest_timestamp > nodes_heard[node_id]:
                        nodes_heard[node_id] = latest_timestamp
            
            # Convertir en liste avec longname
            result = []
            for node_id, last_heard in nodes_heard.items():
                # Obtenir le nom du nœud via node_manager
                longname = node_id  # Par défaut, utiliser l'ID
                if self.node_manager:
                    try:
                        # Convertir !xxxxxxxx en int pour get_node_name
                        if node_id.startswith('!'):
                            node_id_int = int(node_id[1:], 16)
                            longname = self.node_manager.get_node_name(node_id_int)
                        else:
                            longname = self.node_manager.get_node_name(node_id)
                    except Exception as e:
                        print(f"Erreur récupération nom pour {node_id}: {e}")
                
                result.append({
                    'node_id': node_id,
                    'longname': longname,
                    'last_heard': last_heard
                })
            
            # Trier par last_heard (plus récent d'abord)
            result.sort(key=lambda x: x['last_heard'], reverse=True)
            
            return result
            
        except Exception as e:
            print(f"Erreur récupération nœuds MQTT: {e}")
            return []


def test_get_directly_heard_nodes():
    """Test de la méthode get_directly_heard_nodes"""
    
    print("=== Test get_directly_heard_nodes ===\n")
    
    # Créer les mocks
    persistence = MockPersistence()
    node_manager = MockNodeManager()
    collector = MockMQTTCollector(persistence, node_manager)
    
    # Test 1: Récupérer tous les nœuds (48h)
    print("Test 1: Tous les nœuds (48h)")
    nodes = collector.get_directly_heard_nodes(hours=48)
    
    print(f"Nombre de nœuds trouvés: {len(nodes)}")
    assert len(nodes) == 4, f"Expected 4 nodes, got {len(nodes)}"
    
    for i, node in enumerate(nodes, 1):
        elapsed = time.time() - node['last_heard']
        if elapsed < 3600:
            time_str = f"{int(elapsed // 60)}m"
        elif elapsed < 86400:
            time_str = f"{int(elapsed // 3600)}h"
        else:
            time_str = f"{int(elapsed // 86400)}j"
        
        print(f"{i}. {node['longname']} ({node['node_id'][-4:]}) - {time_str} ago")
    
    # Vérifier que le tri est correct (plus récent d'abord)
    assert nodes[0]['longname'] == 'TigroBot', f"Expected TigroBot first, got {nodes[0]['longname']}"
    
    print("\n✅ Test 1 réussi\n")
    
    # Test 2: Filtrer sur 24h (devrait exclure MeshGateway et TestNode)
    print("Test 2: Nœuds récents (24h)")
    nodes = collector.get_directly_heard_nodes(hours=24)
    
    print(f"Nombre de nœuds trouvés: {len(nodes)}")
    # Only TigroBot (5m) and RemoteNode (1h) are within 24h
    assert len(nodes) == 2, f"Expected 2 nodes (within 24h), got {len(nodes)}"
    
    for i, node in enumerate(nodes, 1):
        elapsed = time.time() - node['last_heard']
        if elapsed < 3600:
            time_str = f"{int(elapsed // 60)}m"
        elif elapsed < 86400:
            time_str = f"{int(elapsed // 3600)}h"
        else:
            time_str = f"{int(elapsed // 86400)}j"
        
        print(f"{i}. {node['longname']} ({node['node_id'][-4:]}) - {time_str} ago")
    
    print("\n✅ Test 2 réussi\n")
    
    # Test 3: Filtrer sur 1h (devrait ne garder que TigroBot)
    print("Test 3: Nœuds très récents (1h)")
    nodes = collector.get_directly_heard_nodes(hours=1)
    
    print(f"Nombre de nœuds trouvés: {len(nodes)}")
    assert len(nodes) == 1, f"Expected 1 node (only TigroBot), got {len(nodes)}"
    assert nodes[0]['longname'] == 'TigroBot', f"Expected TigroBot, got {nodes[0]['longname']}"
    
    for i, node in enumerate(nodes, 1):
        elapsed = time.time() - node['last_heard']
        time_str = f"{int(elapsed // 60)}m"
        print(f"{i}. {node['longname']} ({node['node_id'][-4:]}) - {time_str} ago")
    
    print("\n✅ Test 3 réussi\n")
    
    # Test 4: Vérifier les noms de nœuds
    print("Test 4: Vérification des noms")
    nodes = collector.get_directly_heard_nodes(hours=48)
    
    expected_names = {'TigroBot', 'RemoteNode', 'MeshGateway', 'TestNode'}
    actual_names = {node['longname'] for node in nodes}
    
    assert actual_names == expected_names, f"Expected {expected_names}, got {actual_names}"
    print(f"Noms trouvés: {', '.join(sorted(actual_names))}")
    
    print("\n✅ Test 4 réussi\n")
    
    print("=== Tous les tests réussis! ===")


if __name__ == "__main__":
    test_get_directly_heard_nodes()
