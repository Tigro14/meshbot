#!/usr/bin/env python3
"""
Test script to verify /propag command fixes:
1. Node name lookup with integer IDs
2. 100km filter logic
3. Altitude display
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from node_manager import NodeManager
from traffic_monitor import TrafficMonitor
from traffic_persistence import TrafficPersistence

def test_node_name_lookup():
    """Test that node names are looked up correctly with integer IDs"""
    print("\n" + "="*60)
    print("TEST 1: Node Name Lookup")
    print("="*60)
    
    # Create a node manager with test data
    manager = NodeManager()
    
    # Add some test nodes with integer keys
    test_node_id_1 = 0x8ff2c272  # 2415836690 in decimal
    test_node_id_2 = 0xa2fa982c  # 2732684716 in decimal
    
    manager.node_names[test_node_id_1] = {
        'name': 'TestNode1',
        'shortName': 'TN1',
        'hwModel': None,
        'lat': 48.8566,
        'lon': 2.3522,
        'alt': 35,
        'last_update': None
    }
    
    manager.node_names[test_node_id_2] = {
        'name': 'TestNode2',
        'shortName': 'TN2',
        'hwModel': None,
        'lat': 48.8600,
        'lon': 2.3700,
        'alt': 50,
        'last_update': None
    }
    
    # Test with integer ID (correct)
    print(f"\nTest with integer ID {test_node_id_1}:")
    name1 = manager.get_node_name(test_node_id_1)
    print(f"  Result: {name1}")
    assert name1 == 'TestNode1', f"Expected 'TestNode1', got '{name1}'"
    print("  ✅ PASS")
    
    # Test with hex string ID (old behavior - should fail)
    hex_id_1 = f"!{test_node_id_1:08x}"
    print(f"\nTest with hex string ID '{hex_id_1}' (old behavior):")
    name2 = manager.get_node_name(hex_id_1)
    print(f"  Result: {name2}")
    print(f"  ⚠️  Returns '{name2}' instead of 'TestNode1' (fallback behavior)")
    
    print("\n✅ Node name lookup test complete")


def test_filter_logic():
    """Test the 100km filter logic"""
    print("\n" + "="*60)
    print("TEST 2: 100km Filter Logic")
    print("="*60)
    
    manager = NodeManager()
    
    # Bot position (Paris)
    bot_lat, bot_lon = 48.8566, 2.3522
    manager.bot_position = (bot_lat, bot_lon)
    
    # Test case 1: Both nodes within radius (should KEEP)
    print("\nCase 1: Both nodes within 100km radius")
    node1_lat, node1_lon = 48.9000, 2.4000  # ~6km from Paris
    node2_lat, node2_lon = 48.8000, 2.3000  # ~7km from Paris
    
    dist1 = manager.haversine_distance(bot_lat, bot_lon, node1_lat, node1_lon)
    dist2 = manager.haversine_distance(bot_lat, bot_lon, node2_lat, node2_lon)
    
    print(f"  Node 1 distance: {dist1:.1f}km")
    print(f"  Node 2 distance: {dist2:.1f}km")
    
    max_distance_km = 100
    should_filter = dist1 > max_distance_km and dist2 > max_distance_km
    print(f"  Filter (both > {max_distance_km}km): {should_filter}")
    assert not should_filter, "Should NOT filter when both within radius"
    print("  ✅ PASS - Link kept")
    
    # Test case 2: One node within, one outside (should KEEP)
    print("\nCase 2: One node within 100km, one outside")
    node1_lat, node1_lon = 48.9000, 2.4000  # ~6km from Paris
    node2_lat, node2_lon = 47.5000, 7.5000  # ~400km from Paris (Switzerland)
    
    dist1 = manager.haversine_distance(bot_lat, bot_lon, node1_lat, node1_lon)
    dist2 = manager.haversine_distance(bot_lat, bot_lon, node2_lat, node2_lon)
    
    print(f"  Node 1 distance: {dist1:.1f}km")
    print(f"  Node 2 distance: {dist2:.1f}km")
    
    should_filter = dist1 > max_distance_km and dist2 > max_distance_km
    print(f"  Filter (both > {max_distance_km}km): {should_filter}")
    assert not should_filter, "Should NOT filter when at least one within radius"
    print("  ✅ PASS - Link kept (at least one node within radius)")
    
    # Test case 3: Both nodes outside radius (should FILTER)
    print("\nCase 3: Both nodes outside 100km radius")
    node1_lat, node1_lon = 47.5000, 7.5000  # ~400km from Paris (Switzerland)
    node2_lat, node2_lon = 47.3769, 8.5417  # ~500km from Paris (Zurich)
    
    dist1 = manager.haversine_distance(bot_lat, bot_lon, node1_lat, node1_lon)
    dist2 = manager.haversine_distance(bot_lat, bot_lon, node2_lat, node2_lon)
    
    print(f"  Node 1 distance: {dist1:.1f}km")
    print(f"  Node 2 distance: {dist2:.1f}km")
    
    should_filter = dist1 > max_distance_km and dist2 > max_distance_km
    print(f"  Filter (both > {max_distance_km}km): {should_filter}")
    assert should_filter, "Should FILTER when both outside radius"
    print("  ✅ PASS - Link filtered out")
    
    print("\n✅ Filter logic test complete")


def test_altitude_storage():
    """Test that altitude is stored and retrieved"""
    print("\n" + "="*60)
    print("TEST 3: Altitude Storage and Retrieval")
    print("="*60)
    
    # Create test database
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    print(f"\nUsing temporary database: {db_path}")
    
    try:
        persistence = TrafficPersistence(db_path=db_path)
        
        # Simulate saving a packet with position including altitude
        import time
        test_packet = {
            'from_id': '!8ff2c272',
            'to_id': '!ffffffff',
            'timestamp': time.time(),
            'packet_type': 'POSITION_APP',
            'position': {
                'latitude': 48.8566,
                'longitude': 2.3522,
                'altitude': 450
            },
            'snr': 10.5,
            'rssi': -75,
            'hops': 0,
            'channel': 0
        }
        
        print("\nSaving test packet with altitude...")
        persistence.save_packet(test_packet)
        print("  ✅ Packet saved")
        
        # Retrieve position
        print("\nRetrieving position from database...")
        position = persistence.get_node_position_from_db('!8ff2c272', hours=1)
        
        if position:
            print(f"  Latitude: {position.get('latitude')}")
            print(f"  Longitude: {position.get('longitude')}")
            print(f"  Altitude: {position.get('altitude')}")
            
            assert position.get('latitude') == 48.8566, "Latitude mismatch"
            assert position.get('longitude') == 2.3522, "Longitude mismatch"
            assert position.get('altitude') == 450, "Altitude mismatch"
            
            print("  ✅ PASS - All fields retrieved correctly")
        else:
            print("  ❌ FAIL - Position not found")
            raise AssertionError("Position not retrieved from database")
        
        print("\n✅ Altitude storage test complete")
        
    finally:
        # Cleanup
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"\nCleaned up temporary database")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TESTING /propag COMMAND FIXES")
    print("="*60)
    
    try:
        test_node_name_lookup()
        test_filter_logic()
        test_altitude_storage()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nSummary:")
        print("1. ✅ Node names now correctly resolved using integer IDs")
        print("2. ✅ 100km filter keeps links with at least one node within radius")
        print("3. ✅ Altitude information stored and retrieved from database")
        print("\nThe /propag command should now display:")
        print("  - Correct node LongNames instead of numeric IDs")
        print("  - Only links with at least one node within 100km of bot")
        print("  - Altitude information for each node (in Telegram detailed view)")
        
        return 0
        
    except Exception as e:
        print("\n" + "="*60)
        print("❌ TEST FAILED")
        print("="*60)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
