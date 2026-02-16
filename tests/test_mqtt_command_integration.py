#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test d'intégration pour la commande /mqtt
Simule un scénario réaliste avec formatage du message Telegram
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import time


class MockNodeManager:
    """Mock du NodeManager avec des nœuds réalistes"""
    
    def __init__(self):
        self.nodes = {
            0x12345678: "tigrobot",
            0x87654321: "tigrog2",
            0xabcdef01: "Paris-Gateway",
            0x16fad3dc: "Lyon-Mesh-001",
            0xdeadbeef: "Unknown-Node"
        }
    
    def get_node_name(self, node_id):
        """Retourner le nom du nœud ou l'ID si inconnu"""
        if isinstance(node_id, str):
            if node_id.startswith('!'):
                node_id = int(node_id[1:], 16)
        
        return self.nodes.get(node_id, f"!{node_id:08x}")


class MockPersistence:
    """Mock de TrafficPersistence avec données réalistes"""
    
    def __init__(self):
        current_time = time.time()
        
        # Simuler 5 nœuds avec différents timestamps
        self.neighbors_data = {
            "!12345678": [  # tigrobot - très récent (2 min)
                {"node_id": "!87654321", "snr": 10.5, "timestamp": current_time - 120}
            ],
            "!87654321": [  # tigrog2 - récent (30 min)
                {"node_id": "!12345678", "snr": 9.8, "timestamp": current_time - 1800}
            ],
            "!abcdef01": [  # Paris-Gateway - moyen (5h)
                {"node_id": "!12345678", "snr": 8.0, "timestamp": current_time - 18000}
            ],
            "!16fad3dc": [  # Lyon-Mesh-001 - ancien (1.5j)
                {"node_id": "!87654321", "snr": 6.5, "timestamp": current_time - 129600}
            ],
            "!deadbeef": [  # Unknown-Node - inconnu (10h)
                {"node_id": "!12345678", "snr": 5.0, "timestamp": current_time - 36000}
            ]
        }
    
    def load_neighbors(self, hours=48):
        """Simuler le chargement des voisins"""
        cutoff = time.time() - (hours * 3600)
        
        filtered = {}
        for node_id, neighbors in self.neighbors_data.items():
            valid_neighbors = [n for n in neighbors if n['timestamp'] >= cutoff]
            if valid_neighbors:
                filtered[node_id] = valid_neighbors
        
        return filtered


def format_mqtt_response(nodes, mqtt_connected=True, hours=48):
    """
    Formater la réponse comme le ferait la vraie commande /mqtt
    (copie de la logique de mqtt_command - SANS MARKDOWN)
    """
    if not nodes:
        return f"ℹ️ Aucun nœud MQTT entendu dans les {hours} dernières heures.\n\nLe collecteur MQTT est actif mais n'a pas encore reçu de paquets NEIGHBORINFO."
    
    # Formater la réponse
    lines = [
        f"📡 Nœuds MQTT entendus directement ({len(nodes)} nœuds, {hours}h)\n"
    ]
    
    # Statut de connexion
    status = "Connecté 🟢" if mqtt_connected else "Déconnecté 🔴"
    lines.append(f"Statut MQTT: {status}\n")
    
    # Liste des nœuds
    for i, node in enumerate(nodes, 1):
        node_id = node['node_id']
        longname = node['longname']
        last_heard = node['last_heard']
        
        # Calculer le temps écoulé depuis la dernière écoute
        elapsed = int(time.time() - last_heard) if last_heard > 0 else 0
        if elapsed < 60:
            time_str = f"{elapsed}s"
        elif elapsed < 3600:
            time_str = f"{elapsed // 60}m"
        elif elapsed < 86400:
            time_str = f"{elapsed // 3600}h"
        else:
            time_str = f"{elapsed // 86400}j"
        
        # Icône basée sur le temps écoulé
        if elapsed < 3600:  # < 1h
            icon = "🟢"
        elif elapsed < 86400:  # < 24h
            icon = "🟡"
        else:
            icon = "🟠"
        
        # Formatter: numéro, icône, nom, ID court, temps
        short_id = node_id[-4:] if node_id.startswith('!') else node_id
        
        lines.append(f"{i}. {icon} {longname} ({short_id}) - {time_str}")
    
    return "\n".join(lines)


def test_mqtt_command_formatting():
    """Test du formatage complet comme dans Telegram"""
    
    print("=== Test de formatage de la commande /mqtt ===\n")
    
    # Créer les mocks
    persistence = MockPersistence()
    node_manager = MockNodeManager()
    
    # Simuler le collecteur MQTT avec les mocks
    class SimpleMQTTCollector:
        def __init__(self, persistence, node_manager):
            self.persistence = persistence
            self.node_manager = node_manager
            self.enabled = True
            self.connected = True
        
        def get_directly_heard_nodes(self, hours=48):
            """Version simplifiée de get_directly_heard_nodes"""
            neighbors_data = self.persistence.load_neighbors(hours=hours)
            
            if not neighbors_data:
                return []
            
            nodes_heard = {}
            for node_id, neighbors_list in neighbors_data.items():
                if neighbors_list:
                    latest_timestamp = max(n.get('timestamp', 0) for n in neighbors_list)
                    if node_id not in nodes_heard or latest_timestamp > nodes_heard[node_id]:
                        nodes_heard[node_id] = latest_timestamp
            
            result = []
            for node_id, last_heard in nodes_heard.items():
                longname = node_id
                if self.node_manager:
                    try:
                        if node_id.startswith('!'):
                            node_id_int = int(node_id[1:], 16)
                            longname = self.node_manager.get_node_name(node_id_int)
                        else:
                            longname = self.node_manager.get_node_name(node_id)
                    except Exception as e:
                        pass
                
                result.append({
                    'node_id': node_id,
                    'longname': longname,
                    'last_heard': last_heard
                })
            
            result.sort(key=lambda x: x['last_heard'], reverse=True)
            return result
    
    collector = SimpleMQTTCollector(persistence, node_manager)
    
    print("Test 1: Formatage standard (48h, tous les nœuds)")
    print("-" * 60)
    
    nodes = collector.get_directly_heard_nodes(hours=48)
    response = format_mqtt_response(nodes, mqtt_connected=True, hours=48)
    
    print(response)
    print()
    
    # Vérifications
    assert "📡" in response, "Missing emoji"
    assert "5 nœuds" in response, "Wrong node count"
    assert "Connecté 🟢" in response, "Missing connection status"
    assert "tigrobot" in response, "Missing tigrobot"
    assert "🟢" in response, "Missing green icon (recent)"
    assert "🟠" in response, "Missing orange icon (old)"
    
    print("✅ Test 1 réussi\n")
    
    print("Test 2: Filtrage sur 24h (nœuds récents seulement)")
    print("-" * 60)
    
    nodes = collector.get_directly_heard_nodes(hours=24)
    response = format_mqtt_response(nodes, mqtt_connected=True, hours=24)
    
    print(response)
    print()
    
    # Vérifications
    assert "4 nœuds" in response, "Wrong filtered node count"
    assert "Lyon-Mesh-001" not in response, "Should exclude old node"
    
    print("✅ Test 2 réussi\n")
    
    print("Test 3: Déconnecté MQTT")
    print("-" * 60)
    
    response = format_mqtt_response(nodes, mqtt_connected=False, hours=24)
    
    print(response)
    print()
    
    # Vérifications
    assert "Déconnecté 🔴" in response, "Missing disconnected status"
    
    print("✅ Test 3 réussi\n")
    
    print("Test 4: Aucun nœud (liste vide)")
    print("-" * 60)
    
    response = format_mqtt_response([], mqtt_connected=True, hours=1)
    
    print(response)
    print()
    
    # Vérifications
    assert "Aucun nœud MQTT entendu" in response, "Missing empty message"
    assert "1 dernières heures" in response, "Wrong hours in message"
    
    print("✅ Test 4 réussi\n")
    
    print("=== Tous les tests de formatage réussis! ===")
    print("\nExemple de sortie Telegram finale:")
    print("=" * 60)
    nodes = collector.get_directly_heard_nodes(hours=48)
    response = format_mqtt_response(nodes, mqtt_connected=True, hours=48)
    print(response)


if __name__ == "__main__":
    test_mqtt_command_formatting()
