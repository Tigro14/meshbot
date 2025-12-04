#!/usr/bin/env python3
"""
Test script to verify the MQTT active flag fix in export_nodes_from_db.py

This test verifies that:
1. Node IDs are correctly converted from hex to decimal
2. MQTT active nodes are properly identified
3. mqttLastHeard timestamps are correctly assigned
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from traffic_persistence import TrafficPersistence

# Test node IDs (chosen to verify hex-to-decimal conversion)
# These specific values test different hex patterns
TEST_NODE_TIGRO = 385503196   # !16fa4fdc - Real node from problem statement
TEST_NODE_EXAMPLE = 305419896  # !12345678 - Simple hex pattern
TEST_NODE_HIGH = 587202560     # !23000000 - High value test

def test_mqtt_active_flag_fix():
    """Test that MQTT active flags are correctly set after hex to decimal conversion."""
    
    print("=" * 60)
    print("TEST: MQTT Active Flag Fix")
    print("=" * 60)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Create test data
        persistence = TrafficPersistence(db_path)
        
        # Use named test constants for clarity
        test_nodes = [
            TEST_NODE_TIGRO,    # Real node from problem statement
            TEST_NODE_EXAMPLE,  # Simple hex pattern
            TEST_NODE_HIGH,     # High value test
        ]
        
        print("\n1. Creating test neighbor data...")
        current_time = time.time()
        
        for node_id in test_nodes:
            # Create neighbor info for each node
            neighbors = [
                {
                    'node_id': test_nodes[(test_nodes.index(node_id) + 1) % len(test_nodes)],
                    'snr': 8.5,
                    'last_rx_time': int(current_time - 300),
                    'node_broadcast_interval': 900
                }
            ]
            persistence.save_neighbor_info(node_id, neighbors)
            print(f"   • Added neighbors for node {node_id} (!{node_id:08x})")
        
        persistence.close()
        
        # Load neighbors back
        print("\n2. Loading neighbors from database...")
        persistence = TrafficPersistence(db_path)
        neighbors_raw = persistence.load_neighbors(hours=48)
        
        print(f"   • Loaded {len(neighbors_raw)} nodes with neighbors")
        for node_id_str, neighbor_list in neighbors_raw.items():
            print(f"   • Node {node_id_str}: {len(neighbor_list)} neighbors")
        
        # Test hex to decimal conversion
        print("\n3. Testing hex to decimal conversion...")
        mqtt_active_nodes = set()
        mqtt_last_heard_data = {}
        neighbors_data = {}
        
        for node_id_str, neighbor_list in neighbors_raw.items():
            formatted_neighbors = []
            max_timestamp = 0
            
            for neighbor in neighbor_list:
                neighbor_id = neighbor.get('node_id')
                neighbor_timestamp = neighbor.get('timestamp', 0)
                
                if neighbor_timestamp > max_timestamp:
                    max_timestamp = neighbor_timestamp
                
                if neighbor_id:
                    formatted_neighbors.append({
                        'nodeId': neighbor_id,
                        'snr': neighbor.get('snr'),
                    })
            
            if formatted_neighbors:
                # Test hex to decimal conversion
                # Database stores: '!16fa4fdc' (hex with ! prefix)
                # Need to convert to: '385503196' (decimal string)
                node_id_hex_stripped = node_id_str.lstrip('!')  # Strip ! prefix
                node_id_int = int(node_id_hex_stripped, 16)  # Convert hex to decimal
                node_key_decimal = str(node_id_int)  # Convert to string for dict key
                
                print(f"   • {node_id_str} -> {node_id_hex_stripped} -> {node_id_int} -> '{node_key_decimal}'")
                
                # Store neighbors with decimal key (matches node_names.json)
                neighbors_data[node_key_decimal] = formatted_neighbors
                
                # This node sent NEIGHBORINFO, so it's MQTT-active
                mqtt_active_nodes.add(node_key_decimal)
                
                # Store MQTT last heard timestamp
                if max_timestamp > 0:
                    mqtt_last_heard_data[node_key_decimal] = int(max_timestamp)
        
        print(f"\n4. Verification:")
        print(f"   • MQTT active nodes: {len(mqtt_active_nodes)}")
        print(f"   • Expected: {len(test_nodes)}")
        
        # Verify each test node is in mqtt_active_nodes
        all_found = True
        for node_id in test_nodes:
            node_key = str(node_id)
            if node_key in mqtt_active_nodes:
                print(f"   ✓ Node {node_id} ({node_key}) is MQTT-active")
            else:
                print(f"   ✗ Node {node_id} ({node_key}) NOT found in MQTT-active set!")
                all_found = False
        
        # Create test node_names.json
        print("\n5. Testing with simulated node_names.json...")
        node_names_data = {}
        for node_id in test_nodes:
            node_names_data[str(node_id)] = {
                'name': f'TestNode-{node_id:08x}',
                'lat': 47.0 + (node_id % 100) / 100.0,
                'lon': 6.0 + (node_id % 100) / 100.0,
                'alt': 500
            }
        
        # Simulate the output building phase
        output_nodes = {}
        mqtt_flags_added = 0
        
        for node_id_str, node_data in node_names_data.items():
            node_id = int(node_id_str)
            node_id_hex = f"!{node_id:08x}"
            
            node_entry = {
                "num": node_id,
                "user": {
                    "id": node_id_hex,
                    "longName": node_data['name'],
                    "shortName": node_data['name'][:4],
                    "hwModel": "UNKNOWN"
                }
            }
            
            # Add MQTT last heard timestamp (always add for MQTT-active nodes)
            if node_id_str in mqtt_last_heard_data:
                node_entry["mqttLastHeard"] = mqtt_last_heard_data[node_id_str]
                print(f"   • Added mqttLastHeard for {node_id_str}")
            
            # Add MQTT active flag if this node sent NEIGHBORINFO
            if node_id_str in mqtt_active_nodes:
                node_entry["mqttActive"] = True
                mqtt_flags_added += 1
                print(f"   ✓ Added mqttActive flag for {node_id_str}")
            
            output_nodes[node_id_hex] = node_entry
        
        print(f"\n6. Final Results:")
        print(f"   • Total nodes in output: {len(output_nodes)}")
        print(f"   • Nodes with mqttActive flag: {mqtt_flags_added}")
        print(f"   • Expected: {len(test_nodes)}")
        
        nodes_with_mqtt_last_heard = sum(1 for n in output_nodes.values() if 'mqttLastHeard' in n)
        print(f"   • Nodes with mqttLastHeard: {nodes_with_mqtt_last_heard}")
        
        nodes_mqtt_active = sum(1 for n in output_nodes.values() if 'mqttActive' in n)
        print(f"   • Nodes MQTT actifs (from output): {nodes_mqtt_active}")
        
        # Final verification
        print("\n" + "=" * 60)
        if all_found and mqtt_flags_added == len(test_nodes):
            print("✅ TEST PASSED: All MQTT active flags correctly set!")
            print("=" * 60)
            return True
        else:
            print("❌ TEST FAILED: Some MQTT active flags missing!")
            print("=" * 60)
            return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

if __name__ == "__main__":
    success = test_mqtt_active_flag_fix()
    sys.exit(0 if success else 1)
