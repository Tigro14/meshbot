#!/usr/bin/env python3
"""
Export des nodes Meshtastic avec informations de voisinage
Connexion via TCP
"""

import meshtastic
import meshtastic.tcp_interface
import json
import time
from datetime import datetime

def export_mesh_data(host='192.168.1.38', output_file='info_neighbors.json'):
    """
    Exporte les données du mesh incluant les informations de voisinage
    """
    print(f"Connexion à {host}...")
    
    try:
        # Connexion TCP
        interface = meshtastic.tcp_interface.TCPInterface(hostname=host)
        print("✓ Connecté")
        
        # Attendre un peu pour que les données soient disponibles
        time.sleep(2)
        
        # Récupérer les nodes
        nodes_dict = {}
        
        print(f"\nNodes trouvés : {len(interface.nodes)}")
        
        for node_id, node_info in interface.nodes.items():
            print(f"\nTraitement de {node_id}...")
            
            node_data = {
                'num': node_info.get('num'),
                'user': node_info.get('user', {}),
                'position': node_info.get('position', {}),
                'snr': node_info.get('snr'),
                'lastHeard': node_info.get('lastHeard'),
                'deviceMetrics': node_info.get('deviceMetrics', {}),
                'hopsAway': node_info.get('hopsAway', 0)
            }
            
            # IMPORTANT : Récupérer les neighbors
            if 'neighbors' in node_info:
                neighbors_list = []
                neighbors = node_info['neighbors']
                
                print(f"  → {len(neighbors)} voisins détectés")
                
                for neighbor in neighbors:
                    neighbor_data = {
                        'nodeId': neighbor.get('nodeId'),
                        'snr': neighbor.get('snr')
                    }
                    neighbors_list.append(neighbor_data)
                    print(f"    • {neighbor_data['nodeId']} (SNR: {neighbor_data['snr']})")
                
                node_data['neighbors'] = neighbors_list
            else:
                print(f"  ⚠ Pas d'infos de voisinage pour ce node")
            
            nodes_dict[node_id] = node_data
        
        # Créer la structure finale
        output_data = {
            'Nodes in mesh': nodes_dict,
            'exported_at': datetime.now().isoformat(),
            'export_method': 'TCP',
            'host': host
        }
        
        # Sauvegarder
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Export réussi : {output_file}")
        print(f"  Total nodes : {len(nodes_dict)}")
        
        # Statistiques sur les neighbors
        nodes_with_neighbors = sum(1 for n in nodes_dict.values() if 'neighbors' in n)
        total_links = sum(len(n.get('neighbors', [])) for n in nodes_dict.values())
        
        print(f"  Nodes avec voisins : {nodes_with_neighbors}/{len(nodes_dict)}")
        print(f"  Total liaisons : {total_links}")
        
        interface.close()
        return output_data
        
    except Exception as e:
        print(f"✗ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return None

def check_neighbor_info_config(host='192.168.1.38'):
    """
    Vérifie la configuration du module neighborInfo
    """
    print("Vérification de la configuration neighborInfo...")
    
    try:
        interface = meshtastic.tcp_interface.TCPInterface(hostname=host)
        time.sleep(2)
        
        # Récupérer la config (si disponible via l'interface)
        print("\nPour vérifier manuellement la config :")
        print("  meshtastic --host 192.168.1.38 --get neighborinfo")
        
        interface.close()
        
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Export Meshtastic - Données de voisinage")
    print("=" * 60)
    
    # Export
    data = export_mesh_data(host='192.168.1.38')
    
    if data:
        print("\n" + "=" * 60)
        print("Export terminé avec succès !")
        print("=" * 60)
        print("\nFichier généré : info_neighbors.json")
        print("Copiez ce fichier comme 'info.json' pour votre carte web")
        
        # Si pas de neighbors détectés
        nodes = data.get('Nodes in mesh', {})
        if not any('neighbors' in n for n in nodes.values()):
            print("\n⚠ ATTENTION : Aucune donnée de voisinage trouvée")
            print("\nActions possibles :")
            print("1. Attendre le prochain cycle (updateInterval: 14400s = 4h)")
            print("2. Réduire temporairement l'intervalle :")
            print("   meshtastic --host 192.168.1.38 --set neighborinfo.update_interval 900")
            print("3. Vérifier que transmitOverLora est activé")
            print("4. Attendre 15-30 minutes puis relancer cet export")
    else:
        print("\n✗ Échec de l'export")
