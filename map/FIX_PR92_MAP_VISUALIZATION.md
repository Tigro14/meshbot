# Fix for PR #92 - Map Visualization Issues

## Issue

After merging PR #92, the mesh network map lost two critical features:
1. **Hop color information** - All nodes appear grey instead of color-coded by distance
2. **Links between nodes** - Connection lines between neighbor nodes disappeared

## Root Cause

PR #92 replaced the TCP-based `meshtastic --host --info` command with `export_nodes_from_db.py` to eliminate TCP connection conflicts. However, the new export script was only exporting basic node information and missing two critical fields that the map HTML expects:

- **`hopsAway`** - Minimum hop count to reach each node (0 = direct, 1+ = relayed)
- **`neighbors`** - Array of neighbor nodes with connection quality

### How map.html Uses These Fields

```javascript
// Node coloring based on hopsAway
function getNodeColorByHop(hopsAway) {
    if (hopsAway === undefined || hopsAway === null) {
        return '#95a5a6'; // Grey (missing data)
    }
    switch(hopsAway) {
        case 0: return '#27ae60'; // Green (direct)
        case 1: return '#3498db'; // Blue (1 hop)
        case 2: return '#f39c12'; // Yellow (2 hops)
        case 3: return '#e67e22'; // Orange (3 hops)
        case 4: return '#9b59b6'; // Purple (4 hops)
        default: return '#95a5a6'; // Grey (5+ hops)
    }
}

// Link drawing based on neighbors array
function drawLinks(nodes) {
    nodesArray.forEach(node => {
        const neighbors = node.neighbors || [];
        neighbors.forEach(neighbor => {
            // Draw line between node and neighbor
            // Color based on SNR value
        });
    });
}
```

## Solution

Enhanced `export_nodes_from_db.py` to query and include both missing fields from the SQLite database:

### 1. Added hopsAway Field

Query the packets table for minimum hop count per node:

```python
# Get minimum hop count for each node (hopsAway)
cursor.execute("""
    SELECT from_id, MIN(hops) as min_hops
    FROM packets
    WHERE timestamp > ? AND hops IS NOT NULL
    GROUP BY from_id
""", (cutoff,))

for row in cursor.fetchall():
    from_id_str = str(row[0])
    hops_data[from_id_str] = row[1]
```

### 2. Added neighbors Array

Query the neighbors table and format for map compatibility:

```python
# Get neighbor data from neighbors table
neighbors_raw = persistence.load_neighbors(hours=hours)

# Format neighbor data for map compatibility
for node_id_str, neighbor_list in neighbors_raw.items():
    formatted_neighbors = []
    for neighbor in neighbor_list:
        neighbor_id = neighbor.get('node_id')
        if neighbor_id:
            formatted_neighbors.append({
                'nodeId': neighbor_id,  # Already has ! prefix from database
                'snr': neighbor.get('snr'),
            })
    if formatted_neighbors:
        neighbors_data[node_key] = formatted_neighbors
```

### 3. Include Fields in Output

```python
# Add hopsAway if available from SQLite
if node_id_str in hops_data:
    node_entry["hopsAway"] = hops_data[node_id_str]

# Add neighbors array if available from SQLite
if node_id_str in neighbors_data:
    node_entry["neighbors"] = neighbors_data[node_id_str]
```

## Output Format

Before (missing fields):
```json
{
  "Nodes in mesh": {
    "!16fad3dc": {
      "num": 385503196,
      "user": {...},
      "position": {...},
      "snr": 9.75,
      "lastHeard": 1733175600
    }
  }
}
```

After (with hopsAway and neighbors):
```json
{
  "Nodes in mesh": {
    "!16fad3dc": {
      "num": 385503196,
      "user": {...},
      "position": {...},
      "snr": 9.75,
      "lastHeard": 1733175600,
      "hopsAway": 0,
      "neighbors": [
        {
          "nodeId": "!075bcd15",
          "snr": 8.5
        }
      ]
    }
  }
}
```

## Testing

Created comprehensive test suite:

### Test 1: Basic Functionality (test_export_nodes.sh)
- Validates JSON structure without database
- Tests basic node export

### Test 2: Database Integration (test_export_nodes_with_db.sh)
- Creates sample database with hops and neighbors
- Validates hopsAway values are correct (0, 1, 2 hops)
- Validates neighbors arrays are present
- All tests passing ✅

Sample output:
```
✅ hopsAway field present
   • Nodes with hopsAway: 3/3
✅ neighbors field present
   • Nodes with neighbors: 2/3
✅ !16fa4fdc: hopsAway=0 (correct)
✅ !075bcd15: hopsAway=1 (correct)
✅ !3ade68b1: hopsAway=2 (correct)
```

## Impact

### Before Fix
- ❌ All nodes appear grey (no hop color coding)
- ❌ No connection lines between nodes
- ⚠️ Limited map visualization value

### After Fix
- ✅ Nodes color-coded by distance (green=direct, blue=1 hop, yellow=2 hops, etc.)
- ✅ Connection lines drawn between neighbors
- ✅ Full map visualization restored
- ✅ SNR-based link quality indication

## Files Modified

| File | Changes | Description |
|------|---------|-------------|
| `map/export_nodes_from_db.py` | +60 lines | Added hopsAway and neighbors queries |
| `map/README_EXPORT_NODES.md` | +15 lines | Documented new fields |
| `map/test_export_nodes_with_db.sh` | NEW | Comprehensive test with database |

## Backward Compatibility

- ✅ Fully backward compatible
- ✅ Works with or without database (graceful degradation)
- ✅ No changes required to map.html
- ✅ No changes to existing scripts (infoup_db.sh)

## Deployment

No action required - the fix is automatically deployed when:
1. `infoup_db.sh` runs (typically every 10 minutes via cron)
2. Calls `export_nodes_from_db.py` to generate `info.json`
3. New JSON includes hopsAway and neighbors fields
4. Map automatically displays colors and links on next load

## Verification

After deployment, verify by:
1. Opening map.html in browser
2. Check nodes are color-coded (not all grey)
3. Check connection lines visible between nodes
4. Hover over nodes to see hop count
5. Hover over links to see SNR values

## See Also

- `map/README_EXPORT_NODES.md` - Complete export script documentation
- `map/test_export_nodes_with_db.sh` - Test suite
- Issue #92 - Original PR that introduced the regression
