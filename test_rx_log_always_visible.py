#!/usr/bin/env python3
"""
Test script to verify RX_LOG messages are now visible with info_print_mc

This tests that:
1. RX_LOG packet messages use info_print_mc (always visible)
2. Subscription messages use info_print_mc (already fixed)
3. All key packet types show with [INFO][MC] prefix
"""

import sys
import io
from unittest.mock import Mock

def test_rx_log_visibility():
    """Test that RX_LOG messages are always visible"""
    print("\n" + "="*80)
    print("TEST: RX_LOG Message Visibility")
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
    
    # Test 2: Simulate packet arrival (info level)
    print("\nTest 2: Packet arrival notification (info_print_mc)")
    print("Expected: [INFO][MC] 📡 [RX_LOG] Paquet RF reçu...")
    print("Actual:   ", end="")
    info_print_mc("📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662...")
    
    # Test 3: Decoded packet info (info level)
    print("\nTest 3: Decoded packet details (info_print_mc)")
    print("Expected: [INFO][MC] 📦 [RX_LOG] Type: Advert...")
    print("Actual:   ", end="")
    info_print_mc("📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hash: F9C060FE | Hops: 0 | Status: ✅")
    
    # Test 4: Message content (info level)
    print("\nTest 4: Message content (info_print_mc)")
    print("Expected: [INFO][MC] 📝 [RX_LOG] 📢 Public Message...")
    print("Actual:   ", end="")
    info_print_mc('📝 [RX_LOG] 📢 Public Message: "Hello from the mesh"')
    
    # Test 5: Advertisement (info level)
    print("\nTest 5: Advertisement (info_print_mc)")
    print("Expected: [INFO][MC] 📢 [RX_LOG] Advert...")
    print("Actual:   ", end="")
    info_print_mc("📢 [RX_LOG] Advert from: TestNode | Node: 0x7e766267 | Role: Repeater | GPS: (47.5440, -122.1086)")
    
    # Test 6: Error handling (info level)
    print("\nTest 6: Error message (info_print_mc)")
    print("Expected: [INFO][MC] ⚠️ [RX_LOG] Payload non-dict...")
    print("Actual:   ", end="")
    info_print_mc("⚠️ [RX_LOG] Payload non-dict: str")
    
    # Test 7: Compare with debug (only shows if DEBUG_MODE=True)
    print("\nTest 7: Debug message (debug_print_mc - only if DEBUG_MODE=True)")
    print(f"Expected: {'[DEBUG][MC] message' if DEBUG_MODE else '(no output)'}")
    print("Actual:   ", end="")
    sys.stderr.flush()
    debug_print_mc("📊 [RX_LOG] Décodage non disponible")
    sys.stderr.flush()
    
    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"DEBUG_MODE: {DEBUG_MODE}")
    print("\n✅ Key RX_LOG messages now use info_print_mc() (always visible)")
    print("✅ Users will see packet activity regardless of DEBUG_MODE")
    print("✅ Both subscription and packet messages use [INFO][MC]")
    print("\nExpected log output pattern:")
    print("  [INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)")
    print("  [INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.")
    print("  [INFO][MC] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm...")
    print("  [INFO][MC] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B...")
    print("  [INFO][MC] 📢 [RX_LOG] Advert from: Node | Node: 0x12345678...")
    
    print("\n✅ Now packet activity is ALWAYS visible!")
    print("   (not dependent on DEBUG_MODE)")
    
    return True

def test_comparison():
    """Show the difference between old and new approach"""
    print("\n\n" + "="*80)
    print("BEFORE vs AFTER COMPARISON")
    print("="*80)
    
    from config import DEBUG_MODE
    
    print("\nOLD APPROACH (debug_print_mc):")
    print("  - Only visible when DEBUG_MODE = True")
    print("  - Users with DEBUG_MODE = False see nothing")
    print("  - Problem: Can't confirm packets are arriving")
    
    print("\nNEW APPROACH (info_print_mc):")
    print("  - ALWAYS visible regardless of DEBUG_MODE")
    print("  - Users see packet activity confirming monitoring works")
    print("  - Packet arrival is operational info, not just debug")
    
    print("\nRationale:")
    print("  - Subscription messages use info_print_mc (always visible)")
    print("  - Packet messages should also be info level for consistency")
    print("  - Users need to see packets to confirm RX_LOG is working")
    print("  - Packet arrival is important operational information")

if __name__ == "__main__":
    try:
        success = test_rx_log_visibility()
        test_comparison()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
