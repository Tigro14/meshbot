# MQTT Active Nodes Map Visualization - Fix Summary

## Issue
MQTT-active nodes were not appearing with yellow circles on map.html despite the visualization code being in place.

## Root Cause
Node ID format mismatch in `export_nodes_from_db.py`:
- Database stores neighbor node IDs as `'!385503196'` (decimal with `!` prefix)
- After stripping `!`, the code got `'385503196'` (decimal string)
- Code incorrectly assumed this was hex and tried to match it
- `node_names.json` uses decimal string keys like `'385503196'`
- Result: Keys never matched, `mqttActive` flag was never set

## Solution
**File: `map/export_nodes_from_db.py`**

Changed line 136-142 to:
```python
# Remove ! prefix from node_id_str
# node_id_str format from database: '!385503196' (decimal with !)
# node_names.json keys are decimal strings: '385503196'
node_key_decimal = node_id_str.lstrip('!')  # Just strip !, no conversion needed

# Store neighbors with decimal key (matches node_names.json)
neighbors_data[node_key_decimal] = formatted_neighbors

# This node sent NEIGHBORINFO, so it's MQTT-active
mqtt_active_nodes.add(node_key_decimal)

# Store MQTT last heard timestamp
if max_timestamp > 0:
    mqtt_last_heard_data[node_key_decimal] = int(max_timestamp)
```

Also simplified lines 159-163 and 349-357 to use decimal strings consistently.

## Testing
All tests pass:
- ✅ `test_mqtt_active.sh` - Basic mqttActive flag test
- ✅ `test_mqtt_only_nodes.sh` - MQTT-only nodes test
- ✅ `test_mqtt_lastheard.sh` - Last heard timestamp test
- ✅ `test_complete_workflow.sh` - End-to-end workflow test
- ✅ `test_before_after_comparison.sh` - Visual comparison test

## Expected Behavior

### Before Fix (Broken)
```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": { "longName": "tigro G2 PV" },
    "position": {...},
    "neighbors": [...]
    // ❌ NO mqttActive flag
  }
}
```
Result: No yellow circles on map

### After Fix (Working)
```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": { "longName": "tigro G2 PV" },
    "position": {...},
    "neighbors": [...],
    "mqttActive": true  // ✅ Flag is set!
  }
}
```
Result: Yellow circles appear on MQTT-active nodes

## Visualization

### On map.html:

**Regular Node (no MQTT):**
```
⚪ Colored circle marker
```

**MQTT-Active Node:**
```
🟡 Yellow circle (5px border)
   ⚪ Colored circle marker inside
```

**Legend:**
```
🌐 MQTT actif - Yellow circle icon
```

**Popup:**
```
Node Name: tigro G2 PV
🌐 MQTT: Actif
Voisins directs: 1
```

## Production Verification

To verify the fix in production:

1. **Regenerate map data:**
   ```bash
   cd /home/user/meshbot/map
   ./infoup_db.sh
   ```

2. **Check mqttActive flags:**
   ```bash
   grep -C 3 "mqttActive" /tmp/info.json
   ```

3. **Open map.html** in browser:
   ```bash
   firefox map.html  # or any browser
   ```

4. **Verify yellow circles** appear around nodes that have sent NEIGHBORINFO data

5. **Click on node** with yellow circle and verify popup shows "🌐 MQTT: Actif"

## Impact

✅ **Users can now visually identify:**
- Nodes connected to MQTT broker
- Nodes sending regular NEIGHBORINFO broadcasts
- Nodes contributing to network topology data
- Active participants in mesh network monitoring

✅ **Network operators benefit from:**
- Complete topology visualization
- Easy identification of monitoring nodes
- Better network planning and optimization
- Transparent network health status

## Files Modified

- `map/export_nodes_from_db.py` - Fixed node ID format handling

## New Files Added

- `map/FIX_MQTT_ACTIVE_FLAG.md` - Detailed fix documentation
- `map/test_visual_mqtt.html` - Visual test demonstration
- `map/test_complete_workflow.sh` - End-to-end workflow test
- `map/test_before_after_comparison.sh` - Before/after comparison
- `map/SUMMARY_MQTT_ACTIVE_FIX.md` - This summary document

## Related Features

- MQTT neighbor collection (`mqtt_neighbor_collector.py`)
- Map visualization (`map.html`)
- Neighbor data persistence (`traffic_persistence.py`)
- Node database export (`export_nodes_from_db.py`)

## Credits

Fix implemented by GitHub Copilot for issue: "still do not see 🌐 MQTT actif nodes on map.html for now"

Repository: https://github.com/Tigro14/meshbot
