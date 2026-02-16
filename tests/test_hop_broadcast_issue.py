#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour démontrer le problème avec /hop en mode broadcast
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_hop_broadcast_filtering():
    """Tester que /hop est filtré en mode broadcast"""
    print("🧪 Test: /hop en mode broadcast\n")
    
    # Configuration du message
    message = "/hop"
    sender_id = 0x87654321
    my_id = 0x12345678
    to_id = 0xFFFFFFFF  # Broadcast
    
    is_for_me = (to_id == my_id)  # False
    is_from_me = (sender_id == my_id)  # False
    is_broadcast = to_id in [0xFFFFFFFF, 0]  # True
    
    # Liste des broadcast_commands
    broadcast_commands = ['/echo', '/my', '/weather', '/rain', '/bot', '/info', '/propag']
    is_broadcast_command = any(message.startswith(cmd) for cmd in broadcast_commands)
    
    print(f"Message: '{message}'")
    print(f"To: {hex(to_id)} (Broadcast)")
    print()
    print("Conditions:")
    print(f"  is_for_me: {is_for_me}")
    print(f"  is_from_me: {is_from_me}")
    print(f"  is_broadcast: {is_broadcast}")
    print(f"  is_broadcast_command: {is_broadcast_command}")
    print()
    
    # Vérifier le flux de traitement
    print("Flux de traitement:")
    
    # Ligne 73: Vérifier si c'est une broadcast command
    will_enter_broadcast_block = is_broadcast_command and (is_broadcast or is_for_me) and not is_from_me
    print(f"1. Entre dans bloc broadcast (ligne 73): {will_enter_broadcast_block}")
    
    if not will_enter_broadcast_block:
        # Ligne 98-99: Log si DEBUG_MODE
        print(f"2. Log 'MESSAGE REÇU' (ligne 98): Seulement si DEBUG_MODE=True")
        
        # Ligne 102-103: Filtrer si pas pour nous
        will_be_filtered = not is_for_me
        print(f"3. Filtré (ligne 102-103): {will_be_filtered}")
        
        if will_be_filtered:
            print("4. ❌ RETURN - Ne va jamais à _route_command()")
            print("5. ❌ PAS DE LOG pour /hop")
            print("6. ❌ Handler handle_hop() JAMAIS appelé")
            return False
        else:
            print("4. ✅ Va à _route_command()")
            return True
    else:
        print("2. Entre dans le bloc broadcast")
        print("3. ✅ Traité dans le bloc broadcast")
        return True

def test_hop_direct():
    """Tester /hop en mode direct (non-broadcast)"""
    print("\n🧪 Test: /hop en mode direct\n")
    
    # Configuration du message
    message = "/hop"
    sender_id = 0x87654321
    my_id = 0x12345678
    to_id = 0x12345678  # Direct au bot
    
    is_for_me = (to_id == my_id)  # True
    is_from_me = (sender_id == my_id)  # False
    is_broadcast = to_id in [0xFFFFFFFF, 0]  # False
    
    # Liste des broadcast_commands
    broadcast_commands = ['/echo', '/my', '/weather', '/rain', '/bot', '/info', '/propag']
    is_broadcast_command = any(message.startswith(cmd) for cmd in broadcast_commands)
    
    print(f"Message: '{message}'")
    print(f"To: {hex(to_id)} (Direct)")
    print()
    print("Conditions:")
    print(f"  is_for_me: {is_for_me}")
    print(f"  is_from_me: {is_from_me}")
    print(f"  is_broadcast: {is_broadcast}")
    print(f"  is_broadcast_command: {is_broadcast_command}")
    print()
    
    print("Flux de traitement:")
    
    # Ligne 73
    will_enter_broadcast_block = is_broadcast_command and (is_broadcast or is_for_me) and not is_from_me
    print(f"1. Entre dans bloc broadcast (ligne 73): {will_enter_broadcast_block}")
    
    if not will_enter_broadcast_block:
        # Ligne 98-99: Log
        print(f"2. ✅ Log 'MESSAGE REÇU de ...' (ligne 98)")
        
        # Ligne 102-103: Filtrer si pas pour nous
        will_be_filtered = not is_for_me
        print(f"3. Filtré (ligne 102-103): {will_be_filtered}")
        
        if not will_be_filtered:
            print("4. ✅ Va à _route_command()")
            print("5. ✅ LOG 'Hop: TestUser' dans handle_hop()")
            print("6. ✅ Handler handle_hop() appelé")
            return True
        else:
            print("4. ❌ RETURN - Ne va jamais à _route_command()")
            return False

def compare_broadcast_vs_direct():
    """Comparer le comportement broadcast vs direct"""
    print("\n📊 Comparaison: Broadcast vs Direct\n")
    
    print("┌─────────────────┬────────────────┬──────────────────┐")
    print("│ Mode            │ Broadcast      │ Direct           │")
    print("├─────────────────┼────────────────┼──────────────────┤")
    print("│ is_for_me       │ False          │ True             │")
    print("│ is_broadcast    │ True           │ False            │")
    print("│ is_broadcast_cmd│ False (/hop)   │ False (/hop)     │")
    print("│ Entre bloc 73   │ False          │ False            │")
    print("│ Passe filtre 102│ False (❌)     │ True (✅)        │")
    print("│ Appelle handler │ Non (❌)       │ Oui (✅)         │")
    print("│ Log écrit       │ Non (❌)       │ Oui (✅)         │")
    print("└─────────────────┴────────────────┴──────────────────┘")

def solution():
    """Proposer des solutions"""
    print("\n💡 Solutions possibles:\n")
    
    print("Option 1: Ajouter /hop à broadcast_commands")
    print("  Avantages:")
    print("    - /hop fonctionne en broadcast ET en direct")
    print("    - Cohérent avec /my, /weather, /rain, etc.")
    print("    - Sera toujours loggé")
    print("  Inconvénients:")
    print("    - Nécessite implémenter is_broadcast dans handle_hop")
    print()
    
    print("Option 2: Ajouter un log dans le filtre (ligne 98-100)")
    print("  Avantages:")
    print("    - Logs toutes les commandes, même filtrées")
    print("    - Pas de changement de comportement")
    print("  Inconvénients:")
    print("    - /hop ne fonctionnera toujours pas en broadcast")
    print("    - Logs verbeux si DEBUG_MODE=False")
    print()
    
    print("Recommandation: Option 1 (ajouter à broadcast_commands)")
    print("  Car /hop est un alias de /stats hop qui est informatif")
    print("  et devrait fonctionner comme les autres commandes de stats")

if __name__ == "__main__":
    print("="*70)
    print("ANALYSE: Problème /hop non loggé")
    print("="*70)
    print()
    
    result_broadcast = test_hop_broadcast_filtering()
    result_direct = test_hop_direct()
    compare_broadcast_vs_direct()
    solution()
    
    print("\n" + "="*70)
    print("CONCLUSION:")
    if not result_broadcast and result_direct:
        print("  /hop fonctionne en mode DIRECT mais PAS en mode BROADCAST")
        print("  En broadcast, /hop est filtré et JAMAIS loggé")
    print("="*70)
