#!/usr/bin/env python3
"""
Demo: MC/MT Log Prefix Enhancement
Demonstrates the new log prefixes for MeshCore vs Meshtastic identification
"""

import sys
sys.path.insert(0, '/home/runner/work/meshbot/meshbot')

# Set DEBUG_MODE to True for demo
import config
config.DEBUG_MODE = True

from utils import debug_print, info_print, debug_print_mc, info_print_mc, debug_print_mt, info_print_mt

print("=" * 70)
print("MC/MT Log Prefix Enhancement Demo")
print("=" * 70)
print()

print("1. GENERIC LOGS (No prefix - backward compatible)")
print("-" * 70)
info_print("This is a generic info message")
debug_print("This is a generic debug message")
print()

print("2. MESHCORE LOGS (MC prefix)")
print("-" * 70)
info_print_mc("Library meshcore-cli disponible")
info_print_mc("Device connecté sur /dev/ttyUSB0")
debug_print_mc("PyNaCl disponible (validation clés)")
debug_print_mc("NodeManager configuré")
debug_print_mc("📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm")
debug_print_mc("📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B")
debug_print_mc("📢 [RX_LOG] Advert from: NodeName | Role: Repeater | GPS: (47.5440, -122.1086)")
print()

print("3. MESHTASTIC LOGS (MT prefix)")
print("-" * 70)
info_print_mt("Connexion série établie sur /dev/ttyACM0")
info_print_mt("Port /dev/ttyACM0 disponible après 1.2s")
debug_print_mt("✅ Abonné aux événements Meshtastic")
debug_print_mt("🔌 Meshtastic signale une déconnexion: DEVICE_RESTARTING")
debug_print_mt("Tentative de reconnexion (1/3)...")
print()

print("4. MIXED SCENARIO (Real-world example)")
print("-" * 70)
info_print_mc("Initialisation MeshCore companion mode")
info_print_mt("Connexion série Meshtastic en cours...")
debug_print_mt("✅ Port série ouvert")
debug_print_mc("✅ MeshCore event handler configuré")
debug_print_mc("📡 [RX_LOG] Paquet RF reçu (45B) - SNR:8.5dB RSSI:-78dBm")
debug_print_mc("📝 [RX_LOG] 📢 Public Message: 'Hello mesh network!'")
info_print("Bot démarré avec succès")
print()

print("=" * 70)
print("BENEFITS")
print("=" * 70)
print()
print("✅ Easy to identify MeshCore vs Meshtastic logs")
print("✅ [DEBUG][MC] - MeshCore debug logs")
print("✅ [DEBUG][MT] - Meshtastic debug logs")
print("✅ [INFO][MC] - MeshCore info logs")
print("✅ [INFO][MT] - Meshtastic info logs")
print("✅ Backward compatible - generic logs still work")
print("✅ Better troubleshooting and log analysis")
print()

print("GREP EXAMPLES:")
print("-" * 70)
print("  # All MeshCore logs:")
print("  journalctl -u meshbot | grep '\\[MC\\]'")
print()
print("  # All Meshtastic logs:")
print("  journalctl -u meshbot | grep '\\[MT\\]'")
print()
print("  # MeshCore debug only:")
print("  journalctl -u meshbot | grep '\\[DEBUG\\]\\[MC\\]'")
print()
print("  # Meshtastic info only:")
print("  journalctl -u meshbot | grep '\\[INFO\\]\\[MT\\]'")
print()
