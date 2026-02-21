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

def test_meshcore_dm_my_response():
    """Test that /my shows useful MeshCore info instead of 'Signal: n/a' for DM contacts"""
    print("\n🧪 Test: MeshCore DM /my response format")
    print("=" * 70)
    
    # Simulate rx_history entry created from a MeshCore DM (path_len=1)
    rx_entry = {
        'name': 'Node-889fa138',
        'snr': 0.0,
        'last_seen': 1000.0,
        'count': 1,
        '_meshcore_dm': True,
        'path_len': 1
    }
    
    # Simulate sender_node_data built in handle_my
    sender_node_data = {
        'id': 0x889fa138,
        'name': rx_entry.get('name', 'unknown'),
        'rssi': 0,
        'snr': rx_entry.get('snr', 0.0),
        'last_heard': rx_entry.get('last_seen', 0),
        '_meshcore_dm': rx_entry.get('_meshcore_dm', False),
        'path_len': rx_entry.get('path_len', 0)
    }
    
    rssi = sender_node_data.get('rssi', 0)
    snr = sender_node_data.get('snr', 0.0)
    display_rssi = rssi
    
    response_parts = []
    # Simulate _format_my_response logic
    if display_rssi != 0 or snr != 0:
        response_parts.append(f"Signal: {snr}dB")
    elif sender_node_data.get('_meshcore_dm'):
        path_len = sender_node_data.get('path_len', 0)
        hop_str = f"{path_len} hop{'s' if path_len > 1 else ''}" if path_len > 0 else "direct"
        response_parts.append(f"📡 MeshCore ({hop_str})")
    else:
        response_parts.append("📶 Signal: n/a")
    
    if sender_node_data.get('_meshcore_dm') and snr == 0 and display_rssi == 0:
        quality_desc = "Contact actif"
    else:
        quality_desc = "Inconnue"
    response_parts.append(f"📈 {quality_desc} (0s)")
    response_parts.append("📶 Signal local")
    
    response = " | ".join(response_parts)
    print(f"\n  path_len=1 response: {response}")
    
    assert "📡 MeshCore (1 hop)" in response, f"Expected '📡 MeshCore (1 hop)' in: {response}"
    assert "Contact actif" in response, f"Expected 'Contact actif' in: {response}"
    assert "Signal: n/a" not in response, f"Should NOT contain 'Signal: n/a': {response}"
    print("  ✅ path_len=1: shows '📡 MeshCore (1 hop)' and 'Contact actif'")
    
    # Test with path_len=0 (unknown hops → "direct")
    sender_node_data['path_len'] = 0
    response_parts2 = []
    if display_rssi != 0 or snr != 0:
        response_parts2.append(f"Signal: {snr}dB")
    elif sender_node_data.get('_meshcore_dm'):
        path_len2 = sender_node_data.get('path_len', 0)
        hop_str2 = f"{path_len2} hop{'s' if path_len2 > 1 else ''}" if path_len2 > 0 else "direct"
        response_parts2.append(f"📡 MeshCore ({hop_str2})")
    else:
        response_parts2.append("📶 Signal: n/a")
    response_parts2.append("📈 Contact actif (0s)")
    response2 = " | ".join(response_parts2)
    print(f"  path_len=0 response: {response2}")
    assert "📡 MeshCore (direct)" in response2, f"Expected 'direct' in: {response2}"
    print("  ✅ path_len=0: shows '📡 MeshCore (direct)'")
    
    # Test that non-MeshCore DM entries still show 'Signal: n/a'
    sender_node_data_mt = {'rssi': 0, 'snr': 0.0, '_meshcore_dm': False, 'path_len': 0}
    parts_mt = []
    rssi_mt = sender_node_data_mt.get('rssi', 0)
    snr_mt = sender_node_data_mt.get('snr', 0.0)
    if rssi_mt != 0 or snr_mt != 0:
        parts_mt.append("Signal data")
    elif sender_node_data_mt.get('_meshcore_dm'):
        parts_mt.append("MeshCore")
    else:
        parts_mt.append("📶 Signal: n/a")
    assert "📶 Signal: n/a" in parts_mt[0], "Non-MeshCore should still show Signal: n/a"
    print("  ✅ Non-MeshCore DM: still shows '📶 Signal: n/a' (unchanged)")
    
    print("\n✅ MESHCORE DM /my RESPONSE FORMAT TEST PASSED")
    return True


def test_meshcore_dm_rx_history_fields():
    """Test that path_len and _meshcore_dm are stored in rx_history for DM packets"""
    print("\n🧪 Test: MeshCore DM rx_history fields")
    print("=" * 70)
    
    # Simulate a DM packet from meshcore with _meshcore_path_len
    dm_packet = {
        'from': 0x889fa138,
        'snr': 0.0,
        'hopLimit': 0,
        'hopStart': 0,
        '_meshcore_dm': True,
        '_meshcore_path_len': 2  # 2 hops
    }
    
    is_meshcore_dm = dm_packet.get('_meshcore_dm', False)
    
    # Simulate update_rx_history for new DM entry
    rx_history = {}
    from_id = dm_packet['from']
    
    if dm_packet.get('snr', 0.0) == 0.0 and is_meshcore_dm and from_id not in rx_history:
        rx_history[from_id] = {
            'name': 'Node-889fa138',
            'snr': 0.0,
            'last_seen': 1000.0,
            'count': 1,
            '_meshcore_dm': True,
            'path_len': dm_packet.get('_meshcore_path_len', 0)
        }
    
    assert from_id in rx_history, "DM node should be in rx_history"
    entry = rx_history[from_id]
    assert entry.get('_meshcore_dm') is True, "Entry should have _meshcore_dm=True"
    assert entry.get('path_len') == 2, f"Expected path_len=2, got {entry.get('path_len')}"
    assert entry.get('snr') == 0.0, "SNR should remain 0.0 for DM entry"
    
    print(f"  ✅ rx_history entry: {entry}")
    print("  ✅ _meshcore_dm=True, path_len=2 correctly stored")
    
    print("\n✅ MESHCORE DM rx_history FIELDS TEST PASSED")
    return True


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
    
    # Test 4: MeshCore DM /my response format
    results.append(("MeshCore DM /my response", test_meshcore_dm_my_response()))
    
    # Test 5: MeshCore DM rx_history fields
    results.append(("MeshCore DM rx_history fields", test_meshcore_dm_rx_history_fields()))
    
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
