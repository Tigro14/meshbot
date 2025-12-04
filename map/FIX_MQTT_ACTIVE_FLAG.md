# Fix: MQTT Active Nodes Not Appearing on map.html

## Problem Statement (2025-12-04 Update)

MQTT-active nodes were detected during database enrichment but not appearing in final export statistics or on map.html:

**During enrichment:**
```
• MQTT active nodes: 17 nœuds
• MQTT last heard pour 17 nœuds
```

**In final statistics:**
```
• Nœuds MQTT actifs: 0        ← WRONG!
• Nœuds avec mqttLastHeard: 0 ← WRONG!
```

## Root Cause Analysis (UPDATED)

The issue was a **hex-to-decimal conversion bug** in `export_nodes_from_db.py`:

### Actual Database Format

**CRITICAL DISCOVERY:** The database stores node IDs in **HEX format**, not decimal!

1. **Database Storage** (`traffic_persistence.py::save_neighbor_info()`):
   - Receives node ID: `385503196` (decimal integer or string)
   - **Normalizes to hex with ! prefix**: `'!16fa4fdc'`
   - Stores in neighbors table: `node_id = '!16fa4fdc'` (HEX!)

2. **Database Retrieval** (`traffic_persistence.py::load_neighbors()`):
   - Returns dict with keys: `'!16fa4fdc'` (HEX with `!`)

3. **Export Processing** (`export_nodes_from_db.py`):
   - **OLD CODE** (buggy at line 138):
     ```python
     node_key_decimal = node_id_str.lstrip('!')  # Results in '16fa4fdc' (still hex!)
     # Comment incorrectly claimed this was decimal!
     ```
   - **node_names.json** keys are decimal strings: `'385503196'`
   - **Mismatch:** `'16fa4fdc'` (hex) ≠ `'385503196'` (decimal)
   - Result: `mqttActive` flag never set because keys don't match

### Why This Happened

The original comment at lines 136-137 was **INCORRECT**:
```python
# WRONG COMMENT:
# node_id_str format from database: '!385503196' (decimal with !)
# node_names.json keys are decimal strings: '385503196'
```

**Reality:**
- Database stores: `'!16fa4fdc'` (hex with !)
- After `lstrip('!')`: `'16fa4fdc'` (hex without !)
- Variable named `node_key_decimal` but contains hex string!
- Needed conversion: `int('16fa4fdc', 16)` → `385503196`

## Solution (2025-12-04 FIX)

### Code Changes

**File: `map/export_nodes_from_db.py`**

**Before** (lines 134-142, BUGGY):
```python
if formatted_neighbors:
    # Remove ! prefix from node_id_str
    # node_id_str format from database: '!385503196' (decimal with !)  ← WRONG!
    # node_names.json keys are decimal strings: '385503196'
    node_key_decimal = node_id_str.lstrip('!')  # Just strip !, no conversion needed
    
    # Store neighbors with decimal key (matches node_names.json)
    neighbors_data[node_key_decimal] = formatted_neighbors  # ← BUG: hex ≠ decimal
```

**After** (lines 134-140, FIXED):
```python
if formatted_neighbors:
    # Convert node_id from hex to decimal
    # node_id_str format from database: '!16fa4fdc' (hex with ! prefix)
    # node_names.json keys are decimal strings: '385503196'
    node_id_hex_stripped = node_id_str.lstrip('!')  # Strip ! prefix → '16fa4fdc'
    node_id_int = int(node_id_hex_stripped, 16)  # Convert hex to decimal → 385503196
    node_key_decimal = str(node_id_int)  # Convert to string for dict key → '385503196'
    
    # Store neighbors with decimal key (matches node_names.json)
    neighbors_data[node_key_decimal] = formatted_neighbors  # ✓ Keys match!
```

**Example conversion:**
```python
'!16fa4fdc' → '16fa4fdc' → 385503196 → '385503196'
```

**Key Changes:**
1. **Correct hex-to-decimal conversion** using `int(hex_str, 16)`
2. **Accurate comments** explaining the actual database format
3. **Proper variable naming** tracking conversion steps

## Testing

### ✅ NEW: test_mqtt_active_fix.py (2025-12-04)
- Unit test for hex-to-decimal conversion logic
- Creates test neighbor data in SQLite with hex IDs
- Verifies conversion: `'!16fa4fdc'` → `'385503196'`
- Confirms `mqttActive` flags are set correctly
- Result: **PASS** ✅

```bash
$ python3 test_mqtt_active_fix.py
============================================================
✅ TEST PASSED: All MQTT active flags correctly set!
============================================================
```

### ✅ NEW: test_export_nodes_integration.py (2025-12-04)
- Full workflow integration test
- Creates temporary `node_names.json` and `traffic_history.db`
- Runs actual `export_nodes_from_db.py` script
- Verifies JSON output has correct `mqttActive` and `mqttLastHeard` flags
- Result: **PASS** ✅

```bash
$ python3 test_export_nodes_integration.py
======================================================================
✅ INTEGRATION TEST PASSED!
   • All 3 MQTT-active nodes have mqttActive flag
   • mqttLastHeard correctly set for 3 nodes
======================================================================
```

### ✅ Legacy Tests (Still Pass)

All existing tests continue to pass:

#### test_mqtt_active.sh
- Creates nodes with NEIGHBORINFO data
- Verifies `mqttActive` flag is set correctly
- Result: **PASS** ✅

#### test_mqtt_only_nodes.sh
- Tests nodes heard only via MQTT (not in node_names.json)
- Verifies they are added to output with `mqttActive: true`
- Result: **PASS** ✅

#### test_mqtt_lastheard.sh
- Tests that MQTT-only nodes have `lastHeard` timestamps
- Ensures they appear in time-filtered views
- Result: **PASS** ✅

## Visual Verification

### Expected Behavior on map.html

1. **Nodes with `mqttActive: true` in info.json** will have:
   - A bright yellow/gold circle (5px border) around their marker
   - Popup text: "🌐 MQTT: **Actif**"

2. **Legend** shows:
   - Yellow circle icon with text: "🌐 MQTT actif"

3. **Implementation** (already present in map.html, lines 898-914):
   ```javascript
   if (node.mqttActive) {
       const hivizCircle = L.circleMarker([lat, lon], {
           radius: 20,
           fillColor: 'transparent',
           color: '#FFD700',  // Bright yellow/gold
           weight: 5,
           opacity: 1,
           fillOpacity: 0,
           className: 'mqtt-active-hiviz',
           interactive: false
       });
       hivizCircle.addTo(map);
   }
   ```

## Verification Steps

To verify the fix works in production:

1. **Regenerate info.json**:
   ```bash
   cd /home/dietpi/bot/map
   ./infoup_db.sh
   ```

2. **Check for consistent statistics** in stderr output:
   ```
   📊 Enrichissement avec données SQLite...
      • MQTT active nodes: 17 nœuds        ← Should match final stats
   
   📊 Statistiques:
      • Nœuds MQTT actifs: 17              ← Should match enrichment
      • Nœuds avec mqttLastHeard: 17       ← Should match enrichment
   ```

3. **Check mqttActive flags in JSON**:
   ```bash
   grep -c "mqttActive.*true" /home/dietpi/bot/map/info.json
   ```
   
   Should return: `17` (or however many MQTT-active nodes exist)

4. **Inspect a specific node**:
   ```bash
   jq '.["Nodes in mesh"]["!16fa4fdc"]' /home/dietpi/bot/map/info.json
   ```
   
   Expected output should include:
   ```json
   {
     "mqttActive": true,
     "mqttLastHeard": 1733340000,
     "neighbors": [...]
   }
   ```

5. **Open map.html** in a web browser

6. **Verify yellow circles** appear around nodes that have NEIGHBORINFO data

7. **Click on a node** with yellow circle and verify popup shows:
   > 🌐 MQTT: **Actif**

## Impact

- **Users can now see which nodes are actively reporting neighbor data via MQTT**
- **Network topology visualization is more complete**
- **Helps identify nodes that are:
  - Connected to MQTT broker
  - Sending regular NEIGHBORINFO broadcasts
  - Contributing to network topology data**

## Files Changed

**2025-12-04 Update:**
- `map/export_nodes_from_db.py` - Fixed hex-to-decimal conversion (lines 134-140)
- `test_mqtt_active_fix.py` - NEW: Unit test for conversion fix
- `test_export_nodes_integration.py` - NEW: Integration test for full workflow
- `map/FIX_MQTT_ACTIVE_FLAG.md` - Updated with latest fix details

**Original Fix:**
- `map/export_nodes_from_db.py` - Fixed node ID format handling

## Files Verified (No Changes Needed)

- `map/map.html` - Already has correct visualization code
- `traffic_persistence.py` - Database format is correct
- All test scripts pass without modification

## Related Documentation

- `map/MQTT_HIVIZ_FEATURE.md` - Original feature documentation
- `map/FIX_MQTT_ONLY_NODES.md` - Related fix for MQTT-only node visibility
- `map/test_visual_mqtt.html` - Visual test documentation
