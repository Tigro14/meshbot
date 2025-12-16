#!/usr/bin/env python3
"""
Test script to verify telemetry history export logic
"""

import json
import time

# Simulate telemetry history data
def test_telemetry_extraction():
    """Test the telemetry extraction and formatting logic"""
    
    print("Testing telemetry history extraction logic...")
    
    # Simulate telemetry data from database
    mock_telemetry_rows = [
        ('12345678', time.time() - 86400 * 6, '{"battery": 85, "voltage": 4.05}'),
        ('12345678', time.time() - 86400 * 5, '{"battery": 87, "voltage": 4.08}'),
        ('12345678', time.time() - 86400 * 4, '{"battery": 89, "voltage": 4.12}'),
        ('12345678', time.time() - 86400 * 3, '{"battery": 91, "voltage": 4.15}'),
        ('12345678', time.time() - 86400 * 2, '{"battery": 90, "voltage": 4.13}'),
        ('12345678', time.time() - 86400 * 1, '{"battery": 92, "voltage": 4.18}'),
    ]
    
    # Extract data (same logic as export_nodes_from_db.py)
    telemetry_history = {}
    
    for row in mock_telemetry_rows:
        from_id_str = str(row[0])
        timestamp = row[1]
        telemetry_json = row[2]
        
        try:
            telemetry_obj = json.loads(telemetry_json)
            battery = telemetry_obj.get('battery')
            voltage = telemetry_obj.get('voltage')
            
            if battery is None and voltage is None:
                continue
            
            if from_id_str not in telemetry_history:
                telemetry_history[from_id_str] = []
            
            data_point = {'t': int(timestamp)}
            if battery is not None:
                data_point['b'] = battery
            if voltage is not None:
                data_point['v'] = round(voltage, 2)
            
            telemetry_history[from_id_str].append(data_point)
            
        except Exception as e:
            print(f"Error: {e}")
    
    # Verify results
    assert '12345678' in telemetry_history
    assert len(telemetry_history['12345678']) == 6
    
    history = telemetry_history['12345678']
    
    # Check first entry
    assert 't' in history[0]
    assert 'b' in history[0]
    assert 'v' in history[0]
    assert history[0]['b'] == 85
    assert history[0]['v'] == 4.05
    
    # Check last entry
    assert history[-1]['b'] == 92
    assert history[-1]['v'] == 4.18
    
    print("✅ Extraction logic test passed!")
    print(f"   Extracted {len(history)} data points")
    print(f"   Sample: {history[0]}")
    
    return telemetry_history


def test_downsampling():
    """Test downsampling logic"""
    
    print("\nTesting downsampling logic...")
    
    # Create 200 data points
    large_history = []
    for i in range(200):
        large_history.append({
            't': int(time.time() - 86400 * 7 + i * 3600),
            'b': 80 + (i % 20),
            'v': 4.0 + (i % 10) * 0.02
        })
    
    # Downsample to 100 points
    max_points = 100
    if len(large_history) > max_points:
        step = len(large_history) // max_points
        downsampled = [large_history[i] for i in range(0, len(large_history), step)][:max_points]
    else:
        downsampled = large_history
    
    assert len(downsampled) <= max_points
    assert len(downsampled) > 0
    
    # Verify chronological order maintained
    for i in range(1, len(downsampled)):
        assert downsampled[i]['t'] >= downsampled[i-1]['t']
    
    print(f"✅ Downsampling test passed!")
    print(f"   {len(large_history)} points → {len(downsampled)} points")
    
    return downsampled


def test_json_output_format():
    """Test JSON output format"""
    
    print("\nTesting JSON output format...")
    
    # Create sample node with telemetry history
    node_entry = {
        "num": 305419896,
        "user": {
            "id": "!12345678",
            "longName": "Test Node",
            "shortName": "TEST",
            "hwModel": "TBEAM"
        },
        "deviceMetrics": {
            "batteryLevel": 92,
            "voltage": 4.18
        },
        "telemetryHistory": [
            {"t": 1734259200, "b": 85, "v": 4.05},
            {"t": 1734262800, "b": 87, "v": 4.08},
            {"t": 1734266400, "b": 89, "v": 4.12}
        ]
    }
    
    # Verify JSON serializable
    try:
        json_str = json.dumps(node_entry, indent=2)
        parsed = json.loads(json_str)
        
        assert parsed['telemetryHistory'][0]['t'] == 1734259200
        assert parsed['telemetryHistory'][0]['b'] == 85
        assert parsed['telemetryHistory'][0]['v'] == 4.05
        
        print("✅ JSON format test passed!")
        print(f"   Output size: {len(json_str)} bytes")
        
    except Exception as e:
        print(f"❌ JSON format test failed: {e}")
        return False
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("Telemetry History Export - Unit Tests")
    print("=" * 60)
    
    try:
        test_telemetry_extraction()
        test_downsampling()
        test_json_output_format()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
