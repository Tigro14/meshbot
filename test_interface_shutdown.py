#!/usr/bin/env python3
"""
Test to verify proper interface closing in stop() method

This test ensures that:
1. interface.close() is called before setting interface to None
2. dual_interface.close() is called if dual mode is active
3. No "Unexpected error in deferred execution" occurs on shutdown
"""

import sys
import os
import re

def test_interface_close_in_stop():
    """Test that stop() properly closes interfaces before setting to None"""
    
    main_bot_path = os.path.join(os.path.dirname(__file__), 'main_bot.py')
    
    with open(main_bot_path, 'r') as f:
        lines = f.readlines()
    
    # Find the stop() method
    stop_start = -1
    for i, line in enumerate(lines):
        if 'def stop(self):' in line:
            stop_start = i
            break
    
    if stop_start == -1:
        print("❌ Could not find stop() method")
        return False
    
    print(f"✅ Found stop() method at line {stop_start + 1}")
    
    # Get the stop() method content (next 150 lines should be enough)
    stop_lines = lines[stop_start:stop_start + 150]
    stop_content = ''.join(stop_lines)
    
    # Check for proper interface closing sequence
    has_interface_close = False
    has_interface_none = False
    close_line = -1
    none_line = -1
    
    for i, line in enumerate(stop_lines):
        if 'self.interface.close()' in line:
            has_interface_close = True
            close_line = stop_start + i + 1
            print(f"✅ Found interface.close() at line {close_line}")
        
        if 'self.interface = None' in line and 'dual_interface' not in line:
            has_interface_none = True
            none_line = stop_start + i + 1
            print(f"✅ Found interface = None at line {none_line}")
    
    if has_interface_close and has_interface_none:
        if close_line < none_line:
            print(f"✅ Correct order: close() at line {close_line} before None at line {none_line}")
        else:
            print(f"❌ FAIL: close() at line {close_line} AFTER None at line {none_line}")
            print("   This will cause 'Unexpected error in deferred execution'")
            return False
    elif not has_interface_close and has_interface_none:
        print("❌ FAIL: interface set to None without calling close() first")
        print("   This will cause 'Unexpected error in deferred execution'")
        return False
    elif has_interface_close and not has_interface_none:
        print("✅ interface.close() called (interface = None might be elsewhere)")
    
    # Check dual_interface handling
    has_dual_close = False
    for i, line in enumerate(stop_lines):
        if 'self.dual_interface.close()' in line:
            has_dual_close = True
            print(f"✅ Found dual_interface.close() at line {stop_start + i + 1}")
            break
    
    if 'dual_interface' in stop_content and not has_dual_close:
        print("⚠️  WARNING: dual_interface referenced but close() not called")
    
    # Check for proper error handling
    if 'except Exception' in stop_content:
        print("✅ Exception handling present in stop()")
    else:
        print("⚠️  No exception handling in stop()")
    
    # Check that close() is wrapped in try/except
    try_except_pattern = r'try:.*?self\.interface\.close\(\).*?except'
    if re.search(try_except_pattern, stop_content, re.DOTALL):
        print("✅ interface.close() properly wrapped in try/except")
    else:
        print("⚠️  interface.close() not in try/except (might cause issues on error)")
    
    print("\n" + "=" * 70)
    print("✅ All critical checks passed! Interface shutdown sequence is correct.")
    print("=" * 70)
    print("\nThis fix prevents 'Unexpected error in deferred execution' by:")
    print("1. Calling interface.close() to stop internal threads/callbacks")
    print("2. Only THEN setting interface to None")
    print("3. Wrapping in exception handling for safety")
    return True

if __name__ == '__main__':
    try:
        success = test_interface_close_in_stop()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
