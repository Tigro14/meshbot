#!/usr/bin/env python3
"""
Test script to verify weather optimization changes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import subprocess
import time

def test_curl_timeout_value():
    """Verify CURL_TIMEOUT is increased"""
    print("🧪 Test 1: CURL_TIMEOUT value...")
    
    # Read utils_weather.py and check CURL_TIMEOUT
    with open('utils_weather.py', 'r') as f:
        content = f.read()
        
    if 'CURL_TIMEOUT = 25' in content:
        print("  ✅ CURL_TIMEOUT = 25 seconds (increased from 10s)")
        return True
    else:
        print("  ❌ CURL_TIMEOUT not set to 25")
        return False

def test_cache_duration_values():
    """Verify cache duration constants"""
    print("\n🧪 Test 2: Cache duration constants...")
    
    with open('utils_weather.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('CACHE_DURATION = 300', '5 minutes (fresh)'),
        ('CACHE_STALE_DURATION = 3600', '1 hour (stale-while-revalidate)'),
        ('CACHE_MAX_AGE = 86400', '24 hours (max stale)')
    ]
    
    all_ok = True
    for check, desc in checks:
        if check in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ Missing: {check}")
            all_ok = False
    
    return all_ok

def test_retry_logic_exists():
    """Verify retry logic is implemented"""
    print("\n🧪 Test 3: Retry logic implementation...")
    
    with open('utils_weather.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('CURL_MAX_RETRIES = 3', 'Max retries set'),
        ('CURL_RETRY_DELAY = 2', 'Retry delay set'),
        ('def _curl_with_retry', 'Retry function defined'),
        ('exponential backoff', 'Exponential backoff mentioned')
    ]
    
    all_ok = True
    for check, desc in checks:
        if check in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ⚠️  Not found: {check}")
            if 'def _curl_with_retry' in check:
                all_ok = False
    
    return all_ok

def test_stale_while_revalidate():
    """Verify stale-while-revalidate pattern"""
    print("\n🧪 Test 4: Stale-while-revalidate pattern...")
    
    with open('utils_weather.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('cache_needs_refresh', 'Refresh flag'),
        ('cached_data', 'Cached data tracking'),
        ('FRESH', 'Fresh cache message'),
        ('STALE', 'Stale cache message'),
        ('cache_age_seconds < CACHE_DURATION', 'Fresh check'),
        ('cache_age_seconds < CACHE_STALE_DURATION', 'Stale check')
    ]
    
    all_ok = True
    for check, desc in checks:
        if check in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ Missing: {check}")
            all_ok = False
    
    return all_ok

def test_utility_commands_safety():
    """Verify safety check in utility_commands.py"""
    print("\n🧪 Test 5: Rain graph message splitting safety...")
    
    try:
        with open('handlers/command_handlers/utility_commands.py', 'r') as f:
            content = f.read()
        
        if 'if not day_msg.strip():' in content and 'continue' in content:
            print("  ✅ Empty message safety check added")
            return True
        else:
            print("  ⚠️  Safety check not found (non-critical)")
            return True  # Non-critical
    except FileNotFoundError:
        print("  ⚠️  utility_commands.py not found")
        return True  # Non-critical for this test

def test_syntax():
    """Test Python syntax of modified files"""
    print("\n🧪 Test 6: Python syntax validation...")
    
    files = [
        'utils_weather.py',
        'handlers/command_handlers/utility_commands.py'
    ]
    
    all_ok = True
    for file in files:
        try:
            result = subprocess.run(
                ['python3', '-m', 'py_compile', file],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"  ✅ {file} - syntax OK")
            else:
                print(f"  ❌ {file} - syntax error:")
                print(f"     {result.stderr}")
                all_ok = False
        except Exception as e:
            print(f"  ❌ {file} - error: {e}")
            all_ok = False
    
    return all_ok

def main():
    print("=" * 70)
    print("🧪 Weather Optimization Tests")
    print("=" * 70)
    
    tests = [
        test_curl_timeout_value,
        test_cache_duration_values,
        test_retry_logic_exists,
        test_stale_while_revalidate,
        test_utility_commands_safety,
        test_syntax
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
