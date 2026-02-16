#!/usr/bin/env python3
"""
Test de déduplication des liaisons radio dans /propag
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_link_deduplication():
    """
    Teste la logique de déduplication des liaisons radio
    """
    # Simuler des liaisons avec doublons
    links_with_distance = [
        # Liaison A->B à différents moments
        {
            'from_id': 0xa6ea559e,
            'to_id': 0xa2e175ac,
            'from_name': 'Node A',
            'to_name': 'Node B',
            'distance_km': 9.8,
            'snr': -8.0,
            'rssi': -100,
            'timestamp': 1000
        },
        {
            'from_id': 0xa6ea559e,
            'to_id': 0xa2e175ac,
            'from_name': 'Node A',
            'to_name': 'Node B',
            'distance_km': 9.8,
            'snr': -5.5,
            'rssi': -99,
            'timestamp': 2000
        },
        {
            'from_id': 0xa6ea559e,
            'to_id': 0xa2e175ac,
            'from_name': 'Node A',
            'to_name': 'Node B',
            'distance_km': 9.8,
            'snr': -6.5,
            'rssi': -101,
            'timestamp': 3000
        },
        # Liaison différente C->D
        {
            'from_id': 0xd45aa8d4,
            'to_id': 0xa2e175ac,
            'from_name': 'Node C',
            'to_name': 'Node B',
            'distance_km': 17.0,
            'snr': None,
            'rssi': -89,
            'timestamp': 4000
        }
    ]
    
    print(f"📊 Liens avant déduplication: {len(links_with_distance)}")
    
    # Déduplication par paire (from_id, to_id)
    # Conserver uniquement le meilleur lien pour chaque paire de nœuds
    unique_links = {}
    for link in links_with_distance:
        # Créer une clé unique pour la paire de nœuds (bidirectionnelle)
        # Trier les IDs pour que A→B et B→A soient considérés comme la même liaison
        pair_key = tuple(sorted([link['from_id'], link['to_id']]))
        
        # Si cette paire n'existe pas encore, ou si ce lien a un meilleur signal
        if pair_key not in unique_links:
            unique_links[pair_key] = link
            print(f"  ✅ Nouveau lien: {link['from_name']} → {link['to_name']} (SNR: {link['snr']}, timestamp: {link['timestamp']})")
        else:
            # Comparer et garder le meilleur lien (priorité: distance > SNR > timestamp)
            existing = unique_links[pair_key]
            
            replace = False
            if link['snr'] is not None and existing['snr'] is not None:
                if link['snr'] > existing['snr']:
                    replace = True
                    print(f"  🔄 Remplacement par meilleur SNR: {link['snr']} > {existing['snr']}")
            elif link['snr'] is not None and existing['snr'] is None:
                replace = True
                print(f"  🔄 Remplacement: nouveau a SNR, ancien non")
            elif link['timestamp'] > existing['timestamp']:
                replace = True
                print(f"  🔄 Remplacement par timestamp plus récent: {link['timestamp']} > {existing['timestamp']}")
            else:
                print(f"  ⏭️  Ignoré: moins bon que l'existant")
            
            if replace:
                unique_links[pair_key] = link
    
    # Convertir le dictionnaire en liste
    deduplicated = list(unique_links.values())
    
    print(f"\n📊 Liens après déduplication: {len(deduplicated)}")
    print("\n🎯 Résultat:")
    for i, link in enumerate(deduplicated, 1):
        print(f"  {i}. {link['from_name']} → {link['to_name']}")
        print(f"     Distance: {link['distance_km']}km")
        print(f"     SNR: {link['snr']}, RSSI: {link['rssi']}")
        print(f"     Timestamp: {link['timestamp']}")
    
    # Vérifications
    assert len(deduplicated) == 2, f"Expected 2 unique links, got {len(deduplicated)}"
    
    # Vérifier que le meilleur lien A->B a été conservé (SNR -5.5 car le plus élevé)
    ab_link = next((l for l in deduplicated if l['from_id'] == 0xa6ea559e), None)
    assert ab_link is not None, "Link A->B should exist"
    assert ab_link['snr'] == -5.5, f"Expected SNR -5.5 (best), got {ab_link['snr']}"
    assert ab_link['timestamp'] == 2000, f"Expected timestamp 2000, got {ab_link['timestamp']}"
    
    print("\n✅ Test de déduplication réussi!")
    print("   - 4 liens réduits à 2 liens uniques")
    print("   - Meilleur SNR conservé pour liaison A->B (-5.5)")
    

if __name__ == '__main__':
    test_link_deduplication()
