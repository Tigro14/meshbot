# MQTT Active Flag Fix Summary

**Issue Number:** #[Issue not specified in problem statement]  
**Date Fixed:** 2025-12-04  
**Status:** ✅ FIXED AND TESTED

---

## Problem Statement

When running the map export script `infoup_db.sh`, the output showed contradictory statistics:

```
📊 Enrichissement avec données SQLite...
   • MQTT active nodes: 17 nœuds        ← Detected 17 nodes ✓

📊 Statistiques:
   • Nœuds MQTT actifs: 0               ← Final count: ZERO ✗
   • Nœuds avec mqttLastHeard: 0        ← Final count: ZERO ✗
```

**Impact:** MQTT-active nodes were not visible on map.html (no yellow circles), and statistics were incorrect.

---

## Root Cause

### The Bug

**File:** `map/export_nodes_from_db.py`, line 138

```python
# BUGGY CODE:
node_key_decimal = node_id_str.lstrip('!')  # Just strip !, no conversion needed
```

### Database Format Discovery

Investigation revealed the database stores node IDs in **hexadecimal** format:

```sql
-- neighbors table schema
CREATE TABLE neighbors (
    node_id TEXT NOT NULL,        -- Stored as '!16fa4fdc' (hex!)
    neighbor_id TEXT NOT NULL,    -- Stored as '!16fa4fdc' (hex!)
    ...
);
```

**Example:**
- Node ID decimal: `385503196`
- Stored in DB as: `'!16fa4fdc'` (hex with ! prefix)

### The Mismatch

1. **load_neighbors()** returns dict with keys: `'!16fa4fdc'` (hex)
2. **Code stripped !** resulting in: `'16fa4fdc'` (still hex!)
3. **mqtt_active_nodes set** contained: `{'16fa4fdc', ...}` (hex strings)
4. **node_names.json** keys were: `{'385503196', ...}` (decimal strings)
5. **Comparison failed** at line 273: `if node_id_str in mqtt_active_nodes` ✗

### Misleading Comment

The original comment was incorrect:
```python
# WRONG COMMENT (removed):
# node_id_str format from database: '!385503196' (decimal with !)
# node_names.json keys are decimal strings: '385503196'
```

**Truth:** Database stores HEX, not decimal!

---

## The Fix

### Code Change

**File:** `map/export_nodes_from_db.py`, lines 134-140

```python
# FIXED CODE:
if formatted_neighbors:
    # Convert node_id from hex to decimal
    # node_id_str format from database: '!16fa4fdc' (hex with ! prefix)
    # node_names.json keys are decimal strings: '385503196'
    node_id_hex_stripped = node_id_str.lstrip('!')  # Strip ! prefix
    node_id_int = int(node_id_hex_stripped, 16)  # Convert hex to decimal
    node_key_decimal = str(node_id_int)  # Convert to string for dict key
    
    # Store neighbors with decimal key (matches node_names.json)
    neighbors_data[node_key_decimal] = formatted_neighbors  # ✓ Keys match now!
    
    # This node sent NEIGHBORINFO, so it's MQTT-active
    mqtt_active_nodes.add(node_key_decimal)
    
    # Store MQTT last heard timestamp
    if max_timestamp > 0:
        mqtt_last_heard_data[node_key_decimal] = int(max_timestamp)
```

### Conversion Example

```
Input:  '!16fa4fdc'     (from database)
Step 1: '16fa4fdc'      (strip !)
Step 2: 385503196       (convert hex to decimal int)
Step 3: '385503196'     (convert to string)
Result: Matches node_names.json key! ✓
```

---

## Testing

### Unit Test: test_mqtt_active_fix.py

**Purpose:** Verify hex-to-decimal conversion logic

**What it tests:**
1. Creates test neighbor data in SQLite with known hex IDs
2. Loads neighbors using `persistence.load_neighbors()`
3. Applies the conversion: hex → decimal
4. Verifies all nodes are correctly identified as MQTT-active
5. Confirms `mqttActive` and `mqttLastHeard` flags are set

**Test nodes:**
- `TEST_NODE_TIGRO = 385503196` → `!16fa4fdc` (real node from problem)
- `TEST_NODE_EXAMPLE = 305419896` → `!12345678` (simple hex pattern)
- `TEST_NODE_HIGH = 587202560` → `!23000000` (high value)

**Result:**
```
============================================================
✅ TEST PASSED: All MQTT active flags correctly set!
============================================================
```

### Integration Test: test_export_nodes_integration.py

**Purpose:** Test complete workflow end-to-end

**What it tests:**
1. Creates temporary `node_names.json` with 4 test nodes
2. Creates temporary `traffic_history.db` with neighbor data for 3 nodes
3. Runs the actual `export_nodes_from_db.py` script
4. Parses JSON output from stdout
5. Verifies `mqttActive` and `mqttLastHeard` flags are present
6. Confirms final statistics match expectations

**Result:**
```
======================================================================
✅ INTEGRATION TEST PASSED!
   • All 3 MQTT-active nodes have mqttActive flag
   • mqttLastHeard correctly set for 3 nodes
======================================================================
```

---

## Verification in Production

### Step 1: Run the Export Script

```bash
cd /home/dietpi/bot/map
./infoup_db.sh
```

### Step 2: Check Statistics Output

You should now see **consistent** statistics:

```
📊 Enrichissement avec données SQLite...
   • SNR disponible pour 39 nœuds
   • Last heard pour 128 nœuds
   • MQTT last heard pour 17 nœuds          ← 17 nodes detected
   • Hops disponible pour 128 nœuds
   • Neighbors disponible pour 17 nœuds
   • MQTT active nodes: 17 nœuds            ← 17 nodes detected

...

📊 Statistiques:
   • Total nœuds: 392
   • Nœuds avec position GPS: 236
   • Nœuds avec SNR: 39
   • Nœuds avec lastHeard: 128
   • Nœuds avec mqttLastHeard: 17           ← 17 in output ✓
   • Nœuds avec hopsAway: 128
   • Nœuds avec neighbors: 17
   • Nœuds MQTT actifs: 17                  ← 17 in output ✓
   • Nœuds MQTT-only ajoutés: 0
```

### Step 3: Verify JSON Output

```bash
# Count mqttActive flags in JSON
grep -c '"mqttActive": true' /home/dietpi/bot/map/info.json
```

**Expected:** Should return `17` (or however many MQTT-active nodes exist)

### Step 4: Inspect a Specific Node

```bash
jq '.["Nodes in mesh"]["!16fa4fdc"]' /home/dietpi/bot/map/info.json
```

**Expected output:**
```json
{
  "num": 385503196,
  "user": {
    "id": "!16fa4fdc",
    "longName": "NodeName",
    "shortName": "NODE"
  },
  "mqttActive": true,              ← NEW ✓
  "mqttLastHeard": 1733340000,     ← NEW ✓
  "neighbors": [
    {
      "nodeId": "!12345678",
      "snr": 8.5
    }
  ]
}
```

### Step 5: Visual Verification on Map

1. Open `map.html` in a web browser
2. Look for **bright yellow/gold circles** around node markers
3. Click on a node with yellow circle
4. Popup should show: **"🌐 MQTT: Actif"**

---

## Files Modified

### Core Fix
- `map/export_nodes_from_db.py` - Fixed hex-to-decimal conversion (lines 134-140)

### Tests Added
- `test_mqtt_active_fix.py` - Unit test for conversion logic
- `test_export_nodes_integration.py` - End-to-end integration test

### Documentation
- `map/FIX_MQTT_ACTIVE_FLAG.md` - Detailed fix documentation
- `MQTT_ACTIVE_FIX_SUMMARY.md` - This summary document

---

## Benefits of This Fix

1. **Correct Statistics**
   - Final counts now match enrichment detection
   - No more confusing "0 nodes" when 17 exist

2. **Map Visualization**
   - MQTT-active nodes now have yellow circles
   - Easy to identify which nodes are contributing neighbor data
   - Better network topology understanding

3. **Data Integrity**
   - `mqttActive` flag properly set in JSON
   - `mqttLastHeard` timestamps available for filtering
   - Phase 2 MQTT-only node detection now works

4. **Future Proofing**
   - Tests prevent regression
   - Clear documentation of database format
   - Correct comments guide future development

---

## Technical Details

### Why Does Database Use Hex?

**File:** `traffic_persistence.py::save_neighbor_info()`

```python
# Normalizer les IDs
if isinstance(node_id, int):
    node_id_str = f"!{node_id:08x}"  # ← Converts to hex!
else:
    node_id_str = node_id if node_id.startswith('!') else f"!{node_id}"
```

The database normalizes all node IDs to hex format with `!` prefix for consistency.

### Why Does node_names.json Use Decimal?

**File:** `node_manager.py`

Node manager stores nodes with integer keys (which JSON serializes as decimal strings):

```python
self.node_names[node_id] = {  # node_id is int (e.g., 385503196)
    'name': v.get('name', f"Node-{node_id:08x}"),
    'lat': v.get('lat'),
    ...
}
```

### Format Compatibility Matrix

| Component | Format | Example | Notes |
|-----------|--------|---------|-------|
| neighbors table | Hex with ! | `!16fa4fdc` | Normalized by save_neighbor_info() |
| packets table | Decimal string | `385503196` | from_id column |
| node_names.json | Decimal string | `385503196` | JSON keys (from int) |
| Meshtastic API | Hex with ! | `!16fa4fdc` | Standard format |

**Lesson:** Always convert to the target format when crossing boundaries!

---

## Related Issues

This fix may also resolve:
- Map nodes appearing without neighbor links
- Incorrect neighbor counts in visualizations
- MQTT-only nodes not appearing despite being in database
- Time filters excluding active MQTT nodes

---

## Key Takeaways

1. **Trust the code, not the comments** - Original comment said "decimal" but DB stored "hex"
2. **Variable names matter** - `node_key_decimal` contained hex, causing confusion
3. **Test with real data** - Unit tests revealed the conversion bug immediately
4. **Format consistency is critical** - Different components must agree on ID format
5. **Document assumptions** - Database format should be explicitly documented

---

## Support

If you encounter any issues after applying this fix:

1. **Check logs:** Look for conversion errors in stderr output
2. **Verify database:** Use SQLite to inspect neighbors table format
3. **Run tests:** Both test scripts should pass
4. **Compare output:** Before/after infoup_db.sh statistics should match

For questions or issues, refer to:
- `map/FIX_MQTT_ACTIVE_FLAG.md` - Detailed technical documentation
- `map/README_NEIGHBORS.md` - Neighbor system architecture
- `MQTT_NEIGHBOR_COLLECTOR.md` - MQTT collection system

---

**Fix Verified:** 2025-12-04  
**Tests Status:** ✅ ALL PASSING  
**Production Ready:** YES
