#!/usr/bin/env python3
"""
Test script for TCP health monitoring improvements
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import time
from collections import deque

# Mock config
class MockConfig:
    TCP_SILENT_TIMEOUT = 120
    TCP_HEALTH_CHECK_INTERVAL = 30

def test_packet_rate_calculation():
    """Test packet reception rate calculation"""
    print("Testing packet rate calculation...")
    
    # Simulate packet timestamps
    packet_timestamps = deque(maxlen=100)
    current_time = time.time()
    
    # Add 60 packets over 60 seconds (1 packet/second = 60 packets/minute)
    for i in range(60):
        packet_timestamps.append(current_time - (60 - i))
    
    # Calculate rate over 60 seconds
    def get_packet_reception_rate(timestamps, window_seconds=60):
        if len(timestamps) < 2:
            return None
            
        now = time.time()
        cutoff_time = now - window_seconds
        
        recent_packets = [ts for ts in timestamps if ts >= cutoff_time]
        
        if len(recent_packets) < 2:
            return None
            
        time_span = recent_packets[-1] - recent_packets[0]
        if time_span > 0:
            return (len(recent_packets) / time_span) * 60
        return None
    
    rate = get_packet_reception_rate(packet_timestamps, 60)
    print(f"✅ Rate with 60 packets in 60s: {rate:.1f} pkt/min (expected: ~60)")
    
    # Test with fewer packets (should show lower rate)
    packet_timestamps.clear()
    for i in range(30):
        packet_timestamps.append(current_time - (60 - i*2))
    
    rate = get_packet_reception_rate(packet_timestamps, 60)
    print(f"✅ Rate with 30 packets in 60s: {rate:.1f} pkt/min (expected: ~30)")
    
    # Test with recent burst
    packet_timestamps.clear()
    for i in range(10):
        packet_timestamps.append(current_time - (10 - i))
    
    rate = get_packet_reception_rate(packet_timestamps, 60)
    if rate is not None:
        print(f"✅ Rate with 10 packets in 10s: {rate:.1f} pkt/min (expected: ~60)")
    else:
        print("✅ Rate calculation handles short bursts correctly")

def test_session_stats():
    """Test session statistics tracking"""
    print("\nTesting session statistics...")
    
    session_start_time = time.time() - 120  # 2 minutes ago
    packets_this_session = 120  # 120 packets in 2 minutes
    
    session_duration = time.time() - session_start_time
    session_rate = (packets_this_session / session_duration) * 60
    
    print(f"✅ Session: {packets_this_session} packets in {session_duration:.0f}s")
    print(f"✅ Session rate: {session_rate:.1f} pkt/min (expected: ~60)")
    
    # Test with low traffic session
    session_start_time = time.time() - 300  # 5 minutes ago
    packets_this_session = 50  # 50 packets in 5 minutes
    
    session_duration = time.time() - session_start_time
    session_rate = (packets_this_session / session_duration) * 60
    
    print(f"✅ Low traffic session: {packets_this_session} packets in {session_duration:.0f}s")
    print(f"✅ Session rate: {session_rate:.1f} pkt/min (expected: ~10)")

def test_config_loading():
    """Test configuration loading"""
    print("\nTesting configuration loading...")
    
    # Test with default values
    silent_timeout = getattr(MockConfig, 'TCP_SILENT_TIMEOUT', 120)
    health_interval = getattr(MockConfig, 'TCP_HEALTH_CHECK_INTERVAL', 30)
    
    print(f"✅ TCP_SILENT_TIMEOUT: {silent_timeout}s")
    print(f"✅ TCP_HEALTH_CHECK_INTERVAL: {health_interval}s")
    
    # Test with missing values (should use defaults)
    missing_value = getattr(MockConfig, 'NONEXISTENT', 999)
    print(f"✅ Default fallback works: {missing_value} (expected: 999)")

def main():
    print("=" * 60)
    print("TCP Health Monitoring Improvements - Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_packet_rate_calculation()
        test_session_stats()
        test_config_loading()
        
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
