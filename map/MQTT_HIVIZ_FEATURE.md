# MQTT Hi-Viz Circle Feature

## Overview

This feature adds a **thick yellow circle** around nodes that are actively sending NEIGHBORINFO packets via MQTT. This makes it easy to visually identify which nodes are contributing to the network topology via MQTT.

## Visual Appearance

- **Normal Node**: Standard colored circle based on hop distance
- **MQTT Active Node**: Same colored circle + thick yellow border (5px, #FFD700)

## How It Works

### 1. Detection (Backend)

The `export_nodes_from_db.py` script identifies MQTT-active nodes by:

1. Querying the `neighbors` table in the SQLite database
2. Any node that appears as the **sender** of NEIGHBORINFO data is marked as MQTT-active
3. Adds `"mqttActive": true` flag to that node's JSON entry

```python
# Node that sent NEIGHBORINFO is MQTT-active
if formatted_neighbors:
    node_key = node_id_str.lstrip('!')
    neighbors_data[node_key] = formatted_neighbors
    mqtt_active_nodes.add(node_key)  # Mark as MQTT active
```

### 2. Visualization (Frontend)

The `map.html` file renders the hi-viz circle when it detects the `mqttActive` flag:

```javascript
// Add yellow hi-viz circle for MQTT-active nodes
if (node.mqttActive) {
    const hivizCircle = L.circleMarker([lat, lon], {
        radius: 20,
        fillColor: 'transparent',
        color: '#FFD700',  // Bright yellow/gold
        weight: 5,
        opacity: 1,
        fillOpacity: 0,
        interactive: false
    });
    hivizCircle.addTo(map);
}
```

### 3. Enhanced Popup

When you click on an MQTT-active node, the popup shows:

```
🌐 MQTT: Actif
```

in gold color (#FFD700).

## Benefits

1. **Quick Identification**: Instantly see which nodes are MQTT-active
2. **Network Health**: Identify nodes contributing to topology data
3. **Troubleshooting**: Quickly spot if a node stops sending NEIGHBORINFO
4. **Coverage Visualization**: See MQTT coverage across your network

## Technical Details

### Database Schema

MQTT-active nodes are identified from the `neighbors` table:

```sql
CREATE TABLE neighbors (
    node_id TEXT NOT NULL,
    neighbor_id TEXT NOT NULL,
    snr REAL,
    last_rx_time INTEGER,
    node_broadcast_interval INTEGER,
    timestamp REAL NOT NULL
)
```

Any `node_id` that appears in this table is considered MQTT-active (they sent NEIGHBORINFO).

### JSON Format

Example node with MQTT active flag and timestamps:

```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": {
      "id": "!16fa4fdc",
      "longName": "tigro G2 PV",
      "shortName": "TIGR"
    },
    "position": {
      "latitude": 47.2496,
      "longitude": 6.0248
    },
    "lastHeard": 1733175600,
    "mqttLastHeard": 1733175650,
    "neighbors": [...],
    "mqttActive": true
  }
}
```

**Important fields:**
- `mqttActive`: true if node sent NEIGHBORINFO via MQTT
- `mqttLastHeard`: timestamp when node was last heard via MQTT (from neighbor data)
- `lastHeard`: timestamp when node was last heard (from mesh packets, or falls back to mqttLastHeard if no mesh packets)

**Critical fix:** For MQTT-only nodes (nodes heard via MQTT but not directly via mesh), `lastHeard` now uses `mqttLastHeard` as a fallback. This prevents these nodes from being filtered out by time-based filters on the map.

### Map Legend

The legend includes a new entry:

```
[Yellow Circle] 🌐 MQTT actif
```

## Testing

Run the test suite:

```bash
cd map
./test_mqtt_active.sh
```

This test:
1. Creates a sample database with 2 MQTT-active nodes and 1 inactive node
2. Runs the export script
3. Validates that `mqttActive` flag is correctly set
4. Verifies JSON syntax and structure

## Demo

Open `map/demo_mqtt_hiviz.html` in a browser to see a visual demonstration of the feature with animated examples.

## Configuration

No configuration needed! The feature automatically:
- Detects MQTT-active nodes from the database
- Renders the yellow circle on the map
- Updates the legend

## Performance

- **No performance impact**: The MQTT detection is part of the existing neighbor data query
- **Minimal visual overhead**: Only adds one extra circle marker per MQTT-active node
- **Efficient cleanup**: Hi-viz circles are properly removed when markers are recreated

## Troubleshooting

### Yellow circles not appearing on map

If MQTT-active nodes are not showing yellow circles:

1. **Check time filters**: Nodes need a `lastHeard` timestamp to pass time-based filters (6h, 24h, etc.)
   - Solution: The export script now uses `mqttLastHeard` as a fallback for nodes without mesh packets
   
2. **Verify JSON export**: Check that nodes have both fields:
   ```bash
   cd map
   ./export_nodes_from_db.py > /tmp/info.json 2>&1
   grep -A 5 "mqttActive" /tmp/info.json
   ```
   
3. **Check neighbor data in database**:
   ```sql
   sqlite3 ../traffic_history.db "SELECT node_id, COUNT(*) FROM neighbors GROUP BY node_id"
   ```

4. **Run test suite**:
   ```bash
   cd map
   ./test_mqtt_lastheard.sh  # Verifies lastHeard fallback
   ./test_mqtt_active.sh     # Verifies mqttActive flag
   ```

### Understanding the timestamp logic

- **Mesh-only nodes**: `lastHeard` from packets table
- **MQTT-only nodes**: `lastHeard` fallback from neighbor timestamps (NEW)
- **Mesh+MQTT nodes**: `lastHeard` from packets, `mqttLastHeard` from neighbors
- **No data nodes**: No `lastHeard`, filtered out by time filters

## Future Enhancements

Potential improvements:
- Add animation to the yellow circle (pulsing effect)
- Filter map to show only MQTT-active nodes
- Statistics panel showing MQTT-active node count
- Time-based fade (show how recently node was MQTT-active)
