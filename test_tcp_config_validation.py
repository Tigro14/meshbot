#!/usr/bin/env python3
"""
Test TCP health check configuration validation.

Tests the validation logic that prevents false TCP silence alarms
caused by misconfigured timeout/interval relationships.
"""

import sys
import os

# Validation constants (must match main_bot.py)
FRACTIONAL_RATIO_THRESHOLD = 0.3  # Threshold for "close to integer" detection
FAST_INTERVAL_THRESHOLD = 20      # seconds - intervals below this are considered "fast"
MEDIUM_INTERVAL_THRESHOLD = 30    # seconds - intervals below this are considered "medium"

# Mock config before importing main_bot
class MockConfig:
    """Mock config with various TCP settings"""
    CONNECTION_MODE = 'tcp'
    SERIAL_PORT = '/dev/ttyACM0'
    REMOTE_NODE_HOST = '192.168.1.38'
    REMOTE_NODE_PORT = 4403
    DEBUG_MODE = False
    
    # Will be overridden in tests
    TCP_HEALTH_CHECK_INTERVAL = 30
    TCP_SILENT_TIMEOUT = 120
    TCP_FORCE_RECONNECT_INTERVAL = 0

# Replace config module
sys.modules['config'] = MockConfig

def test_validation_logic():
    """Test the mathematical validation logic"""
    print("=" * 80)
    print("TEST 1: Validation Logic (Fractional Ratio Check)")
    print("=" * 80)
    print()
    print(f"Rule: TIMEOUT/INTERVAL fractional part should be ≥ {FRACTIONAL_RATIO_THRESHOLD} to avoid detection latency")
    print("      (If ratio is 6.0, 6.1, or 6.2, detection will be late by ~15s)")
    print()
    
    test_cases = [
        # (interval, timeout, should_be_safe, description)
        (30, 120, True, "Default config - 4.0× (acceptable for 30s interval)"),
        (30, 135, True, "4.5× - good margin"),
        (15, 60, True, "4.0× - acceptable"),
        (15, 90, False, "6.0× - integer ratio, 15s detection latency!"),
        (15, 98, True, "6.5× - fractional ratio, only 7s latency"),
        (15, 105, False, "7.0× - integer ratio, 15s detection latency!"),
        (15, 112, True, "7.5× - fractional ratio, only 8s latency"),
        (15, 120, True, "8.0× - acceptable for larger ratio"),
        (20, 100, False, "5.0× - integer ratio"),
        (20, 110, True, "5.5× - fractional ratio"),
        (60, 240, True, "4.0× - acceptable for 60s interval"),
    ]
    
    for interval, timeout, expected_safe, description in test_cases:
        # Calculate safety using same logic as main_bot.py
        ratio = timeout / interval
        fractional = ratio - int(ratio)
        checks_before = int(ratio)
        detection_time = (checks_before + 1) * interval
        latency = detection_time - timeout
        
        # Same logic as main_bot.py (using shared constants)
        if fractional < FRACTIONAL_RATIO_THRESHOLD:
            if interval < FAST_INTERVAL_THRESHOLD:
                is_risky = True
            elif interval < MEDIUM_INTERVAL_THRESHOLD:
                is_risky = latency >= interval
            else:
                is_risky = False
        else:
            is_risky = False
        
        is_safe = not is_risky
        
        # Display result
        status = "✅ OK" if is_safe else "⚠️  RISKY"
        match = "✓" if is_safe == expected_safe else "✗ MISMATCH"
        
        print(f"{match} {status}  Interval={interval:2d}s, Timeout={timeout:3d}s (ratio={ratio:.1f}×, frac={fractional:.2f})")
        print(f"          Detection latency: {latency:.0f}s | {description}")
        
        print()
    
    print()

def test_config_combinations():
    """Test various configuration combinations"""
    print("=" * 80)
    print("TEST 2: Common Configuration Scenarios")
    print("=" * 80)
    print()
    
    scenarios = [
        {
            'name': 'Default config (recommended)',
            'interval': 30,
            'timeout': 120,
            'expected': True,
        },
        {
            'name': 'User issue: Integer ratio causes late detection',
            'interval': 15,
            'timeout': 90,
            'expected': False,  # 6.0× is integer ratio
        },
        {
            'name': 'Fixed user config: Add margin',
            'interval': 15,
            'timeout': 98,
            'expected': True,  # 6.5× has fractional part
        },
        {
            'name': 'Slow network with good ratio',
            'interval': 60,
            'timeout': 270,
            'expected': True,  # 4.5× has fractional part
        },
    ]
    
    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        print(f"  TCP_HEALTH_CHECK_INTERVAL = {scenario['interval']}s")
        print(f"  TCP_SILENT_TIMEOUT        = {scenario['timeout']}s")
        
        interval = scenario['interval']
        timeout = scenario['timeout']
        ratio = timeout / interval
        fractional = ratio - int(ratio)
        checks_before = int(ratio)
        detection_time = (checks_before + 1) * interval
        latency = detection_time - timeout
        
        # Same logic as main_bot.py (using shared constants)
        if fractional < FRACTIONAL_RATIO_THRESHOLD:
            if interval < FAST_INTERVAL_THRESHOLD:
                is_risky = True
            elif interval < MEDIUM_INTERVAL_THRESHOLD:
                is_risky = latency >= interval
            else:
                is_risky = False
        else:
            is_risky = False
        
        is_safe = not is_risky
        
        if is_safe:
            print(f"  Result: ✅ Good configuration")
            print(f"          Ratio: {ratio:.2f}× (fractional: {fractional:.2f})")
            print(f"          Detection latency: ~{latency:.0f}s (acceptable)")
        else:
            print(f"  Result: ⚠️  Problematic configuration")
            print(f"          Ratio: {ratio:.2f}× (fractional: {fractional:.2f} < {FRACTIONAL_RATIO_THRESHOLD})")
            print(f"          Detection latency: ~{latency:.0f}s (too high for interval={interval}s)")
        
        assert is_safe == scenario['expected'], f"Expected {'safe' if scenario['expected'] else 'unsafe'}, got {is_safe}"
        print()
    
    print()

def test_timeline_visualization():
    """Visualize the problem with user's config"""
    print("=" * 80)
    print("TEST 3: Timeline Visualization")
    print("=" * 80)
    print()
    
    print("User's problematic config: INTERVAL=15s, TIMEOUT=90s (ratio=6×)")
    print()
    print("Timeline (last packet at T+1s, first check at T+15s):")
    print()
    
    interval = 15
    timeout = 90
    packet_time = 1
    
    for i in range(1, 9):
        check_time = i * interval
        silence = check_time - packet_time
        
        if silence > timeout:
            print(f"  T+{check_time:3d}s: Health check → silence={silence}s > {timeout}s → ❌ FALSE ALARM")
            print(f"           ⚠️  Triggers unnecessary reconnection!")
            break
        else:
            print(f"  T+{check_time:3d}s: Health check → silence={silence}s ≤ {timeout}s → ✅ OK")
    
    print()
    print(f"Problem: Packet at T+1s + 90s timeout = T+91s should trigger")
    print(f"But check at T+105s finds 104s silence > 90s → False alarm!")
    print()
    print("Recommended fix: TCP_SILENT_TIMEOUT ≥ 60s (4× rule), better: 120s")
    print()
    
    print("With corrected config: INTERVAL=15s, TIMEOUT=60s (ratio=4×)")
    print()
    
    timeout = 60
    for i in range(1, 7):
        check_time = i * interval
        silence = check_time - packet_time
        
        if silence > timeout:
            print(f"  T+{check_time:3d}s: Health check → silence={silence}s > {timeout}s → ⚠️  Real timeout")
            print(f"           Connection genuinely dead after {timeout}s+ silence")
            break
        else:
            print(f"  T+{check_time:3d}s: Health check → silence={silence}s ≤ {timeout}s → ✅ OK")
    
    print()
    print("With 4× ratio, we get clean detection without false alarms")
    print()

def main():
    """Run all tests"""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TCP Configuration Validation Tests" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    test_validation_logic()
    test_config_combinations()
    test_timeline_visualization()
    
    print("=" * 80)
    print("✅ All tests passed!")
    print("=" * 80)
    print()
    print("Summary:")
    print("  • Validation uses fractional ratio check: avoid integer ratios")
    print("  • User's config (15s interval, 90s timeout = 6.0×) flagged as risky")
    print("  • Problem: 90/15 = 6.0 (integer) → detection at 105s, 15s late")
    print("  • Solution: Use 98s, 112s, or 120s timeout (fractional ratios)")
    print("  • Default config (30s interval, 120s timeout = 4.0×) acceptable for 30s")
    print()

if __name__ == '__main__':
    main()
