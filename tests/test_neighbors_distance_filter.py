#!/usr/bin/env python3
"""
Test script to verify the distance filtering in get_neighbors_report()
"""

import sys
import os

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock config to avoid import errors
class MockConfig:
    NEIGHBORS_MAX_DISTANCE_KM = 100
    DEBUG_MODE = True

sys.modules['config'] = MockConfig()

from node_manager import NodeManager
from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor

def test_distance_filtering():
    """Test that nodes beyond max_distance_km are filtered"""
    print("Testing neighbor distance filtering...")
    
    # Create mock components
    node_manager = NodeManager()
    
    # Set bot position (example: somewhere in France)
    node_manager.bot_position = (47.2380, 6.0240)  # Besançon, France
    
    # Add some test nodes with positions
    # Node 1: Close (Besançon area - ~10km)
    node_manager.node_names[0x12345678] = {
        'name': 'CloseNode',
        'lat': 47.2500,
        'lon': 6.0300,
        'alt': 300,
        'last_update': 1234567890
    }
    
    # Node 2: Far (Paris - ~300km)
    node_manager.node_names[0x87654321] = {
        'name': 'FarNode',
        'lat': 48.8566,
        'lon': 2.3522,
        'alt': 35,
        'last_update': 1234567890
    }
    
    # Node 3: Medium distance (Lyon - ~150km)
    node_manager.node_names[0xABCDEF00] = {
        'name': 'MediumNode',
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
    
    # Test distance calculations
    print("\n=== Distance Calculations ===")
    
    for node_id, node_data in node_manager.node_names.items():
        if node_data['lat'] is not None and node_data['lon'] is not None:
            distance = node_manager.get_node_distance(node_id)
            print(f"Node {node_data['name']}: {distance:.1f}km from bot")
    
    # Test filtering logic
    print("\n=== Filter Logic Test ===")
    max_distance = 100
    
    ref_lat, ref_lon = node_manager.bot_position
    print(f"Bot position: ({ref_lat}, {ref_lon})")
    print(f"Max distance: {max_distance}km\n")
    
    for node_id, node_data in node_manager.node_names.items():
        node_name = node_data['name']
        node_lat = node_data.get('lat')
        node_lon = node_data.get('lon')
        
        if node_lat is not None and node_lon is not None:
            distance = node_manager.haversine_distance(ref_lat, ref_lon, node_lat, node_lon)
            
            if distance <= max_distance:
                print(f"✅ KEEP: {node_name} at {distance:.1f}km (within {max_distance}km)")
            else:
                print(f"❌ FILTER: {node_name} at {distance:.1f}km (beyond {max_distance}km)")
        else:
            print(f"⚠️ KEEP: {node_name} (no GPS position)")
    
    print("\n=== Test Complete ===")
    print("Expected results:")
    print("  - CloseNode should be kept (<100km)")
    print("  - FarNode should be filtered (>100km)")
    print("  - MediumNode should be filtered (>100km)")
    print("  - NoGPSNode should be kept (no position to filter)")

if __name__ == "__main__":
    test_distance_filtering()
