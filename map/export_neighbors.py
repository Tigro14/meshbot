#!/usr/bin/env python3
"""
Script d'export des informations de voisinage Meshtastic
Version ultra-robuste avec sérialisation récursive complète
"""

import json
import time
import meshtastic.tcp_interface
from datetime import datetime

def make_json_safe(obj, max_depth=10, current_depth=0):
    """
    Convertir récursivement n'importe quel objet en type JSON-safe
    Gère tous les types Meshtastic, protobuf, etc.
    """
    # Protection contre récursion infinie
    if current_depth > max_depth:
        return str(obj)
    
    # Types déjà JSON-safe
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    
    # Bytes -> hex string
    if isinstance(obj, bytes):
        return obj.hex()
    
    # Liste
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(item, max_depth, current_depth + 1) for item in obj]
    
    # Dictionnaire
    if isinstance(obj, dict):
        return {
            str(k): make_json_safe(v, max_depth, current_depth + 1) 
            for k, v in obj.items()
        }
    
    # Objets protobuf ou Meshtastic
    # Essayer d'extraire les attributs
    try:
        # Si l'objet a une méthode __dict__, l'utiliser
        if hasattr(obj, '__dict__'):
            obj_dict = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):  # Ignorer les attributs privés
                    obj_dict[key] = make_json_safe(value, max_depth, current_depth + 1)
            return obj_dict
        
        # Sinon, essayer dir() pour lister les attributs
        obj_dict = {}
        for attr_name in dir(obj):
            if not attr_name.startswith('_') and not callable(getattr(obj, attr_name, None)):
                try:
                    value = getattr(obj, attr_name)
                    obj_dict[attr_name] = make_json_safe(value, max_depth, current_depth + 1)
                except:
                    continue
        
        if obj_dict:
            return obj_dict
        
        # En dernier recours, convertir en string
        return str(obj)
        
    except:
        return str(obj)

def extract_neighbors(node_info):
    """
    Extraire les informations de voisinage d'un nœud
    """
    neighbors = []
    
    try:
        # Chercher dans tous les attributs possibles
        for attr_name in ['neighborinfo', 'neighbour_info', 'neighborInfo', 'neighbors']:
            if hasattr(node_info, attr_name):
                attr = getattr(node_info, attr_name)
                
                if attr is None:
                    continue
                
                # Si c'est neighborinfo, chercher neighbors dedans
                if attr_name in ['neighborinfo', 'neighbour_info', 'neighborInfo']:
                    if hasattr(attr, 'neighbors'):
                        neighbor_list = getattr(attr, 'neighbors')
                        if neighbor_list:
                            print(f"  ✓ Trouvé {len(neighbor_list)} voisins dans {attr_name}.neighbors")
                            
                            for neighbor in neighbor_list:
                                # Convertir le voisin en dict JSON-safe
                                neighbor_data = make_json_safe(neighbor)
                                neighbors.append(neighbor_data)
                            
                            return neighbors
                
                # Si c'est directement neighbors
                elif attr_name == 'neighbors' and attr:
                    print(f"  ✓ Trouvé {len(attr)} voisins dans {attr_name}")
                    for neighbor in attr:
                        neighbor_data = make_json_safe(neighbor)
                        neighbors.append(neighbor_data)
                    return neighbors
        
        # Si dict
        if isinstance(node_info, dict):
            for key in ['neighborinfo', 'neighbour_info', 'neighborInfo']:
                if key in node_info and node_info[key]:
                    neighborinfo = node_info[key]
                    if isinstance(neighborinfo, dict) and 'neighbors' in neighborinfo:
                        neighbors_list = neighborinfo['neighbors']
                        print(f"  ✓ Trouvé {len(neighbors_list)} voisins dans dict[{key}]['neighbors']")
                        return [make_json_safe(n) for n in neighbors_list]
        
        print(f"  ⚠ Pas d'infos de voisinage détectées")
        return []
        
    except Exception as e:
        print(f"  ✗ Erreur extraction voisins: {e}")
        import traceback
        print(traceback.format_exc())
        return []

def export_mesh_data(host, port=4403, output_file="mesh_neighbors.json"):
    """
    Se connecter à un nœud et exporter toutes les données
    """
    print(f"🔌 Connexion à {host}:{port}...")
    
    try:
        interface = meshtastic.tcp_interface.TCPInterface(
            hostname=host,
            portNumber=port
        )
        
        print("⏳ Chargement des données (10 secondes)...")
        time.sleep(10)  # Attendre plus longtemps
        
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
            
            # Convertir TOUT le nœud en JSON-safe
            node_data = make_json_safe(node_info)
            
            # Ajouter timestamp
            node_data['export_timestamp'] = datetime.now().isoformat()
            
            # Extraire et ajouter les voisins
            neighbors = extract_neighbors(node_info)
            node_data['neighbors_extracted'] = neighbors
            node_data['neighbor_count'] = len(neighbors)
            
            output_data['nodes'][node_id_clean] = node_data
        
        interface.close()
        
        # Statistiques
        total_neighbors = sum(
            len(node.get('neighbors_extracted', [])) 
            for node in output_data['nodes'].values()
        )
        nodes_with_neighbors = sum(
            1 for node in output_data['nodes'].values() 
            if len(node.get('neighbors_extracted', [])) > 0
        )
        
        output_data['statistics'] = {
            'nodes_with_neighbors': nodes_with_neighbors,
            'total_neighbor_entries': total_neighbors,
            'average_neighbors': total_neighbors / len(nodes) if nodes else 0
        }
        
        # Écrire le JSON
        print(f"\n💾 Écriture dans {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Export réussi!")
        print(f"📊 Statistiques:")
        print(f"   • Nœuds avec voisins: {nodes_with_neighbors}/{len(nodes)}")
        print(f"   • Total entrées voisins: {total_neighbors}")
        if nodes:
            print(f"   • Moyenne voisins/nœud: {total_neighbors / len(nodes):.1f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur : {e}")
        import traceback
        print(traceback.format_exc())
        return False

def debug_node_structure(host, port=4403):
    """
    Mode debug : afficher la structure détaillée d'un nœud
    """
    print(f"🔍 MODE DEBUG - Analyse structure nœud sur {host}:{port}\n")
    
    try:
        interface = meshtastic.tcp_interface.TCPInterface(
            hostname=host,
            portNumber=port
        )
        
        print("⏳ Chargement des données (10 secondes)...")
        time.sleep(10)
        
        nodes = interface.nodes
        print(f"📊 {len(nodes)} nœuds trouvés\n")
        
        if not nodes:
            print("❌ Aucun nœud trouvé")
            interface.close()
            return
        
        # Prendre le premier nœud avec le plus d'infos
        node_id, node_info = next(iter(nodes.items()))
        
        print(f"{'='*60}")
        print(f"📋 ANALYSE DU NŒUD {node_id}")
        print(f"{'='*60}\n")
        
        print(f"Type: {type(node_info)}")
        print(f"\n📦 Attributs disponibles:")
        
        for attr_name in sorted(dir(node_info)):
            if not attr_name.startswith('_'):
                try:
                    value = getattr(node_info, attr_name)
                    if not callable(value):
                        print(f"   • {attr_name}: {type(value).__name__}")
                        
                        # Si c'est un objet intéressant, afficher plus de détails
                        if attr_name in ['neighborinfo', 'neighbour_info', 'neighbors']:
                            print(f"     └─ Contenu: {value}")
                            if hasattr(value, '__dict__'):
                                print(f"     └─ Sous-attributs: {dir(value)}")
                except Exception as e:
                    print(f"   • {attr_name}: [Erreur: {e}]")
        
        # Si c'est un dict
        if isinstance(node_info, dict):
            print(f"\n📦 Clés du dictionnaire:")
            for key in sorted(node_info.keys()):
                print(f"   • {key}: {type(node_info[key]).__name__}")
        
        # Vérification spécifique neighborinfo
        print(f"\n{'='*60}")
        print(f"🔍 RECHERCHE SPÉCIFIQUE NEIGHBORINFO")
        print(f"{'='*60}\n")
        
        found_neighborinfo = False
        
        # Méthode 1
        if hasattr(node_info, 'neighborinfo'):
            neighborinfo = node_info.neighborinfo
            print(f"✓ node_info.neighborinfo existe")
            print(f"  Type: {type(neighborinfo)}")
            print(f"  Valeur: {neighborinfo}")
            
            if hasattr(neighborinfo, 'neighbors'):
                neighbors = neighborinfo.neighbors
                print(f"  └─ .neighbors existe")
                print(f"     Type: {type(neighbors)}")
                print(f"     Longueur: {len(neighbors) if hasattr(neighbors, '__len__') else 'N/A'}")
                print(f"     Contenu: {neighbors}")
                found_neighborinfo = True
        else:
            print(f"✗ node_info.neighborinfo n'existe pas")
        
        # Méthode 2
        if isinstance(node_info, dict) and 'neighborinfo' in node_info:
            print(f"\n✓ node_info['neighborinfo'] existe (dict)")
            neighborinfo = node_info['neighborinfo']
            print(f"  Type: {type(neighborinfo)}")
            print(f"  Contenu: {neighborinfo}")
            found_neighborinfo = True
        
        if not found_neighborinfo:
            print(f"\n⚠️  AUCUNE INFO DE VOISINAGE TROUVÉE")
            print(f"\nCela signifie probablement que:")
            print(f"  1. Le module neighbor_info n'est pas activé sur les nœuds")
            print(f"  2. Les nœuds n'ont pas encore envoyé d'infos de voisinage")
            print(f"  3. Le temps d'attente est insuffisant (essayer 30s+)")
        
        interface.close()
        
    except Exception as e:
        print(f"✗ Erreur debug: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    import sys
    
    # Configuration
    HOST = "192.168.1.38"  # tigrog2
    PORT = 4403
    OUTPUT_FILE = "mesh_neighbors.json"
    
    # Mode debug si argument --debug
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        debug_node_structure(HOST, PORT)
    else:
        # Export normal
        success = export_mesh_data(HOST, PORT, OUTPUT_FILE)
        sys.exit(0 if success else 1)
