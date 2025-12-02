#!/usr/bin/env python3
"""
Validation script to check if info.json has the required fields for map visualization.
"""

import json
import sys

def validate_info_json(json_file):
    """Validate that info.json has all required fields."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if 'Nodes in mesh' not in data:
            print("❌ ERREUR: Clé 'Nodes in mesh' manquante")
            return False
        
        nodes = data['Nodes in mesh']
        print(f"✅ Trouvé {len(nodes)} nœuds\n")
        
        nodes_with_hops = 0
        nodes_with_neighbors = 0
        total_neighbors = 0
        
        for node_id, node in nodes.items():
            # Check hopsAway
            if 'hopsAway' in node:
                nodes_with_hops += 1
            
            # Check neighbors
            if 'neighbors' in node and isinstance(node['neighbors'], list):
                if len(node['neighbors']) > 0:
                    nodes_with_neighbors += 1
                    total_neighbors += len(node['neighbors'])
                    
                    # Validate neighbor structure
                    for neighbor in node['neighbors']:
                        if 'nodeId' not in neighbor:
                            print(f"⚠️  Nœud {node_id}: voisin sans 'nodeId'")
                        if 'snr' not in neighbor:
                            print(f"⚠️  Nœud {node_id}: voisin sans 'snr'")
        
        print(f"📊 Statistiques:")
        print(f"   • Nœuds avec hopsAway: {nodes_with_hops}/{len(nodes)}")
        print(f"   • Nœuds avec neighbors: {nodes_with_neighbors}/{len(nodes)}")
        print(f"   • Total voisins: {total_neighbors}")
        
        if nodes_with_hops == 0:
            print("\n❌ PROBLÈME: Aucun nœud n'a le champ 'hopsAway'")
            print("   → Les nœuds apparaîtront GRIS sur la carte")
            print("   → Vérifiez que la base de données contient des paquets avec 'hops'")
            return False
        
        if nodes_with_neighbors == 0:
            print("\n❌ PROBLÈME: Aucun nœud n'a de voisins")
            print("   → Aucune liaison ne sera affichée sur la carte")
            print("   → Vérifiez que la base de données contient des NEIGHBORINFO_APP")
            return False
        
        print("\n✅ Le fichier JSON semble correct pour la visualisation carte!")
        
        # Show sample
        print("\n📋 Exemple de nœud:")
        sample_node_id = list(nodes.keys())[0]
        sample = nodes[sample_node_id]
        print(f"   Node ID: {sample_node_id}")
        print(f"   Name: {sample.get('user', {}).get('longName', 'N/A')}")
        print(f"   hopsAway: {sample.get('hopsAway', 'MANQUANT')}")
        print(f"   neighbors: {len(sample.get('neighbors', []))} voisin(s)")
        if 'neighbors' in sample and sample['neighbors']:
            print(f"   Premier voisin: {sample['neighbors'][0]}")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Fichier non trouvé: {json_file}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    json_file = sys.argv[1] if len(sys.argv) > 1 else "info.json"
    
    print(f"🔍 Validation de {json_file}\n")
    print("=" * 60)
    
    success = validate_info_json(json_file)
    sys.exit(0 if success else 1)
