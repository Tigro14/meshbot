# Telemetry Display Fix Summary

## Problem
Node telemetry data (battery level, voltage, temperature, humidity, pressure) was not appearing in the map.html visualization, despite being stored in the traffic_history.db database.

## Root Cause
The `export_nodes_from_db.py` script had a critical bug:
- Line 77: `telemetry_data = {}` dictionary was initialized
- Line 131: `node_stats_raw` loaded from database with all telemetry
- **Missing**: Code to populate `telemetry_data` from `node_stats_raw`
- Lines 328-351: Code tried to use `telemetry_data[node_id_str]` but it was always empty

## Solution
Added telemetry extraction logic after line 143 (24 new lines):

```python
# Extract telemetry data for map display
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
```

## Impact

### Before Fix
```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": {
      "id": "!16fa4fdc",
      "longName": "TestNode1",
      "shortName": "TST1"
    },
    "position": {
      "latitude": 48.8566,
      "longitude": 2.3522
    }
    // ❌ No deviceMetrics
    // ❌ No environmentMetrics
  }
}
```

### After Fix
```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": {
      "id": "!16fa4fdc",
      "longName": "TestNode1",
      "shortName": "TST1"
    },
    "position": {
      "latitude": 48.8566,
      "longitude": 2.3522
    },
    "deviceMetrics": {
      "batteryLevel": 85,
      "voltage": 4.15
    },
    "environmentMetrics": {
      "temperature": 22.5,
      "relativeHumidity": 65.0,
      "barometricPressure": 1013.25
    }
  }
}
```

## Verification

### How to Test
Run the `infoup_db.sh` script to regenerate map data:
```bash
cd /home/dietpi/bot/map
./infoup_db.sh
```

Check the generated `info.json` for telemetry data:
```bash
# Look for deviceMetrics and environmentMetrics in the JSON
jq '.["Nodes in mesh"] | to_entries[] | select(.value.deviceMetrics) | {key: .key, battery: .value.deviceMetrics.batteryLevel}' info.json
```

### Map Display
Open `map.html` in a browser and click on any node marker. The popup should now show:
- 🔋 Battery level (%)
- ⚡ Voltage (V)
- 🌡️ Temperature (°C)
- 💧 Humidity (%)
- 🌫️ Pressure (hPa)

## Testing
Two comprehensive tests added:
1. **test_telemetry_export.py** - Unit test for telemetry extraction
2. **test_telemetry_map_integration.py** - End-to-end integration test

Both tests pass ✅

## Files Modified
- `map/export_nodes_from_db.py` - Added telemetry data population (24 lines)

## Benefits
- ✅ Node telemetry now visible in map popups
- ✅ Battery levels displayed for nodes with telemetry
- ✅ Environment sensors (temperature, humidity, pressure) shown
- ✅ Better network monitoring and troubleshooting
- ✅ No breaking changes - gracefully handles missing telemetry
