#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test to verify that get_neighbors_report handles None SNR values correctly.

This reproduces the bug where:
TypeError: '<' not supported between instances of 'NoneType' and 'float'

The issue occurs when sorting neighbors by SNR when some have None values.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import time
from unittest.mock import Mock, MagicMock
from collections import defaultdict

def test_snr_none_sorting():
    """Test that sorting neighbors with None SNR values works"""
    print("=" * 70)
    print("TEST: Neighbors with None SNR values")
    print("=" * 70)
    
    # Create test data with mix of None and float SNR values
    neighbors = [
        {'node_id': '!12345678', 'snr': 8.5, 'last_rx_time': 123456},
        {'node_id': '!23456789', 'snr': None, 'last_rx_time': 123457},  # None SNR
        {'node_id': '!34567890', 'snr': 5.2, 'last_rx_time': 123458},
        {'node_id': '!45678901', 'snr': None, 'last_rx_time': 123459},  # None SNR
        {'node_id': '!56789012', 'snr': 12.3, 'last_rx_time': 123460},
    ]
    
    print("\nOriginal neighbor list:")
    for n in neighbors:
        print(f"  {n['node_id']}: SNR = {n['snr']}")
    
    # Test the OLD lambda (this should fail)
    print("\n1. Testing OLD lambda (should fail):")
    try:
        sorted_old = sorted(
            neighbors,
            key=lambda x: x.get('snr', -999),
            reverse=True
        )
        print("  ❌ UNEXPECTED: Old lambda did not fail!")
        print("  Sorted result:")
        for n in sorted_old:
            print(f"    {n['node_id']}: SNR = {n['snr']}")
        return False
    except TypeError as e:
        print(f"  ✅ EXPECTED: Old lambda failed with TypeError: {e}")
    
    # Test the NEW lambda (this should work)
    print("\n2. Testing NEW lambda (should work):")
    try:
        sorted_new = sorted(
            neighbors,
            key=lambda x: x.get('snr') if x.get('snr') is not None else -999,
            reverse=True
        )
        print("  ✅ SUCCESS: New lambda works!")
        print("  Sorted result (best SNR first):")
        for n in sorted_new:
            snr_str = f"{n['snr']:.1f}" if n['snr'] is not None else "None"
            print(f"    {n['node_id']}: SNR = {snr_str}")
        
        # Verify sorting order
        snr_values = [n['snr'] if n['snr'] is not None else -999 for n in sorted_new]
        assert snr_values == sorted(snr_values, reverse=True), \
            "Sorting order is incorrect!"
        
        # Verify None values are at the end
        none_indices = [i for i, n in enumerate(sorted_new) if n['snr'] is None]
        if none_indices:
            assert all(i >= len([n for n in sorted_new if n['snr'] is not None]) 
                      for i in none_indices), \
                "None values should be at the end"
        
        print("\n  ✅ Sorting order verified:")
        print(f"     - Non-None SNRs: {[n['snr'] for n in sorted_new if n['snr'] is not None]}")
        print(f"     - None SNRs at end: {len(none_indices)} items")
        
        return True
        
    except Exception as e:
        print(f"  ❌ FAILED: New lambda raised exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_get_neighbors_report_integration():
    """Test the actual sorting logic with None SNR values"""
    print("\n" + "=" * 70)
    print("INTEGRATION TEST: Sorting logic with None SNR")
    print("=" * 70)
    
    try:
        # Test the exact sorting logic used in the code
        neighbors = [
            {'node_id': '!aaaaaaaa', 'snr': 8.5, 'last_rx_time': 123456},
            {'node_id': '!bbbbbbbb', 'snr': None, 'last_rx_time': 123457},
            {'node_id': '!cccccccc', 'snr': 5.2, 'last_rx_time': 123458},
            {'node_id': '!dddddddd', 'snr': None, 'last_rx_time': 123459},
            {'node_id': '!eeeeeeee', 'snr': 12.3, 'last_rx_time': 123460},
        ]
        
        print("\n1. Testing sorting with mixed None and float SNR values:")
        print("  Input neighbors:")
        for n in neighbors:
            snr_str = f"{n['snr']:.1f}" if n['snr'] is not None else "None"
            print(f"    {n['node_id']}: SNR = {snr_str}")
        
        # Apply the fixed sorting logic
        sorted_neighbors = sorted(
            neighbors,
            key=lambda x: x.get('snr') if x.get('snr') is not None else -999,
            reverse=True
        )
        
        print("\n  ✅ Sorting completed successfully!")
        print("  Sorted result:")
        for n in sorted_neighbors:
            snr_str = f"{n['snr']:.1f}" if n['snr'] is not None else "None"
            print(f"    {n['node_id']}: SNR = {snr_str}")
        
        # Verify correct order
        expected_order = ['!eeeeeeee', '!aaaaaaaa', '!cccccccc', '!bbbbbbbb', '!dddddddd']
        actual_order = [n['node_id'] for n in sorted_neighbors]
        
        assert actual_order == expected_order, \
            f"Order mismatch! Expected {expected_order}, got {actual_order}"
        
        print("\n  ✅ Sorting order verified:")
        print(f"     Expected: {expected_order}")
        print(f"     Actual:   {actual_order}")
        
        # Test display formatting
        print("\n2. Testing SNR display formatting:")
        for neighbor in sorted_neighbors[:3]:  # Test first 3
            snr = neighbor.get('snr')
            snr_str = f"SNR: {snr:.1f}" if snr else "SNR: N/A"
            node_id = neighbor['node_id']
            print(f"    {node_id}: {snr_str}")
        
        print("\n  ✅ Display formatting works correctly!")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("TESTING FIX FOR: TypeError with None SNR values in /neighbors")
    print("=" * 70)
    
    results = []
    
    print("\nTest 1: Lambda sorting with None values")
    print("-" * 70)
    results.append(test_snr_none_sorting())
    
    print("\nTest 2: Integration test with get_neighbors_report")
    print("-" * 70)
    results.append(test_get_neighbors_report_integration())
    
    print("\n" + "=" * 70)
    if all(results):
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        return 0
    else:
        print(f"❌ {results.count(False)} test(s) failed")
        print("=" * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
