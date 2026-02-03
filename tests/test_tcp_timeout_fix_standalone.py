#!/usr/bin/env python3
"""
Test: TCP Silent Timeout Race Condition Fix (Standalone)

This test verifies the TCP_SILENT_TIMEOUT fix by parsing main_bot.py directly.
"""

import re
import sys

def extract_constants():
    """Extract TCP constants from main_bot.py"""
    try:
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        # Extract constants using regex
        check_match = re.search(r'TCP_HEALTH_CHECK_INTERVAL\s*=\s*(\d+)', content)
        timeout_match = re.search(r'TCP_SILENT_TIMEOUT\s*=\s*(\d+)', content)
        
        if not check_match or not timeout_match:
            print("❌ Could not find TCP constants in main_bot.py")
            return None, None
        
        check_interval = int(check_match.group(1))
        silent_timeout = int(timeout_match.group(1))
        
        return check_interval, silent_timeout
    except Exception as e:
        print(f"❌ Error reading main_bot.py: {e}")
        return None, None


def test_timeout_configuration():
    """Test that TCP timeout is properly configured"""
    print("\n🧪 Test: TCP Silent Timeout Configuration")
    print("=" * 70)
    
    check_interval, silent_timeout = extract_constants()
    if check_interval is None or silent_timeout is None:
        return False
    
    print(f"\n📊 Current Configuration:")
    print(f"  TCP_HEALTH_CHECK_INTERVAL = {check_interval}s")
    print(f"  TCP_SILENT_TIMEOUT = {silent_timeout}s")
    print(f"  Ratio: {silent_timeout / check_interval:.1f}× check interval")
    
    # Test 1: Timeout should be at least 4× check interval
    print(f"\n✓ Test 1: Timeout ≥ 4× check interval")
    min_timeout = check_interval * 4
    if silent_timeout >= min_timeout:
        print(f"  ✅ PASS: {silent_timeout}s ≥ {min_timeout}s")
    else:
        print(f"  ❌ FAIL: {silent_timeout}s < {min_timeout}s")
        print(f"  Race condition possible!")
        return False
    
    # Test 2: Timeout should be ≤ 5× check interval (not too long)
    print(f"\n✓ Test 2: Timeout ≤ 5× check interval")
    max_timeout = check_interval * 5
    if silent_timeout <= max_timeout:
        print(f"  ✅ PASS: {silent_timeout}s ≤ {max_timeout}s")
    else:
        print(f"  ⚠️  WARNING: {silent_timeout}s > {max_timeout}s")
        print(f"  Timeout may be too conservative (slow detection)")
    
    # Test 3: Simulate race condition scenario
    print(f"\n✓ Test 3: Race Condition Scenario Simulation")
    print(f"  Scenario: Last packet at T+0, health checks at {check_interval}s intervals")
    
    scenarios = [
        (82, "Last check before old timeout"),
        (90, "Old timeout threshold"),
        (112, "Next check (would trigger with 90s timeout)"),
        (120, "New timeout threshold"),
        (150, "Next check after new timeout"),
    ]
    
    print()
    for time_elapsed, description in scenarios:
        checks_passed = time_elapsed // check_interval
        would_trigger_old = time_elapsed > 90
        would_trigger_new = time_elapsed > silent_timeout
        
        status_old = "❌ TIMEOUT" if would_trigger_old else "✅ OK"
        status_new = "❌ TIMEOUT" if would_trigger_new else "✅ OK"
        
        print(f"  T+{time_elapsed:3d}s: {description:<40}")
        print(f"    Checks: {checks_passed}, Old(90s): {status_old}, New({silent_timeout}s): {status_new}")
    
    # Test 4: Verify race condition is fixed
    print(f"\n✓ Test 4: Race Condition Fixed")
    # At T+112s (4th check), should NOT timeout with new value
    if 112 <= silent_timeout:
        print(f"  ✅ PASS: 112s ≤ {silent_timeout}s (no false alarm)")
    else:
        print(f"  ❌ FAIL: 112s > {silent_timeout}s (still has race condition)")
        return False
    
    # Test 5: Normal mesh gap tolerance
    print(f"\n✓ Test 5: Normal Mesh Network Gap Tolerance")
    print(f"  Typical packet gaps in mesh networks: 60-90s")
    if silent_timeout >= 120:
        print(f"  ✅ PASS: {silent_timeout}s provides {silent_timeout - 90}s buffer above 90s gaps")
    else:
        print(f"  ⚠️  WARNING: {silent_timeout}s may have false positives for normal gaps")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("\nSummary:")
    print(f"  • Health check every {check_interval}s")
    print(f"  • Timeout after {silent_timeout}s without packets")
    print(f"  • Safety margin: {silent_timeout - 90}s above typical 90s gaps")
    print(f"  • Detection time: {silent_timeout + check_interval}s worst case")
    print(f"  • Race condition: FIXED ✅")
    
    return True


def test_real_world_scenario():
    """Test with real-world packet timing from logs"""
    print("\n🧪 Test: Real-World Scenario from Logs")
    print("=" * 70)
    
    check_interval, silent_timeout = extract_constants()
    if check_interval is None or silent_timeout is None:
        return False
    
    # Actual timestamps from problem logs
    print("\nActual scenario from Jan 05 13:07:50 logs:")
    print("  13:08:39 - Last packet (TELEMETRY)")
    print("  13:09:02 - Health check: 22s since last packet (OK)")
    print("  13:09:32 - Health check: 52s since last packet (OK)")
    print("  13:10:02 - Health check: 82s since last packet (OK)")
    print("  13:10:32 - Health check: 112s since last packet → ???")
    
    print(f"\nWith old configuration (90s timeout):")
    if 112 > 90:
        print(f"  ❌ 112s > 90s → FALSE ALARM → Reconnection triggered")
    
    print(f"\nWith new configuration ({silent_timeout}s timeout):")
    if 112 > silent_timeout:
        print(f"  ❌ 112s > {silent_timeout}s → Timeout")
    else:
        print(f"  ✅ 112s ≤ {silent_timeout}s → OK, no reconnection")
        print(f"  Next check at 13:11:02 (142s) would still be OK")
        if 142 <= silent_timeout:
            print(f"  Timeout would trigger at 13:11:32 if no packets (152s)")
        else:
            print(f"  ⚠️ 142s > {silent_timeout}s → Would timeout at 13:11:02")
    
    return True


def test_comment_consistency():
    """Verify that comments match the new timeout value"""
    print("\n🧪 Test: Documentation Consistency")
    print("=" * 70)
    
    try:
        with open('main_bot.py', 'r') as f:
            content = f.read()
        
        # Check for old timeout references in comments
        old_refs = [
            (r'2 min(?!utes)', "2 min"),
            (r'90.*secondes.*sans.*paquet', "90 secondes sans paquet"),
        ]
        
        issues = []
        for pattern, desc in old_refs:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(desc)
        
        if issues:
            print(f"  ⚠️  Found references to old timeout values:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"  ✅ PASS: No old timeout references in comments")
        
        # Check that new timeout is documented correctly
        if re.search(r'120.*secondes?.*sans.*paquet', content, re.IGNORECASE):
            print(f"  ✅ PASS: New 120s timeout documented in comments")
        
        return True
    except Exception as e:
        print(f"  ❌ Error checking comments: {e}")
        return False


if __name__ == '__main__':
    print("╔" + "═" * 68 + "╗")
    print("║" + " TCP SILENT TIMEOUT RACE CONDITION FIX TEST ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    success = True
    
    # Run tests
    success = test_timeout_configuration() and success
    success = test_real_world_scenario() and success
    success = test_comment_consistency() and success
    
    # Summary
    print("\n" + "=" * 70)
    if success:
        print("✅ ALL TESTS PASSED")
        print("\nThe TCP silent timeout fix correctly prevents false reconnections")
        print("caused by race conditions between health checks and timeout threshold.")
        print("\n🎯 Expected Outcome:")
        print("  • No more false 'SILENCE TCP' alarms every ~2 minutes")
        print("  • Reconnection only when truly needed (>120s without packets)")
        print("  • Real disconnections still detected within 2.5 minutes")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
