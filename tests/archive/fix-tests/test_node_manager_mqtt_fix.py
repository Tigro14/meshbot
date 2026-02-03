#!/usr/bin/env python3
"""
Test script for NodeManager methods used by MQTT Neighbor Collector

This test validates the fix for the AttributeError:
"'NodeManager' object has no attribute 'get_node_data'"

The MQTT neighbor collector (mqtt_neighbor_collector.py line 458) requires:
1. get_node_data(node_id) - returns dict with 'latitude', 'longitude' keys
2. get_reference_position() - returns tuple (lat, lon)
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create minimal config if it doesn't exist (for testing)
if not os.path.exists('config.py'):
    print("ℹ️  Creating minimal config.py for testing...")
    with open('config.py', 'w') as f:
        f.write("# Minimal config for testing\n")
        f.write("DEBUG_MODE = False\n")
        f.write("NODE_NAMES_FILE = 'node_names.json'\n")
    
    # Clean up after tests
    import atexit
    def cleanup():
        if os.path.exists('config.py'):
            os.remove('config.py')
            print("ℹ️  Cleaned up temporary config.py")
    atexit.register(cleanup)

def test_get_node_data():
    """Test get_node_data method"""
    print("\n" + "="*60)
    print("TEST: get_node_data method")
    print("="*60)
    
    from node_manager import NodeManager
    nm = NodeManager()
    
    # Test 1: Non-existent node
    result = nm.get_node_data(12345)
    assert result is None, "Should return None for non-existent node"
    print("✅ Test 1 passed: Returns None for non-existent node")
    
    # Test 2: Node without position
    nm.node_names[12345] = {
        'name': 'TestNode',
        'lat': None,
        'lon': None,
        'alt': None,
        'last_update': None
    }
    result = nm.get_node_data(12345)
    assert result is None, "Should return None when node has no position"
    print("✅ Test 2 passed: Returns None for node without GPS position")
    
    # Test 3: Node with valid position
    nm.node_names[12345] = {
        'name': 'TestNode',
        'lat': 47.123,
        'lon': 6.456,
        'alt': 100,
        'last_update': 1234567890
    }
    result = nm.get_node_data(12345)
    assert result is not None, "Should return data when node has position"
    assert result['latitude'] == 47.123, "latitude should match internal lat"
    assert result['longitude'] == 6.456, "longitude should match internal lon"
    assert result['altitude'] == 100, "altitude should match"
    assert result['name'] == 'TestNode', "name should match"
    print("✅ Test 3 passed: Returns correct data structure with lat/lon mapped to latitude/longitude")
    
    return True

def test_get_reference_position():
    """Test get_reference_position method"""
    print("\n" + "="*60)
    print("TEST: get_reference_position method")
    print("="*60)
    
    from node_manager import NodeManager
    nm = NodeManager()
    
    # Test 1: No bot position configured
    nm.bot_position = None
    result = nm.get_reference_position()
    assert result is None, "Should return None when bot_position not set"
    print("✅ Test 1 passed: Returns None when BOT_POSITION not configured")
    
    # Test 2: Valid bot position
    nm.bot_position = (47.5, 6.8)
    result = nm.get_reference_position()
    assert result == (47.5, 6.8), "Should return bot_position tuple"
    assert isinstance(result, tuple), "Should return a tuple"
    assert len(result) == 2, "Should return 2-element tuple"
    print("✅ Test 2 passed: Returns correct (latitude, longitude) tuple")
    
    return True

def test_mqtt_collector_scenario():
    """Simulate the exact scenario from mqtt_neighbor_collector.py"""
    print("\n" + "="*60)
    print("TEST: MQTT Neighbor Collector scenario")
    print("="*60)
    
    from node_manager import NodeManager
    
    # Simulate the scenario from the error log
    # Dec 04 09:09:12 DietPi meshtastic-bot[2292925]: [DEBUG] 👥 Erreur calcul distance pour !a2e99ad8
    nm = NodeManager()
    node_id = 0xa2e99ad8  # The node ID from the log
    node_id_str = f"!{node_id:08x}"
    
    print(f"Simulating MQTT neighbor collector for node: {node_id_str}")
    
    # This is the exact code path from mqtt_neighbor_collector.py lines 455-476
    should_log = True
    distance_km = None
    
    try:
        # This was failing with AttributeError before the fix
        node_data = nm.get_node_data(node_id)
        print(f"✅ get_node_data() method exists and returns: {node_data}")
        
        if node_data and 'latitude' in node_data and 'longitude' in node_data:
            node_lat = node_data['latitude']
            node_lon = node_data['longitude']
            
            # Get reference position (bot)
            ref_pos = nm.get_reference_position()
            print(f"✅ get_reference_position() method exists and returns: {ref_pos}")
            
            if ref_pos and ref_pos[0] != 0 and ref_pos[1] != 0:
                ref_lat, ref_lon = ref_pos
                distance_km = nm.haversine_distance(
                    ref_lat, ref_lon, node_lat, node_lon
                )
                
                # Filter: only display if <100km
                if distance_km >= 100:
                    should_log = False
                    
                print(f"✅ Distance calculation works: {distance_km:.1f}km")
            else:
                print("ℹ️  Bot position not configured (expected in test)")
        else:
            print("ℹ️  Node has no position data (expected for this test)")
            
        print("✅ No AttributeError - the bug is fixed!")
        return True
        
    except AttributeError as e:
        print(f"❌ FAILED: {e}")
        print("This is the original bug that should be fixed")
        return False
    except Exception as e:
        print(f"⚠️  Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MQTT Neighbor Collector - NodeManager Methods Test Suite")
    print("="*60)
    print("\nTesting fix for AttributeError:")
    print("'NodeManager' object has no attribute 'get_node_data'")
    
    try:
        tests_passed = []
        
        # Run tests
        tests_passed.append(test_get_node_data())
        tests_passed.append(test_get_reference_position())
        tests_passed.append(test_mqtt_collector_scenario())
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        if all(tests_passed):
            print("🎉 All tests PASSED!")
            print("\nThe AttributeError is fixed. The MQTT neighbor collector")
            print("can now call get_node_data() and get_reference_position()")
            print("on NodeManager without errors.")
            return 0
        else:
            print("❌ Some tests FAILED")
            return 1
            
    except Exception as e:
        print(f"\n❌ Fatal error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
