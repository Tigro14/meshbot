#!/usr/bin/env python3
"""
Manual test output formatter for /info command
This shows what the output should look like for different scenarios
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_compact_format():
    """Show example compact format output"""
    print("\n" + "="*60)
    print("COMPACT FORMAT (MESH - ≤180 chars)")
    print("="*60)
    
    examples = [
        {
            'name': "Full data",
            'output': "ℹ️ tigrog2 (!f547fabc) | 📍 47.2346,6.8901 | ⛰️ 520m | ↔️ 12.3km | 📶 -87dB SNR8.2 | ⏱️ 2h ago | 📊 1234pkt"
        },
        {
            'name': "No GPS",
            'output': "ℹ️ TestNode (!12345678) | 📍 GPS n/a | 📶 -95dB SNR5.5 | ⏱️ 1h ago | 📊 456pkt"
        },
        {
            'name': "Minimal data",
            'output': "ℹ️ RemoteNode (!abcd1234) | 📍 GPS n/a | ⏱️ 3d ago"
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


def test_detailed_format():
    """Show example detailed format output"""
    print("\n" + "="*60)
    print("DETAILED FORMAT (TELEGRAM/CLI)")
    print("="*60)
    
    detailed_output = """ℹ️ INFORMATIONS NŒUD
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

⏱️ DERNIÈRE RÉCEPTION: il y a 2h

📊 STATISTIQUES MESH
   Paquets totaux: 1234
   Types de paquets:
     • 💬 Messages: 456
     • 📍 Position: 123
     • ℹ️ NodeInfo: 45
     • 📊 Télémétrie: 67
   Télémétrie:
     • Batterie: 85%
     • Voltage: 4.15V
   Premier vu: il y a 7d
   Dernier vu: il y a 2h"""
    
    print(detailed_output)
    print(f"\nLength: {len(detailed_output)} chars")


def test_usage_scenarios():
    """Show different usage scenarios"""
    print("\n" + "="*60)
    print("USAGE SCENARIOS")
    print("="*60)
    
    scenarios = [
        ("By exact name", "/info tigrog2", "Finds node with name 'tigrog2'"),
        ("By partial name", "/info tigro", "Finds node containing 'tigro'"),
        ("By full ID", "/info F547FABC", "Finds node by hex ID"),
        ("By partial ID", "/info F547F", "Finds node by partial hex ID"),
        ("With prefix", "/info !F547FABC", "Handles Meshtastic ID prefix"),
        ("Public broadcast", "/info tigrog2 (broadcast)", "Sends compact response to mesh"),
        ("Private DM", "/info tigrog2 (DM)", "Sends response as private message"),
    ]
    
    for scenario, command, description in scenarios:
        print(f"\n{scenario}:")
        print(f"  Command: {command}")
        print(f"  Result: {description}")


def test_error_scenarios():
    """Show error handling scenarios"""
    print("\n" + "="*60)
    print("ERROR SCENARIOS")
    print("="*60)
    
    errors = [
        {
            'input': "/info",
            'error': "Usage: /info <node_name>",
            'reason': "Missing argument"
        },
        {
            'input': "/info NonExistentNode",
            'error': "❌ Nœud 'NonExistentNode' introuvable",
            'reason': "Node not found"
        },
    ]
    
    for error in errors:
        print(f"\nInput: {error['input']}")
        print(f"  Error: {error['error']}")
        print(f"  Reason: {error['reason']}")


def main():
    """Show all test examples"""
    print("\n" + "="*70)
    print(" "*20 + "/info COMMAND OUTPUT EXAMPLES")
    print("="*70)
    
    test_compact_format()
    test_detailed_format()
    test_usage_scenarios()
    test_error_scenarios()
    
    print("\n" + "="*70)
    print("END OF EXAMPLES")
    print("="*70)


if __name__ == "__main__":
    main()
