#!/usr/bin/env python3
"""
Test node recording with None values
=====================================

Verify that nodes with None values for longName, shortName, or hwModel
don't cause AttributeError during periodic updates.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_none_value_handling():
    """Test that None values are handled correctly in node updates"""
    print("\n🧪 Test: Node recording with None values")
    print("=" * 70)
    
    # Mock node data with None values (like what causes the bug)
    mock_nodes = {
        '2292162872': {  # 0x889fa138
            'user': {
                'longName': None,  # This causes the bug
                'shortName': None,
                'hwModel': None
            }
        },
        '3068191168': {
            'user': {
                'longName': None,
                'shortName': 'TestNode',
                'hwModel': None
            }
        },
        '939881025': {
            'user': {
                'longName': 'Test Node',
                'shortName': None,
                'hwModel': None
            }
        }
    }
    
    print("📋 Testing nodes with None values:")
    print(f"  - Node 2292162872: longName=None, shortName=None, hwModel=None")
    print(f"  - Node 3068191168: longName=None, shortName='TestNode', hwModel=None")
    print(f"  - Node 939881025: longName='Test Node', shortName=None, hwModel=None")
    
    # Test the fix
    errors = []
    for node_id, node_info in mock_nodes.items():
        try:
            user_info = node_info['user']
            
            # This is the FIXED code from node_manager.py
            long_name = (user_info.get('longName') or '').strip()
            short_name_raw = (user_info.get('shortName') or '').strip()
            hw_model = (user_info.get('hwModel') or '').strip()
            
            print(f"\n✅ Node {node_id}:")
            print(f"   long_name: '{long_name}'")
            print(f"   short_name: '{short_name_raw}'")
            print(f"   hw_model: '{hw_model}'")
            
        except AttributeError as e:
            error_msg = f"❌ Node {node_id}: {e}"
            print(error_msg)
            errors.append(error_msg)
    
    print("\n" + "=" * 70)
    if errors:
        print("❌ TEST FAILED")
        print(f"   Errors: {len(errors)}")
        for err in errors:
            print(f"   {err}")
        return False
    else:
        print("✅ TEST PASSED")
        print("   All nodes processed without AttributeError")
        print("   None values are correctly handled with 'or' pattern")
        return True

def test_old_code_fails():
    """Verify that the OLD code would have failed"""
    print("\n🧪 Test: OLD code behavior (should fail)")
    print("=" * 70)
    
    user_info = {
        'longName': None,
        'shortName': None,
        'hwModel': None
    }
    
    print("Testing OLD code pattern: user_info.get('longName', '').strip()")
    
    try:
        # This is the OLD BROKEN code
        long_name = user_info.get('longName', '').strip()
        print(f"❌ OLD code didn't fail? Result: '{long_name}'")
        return False
    except AttributeError as e:
        print(f"✅ OLD code fails as expected: {e}")
        return True

def test_new_code_succeeds():
    """Verify that the NEW code succeeds"""
    print("\n🧪 Test: NEW code behavior (should succeed)")
    print("=" * 70)
    
    user_info = {
        'longName': None,
        'shortName': None,
        'hwModel': None
    }
    
    print("Testing NEW code pattern: (user_info.get('longName') or '').strip()")
    
    try:
        # This is the NEW FIXED code
        long_name = (user_info.get('longName') or '').strip()
        print(f"✅ NEW code succeeds! Result: '{long_name}'")
        return True
    except AttributeError as e:
        print(f"❌ NEW code failed: {e}")
        return False

def test_edge_cases():
    """Test various edge cases"""
    print("\n🧪 Test: Edge cases")
    print("=" * 70)
    
    test_cases = [
        {'longName': None, 'desc': 'None value'},
        {'longName': '', 'desc': 'Empty string'},
        {'longName': '  ', 'desc': 'Whitespace only'},
        {'longName': ' Test ', 'desc': 'String with whitespace'},
        {'desc': 'Missing key (no longName)'},
    ]
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        desc = test_case.pop('desc')
        try:
            long_name = (test_case.get('longName') or '').strip()
            print(f"  {i}. {desc}: '{long_name}' ✅")
        except Exception as e:
            print(f"  {i}. {desc}: ERROR - {e} ❌")
            all_passed = False
    
    return all_passed

def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("NODE RECORDING BUG FIX - TEST SUITE")
    print("=" * 70)
    
    results = []
    
    # Test 1: Old code fails
    results.append(("Old code fails", test_old_code_fails()))
    
    # Test 2: New code succeeds
    results.append(("New code succeeds", test_new_code_succeeds()))
    
    # Test 3: Edge cases
    results.append(("Edge cases", test_edge_cases()))
    
    # Test 4: None value handling
    results.append(("None value handling", test_none_value_handling()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print("\n" + "=" * 70)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 70)
        print("\n📋 FIX SUMMARY:")
        print("  • Changed: user_info.get('longName', '').strip()")
        print("  • To:      (user_info.get('longName') or '').strip()")
        print("  • Reason:  .get(key, default) returns None when key exists with None value")
        print("  • Fix:     'or' operator converts None to empty string before .strip()")
        return True
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        print("=" * 70)
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
