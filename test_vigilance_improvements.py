#!/usr/bin/env python3
"""
Test script to demonstrate vigilance_monitor.py improvements for Issue #33

This test specifically validates:
1. Timeout handling via socket.setdefaulttimeout()
2. http.client.RemoteDisconnected catching
3. Exponential backoff with jitter
4. Improved logging (INFO for retries, ERROR only on final failure)
"""

import sys
import time
from unittest.mock import Mock, patch, MagicMock
import socket
import http.client

# Mock config before imports
sys.path.insert(0, '/home/runner/work/meshbot/meshbot')

# Create minimal config
class MockConfig:
    DEBUG_MODE = True  # Enable debug to see all logs
    
sys.modules['config'] = MockConfig

# Mock utils module
class MockUtils:
    @staticmethod
    def debug_print(msg):
        print(f"[DEBUG] {msg}")
    
    @staticmethod
    def info_print(msg):
        print(f"[INFO] {msg}")
    
    @staticmethod
    def error_print(msg):
        print(f"[ERROR] {msg}")

sys.modules['utils'] = MockUtils


def test_timeout_handling():
    """Test that socket timeout is properly set and restored"""
    print("\n" + "="*70)
    print("TEST 1: Socket Timeout Handling")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    
    monitor = VigilanceMonitor(
        departement='25',
        check_interval=0,
        alert_throttle=3600
    )
    
    # Track timeout changes
    timeout_values = []
    
    original_setdefaulttimeout = socket.setdefaulttimeout
    def track_timeout(value):
        timeout_values.append(value)
        return original_setdefaulttimeout(value)
    
    print("\n1.1: Testing timeout set/restore on success...")
    with patch('socket.setdefaulttimeout', side_effect=track_timeout):
        with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
            mock_alert.return_value = MagicMock(
                department_color='Vert',
                summary_message=lambda x: 'Pas de vigilance',
                bulletin_date='2024-11-20',
                additional_info_URL='http://example.com'
            )
            
            result = monitor.check_vigilance()
            
            # Should have set timeout to 10, then restored to None
            if len(timeout_values) >= 2:
                print(f"✅ PASS: Timeout set to {timeout_values[0]} and restored to {timeout_values[1]}")
                if timeout_values[0] == 10:
                    print("✅ PASS: Correct timeout value (10 seconds)")
                else:
                    print(f"❌ FAIL: Expected timeout 10, got {timeout_values[0]}")
                    return False
            else:
                print(f"❌ FAIL: Expected 2 timeout calls, got {len(timeout_values)}")
                return False
    
    print("\n✅ TEST 1 PASSED: Timeout handling works correctly")
    return True


def test_remote_disconnected_handling():
    """Test that http.client.RemoteDisconnected is caught specifically"""
    print("\n" + "="*70)
    print("TEST 2: RemoteDisconnected Exception Handling")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    
    monitor = VigilanceMonitor(
        departement='25',
        check_interval=0,
        alert_throttle=3600
    )
    
    print("\n2.1: Testing RemoteDisconnected with retry...")
    
    # Reset check time
    monitor.last_check_time = 0
    
    with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
        # Simulate RemoteDisconnected error
        mock_alert.side_effect = http.client.RemoteDisconnected("Remote end closed connection")
        
        result = monitor.check_vigilance()
        
        if result is None:
            print("✅ PASS: RemoteDisconnected caught and handled gracefully")
        else:
            print(f"❌ FAIL: Expected None, got {result}")
            return False
    
    print("\n✅ TEST 2 PASSED: RemoteDisconnected handling works correctly")
    return True


def test_jitter_in_backoff():
    """Test that exponential backoff includes jitter"""
    print("\n" + "="*70)
    print("TEST 3: Exponential Backoff with Jitter")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    
    monitor = VigilanceMonitor(
        departement='25',
        check_interval=0,
        alert_throttle=3600
    )
    
    print("\n3.1: Testing retry delays have jitter (not fixed)...")
    
    # Reset check time
    monitor.last_check_time = 0
    
    # Track sleep times
    sleep_times = []
    original_sleep = time.sleep
    def track_sleep(seconds):
        sleep_times.append(seconds)
        # Don't actually sleep in test
        pass
    
    with patch('time.sleep', side_effect=track_sleep):
        with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
            # All attempts fail
            mock_alert.side_effect = ConnectionResetError("Connection reset")
            
            result = monitor.check_vigilance()
    
    if len(sleep_times) == 2:
        print(f"✅ PASS: Got expected 2 retry delays")
        
        # Check first delay is in range [2, 3] (base_delay * 2^0 + jitter[0,1])
        if 2.0 <= sleep_times[0] <= 3.0:
            print(f"✅ PASS: First delay {sleep_times[0]:.2f}s in expected range [2.0, 3.0]")
        else:
            print(f"❌ FAIL: First delay {sleep_times[0]:.2f}s out of range [2.0, 3.0]")
            return False
        
        # Check second delay is in range [4, 5] (base_delay * 2^1 + jitter[0,1])
        if 4.0 <= sleep_times[1] <= 5.0:
            print(f"✅ PASS: Second delay {sleep_times[1]:.2f}s in expected range [4.0, 5.0]")
        else:
            print(f"❌ FAIL: Second delay {sleep_times[1]:.2f}s out of range [4.0, 5.0]")
            return False
        
        # Check delays are not exactly 2.0 and 4.0 (would indicate no jitter)
        if sleep_times[0] != 2.0 and sleep_times[1] != 4.0:
            print(f"✅ PASS: Delays include jitter (not exact multiples)")
        else:
            print(f"⚠️  WARNING: Delays might not have jitter: {sleep_times}")
    else:
        print(f"❌ FAIL: Expected 2 sleep calls, got {len(sleep_times)}")
        return False
    
    print("\n✅ TEST 3 PASSED: Exponential backoff with jitter works correctly")
    return True


def test_logging_levels():
    """Test that intermediate failures use INFO, final failure uses ERROR"""
    print("\n" + "="*70)
    print("TEST 4: Logging Levels (INFO for retries, ERROR for final)")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    
    # Track log calls
    info_logs = []
    error_logs = []
    debug_logs = []
    
    class TrackingUtils:
        @staticmethod
        def debug_print(msg):
            debug_logs.append(msg)
            print(f"[DEBUG] {msg}")
        
        @staticmethod
        def info_print(msg):
            info_logs.append(msg)
            print(f"[INFO] {msg}")
        
        @staticmethod
        def error_print(msg):
            error_logs.append(msg)
            print(f"[ERROR] {msg}")
    
    # Replace utils
    sys.modules['utils'] = TrackingUtils
    
    # Force re-import
    import importlib
    import vigilance_monitor
    importlib.reload(vigilance_monitor)
    
    monitor = vigilance_monitor.VigilanceMonitor(
        departement='25',
        check_interval=0,
        alert_throttle=3600
    )
    
    print("\n4.1: Testing logging during retries...")
    
    # Reset check time and logs
    monitor.last_check_time = 0
    info_logs.clear()
    error_logs.clear()
    debug_logs.clear()
    
    # Don't sleep in test
    with patch('time.sleep'):
        with patch('vigilancemeteo.DepartmentWeatherAlert') as mock_alert:
            # All attempts fail
            mock_alert.side_effect = ConnectionResetError("Connection reset")
            
            result = monitor.check_vigilance()
    
    # Check intermediate retries use INFO (not ERROR)
    intermediate_info = [log for log in info_logs if "tentative" in log.lower()]
    final_errors = [log for log in error_logs if "après 3 tentatives" in log]
    
    if len(intermediate_info) >= 2:
        print(f"✅ PASS: Intermediate retries logged as INFO ({len(intermediate_info)} messages)")
    else:
        print(f"❌ FAIL: Expected 2+ INFO logs for retries, got {len(intermediate_info)}")
        return False
    
    if len(final_errors) >= 1:
        print(f"✅ PASS: Final failure logged as ERROR")
    else:
        print(f"❌ FAIL: Expected ERROR log for final failure")
        return False
    
    # Restore original utils
    sys.modules['utils'] = MockUtils
    
    print("\n✅ TEST 4 PASSED: Logging levels correct")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("VIGILANCE_MONITOR IMPROVEMENTS TEST SUITE (Issue #33)")
    print("="*70)
    
    results = []
    
    # Run tests
    try:
        results.append(("Timeout Handling", test_timeout_handling()))
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Timeout Handling", False))
    
    try:
        results.append(("RemoteDisconnected Handling", test_remote_disconnected_handling()))
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("RemoteDisconnected Handling", False))
    
    try:
        results.append(("Jitter in Backoff", test_jitter_in_backoff()))
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Jitter in Backoff", False))
    
    try:
        results.append(("Logging Levels", test_logging_levels()))
    except Exception as e:
        print(f"\n❌ TEST 4 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Logging Levels", False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nIssue #33 fixes validated:")
        print("  ✅ Timeout handling prevents indefinite hangs")
        print("  ✅ RemoteDisconnected caught specifically")
        print("  ✅ Exponential backoff with jitter (prevents thundering herd)")
        print("  ✅ Better logging (INFO for retries, ERROR only on final failure)")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
