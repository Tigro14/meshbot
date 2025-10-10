#!/usr/bin/env python3
"""
Script d'export des informations de voisinage Meshtastic
Version corrigée avec gestion des neighborinfo et sérialisation JSON
"""

import json
import time
import meshtastic.tcp_interface
from datetime import datetime

def serialize_node_data(node_id, node_info):
    """
    Convertir un nœud Meshtastic en dictionnaire sérialisable
    """
    try:
        node_data = {
            'node_id': f"!{node_id:08x}" if isinstance(node_id, int) else str(node_id),
            'timestamp': datetime.now().isoformat()
        }
        
        # Informations utilisateur
        if hasattr(node_info, 'user'):
            user = node_info.user
            node_data['user'] = {
                'longName': getattr(user, 'longName', ''),
                'shortName': getattr(user, 'shortName', ''),
                'macaddr': getattr(user, 'macaddr', '').hex() if hasattr(user, 'macaddr') else '',
                'hwModel': getattr(user, 'hwModel', 0)
            }
        elif isinstance(node_info, dict) and 'user' in node_info:
            user = node_info['user']
            if isinstance(user, dict):
                node_data['user'] = user
            else:
                node_data['user'] = {
                    'longName': getattr(user, 'longName', ''),
                    'shortName': getattr(user, 'shortName', ''),
                }
        
        # Position
        if hasattr(node_info, 'position'):
            pos = node_info.position
            node_data['position'] = {
                'latitude': getattr(pos, 'latitude', 0) / 1e7 if hasattr(pos, 'latitude') else 0,
                'longitude': getattr(pos, 'longitude', 0) / 1e7 if hasattr(pos, 'longitude') else 0,
                'altitude': getattr(pos, 'altitude', 0)
            }
        elif isinstance(node_info, dict) and 'position' in node_info:
            pos = node_info['position']
            if isinstance(pos, dict):
                node_data['position'] = pos
        
        # Métriques
        node_data['metrics'] = {
            'snr': getattr(node_info, 'snr', 0) if hasattr(node_info, 'snr') else node_info.get('snr', 0),
            'rssi': getattr(node_info, 'rssi', 0) if hasattr(node_info, 'rssi') else node_info.get('rssi', 0),
            'lastHeard': getattr(node_info, 'lastHeard', 0) if hasattr(node_info, 'lastHeard') else node_info.get('lastHeard', 0),
            'hopsAway': getattr(node_info, 'hopsAway', 0) if hasattr(node_info, 'hopsAway') else node_info.get('hopsAway', 0)
        }
        
        return node_data
        
    except Exception as e:
        print(f"  ⚠ Erreur sérialisation nœud {node_id}: {e}")
        return {
            'node_id': str(node_id),
            'error': str(e)
        }

def extract_neighbors(node_info):
    """
    Extraire les informations de voisinage d'un nœud
    Gère plusieurs formats possibles
    """
    neighbors = []
    
    try:
        # Méthode 1 : neighborinfo (protobuf)
        if hasattr(node_info, 'neighborinfo') and node_info.neighborinfo:
            neighborinfo = node_info.neighborinfo
            
            # Les voisins sont dans neighborinfo.neighbors
            if hasattr(neighborinfo, 'neighbors'):
                for neighbor in neighborinfo.neighbors:
                    neighbor_data = {
                        'node_id': f"!{neighbor.node_id:08x}",
                        'snr': neighbor.snr if hasattr(neighbor, 'snr') else 0
                    }
                    neighbors.append(neighbor_data)
                    
            print(f"  ✓ {len(neighbors)} voisins depuis neighborinfo.neighbors")
            return neighbors
        
        # Méthode 2 : neighbors (dictionnaire)
        if isinstance(node_info, dict) and 'neighborinfo' in node_info:
            neighborinfo = node_info['neighborinfo']
            
            if isinstance(neighborinfo, dict) and 'neighbors' in neighborinfo:
                for neighbor in neighborinfo['neighbors']:
                    if isinstance(neighbor, dict):
                        neighbors.append(neighbor)
                    else:
                        neighbor_data = {
                            'node_id': f"!{neighbor.node_id:08x}",
                            'snr': getattr(neighbor, 'snr', 0)
                        }
                        neighbors.append(neighbor_data)
                        
            print(f"  ✓ {len(neighbors)} voisins depuis dict neighborinfo")
            return neighbors
        
        # Méthode 3 : Vérifier les attributs directs
        for attr_name in ['neighbors', 'neighbour_info', 'neighborInfo']:
            if hasattr(node_info, attr_name):
                attr = getattr(node_info, attr_name)
                if attr:
                    print(f"  ℹ Attribut '{attr_name}' trouvé: {type(attr)}")
                    # Tenter d'extraire les données
                    if isinstance(attr, list):
                        for item in attr:
                            if hasattr(item, 'node_id'):
                                neighbors.append({
                                    'node_id': f"!{item.node_id:08x}",
                                    'snr': getattr(item, 'snr', 0)
                                })
        
        if neighbors:
            print(f"  ✓ {len(neighbors)} voisins depuis attributs directs")
            return neighbors
        
        # Aucun voisin trouvé
        print(f"  ⚠ Pas d'infos de voisinage détectées")
        return []
        
    except Exception as e:
        print(f"  ✗ Erreur extraction voisins: {e}")
        import traceback
        print(traceback.format_exc())
        return []

def export_mesh_data(host, port=4403, output_file="mesh_neighbors.json"):
    """
    Se connecter à un nœud et exporter toutes les données de voisinage
    """
    print(f"🔌 Connexion à {host}:{port}...")
    
    try:
        interface = meshtastic.tcp_interface.TCPInterface(
            hostname=host,
            portNumber=port
        )
        
        # Attendre que les données se chargent
        print("⏳ Chargement des données...")
        time.sleep(5)
        
        # Récupérer tous les nœuds
        nodes = interface.nodes
        print(f"📊 {len(nodes)} nœuds trouvés\n")
        
        # Structure de sortie
        output_data = {
            'export_time': datetime.now().isoformat(),
            'source_host': host,
            'total_nodes': len(nodes),
            'nodes': {}
        }
        
        # Traiter chaque nœud
        for node_id, node_info in nodes.items():
            # Normaliser node_id
            if isinstance(node_id, str):
                if node_id.startswith('!'):
                    node_id_clean = node_id
                else:
                    node_id_clean = f"!{int(node_id, 16):08x}"
            else:
                node_id_clean = f"!{node_id:08x}"
            
            print(f"Traitement de {node_id_clean}...")
            
            # Sérialiser les données du nœud
            node_data = serialize_node_data(node_id, node_info)
            
            # Extraire les voisins
            neighbors = extract_neighbors(node_info)
            node_data['neighbors'] = neighbors
            node_data['neighbor_count'] = len(neighbors)
            
            output_data['nodes'][node_id_clean] = node_data
        
        # Fermer l'interface
        interface.close()
        
        # Statistiques finales
        total_neighbors = sum(
            len(node.get('neighbors', [])) 
            for node in output_data['nodes'].values()
        )
        nodes_with_neighbors = sum(
            1 for node in output_data['nodes'].values() 
            if len(node.get('neighbors', [])) > 0
        )
        
        output_data['statistics'] = {
            'nodes_with_neighbors': nodes_with_neighbors,
            'total_neighbor_entries': total_neighbors,
            'average_neighbors': total_neighbors / len(nodes) if nodes else 0
        }
        
        # Écrire le fichier JSON
        print(f"\n💾 Écriture dans {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Export réussi!")
        print(f"📊 Statistiques:")
        print(f"   • Nœuds avec voisins: {nodes_with_neighbors}/{len(nodes)}")
        print(f"   • Total entrées voisins: {total_neighbors}")
        print(f"   • Moyenne voisins/nœud: {total_neighbors / len(nodes):.1f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur : {e}")
        import traceback
        print(traceback.format_exc())
        return False

def debug_node_structure(host, port=4403):
    """
    Mode debug : afficher la structure d'un nœud pour diagnostic
    """
    print(f"🔍 MODE DEBUG - Analyse structure nœud sur {host}:{port}\n")
    
    try:
        interface = meshtastic.tcp_interface.TCPInterface(
            hostname=host,
            portNumber=port
        )
        
        time.sleep(5)
        nodes = interface.nodes
        
        # Prendre le premier nœud
        if not nodes:
            print("❌ Aucun nœud trouvé")
            return
        
        node_id, node_info = next(iter(nodes.items()))
        
        print(f"📋 Structure du nœud {node_id}:")
        print(f"   Type: {type(node_info)}")
        print(f"   Attributs: {dir(node_info)}")
        
        # Vérifier neighborinfo
        if hasattr(node_info, 'neighborinfo'):
            print(f"\n✓ node_info.neighborinfo existe")
            neighborinfo = node_info.neighborinfo
            print(f"   Type: {type(neighborinfo)}")
            print(f"   Attributs: {dir(neighborinfo)}")
            
            if hasattr(neighborinfo, 'neighbors'):
                print(f"\n✓ neighborinfo.neighbors existe")
                print(f"   Type: {type(neighborinfo.neighbors)}")
                print(f"   Contenu: {neighborinfo.neighbors}")
        else:
            print(f"\n✗ node_info.neighborinfo n'existe pas")
        
        # Afficher toutes les clés si c'est un dict
        if isinstance(node_info, dict):
            print(f"\n📦 Clés du dictionnaire:")
            for key in node_info.keys():
                print(f"   • {key}: {type(node_info[key])}")
        
        interface.close()
        
    except Exception as e:
        print(f"✗ Erreur debug: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    import sys
    
    # Configuration
    HOST = "192.168.1.38"  # Adresse de tigrog2
    PORT = 4403
    OUTPUT_FILE = "mesh_neighbors.json"
    
    # Mode debug si argument --debug
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        debug_node_structure(HOST, PORT)
    else:
        # Export normal
        success = export_mesh_data(HOST, PORT, OUTPUT_FILE)
        sys.exit(0 if success else 1)
