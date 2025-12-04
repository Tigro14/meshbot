# MQTT LastHeard Fix - Technical Documentation

## Problem Statement

MQTT yellow circles were not showing on `map.html` because MQTT-only nodes (nodes heard via NEIGHBORINFO packets but not directly via mesh) did not have `lastHeard` timestamps. Without this timestamp, these nodes were filtered out by time-based filters (6h, 24h, etc.) on the map, preventing their yellow MQTT-active circles from appearing.

## Root Cause Analysis

### Data Flow

1. **Mesh Packets** → `packets` table → `lastHeard` timestamp
2. **MQTT NEIGHBORINFO** → `neighbors` table → `timestamp` field
3. **Export Script** queries both tables separately
4. **Problem**: MQTT-only nodes only exist in `neighbors` table, not `packets` table

### Why Yellow Circles Didn't Appear

```javascript
// In map.html (lines 808-813)
const lastHeard = node.lastHeard || 0;
const hoursAgo = (now - lastHeard) / 3600;

if (currentFilter !== 'all') {
    const hours = parseInt(currentFilter);
    if (hoursAgo > hours) {
        return;  // Node filtered out - won't render
    }
}
```

**Result**: MQTT-only nodes with no `lastHeard` would be filtered out before the yellow circle code (lines 897-914) could execute.

## Solution

### Changes to `export_nodes_from_db.py`

1. **Track MQTT timestamps** from neighbor data:
   ```python
   mqtt_last_heard_data = {}  # Track when node was last heard via MQTT
   
   for node_id_str, neighbor_list in neighbors_raw.items():
       max_timestamp = 0
       for neighbor in neighbor_list:
           neighbor_timestamp = neighbor.get('timestamp', 0)
           if neighbor_timestamp > max_timestamp:
               max_timestamp = neighbor_timestamp
       
       if max_timestamp > 0:
           mqtt_last_heard_data[node_key] = int(max_timestamp)
   ```

2. **Use MQTT timestamp as fallback** for `lastHeard`:
   ```python
   # Add lastHeard if available from SQLite (mesh packets)
   if node_id_str in last_heard_data:
       node_entry["lastHeard"] = last_heard_data[node_id_str]
   elif node_id_str in mqtt_last_heard_data:
       # Fallback: Use MQTT timestamp if no mesh packets
       # This ensures MQTT-only nodes are not filtered out by time
       node_entry["lastHeard"] = mqtt_last_heard_data[node_id_str]
   ```

3. **Add separate `mqttLastHeard` field** for transparency:
   ```python
   # Add MQTT last heard timestamp (always add for MQTT-active nodes)
   if node_id_str in mqtt_last_heard_data:
       node_entry["mqttLastHeard"] = mqtt_last_heard_data[node_id_str]
   ```

### JSON Structure Changes

**Before** (MQTT-only node):
```json
{
  "!075bcd15": {
    "user": { "longName": "Remote Node" },
    "position": { "latitude": 47.2181, "longitude": -1.5528 },
    "neighbors": [...],
    "mqttActive": true
    // ❌ Missing lastHeard - filtered out by time filters!
  }
}
```

**After** (MQTT-only node):
```json
{
  "!075bcd15": {
    "user": { "longName": "Remote Node" },
    "position": { "latitude": 47.2181, "longitude": -1.5528 },
    "lastHeard": 1733175500,        // ✅ Fallback from MQTT timestamp
    "mqttLastHeard": 1733175500,    // ✅ Explicit MQTT timestamp
    "neighbors": [...],
    "mqttActive": true
  }
}
```

## Testing

### Test Suite

1. **`test_mqtt_active.sh`** (existing)
   - Validates `mqttActive` flag is set correctly
   - Tests backward compatibility

2. **`test_mqtt_lastheard.sh`** (new)
   - Tests three scenarios:
     - Mesh+MQTT nodes: `lastHeard` from packets, `mqttLastHeard` from neighbors
     - MQTT-only nodes: `lastHeard` fallback from MQTT timestamp
     - Non-MQTT nodes: no `mqttLastHeard`
   - Validates critical fix: MQTT-only nodes have `lastHeard`

3. **`test_mqtt_lastheard_visual.html`** (new)
   - Visual HTML test page
   - Interactive demonstration of the fix
   - Shows all test results with color coding

### Running Tests

```bash
cd map

# Test 1: MQTT active flag (backward compatibility)
./test_mqtt_active.sh

# Test 2: MQTT lastHeard timestamps (new fix)
./test_mqtt_lastheard.sh

# Test 3: Visual verification
python3 -m http.server 8000
# Open http://localhost:8000/test_mqtt_lastheard_visual.html
```

## Impact

### Before Fix

- **MQTT-only nodes**: Hidden from map (no `lastHeard` → filtered out)
- **Yellow circles**: Only visible for nodes also heard via mesh
- **Network visibility**: Incomplete topology (missing remote MQTT nodes)

### After Fix

- **MQTT-only nodes**: ✅ Visible on map with proper timestamps
- **Yellow circles**: ✅ Appear for all MQTT-active nodes
- **Network visibility**: ✅ Complete topology including remote nodes
- **Time filters**: ✅ Work correctly for all node types

## Node Type Taxonomy

| Node Type | Mesh Packets | MQTT Neighbors | lastHeard Source | mqttActive | mqttLastHeard |
|-----------|--------------|----------------|------------------|------------|---------------|
| Mesh+MQTT | ✅ Yes | ✅ Yes | packets table | ✅ true | ✅ timestamp |
| MQTT-only | ❌ No | ✅ Yes | **neighbors fallback** | ✅ true | ✅ timestamp |
| Mesh-only | ✅ Yes | ❌ No | packets table | ❌ false | ❌ absent |
| No data | ❌ No | ❌ No | ❌ absent | ❌ false | ❌ absent |

## Files Modified

1. **`map/export_nodes_from_db.py`**
   - Added `mqtt_last_heard_data` tracking
   - Implemented fallback logic for `lastHeard`
   - Added `mqttLastHeard` field to JSON output
   - Updated statistics logging

2. **`map/MQTT_HIVIZ_FEATURE.md`**
   - Documented new fields (`mqttLastHeard`, fallback logic)
   - Added troubleshooting section
   - Explained timestamp logic for different node types

3. **`map/test_mqtt_lastheard.sh`** (new)
   - Comprehensive test for all scenarios
   - Validates critical fix

4. **`map/test_mqtt_lastheard_visual.html`** (new)
   - Visual demonstration of the fix
   - Interactive test results

## Backward Compatibility

✅ **Fully backward compatible**
- Existing `mqttActive` flag unchanged
- No breaking changes to JSON structure
- New fields are optional additions
- Existing tests (`test_mqtt_active.sh`) still pass
- `map.html` doesn't need modifications (only uses `lastHeard` and `mqttActive`)

## Performance

- **No performance impact**: MQTT timestamp extraction is part of existing neighbor data query
- **Minimal memory overhead**: One additional dictionary for `mqtt_last_heard_data`
- **No database changes**: Uses existing `timestamp` field in `neighbors` table

## Future Enhancements

Potential improvements:
- Add visual indicator in map popup to distinguish MQTT-only nodes
- Show `mqttLastHeard` timestamp in node popup
- Add filter to show only MQTT-active nodes
- Time-based fade for MQTT activity (show how recently active)

## References

- Original issue: MQTT yellow circles not showing on map.html
- Related documentation: `map/MQTT_HIVIZ_FEATURE.md`
- Database schema: `traffic_persistence.py` (neighbors table)
- Map visualization: `map/map.html` (lines 886-914, 808-813)
