#!/usr/bin/env python3
"""
Integration test for the complete export_nodes_from_db.py workflow.

This test simulates the real-world scenario:
1. Creates node_names.json with sample data
2. Creates traffic_history.db with neighbor data
3. Runs export_nodes_from_db.py
4. Verifies MQTT active flags are present in output
"""

import json
import os
import sys
import tempfile
import subprocess
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from traffic_persistence import TrafficPersistence

def test_export_nodes_integration():
    """Integration test for export_nodes_from_db.py with MQTT active fix."""
    
    print("=" * 70)
    print("INTEGRATION TEST: export_nodes_from_db.py with MQTT Active Fix")
    print("=" * 70)
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix='meshbot_test_')
    print(f"\n📁 Test directory: {temp_dir}")
    
    try:
        # Paths
        node_names_file = os.path.join(temp_dir, 'node_names.json')
        db_path = os.path.join(temp_dir, 'traffic_history.db')
        
        # Test data
        test_nodes = [
            {'id': 385503196, 'name': 'TestNode1', 'lat': 47.123, 'lon': 6.456, 'alt': 500},
            {'id': 305419896, 'name': 'TestNode2', 'lat': 47.234, 'lon': 6.567, 'alt': 600},
            {'id': 587202560, 'name': 'TestNode3', 'lat': 47.345, 'lon': 6.678, 'alt': 700},
            {'id': 123456789, 'name': 'TestNode4', 'lat': 47.456, 'lon': 6.789, 'alt': 800},
        ]
        
        # 1. Create node_names.json
        print("\n1. Creating node_names.json...")
        node_names_data = {}
        for node in test_nodes:
            node_names_data[str(node['id'])] = {
                'name': node['name'],
                'lat': node['lat'],
                'lon': node['lon'],
                'alt': node['alt'],
                'last_update': time.time()
            }
        
        with open(node_names_file, 'w') as f:
            json.dump(node_names_data, f, indent=2)
        
        print(f"   ✓ Created {node_names_file} with {len(node_names_data)} nodes")
        
        # 2. Create traffic_history.db with neighbor data
        print("\n2. Creating traffic_history.db with neighbor data...")
        persistence = TrafficPersistence(db_path)
        
        # Only first 3 nodes send neighbor info (MQTT-active)
        mqtt_active_count = 3
        current_time = time.time()
        
        for i, node in enumerate(test_nodes[:mqtt_active_count]):
            # Each node has 1-2 neighbors
            neighbors = [
                {
                    'node_id': test_nodes[(i + 1) % len(test_nodes)]['id'],
                    'snr': 8.5 + i,
                    'last_rx_time': int(current_time - 300),
                    'node_broadcast_interval': 900
                }
            ]
            persistence.save_neighbor_info(node['id'], neighbors)
            print(f"   • Node {node['id']} ({node['name']}): {len(neighbors)} neighbors")
        
        persistence.close()
        print(f"   ✓ Created {db_path} with neighbor data for {mqtt_active_count} nodes")
        
        # 3. Run export_nodes_from_db.py
        print("\n3. Running export_nodes_from_db.py...")
        script_path = os.path.join(os.path.dirname(__file__), 'map', 'export_nodes_from_db.py')
        
        result = subprocess.run(
            ['python3', script_path, node_names_file, db_path, '48'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"   ✗ Script failed with exit code {result.returncode}")
            print(f"   STDERR:\n{result.stderr}")
            return False
        
        print("   ✓ Script executed successfully")
        
        # Parse output JSON (stdout)
        try:
            output_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"   ✗ Failed to parse JSON output: {e}")
            print(f"   STDOUT:\n{result.stdout}")
            return False
        
        # 4. Verify output
        print("\n4. Verifying output...")
        
        if 'Nodes in mesh' not in output_data:
            print("   ✗ 'Nodes in mesh' not found in output")
            return False
        
        nodes = output_data['Nodes in mesh']
        print(f"   ✓ Found {len(nodes)} nodes in output")
        
        # Count MQTT active flags
        mqtt_active_in_output = 0
        mqtt_last_heard_in_output = 0
        neighbors_in_output = 0
        
        for node_id_hex, node_entry in nodes.items():
            if 'mqttActive' in node_entry and node_entry['mqttActive']:
                mqtt_active_in_output += 1
                node_num = node_entry.get('num')
                node_name = node_entry.get('user', {}).get('longName', 'Unknown')
                print(f"   • Node {node_name} ({node_num}): mqttActive=True")
            
            if 'mqttLastHeard' in node_entry:
                mqtt_last_heard_in_output += 1
            
            if 'neighbors' in node_entry:
                neighbors_in_output += 1
        
        print(f"\n5. Statistics:")
        print(f"   • Total nodes: {len(nodes)}")
        print(f"   • Nodes with mqttActive flag: {mqtt_active_in_output}")
        print(f"   • Expected MQTT active: {mqtt_active_count}")
        print(f"   • Nodes with mqttLastHeard: {mqtt_last_heard_in_output}")
        print(f"   • Nodes with neighbors: {neighbors_in_output}")
        
        # Parse stderr for statistics
        print(f"\n6. Script output (stderr):")
        for line in result.stderr.split('\n'):
            if 'MQTT' in line or 'nœuds' in line or '•' in line:
                print(f"   {line}")
        
        # Verify expectations
        print("\n" + "=" * 70)
        if mqtt_active_in_output == mqtt_active_count:
            print("✅ INTEGRATION TEST PASSED!")
            print(f"   • All {mqtt_active_count} MQTT-active nodes have mqttActive flag")
            print(f"   • mqttLastHeard correctly set for {mqtt_last_heard_in_output} nodes")
            print("=" * 70)
            return True
        else:
            print("❌ INTEGRATION TEST FAILED!")
            print(f"   • Expected {mqtt_active_count} MQTT-active nodes")
            print(f"   • Got {mqtt_active_in_output} nodes with mqttActive flag")
            print("=" * 70)
            return False
        
    finally:
        # Cleanup
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n🗑️  Cleaned up test directory: {temp_dir}")

if __name__ == "__main__":
    success = test_export_nodes_integration()
    sys.exit(0 if success else 1)
