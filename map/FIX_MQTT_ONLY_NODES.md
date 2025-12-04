# Fix: MQTT-Only Nodes Missing from map.html

## Problem Statement

MQTT active nodes (yellow circles) were not appearing on `map.html` when the nodes were **MQTT-only** (heard via NEIGHBORINFO packets via MQTT but never heard directly via mesh radio).

## Root Cause

The `export_nodes_from_db.py` script only exported nodes that existed in `node_names.json`. However, MQTT-only nodes were not added to `node_names.json` by the `NodeManager` because:

1. `NodeManager` only updates `node_names.json` from packets received directly via the Meshtastic radio interface
2. MQTT-only nodes only send NEIGHBORINFO packets via MQTT (not via radio)
3. Therefore, they never got added to `node_names.json`
4. Therefore, they were never exported to `info.json` which powers the map
5. Therefore, their yellow MQTT-active circles never appeared on the map

## Solution

Modified `export_nodes_from_db.py` to add a **Phase 2** processing step that:

1. Queries the `packets` table for position and name data of all MQTT-active nodes
2. After processing nodes from `node_names.json` (Phase 1), adds any MQTT-active nodes that:
   - Have position data in the packets table
   - Are NOT already in the output (because they weren't in node_names.json)
3. Ensures these nodes have:
   - Position coordinates (lat/lon/alt) from packets table
   - `lastHeard` timestamp (using `mqttLastHeard` fallback) to pass time filters
   - `mqttActive` flag set to true
   - Neighbor data if available

## Changes Made

### `map/export_nodes_from_db.py`

1. **Added MQTT node data extraction** (after line 142):
   - Query packets table for position/name data of MQTT-active nodes
   - Store in `mqtt_node_data` dictionary

2. **Added Phase 2 processing** (after line 270):
   - Loop through `mqtt_node_data`
   - Skip nodes already in output (from Phase 1)
   - Build complete node entries with all required fields
   - Add to output with `mqttActive=True` and `lastHeard` timestamp

3. **Enhanced statistics logging**:
   - Added "MQTT nodes avec position (packets)" count
   - Added "Nœuds MQTT-only ajoutés" count

### `map/test_mqtt_only_nodes.sh` (new)

Comprehensive test that verifies:
- MQTT-only nodes (NOT in node_names.json) are exported
- They have position data from packets table
- They have `lastHeard` timestamp
- They are marked as `mqttActive`
- They will pass time-based filters on the map

## Testing

### Test Results

Both tests pass:

```bash
cd map/
./test_mqtt_lastheard.sh    # ✅ Existing test - backward compatibility
./test_mqtt_only_nodes.sh   # ✅ New test - MQTT-only nodes
```

### Test Coverage

1. **Nodes in node_names.json + MQTT**:
   - Exported with all data
   - `lastHeard` from packets, `mqttLastHeard` from neighbors
   - ✅ Working before fix, still working after

2. **Nodes ONLY in node_names.json** (no MQTT):
   - Exported with position from node_names.json
   - No `mqttActive` flag
   - ✅ Working before fix, still working after

3. **MQTT-only nodes** (NOT in node_names.json):
   - ❌ Missing before fix
   - ✅ **Now exported with position from packets table**
   - ✅ **Have `lastHeard` timestamp (critical for time filters)**
   - ✅ **Marked as `mqttActive`**
   - ✅ **Will appear on map with yellow circles**

## Impact

### Before Fix

- MQTT-only nodes: ❌ Hidden from map (not in export)
- Yellow circles: Only visible for nodes also heard via mesh
- Network visibility: Incomplete topology (missing remote MQTT nodes)

### After Fix

- MQTT-only nodes: ✅ **Visible on map with position data**
- Yellow circles: ✅ **Appear for ALL MQTT-active nodes**
- Network visibility: ✅ **Complete topology including remote nodes**
- Time filters: ✅ **Work correctly for all node types**

## Node Type Taxonomy (Updated)

| Node Type | In node_names.json | In packets | In neighbors | Export Status | Yellow Circle |
|-----------|-------------------|------------|--------------|---------------|---------------|
| Mesh+MQTT | ✅ Yes | ✅ Yes | ✅ Yes | Phase 1 | ✅ Yes |
| MQTT-only | ❌ No | ✅ Yes | ✅ Yes | **Phase 2 (NEW)** | ✅ **Yes (NEW)** |
| Mesh-only | ✅ Yes | ✅ Yes | ❌ No | Phase 1 | ❌ No |
| Name-only | ✅ Yes | ❌ No | ❌ No | Phase 1 | ❌ No |

## Backward Compatibility

✅ **Fully backward compatible**
- No breaking changes to JSON structure
- All existing tests pass
- Phase 1 processing unchanged
- Phase 2 only adds new nodes that were previously missing
- Map.html doesn't need modifications (already supports mqttActive flag)

## Performance Impact

- **Minimal**: One additional SQL query per MQTT-active node
- **Benefit**: Much smaller than querying via TCP (old method)
- **No database schema changes**: Uses existing tables and columns

## Related Issues

- Original issue: "We still do not see the MQTT active node (yellow circle) on the map.html"
- Related docs: `map/MQTT_HIVIZ_FEATURE.md`, `map/MQTT_LASTHEARD_FIX.md`

## Files Modified

1. `map/export_nodes_from_db.py` - Added Phase 2 MQTT-only node processing
2. `map/test_mqtt_only_nodes.sh` - New comprehensive test (created)
3. `map/FIX_MQTT_ONLY_NODES.md` - This documentation (created)
