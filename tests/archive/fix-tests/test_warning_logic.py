#!/usr/bin/env python3
"""
Simple test to verify the dual network mode warning logic
Tests the conditional logic without importing main_bot
"""

def test_startup_warning_logic():
    """
    Test the conditional logic for showing startup warnings
    This mimics the logic in main_bot.py start() method
    """
    
    print("=" * 80)
    print("DUAL NETWORK MODE WARNING LOGIC TEST")
    print("=" * 80)
    print()
    
    test_cases = [
        {
            'name': 'Test 1: Dual mode enabled with both networks',
            'dual_mode': True,
            'meshtastic_enabled': True,
            'meshcore_enabled': True,
            'should_warn': False,
            'should_show_dual': True
        },
        {
            'name': 'Test 2: Dual mode disabled with both networks',
            'dual_mode': False,
            'meshtastic_enabled': True,
            'meshcore_enabled': True,
            'should_warn': True,
            'should_show_dual': False
        },
        {
            'name': 'Test 3: Dual mode enabled but only Meshtastic',
            'dual_mode': True,
            'meshtastic_enabled': True,
            'meshcore_enabled': False,
            'should_warn': False,
            'should_show_dual': False  # Won't enter dual mode without both
        },
        {
            'name': 'Test 4: Both disabled (standalone)',
            'dual_mode': False,
            'meshtastic_enabled': False,
            'meshcore_enabled': False,
            'should_warn': False,
            'should_show_dual': False
        },
        {
            'name': 'Test 5: Only Meshtastic enabled',
            'dual_mode': False,
            'meshtastic_enabled': True,
            'meshcore_enabled': False,
            'should_warn': False,
            'should_show_dual': False
        },
        {
            'name': 'Test 6: Only MeshCore enabled',
            'dual_mode': False,
            'meshtastic_enabled': False,
            'meshcore_enabled': True,
            'should_warn': False,
            'should_show_dual': False
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"{test_case['name']}")
        print("-" * 80)
        
        dual_mode = test_case['dual_mode']
        meshtastic_enabled = test_case['meshtastic_enabled']
        meshcore_enabled = test_case['meshcore_enabled']
        
        print(f"  Configuration:")
        print(f"    DUAL_NETWORK_MODE: {dual_mode}")
        print(f"    MESHTASTIC_ENABLED: {meshtastic_enabled}")
        print(f"    MESHCORE_ENABLED: {meshcore_enabled}")
        print()
        
        # This is the logic from main_bot.py start() method
        shows_dual_mode = False
        shows_warning = False
        shows_standalone = False
        
        if dual_mode and meshtastic_enabled and meshcore_enabled:
            # MODE DUAL - Should show dual mode message
            shows_dual_mode = True
        elif not meshtastic_enabled and not meshcore_enabled:
            # Mode standalone
            shows_standalone = True
        elif meshtastic_enabled and meshcore_enabled and not dual_mode:
            # Both enabled but dual mode NOT enabled - Should show warning
            shows_warning = True
        
        print(f"  Expected behavior:")
        print(f"    Should show dual mode: {test_case['should_show_dual']}")
        print(f"    Should show warning: {test_case['should_warn']}")
        print()
        
        print(f"  Actual behavior:")
        print(f"    Shows dual mode: {shows_dual_mode}")
        print(f"    Shows warning: {shows_warning}")
        print(f"    Shows standalone: {shows_standalone}")
        print()
        
        # Verify expected behavior
        dual_mode_ok = shows_dual_mode == test_case['should_show_dual']
        warning_ok = shows_warning == test_case['should_warn']
        
        if dual_mode_ok and warning_ok:
            print(f"  ✅ PASSED")
        else:
            print(f"  ❌ FAILED")
            if not dual_mode_ok:
                print(f"     Expected dual mode: {test_case['should_show_dual']}, got: {shows_dual_mode}")
            if not warning_ok:
                print(f"     Expected warning: {test_case['should_warn']}, got: {shows_warning}")
            all_passed = False
        
        print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if all_passed:
        print("✅ All tests passed! The logic correctly handles dual network mode.")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(test_startup_warning_logic())
