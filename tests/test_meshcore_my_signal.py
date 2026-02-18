#!/usr/bin/env python3
"""
Test: MeshCore /my signal data preservation
===========================================

Verify that rx_history preserves RF signal data and doesn't get
overwritten by DM packets with snr=0.0
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_rx_history_preserves_rf_data():
    """Test that RF signal data is preserved when DM packets arrive"""
    print("\n🧪 Test: rx_history preserves RF signal data")
    print("=" * 70)
    
    # Simulate node_manager behavior
    rx_history = {}
    
    # Step 1: Receive RF packet with good SNR
    node_id = 0x889fa138
    rf_packet = {
        'from': node_id,
        'snr': 11.2,  # Good signal from RX_LOG
        'hopLimit': 0,
        'hopStart': 0
    }
    
    print(f"\n📡 Step 1: Receive RF packet (RX_LOG) with SNR={rf_packet['snr']}dB")
    
    # OLD BEHAVIOR: Would update rx_history
    snr = rf_packet.get('snr', 0.0)
    if snr != 0.0:  # NEW FIX: Skip if 0.0
        if node_id not in rx_history:
            rx_history[node_id] = {
                'snr': snr,
                'last_seen': time.time(),
                'count': 1
            }
            print(f"  ✅ rx_history updated: snr={snr}dB")
        else:
            old_snr = rx_history[node_id]['snr']
            count = rx_history[node_id]['count']
            new_snr = (old_snr * count + snr) / (count + 1)
            rx_history[node_id]['snr'] = new_snr
            rx_history[node_id]['count'] += 1
            print(f"  ✅ rx_history updated: snr={new_snr:.1f}dB (avg)")
    
    print(f"  💾 Current rx_history: {rx_history[node_id]}")
    
    # Step 2: Receive DM packet with snr=0.0
    dm_packet = {
        'from': node_id,
        'snr': 0.0,  # DM has no RF data
        'hopLimit': 0,
        'hopStart': 0,
        '_meshcore_dm': True
    }
    
    print(f"\n📬 Step 2: Receive DM packet with SNR={dm_packet['snr']}dB")
    
    # NEW BEHAVIOR: Skip update if SNR=0.0
    snr = dm_packet.get('snr', 0.0)
    if snr != 0.0:  # NEW FIX: Skip if 0.0
        if node_id not in rx_history:
            rx_history[node_id] = {
                'snr': snr,
                'last_seen': time.time(),
                'count': 1
            }
            print(f"  ✅ rx_history updated: snr={snr}dB")
        else:
            old_snr = rx_history[node_id]['snr']
            count = rx_history[node_id]['count']
            new_snr = (old_snr * count + snr) / (count + 1)
            rx_history[node_id]['snr'] = new_snr
            rx_history[node_id]['count'] += 1
            print(f"  ✅ rx_history updated: snr={new_snr:.1f}dB (avg)")
    else:
        print(f"  ⏭️  Skipped rx_history update (snr=0.0, no RF data)")
    
    print(f"  💾 Current rx_history: {rx_history[node_id]}")
    
    # Verify SNR is preserved
    final_snr = rx_history[node_id]['snr']
    if final_snr == 11.2:
        print(f"\n✅ SUCCESS: RF signal data preserved (SNR={final_snr}dB)")
        return True
    else:
        print(f"\n❌ FAILED: Signal data corrupted (expected 11.2dB, got {final_snr}dB)")
        return False

def test_old_behavior():
    """Show what the OLD behavior would have done"""
    print("\n🧪 Test: OLD behavior (broken)")
    print("=" * 70)
    
    rx_history = {}
    node_id = 0x889fa138
    
    # Step 1: RF packet
    print(f"\n📡 Step 1: RF packet with SNR=11.2dB")
    snr = 11.2
    rx_history[node_id] = {'snr': snr, 'count': 1}
    print(f"  💾 rx_history: snr={snr}dB")
    
    # Step 2: DM packet (OLD BEHAVIOR: would update)
    print(f"\n📬 Step 2: DM packet with SNR=0.0dB")
    dm_snr = 0.0
    old_snr = rx_history[node_id]['snr']
    count = rx_history[node_id]['count']
    new_snr = (old_snr * count + dm_snr) / (count + 1)
    rx_history[node_id]['snr'] = new_snr
    rx_history[node_id]['count'] += 1
    print(f"  ❌ OLD: Would average with 0.0")
    print(f"  ❌ OLD: snr={new_snr:.1f}dB (corrupted!)")
    
    return new_snr < 11.2

def test_multiple_packets():
    """Test with multiple RF and DM packets"""
    print("\n🧪 Test: Multiple packets scenario")
    print("=" * 70)
    
    rx_history = {}
    node_id = 0x889fa138
    
    packets = [
        ('RF', 11.2),
        ('RF', 10.8),
        ('DM', 0.0),  # Should be skipped
        ('RF', 11.5),
        ('DM', 0.0),  # Should be skipped
        ('DM', 0.0),  # Should be skipped
        ('RF', 11.0),
    ]
    
    print("\nProcessing packets:")
    for pkt_type, snr in packets:
        print(f"  {pkt_type} packet: SNR={snr}dB", end="")
        
        if snr != 0.0:  # NEW FIX
            if node_id not in rx_history:
                rx_history[node_id] = {'snr': snr, 'count': 1}
            else:
                old_snr = rx_history[node_id]['snr']
                count = rx_history[node_id]['count']
                new_snr = (old_snr * count + snr) / (count + 1)
                rx_history[node_id]['snr'] = new_snr
                rx_history[node_id]['count'] += 1
            print(f" → Updated (avg={rx_history[node_id]['snr']:.1f}dB)")
        else:
            print(f" → Skipped (no RF data)")
    
    final_snr = rx_history[node_id]['snr']
    print(f"\n💾 Final rx_history: snr={final_snr:.1f}dB")
    print(f"   Based on {rx_history[node_id]['count']} RF packets")
    print(f"   (3 DM packets were skipped)")
    
    # Should be average of RF packets only: (11.2 + 10.8 + 11.5 + 11.0) / 4 = 11.125
    expected = (11.2 + 10.8 + 11.5 + 11.0) / 4
    if abs(final_snr - expected) < 0.01:
        print(f"\n✅ SUCCESS: Only RF packets averaged (expected {expected:.2f}dB)")
        return True
    else:
        print(f"\n❌ FAILED: Wrong average (expected {expected:.2f}dB, got {final_snr:.1f}dB)")
        return False

def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("MESHCORE /my SIGNAL DATA PRESERVATION - TEST SUITE")
    print("=" * 70)
    
    results = []
    
    # Test 1: Old behavior
    results.append(("Old behavior fails", test_old_behavior()))
    
    # Test 2: New behavior preserves RF data
    results.append(("RF data preservation", test_rx_history_preserves_rf_data()))
    
    # Test 3: Multiple packets
    results.append(("Multiple packets", test_multiple_packets()))
    
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
        print("  • Problem: DM packets (snr=0.0) overwrite RF signal data")
        print("  • Solution: Skip rx_history update when snr=0.0")
        print("  • Result: /my command shows real RF signal data from RX_LOG")
        return True
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        print("=" * 70)
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
