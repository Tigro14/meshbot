# Issue Resolution: Remove TCP Node Info from infoup_db.sh

## Issue
Remove the "Récupération des infos nœuds via meshtastic" remaining via TCP from `map/infoup_db.sh` and replace by a call to SQLite bot db.

## Root Cause
The `infoup_db.sh` script was using `meshtastic --host 192.168.1.38 --info` to retrieve node information via a TCP connection to the Meshtastic node. This created conflicts with the bot's own TCP connection due to the "unique TCP session" limitation.

## Solution Overview
Created a new export script (`export_nodes_from_db.py`) that reads node information from local files maintained by the bot, eliminating the need for a TCP connection entirely.

## Implementation Details

### 1. New Script: `export_nodes_from_db.py`

**Purpose**: Export node information from bot's local data sources

**Data Sources**:
- **Primary**: `node_names.json`
  - Maintained by `NodeManager` class
  - Contains: node IDs, names, GPS coordinates, last update
  
- **Secondary** (optional): `traffic_history.db`
  - Contains SNR values from recent packets
  - Contains lastHeard timestamps

**Output Format**: JSON compatible with `meshtastic --info`

**Key Features**:
- Clean output: JSON on stdout, logs on stderr
- Graceful degradation if database unavailable
- Automatic node ID formatting (hex with `!` prefix)
- Position data included when available
- Signal metrics (SNR, lastHeard) from database

### 2. Modified Script: `infoup_db.sh`

**Removed Lines**:
```bash
meshtastic --host 192.168.1.38 --info > $JSON_FILE
python3 info_json_clean.py info.json info_clean.json
mv info_clean.json $JSON_FILE
```

**Added Lines**:
```bash
NODE_NAMES_FILE="/home/dietpi/bot/node_names.json"
/home/dietpi/bot/map/export_nodes_from_db.py "$NODE_NAMES_FILE" "$DB_PATH" 48 > $JSON_FILE
```

**Result**: 
- TCP connection completely eliminated
- No post-processing cleanup needed
- Simpler and more reliable workflow

### 3. Documentation

**Updated**: `map/README_NEIGHBORS.md`
- Added export_nodes_from_db.py to file list
- Enhanced migration guide with node export examples
- Updated "How It Works" with node collection details

**New**: `map/README_EXPORT_NODES.md`
- Complete usage guide
- Data source documentation
- Error handling examples
- Before/after comparison

### 4. Testing

**New**: `map/test_export_nodes.sh`
- Automated test script
- Creates sample data
- Validates JSON structure
- All tests passing ✅

## Testing Results

```bash
$ cd map && ./test_export_nodes.sh
🧪 Test export_nodes_from_db.py
================================
✅ Created sample node_names.json with 3 nodes
✅ Output file created: 841 bytes
✅ JSON syntax is valid
✅ Has 'Nodes in mesh' key
✅ Found node !16fa4fdc
✅ Has user information
✅ Has position data
✅ Correct node count: 3
✅ All tests passed!
```

## Benefits

### Technical Benefits
✅ **No TCP conflicts**: Bot and map generation run independently
✅ **Simpler workflow**: Direct JSON output, no cleanup needed
✅ **Better reliability**: No dependency on meshtastic CLI tool
✅ **Historical data**: Enriched with SNR and lastHeard from database
✅ **Graceful degradation**: Works even if database unavailable

### Operational Benefits
✅ **Can run anytime**: No need to stop bot for map updates
✅ **Better performance**: No network calls, reads local files
✅ **Easier debugging**: Clear separation of logs and output
✅ **More maintainable**: Pure Python, no shell parsing

## Files Changed

| File | Type | Lines | Description |
|------|------|-------|-------------|
| `map/export_nodes_from_db.py` | NEW | 252 | Node export script |
| `map/infoup_db.sh` | MODIFIED | -10/+4 | Remove TCP calls |
| `map/README_NEIGHBORS.md` | UPDATED | +40 | Enhanced docs |
| `map/README_EXPORT_NODES.md` | NEW | 193 | Usage guide |
| `map/test_export_nodes.sh` | NEW | 130 | Test script |

**Total**: 3 new files, 2 modified files

## Backward Compatibility

- ✅ Legacy scripts (`infoup.sh`, `infoup_improved.sh`) remain unchanged
- ✅ Users can continue using TCP-based approach if needed
- ✅ `export_neighbors.py` (TCP-based) kept for compatibility
- ✅ No breaking changes to existing workflows

## Migration Path

### For Users Currently Using `infoup.sh` or `infoup_improved.sh`

1. Switch to `infoup_db.sh` in cron jobs:
   ```bash
   # Old
   */10 * * * * /home/dietpi/bot/map/infoup.sh
   
   # New
   */10 * * * * /home/dietpi/bot/map/infoup_db.sh
   ```

2. Verify node_names.json exists:
   ```bash
   ls -lh /home/dietpi/bot/node_names.json
   ```

3. Test manually:
   ```bash
   cd /home/dietpi/bot/map
   ./infoup_db.sh
   ```

## Verification

### Before (with TCP)
```bash
$ grep "meshtastic --host" map/infoup_db.sh
meshtastic --host 192.168.1.38 --info > $JSON_FILE
```

### After (no TCP)
```bash
$ grep "meshtastic --host" map/infoup_db.sh
$ # No output - TCP call removed
```

### Confirm Only Comments Reference TCP
```bash
$ grep -i tcp map/infoup_db.sh
# Version améliorée: utilise la base de données SQLite au lieu d'une connexion TCP
# Évite les conflits de connexion TCP unique
# Utiliser le nouveau script qui lit depuis la DB au lieu de se connecter en TCP
```

All references are in comments explaining we DON'T use TCP ✅

## Conclusion

**Issue Status**: ✅ **RESOLVED**

The TCP-based `meshtastic --host --info` call has been completely removed from `infoup_db.sh` and replaced with a local file-based export system. The solution:

1. ✅ Eliminates TCP connection conflicts
2. ✅ Provides same functionality (node information export)
3. ✅ Adds enhancements (SNR, lastHeard enrichment)
4. ✅ Is well-tested (automated test suite)
5. ✅ Is well-documented (comprehensive guides)
6. ✅ Maintains backward compatibility (legacy scripts unchanged)

**Ready for production deployment.**

## See Also

- `map/export_nodes_from_db.py` - Implementation
- `map/README_EXPORT_NODES.md` - Usage guide
- `map/README_NEIGHBORS.md` - Overall architecture
- `map/test_export_nodes.sh` - Test suite
