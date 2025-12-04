# Distance Filtering for /neighbors Command

## Problem Statement

The `/neighbors` command (especially via Telegram) was showing too many foreign nodes from the public MQTT feed that are located more than 100km away from our node. This made the output cluttered with irrelevant nodes that are not part of the local mesh network.

## Solution

Implemented distance-based filtering in the `get_neighbors_report()` method to automatically filter out nodes beyond a configurable distance threshold.

## Implementation Details

### 1. Configuration

A new configuration option was added to `config.py.sample`:

```python
# Distance maximale (km) pour afficher les voisins MQTT dans /neighbors
# Les nœuds situés à plus de cette distance du bot seront filtrés (nœuds étrangers)
NEIGHBORS_MAX_DISTANCE_KM = 100  # Défaut: 100km
```

### 2. Modified Files

#### traffic_monitor.py

The `get_neighbors_report()` method was enhanced with distance filtering:

**New Parameter:**
- `max_distance_km` (optional): Maximum distance in km to filter nodes. Defaults to `config.NEIGHBORS_MAX_DISTANCE_KM` or 100km.

**Filtering Logic:**
1. After loading neighbor data from SQLite, get bot's reference position
2. For each node, calculate GPS distance from bot using Haversine formula
3. Filter out nodes beyond `max_distance_km`
4. Keep nodes without GPS position (may be local nodes without GPS)
5. Log filtered nodes to debug output

**Code Flow:**
```python
def get_neighbors_report(self, node_filter=None, compact=True, max_distance_km=None):
    # Load config if not provided
    if max_distance_km is None:
        max_distance_km = config.NEIGHBORS_MAX_DISTANCE_KM or 100
    
    # Load neighbor data
    neighbors_data = self.persistence.load_neighbors(hours=48)
    
    # Filter by distance
    ref_pos = self.node_manager.get_reference_position()
    if ref_pos:
        for node_id, neighbors in neighbors_data.items():
            node_data = self.node_manager.get_node_data(node_id_int)
            if node_data has GPS:
                distance = haversine_distance(ref_pos, node_pos)
                if distance > max_distance_km:
                    # Filter out this node
                    nodes_filtered_count += 1
    
    # Continue with existing formatting logic...
```

### 3. Testing

Three test scripts were created:

#### test_neighbors_distance_filter.py
Basic unit test validating:
- Distance calculation logic (Haversine formula)
- Filtering behavior with nodes at various distances
- Nodes >100km are filtered, <100km are kept

#### test_neighbors_integration.py
Comprehensive integration test with:
- Mock database with neighbor data
- Mock nodes at different distances
- Tests for compact format (LoRa)
- Tests for detailed format (Telegram)
- Tests for custom distance threshold
- Tests for node-specific filtering

**Test Results:**
```
✅ Compact format filtering works correctly
✅ Detailed format filtering works correctly
✅ Custom distance threshold works correctly
✅ Node-specific filtering works correctly
✅ Both compact and detailed formats work
```

#### test_neighbors_telegram_wrapper.py
Existing test ensuring:
- Telegram command structure remains intact
- Authorization checks still work
- Handler registration is correct

## Usage

### Default Behavior (100km)

```bash
# Telegram
/neighbors

# Mesh
/neighbors
```

Both commands will now automatically filter out nodes beyond 100km.

### Custom Distance Threshold

For programmatic use, you can override the distance:

```python
# Show nodes within 50km
report = traffic_monitor.get_neighbors_report(
    node_filter=None,
    compact=False,
    max_distance_km=50
)

# Show all nodes (no distance filtering)
report = traffic_monitor.get_neighbors_report(
    node_filter=None,
    compact=False,
    max_distance_km=999999
)
```

### Configuration

To change the default distance threshold, edit `config.py`:

```python
# Show nodes within 50km instead of 100km
NEIGHBORS_MAX_DISTANCE_KM = 50

# Show nodes within 200km (larger area)
NEIGHBORS_MAX_DISTANCE_KM = 200
```

## Edge Cases

1. **Nodes without GPS position**: Kept in the list (may be local nodes without GPS)
2. **Bot without GPS position**: Filtering is disabled, all nodes shown
3. **Node filter specified**: Distance filtering is still applied after node name/ID filtering
4. **Custom threshold**: Can be passed programmatically to override config

## Debug Logging

When `DEBUG_MODE = True`, the filtering process logs:

```
👥 Nœud filtré (>100km): !87654321 à 326.9km
👥 3 nœud(s) filtré(s) pour distance >100km
```

## Benefits

✅ **Cleaner output**: Only shows relevant local nodes
✅ **Configurable**: Easy to adjust distance threshold
✅ **Backward compatible**: Default behavior maintains 100km threshold
✅ **Automatic**: No user action required
✅ **Flexible**: Works for both Telegram and mesh commands
✅ **Robust**: Handles edge cases (no GPS, custom filters, etc.)

## Performance Impact

Minimal:
- Distance calculation is O(n) where n = number of nodes
- Haversine formula is lightweight (just trigonometry)
- Filtering happens in-memory before formatting
- No additional database queries

## Future Improvements

Potential enhancements:
1. Add `/neighbors all` command to bypass filtering
2. Add distance info to output (e.g., "CloseNode [1.4km]")
3. Allow per-user distance preferences via Telegram
4. Add distance-based coloring/icons in detailed output

## Related Issues

Fixes the issue where public MQTT neighbor collector was showing too many foreign nodes (>100km) in the `/neighbors` command output.
