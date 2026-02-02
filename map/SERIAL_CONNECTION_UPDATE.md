# Map Generation System - Serial Connection Update

## Summary

This document describes the updates made to the map generation system to properly work with Serial connections instead of TCP, and to remove hardcoded node identifiers.

## Changes Made

### 1. Fixed Hardcoded Node Identifier in map.html

**Problem:**
- `map.html` had hardcoded references to "tigro G2 PV" as the owner node name
- Line 6: Title contained "tigro G2 PV"
- Line 504: Stats title contained "tigro G2 PV"
- Line 566: myNodeId was hardcoded to '!a2e175ac'

**Solution:**
- Changed myNodeId from hardcoded value to `null` (auto-detected)
- Added myNodeName variable to store detected owner node name
- Enhanced `parseNodeInfo()` function to detect owner node dynamically:
  - Primary: Looks for node with `hopsAway === 0` or `hopsAway === undefined/null`
  - Fallback: Uses first node with valid position if no owner found
- Dynamically updates page title and stats title with detected owner node name

**Benefits:**
- ✅ Map works with any node (not just tigro G2 PV)
- ✅ Automatically adapts to Serial or TCP connected node
- ✅ Uses actual node name from data instead of static string
- ✅ Proper fallback handling when owner detection fails

### 2. Verified Data Sources

**Confirmed that infoup_db.sh uses database-only mode:**

```bash
# Line 23-24: TCP_QUERY_HOST is empty by default
TCP_QUERY_HOST=""  # Example: "192.168.1.38"
TCP_QUERY_PORT="4403"

# Line 35: Uses database-only export by default
EXPORT_CMD="/home/dietpi/bot/map/export_neighbors_from_db.py $DB_PATH 720"
```

**Data flow verified:**

```
Serial/TCP Connection
        ↓
    main_bot.py
        ↓
traffic_persistence.py (SQLite)
        ↓
[traffic_history.db]
        ↓
        ├─→ export_neighbors_from_db.py → info_neighbors.json
        └─→ export_nodes_from_db.py → info_temp.json
                ↓
        merge_neighbor_data.py
                ↓
            info.json (complete data)
                ↓
            map.html (visualization)
```

**No deprecated sources:**
- ✅ `export_neighbors_from_db.py` reads from SQLite `neighbors` table
- ✅ `export_nodes_from_db.py` reads from `node_names.json` + SQLite enrichment
- ✅ No TCP dependency in default configuration
- ✅ All data comes from Meshtastic tables (collected by bot)

## Testing

### Owner Node Detection Test

A comprehensive test file was created: `map/test_owner_node_detection.html`

**Test scenarios:**
1. ✅ Normal case: Node with hopsAway = 0
2. ✅ Edge case: Node with undefined hopsAway
3. ✅ Fallback case: No owner node (all have hopsAway > 0)

**To run the test:**
```bash
# Open in browser
firefox map/test_owner_node_detection.html
```

### Workflow Validation

The existing workflow test validates the complete pipeline:
```bash
cd map/
./test_complete_workflow.sh
```

This test:
- Creates sample node database
- Simulates NEIGHBORINFO packets
- Runs export scripts
- Validates output JSON structure
- Confirms mqttActive flags are set correctly

## Configuration

### Current Setup (Serial Connection)

**infoup_db.sh configuration:**
```bash
# Database paths
JSON_FILE="/home/dietpi/bot/map/info.json"
JSON_LINKS_FILE="/home/dietpi/bot/map/info_neighbors.json"
DB_PATH="/home/dietpi/bot/traffic_history.db"
NODE_NAMES_FILE="/home/dietpi/bot/node_names.json"

# TCP query disabled (safe for Serial connection)
TCP_QUERY_HOST=""
```

**No changes needed** - Current configuration is correct for Serial connections.

### Optional: Hybrid Mode (Advanced)

If you need to query an external node via TCP **while bot uses Serial**, you can enable hybrid mode:

```bash
# In infoup_db.sh
TCP_QUERY_HOST="192.168.1.38"  # External node IP
TCP_QUERY_PORT="4403"
```

**WARNING:** Only enable this if:
- Bot uses Serial connection (not TCP to same node)
- You want additional neighbor data from external node
- You understand TCP conflict risks

## Usage

### Generate Map Data

```bash
cd /home/dietpi/bot/map
./infoup_db.sh
```

This will:
1. Export neighbors from database → `info_neighbors.json`
2. Export nodes from database → `info_temp.json`
3. Merge data → `info.json`
4. Upload to web server (if configured)

### View Map

Open `map.html` in browser. The map will:
1. Load `info.json` from server
2. Auto-detect owner node (hopsAway == 0)
3. Update title with owner node name
4. Display network topology with correct owner node

## Owner Node Detection Logic

```javascript
// In map.html parseNodeInfo() function
for (const [nodeId, nodeData] of Object.entries(data['Nodes in mesh'])) {
    // Primary detection: hopsAway == 0 or undefined
    if (nodeData.hopsAway === 0 || 
        nodeData.hopsAway === undefined || 
        nodeData.hopsAway === null) {
        
        myNodeId = nodeId;
        myNodeName = nodeData.user?.longName || 
                     nodeData.user?.shortName || 
                     nodeId;
        
        // Update page title and stats
        document.title = `Carte Réseau Meshtastic - Vu par ${myNodeName}`;
        document.getElementById('statsTitle').textContent = 
            `Réseau Mesh vu par ${myNodeName}`;
        
        break;
    }
}

// Fallback: use first node with position
if (!myNodeId) {
    // ... fallback logic ...
}
```

## Benefits

1. **Works with Serial Connection**: No TCP conflicts, uses database as source
2. **Dynamic Owner Detection**: Adapts to any node automatically
3. **No Hardcoded Values**: Uses actual data from Meshtastic
4. **Backward Compatible**: Falls back gracefully if owner not detected
5. **Clean Data Flow**: Database → Export → Merge → Visualization

## Maintenance

### When to Update

You should **not** need to update these files unless:
- Changing from Serial to TCP connection (update `main_bot.py` config)
- Wanting to enable hybrid mode (update `infoup_db.sh`)
- Changing web server upload destination (update `infoup_db.sh` scp command)

### Troubleshooting

**Map shows wrong owner node:**
- Check `info.json` - ensure owner node has `hopsAway: 0` or no hopsAway field
- Verify bot's Serial connection is working
- Check that `traffic_history.db` has recent data

**Links not showing:**
- Verify `info_neighbors.json` was generated
- Check that nodes are sending NEIGHBORINFO packets
- Ensure MQTT collector is running (if using MQTT neighbors)

**Title not updating:**
- Check browser console for JavaScript errors
- Verify `statsTitle` element exists in HTML
- Ensure `parseNodeInfo()` completed successfully

## Related Files

- `/home/dietpi/bot/map/infoup_db.sh` - Main export script
- `/home/dietpi/bot/map/export_neighbors_from_db.py` - Neighbor export
- `/home/dietpi/bot/map/export_nodes_from_db.py` - Node export
- `/home/dietpi/bot/map/merge_neighbor_data.py` - Data merger
- `/home/dietpi/bot/map/map.html` - Visualization
- `/home/dietpi/bot/traffic_history.db` - SQLite database
- `/home/dietpi/bot/node_names.json` - Node database

## References

- `map/README_NEIGHBORS.md` - Neighbor data collection
- `map/HYBRID_MODE_GUIDE.md` - Hybrid mode documentation
- `config.py.sample` - Bot configuration template
