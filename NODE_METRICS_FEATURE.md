# Node Metrics Display Feature

## Overview

This feature adds collected metrics to each node's information popup on the map.html visualization.

## Problem Solved

Previously, the map.html only displayed basic node information (ID, hops, SNR, neighbors). The bot was collecting extensive metrics in the `node_stats` database table, but these were not displayed on the map.

## Solution

### 1. Data Export Enhancement (`export_nodes_from_db.py`)

The export script now loads and exports node statistics from the `node_stats` table:

```python
# Load node_stats data for metrics display
node_stats_raw = persistence.load_node_stats()
node_stats_data = {}
for node_id_str, stats in node_stats_raw.items():
    node_stats_data[str(node_id_str)] = {
        'total_packets': stats.get('total_packets', 0),
        'total_bytes': stats.get('total_bytes', 0),
        'by_type': dict(stats.get('by_type', {})),
        'message_stats': stats.get('message_stats', {}),
        'telemetry_stats': stats.get('telemetry_stats', {}),
        'position_stats': stats.get('position_stats', {}),
        'routing_stats': stats.get('routing_stats', {})
    }
```

Each node entry in the exported JSON now includes a `nodeStats` field:

```json
{
  "user": {
    "id": "!16fa4fdc",
    "longName": "Test Node",
    "shortName": "TEST"
  },
  "nodeStats": {
    "totalPackets": 1234,
    "totalBytes": 567890,
    "packetTypes": {
      "TEXT_MESSAGE_APP": 456,
      "TELEMETRY_APP": 234,
      "POSITION_APP": 123
    },
    "messageStats": {...},
    "positionStats": {...},
    "routingStats": {...}
  }
}
```

### 2. Map Display Enhancement (`map.html`)

The node information popup now displays two new sections:

#### 📊 Métriques collectées (Collected Metrics)

- **Paquets reçus**: Total number of packets received from this node
- **Volume**: Total data volume in KB
- **Types de paquets**: Top 3 packet types with counts
  - Packet type names are simplified (e.g., "TEXT MESSAGE" instead of "TEXT_MESSAGE_APP")

#### 📡 Télémétrie (Telemetry)

- **Battery**: Level percentage and voltage
- **Temperature**: Current temperature reading
- **Humidity**: Relative humidity percentage
- **Pressure**: Barometric pressure

## Example Popup Display

### Before (Basic Info Only)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━
Test Node
━━━━━━━━━━━━━━━━━━━━━━━━━━
ID: TEST
Modèle: TBEAM
Hops: 2
SNR: 8.5 dB
Voisins directs: 3
  • Node1 (9.2 dB)
  • Node2 (7.1 dB)
  • Node3 (5.8 dB)
🌐 MQTT: Actif

Dernier contact: 15/12/2025 14:30:45
Il y a 5 minutes
```

### After (With Metrics)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━
Test Node
━━━━━━━━━━━━━━━━━━━━━━━━━━
ID: TEST
Modèle: TBEAM
Hops: 2
SNR: 8.5 dB
Voisins directs: 3
  • Node1 (9.2 dB)
  • Node2 (7.1 dB)
  • Node3 (5.8 dB)
🌐 MQTT: Actif

📊 Métriques collectées:
  Paquets reçus: 1234
  Volume: 554.6 Ko
  Types de paquets:
    • TEXT MESSAGE: 456
    • TELEMETRY: 234
    • POSITION: 123

📡 Télémétrie:
  🔋 Batterie: 85%
  ⚡ Voltage: 4.15V
  🌡️ Température: 22.5°C
  💧 Humidité: 65%

Dernier contact: 15/12/2025 14:30:45
Il y a 5 minutes
```

## Technical Details

### Database Schema Used

The feature uses the existing `node_stats` table schema:

```sql
CREATE TABLE node_stats (
    node_id TEXT PRIMARY KEY,
    total_packets INTEGER,
    total_bytes INTEGER,
    packet_types TEXT,  -- JSON: {"TEXT_MESSAGE_APP": 456, ...}
    hourly_activity TEXT,
    message_stats TEXT,
    telemetry_stats TEXT,
    position_stats TEXT,
    routing_stats TEXT,
    last_updated REAL,
    last_battery_level INTEGER,
    last_battery_voltage REAL,
    last_telemetry_update REAL,
    last_temperature REAL,
    last_humidity REAL,
    last_pressure REAL,
    last_air_quality REAL
)
```

### Files Modified

1. **`map/export_nodes_from_db.py`**: 
   - Added loading of `node_stats` data
   - Added `nodeStats` field to exported JSON
   - ~15 lines added

2. **`map/map.html`**:
   - Added metrics display section in popup generation
   - Added telemetry display section (battery, environment)
   - Implemented in both `createMarkers()` and `createSingleMarker()` functions
   - ~80 lines added

### Graceful Degradation

The feature gracefully handles missing data:

- If `node_stats` data is not available for a node, the metrics section is not displayed
- If specific telemetry fields are missing, only available fields are shown
- Existing nodes without metrics continue to display normally

## Testing

A comprehensive test suite validates:

1. ✅ Node stats data structure export
2. ✅ JSON field mapping correctness
3. ✅ Popup HTML rendering
4. ✅ Telemetry data display
5. ✅ Graceful handling of missing data

Run tests:
```bash
python3 test_node_metrics_export.py
```

## Benefits

1. **Better Network Insight**: Users can see which nodes are most active
2. **Debugging Aid**: Packet type distribution helps diagnose issues
3. **Resource Monitoring**: Battery and environmental data at a glance
4. **Historical Context**: Total packets/bytes show node activity over time
5. **No Additional Load**: Uses existing collected data, no new database queries

## Future Enhancements

Possible future improvements:

- Add message rate (messages per hour)
- Show routing statistics (relayed packets)
- Display position update frequency
- Add signal strength trends
- Show hourly activity graphs

## Compatibility

- **No breaking changes**: Existing functionality preserved
- **Backward compatible**: Works with nodes that have no metrics data
- **No schema changes**: Uses existing database structure
- **No config changes**: No new configuration required
