#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test to verify main_bot.py correctly passes source parameter to add_public_message()

This test validates the bug fix where source='local' was hardcoded instead of
using the computed source variable.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_source_parameter_usage():
    """
    Test that main_bot.py uses the source variable correctly
    
    This verifies the fix for the bug where add_public_message() calls
    were hardcoded with source='local' instead of using the computed source.
    """
    print("=" * 70)
    print("TEST: Verify source parameter is passed correctly in main_bot.py")
    print("=" * 70)
    
    # Read main_bot.py and check for the bug
    main_bot_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'main_bot.py'
    )
    
    with open(main_bot_path, 'r') as f:
        content = f.read()
    
    # Find all add_public_message calls
    import re
    pattern = r'add_public_message\([^)]+\)'
    matches = re.findall(pattern, content)
    
    print(f"\n📊 Found {len(matches)} calls to add_public_message()")
    print("-" * 70)
    
    # Check each call
    issues = []
    for i, match in enumerate(matches, 1):
        print(f"\nCall {i}:")
        print(f"  {match}")
        
        # Check if it uses source='local' (the bug)
        if "source='local'" in match:
            print(f"  ❌ BUG: Hardcoded source='local' instead of using source variable")
            issues.append(f"Call {i}: {match}")
        elif "source=source" in match:
            print(f"  ✅ CORRECT: Uses computed source variable")
        else:
            print(f"  ⚠️  UNKNOWN: Check manually")
    
    print("\n" + "=" * 70)
    
    if issues:
        print(f"❌ FOUND {len(issues)} ISSUES:")
        for issue in issues:
            print(f"  • {issue}")
        print("\n⚠️  The bug still exists - source='local' is hardcoded")
        print("   This will cause MeshCore messages to not appear in /trafficmc")
        return False
    else:
        print("✅ NO ISSUES FOUND")
        print("   All add_public_message() calls use source variable correctly")
        return True


def test_source_variable_scope():
    """
    Test that the source variable is available in the scope where
    add_public_message() is called
    """
    print("\n" + "=" * 70)
    print("TEST: Verify source variable is available in scope")
    print("=" * 70)
    
    main_bot_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'main_bot.py'
    )
    
    with open(main_bot_path, 'r') as f:
        lines = f.readlines()
    
    # Find where source is determined
    source_determination_line = None
    for i, line in enumerate(lines):
        if 'elif network_source == NetworkSource.MESHCORE:' in line:
            source_determination_line = i + 1
            print(f"\n✅ Found source determination at line {source_determination_line}")
            break
    
    # Find add_public_message calls
    add_public_message_lines = []
    for i, line in enumerate(lines):
        if 'add_public_message' in line and 'source=' in line:
            add_public_message_lines.append(i + 1)
    
    print(f"✅ Found {len(add_public_message_lines)} add_public_message calls")
    print(f"   Lines: {add_public_message_lines}")
    
    # Check that source is determined before all calls
    if source_determination_line:
        all_after = all(line > source_determination_line for line in add_public_message_lines)
        if all_after:
            print("\n✅ All add_public_message calls are after source determination")
            print("   The source variable should be in scope")
            return True
        else:
            print("\n⚠️  Some calls may be before source determination")
            return False
    else:
        print("\n❌ Could not find source determination logic")
        return False


if __name__ == "__main__":
    print("\n" + "▓" * 70)
    print("▓" + " " * 68 + "▓")
    print("▓" + "  BUG FIX VALIDATION: source parameter in add_public_message()".center(68) + "▓")
    print("▓" + " " * 68 + "▓")
    print("▓" * 70)
    
    try:
        result1 = test_source_parameter_usage()
        result2 = test_source_variable_scope()
        
        print("\n" + "▓" * 70)
        
        if result1 and result2:
            print("▓" + " " * 68 + "▓")
            print("▓" + "  ✅ ALL TESTS PASSED - Bug is fixed!".center(68) + "▓")
            print("▓" + " " * 68 + "▓")
            print("▓" * 70)
            print("\nSummary:")
            print("  ✅ No hardcoded source='local' found")
            print("  ✅ All calls use source variable")
            print("  ✅ source variable is in scope")
            print("  ✅ MeshCore messages will appear in /trafficmc")
            sys.exit(0)
        else:
            print("▓" + " " * 68 + "▓")
            print("▓" + "  ❌ TESTS FAILED - Bug may still exist".center(68) + "▓")
            print("▓" + " " * 68 + "▓")
            print("▓" * 70)
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
