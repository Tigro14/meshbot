#!/usr/bin/env python3
"""
Test suite for rx_history timestamp fix.

Verifies that last_seen timestamp is ALWAYS updated,
even for packets with snr=0.0 (DM packets).

This ensures /my command shows recent activity instead of stale data.
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_timestamp_updates_with_zero_snr():
    """Test that last_seen updates even when snr=0.0"""
    print("\n" + "="*60)
    print("TEST 1: Timestamp updates with snr=0.0")
    print("="*60)
    
    from node_manager import NodeManager
    
    nm = NodeManager()
    
    # Initial state: Node exists with old timestamp and snr=10.0
    old_time = time.time() - 86400  # 1 day ago
    nm.rx_history[0x889fa138] = {
        'name': 'Node-889fa138',
        'snr': 10.0,
        'last_seen': old_time,
        'count': 5
    }
    
    print(f"Initial state:")
    print(f"  snr: {nm.rx_history[0x889fa138]['snr']}")
    print(f"  last_seen: {nm.rx_history[0x889fa138]['last_seen']}")
    print(f"  age: {time.time() - old_time:.0f} seconds")
    
    # DM packet arrives with snr=0.0
    dm_packet = {
        'from': 0x889fa138,
        'snr': 0.0,
        'rssi': 0,
        'hopLimit': 0,
        'hopStart': 0,
        '_meshcore_dm': True,
        '_meshcore_rx_log': False
    }
    
    print(f"\nDM packet arrives:")
    print(f"  snr: 0.0")
    print(f"  _meshcore_dm: True")
    
    current_time = time.time()
    nm.update_rx_history(dm_packet)
    
    # Check results
    print(f"\nAfter update:")
    print(f"  snr: {nm.rx_history[0x889fa138]['snr']}")
    print(f"  last_seen: {nm.rx_history[0x889fa138]['last_seen']}")
    print(f"  age: {time.time() - nm.rx_history[0x889fa138]['last_seen']:.0f} seconds")
    
    # Verify timestamp was updated
    time_diff = nm.rx_history[0x889fa138]['last_seen'] - current_time
    assert abs(time_diff) < 2, f"Timestamp not updated! diff={time_diff}"
    
    # Verify SNR was NOT updated (still 10.0)
    assert nm.rx_history[0x889fa138]['snr'] == 10.0, \
        f"SNR should not change! Got {nm.rx_history[0x889fa138]['snr']}"
    
    print("✅ PASS: Timestamp updated, SNR preserved")
    return True

def test_new_entry_with_zero_snr():
    """Test that new entries can be created with snr=0.0"""
    print("\n" + "="*60)
    print("TEST 2: New entry creation with snr=0.0")
    print("="*60)
    
    from node_manager import NodeManager
    
    nm = NodeManager()
    
    # DM packet from unknown node
    dm_packet = {
        'from': 0x12345678,
        'snr': 0.0,
        'rssi': 0,
        'hopLimit': 0,
        'hopStart': 0,
        '_meshcore_dm': True,
        '_meshcore_rx_log': False
    }
    
    print(f"DM packet from new node:")
    print(f"  from: 0x12345678")
    print(f"  snr: 0.0")
    
    nm.update_rx_history(dm_packet)
    
    # Check results
    assert 0x12345678 in nm.rx_history, "Entry not created!"
    
    print(f"\nNew entry created:")
    print(f"  snr: {nm.rx_history[0x12345678]['snr']}")
    print(f"  last_seen: {nm.rx_history[0x12345678]['last_seen']}")
    print(f"  count: {nm.rx_history[0x12345678]['count']}")
    
    assert nm.rx_history[0x12345678]['snr'] == 0.0
    assert nm.rx_history[0x12345678]['count'] == 1
    
    print("✅ PASS: New entry created with snr=0.0")
    return True

def test_full_update_with_real_snr():
    """Test that real SNR values still update properly"""
    print("\n" + "="*60)
    print("TEST 3: Full update with real SNR")
    print("="*60)
    
    from node_manager import NodeManager
    
    nm = NodeManager()
    
    # Initial state
    old_time = time.time() - 3600  # 1 hour ago
    nm.rx_history[0x889fa138] = {
        'name': 'Node-889fa138',
        'snr': 10.0,
        'last_seen': old_time,
        'count': 5
    }
    
    print(f"Initial state:")
    print(f"  snr: {nm.rx_history[0x889fa138]['snr']}")
    print(f"  count: {nm.rx_history[0x889fa138]['count']}")
    
    # RX_LOG packet with real SNR
    rx_log_packet = {
        'from': 0x889fa138,
        'snr': 12.0,
        'rssi': -70,
        'hopLimit': 0,
        'hopStart': 3,
        '_meshcore_dm': False,
        '_meshcore_rx_log': True
    }
    
    print(f"\nRX_LOG packet arrives:")
    print(f"  snr: 12.0")
    print(f"  _meshcore_rx_log: True")
    
    nm.update_rx_history(rx_log_packet)
    
    # Check results
    print(f"\nAfter update:")
    print(f"  snr: {nm.rx_history[0x889fa138]['snr']:.2f}")
    print(f"  count: {nm.rx_history[0x889fa138]['count']}")
    
    # Verify SNR was averaged
    expected_snr = (10.0 * 5 + 12.0) / 6
    assert abs(nm.rx_history[0x889fa138]['snr'] - expected_snr) < 0.01, \
        f"SNR not averaged correctly! Expected {expected_snr:.2f}, got {nm.rx_history[0x889fa138]['snr']:.2f}"
    
    # Verify count increased
    assert nm.rx_history[0x889fa138]['count'] == 6
    
    print(f"✅ PASS: SNR averaged to {nm.rx_history[0x889fa138]['snr']:.2f}dB")
    return True

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("RX_HISTORY TIMESTAMP FIX TEST SUITE")
    print("="*60)
    
    tests = [
        test_timestamp_updates_with_zero_snr,
        test_new_entry_with_zero_snr,
        test_full_update_with_real_snr
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED\n")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
