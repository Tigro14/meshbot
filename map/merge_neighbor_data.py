#!/usr/bin/env python3
"""
Merge info_neighbors.json into info.json

This script reads neighbor data from info_neighbors.json (output of export_neighbors_from_db.py)
and merges it into info.json (output of export_nodes_from_db.py), adding the neighbors array
to each node.

Usage:
    merge_neighbor_data.py info.json info_neighbors.json output.json
"""

import json
import sys

def merge_neighbor_data(info_file, neighbors_file, output_file):
    """
    Merge neighbor data into node info.
    
    Args:
        info_file: Path to info.json (has node data with hopsAway)
        neighbors_file: Path to info_neighbors.json (has neighbor relationships)
        output_file: Path to write merged output
    """
    try:
        # Load info.json
        with open(info_file, 'r') as f:
            info_data = json.load(f)
        
        if 'Nodes in mesh' not in info_data:
            print(f"❌ Erreur: 'Nodes in mesh' manquant dans {info_file}", file=sys.stderr)
            return False
        
        nodes = info_data['Nodes in mesh']
        print(f"✅ Chargé {len(nodes)} nœuds depuis {info_file}", file=sys.stderr)
        
        # Load info_neighbors.json
        try:
            with open(neighbors_file, 'r') as f:
                neighbors_data = json.load(f)
            
            if 'nodes' not in neighbors_data:
                print(f"⚠️  'nodes' manquant dans {neighbors_file}, aucun voisin à fusionner", file=sys.stderr)
                neighbor_nodes = {}
            else:
                neighbor_nodes = neighbors_data['nodes']
                print(f"✅ Chargé {len(neighbor_nodes)} nœuds avec voisins depuis {neighbors_file}", file=sys.stderr)
        
        except FileNotFoundError:
            print(f"⚠️  {neighbors_file} non trouvé, aucun voisin à fusionner", file=sys.stderr)
            neighbor_nodes = {}
        except json.JSONDecodeError as e:
            print(f"⚠️  Erreur JSON dans {neighbors_file}: {e}, aucun voisin à fusionner", file=sys.stderr)
            neighbor_nodes = {}
        
        # Merge neighbors into nodes
        nodes_updated = 0
        total_neighbors_added = 0
        
        for node_id, node_data in nodes.items():
            # Check if this node has neighbors in the neighbors file
            if node_id in neighbor_nodes:
                neighbor_info = neighbor_nodes[node_id]
                neighbors_list = neighbor_info.get('neighbors_extracted', [])
                
                if neighbors_list:
                    # Convert to the format map.html expects
                    formatted_neighbors = []
                    for neighbor in neighbors_list:
                        # neighbor can have various formats, normalize it
                        if isinstance(neighbor, dict):
                            neighbor_id = neighbor.get('node_id') or neighbor.get('nodeId')
                            snr = neighbor.get('snr') or neighbor.get('SNR')
                            
                            if neighbor_id:
                                formatted_neighbors.append({
                                    'nodeId': neighbor_id if isinstance(neighbor_id, str) else f"!{neighbor_id:08x}",
                                    'snr': snr
                                })
                    
                    if formatted_neighbors:
                        node_data['neighbors'] = formatted_neighbors
                        nodes_updated += 1
                        total_neighbors_added += len(formatted_neighbors)
        
        print(f"📊 Fusion: {nodes_updated} nœuds mis à jour avec {total_neighbors_added} voisins", file=sys.stderr)
        
        # Write merged output
        with open(output_file, 'w') as f:
            json.dump(info_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Fichier fusionné écrit: {output_file}", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: merge_neighbor_data.py info.json info_neighbors.json output.json")
        print()
        print("Fusionne les données de voisinage dans le fichier info.json principal")
        sys.exit(1)
    
    info_file = sys.argv[1]
    neighbors_file = sys.argv[2]
    output_file = sys.argv[3]
    
    success = merge_neighbor_data(info_file, neighbors_file, output_file)
    sys.exit(0 if success else 1)
