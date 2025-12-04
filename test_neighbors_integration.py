#!/usr/bin/env python3
"""
Integration test for the /neighbors distance filtering feature
This tests the complete flow with mocked database data
"""

import sys
import os
import tempfile
import sqlite3
from datetime import datetime, timedelta

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock config
class MockConfig:
    NEIGHBORS_MAX_DISTANCE_KM = 100
    DEBUG_MODE = False
    NODE_NAMES_FILE = "/tmp/test_nodes.json"

sys.modules['config'] = MockConfig()

from node_manager import NodeManager
from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor

def create_test_database():
    """Create a temporary test database with neighbor data"""
    # Create temporary database
    db_path = tempfile.mktemp(suffix='.db')
    
    # Initialize persistence
    persistence = TrafficPersistence(db_path=db_path)
    
    # Add test neighbor data
    # Node !12345678 (close) has 2 neighbors
    persistence.save_neighbor_info('!12345678', [
        {'node_id': 0x11111111, 'snr': 8.5, 'last_rx_time': 100, 'node_broadcast_interval': 900},
        {'node_id': 0x22222222, 'snr': 6.2, 'last_rx_time': 200, 'node_broadcast_interval': 900}
    ])
    
    # Node !87654321 (far - Paris) has 1 neighbor
    persistence.save_neighbor_info('!87654321', [
        {'node_id': 0x33333333, 'snr': 5.1, 'last_rx_time': 150, 'node_broadcast_interval': 900}
    ])
    
    # Node !abcdef00 (medium - Lyon) has 3 neighbors
    persistence.save_neighbor_info('!abcdef00', [
        {'node_id': 0x44444444, 'snr': 9.2, 'last_rx_time': 180, 'node_broadcast_interval': 900},
        {'node_id': 0x55555555, 'snr': 7.8, 'last_rx_time': 190, 'node_broadcast_interval': 900},
        {'node_id': 0x66666666, 'snr': 4.3, 'last_rx_time': 210, 'node_broadcast_interval': 900}
    ])
    
    # Node !11111111 (no GPS) has 1 neighbor
    persistence.save_neighbor_info('!11111111', [
        {'node_id': 0x77777777, 'snr': 6.7, 'last_rx_time': 170, 'node_broadcast_interval': 900}
    ])
    
    return persistence, db_path

def setup_node_manager():
    """Setup node manager with test nodes"""
    node_manager = NodeManager()
    
    # Set bot position (Besançon, France)
    node_manager.bot_position = (47.2380, 6.0240)
    
    # Add test nodes with positions
    # Node 1: Close (Besançon area - ~1.4km)
    node_manager.node_names[0x12345678] = {
        'name': 'CloseNode',
        'lat': 47.2500,
        'lon': 6.0300,
        'alt': 300,
        'last_update': 1234567890
    }
    
    # Node 2: Far (Paris - ~327km)
    node_manager.node_names[0x87654321] = {
        'name': 'FarNode_Paris',
        'lat': 48.8566,
        'lon': 2.3522,
        'alt': 35,
        'last_update': 1234567890
    }
    
    # Node 3: Medium distance (Lyon - ~187km)
    node_manager.node_names[0xABCDEF00] = {
        'name': 'MediumNode_Lyon',
        'lat': 45.7640,
        'lon': 4.8357,
        'alt': 170,
        'last_update': 1234567890
    }
    
    # Node 4: No GPS position
    node_manager.node_names[0x11111111] = {
        'name': 'NoGPSNode',
        'lat': None,
        'lon': None,
        'alt': None,
        'last_update': 1234567890
    }
    
    return node_manager

def test_neighbors_report_filtering():
    """Test that get_neighbors_report filters nodes by distance"""
    print("=" * 70)
    print("Integration Test: /neighbors Distance Filtering")
    print("=" * 70)
    
    # Setup
    print("\n📋 Setting up test environment...")
    persistence, db_path = create_test_database()
    node_manager = setup_node_manager()
    traffic_monitor = TrafficMonitor(node_manager)
    traffic_monitor.persistence = persistence
    
    print(f"✅ Test database created: {db_path}")
    print(f"✅ Bot position: {node_manager.bot_position}")
    print(f"✅ Max distance: 100km")
    
    # Test 1: Compact format (LoRa)
    print("\n" + "=" * 70)
    print("Test 1: Compact Format (LoRa - 180 chars)")
    print("=" * 70)
    
    report_compact = traffic_monitor.get_neighbors_report(
        node_filter=None,
        compact=True,
        max_distance_km=100
    )
    
    print("\n📝 Generated Report (compact):")
    print("-" * 70)
    print(report_compact)
    print("-" * 70)
    
    # Verify compact report
    assert 'CloseNod' in report_compact or '!12345678' in report_compact, \
        "CloseNode should be in report (within 100km)"
    assert 'FarNode' not in report_compact and '!87654321' not in report_compact, \
        "FarNode should NOT be in report (beyond 100km)"
    assert 'MediumNode' not in report_compact and '!abcdef00' not in report_compact, \
        "MediumNode should NOT be in report (beyond 100km)"
    
    print("\n✅ Compact format filtering works correctly")
    
    # Test 2: Detailed format (Telegram)
    print("\n" + "=" * 70)
    print("Test 2: Detailed Format (Telegram)")
    print("=" * 70)
    
    report_detailed = traffic_monitor.get_neighbors_report(
        node_filter=None,
        compact=False,
        max_distance_km=100
    )
    
    print("\n📝 Generated Report (detailed):")
    print("-" * 70)
    print(report_detailed)
    print("-" * 70)
    
    # Verify detailed report
    assert 'CloseNode' in report_detailed or '!12345678' in report_detailed, \
        "CloseNode should be in detailed report (within 100km)"
    assert 'FarNode' not in report_detailed and '!87654321' not in report_detailed, \
        "FarNode should NOT be in detailed report (beyond 100km)"
    assert 'MediumNode' not in report_detailed and '!abcdef00' not in report_detailed, \
        "MediumNode should NOT be in detailed report (beyond 100km)"
    assert 'NoGPSNode' in report_detailed or '!11111111' in report_detailed, \
        "NoGPSNode should be in report (no GPS to filter)"
    
    print("\n✅ Detailed format filtering works correctly")
    
    # Test 3: Custom distance threshold
    print("\n" + "=" * 70)
    print("Test 3: Custom Distance Threshold (200km)")
    print("=" * 70)
    
    report_200km = traffic_monitor.get_neighbors_report(
        node_filter=None,
        compact=False,
        max_distance_km=200
    )
    
    print("\n📝 Generated Report (200km threshold):")
    print("-" * 70)
    print(report_200km)
    print("-" * 70)
    
    # With 200km threshold, MediumNode (187km) should be included
    assert 'CloseNode' in report_200km or '!12345678' in report_200km, \
        "CloseNode should be in report"
    assert 'MediumNode' in report_200km or '!abcdef00' in report_200km, \
        "MediumNode should be in report (within 200km)"
    assert 'FarNode' not in report_200km and '!87654321' not in report_200km, \
        "FarNode should NOT be in report (beyond 200km)"
    
    print("\n✅ Custom distance threshold works correctly")
    
    # Test 4: Node-specific filter
    print("\n" + "=" * 70)
    print("Test 4: Node-Specific Filter")
    print("=" * 70)
    
    report_filtered = traffic_monitor.get_neighbors_report(
        node_filter='Close',
        compact=False,
        max_distance_km=100
    )
    
    print("\n📝 Generated Report (filter='Close'):")
    print("-" * 70)
    print(report_filtered)
    print("-" * 70)
    
    # Should only show CloseNode
    assert 'CloseNode' in report_filtered, "Should show CloseNode"
    assert 'FarNode' not in report_filtered, "Should not show FarNode"
    assert 'MediumNode' not in report_filtered, "Should not show MediumNode"
    
    print("\n✅ Node-specific filtering works correctly")
    
    # Cleanup
    print("\n🧹 Cleaning up test database...")
    persistence.conn.close()
    os.unlink(db_path)
    
    print("\n" + "=" * 70)
    print("✅ All integration tests passed!")
    print("=" * 70)
    print("\nSummary:")
    print("  • Distance filtering removes nodes >100km ✅")
    print("  • Nodes without GPS position are kept ✅")
    print("  • Custom distance threshold works ✅")
    print("  • Node-specific filters still work ✅")
    print("  • Both compact and detailed formats work ✅")
    
    return True

if __name__ == "__main__":
    try:
        success = test_neighbors_report_filtering()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
