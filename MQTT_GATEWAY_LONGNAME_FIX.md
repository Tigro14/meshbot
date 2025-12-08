# MQTT Gateway Longname Resolution Fix

**Date**: 2025-12-08  
**Issue**: Gateway nodes in MQTT debug logs show hex ID instead of longname  
**Status**: ✅ Fixed

## Problem

The MQTT debug log displayed:
```
👥 [MQTT] Paquet POSITION de a2ea17b8 (🚀 Normandy SR-2) via !a2ea17b8
```

The "via" node showed the gateway's hex ID (`!a2ea17b8`) instead of its human-readable longname, making logs harder to read and understand.

## Root Cause

The `_resolve_gateway_name()` method in `mqtt_neighbor_collector.py` received the `gateway_id` as a string (e.g., `"!a2ea17b8"`), but called `node_manager.get_node_name(gateway_id)` with the string directly.

The `node_names` dictionary in `node_manager.py` is indexed by **integers**, not strings:
```python
# In node_manager.py line 86
node_id = int(k)  # Dictionary keys are integers
self.node_names[node_id] = {...}
```

When `get_node_name()` received a string that wasn't in the dictionary, it just returned the string as-is (line 173):
```python
if isinstance(node_id, str):
    return node_id  # Returns "!a2ea17b8" unchanged
```

## Solution

Modified `_resolve_gateway_name()` to convert the string gateway_id to an integer before calling `get_node_name()`:

```python
def _resolve_gateway_name(self, gateway_id):
    # Convert gateway_id string to integer for node_names lookup
    gateway_id_str = gateway_id
    if gateway_id_str.startswith('!'):
        gateway_id_int = int(gateway_id_str[1:], 16)  # "!a2ea17b8" → 0xa2ea17b8
    else:
        gateway_id_int = int(gateway_id_str, 16)      # "a2ea17b8" → 0xa2ea17b8
    
    # Get the node name using the integer ID
    gateway_name = self.node_manager.get_node_name(gateway_id_int)
    
    # If unknown, return original ID string
    if gateway_name in ["Unknown", None] or gateway_name.startswith(("!", "Node-")):
        return gateway_id_str
    
    return gateway_name
```

## Changes Made

### 1. `mqtt_neighbor_collector.py` (lines 296-334)
- Modified `_resolve_gateway_name()` method
- Added hex string to integer conversion
- Enhanced error handling for invalid hex strings
- Returns original ID if node name is "Unknown" or "Node-xxxxxxxx" format

### 2. `test_mqtt_via_info.py` (line 118)
- Updated Test 2 mock expectations
- Changed from `node_id == "!12345678"` to `node_id == 0x12345678`
- Matches new behavior where gateway_id is converted to integer

### 3. `test_gateway_longname_fix.py` (NEW)
- Comprehensive test suite with 6 test cases
- Covers all edge cases and error conditions

## Test Results

All tests pass successfully:

### ✅ test_gateway_longname_fix.py - 6/6 tests
- Gateway ID with '!' prefix → Resolved to longname
- Gateway ID without '!' prefix → Resolved to longname
- Unknown node → Returns original ID
- Node-xxxxxxxx format → Returns original ID
- Empty gateway_id → Returns None
- Invalid hex string → Returns original ID

### ✅ test_mqtt_via_info.py - 3/3 tests
- Gateway ID extraction → Working
- Gateway name resolution → Working  
- Missing gateway_id → Handled gracefully

### ✅ test_mqtt_debug_longname.py - 4/4 tests
- All longname formatting tests → Passing

## Expected Result

After the fix, logs now display:
```
👥 [MQTT] Paquet POSITION de a2ea17b8 (🚀 Normandy SR-2) via 🚀 Normandy SR-2
```

The gateway node now shows its longname, making it immediately clear which gateway relayed the packet.

## Benefits

✓ **Better log readability** - See friendly names instead of hex IDs  
✓ **Easier debugging** - Quickly identify which gateway relayed packets  
✓ **Consistent formatting** - Both sender and gateway show longnames  
✓ **Network topology understanding** - See relay paths at a glance

## Example Use Case

In a mesh network with multiple gateways uploading to MQTT:

**Gateway 'MountainRepeater' (!a2ea17b8) relays a position packet:**
- BEFORE: `via !a2ea17b8`
- AFTER: `via MountainRepeater`

**Gateway 'ValleyNode' (!b3fb28c9) relays a telemetry packet:**
- BEFORE: `via !b3fb28c9`
- AFTER: `via ValleyNode`

This makes it immediately clear which gateway is relaying packets, helping to understand network topology and troubleshoot connectivity issues.

## Edge Cases Handled

1. **With '!' prefix**: `"!a2ea17b8"` → Converts to `0xa2ea17b8`
2. **Without prefix**: `"a2ea17b8"` → Converts to `0xa2ea17b8`
3. **Unknown nodes**: Returns original ID string (e.g., `"!99999999"`)
4. **Default names**: If `get_node_name()` returns `"Node-a2ea17b8"`, returns original ID
5. **Empty gateway_id**: Returns `None` (no "via" suffix added)
6. **Invalid hex**: Catches `ValueError` and returns original ID

## Implementation Details

### Before Fix
```python
gateway_name = self.node_manager.get_node_name(gateway_id)
# gateway_id = "!a2ea17b8" (string)
# node_names[string] → not found → returns "!a2ea17b8"
```

### After Fix
```python
gateway_id_int = int(gateway_id.lstrip('!'), 16)  # → 2733250488
gateway_name = self.node_manager.get_node_name(gateway_id_int)
# node_names[2733250488] → "🚀 Normandy SR-2"
```

## Testing

To verify the fix:

```bash
# Run comprehensive test suite
python test_gateway_longname_fix.py

# Run existing MQTT tests
python test_mqtt_via_info.py
python test_mqtt_debug_longname.py

# Run demonstration
python demo_gateway_longname_fix.py
```

## Related Files

- `mqtt_neighbor_collector.py` - Main implementation
- `node_manager.py` - Node name lookup logic
- `test_gateway_longname_fix.py` - Test suite for the fix
- `test_mqtt_via_info.py` - MQTT via information tests
- `demo_gateway_longname_fix.py` - Visual demonstration

## Commit

**Commit**: `Fix MQTT gateway longname resolution in debug logs`  
**Files Changed**: 3 files, +279 insertions, -6 deletions

---

**Author**: GitHub Copilot  
**Reviewer**: Tigro14
