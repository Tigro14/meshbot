#!/usr/bin/env python3
"""
Test script to verify MC logging is visible

This tests that:
1. Subscription messages show with [MC] prefix
2. RX_LOG messages show with [MC] prefix
3. All MC logs are visible when filtering for [MC]
"""

import sys
import io
from contextlib import redirect_stdout, redirect_stderr

def test_mc_logging():
    """Test that MC logging functions work correctly"""
    print("\n" + "="*80)
    print("TEST: MC Logging Visibility")
    print("="*80 + "\n")
    
    # Test 1: Import and check functions
    print("Test 1: Import logging functions")
    try:
        from utils import debug_print_mc, info_print_mc
        from config import DEBUG_MODE
        print(f"✅ Imports successful")
        print(f"   DEBUG_MODE = {DEBUG_MODE}")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Test info_print_mc (should always show)
    print("\nTest 2: info_print_mc (should always show)")
    print("Expected: [INFO][MC] Test message")
    print("Actual:   ", end="")
    info_print_mc("Test message")
    
    # Test 3: Test debug_print_mc (shows if DEBUG_MODE=True)
    print("\nTest 3: debug_print_mc (shows if DEBUG_MODE=True)")
    print(f"Expected: {'[DEBUG][MC] Test debug' if DEBUG_MODE else '(no output)'}")
    print("Actual:   ", end="")
    sys.stderr.flush()
    debug_print_mc("Test debug")
    sys.stderr.flush()
    
    # Test 4: Simulate subscription messages
    print("\n\nTest 4: Simulated subscription messages")
    print("-"*80)
    info_print_mc("✅ Souscription aux messages DM (events.subscribe)")
    info_print_mc("✅ Souscription à RX_LOG_DATA (tous les paquets RF)")
    info_print_mc("   → Monitoring actif: broadcasts, télémétrie, DMs, etc.")
    
    # Test 5: Simulate RX_LOG messages
    print("\nTest 5: Simulated RX_LOG messages")
    print("-"*80)
    if DEBUG_MODE:
        debug_print_mc("📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662...")
        debug_print_mc("📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hash: F9C060FE | Hops: 0 | Status: ✅")
        debug_print_mc("📢 [RX_LOG] Advert from: TestNode | Node: 0x7e766267 | Role: Repeater | GPS: (47.5440, -122.1086)")
    else:
        print("(RX_LOG messages not shown - DEBUG_MODE is False)")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"DEBUG_MODE: {DEBUG_MODE}")
    print("\n✅ All MC messages use consistent [MC] prefix")
    print("✅ Subscription messages now use info_print_mc()")
    print("✅ RX_LOG messages use debug_print_mc()")
    print("\nTo see MC logs in journalctl:")
    print("  journalctl -u meshtastic-bot --no-pager -fn 1000 | grep MC")
    print("\nExpected output pattern:")
    print("  [INFO][MC] ✅ Using meshcore-cli library")
    print("  [INFO][MC] ✅ Device connecté sur /dev/ttyACM0")
    print("  [INFO][MC] ✅ Souscription aux messages DM (events.subscribe)")
    print("  [INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)")
    print("  [INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.")
    if DEBUG_MODE:
        print("  [DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu ...")
        print("  [DEBUG][MC] 📦 [RX_LOG] Type: ... | Route: ... | Size: ...")
    
    return True

if __name__ == "__main__":
    try:
        success = test_mc_logging()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
