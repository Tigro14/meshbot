# Telemetry Storage Implementation

## Overview

This implementation adds battery and environment telemetry storage to the SQLite database, enabling display of telemetry data in the map.html node popups.

## Features

### Device Metrics (Battery)
- **Battery Level**: Percentage (0-100%)
- **Battery Voltage**: Voltage in volts

### Environment Metrics
- **Temperature**: Celsius
- **Humidity**: Relative humidity percentage
- **Barometric Pressure**: Pressure in Pascals
- **Air Quality**: IAQ (Indoor Air Quality) index

## Database Schema

### Table: `node_stats`

New columns added:

```sql
last_battery_level INTEGER         -- Battery percentage (0-100)
last_battery_voltage REAL          -- Battery voltage in volts
last_telemetry_update REAL         -- Timestamp of last telemetry update
last_temperature REAL              -- Temperature in Celsius
last_humidity REAL                 -- Relative humidity percentage
last_pressure REAL                 -- Barometric pressure in Pascals
last_air_quality REAL              -- Indoor Air Quality (IAQ) index
```

### Migration

The database automatically migrates when starting the bot. The migration:
1. Creates the `node_stats` table if it doesn't exist
2. Adds telemetry columns to existing `node_stats` tables
3. Handles both new and existing databases gracefully

## Data Flow

### 1. Collection (traffic_monitor.py)

When a `TELEMETRY_APP` packet is received:

```python
# Device metrics (battery, voltage, channel utilization)
if 'deviceMetrics' in telemetry:
    metrics = telemetry['deviceMetrics']
    tel_stats['last_battery'] = metrics.get('batteryLevel')
    tel_stats['last_voltage'] = metrics.get('voltage')
    tel_stats['last_channel_util'] = metrics.get('channelUtilization')
    tel_stats['last_air_util'] = metrics.get('airUtilTx')

# Environment metrics (temperature, humidity, pressure, air quality)
if 'environmentMetrics' in telemetry:
    env_metrics = telemetry['environmentMetrics']
    tel_stats['last_temperature'] = env_metrics.get('temperature')
    tel_stats['last_humidity'] = env_metrics.get('relativeHumidity')
    tel_stats['last_pressure'] = env_metrics.get('barometricPressure')
    tel_stats['last_air_quality'] = env_metrics.get('iaq')
```

### 2. Storage (traffic_persistence.py)

Telemetry data is saved to SQLite in `save_node_stats()`:

```python
cursor.execute('''
    INSERT OR REPLACE INTO node_stats (
        ..., 
        last_battery_level, last_battery_voltage, last_telemetry_update,
        last_temperature, last_humidity, last_pressure, last_air_quality
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ...)
''')
```

### 3. Export (map/export_nodes_from_db.py)

Telemetry data is included in the JSON export:

```python
# Query telemetry data
cursor.execute("""
    SELECT node_id, last_battery_level, last_battery_voltage, last_telemetry_update,
           last_temperature, last_humidity, last_pressure, last_air_quality
    FROM node_stats
    WHERE last_battery_level IS NOT NULL OR last_battery_voltage IS NOT NULL
       OR last_temperature IS NOT NULL ...
""")

# Add to node entry
node_entry["deviceMetrics"] = {
    "batteryLevel": battery_level,
    "voltage": battery_voltage
}

node_entry["environmentMetrics"] = {
    "temperature": temperature,
    "relativeHumidity": humidity,
    "barometricPressure": pressure,
    "iaq": air_quality
}
```

### 4. Display (map.html)

The map.html receives telemetry data in the JSON export and can display it in node popups:

```javascript
// Example JSON structure
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": {...},
    "position": {...},
    "deviceMetrics": {
      "batteryLevel": 85,
      "voltage": 12.5
    },
    "environmentMetrics": {
      "temperature": 22.5,
      "relativeHumidity": 65.0,
      "barometricPressure": 101325.0,
      "iaq": 50
    }
  }
}
```

## Testing

Run the test suite to verify implementation:

```bash
python3 test_telemetry_storage.py
```

### Test Coverage

1. **Battery Telemetry Storage** - Verifies battery level and voltage storage
2. **Environment Metrics Storage** - Verifies temp, humidity, pressure, IAQ storage
3. **Combined Telemetry Storage** - Verifies both device and environment metrics coexist
4. **TrafficMonitor Extraction** - Verifies telemetry extraction from TELEMETRY_APP packets

## Usage Example

### Sending Telemetry via Meshtastic

Device metrics (battery):
```python
from meshtastic.protobuf import telemetry_pb2

device_telemetry = telemetry_pb2.Telemetry()
device_telemetry.device_metrics.battery_level = 85
device_telemetry.device_metrics.voltage = 12.5

interface.sendData(device_telemetry, portNum=portnums_pb2.TELEMETRY_APP)
```

Environment metrics (temperature, humidity, pressure):
```python
env_telemetry = telemetry_pb2.Telemetry()
env_telemetry.environment_metrics.temperature = 22.5
env_telemetry.environment_metrics.relative_humidity = 65.0
env_telemetry.environment_metrics.barometric_pressure = 101325.0
env_telemetry.environment_metrics.iaq = 50

interface.sendData(env_telemetry, portNum=portnums_pb2.TELEMETRY_APP)
```

**Note**: Meshtastic uses a `oneof` field, so device metrics and environment metrics must be sent in separate packets.

### Exporting for Map

```bash
cd map/
./export_nodes_from_db.py > info.json
```

The `info.json` will include telemetry data for all nodes that have sent telemetry packets.

## Troubleshooting

### Telemetry not showing in database

1. Check if node is sending `TELEMETRY_APP` packets
2. Verify packets are being received (check bot logs)
3. Ensure telemetry data is not being filtered (check `my_node_id` parameter)

### Environment metrics not showing

Verify the packet contains `environmentMetrics` field:
```python
'telemetry': {
    'environmentMetrics': {
        'temperature': 22.5,
        # ... other fields
    }
}
```

### Export doesn't include telemetry

1. Check that `node_stats` table has telemetry data:
   ```sql
   SELECT node_id, last_battery_level, last_temperature 
   FROM node_stats 
   WHERE last_battery_level IS NOT NULL OR last_temperature IS NOT NULL;
   ```

2. Verify export script is querying telemetry columns
3. Check that telemetry data timestamp is recent (not too old)

## Related Files

- `traffic_persistence.py` - Database schema and persistence logic
- `traffic_monitor.py` - Telemetry extraction from packets
- `map/export_nodes_from_db.py` - JSON export with telemetry
- `test_telemetry_storage.py` - Test suite
- `main_bot.py` - Example of sending telemetry packets (ESPHome integration)

## Future Enhancements

Potential improvements:
- Add telemetry history (time-series data)
- Add telemetry graphs in map popups
- Add telemetry alerts (low battery, high temperature)
- Add telemetry aggregation (min/max/avg over time)
