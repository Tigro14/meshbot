# Node Storage Migration: JSON to SQLite

## Summary

This migration removes the deprecated `node_names.json` file storage system and fully migrates to SQLite-based storage in the `meshtastic_nodes` table.

## Background

Previously, the bot maintained a dual-storage system:
- **JSON file** (`node_names.json`): Legacy storage for node names, positions, and metadata
- **SQLite database** (`meshtastic_nodes` table): Modern storage introduced for better scalability

This dual-storage approach was causing:
- Code complexity with redundant save operations
- Potential sync issues between JSON and SQLite
- Slower startup time loading from JSON
- File I/O overhead

## Changes Made

### Core Implementation

1. **traffic_persistence.py** - New SQLite query methods:
   - `get_all_meshtastic_nodes()` - Load all nodes from SQLite
   - `get_node_by_id(node_id)` - Query specific node by ID

2. **node_manager.py** - Removed JSON operations:
   - Removed `load_node_names()` method (read JSON)
   - Removed `save_node_names()` method (write JSON)
   - Added `load_nodes_from_sqlite()` method
   - Updated `get_node_name()` to query SQLite on cache miss
   - Removed `json` and `os` imports (no longer needed)
   - Removed `_last_node_save` throttling variable

3. **main_bot.py** - Integration changes:
   - Connect `node_manager.persistence` to `traffic_monitor.persistence`
   - Call `load_nodes_from_sqlite()` at startup
   - Removed `load_node_names()` call in start() method
   - Removed `save_node_names(force=True)` call in shutdown

### Supporting Files

4. **meshcore_cli_wrapper.py** - Removed JSON saves when adding contacts
5. **mqtt_neighbor_collector.py** - Removed JSON saves when processing NODEINFO
6. **view_node_positions.py** - Updated to read from SQLite instead of JSON
7. **debug_keys_mismatch.py** - Updated comments to reference SQLite

### Configuration

8. **config.py.sample** - Removed `NODE_NAMES_FILE` variable, added SQLite comment
9. **config.meshcore.example** - Removed `NODE_NAMES_FILE` variable

### Documentation

10. **CLAUDE.md** - Updated map data sources to reference SQLite
11. **test_node_sqlite_migration.py** - Comprehensive test suite (NEW)

## Testing

Created comprehensive test suite with 7 test cases:

1. ✅ Load from empty SQLite database
2. ✅ Save and load node with full metadata
3. ✅ Get node name from SQLite on cache miss
4. ✅ Fallback name generation for unknown nodes
5. ✅ Load multiple nodes from SQLite
6. ✅ Direct query via `get_node_by_id()`
7. ✅ Bulk query via `get_all_meshtastic_nodes()`

All tests pass successfully.

## Migration for Users

**No manual migration required!**

- The bot will start with an empty in-memory cache
- On startup, it loads all nodes from SQLite via `load_nodes_from_sqlite()`
- As new NODEINFO packets arrive, nodes are saved directly to SQLite
- Old `node_names.json` files can be safely deleted (they are no longer used)

## Benefits

### Performance
- ✅ Faster queries using SQLite indexes
- ✅ No file I/O overhead on every update
- ✅ Immediate consistency (no throttled writes)

### Code Quality
- ✅ Single source of truth (SQLite only)
- ✅ Removed ~100 lines of redundant code
- ✅ Simplified node manager logic
- ✅ Better separation of concerns

### Reliability
- ✅ ACID transactions (atomic, consistent, isolated, durable)
- ✅ No risk of JSON corruption
- ✅ No sync issues between storage backends
- ✅ Better error handling

## Backward Compatibility

### Map Export Scripts

The `map/export_nodes_from_db.py` script and related shell scripts still reference `node_names.json` as an optional input parameter for backward compatibility. These should be updated in a separate PR to use only SQLite.

Files affected (future work):
- `map/export_nodes_from_db.py`
- `map/infoup_db.sh`
- `map/test_*.sh` (multiple test scripts)

### Test Files

Test files that mock the node_manager may need to be updated to set `node_manager.persistence` instead of relying on JSON files. Search for `NODE_NAMES_FILE` in test files.

## Database Schema

Node data is stored in the `meshtastic_nodes` table:

```sql
CREATE TABLE meshtastic_nodes (
    node_id TEXT PRIMARY KEY,
    name TEXT,
    shortName TEXT,
    hwModel TEXT,
    publicKey BLOB,
    lat REAL,
    lon REAL,
    alt INTEGER,
    last_updated REAL,
    source TEXT DEFAULT 'radio'
)
```

Index for efficient queries:
```sql
CREATE INDEX idx_meshtastic_nodes_last_updated 
ON meshtastic_nodes(last_updated)
```

## Files Changed

### Modified (11 files)
1. `traffic_persistence.py` - Added SQLite query methods
2. `main_bot.py` - Integration and startup changes
3. `node_manager.py` - Core migration (removed JSON, added SQLite)
4. `meshcore_cli_wrapper.py` - Removed JSON saves
5. `mqtt_neighbor_collector.py` - Removed JSON saves
6. `view_node_positions.py` - Read from SQLite
7. `debug_keys_mismatch.py` - Updated comments
8. `config.py.sample` - Removed NODE_NAMES_FILE
9. `config.meshcore.example` - Removed NODE_NAMES_FILE
10. `CLAUDE.md` - Updated documentation
11. `test_node_sqlite_migration.py` - New test suite

### Created (2 files)
1. `test_node_sqlite_migration.py` - Comprehensive test suite
2. `NODE_STORAGE_MIGRATION.md` - This document

## Verification

To verify the migration worked correctly:

1. **Check node loading at startup:**
   ```
   grep "nœuds chargés depuis SQLite" /var/log/syslog
   ```

2. **Check SQLite database:**
   ```bash
   sqlite3 traffic_history.db "SELECT COUNT(*) FROM meshtastic_nodes;"
   ```

3. **Run tests:**
   ```bash
   python3 test_node_sqlite_migration.py -v
   ```

4. **Check for JSON references:**
   ```bash
   grep -r "node_names\.json" *.py | grep -v test_ | grep -v demo_
   ```
   Should only show map export scripts (future work).

## Rollback Plan

If issues arise, rollback is possible by:

1. Revert the commits in this PR
2. Ensure `node_names.json` exists with node data
3. Restart the bot

However, **this should not be necessary** as all functionality is preserved in SQLite.

## Future Enhancements

1. **Map Export Scripts**: Update to use only SQLite (no JSON input)
2. **Node Data Export**: Add CLI tool to export nodes from SQLite to JSON for external tools
3. **Node Data Import**: Add CLI tool to import nodes from JSON to SQLite (one-time migration helper)
4. **Performance Optimization**: Add more SQLite indexes for common queries

## Author

GitHub Copilot (assisted by Tigro14)

## Date

2026-01-22
