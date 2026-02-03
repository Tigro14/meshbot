#!/usr/bin/env python3
"""
Test script to verify telemetry data is correctly exported to map JSON.
"""

import sqlite3
import json
import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traffic_persistence import TrafficPersistence

def create_test_database():
    """Create a temporary test database with telemetry data."""
    db_path = tempfile.mktemp(suffix='.db')
    
    # Create persistence instance (this will create tables)
    persistence = TrafficPersistence(db_path)
    
    # Add test node_stats with telemetry data
    cursor = persistence.conn.cursor()
    
    test_node_id = '385503196'  # Example node ID (decimal)
    
    cursor.execute('''
        INSERT INTO node_stats (
            node_id, total_packets, total_bytes, packet_types,
            hourly_activity, message_stats, telemetry_stats,
            position_stats, routing_stats, last_updated,
            last_battery_level, last_battery_voltage, last_telemetry_update,
            last_temperature, last_humidity, last_pressure, last_air_quality
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        test_node_id,
        100,  # total_packets
        50000,  # total_bytes
        json.dumps({}),  # packet_types
        json.dumps({}),  # hourly_activity
        json.dumps({}),  # message_stats
        json.dumps({
            'last_battery': 85,
            'last_voltage': 4.15,
            'last_temperature': 22.5,
            'last_humidity': 65.0,
            'last_pressure': 1013.25,
            'last_air_quality': 50
        }),  # telemetry_stats
        json.dumps({}),  # position_stats
        json.dumps({}),  # routing_stats
        1700000000.0,  # last_updated
        85,  # last_battery_level
        4.15,  # last_battery_voltage
        1700000000.0,  # last_telemetry_update
        22.5,  # last_temperature
        65.0,  # last_humidity
        1013.25,  # last_pressure
        50  # last_air_quality
    ))
    
    persistence.conn.commit()
    persistence.close()
    
    return db_path, test_node_id

def test_telemetry_extraction():
    """Test that telemetry data is correctly extracted from node_stats."""
    
    print("🧪 Test: Telemetry Data Extraction")
    print("=" * 60)
    
    # Create test database
    db_path, test_node_id = create_test_database()
    print(f"✅ Created test database: {db_path}")
    print(f"✅ Test node ID: {test_node_id}")
    
    try:
        # Load node_stats
        persistence = TrafficPersistence(db_path)
        node_stats_raw = persistence.load_node_stats()
        
        print(f"\n📊 Loaded node_stats for {len(node_stats_raw)} nodes")
        
        # Check if our test node is present
        if test_node_id not in node_stats_raw:
            print(f"❌ FAIL: Test node {test_node_id} not found in node_stats")
            return False
        
        print(f"✅ Test node found in node_stats")
        
        # Extract telemetry data (simulate what export_nodes_from_db.py does)
        telemetry_data = {}
        
        for node_id_str, stats in node_stats_raw.items():
            telem_stats = stats.get('telemetry_stats', {})
            if telem_stats:
                telemetry_entry = {}
                
                # Battery metrics
                if telem_stats.get('last_battery') is not None:
                    telemetry_entry['battery_level'] = telem_stats['last_battery']
                if telem_stats.get('last_voltage') is not None:
                    telemetry_entry['battery_voltage'] = telem_stats['last_voltage']
                
                # Environment metrics
                if telem_stats.get('last_temperature') is not None:
                    telemetry_entry['temperature'] = telem_stats['last_temperature']
                if telem_stats.get('last_humidity') is not None:
                    telemetry_entry['humidity'] = telem_stats['last_humidity']
                if telem_stats.get('last_pressure') is not None:
                    telemetry_entry['pressure'] = telem_stats['last_pressure']
                if telem_stats.get('last_air_quality') is not None:
                    telemetry_entry['air_quality'] = telem_stats['last_air_quality']
                
                # Only add to telemetry_data if we have at least one metric
                if telemetry_entry:
                    telemetry_data[str(node_id_str)] = telemetry_entry
        
        print(f"\n📡 Extracted telemetry for {len(telemetry_data)} nodes")
        
        # Verify telemetry data for test node
        if test_node_id not in telemetry_data:
            print(f"❌ FAIL: Telemetry data not extracted for test node")
            return False
        
        telem = telemetry_data[test_node_id]
        print(f"\n✅ Telemetry data for test node:")
        print(f"   🔋 Battery Level: {telem.get('battery_level')}%")
        print(f"   ⚡ Battery Voltage: {telem.get('battery_voltage')}V")
        print(f"   🌡️ Temperature: {telem.get('temperature')}°C")
        print(f"   💧 Humidity: {telem.get('humidity')}%")
        print(f"   🌫️ Pressure: {telem.get('pressure')} hPa")
        print(f"   🌬️ Air Quality: {telem.get('air_quality')}")
        
        # Verify values
        expected = {
            'battery_level': 85,
            'battery_voltage': 4.15,
            'temperature': 22.5,
            'humidity': 65.0,
            'pressure': 1013.25,
            'air_quality': 50
        }
        
        for key, expected_value in expected.items():
            actual_value = telem.get(key)
            if actual_value != expected_value:
                print(f"❌ FAIL: {key} mismatch - expected {expected_value}, got {actual_value}")
                return False
        
        print(f"\n✅ All telemetry values match expected values")
        
        # Test how this would be added to node entry
        node_entry = {}
        
        # Device metrics (battery)
        if telem.get('battery_level') is not None or telem.get('battery_voltage') is not None:
            if "deviceMetrics" not in node_entry:
                node_entry["deviceMetrics"] = {}
            if telem.get('battery_level') is not None:
                node_entry["deviceMetrics"]["batteryLevel"] = telem['battery_level']
            if telem.get('battery_voltage') is not None:
                node_entry["deviceMetrics"]["voltage"] = telem['battery_voltage']
        
        # Environment metrics
        if (telem.get('temperature') is not None or telem.get('humidity') is not None or
            telem.get('pressure') is not None or telem.get('air_quality') is not None):
            node_entry["environmentMetrics"] = {}
            if telem.get('temperature') is not None:
                node_entry["environmentMetrics"]["temperature"] = telem['temperature']
            if telem.get('humidity') is not None:
                node_entry["environmentMetrics"]["relativeHumidity"] = telem['humidity']
            if telem.get('pressure') is not None:
                node_entry["environmentMetrics"]["barometricPressure"] = telem['pressure']
            if telem.get('air_quality') is not None:
                node_entry["environmentMetrics"]["iaq"] = telem['air_quality']
        
        print(f"\n✅ Node entry with telemetry:")
        print(json.dumps(node_entry, indent=2))
        
        # Verify node entry structure
        if "deviceMetrics" not in node_entry:
            print(f"❌ FAIL: deviceMetrics not in node entry")
            return False
        
        if "environmentMetrics" not in node_entry:
            print(f"❌ FAIL: environmentMetrics not in node entry")
            return False
        
        print(f"\n✅ SUCCESS: All tests passed!")
        
        persistence.close()
        return True
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"\n🧹 Cleaned up test database")

if __name__ == "__main__":
    success = test_telemetry_extraction()
    sys.exit(0 if success else 1)
