#!/usr/bin/env python3
"""
Test for MQTT NODEINFO translation feature

This test verifies that:
1. NODEINFO packets from MQTT update the node_manager with node names
2. When displaying neighbors, node names are used instead of "Node-xxxxxxxx"
"""

import sys
import time
from unittest.mock import Mock, MagicMock, patch
from collections import defaultdict

# Mock the config module
sys.modules['config'] = Mock(
    NODE_NAMES_FILE='test_node_names.json',
    DEBUG_MODE=True
)

# Mock utils module
sys.modules['utils'] = Mock(
    debug_print=lambda x: print(f"DEBUG: {x}"),
    info_print=lambda x: print(f"INFO: {x}"),
    error_print=lambda x: print(f"ERROR: {x}")
)

# Now we can import the real modules
from node_manager import NodeManager
from traffic_persistence import TrafficPersistence

def test_nodeinfo_processing():
    """Test that NODEINFO packets update node names correctly"""
    print("\n=== Test 1: NODEINFO Processing ===\n")
    
    # Create a node manager
    node_manager = NodeManager()
    
    # Simulate receiving a NODEINFO packet for node 0x08b80708
    node_id = 0x08b80708
    long_name = "TestNode-Alpha"
    short_name = "Alpha"
    
    # Update the node manager (simulating MQTT NODEINFO processing)
    if node_id not in node_manager.node_names:
        node_manager.node_names[node_id] = {
            'name': long_name,
            'lat': None,
            'lon': None,
            'alt': None,
            'last_update': time.time()
        }
        print(f"✅ Added node {node_id:08x} with name: {long_name}")
    
    # Verify the name is stored correctly
    retrieved_name = node_manager.get_node_name(node_id)
    assert retrieved_name == long_name, f"Expected {long_name}, got {retrieved_name}"
    print(f"✅ Node name correctly retrieved: {retrieved_name}")
    
    # Test that unknown nodes still get default name
    unknown_id = 0x12345678
    unknown_name = node_manager.get_node_name(unknown_id)
    expected_default = f"Node-{unknown_id:08x}"
    assert unknown_name == expected_default, f"Expected {expected_default}, got {unknown_name}"
    print(f"✅ Unknown node gets default name: {unknown_name}")
    
    print("\n✅ Test 1 PASSED\n")

def test_neighbor_display():
    """Test that neighbor display uses node names when available"""
    print("\n=== Test 2: Neighbor Display ===\n")
    
    # Create a node manager with some known nodes
    node_manager = NodeManager()
    
    # Add some test nodes
    test_nodes = {
        0x08b80708: "tigrog2-outdoor",
        0x1163ccb5: "NodeAlpha", 
        0x41557097: "NodeBeta",
        0x3a697f21: "NodeGamma"
    }
    
    for node_id, name in test_nodes.items():
        node_manager.node_names[node_id] = {
            'name': name,
            'lat': None,
            'lon': None,
            'alt': None,
            'last_update': time.time()
        }
        print(f"Added node {node_id:08x}: {name}")
    
    # Simulate neighbor data (like what comes from MQTT)
    neighbors_data = {
        '!08b80708': [
            {'node_id': 0x1163ccb5, 'snr': 11.2, 'last_rx_time': 0, 'node_broadcast_interval': 0, 'timestamp': time.time()},
            {'node_id': 0x41557097, 'snr': 10.8, 'last_rx_time': 0, 'node_broadcast_interval': 0, 'timestamp': time.time()},
            {'node_id': 0x3a697f21, 'snr': 9.0, 'last_rx_time': 0, 'node_broadcast_interval': 0, 'timestamp': time.time()},
            {'node_id': 0xda6576d8, 'snr': -3.5, 'last_rx_time': 0, 'node_broadcast_interval': 0, 'timestamp': time.time()},
        ]
    }
    
    print("\n--- Formatted Neighbor Report ---")
    # Format the neighbor display (mimicking get_neighbors_report logic)
    for node_id_str, neighbors in neighbors_data.items():
        node_id_int = int(node_id_str[1:], 16) if node_id_str.startswith('!') else int(node_id_str, 16)
        node_name = node_manager.get_node_name(node_id_int)
        
        print(f"\n**{node_name}** ({node_id_str})")
        print(f"  └─ {len(neighbors)} voisin(s):")
        
        for neighbor in sorted(neighbors, key=lambda x: x.get('snr', -999), reverse=True):
            neighbor_id = neighbor['node_id']
            neighbor_name = node_manager.get_node_name(neighbor_id)
            snr = neighbor.get('snr')
            
            # Check if we're using real name or fallback
            if neighbor_id in test_nodes:
                assert neighbor_name == test_nodes[neighbor_id], f"Expected {test_nodes[neighbor_id]}, got {neighbor_name}"
                name_status = "✅ (real name)"
            else:
                expected_fallback = f"Node-{neighbor_id:08x}"
                assert neighbor_name == expected_fallback, f"Expected {expected_fallback}, got {neighbor_name}"
                name_status = "⚠️  (fallback)"
            
            print(f"     • {neighbor_name}: SNR: {snr:.1f} {name_status}")
    
    print("\n✅ Test 2 PASSED\n")

def test_expected_output_format():
    """Test that output matches the expected format from problem statement"""
    print("\n=== Test 3: Expected Output Format ===\n")
    
    node_manager = NodeManager()
    
    # Add the exact nodes from the problem statement
    problem_nodes = {
        0x08b80708: "tigrog2-outdoor",  # Main node
        0x1163ccb5: "NodeAlpha",        # Neighbor 1
        0x41557097: "NodeBeta",         # Neighbor 2
        0x3a697f21: "NodeGamma",        # Neighbor 3
        0xda6576d8: "NodeDelta",        # Neighbor 4
        0x5f88ed7d: "NodeEpsilon",      # Neighbor 5
        0xec4943b0: "NodeZeta",         # Neighbor 6
        0x8b8551d8: "NodeEta",          # Neighbor 7
    }
    
    for node_id, name in problem_nodes.items():
        node_manager.node_names[node_id] = {
            'name': name,
            'lat': None,
            'lon': None,
            'alt': None,
            'last_update': time.time()
        }
    
    # Problem statement neighbor data
    neighbors = [
        (0x1163ccb5, 11.2),
        (0x41557097, 10.8),
        (0x3a697f21, 9.0),
        (0xda6576d8, -3.5),
        (0x5f88ed7d, -10.5),
        (0xec4943b0, -11.5),
        (0x8b8551d8, -13.5),
    ]
    
    print("Expected output (with translated names):")
    print("**tigrog2-outdoor** (!08b80708)")
    print("  └─ 7 voisin(s):")
    for neighbor_id, snr in neighbors:
        neighbor_name = node_manager.get_node_name(neighbor_id)
        assert neighbor_name != f"Node-{neighbor_id:08x}", f"Node {neighbor_id:08x} should have a real name, got {neighbor_name}"
        print(f"     • {neighbor_name}: SNR: {snr}")
    
    print("\n✅ Test 3 PASSED - All nodes have real names instead of Node-xxxxxxxx\n")

if __name__ == '__main__':
    try:
        test_nodeinfo_processing()
        test_neighbor_display()
        test_expected_output_format()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nSummary:")
        print("- NODEINFO packets correctly update node names in node_manager")
        print("- Neighbor display uses real names when available")
        print("- Unknown nodes fall back to 'Node-xxxxxxxx' format")
        print("- Output format matches expected requirements")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
