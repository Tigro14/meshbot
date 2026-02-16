#!/usr/bin/env python3
"""
Test script to debug neighbor data extraction from interface.nodes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import sys

def test_interface_nodes_structure():
    """Test what structure interface.nodes actually has"""
    print("Testing neighbor extraction from interface.nodes...")
    
    # Mock interface.nodes structure (based on Meshtastic library)
    # Testing different possible structures
    
    # Test 1: Check if neighborinfo exists at node level
    print("\n=== Test 1: Node with neighborinfo ===")
    mock_node_with_neighbors = {
        'user': {
            'longName': 'TestNode',
            'shortName': 'TEST'
        },
        'neighborinfo': {
            'neighbors': [
                {
                    'node_id': 0x12345678,
                    'snr': 10.5,
                    'last_rx_time': 1234567890,
                    'node_broadcast_interval': 900
                }
            ]
        }
    }
    
    print(f"Node structure: {mock_node_with_neighbors.keys()}")
    if 'neighborinfo' in mock_node_with_neighbors:
        print(f"  ✅ Has neighborinfo")
        print(f"  Neighborinfo keys: {mock_node_with_neighbors['neighborinfo'].keys()}")
        if 'neighbors' in mock_node_with_neighbors['neighborinfo']:
            print(f"  ✅ Has neighbors list: {len(mock_node_with_neighbors['neighborinfo']['neighbors'])} neighbors")
    else:
        print(f"  ❌ No neighborinfo")
    
    # Test 2: Check wait_time impact
    print("\n=== Test 2: Wait Time Impact ===")
    print("Current wait_time in populate_neighbors_from_interface: 10 seconds")
    print("Is 10 seconds enough for TCP interface to load all node data?")
    print("Recommendation: May need to increase wait time or add polling logic")
    
    # Test 3: Check if interface.nodes is populated immediately
    print("\n=== Test 3: Interface Initialization ===")
    print("When does interface.nodes get populated?")
    print("- Serial: Usually fast (< 5 seconds)")
    print("- TCP: May take longer, depends on:")
    print("  * Network latency")
    print("  * Number of nodes in database")
    print("  * ESP32 processing speed")
    print("Recommendation: Add retry logic with longer timeout")

if __name__ == "__main__":
    test_interface_nodes_structure()
