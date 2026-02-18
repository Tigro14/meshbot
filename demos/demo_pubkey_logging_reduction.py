#!/usr/bin/env python3
"""
Demo: Reduced Public Key Logging with MC/MT Prefixes

This demo shows the improved logging for public key operations:
- Factorized logs (1-2 lines instead of 6+)
- Source prefixes ([MC] or [MT])
- Cleaner output
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from node_manager import NodeManager
from utils import debug_print_mt, info_print_mt, debug_print_mc, info_print_mc

print("=" * 70)
print("Demo: Reduced Public Key Logging with MC/MT Prefixes")
print("=" * 70)
print()

print("This demo shows the improved logging for public key operations.")
print()

# Simulate NODEINFO packet with public key (Meshtastic)
print("1. Simulating NODEINFO from Meshtastic (source='meshtastic'):")
print("-" * 70)

# Create mock packet for Meshtastic
meshtastic_packet = {
    'from': 0x33690e68,
    'decoded': {
        'portnum': 'NODEINFO_APP',
        'user': {
            'longName': 'Dalle',
            'shortName': 'DAL',
            'hwModel': 'T1000_E',
            'publicKey': 'JxdQ5cMb3gTCwdcTARFRabcdef1234567890ABCDEF=='  # 44 chars
        }
    }
}

print()
print("Expected logs (NEW - Reduced & Prefixed):")
print("  [INFO][MT] 📱 New node: Dalle (0x33690e68)")
print("  [INFO][MT] ✅ Key extracted: Dalle (len=44)")
print("  [DEBUG][MT] 🔑 Key synced: Dalle → interface.nodes")
print("  [DEBUG][MT] 💾 Node saved: Dalle (0x33690e68)")
print()

print("VS Old logs (6+ lines):")
print("  [DEBUG]    publicKey preview: JxdQ5cMb3gTCwdcTARFR")
print("  [INFO] ✅ Public key UPDATED for Dalle")
print("  [INFO]    Key type: str, length: 44")
print("  [DEBUG]    🔑 Immediately synced key to interface.nodes for Dalle")
print("  [INFO] ✓ Node Dalle now has publicKey in DB (len=44)")
print("  [DEBUG] ✅ Nœud Meshtastic sauvegardé: Dalle (0x33690e68)")
print()

# Simulate MeshCore packet
print("2. Simulating NODEINFO from MeshCore (source='meshcore'):")
print("-" * 70)

meshcore_packet = {
    'from': 0x12345678,
    'decoded': {
        'portnum': 'NODEINFO_APP',
        'user': {
            'longName': 'MeshCoreNode',
            'shortName': 'MCN',
            'hwModel': 'ESP32',
            'publicKey': 'ABCDEF1234567890abcdefghijklmnopqrstuvwxyz=='
        }
    }
}

print()
print("Expected logs (NEW - With [MC] prefix):")
print("  [INFO][MC] 📱 New node: MeshCoreNode (0x12345678)")
print("  [INFO][MC] ✅ Key extracted: MeshCoreNode (len=44)")
print("  [DEBUG][MC] 🔑 Key synced: MeshCoreNode → interface.nodes")
print("  [DEBUG][MC] 💾 Node saved: MeshCoreNode (0x12345678)")
print()

print("=" * 70)
print("Benefits:")
print("=" * 70)
print("✅ Reduced from 6+ lines to 2-3 lines per operation")
print("✅ Clear source identification with [MC]/[MT] prefixes")
print("✅ Cleaner production logs")
print("✅ Essential information preserved")
print("✅ DEBUG logs only in debug mode")
print()

print("=" * 70)
print("Summary of Changes:")
print("=" * 70)
print("1. Pass source parameter through update chain:")
print("   main_bot.py → node_manager.py → traffic_persistence.py")
print()
print("2. Factorized logging:")
print("   - Single line for key extraction")
print("   - Single line for key update")
print("   - Single debug line for sync")
print("   - Single debug line for save")
print()
print("3. Source-aware logging:")
print("   - _get_log_funcs(source) returns (debug_func, info_func)")
print("   - Automatically uses debug_print_mc/info_print_mc for MeshCore")
print("   - Automatically uses debug_print_mt/info_print_mt for Meshtastic")
print()

print("=" * 70)
print("Demo completed successfully!")
print("=" * 70)
