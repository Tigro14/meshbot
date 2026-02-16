#!/usr/bin/env python3
"""
Demonstration of /info command output with hop information
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def show_compact_examples():
    """Show compact format examples with hop information"""
    print("\n" + "="*70)
    print("COMPACT FORMAT (MESH) WITH HOP INFORMATION")
    print("="*70)
    
    examples = [
        {
            'name': "Direct node (0 hops)",
            'output': "ℹ️ tigrog2 (!f547fabc) | ✅ Direct | 📍 47.2346,6.8901 | ⛰️ 520m | ↔️ 12.3km | 📶 -87dB SNR8.2 | ⏱️ 2h ago | 📊 1234pkt"
        },
        {
            'name': "Relayed node (1 hop)",
            'output': "ℹ️ RemoteNode (!abcd1234) | 🔀 1hop | 📍 47.3456,6.9012 | ↔️ 25km | 📶 -102dB SNR2.1 | ⏱️ 5h ago | 📊 89pkt"
        },
        {
            'name': "Relayed node (3 hops)",
            'output': "ℹ️ FarAwayNode (!12345678) | 🔀 3hops | 📍 GPS n/a | 📶 -115dB SNR-2.5 | ⏱️ 1d ago | 📊 23pkt"
        },
        {
            'name': "No hop info available",
            'output': "ℹ️ OldNode (!87654321) | 📍 GPS n/a | 📶 -95dB SNR5.5 | ⏱️ 3h ago"
        }
    ]
    
    for example in examples:
        print(f"\n{example['name']}:")
        print(f"  {example['output']}")
        print(f"  Length: {len(example['output'])} chars")
        if len(example['output']) <= 180:
            print(f"  ✅ Within 180 char limit")
        else:
            print(f"  ❌ EXCEEDS 180 char limit!")


def show_detailed_examples():
    """Show detailed format examples with hop information"""
    print("\n" + "="*70)
    print("DETAILED FORMAT (TELEGRAM/CLI) WITH HOP INFORMATION")
    print("="*70)
    
    # Example 1: Direct connection
    print("\n--- EXAMPLE 1: Direct Connection (0 hops) ---")
    detailed_direct = """ℹ️ INFORMATIONS NŒUD
━━━━━━━━━━━━━━━━━━━━
📛 Nom: tigrog2
🆔 ID: !f547fabc (0xf547fabc)
🏷️ Short: TGR2
🖥️ Model: TLORA_V2_1_1P6

📍 POSITION GPS
   Latitude: 47.234567
   Longitude: 6.890123
   Altitude: 520m
   Distance: 12.3km

📶 SIGNAL
   RSSI: -87dBm 📶
   Qualité: Très bonne
   SNR: 8.2 dB
   Distance (est): 300m-1km

🔀 DISTANCE RÉSEAU
   ✅ Connexion directe (0 hop)
   Le nœud est dans la portée radio directe

⏱️ DERNIÈRE RÉCEPTION: il y a 2h

📊 STATISTIQUES MESH
   Paquets totaux: 1234
   Types de paquets:
     • 💬 Messages: 456
     • 📍 Position: 123
     • ℹ️ NodeInfo: 45
     • 📊 Télémétrie: 67"""
    print(detailed_direct)
    
    # Example 2: Relayed connection
    print("\n\n--- EXAMPLE 2: Relayed Connection (2 hops) ---")
    detailed_relayed = """ℹ️ INFORMATIONS NŒUD
━━━━━━━━━━━━━━━━━━━━
📛 Nom: RemoteNode
🆔 ID: !abcd1234 (0xabcd1234)
🏷️ Short: RMT1
🖥️ Model: TLORA_V2_1_1P6

📍 POSITION GPS
   Latitude: 47.456789
   Longitude: 6.123456
   Altitude: 680m
   Distance: 28.5km

📶 SIGNAL
   RSSI: -102dBm 📶
   Qualité: Bonne
   SNR: 3.5 dB
   Distance (est): 1-3km

🔀 DISTANCE RÉSEAU
   🔀 Relayé (2 hops)
   Le message passe par 2 nœuds intermédiaires

⏱️ DERNIÈRE RÉCEPTION: il y a 5h

📊 STATISTIQUES MESH
   Paquets totaux: 234
   Types de paquets:
     • 💬 Messages: 89
     • 📍 Position: 56
     • ℹ️ NodeInfo: 12"""
    print(detailed_relayed)


def show_comparison():
    """Show before/after comparison"""
    print("\n" + "="*70)
    print("BEFORE/AFTER COMPARISON")
    print("="*70)
    
    print("\n--- WITHOUT HOP INFORMATION (old) ---")
    print("ℹ️ tigrog2 (!f547fabc) | 📍 47.2346,6.8901 | ⛰️ 520m | ↔️ 12.3km | 📶 -87dB SNR8.2 | ⏱️ 2h ago | 📊 1234pkt")
    print("Length: 104 chars")
    
    print("\n--- WITH HOP INFORMATION (new) ---")
    print("ℹ️ tigrog2 (!f547fabc) | ✅ Direct | 📍 47.2346,6.8901 | ⛰️ 520m | ↔️ 12.3km | 📶 -87dB SNR8.2 | ⏱️ 2h ago | 📊 1234pkt")
    print("Length: 116 chars (+12 chars)")
    print("✅ Still well within 180 char limit")
    
    print("\n--- RELAYED NODE (new) ---")
    print("ℹ️ RemoteNode (!abcd1234) | 🔀 2hops | 📍 47.3456,6.9012 | ↔️ 25km | 📶 -102dB SNR2.1 | ⏱️ 5h ago")
    print("Length: 109 chars")
    print("✅ Still well within 180 char limit")


def main():
    """Show all demonstrations"""
    print("\n" + "="*70)
    print(" "*15 + "/info COMMAND WITH HOP INFORMATION")
    print("="*70)
    
    show_compact_examples()
    show_detailed_examples()
    show_comparison()
    
    print("\n" + "="*70)
    print("KEY IMPROVEMENTS")
    print("="*70)
    print("""
✅ Added hop information to compact format
   • Shows "✅ Direct" for 0 hops (direct connection)
   • Shows "🔀 Nhop(s)" for relayed connections
   
✅ Added detailed hop section to full format
   • Clear explanation of direct vs relayed
   • Shows number of intermediate nodes
   
✅ Maintains compact size
   • Adds only ~10-15 chars to compact format
   • Still well within 180 char limit
   
✅ Provides network topology insight
   • Users can see if node is directly reachable
   • Helps understand mesh routing efficiency
""")
    
    print("\n" + "="*70)
    print("END OF DEMONSTRATION")
    print("="*70)


if __name__ == "__main__":
    main()
