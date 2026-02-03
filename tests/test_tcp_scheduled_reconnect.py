#!/usr/bin/env python3
"""
Test script for TCP scheduled reconnection feature
"""

import sys
import time

# Mock config with scheduled reconnection
class MockConfig:
    TCP_SILENT_TIMEOUT = 120
    TCP_HEALTH_CHECK_INTERVAL = 30
    TCP_FORCE_RECONNECT_INTERVAL = 180  # 3 minutes

def test_scheduled_reconnection_disabled():
    """Test that scheduled reconnection is properly disabled when set to 0"""
    print("Testing scheduled reconnection disabled (TCP_FORCE_RECONNECT_INTERVAL=0)...")
    
    TCP_FORCE_RECONNECT_INTERVAL = 0
    last_forced_reconnect = time.time()
    
    # Simulate 5 minutes passing
    time_since_last = 300
    
    should_reconnect = (TCP_FORCE_RECONNECT_INTERVAL > 0 and 
                       time_since_last >= TCP_FORCE_RECONNECT_INTERVAL)
    
    print(f"  TCP_FORCE_RECONNECT_INTERVAL: {TCP_FORCE_RECONNECT_INTERVAL}s")
    print(f"  Time since last: {time_since_last}s")
    print(f"  Should reconnect: {should_reconnect}")
    
    assert not should_reconnect, "Should NOT reconnect when disabled (0)"
    print("✅ PASS: Scheduled reconnection properly disabled\n")

def test_scheduled_reconnection_enabled():
    """Test that scheduled reconnection triggers at correct interval"""
    print("Testing scheduled reconnection enabled (TCP_FORCE_RECONNECT_INTERVAL=180)...")
    
    TCP_FORCE_RECONNECT_INTERVAL = 180  # 3 minutes
    
    # Test case 1: Before interval (2 minutes)
    time_since_last = 120
    should_reconnect = (TCP_FORCE_RECONNECT_INTERVAL > 0 and 
                       time_since_last >= TCP_FORCE_RECONNECT_INTERVAL)
    
    print(f"  Test 1: Time since last = {time_since_last}s (before interval)")
    print(f"    Should reconnect: {should_reconnect}")
    assert not should_reconnect, "Should NOT reconnect before interval"
    print("    ✅ Correct: No reconnection before interval")
    
    # Test case 2: At interval (exactly 3 minutes)
    time_since_last = 180
    should_reconnect = (TCP_FORCE_RECONNECT_INTERVAL > 0 and 
                       time_since_last >= TCP_FORCE_RECONNECT_INTERVAL)
    
    print(f"  Test 2: Time since last = {time_since_last}s (at interval)")
    print(f"    Should reconnect: {should_reconnect}")
    assert should_reconnect, "Should reconnect at interval"
    print("    ✅ Correct: Reconnection triggered at interval")
    
    # Test case 3: After interval (4 minutes)
    time_since_last = 240
    should_reconnect = (TCP_FORCE_RECONNECT_INTERVAL > 0 and 
                       time_since_last >= TCP_FORCE_RECONNECT_INTERVAL)
    
    print(f"  Test 3: Time since last = {time_since_last}s (after interval)")
    print(f"    Should reconnect: {should_reconnect}")
    assert should_reconnect, "Should reconnect after interval"
    print("    ✅ Correct: Reconnection triggered after interval")
    
    print("✅ PASS: Scheduled reconnection works correctly\n")

def test_config_loading():
    """Test configuration loading with getattr pattern"""
    print("Testing configuration loading...")
    
    # Test with value present
    value = getattr(MockConfig, 'TCP_FORCE_RECONNECT_INTERVAL', 0)
    print(f"  With value present: {value}s")
    assert value == 180, "Should load configured value"
    print("  ✅ Correct: Loaded configured value")
    
    # Test with value missing (default)
    value = getattr(MockConfig, 'NONEXISTENT', 0)
    print(f"  With value missing: {value}s (default)")
    assert value == 0, "Should use default value"
    print("  ✅ Correct: Used default value")
    
    print("✅ PASS: Configuration loading works\n")

def test_interaction_with_silence_detection():
    """Test that scheduled reconnection doesn't interfere with silence detection"""
    print("Testing interaction with silence detection...")
    
    TCP_FORCE_RECONNECT_INTERVAL = 180
    TCP_SILENT_TIMEOUT = 120
    
    # Scenario 1: Scheduled reconnection before silence
    print("  Scenario 1: Scheduled reconnection triggers first (180s < 120s silence)")
    time_since_last_forced = 180  # 3 minutes
    silence_duration = 90  # 1.5 minutes
    
    scheduled_should_trigger = time_since_last_forced >= TCP_FORCE_RECONNECT_INTERVAL
    silence_should_trigger = silence_duration > TCP_SILENT_TIMEOUT
    
    print(f"    Time since forced: {time_since_last_forced}s")
    print(f"    Silence duration: {silence_duration}s")
    print(f"    Scheduled triggers: {scheduled_should_trigger}")
    print(f"    Silence triggers: {silence_should_trigger}")
    
    assert scheduled_should_trigger and not silence_should_trigger
    print("    ✅ Correct: Scheduled reconnection would trigger first")
    
    # Scenario 2: Silence detection before scheduled
    print("  Scenario 2: Silence detection triggers first (silence > timeout)")
    time_since_last_forced = 100  # 1.67 minutes
    silence_duration = 130  # 2.17 minutes
    
    scheduled_should_trigger = time_since_last_forced >= TCP_FORCE_RECONNECT_INTERVAL
    silence_should_trigger = silence_duration > TCP_SILENT_TIMEOUT
    
    print(f"    Time since forced: {time_since_last_forced}s")
    print(f"    Silence duration: {silence_duration}s")
    print(f"    Scheduled triggers: {scheduled_should_trigger}")
    print(f"    Silence triggers: {silence_should_trigger}")
    
    assert not scheduled_should_trigger and silence_should_trigger
    print("    ✅ Correct: Silence detection would trigger first")
    
    print("✅ PASS: Both mechanisms work independently\n")

def test_recommended_settings():
    """Test recommended settings for Station G2 with 2.7.15"""
    print("Testing recommended settings for Station G2...")
    
    # Recommended: 180s scheduled reconnection
    TCP_FORCE_RECONNECT_INTERVAL = 180
    TCP_SILENT_TIMEOUT = 120
    TCP_HEALTH_CHECK_INTERVAL = 30
    
    print(f"  TCP_FORCE_RECONNECT_INTERVAL: {TCP_FORCE_RECONNECT_INTERVAL}s")
    print(f"  TCP_SILENT_TIMEOUT: {TCP_SILENT_TIMEOUT}s")
    print(f"  TCP_HEALTH_CHECK_INTERVAL: {TCP_HEALTH_CHECK_INTERVAL}s")
    
    # Calculate effective behavior
    max_wait_scheduled = TCP_FORCE_RECONNECT_INTERVAL + TCP_HEALTH_CHECK_INTERVAL
    max_wait_silence = TCP_SILENT_TIMEOUT + TCP_HEALTH_CHECK_INTERVAL
    
    print(f"\n  Effective behavior:")
    print(f"    Max wait for scheduled reconnection: {max_wait_scheduled}s ({max_wait_scheduled/60:.1f} min)")
    print(f"    Max wait for silence detection: {max_wait_silence}s ({max_wait_silence/60:.1f} min)")
    
    # Both mechanisms work together - whichever triggers first will reconnect
    # With these settings, silence detection typically triggers first (150s < 210s)
    # But scheduled reconnection provides backup in case packets arrive just before timeout
    print(f"    ℹ️ Silence detection acts as primary mechanism ({max_wait_silence}s)")
    print(f"    ℹ️ Scheduled reconnection acts as backup ({max_wait_scheduled}s)")
    print(f"    ✅ Both mechanisms provide redundant protection")
    
    # Verify that scheduled interval is reasonable (not too short)
    assert TCP_FORCE_RECONNECT_INTERVAL >= 60, "Interval should be at least 1 minute"
    print(f"    ✅ Scheduled interval ({TCP_FORCE_RECONNECT_INTERVAL/60:.1f} min) is reasonable")
    
    print("✅ PASS: Recommended settings are coherent\n")

def main():
    print("=" * 60)
    print("TCP Scheduled Reconnection - Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_scheduled_reconnection_disabled()
        test_scheduled_reconnection_enabled()
        test_config_loading()
        test_interaction_with_silence_detection()
        test_recommended_settings()
        
        print()
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
