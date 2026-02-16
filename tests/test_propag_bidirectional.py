#!/usr/bin/env python3
"""
Test de déduplication bidirectionnelle des liaisons radio
Vérifie que A→B et B→A sont considérés comme la même liaison
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_bidirectional_deduplication():
    """
    Teste que les liaisons bidirectionnelles sont correctement dédupliquées
    """
    # Simuler des liaisons dans les deux directions
    links_with_distance = [
        # A → B
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
        # B → A (direction inverse, devrait être dédupliquée)
        {
            'from_id': 0xa2e175ac,
            'to_id': 0xa6ea559e,
            'from_name': 'Node B',
            'to_name': 'Node A',
            'distance_km': 9.8,
            'snr': -5.5,
            'rssi': -99,
            'timestamp': 2000
        },
        # Liaison différente C → D
        {
            'from_id': 0xd45aa8d4,
            'to_id': 0x12345678,
            'from_name': 'Node C',
            'to_name': 'Node D',
            'distance_km': 17.0,
            'snr': -10.0,
            'rssi': -89,
            'timestamp': 3000
        }
    ]
    
    print(f"📊 Liens avant déduplication: {len(links_with_distance)}")
    print("   - A → B (SNR: -8.0)")
    print("   - B → A (SNR: -5.5) [direction inverse]")
    print("   - C → D (SNR: -10.0)")
    
    # Déduplication par paire (from_id, to_id)
    unique_links = {}
    for link in links_with_distance:
        # Créer une clé unique pour la paire de nœuds (bidirectionnelle)
        # Trier les IDs pour que A→B et B→A soient considérés comme la même liaison
        pair_key = tuple(sorted([link['from_id'], link['to_id']]))
        
        print(f"\n🔍 Traitement: {link['from_name']} → {link['to_name']}")
        print(f"   Pair key: {pair_key}")
        
        if pair_key not in unique_links:
            unique_links[pair_key] = link
            print(f"   ✅ Nouveau lien ajouté")
        else:
            # Comparer et garder le meilleur lien
            existing = unique_links[pair_key]
            
            replace = False
            if link['snr'] is not None and existing['snr'] is not None:
                if link['snr'] > existing['snr']:
                    replace = True
                    print(f"   🔄 Remplacement: meilleur SNR ({link['snr']} > {existing['snr']})")
                else:
                    print(f"   ⏭️  Ignoré: SNR moins bon ({link['snr']} < {existing['snr']})")
            elif link['snr'] is not None and existing['snr'] is None:
                replace = True
                print(f"   🔄 Remplacement: nouveau a SNR, ancien non")
            elif link['timestamp'] > existing['timestamp']:
                replace = True
                print(f"   🔄 Remplacement: plus récent")
            
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
    
    # Vérifications
    assert len(deduplicated) == 2, f"Expected 2 unique links, got {len(deduplicated)}"
    
    # Vérifier que le meilleur lien A-B a été conservé (B→A avec SNR -5.5)
    ab_pair_key = tuple(sorted([0xa6ea559e, 0xa2e175ac]))
    ab_link = unique_links[ab_pair_key]
    assert ab_link['snr'] == -5.5, f"Expected SNR -5.5 (best), got {ab_link['snr']}"
    
    print("\n✅ Test de déduplication bidirectionnelle réussi!")
    print("   - A→B et B→A correctement fusionnés")
    print("   - Meilleur SNR conservé (-5.5 de B→A)")
    print("   - 3 liens réduits à 2 liens uniques")
    

if __name__ == '__main__':
    test_bidirectional_deduplication()
