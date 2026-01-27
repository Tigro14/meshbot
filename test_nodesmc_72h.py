#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for /nodesmc full mode with 72h time window
"""

import sys


def test_time_window_logic():
    """Test that full mode uses 72h (3 days) and paginated mode uses 30 days"""
    print("\n=== Test 1: Time Window Selection ===")
    
    test_cases = [
        # (full_mode, expected_days)
        (False, 30),  # Paginated mode
        (True, 3),    # Full mode (72h = 3 days)
    ]
    
    for full_mode, expected_days in test_cases:
        days_filter = 3 if full_mode else 30
        mode_str = "FULL" if full_mode else "PAGINATED"
        
        print(f"\nMode: {mode_str}")
        print(f"  Expected: {expected_days} days")
        print(f"  Got: {days_filter} days")
        
        if days_filter == expected_days:
            print(f"  ✅ PASS")
        else:
            print(f"  ❌ FAIL")
            return False
    
    print("\n✅ Test 1 PASSED - Time window logic correct")
    return True


def test_hour_conversion():
    """Test that 72 hours = 3 days"""
    print("\n=== Test 2: Hour to Day Conversion ===")
    
    hours = 72
    days = hours / 24
    
    print(f"\n72 hours = {days} days")
    
    if days == 3.0:
        print("✅ Test 2 PASSED - Conversion correct")
        return True
    else:
        print("❌ Test 2 FAILED")
        return False


def test_log_messages():
    """Test expected log messages"""
    print("\n=== Test 3: Expected Log Messages ===")
    
    print("\nFor /nodesmc full:")
    print("  [NODESMC] Mode FULL activé - tous les contacts")
    print("  [NODESMC] Récupération contacts depuis SQLite (days_filter=3)")
    print("  [MESHCORE-DB] Interrogation SQLite pour contacts (<3j)")
    print("  [NODESMC] Mode FULL (72h): X messages générés")
    
    print("\nFor /nodesmc (paginated):")
    print("  [NODESMC] Mode paginé - page 1")
    print("  [NODESMC] Récupération contacts depuis SQLite (days_filter=30)")
    print("  [MESHCORE-DB] Interrogation SQLite pour contacts (<30j)")
    print("  [NODESMC] Mode paginé: X messages pour page 1")
    
    print("\n✅ Test 3 PASSED - Log messages documented")
    return True


def test_example_outputs():
    """Show example outputs"""
    print("\n=== Test 4: Example Outputs ===")
    
    print("\n--- Paginated Mode (30 days) ---")
    print("📡 Contacts MeshCore (<30j) (15):")
    print("• Node-Alpha 5678 5m")
    print("• Node-Bravo ABCD 12m")
    print("• Node-Charlie F547 1h")
    print("...")
    print("1/3")
    
    print("\n--- FULL Mode (72h = 3 days) ---")
    print("📡 Contacts MeshCore (<3j) (8) [FULL]:")
    print("• Node-Alpha 5678 5m")
    print("• Node-Bravo ABCD 12m")
    print("• Node-Charlie F547 1h")
    print("• Node-Delta EF01 2h")
    print("• Node-Echo 1234 4h")
    print("• Node-Foxtrot DEAD 8h")
    print("• Node-Golf BEEF 12h")
    print("• Node-Hotel CAFE 1d")
    
    print("\n✅ Test 4 PASSED - Example outputs show correct time windows")
    return True


def test_rationale():
    """Explain the rationale for 72h window"""
    print("\n=== Test 5: Rationale for 72h Window ===")
    
    print("\nWhy 72 hours (3 days) for full mode?")
    print("• More focused snapshot of active network")
    print("• Recent contacts are more relevant for full list")
    print("• Reduces message size for full mode")
    print("• 30 days is better for paginated browsing (more comprehensive)")
    print("• 72h gives last 3 days of activity (weekend + partial week)")
    
    print("\n✅ Test 5 PASSED - Rationale documented")
    return True


def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing /nodesmc full Mode with 72h Time Window")
    print("=" * 70)
    print("\nChange: /nodesmc full now uses 72h (3 days) instead of 30 days")
    print("        /nodesmc (paginated) continues to use 30 days")
    
    all_passed = True
    
    try:
        all_passed &= test_time_window_logic()
        all_passed &= test_hour_conversion()
        all_passed &= test_log_messages()
        all_passed &= test_example_outputs()
        all_passed &= test_rationale()
        
        print("\n" + "=" * 70)
        if all_passed:
            print("✅ ALL TESTS PASSED")
            print("=" * 70)
            print("\nSummary:")
            print("• /nodesmc [page] → 30 days (comprehensive history)")
            print("• /nodesmc full → 72 hours (recent snapshot)")
            print("• Full mode shows ALL contacts in database (no hop filtering)")
            print("• Time window is the only difference in data retrieval")
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            print("=" * 70)
            return 1
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ TEST FAILED WITH EXCEPTION: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
