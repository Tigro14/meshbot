# Fix for MQTT Neighbor Collector AttributeError

## Problem

The MQTT neighbor collector was failing with the following error:

```
Dec 04 09:09:12 DietPi meshtastic-bot[2292925]: [DEBUG] 👥 [MQTT] Paquet NEIGHBORINFO de a2e99ad8
Dec 04 09:09:12 DietPi meshtastic-bot[2292925]: [DEBUG] 👥 Erreur calcul distance pour !a2e99ad8: 'NodeManager' object has no attribute 'get_node_data'
```

## Root Cause

The file `mqtt_neighbor_collector.py` at line 458 calls:
```python
node_data = self.node_manager.get_node_data(node_id)
```

And at line 464 calls:
```python
ref_pos = self.node_manager.get_reference_position()
```

However, the `NodeManager` class in `node_manager.py` did not have these two methods defined, causing an `AttributeError`.

## Solution

Added two new methods to the `NodeManager` class:

### 1. `get_node_data(node_id)`

Returns complete node data including position information.

**Purpose**: Retrieve GPS position and other data for a specific node.

**Returns**:
- Dictionary with keys: `'latitude'`, `'longitude'`, `'altitude'`, `'name'`, `'last_update'`
- `None` if node doesn't exist or has no GPS position

**Key Feature**: Maps internal storage keys (`lat`/`lon`) to API-compatible keys (`latitude`/`longitude`)

**Example**:
```python
node_data = node_manager.get_node_data(0xa2e99ad8)
if node_data:
    lat = node_data['latitude']
    lon = node_data['longitude']
```

### 2. `get_reference_position()`

Returns the bot's reference position (configured in `BOT_POSITION`).

**Purpose**: Get the bot's GPS coordinates for distance calculations.

**Returns**:
- Tuple `(latitude, longitude)` 
- `None` if `BOT_POSITION` is not configured in config.py

**Example**:
```python
ref_pos = node_manager.get_reference_position()
if ref_pos and ref_pos[0] != 0 and ref_pos[1] != 0:
    ref_lat, ref_lon = ref_pos
    distance = haversine_distance(ref_lat, ref_lon, node_lat, node_lon)
```

## Implementation Details

### Data Structure Mapping

The `NodeManager` internally stores node data as:
```python
node_names[node_id] = {
    'name': 'NodeName',
    'lat': 47.123,      # Internal key
    'lon': 6.456,       # Internal key
    'alt': 100,
    'last_update': 1234567890
}
```

The `get_node_data()` method maps this to the expected API format:
```python
{
    'latitude': 47.123,   # API key (mapped from 'lat')
    'longitude': 6.456,   # API key (mapped from 'lon')
    'altitude': 100,
    'name': 'NodeName',
    'last_update': 1234567890
}
```

This mapping ensures compatibility with the MQTT neighbor collector code without requiring changes to the internal data structure or other parts of the codebase.

### Edge Cases Handled

1. **Node doesn't exist**: Returns `None`
2. **Node has no GPS position** (lat/lon are `None`): Returns `None`
3. **Bot position not configured**: `get_reference_position()` returns `None`

All edge cases are handled gracefully, allowing the MQTT neighbor collector to continue functioning even when some data is unavailable.

## Testing

### Manual Tests Performed

1. **Syntax Check**: `python3 -m py_compile node_manager.py` ✅
2. **Import Test**: Verified both methods exist after import ✅
3. **Unit Tests**: 5 test scenarios covering all edge cases ✅
4. **Scenario Simulation**: Simulated exact error scenario from logs ✅

### Test Script

A comprehensive test script `test_node_manager_mqtt_fix.py` has been added that:
- Tests all edge cases for `get_node_data()`
- Tests all edge cases for `get_reference_position()`
- Simulates the exact code path from `mqtt_neighbor_collector.py`
- Auto-manages test dependencies (creates/cleans up config.py)

Run with: `python3 test_node_manager_mqtt_fix.py`

## Impact

### Files Modified
- `node_manager.py`: Added 2 new methods (42 lines)

### Files Added
- `test_node_manager_mqtt_fix.py`: Comprehensive test suite (204 lines)

### Other Files Affected
- None (only `mqtt_neighbor_collector.py` uses these methods)

## Verification

The fix can be verified by:

1. Running the test script:
   ```bash
   python3 test_node_manager_mqtt_fix.py
   ```
   Expected output: "🎉 All tests PASSED!"

2. Monitoring logs after deployment:
   ```bash
   journalctl -u meshtastic-bot -f | grep "NEIGHBORINFO"
   ```
   The AttributeError should no longer appear.

## Backward Compatibility

✅ **Fully backward compatible**
- No existing methods were modified
- No internal data structures were changed
- Only new methods were added
- All existing functionality remains unchanged

## Future Considerations

The internal data structure uses `lat`/`lon` keys while the API uses `latitude`/`longitude`. This mapping is handled by `get_node_data()`. If the internal structure is ever standardized to use `latitude`/`longitude` throughout, the `get_node_data()` method can be simplified to return the data directly without mapping.
