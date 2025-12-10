#!/usr/bin/env python3
"""
Test telemetry storage in node_stats table.
Verify that battery and environment metrics are properly stored and retrieved.
"""

import os
import sys
import tempfile
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor
from node_manager import NodeManager


def test_battery_telemetry_storage():
    """Test that battery telemetry is stored and retrieved correctly."""
    print("\n" + "="*70)
    print("TEST 1: Battery Telemetry Storage")
    print("="*70)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize persistence
        persistence = TrafficPersistence(db_path)
        
        # Create mock node stats with battery telemetry
        node_stats = {
            '123456789': {
                'total_packets': 10,
                'total_bytes': 1024,
                'by_type': {'TELEMETRY_APP': 5},
                'hourly_activity': {},
                'message_stats': {},
                'telemetry_stats': {
                    'last_battery': 85,  # 85%
                    'last_voltage': 12.5,  # 12.5V
                    'count': 5
                },
                'position_stats': {},
                'routing_stats': {}
            }
        }
        
        # Save node stats
        print("\n📊 Saving node stats with battery telemetry...")
        persistence.save_node_stats(node_stats)
        
        # Load node stats
        print("📖 Loading node stats from database...")
        loaded_stats = persistence.load_node_stats()
        
        # Verify battery data was saved and loaded correctly
        assert '123456789' in loaded_stats, "Node not found in loaded stats"
        telem = loaded_stats['123456789']['telemetry_stats']
        
        print(f"\n✅ Verification:")
        print(f"   Battery Level: {telem.get('last_battery')}% (expected: 85%)")
        print(f"   Battery Voltage: {telem.get('last_voltage')}V (expected: 12.5V)")
        
        assert telem.get('last_battery') == 85, f"Battery level mismatch: {telem.get('last_battery')} != 85"
        assert telem.get('last_voltage') == 12.5, f"Battery voltage mismatch: {telem.get('last_voltage')} != 12.5"
        assert telem.get('last_telemetry_update') is not None, "Telemetry update timestamp missing"
        
        print("\n✅ TEST 1 PASSED: Battery telemetry stored and retrieved correctly")
        
        persistence.close()
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


def test_environment_telemetry_storage():
    """Test that environment metrics are stored and retrieved correctly."""
    print("\n" + "="*70)
    print("TEST 2: Environment Metrics Storage")
    print("="*70)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize persistence
        persistence = TrafficPersistence(db_path)
        
        # Create mock node stats with environment telemetry
        node_stats = {
            '987654321': {
                'total_packets': 15,
                'total_bytes': 2048,
                'by_type': {'TELEMETRY_APP': 10},
                'hourly_activity': {},
                'message_stats': {},
                'telemetry_stats': {
                    'last_temperature': 22.5,  # 22.5°C
                    'last_humidity': 65.0,     # 65%
                    'last_pressure': 101325.0, # 101325 Pa (1 atm)
                    'last_air_quality': 50,    # IAQ 50 (good)
                    'count': 10
                },
                'position_stats': {},
                'routing_stats': {}
            }
        }
        
        # Save node stats
        print("\n📊 Saving node stats with environment metrics...")
        persistence.save_node_stats(node_stats)
        
        # Load node stats
        print("📖 Loading node stats from database...")
        loaded_stats = persistence.load_node_stats()
        
        # Verify environment data was saved and loaded correctly
        assert '987654321' in loaded_stats, "Node not found in loaded stats"
        telem = loaded_stats['987654321']['telemetry_stats']
        
        print(f"\n✅ Verification:")
        print(f"   Temperature: {telem.get('last_temperature')}°C (expected: 22.5°C)")
        print(f"   Humidity: {telem.get('last_humidity')}% (expected: 65%)")
        print(f"   Pressure: {telem.get('last_pressure')} Pa (expected: 101325 Pa)")
        print(f"   Air Quality: {telem.get('last_air_quality')} IAQ (expected: 50 IAQ)")
        
        assert telem.get('last_temperature') == 22.5, f"Temperature mismatch: {telem.get('last_temperature')} != 22.5"
        assert telem.get('last_humidity') == 65.0, f"Humidity mismatch: {telem.get('last_humidity')} != 65.0"
        assert telem.get('last_pressure') == 101325.0, f"Pressure mismatch: {telem.get('last_pressure')} != 101325.0"
        assert telem.get('last_air_quality') == 50, f"Air quality mismatch: {telem.get('last_air_quality')} != 50"
        assert telem.get('last_telemetry_update') is not None, "Telemetry update timestamp missing"
        
        print("\n✅ TEST 2 PASSED: Environment metrics stored and retrieved correctly")
        
        persistence.close()
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


def test_combined_telemetry_storage():
    """Test that both battery and environment metrics can coexist."""
    print("\n" + "="*70)
    print("TEST 3: Combined Telemetry Storage")
    print("="*70)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize persistence
        persistence = TrafficPersistence(db_path)
        
        # Create mock node stats with both battery and environment telemetry
        node_stats = {
            '555666777': {
                'total_packets': 20,
                'total_bytes': 4096,
                'by_type': {'TELEMETRY_APP': 15},
                'hourly_activity': {},
                'message_stats': {},
                'telemetry_stats': {
                    # Battery metrics
                    'last_battery': 92,
                    'last_voltage': 13.2,
                    # Environment metrics
                    'last_temperature': 21.0,
                    'last_humidity': 58.5,
                    'last_pressure': 100800.0,
                    'last_air_quality': 35,
                    'count': 15
                },
                'position_stats': {},
                'routing_stats': {}
            }
        }
        
        # Save node stats
        print("\n📊 Saving node stats with combined telemetry...")
        persistence.save_node_stats(node_stats)
        
        # Load node stats
        print("📖 Loading node stats from database...")
        loaded_stats = persistence.load_node_stats()
        
        # Verify all data was saved and loaded correctly
        assert '555666777' in loaded_stats, "Node not found in loaded stats"
        telem = loaded_stats['555666777']['telemetry_stats']
        
        print(f"\n✅ Verification:")
        print(f"   Battery Level: {telem.get('last_battery')}%")
        print(f"   Battery Voltage: {telem.get('last_voltage')}V")
        print(f"   Temperature: {telem.get('last_temperature')}°C")
        print(f"   Humidity: {telem.get('last_humidity')}%")
        print(f"   Pressure: {telem.get('last_pressure')} Pa")
        print(f"   Air Quality: {telem.get('last_air_quality')} IAQ")
        
        # Verify all metrics
        assert telem.get('last_battery') == 92
        assert telem.get('last_voltage') == 13.2
        assert telem.get('last_temperature') == 21.0
        assert telem.get('last_humidity') == 58.5
        assert telem.get('last_pressure') == 100800.0
        assert telem.get('last_air_quality') == 35
        
        print("\n✅ TEST 3 PASSED: Combined telemetry stored correctly")
        
        persistence.close()
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


def test_traffic_monitor_extraction():
    """Test that TrafficMonitor correctly extracts telemetry from packets."""
    print("\n" + "="*70)
    print("TEST 4: TrafficMonitor Telemetry Extraction")
    print("="*70)
    
    # Use the default database path that TrafficMonitor creates
    db_path = "traffic_history.db"
    
    # Remove existing database for clean test
    if os.path.exists(db_path):
        os.remove(db_path)
    
    try:
        # Initialize components
        node_manager = NodeManager()
        # TrafficMonitor will create its own persistence with default path
        traffic_monitor = TrafficMonitor(node_manager)
        
        # Create mock telemetry packet with deviceMetrics
        device_packet = {
            'from': 111222333,
            'to': 0xFFFFFFFF,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {
                    'deviceMetrics': {
                        'batteryLevel': 78,
                        'voltage': 12.1,
                        'channelUtilization': 15.5,
                        'airUtilTx': 0.8
                    }
                }
            },
            'rxSnr': 5.5,
            'rxRssi': -85,
            'hopLimit': 3,
            'hopStart': 3
        }
        
        # Create mock telemetry packet with environmentMetrics
        env_packet = {
            'from': 444555666,
            'to': 0xFFFFFFFF,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {
                    'environmentMetrics': {
                        'temperature': 23.8,
                        'relativeHumidity': 72.5,
                        'barometricPressure': 102100.0,
                        'iaq': 45
                    }
                }
            },
            'rxSnr': 6.2,
            'rxRssi': -82,
            'hopLimit': 3,
            'hopStart': 3
        }
        
        # Process packets (set my_node_id=None so our test packets aren't filtered)
        print("\n📦 Processing device metrics packet...")
        traffic_monitor.add_packet(device_packet, source='local', my_node_id=None)
        
        print("📦 Processing environment metrics packet...")
        traffic_monitor.add_packet(env_packet, source='local', my_node_id=None)
        
        # Force save to database
        print("💾 Saving stats to database...")
        traffic_monitor.persistence.save_node_stats(traffic_monitor.node_stats)
        
        # Load from database
        print("📖 Loading stats from database...")
        loaded_stats = traffic_monitor.persistence.load_node_stats()
        
        # Debug: show what nodes are available
        print(f"\nℹ️  Available nodes in database: {list(loaded_stats.keys())}")
        
        # Verify device metrics extraction
        print(f"\n✅ Device Metrics Verification:")
        device_node_id = str(111222333)
        if device_node_id not in loaded_stats:
            print(f"⚠️  Node {device_node_id} not found, checking node_stats directly...")
            print(f"Node stats keys: {list(traffic_monitor.node_stats.keys())}")
            if device_node_id in traffic_monitor.node_stats:
                device_telem = traffic_monitor.node_stats[device_node_id]['telemetry_stats']
                print(f"   Battery (in-memory): {device_telem.get('last_battery')}%")
                print(f"   Voltage (in-memory): {device_telem.get('last_voltage')}V")
                assert device_telem.get('last_battery') == 78
                assert device_telem.get('last_voltage') == 12.1
            else:
                raise AssertionError(f"Device node {device_node_id} not found in node_stats")
        else:
            device_telem = loaded_stats[device_node_id]['telemetry_stats']
            print(f"   Battery: {device_telem.get('last_battery')}%")
            print(f"   Voltage: {device_telem.get('last_voltage')}V")
            assert device_telem.get('last_battery') == 78
            assert device_telem.get('last_voltage') == 12.1
        
        # Verify environment metrics extraction
        print(f"\n✅ Environment Metrics Verification:")
        env_node_id = str(444555666)
        if env_node_id not in loaded_stats:
            print(f"⚠️  Node {env_node_id} not found, checking node_stats directly...")
            if env_node_id in traffic_monitor.node_stats:
                env_telem = traffic_monitor.node_stats[env_node_id]['telemetry_stats']
                print(f"   Temperature (in-memory): {env_telem.get('last_temperature')}°C")
                print(f"   Humidity (in-memory): {env_telem.get('last_humidity')}%")
                print(f"   Pressure (in-memory): {env_telem.get('last_pressure')} Pa")
                print(f"   Air Quality (in-memory): {env_telem.get('last_air_quality')} IAQ")
                assert env_telem.get('last_temperature') == 23.8
                assert env_telem.get('last_humidity') == 72.5
                assert env_telem.get('last_pressure') == 102100.0
                assert env_telem.get('last_air_quality') == 45
            else:
                raise AssertionError(f"Environment node {env_node_id} not found in node_stats")
        else:
            env_telem = loaded_stats[env_node_id]['telemetry_stats']
            print(f"   Temperature: {env_telem.get('last_temperature')}°C")
            print(f"   Humidity: {env_telem.get('last_humidity')}%")
            print(f"   Pressure: {env_telem.get('last_pressure')} Pa")
            print(f"   Air Quality: {env_telem.get('last_air_quality')} IAQ")
            assert env_telem.get('last_temperature') == 23.8
            assert env_telem.get('last_humidity') == 72.5
            assert env_telem.get('last_pressure') == 102100.0
            assert env_telem.get('last_air_quality') == 45
        
        print("\n✅ TEST 4 PASSED: TrafficMonitor extracts telemetry correctly")
        
        traffic_monitor.persistence.close()
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("TELEMETRY STORAGE TEST SUITE")
    print("="*70)
    print("Testing battery and environment metrics storage in node_stats table")
    
    try:
        test_battery_telemetry_storage()
        test_environment_telemetry_storage()
        test_combined_telemetry_storage()
        test_traffic_monitor_extraction()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nNext steps:")
        print("1. Run the bot to collect telemetry data")
        print("2. Run export_nodes_from_db.py to verify JSON export")
        print("3. Check map.html to see telemetry displayed in node popups")
        print("")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
