#!/usr/bin/env python3
"""
Test to verify that Meshtastic traffic logs use [MT] prefix
"""

import sys
import io
from contextlib import redirect_stderr

# Import logging functions
from utils import debug_print_mt, info_print_mt

def test_mt_prefix():
    """Test that MT prefix appears correctly in Meshtastic traffic logs"""
    
    print("Testing Meshtastic Traffic [MT] Prefix")
    print("=" * 60)
    
    # Capture stderr (where debug_print outputs)
    captured_output = io.StringIO()
    
    # Test debug_print_mt
    with redirect_stderr(captured_output):
        debug_print_mt("🔍 Found node 0x16cd7380 in interface.nodes")
        debug_print_mt("📍 Position mise à jour pour 16cd7380: 48.83743, 2.38551")
        debug_print_mt("📍 Position capturée: 16cd7380 -> 48.83743, 2.38551")
        debug_print_mt("📊 Paquet enregistré ([local]): POSITION_APP de Lorux G2🧊")
        debug_print_mt("📦 POSITION_APP de Lorux G2🧊 d7380 [direct] (SNR:-4.2dB)")
        debug_print_mt("🌐 LOCAL POSITION from Lorux G2🧊 (cd7380) | Hops:0/5 | SNR:-4.2dB(🔴)")
        debug_print_mt("  └─ Lat:0.000005° | Lon:0.000000° | Alt:25m | Payload:27B")
    
    # Test info_print_mt
    print()
    info_print_mt("💿 [ROUTE-SAVE] Routage paquet: source=local, type=POSITION_APP")
    
    print()
    output = captured_output.getvalue()
    
    # Verify output contains [DEBUG][MT] prefix
    if "[DEBUG][MT]" in output:
        print("✅ PASS: debug_print_mt() produces [DEBUG][MT] prefix")
    else:
        print("❌ FAIL: [DEBUG][MT] prefix not found in output")
        print("Output:", output[:200])
        return False
    
    # Count occurrences
    mt_count = output.count("[DEBUG][MT]")
    print(f"✅ Found {mt_count} [DEBUG][MT] prefixed messages")
    
    print()
    print("Expected output format:")
    print("  [DEBUG][MT] 🔍 Found node 0x16cd7380 in interface.nodes")
    print("  [DEBUG][MT] 📍 Position mise à jour pour 16cd7380")
    print("  [INFO][MT] 💿 [ROUTE-SAVE] Routage paquet")
    
    return True

if __name__ == "__main__":
    success = test_mt_prefix()
    sys.exit(0 if success else 1)
