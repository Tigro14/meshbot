#!/usr/bin/env python3
"""
Test: MeshCore RX_LOG packets update rx_history
================================================

Verify that RX_LOG packets with real SNR data update rx_history,
while DM packets with snr=0.0 are skipped.
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_dm_packet_skipped():
    """Test that DM packets with snr=0.0 are skipped"""
    print("\n🧪 Test 1: DM packets should be skipped")
    print("=" * 70)
    
    from node_manager import NodeManager
    
    node_mgr = NodeManager()
    node_mgr.rx_history = {}  # Clear history
    
    # Simulate DM packet (snr=0.0, _meshcore_dm=True)
    dm_packet = {
        'from': 0x889fa138,
        'to': 0xfffffffe,
        'snr': 0.0,
        'hopLimit': 0,
        'hopStart': 0,
        '_meshcore_dm': True
    }
    
    node_mgr.update_rx_history(dm_packet)
    
    # Check that rx_history was NOT updated
    if 0x889fa138 not in node_mgr.rx_history:
        print("  ✅ DM packet correctly skipped (not in rx_history)")
        return True
    else:
        print("  ❌ DM packet was incorrectly added to rx_history")
        return False

def test_rx_log_with_real_snr():
    """Test that RX_LOG packets with real SNR update rx_history"""
    print("\n🧪 Test 2: RX_LOG packets with real SNR should update rx_history")
    print("=" * 70)
    
    from node_manager import NodeManager
    
    node_mgr = NodeManager()
    node_mgr.rx_history = {}  # Clear history
    
    # Simulate RX_LOG packet with real SNR
    rx_log_packet = {
        'from': 0x889fa138,
        'to': 0xfffffffe,
        'snr': 11.2,
        'rssi': -75,
        'hopLimit': 0,
        'hopStart': 3,
        '_meshcore_rx_log': True
    }
    
    node_mgr.update_rx_history(rx_log_packet)
    
    # Check that rx_history was updated
    if 0x889fa138 in node_mgr.rx_history:
        rx_data = node_mgr.rx_history[0x889fa138]
        print(f"  ✅ RX_LOG packet added to rx_history")
        print(f"     SNR: {rx_data.get('snr', 0)}")
        print(f"     Count: {rx_data.get('count', 0)}")
        print(f"     Last seen: {rx_data.get('last_seen', 0)}")
        
        # Verify SNR is correct
        if rx_data.get('snr', 0) == 11.2:
            print(f"  ✅ SNR correctly stored: 11.2dB")
            return True
        else:
            print(f"  ❌ SNR incorrect: {rx_data.get('snr', 0)}")
            return False
    else:
        print("  ❌ RX_LOG packet was not added to rx_history")
        return False

def test_rx_log_with_zero_snr():
    """Test that RX_LOG packets with snr=0.0 still update rx_history"""
    print("\n🧪 Test 3: RX_LOG packets with snr=0.0 should STILL update rx_history")
    print("=" * 70)
    
    from node_manager import NodeManager
    
    node_mgr = NodeManager()
    node_mgr.rx_history = {}  # Clear history
    
    # Simulate RX_LOG packet with SNR=0.0 (edge case: very weak signal)
    rx_log_packet = {
        'from': 0x889fa138,
        'to': 0xfffffffe,
        'snr': 0.0,
        'rssi': -120,
        'hopLimit': 0,
        'hopStart': 1,
        '_meshcore_rx_log': True  # Key: This is an RX_LOG packet
    }
    
    node_mgr.update_rx_history(rx_log_packet)
    
    # Check that rx_history was updated (special case for RX_LOG)
    if 0x889fa138 in node_mgr.rx_history:
        print("  ✅ RX_LOG packet with SNR=0.0 was added (RX_LOG flag overrides skip)")
        return True
    else:
        print("  ❌ RX_LOG packet with SNR=0.0 was skipped (incorrect)")
        return False

def test_field_name_fix():
    """Test that last_seen field is correctly accessed"""
    print("\n🧪 Test 4: Field name 'last_seen' should be used correctly")
    print("=" * 70)
    
    from node_manager import NodeManager
    
    node_mgr = NodeManager()
    node_mgr.rx_history = {}
    
    # Add a node with last_seen
    rx_log_packet = {
        'from': 0x889fa138,
        'snr': 11.2,
        'hopLimit': 0,
        'hopStart': 3,
        '_meshcore_rx_log': True
    }
    
    node_mgr.update_rx_history(rx_log_packet)
    
    # Check field name
    if 0x889fa138 in node_mgr.rx_history:
        rx_data = node_mgr.rx_history[0x889fa138]
        if 'last_seen' in rx_data:
            print(f"  ✅ Field 'last_seen' exists in rx_history")
            print(f"     Value: {rx_data['last_seen']}")
            
            # Simulate /my command access
            last_heard = rx_data.get('last_seen', 0)  # NEW: Correct field name
            last_heard_old = rx_data.get('last_time', 0)  # OLD: Wrong field name
            
            print(f"\n  Field access comparison:")
            print(f"     last_seen (correct): {last_heard}")
            print(f"     last_time (old bug): {last_heard_old}")
            
            if last_heard > 0 and last_heard_old == 0:
                print(f"  ✅ Field name fix verified")
                return True
            else:
                print(f"  ❌ Field access issue")
                return False
        else:
            print(f"  ❌ Field 'last_seen' not in rx_history")
            return False
    else:
        print("  ❌ Node not in rx_history")
        return False

def test_sequence_dm_then_rx_log():
    """Test realistic sequence: DM arrives first, then RX_LOG"""
    print("\n🧪 Test 5: Realistic sequence - DM first, then RX_LOG")
    print("=" * 70)
    
    from node_manager import NodeManager
    
    node_mgr = NodeManager()
    node_mgr.rx_history = {}
    
    node_id = 0x889fa138
    
    print("\n  Step 1: DM packet arrives (snr=0.0)")
    dm_packet = {
        'from': node_id,
        'snr': 0.0,
        'hopLimit': 0,
        'hopStart': 0,
        '_meshcore_dm': True
    }
    node_mgr.update_rx_history(dm_packet)
    
    if node_id not in node_mgr.rx_history:
        print("    ✅ DM skipped (not in rx_history)")
    else:
        print("    ❌ DM incorrectly added")
        return False
    
    print("\n  Step 2: RX_LOG packet arrives (snr=11.2)")
    rx_log_packet = {
        'from': node_id,
        'snr': 11.2,
        'rssi': -75,
        'hopLimit': 0,
        'hopStart': 3,
        '_meshcore_rx_log': True
    }
    node_mgr.update_rx_history(rx_log_packet)
    
    if node_id in node_mgr.rx_history:
        snr = node_mgr.rx_history[node_id].get('snr', 0)
        print(f"    ✅ RX_LOG added to rx_history (SNR: {snr})")
        
        if snr == 11.2:
            print(f"\n  ✅ Final state correct: Node has real SNR data")
            return True
        else:
            print(f"\n  ❌ SNR incorrect: {snr}")
            return False
    else:
        print("    ❌ RX_LOG not added")
        return False

def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("MESHCORE RX_LOG RX_HISTORY UPDATE - TEST SUITE")
    print("=" * 70)
    
    results = []
    
    # Test 1: DM packets skipped
    results.append(("DM packets skipped", test_dm_packet_skipped()))
    
    # Test 2: RX_LOG with real SNR
    results.append(("RX_LOG real SNR recorded", test_rx_log_with_real_snr()))
    
    # Test 3: RX_LOG with snr=0.0
    results.append(("RX_LOG snr=0.0 recorded", test_rx_log_with_zero_snr()))
    
    # Test 4: Field name fix
    results.append(("Field name 'last_seen'", test_field_name_fix()))
    
    # Test 5: Sequence test
    results.append(("DM then RX_LOG sequence", test_sequence_dm_then_rx_log()))
    
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
        print("\n📋 FIX SUMMARY:")
        print("  1. ✅ DM packets with snr=0.0 are skipped")
        print("  2. ✅ RX_LOG packets always update rx_history")
        print("  3. ✅ RX_LOG with snr=0.0 still updates (edge case)")
        print("  4. ✅ Field name 'last_seen' used correctly")
        print("  5. ✅ Realistic sequence works (DM → RX_LOG)")
        return True
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed}/{total})")
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
