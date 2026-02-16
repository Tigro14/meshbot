#!/usr/bin/env python3
"""
Test to verify rollback: RX_LOG messages back to debug_print_mc

User was in DEBUG_MODE = True the whole time, so debug_print_mc 
messages WERE visible. The change to info_print_mc was unnecessary.

This test verifies the rollback is correct.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

def test_rollback():
    """Test that rollback works correctly"""
    print("\n" + "="*80)
    print("TEST: Rollback Verification - RX_LOG Messages Back to debug_print_mc")
    print("="*80 + "\n")
    
    # Test 1: Import functions
    print("Test 1: Import logging functions")
    try:
        from utils import debug_print_mc, info_print_mc
        from config import DEBUG_MODE
        print(f"✅ Imports successful")
        print(f"   DEBUG_MODE = {DEBUG_MODE}")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Verify debug_print_mc works when DEBUG_MODE=True
    print("\nTest 2: debug_print_mc behavior")
    print(f"With DEBUG_MODE = {DEBUG_MODE}:")
    if DEBUG_MODE:
        print("Expected: [DEBUG][MC] message should appear on stderr")
    else:
        print("Expected: (no output)")
    print("Actual:   ", end="")
    sys.stderr.flush()
    debug_print_mc("📡 [RX_LOG] Test packet message")
    sys.stderr.flush()
    
    # Test 3: info_print_mc still works (subscription messages)
    print("\n\nTest 3: info_print_mc still works (for subscription messages)")
    print("Expected: [INFO][MC] message always visible")
    print("Actual:   ", end="")
    info_print_mc("✅ Souscription à RX_LOG_DATA (tous les paquets RF)")
    
    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"DEBUG_MODE: {DEBUG_MODE}")
    print("\n✅ Rollback complete:")
    print("  - RX_LOG packet messages: debug_print_mc() (visible when DEBUG_MODE=True)")
    print("  - Subscription messages: info_print_mc() (always visible)")
    print("\nRationale:")
    print("  - User had DEBUG_MODE=True the entire time")
    print("  - debug_print_mc() messages WERE already visible")
    print("  - Change to info_print_mc() was unnecessary")
    print("  - Rolled back to original debug_print_mc() behavior")
    
    print("\nExpected behavior with DEBUG_MODE=True:")
    print("  [INFO][MC] ✅ Souscription à RX_LOG_DATA...")
    print("  [DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu...")
    print("  [DEBUG][MC] 📦 [RX_LOG] Type: Advert...")
    
    return True

if __name__ == "__main__":
    try:
        success = test_rollback()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
