#!/usr/bin/env python3
"""
Integration test to verify telemetry data flows correctly from database to map JSON.
This simulates the entire infoup_db.sh workflow.
"""

import sqlite3
import json
import os
import sys
import tempfile
import subprocess

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traffic_persistence import TrafficPersistence

def create_test_data():
    """Create test database and node_names.json."""
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'traffic_history.db')
    node_names_path = os.path.join(temp_dir, 'node_names.json')
    
    # Create persistence instance
    persistence = TrafficPersistence(db_path)
    cursor = persistence.conn.cursor()
    
    # Add test nodes with telemetry data
    test_nodes = [
        {
            'id': '385503196',  # !16fa4fdc
            'name': 'TestNode1',
            'short': 'TST1',
            'hw': 'RAK4631',
            'lat': 48.8566,
            'lon': 2.3522,
            'battery': 85,
            'voltage': 4.15,
            'temp': 22.5,
            'humidity': 65.0,
            'pressure': 1013.25
        },
        {
            'id': '305419896',  # !12345678
            'name': 'TestNode2',
            'short': 'TST2',
            'hw': 'TBEAM',
            'lat': 48.8700,
            'lon': 2.3800,
            'battery': 92,
            'voltage': 4.18,
            'temp': 21.0,
            'humidity': 70.0,
            'pressure': None  # Test missing data
        }
    ]
    
    # Create node_names.json
    node_names_data = {}
    for node in test_nodes:
        node_names_data[node['id']] = {
            'name': node['name'],
            'shortName': node['short'],
            'hwModel': node['hw'],
            'lat': node['lat'],
            'lon': node['lon']
        }
    
    with open(node_names_path, 'w') as f:
        json.dump(node_names_data, f, indent=2)
    
    print(f"✅ Created node_names.json with {len(test_nodes)} nodes")
    
    # Add node_stats with telemetry
    for node in test_nodes:
        telemetry_stats = {}
        if node['battery'] is not None:
            telemetry_stats['last_battery'] = node['battery']
        if node['voltage'] is not None:
            telemetry_stats['last_voltage'] = node['voltage']
        if node['temp'] is not None:
            telemetry_stats['last_temperature'] = node['temp']
        if node['humidity'] is not None:
            telemetry_stats['last_humidity'] = node['humidity']
        if node['pressure'] is not None:
            telemetry_stats['last_pressure'] = node['pressure']
        
        cursor.execute('''
            INSERT INTO node_stats (
                node_id, total_packets, total_bytes, packet_types,
                hourly_activity, message_stats, telemetry_stats,
                position_stats, routing_stats, last_updated,
                last_battery_level, last_battery_voltage, last_telemetry_update,
                last_temperature, last_humidity, last_pressure, last_air_quality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            node['id'],
            100,  # total_packets
            50000,  # total_bytes
            json.dumps({}),
            json.dumps({}),
            json.dumps({}),
            json.dumps(telemetry_stats),
            json.dumps({}),
            json.dumps({}),
            1700000000.0,  # last_updated
            node['battery'],
            node['voltage'],
            1700000000.0 if node['battery'] or node['voltage'] else None,
            node['temp'],
            node['humidity'],
            node['pressure'],
            None  # air_quality
        ))
    
    persistence.conn.commit()
    persistence.close()
    
    print(f"✅ Created database with telemetry for {len(test_nodes)} nodes")
    
    return temp_dir, db_path, node_names_path, test_nodes

def test_export_script():
    """Test the export_nodes_from_db.py script."""
    
    print("\n🧪 Integration Test: Telemetry in Map Export")
    print("=" * 60)
    
    # Create test data
    temp_dir, db_path, node_names_path, test_nodes = create_test_data()
    
    try:
        # Run export script
        script_path = os.path.join(os.path.dirname(__file__), 'map', 'export_nodes_from_db.py')
        output_path = os.path.join(temp_dir, 'output.json')
        
        print(f"\n📤 Running export_nodes_from_db.py...")
        result = subprocess.run(
            [sys.executable, script_path, node_names_path, db_path, '720'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ Export script failed:")
            print(result.stderr)
            return False
        
        # Parse output JSON
        try:
            output_json = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON output: {e}")
            print(f"Output: {result.stdout[:500]}")
            return False
        
        # Extract nodes from wrapper structure
        if "Nodes in mesh" in output_json:
            nodes_data = output_json["Nodes in mesh"]
        else:
            nodes_data = output_json
        
        print(f"✅ Export script completed successfully")
        print(f"📊 Exported {len(nodes_data)} nodes")
        
        # Verify telemetry data for each test node
        success = True
        for node in test_nodes:
            node_id_hex = f"!{int(node['id']):08x}"
            
            if node_id_hex not in nodes_data:
                print(f"❌ Node {node['name']} ({node_id_hex}) not in output")
                success = False
                continue
            
            node_data = nodes_data[node_id_hex]
            
            print(f"\n🔍 Checking {node['name']} ({node_id_hex}):")
            
            # Check device metrics (battery)
            has_battery = node['battery'] is not None or node['voltage'] is not None
            if has_battery:
                if 'deviceMetrics' not in node_data:
                    print(f"   ❌ deviceMetrics missing")
                    success = False
                else:
                    dm = node_data['deviceMetrics']
                    
                    if node['battery'] is not None:
                        if dm.get('batteryLevel') == node['battery']:
                            print(f"   ✅ Battery: {dm.get('batteryLevel')}%")
                        else:
                            print(f"   ❌ Battery mismatch: expected {node['battery']}, got {dm.get('batteryLevel')}")
                            success = False
                    
                    if node['voltage'] is not None:
                        if dm.get('voltage') == node['voltage']:
                            print(f"   ✅ Voltage: {dm.get('voltage')}V")
                        else:
                            print(f"   ❌ Voltage mismatch: expected {node['voltage']}, got {dm.get('voltage')}")
                            success = False
            
            # Check environment metrics
            has_env = (node['temp'] is not None or node['humidity'] is not None or 
                      node['pressure'] is not None)
            if has_env:
                if 'environmentMetrics' not in node_data:
                    print(f"   ❌ environmentMetrics missing")
                    success = False
                else:
                    em = node_data['environmentMetrics']
                    
                    if node['temp'] is not None:
                        if em.get('temperature') == node['temp']:
                            print(f"   ✅ Temperature: {em.get('temperature')}°C")
                        else:
                            print(f"   ❌ Temperature mismatch: expected {node['temp']}, got {em.get('temperature')}")
                            success = False
                    
                    if node['humidity'] is not None:
                        if em.get('relativeHumidity') == node['humidity']:
                            print(f"   ✅ Humidity: {em.get('relativeHumidity')}%")
                        else:
                            print(f"   ❌ Humidity mismatch: expected {node['humidity']}, got {em.get('relativeHumidity')}")
                            success = False
                    
                    if node['pressure'] is not None:
                        if em.get('barometricPressure') == node['pressure']:
                            print(f"   ✅ Pressure: {em.get('barometricPressure')} hPa")
                        else:
                            print(f"   ❌ Pressure mismatch: expected {node['pressure']}, got {em.get('barometricPressure')}")
                            success = False
        
        if success:
            print(f"\n✅ SUCCESS: All telemetry data correctly exported!")
        else:
            print(f"\n❌ FAILURE: Some telemetry data missing or incorrect")
        
        return success
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Cleaned up test directory")

if __name__ == "__main__":
    success = test_export_script()
    sys.exit(0 if success else 1)
