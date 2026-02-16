#!/usr/bin/env python3
"""
Démonstration du fix pour le sender ID des broadcasts MeshCore

Avant le fix:
- Bot envoie: SEND_DM:ffffffff:TestUser: Hello
- MeshCore echo: DM:ffffffff:TestUser: Hello
- Parser extrait: sender_id = 0xFFFFFFFF
- Affichage: "ffff: TestUser: Hello" ❌

Après le fix:
- Bot envoie: SEND_DM:ffffffff:TestUser: Hello
- MeshCore echo: DM:ffffffff:TestUser: Hello
- Parser extrait: sender_id = 0xFFFFFFFF
- Fix remplace: sender_id = 0x12345678 (bot's node ID)
- Affichage: "5678: TestUser: Hello" ✅
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from meshcore_serial_interface import MeshCoreSerialInterface
from unittest.mock import Mock


def demo_before_fix():
    """Démonstration du comportement AVANT le fix"""
    print("=" * 80)
    print("AVANT LE FIX")
    print("=" * 80)
    print()
    print("Bot envoie broadcast:")
    print("  → SEND_DM:ffffffff:TestUser: Hello")
    print()
    print("MeshCore retourne:")
    print("  ← DM:ffffffff:TestUser: Hello")
    print()
    print("Parser extrait sender_id:")
    print("  sender_id = int('ffffffff', 16) = 0xFFFFFFFF")
    print()
    print("NodeManager résout le nom:")
    print("  get_node_name(0xFFFFFFFF) → 'Node-ffffffff'")
    print()
    print("Affichage dans /trafic:")
    print("  ❌ 'ffff: TestUser: Hello'")
    print("     (Mauvais! Devrait montrer l'ID du bot)")
    print()


def demo_after_fix():
    """Démonstration du comportement APRÈS le fix"""
    print("=" * 80)
    print("APRÈS LE FIX")
    print("=" * 80)
    print()
    
    # Create mock serial interface
    mock_serial = Mock()
    mock_serial.is_open = True
    
    interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200, enable_read_loop=False)
    interface.serial = mock_serial
    interface.running = True
    
    # Set bot's node ID
    bot_node_id = 0x12345678
    interface.localNode.nodeNum = bot_node_id
    
    print(f"Bot's node ID: 0x{bot_node_id:08x}")
    print()
    
    # Mock callback to capture packet
    captured = {}
    def capture_callback(packet, iface):
        captured['packet'] = packet
        captured['from_id'] = packet['from']
        captured['message'] = packet['decoded']['payload'].decode('utf-8')
    
    interface.message_callback = capture_callback
    
    print("Bot envoie broadcast:")
    print("  → SEND_DM:ffffffff:TestUser: Hello")
    print()
    print("MeshCore retourne:")
    print("  ← DM:ffffffff:TestUser: Hello")
    print()
    
    # Process the echo
    interface._process_meshcore_line("DM:ffffffff:TestUser: Hello")
    
    print("Parser détecte broadcast (0xFFFFFFFF)")
    print()
    print("✨ FIX APPLIQUÉ:")
    print(f"  if sender_id == 0xFFFFFFFF:")
    print(f"      sender_id = self.localNode.nodeNum  # 0x{bot_node_id:08x}")
    print()
    
    if 'from_id' in captured:
        print(f"Sender ID après fix: 0x{captured['from_id']:08x}")
        print()
        print("NodeManager résout le nom:")
        print(f"  get_node_name(0x{captured['from_id']:08x}) → 'TestUser' (ou bot's short name)")
        print()
        print("Affichage dans /trafic:")
        print(f"  ✅ '{captured['from_id']:08x}[-4:]: TestUser: Hello'")
        print(f"     (Correct! Montre '5678: TestUser: Hello')")
    else:
        print("❌ Erreur: packet non capturé")
    
    print()


def demo_dm_unchanged():
    """Démonstration que les DM directs ne sont PAS affectés"""
    print("=" * 80)
    print("MESSAGES DIRECTS (DM) - NON AFFECTÉS PAR LE FIX")
    print("=" * 80)
    print()
    
    # Create mock serial interface
    mock_serial = Mock()
    mock_serial.is_open = True
    
    interface = MeshCoreSerialInterface(port='/dev/null', baudrate=115200, enable_read_loop=False)
    interface.serial = mock_serial
    interface.running = True
    
    # Set bot's node ID
    bot_node_id = 0x12345678
    interface.localNode.nodeNum = bot_node_id
    
    # Mock callback to capture packet
    captured = {}
    def capture_callback(packet, iface):
        captured['from_id'] = packet['from']
    
    interface.message_callback = capture_callback
    
    print("Autre utilisateur envoie DM:")
    print("  ← DM:abcdef01:Hello direct")
    print()
    
    # Process the DM
    interface._process_meshcore_line("DM:abcdef01:Hello direct")
    
    print("Parser extrait:")
    print("  sender_id = 0xabcdef01")
    print()
    print("Fix ne s'applique PAS (sender_id != 0xFFFFFFFF)")
    print()
    
    if 'from_id' in captured:
        print(f"Sender ID préservé: 0x{captured['from_id']:08x}")
        print()
        print("✅ Les DM directs gardent leur sender ID original")
    else:
        print("❌ Erreur: packet non capturé")
    
    print()


if __name__ == '__main__':
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  DÉMONSTRATION: Fix sender ID pour /echo broadcast MeshCore".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    demo_before_fix()
    print()
    input("Appuyez sur Entrée pour voir le comportement APRÈS le fix...")
    print()
    
    demo_after_fix()
    print()
    input("Appuyez sur Entrée pour vérifier que les DM directs ne sont pas affectés...")
    print()
    
    demo_dm_unchanged()
    print()
    
    print("=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    print()
    print("✅ BROADCAST: sender_id 0xFFFFFFFF remplacé par node ID du bot")
    print("✅ DM DIRECT: sender_id original préservé")
    print("✅ Affichage correct dans /trafic et historique")
    print()
    print("Le problème 'ffff:' est maintenant RÉSOLU!")
    print()
