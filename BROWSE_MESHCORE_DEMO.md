# MeshCore Browse Support - Demo & Documentation

## Overview

The `browse_traffic_db.py` tool has been enhanced with **dual-mode support** for browsing both Meshtastic and MeshCore data. Users can now toggle between two independent data sources using a simple key press.

## Key Features

### 1. **Mode Toggle (m key)**

Press `m` to toggle between:
- 🔷 **Meshtastic Mode** - Browse Meshtastic radio data
- 🔶 **MeshCore Mode** - Browse MeshCore protocol data

### 2. **Independent View Cycles**

Each mode has its own view cycle accessible via `v` key:

**Meshtastic Mode (🔷):**
- 📦 Packets → 💬 Messages → 🌐 Node Stats → 📡 Meshtastic Nodes

**MeshCore Mode (🔶):**
- 📦 MC Packets → 💬 MC Messages → 🔧 MeshCore Contacts

### 3. **Unified Filter Support**

All filters work in both modes:
- **Type filter** (`f` key) - Filter by packet type
- **Encryption filter** (`e` key) - Show all/encrypted only/clear only
- **Search** (`/` key) - Search in messages
- **Sort order** (`s` key) - Toggle newest/oldest first
- **Node focus** (`F` key) - Focus on specific node's packets

## Usage Examples

### Starting the Browser

```bash
# Default usage (uses traffic_history.db)
python3 browse_traffic_db.py

# Specify custom database
python3 browse_traffic_db.py --db /path/to/custom.db
```

### Navigation Workflow

1. **Launch the browser** - Starts in Meshtastic mode, packets view
2. **Press `v`** - Cycle through Meshtastic views
3. **Press `m`** - Switch to MeshCore mode
4. **Press `v`** - Cycle through MeshCore views
5. **Press `m`** - Switch back to Meshtastic mode

### Filter Workflow

1. **View packets** (either mode)
2. **Press `f`** - Select packet type filter
3. **Type `1-9`** - Choose type from list
4. **Press `0`** - Clear filter

### Focus Workflow

1. **Navigate to nodes view** (press `v` until you reach nodes)
2. **Select a node** - Use arrow keys
3. **Press `F`** - Focus on that node
4. **View switches to packets** - Filtered by selected node
5. **Press `0`** - Clear node filter

## Data Sources

### Meshtastic Tables
- `packets` - All Meshtastic packets
- `public_messages` - Text messages only
- `node_stats` - Aggregated statistics
- `meshtastic_nodes` - Nodes learned via radio

### MeshCore Tables
- `meshcore_packets` - All MeshCore packets
- `meshcore_contacts` - Contacts learned via meshcore-cli

Note: MeshCore messages are derived from `meshcore_packets` where `packet_type = 'TEXT_MESSAGE_APP'`

## UI Indicators

### Header Indicators
- **Mode badge**: 🔷 MESHTASTIC or 🔶 MESHCORE
- **View icon**: 📦 💬 🌐 📡 🔧 (varies by view)
- **Active filters**: [Filter: TYPE], [🔒 Encrypted only], [Search: 'term']
- **Sort indicator**: [↓] for descending, [↑] for ascending

### Footer Indicators
- **Mode toggle hint**: `m:→MeshCore` or `m:→Meshtastic`
- **Next view hint**: `v:→Msgs` (shows next view in cycle)
- **Active features**: Context-aware based on current view

## Test Results

Using test database with:
- 3 Meshtastic nodes, 20 packets (8 messages)
- 3 MeshCore contacts, 15 packets (5 messages)

```
🔷 MESHTASTIC MODE TEST
  📦 Packets view: 20 items ✓
  💬 Messages view: 8 items ✓
  📡 Meshtastic nodes: 3 items ✓

🔶 MESHCORE MODE TEST
  📦 MeshCore packets: 15 items ✓
  💬 MeshCore messages: 5 items ✓
  🔧 MeshCore contacts: 3 items ✓

🔍 FILTER TESTS
  📦 Meshtastic TEXT_MESSAGE_APP filter: 8 items ✓
  📦 MeshCore TEXT_MESSAGE_APP filter: 5 items ✓
```

## Key Bindings Summary

| Key | Action | Description |
|-----|--------|-------------|
| `m` | **Toggle Mode** | Switch between Meshtastic and MeshCore |
| `v` | **Cycle View** | Next view in current mode |
| `f` | **Filter Type** | Filter by packet type (packets view) |
| `e` | **Filter Encryption** | Cycle: all → encrypted → clear |
| `s` | **Sort Order** | Toggle: newest ↓ ⟷ oldest ↑ |
| `F` | **Focus Node** | Filter packets by selected node |
| `0` | **Clear Node Filter** | Remove node focus |
| `/` | **Search** | Search in messages |
| `r` | **Refresh** | Reload data from database |
| `x` | **Export Text** | Export to .txt file |
| `c` | **Export CSV** | Export to .csv file |
| `S` | **Export Screen** | Export visible lines |
| `?` | **Help** | Show help screen |
| `q` / `ESC` | **Quit** | Exit browser |

## Implementation Details

### Code Changes
- Added `current_mode` state variable ('meshtastic' or 'meshcore')
- Added `load_meshcore_packets()` and `load_meshcore_messages()` methods
- Updated view cycling logic to be mode-aware
- Updated header/footer to show mode indicators
- Updated filter dialog to query appropriate table based on mode
- Updated all key handlers to support both modes

### Files Modified
- `browse_traffic_db.py` - Single file with all changes (~160 lines modified)

### Backward Compatibility
- Default mode is Meshtastic (maintains original behavior)
- Existing Meshtastic views work exactly as before
- No breaking changes to command-line interface

## Benefits

1. ✅ **Single Tool** - No need for separate browser for MeshCore
2. ✅ **Consistent UI** - Same interface for both data sources
3. ✅ **No Code Duplication** - Reuses drawing and filtering logic
4. ✅ **Easy Extension** - Can add more modes in the future
5. ✅ **Minimal Changes** - Small, focused modifications

## Future Enhancements

Potential improvements:
- Add statistics view for MeshCore mode
- Add combined view showing both sources
- Add filtering by time range
- Add real-time monitoring mode
- Add graph/chart visualizations

## Testing

To test with your own data:
1. Ensure `traffic_history.db` has both `meshcore_packets` and `meshcore_contacts` tables
2. Run the browser: `python3 browse_traffic_db.py`
3. Use `m` key to switch modes
4. Use `v` key to cycle through views
5. Test filters with `f`, `e`, `s` keys

## Troubleshooting

**Q: Mode toggle doesn't show MeshCore data**
A: Ensure your database has `meshcore_packets` and `meshcore_contacts` tables populated

**Q: Filter dialog shows no types**
A: Database may be empty for that mode. Check with `sqlite3 traffic_history.db "SELECT COUNT(*) FROM meshcore_packets;"`

**Q: Browser exits immediately**
A: Check database file exists and is readable. Use `--db` flag to specify path.

## Related Files

- `traffic_persistence.py` - Database schema and persistence logic
- `main_bot.py` - MeshCore packet collection
- `meshcore_serial_interface.py` - MeshCore protocol interface
