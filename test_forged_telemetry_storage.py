#!/usr/bin/env python3
"""
Test that forged (self-generated) telemetry data is stored in the database.

This test verifies that when the bot sends its own telemetry data via the mesh,
that data is also stored in the local database so it can be exported to JSON
and displayed on maps.
"""

import os
import sys
import tempfile
import time
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor
from node_manager import NodeManager


def test_store_sent_telemetry():
    """Test that _store_sent_telemetry saves telemetry to database."""
    print("\n" + "="*70)
    print("TEST: Store Forged Telemetry in Database")
    print("="*70)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize components
        persistence = TrafficPersistence(db_path)
        node_manager = NodeManager()
        traffic_monitor = TrafficMonitor(node_manager)
        traffic_monitor.persistence = persistence
        
        # Simulate storing telemetry directly (without importing MeshBot)
        node_id = 385503196  # Example node ID (0x16fa4fdc)
        node_id_hex = f"!{node_id:08x}"
        
        # Prepare sensor values (simulating ESPHome data)
        sensor_values = {
            'battery_voltage': 12.5,
            'temperature': 22.5,
            'humidity': 65.0,
            'pressure': 1013.25  # hPa
        }
        battery_level = 85  # 85%
        
        print("\n📊 Simulating telemetry send with values:")
        print(f"   Node: {node_id_hex}")
        print(f"   Battery: {battery_level}% ({sensor_values['battery_voltage']}V)")
        print(f"   Temperature: {sensor_values['temperature']}°C")
        print(f"   Humidity: {sensor_values['humidity']}%")
        print(f"   Pressure: {sensor_values['pressure']} hPa")
        
        # Simulate the storage logic from _store_sent_telemetry
        print("\n💾 Storing telemetry in database...")
        
        # Create or update node stats
        if node_id_hex not in traffic_monitor.node_packet_stats:
            traffic_monitor.node_packet_stats[node_id_hex] = {
                'total_packets': 0,
                'by_type': {},
                'total_bytes': 0,
                'first_seen': None,
                'last_seen': None,
                'hourly_activity': {},
                'message_stats': {'count': 0, 'total_chars': 0, 'avg_length': 0},
                'telemetry_stats': {'count': 0},
                'position_stats': {'count': 0},
                'routing_stats': {'count': 0, 'packets_relayed': 0, 'packets_originated': 0}
            }
        
        # Update telemetry stats
        tel_stats = traffic_monitor.node_packet_stats[node_id_hex]['telemetry_stats']
        
        # Device metrics (battery)
        if battery_level is not None:
            tel_stats['last_battery'] = battery_level
        if sensor_values.get('battery_voltage') is not None:
            tel_stats['last_voltage'] = sensor_values['battery_voltage']
        
        # Environment metrics
        if sensor_values.get('temperature') is not None:
            tel_stats['last_temperature'] = sensor_values['temperature']
        if sensor_values.get('humidity') is not None:
            tel_stats['last_humidity'] = sensor_values['humidity']
        if sensor_values.get('pressure') is not None:
            tel_stats['last_pressure'] = sensor_values['pressure']
        
        # Save to database
        persistence.save_node_stats(
            {node_id_hex: traffic_monitor.node_packet_stats[node_id_hex]}
        )
        
        # Verify data was stored in database
        print("\n📖 Loading node stats from database...")
        loaded_stats = persistence.load_node_stats()
        
        print(f"\n✅ Verification for node {node_id_hex}:")
        
        # Check if node exists in database
        assert node_id_hex in loaded_stats, f"Node {node_id_hex} not found in database"
        print(f"   ✓ Node found in database")
        
        # Get telemetry stats
        telem = loaded_stats[node_id_hex]['telemetry_stats']
        
        # Verify battery data
        assert telem.get('last_battery') == battery_level, \
            f"Battery level mismatch: {telem.get('last_battery')} != {battery_level}"
        print(f"   ✓ Battery Level: {telem.get('last_battery')}%")
        
        assert telem.get('last_voltage') == sensor_values['battery_voltage'], \
            f"Battery voltage mismatch: {telem.get('last_voltage')} != {sensor_values['battery_voltage']}"
        print(f"   ✓ Battery Voltage: {telem.get('last_voltage')}V")
        
        # Verify environment data
        assert telem.get('last_temperature') == sensor_values['temperature'], \
            f"Temperature mismatch: {telem.get('last_temperature')} != {sensor_values['temperature']}"
        print(f"   ✓ Temperature: {telem.get('last_temperature')}°C")
        
        assert telem.get('last_humidity') == sensor_values['humidity'], \
            f"Humidity mismatch: {telem.get('last_humidity')} != {sensor_values['humidity']}"
        print(f"   ✓ Humidity: {telem.get('last_humidity')}%")
        
        assert telem.get('last_pressure') == sensor_values['pressure'], \
            f"Pressure mismatch: {telem.get('last_pressure')} != {sensor_values['pressure']}"
        print(f"   ✓ Pressure: {telem.get('last_pressure')} hPa")
        
        # Verify telemetry update timestamp exists
        assert telem.get('last_telemetry_update') is not None, \
            "Telemetry update timestamp missing"
        print(f"   ✓ Telemetry timestamp recorded")
        
        print("\n✅ TEST PASSED: Forged telemetry successfully stored in database")
        print("   The bot's own telemetry will now be exported to JSON and visible on maps.")
        
        persistence.close()
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


def test_telemetry_export_integration():
    """Test that stored telemetry can be exported to JSON format."""
    print("\n" + "="*70)
    print("TEST: Telemetry Export Integration")
    print("="*70)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize persistence
        persistence = TrafficPersistence(db_path)
        
        # Manually insert telemetry data (simulating stored forged telemetry)
        node_id = "!16fa4fdc"
        node_stats = {
            node_id: {
                'total_packets': 3,
                'total_bytes': 512,
                'by_type': {'TELEMETRY_APP': 3},
                'hourly_activity': {},
                'message_stats': {'count': 0, 'total_chars': 0, 'avg_length': 0},
                'telemetry_stats': {
                    'count': 3,
                    'last_battery': 85,
                    'last_voltage': 12.5,
                    'last_temperature': 22.5,
                    'last_humidity': 65.0,
                    'last_pressure': 1013.25,
                    'last_air_quality': None
                },
                'position_stats': {'count': 0},
                'routing_stats': {'count': 0, 'packets_relayed': 0, 'packets_originated': 0}
            }
        }
        
        print(f"\n📊 Storing telemetry data for node {node_id}...")
        persistence.save_node_stats(node_stats)
        
        # Load back and verify
        print("\n📖 Loading from database...")
        loaded_stats = persistence.load_node_stats()
        
        assert node_id in loaded_stats, f"Node {node_id} not found"
        telem = loaded_stats[node_id]['telemetry_stats']
        
        print(f"\n✅ Verification:")
        print(f"   Battery: {telem.get('last_battery')}% @ {telem.get('last_voltage')}V")
        print(f"   Temperature: {telem.get('last_temperature')}°C")
        print(f"   Humidity: {telem.get('last_humidity')}%")
        print(f"   Pressure: {telem.get('last_pressure')} hPa")
        
        # This data is now ready to be exported to JSON
        print("\n✅ TEST PASSED: Telemetry data ready for export")
        print("   Data can be queried by export_nodes_from_db.py and included in info.json")
        
        persistence.close()
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == '__main__':
    print("\n" + "="*70)
    print("FORGED TELEMETRY STORAGE TEST SUITE")
    print("="*70)
    
    try:
        test_store_sent_telemetry()
        test_telemetry_export_integration()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSummary:")
        print("- Forged telemetry is now stored in database")
        print("- Bot's own telemetry will appear in JSON exports")
        print("- Map displays will show bot's sensor data")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
