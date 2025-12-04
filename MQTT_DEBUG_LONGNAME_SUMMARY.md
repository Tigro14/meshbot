# MQTT Debug Log Enhancement - Implementation Summary

## Problem Statement

In the debug log, for each MQTT line, we needed to add the longname associated with the node ID when possible.

**Before:**
```
Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet POSITION de 2867b4fa
Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de ae613834
Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de d4b288a9
```

## Solution Implemented

### File Modified: `mqtt_neighbor_collector.py`

**Location:** Lines 377-396

**Implementation:**
```python
if is_loggable:
    portnum_names = {
        portnums_pb2.PortNum.POSITION_APP: "POSITION",
        portnums_pb2.PortNum.NODEINFO_APP: "NODEINFO",
        portnums_pb2.PortNum.TELEMETRY_APP: "TELEMETRY",
        portnums_pb2.PortNum.NEIGHBORINFO_APP: "NEIGHBORINFO"
    }
    portnum_name = portnum_names.get(portnum, f"UNKNOWN({portnum})")
    # Get longname if available from node_manager
    longname = None
    if self.node_manager:
        longname = self.node_manager.get_node_name(from_id)
        # If get_node_name returns "Unknown" or a hex ID, don't use it
        if longname and (longname == "Unknown" or longname.startswith("!")):
            longname = None
    
    if longname:
        debug_print(f"👥 [MQTT] Paquet {portnum_name} de {from_id:08x} ({longname})")
    else:
        debug_print(f"👥 [MQTT] Paquet {portnum_name} de {from_id:08x}")
```

## Result

**After (with available longnames):**
```
Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet POSITION de 2867b4fa (TigroRouter)
Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de ae613834 (NodeAlpha)
Dec 04 21:36:07 DietPi meshtastic-bot[932]: [DEBUG] 👥 [MQTT] Paquet NODEINFO de d4b288a9 (MeshNode-West)
```

## Behavior

### When Longname is Available
- Format: `👥 [MQTT] Paquet {TYPE} de {HEXID} ({LongName})`
- Example: `👥 [MQTT] Paquet POSITION de 2867b4fa (TigroRouter)`

### When Longname is NOT Available
- Format: `👥 [MQTT] Paquet {TYPE} de {HEXID}`
- Example: `👥 [MQTT] Paquet POSITION de 2867b4fa`

### Filtering Logic
The longname is NOT displayed if:
- `node_manager` is not available
- Node ID is not found in `node_manager`
- `get_node_name()` returns "Unknown"
- `get_node_name()` returns a hex ID (starts with "!")

## Testing

### Test File: `test_mqtt_debug_longname.py`

**Test Cases:**
1. ✅ Node with known longname → Shows `(LongName)`
2. ✅ Unknown node → Shows hex ID only
3. ✅ Node with "Unknown" name → Shows hex ID only
4. ✅ Proper formatting for all packet types

**All tests pass successfully.**

### Demonstration: `demo_mqtt_longname.py`

Shows visual before/after comparison with examples.

## Benefits

✅ **Quick node identification** - No need to cross-reference hex IDs with node names
✅ **Easier debugging** - Instantly see which nodes are generating traffic
✅ **Better monitoring** - Track specific nodes by name in logs
✅ **No overhead** - Gracefully falls back when longname unavailable
✅ **Backward compatible** - Maintains existing format when names not available

## Impact

- **Minimal code change** - Only 11 lines added
- **No breaking changes** - Fully backward compatible
- **Performance neutral** - Simple dictionary lookup
- **User experience** - Significantly improved log readability

## Files Changed

1. `mqtt_neighbor_collector.py` - Main implementation (11 lines added)
2. `test_mqtt_debug_longname.py` - Test suite (new file, 123 lines)
3. `demo_mqtt_longname.py` - Visual demonstration (new file, 47 lines)

## Verification

- ✅ Python syntax validation passed
- ✅ Unit tests pass (4/4 test cases)
- ✅ No conflicts with existing functionality
- ✅ Graceful degradation when dependencies unavailable
