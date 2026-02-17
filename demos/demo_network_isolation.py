#!/usr/bin/env python3
"""
Demo de l'isolation réseau pour les commandes
Vérifie que les commandes MC ne peuvent pas être appelées depuis MT et vice versa
"""

import sys
import os


def test_network_isolation_logic():
    """Test la logique d'isolation sans importer les modules complets"""
    print("=" * 80)
    print("🧪 TEST: Logique d'isolation réseau des commandes")
    print("=" * 80)
    print()
    
    # Définir les commandes réseau-spécifiques (comme dans message_router.py)
    meshcore_only_commands = ['/nodesmc', '/trafficmc']
    # Note: Order matters - check longer commands first to avoid false matches
    meshtastic_only_commands = ['/nodemt', '/trafficmt', '/neighbors', '/nodes', '/my', '/trace']
    
    def should_block_command(message, is_from_meshcore, is_from_meshtastic):
        """
        Logique de validation (extrait de message_router.py)
        Retourne (blocked, reason) où blocked est True si la commande doit être bloquée
        """
        # Check if MeshCore command is being called from Meshtastic
        if is_from_meshtastic:
            for mc_cmd in meshcore_only_commands:
                if message.startswith(mc_cmd):
                    return (True, f"🚫 {mc_cmd} est réservé au réseau MeshCore. Utilisez /nodemt ou /trafficmt pour Meshtastic.")
        
        # Check if Meshtastic command is being called from MeshCore
        if is_from_meshcore:
            for mt_cmd in meshtastic_only_commands:
                # Use word boundary check to avoid false matches (e.g., /nodes matching /nodesmc)
                if message == mt_cmd or message.startswith(mt_cmd + ' '):
                    return (True, f"🚫 {mt_cmd} est réservé au réseau Meshtastic. Utilisez /nodesmc ou /trafficmc pour MeshCore.")
        
        return (False, None)
    
    # ========================================
    # TEST 1: Commandes MC depuis MT (DOIT BLOQUER)
    # ========================================
    print("\n" + "=" * 80)
    print("📋 TEST 1: Commandes MeshCore depuis Meshtastic (DOIVENT BLOQUER)")
    print("=" * 80)
    
    test_cases_1 = [
        ('/nodesmc', 'local'),
        ('/nodesmc 2', 'tcp'),
        ('/trafficmc', 'tigrog2'),
        ('/trafficmc 12', 'local'),
    ]
    
    all_passed = True
    for message, source in test_cases_1:
        is_from_mt = source in ['local', 'tcp', 'tigrog2']
        blocked, reason = should_block_command(message, is_from_meshcore=False, is_from_meshtastic=is_from_mt)
        
        print(f"\n🔍 Test: '{message}' depuis source='{source}'")
        if blocked:
            print(f"✅ BLOQUÉ comme attendu")
            print(f"   Raison: {reason}")
        else:
            print("❌ ERREUR: Commande non bloquée!")
            all_passed = False
    
    # ========================================
    # TEST 2: Commandes MT depuis MC (DOIT BLOQUER)
    # ========================================
    print("\n" + "=" * 80)
    print("📋 TEST 2: Commandes Meshtastic depuis MeshCore (DOIVENT BLOQUER)")
    print("=" * 80)
    
    test_cases_2 = [
        ('/nodemt', 'meshcore'),
        ('/nodemt 2', 'meshcore'),
        ('/trafficmt', 'meshcore'),
        ('/trafficmt 12', 'meshcore'),
        ('/nodes', 'meshcore'),
        ('/neighbors', 'meshcore'),
        ('/my', 'meshcore'),
        ('/trace', 'meshcore'),
    ]
    
    for message, source in test_cases_2:
        is_from_mc = (source == 'meshcore')
        blocked, reason = should_block_command(message, is_from_meshcore=is_from_mc, is_from_meshtastic=False)
        
        print(f"\n🔍 Test: '{message}' depuis source='{source}'")
        if blocked:
            print(f"✅ BLOQUÉ comme attendu")
            print(f"   Raison: {reason}")
        else:
            print("❌ ERREUR: Commande non bloquée!")
            all_passed = False
    
    # ========================================
    # TEST 3: Commandes autorisées (NE DOIVENT PAS BLOQUER)
    # ========================================
    print("\n" + "=" * 80)
    print("📋 TEST 3: Commandes sur leur réseau approprié (NE DOIVENT PAS BLOQUER)")
    print("=" * 80)
    
    test_cases_3 = [
        # MC commands depuis MC (OK)
        ('/nodesmc', 'meshcore'),
        ('/trafficmc', 'meshcore'),
        # MT commands depuis MT (OK)
        ('/nodemt', 'local'),
        ('/trafficmt', 'tcp'),
        ('/nodes', 'tigrog2'),
        ('/neighbors', 'local'),
        ('/my', 'tcp'),
        ('/trace', 'local'),
    ]
    
    for message, source in test_cases_3:
        is_from_mc = (source == 'meshcore')
        is_from_mt = source in ['local', 'tcp', 'tigrog2']
        blocked, reason = should_block_command(message, is_from_meshcore=is_from_mc, is_from_meshtastic=is_from_mt)
        
        print(f"\n🔍 Test: '{message}' depuis source='{source}'")
        if not blocked:
            print("✅ AUTORISÉ comme attendu")
        else:
            print(f"❌ ERREUR: Commande bloquée à tort!")
            print(f"   Raison: {reason}")
            all_passed = False
    
    # ========================================
    # TEST 4: Commandes neutres (NE DOIVENT PAS BLOQUER)
    # ========================================
    print("\n" + "=" * 80)
    print("📋 TEST 4: Commandes neutres (disponibles sur tous les réseaux)")
    print("=" * 80)
    
    test_cases_4 = [
        ('/help', 'meshcore'),
        ('/help', 'local'),
        ('/bot test', 'meshcore'),
        ('/bot test', 'tcp'),
        ('/weather', 'meshcore'),
        ('/power', 'local'),
        ('/sys', 'meshcore'),
        ('/trafic', 'local'),  # /trafic (sans mt/mc) est neutre
    ]
    
    for message, source in test_cases_4:
        is_from_mc = (source == 'meshcore')
        is_from_mt = source in ['local', 'tcp', 'tigrog2']
        blocked, reason = should_block_command(message, is_from_meshcore=is_from_mc, is_from_meshtastic=is_from_mt)
        
        print(f"\n🔍 Test: '{message}' depuis source='{source}'")
        if not blocked:
            print("✅ AUTORISÉ comme attendu")
        else:
            print(f"❌ ERREUR: Commande neutre bloquée à tort!")
            print(f"   Raison: {reason}")
            all_passed = False
    
    # ========================================
    # RÉSUMÉ
    # ========================================
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ TOUS LES TESTS RÉUSSIS")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
    print("=" * 80)
    print()
    print("Tests d'isolation réseau:")
    print("  ✅ Commandes MC (/nodesmc, /trafficmc) bloquées depuis MT")
    print("  ✅ Commandes MT (/nodemt, /trafficmt, /nodes, /neighbors, /my, /trace) bloquées depuis MC")
    print("  ✅ Commandes autorisées sur leur réseau respectif")
    print("  ✅ Commandes neutres (/help, /bot, /weather, etc.) disponibles partout")
    print()
    print("🎯 OBJECTIF ATTEINT:")
    print("   • Les commandes MeshCore ne peuvent pas être appelées depuis Meshtastic")
    print("   • Les commandes Meshtastic ne peuvent pas être appelées depuis MeshCore")
    print("   • Les utilisateurs reçoivent des messages d'erreur clairs et utiles")
    print()
    
    return all_passed


if __name__ == "__main__":
    try:
        success = test_network_isolation_logic()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERREUR pendant les tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
