# MQTT-Only Nodes Fix - Visual Summary

## What This Fix Does

This fix ensures that **MQTT-only nodes** (nodes that only send NEIGHBORINFO via MQTT but are never heard directly via mesh radio) now appear on the map with their yellow MQTT-active circles.

## Visual Comparison

### Before Fix

```
┌─────────────────────────────────────────────┐
│           map.html (Before)                 │
├─────────────────────────────────────────────┤
│                                             │
│   🟢 Node A (Direct mesh + MQTT)           │
│   💛 Yellow circle                          │
│                                             │
│   🔵 Node B (Direct mesh, no MQTT)         │
│   No yellow circle                          │
│                                             │
│   ❌ Node C (MQTT-only)                    │
│   NOT VISIBLE - Missing from map!           │
│                                             │
└─────────────────────────────────────────────┘
```

### After Fix

```
┌─────────────────────────────────────────────┐
│           map.html (After)                  │
├─────────────────────────────────────────────┤
│                                             │
│   🟢 Node A (Direct mesh + MQTT)           │
│   💛 Yellow circle                          │
│                                             │
│   🔵 Node B (Direct mesh, no MQTT)         │
│   No yellow circle                          │
│                                             │
│   🟡 Node C (MQTT-only) ✅ NOW VISIBLE!    │
│   💛 Yellow circle                          │
│                                             │
└─────────────────────────────────────────────┘
```

## Data Flow Diagram

### Before Fix

```
MQTT NEIGHBORINFO Packet
         │
         ├──> Save to neighbors table ✅
         │
         └──> Check node_names.json
                    │
                    └──> NOT FOUND ❌
                         (Never heard via mesh radio)
                              │
                              └──> NOT exported to info.json ❌
                                        │
                                        └──> NOT on map.html ❌
```

### After Fix

```
MQTT NEIGHBORINFO Packet
         │
         ├──> Save to neighbors table ✅
         │
         ├──> Check node_names.json
         │         │
         │         └──> NOT FOUND (MQTT-only)
         │
         └──> Phase 2: Query packets table for position ✅
                    │
                    ├──> Position found in packets ✅
                    │
                    ├──> Build complete node entry ✅
                    │    • Position (lat/lon/alt)
                    │    • Name (from sender_name)
                    │    • mqttActive = true
                    │    • lastHeard (from MQTT timestamp)
                    │
                    └──> Export to info.json ✅
                              │
                              └──> Appears on map.html ✅
                                   with yellow circle! 💛
```

## Technical Details

### What Gets Exported

For MQTT-only nodes, the export now includes:

```json
{
  "!075bcd15": {
    "num": 123456789,
    "user": {
      "id": "!075bcd15",
      "longName": "Remote MQTT Node",
      "shortName": "REMO"
    },
    "position": {
      "latitude": 47.2181,
      "longitude": -1.5528,
      "altitude": 50
    },
    "lastHeard": 1733175500,      // ✅ Critical for time filters
    "mqttLastHeard": 1733175500,  // ✅ Explicit MQTT timestamp
    "neighbors": [...],            // ✅ NEIGHBORINFO data
    "mqttActive": true             // ✅ Yellow circle flag
  }
}
```

### Key Fields

1. **`position`**: Extracted from packets table (POSITION_APP or NODEINFO_APP packets received via MQTT)
2. **`lastHeard`**: Uses MQTT timestamp (prevents filtering by time filters)
3. **`mqttActive`**: Set to true (triggers yellow circle on map)
4. **`neighbors`**: NEIGHBORINFO data (already collected)

## Use Cases

### Scenario 1: Remote MQTT Gateway

```
Network A (Local Mesh)          Internet (MQTT)          Network B (Remote Mesh)
                                                          
┌──────────┐                                             ┌──────────┐
│ Node A   │────┐                                   ┌────│ Node D   │
└──────────┘    │                                   │    └──────────┘
                │    ┌─────────┐       ┌─────────┐ │
┌──────────┐    ├────│MQTT GW  │◄─────►│MQTT GW  │─┤    ┌──────────┐
│ Node B   │────┘    └─────────┘       └─────────┘ └────│ Node E   │
└──────────┘                                             └──────────┘
   (Direct mesh)                                         (MQTT-only from
                                                          perspective of
                                                          Network A)
```

**Before Fix**: Nodes D and E not visible on Network A's map
**After Fix**: ✅ Nodes D and E appear with yellow circles

### Scenario 2: Indoor vs Outdoor Antennas

```
                    ┌─────────────┐
                    │  MQTT Server│
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         ┌────▼────┐              ┌────▼────┐
         │Indoor   │              │Outdoor  │
         │Antenna  │              │Antenna  │
         │(tigrobot│              │(tigrog2)│
         └────┬────┘              └────┬────┘
              │                        │
        Direct Mesh               Direct Mesh
         Coverage                  Coverage
         (Limited)                 (Extended)
              │                        │
        Local nodes              Remote nodes
                                 (MQTT-only from
                                  indoor perspective)
```

**Before Fix**: Remote nodes (heard by outdoor antenna via MQTT) not visible
**After Fix**: ✅ Complete network visibility from both antennas

## Testing

### Test Coverage Matrix

| Node Type | In node_names.json | MQTT Active | Test | Result |
|-----------|-------------------|-------------|------|--------|
| Mesh+MQTT | ✅ Yes | ✅ Yes | test_mqtt_lastheard.sh | ✅ Pass |
| Mesh-only | ✅ Yes | ❌ No | test_mqtt_lastheard.sh | ✅ Pass |
| MQTT-only | ❌ No | ✅ Yes | test_mqtt_only_nodes.sh | ✅ Pass |

### Validation Checklist

- [x] MQTT-only node exported to info.json
- [x] Has valid position coordinates (from packets table)
- [x] Has `mqttActive` flag set to true
- [x] Has `lastHeard` timestamp (prevents time filter exclusion)
- [x] Has `mqttLastHeard` timestamp
- [x] Has neighbor data
- [x] Appears on map.html
- [x] Shows yellow MQTT-active circle
- [x] Backward compatible (existing tests pass)

## Deployment

After deploying this fix:

1. Run `export_nodes_from_db.py` to regenerate info.json
2. Upload to web server (or let cron job do it)
3. Refresh map.html in browser
4. MQTT-only nodes should now appear with yellow circles! 💛

## References

- Main fix: `map/export_nodes_from_db.py` (Phase 2 processing)
- Test: `map/test_mqtt_only_nodes.sh`
- Documentation: `map/FIX_MQTT_ONLY_NODES.md`
- Related: `map/MQTT_HIVIZ_FEATURE.md`, `map/MQTT_LASTHEARD_FIX.md`
