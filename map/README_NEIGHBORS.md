# Mesh Network Mapping

This directory contains tools for visualizing the Meshtastic network topology.

## Files

### Data Export Scripts

- **`export_nodes_from_db.py`** (NEW) - Export node information from bot's local files
  - Reads from `node_names.json` (maintained by bot)
  - Enriches with data from `traffic_history.db` (SNR, lastHeard)
  - No TCP connection needed (avoids "unique session" violations)
  - Output: JSON on stdout (compatible with `meshtastic --info`), logs on stderr
  - Usage: `./export_nodes_from_db.py [node_names_file] [db_path] [hours]`
  - Replaces: `meshtastic --host <ip> --info`

- **`export_neighbors_from_db.py`** (NEW) - Export neighbor data from bot's SQLite database
  - Reads from `traffic_history.db`
  - No TCP connection needed (avoids "unique session" violations)
  - Output: JSON on stdout, logs on stderr
  - Usage: `./export_neighbors_from_db.py [db_path] [hours]`

- **`export_neighbors.py`** (LEGACY) - Export neighbor data via TCP connection
  - Connects directly to Meshtastic node via TCP
  - Can conflict with bot's TCP connection
  - Kept for backward compatibility

### Update Scripts

- **`infoup_db.sh`** (RECOMMENDED) - Update maps using database export
  - Uses `export_nodes_from_db.py` for node information (no TCP needed)
  - Uses `export_neighbors_from_db.py` for neighbor data (no TCP needed)
  - Recommended for use when bot is running
  - Completely avoids TCP connection conflicts

- **`infoup.sh`** (LEGACY) - Original update script using TCP
  - Uses `meshtastic --host --info` and `export_neighbors.py`
  - May conflict with running bot
  - Use only when bot is stopped

### HTML Maps

- **`mesh_map.html`** - Interactive network topology map
- **`map.html`** - Geographic node map
- **`meshlink.html`** - Link quality visualization

### Utilities

- **`info_json_clean.py`** - Clean node info JSON
- **`validate_map_data.sh`** - Validate generated JSON

## Migration Guide

### From TCP to Database-based Export

**Old workflow (with TCP conflicts):**
```bash
# Node information via TCP - conflicts with bot
meshtastic --host 192.168.1.38 --info > info.json

# Neighbor data via TCP - conflicts with bot
./export_neighbors.py > info_neighbors.json
```

**New workflow (no conflicts):**
```bash
# Node information from local files - no TCP needed
./export_nodes_from_db.py ../node_names.json ../traffic_history.db 48 > info.json

# Neighbor data from database - no TCP needed
./export_neighbors_from_db.py ../traffic_history.db 48 > info_neighbors.json
```

### Updating Cron Jobs

If you have a cron job running `infoup.sh`, update it to use `infoup_db.sh`:

```bash
# Old (may conflict with bot)
0 */6 * * * /home/dietpi/bot/map/infoup.sh

# New (safe to run anytime)
0 */6 * * * /home/dietpi/bot/map/infoup_db.sh
```

## How It Works

### Data Collection

#### Node Information
1. **Bot collects NODEINFO_APP packets** with node names and details
2. **Bot collects POSITION_APP packets** with GPS coordinates
3. **NodeManager maintains `node_names.json`** with consolidated node data:
   - Node ID
   - Long name / short name
   - GPS coordinates (latitude, longitude, altitude)
   - Last update timestamp
4. **Traffic monitor stores packets in SQLite** with SNR and signal metrics

#### Neighbor Information
1. **Bot collects NEIGHBORINFO_APP packets** automatically
2. **Traffic monitor extracts neighbor data** from packets
3. **SQLite database stores** node relationships with metadata:
   - Node ID
   - Neighbor ID
   - SNR (signal quality)
   - Last RX time
   - Broadcast interval

### Data Export

#### Node Export
1. **export_nodes_from_db.py** reads `node_names.json`
2. Enriches with SQLite data (SNR, lastHeard from packets)
3. Generates JSON compatible with `meshtastic --info` format
4. Outputs to stdout for piping or redirection

#### Neighbor Export
1. **export_neighbors_from_db.py** queries the database
2. Generates JSON compatible with HTML maps
3. Outputs to stdout for piping or redirection

### Benefits

✅ **No TCP conflicts** - bot and maps can both access data simultaneously (database-only mode)
✅ **Historical data** - 48 hours of neighbor relationships and node metrics
✅ **Automatic updates** - data collected continuously by bot
✅ **Simplified architecture** - single data source (bot's files)
✅ **Complete replacement** - no need for `meshtastic --host --info` TCP connection
✅ **Hybrid mode available** - optional TCP query for complete neighbor data (see HYBRID_MODE_GUIDE.md)

## Hybrid Mode (New Feature)

If you need complete neighbor data (all nodes, not just packets bot received), you can use hybrid mode:

```bash
# Stop bot first to avoid conflicts
sudo systemctl stop meshbot

# Run hybrid mode (queries TCP node + merges with database)
./export_neighbors_from_db.py --tcp-query 192.168.1.38 > info_neighbors.json

# Restart bot
sudo systemctl start meshbot
```

**See `HYBRID_MODE_GUIDE.md` for:**
- Detailed explanation of database-only vs hybrid modes
- Configuration via `infoup_db.sh`
- Recommended usage patterns
- Troubleshooting tips

## Troubleshooting

### No neighbor data in database

**Problem:** `export_neighbors_from_db.py` returns empty JSON or very few nodes (e.g., 42 instead of 500)

**Root Cause:** Database-based collection only captures NEIGHBORINFO_APP packets bot receives

**Solutions:**
1. **Wait longer:** Nodes broadcast every 15-30 minutes, allow 1-2 hours for data collection
2. **Check neighbor_info enabled:**
   ```bash
   meshtastic --host 192.168.1.38 --get neighbor_info
   ```
3. **Verify bot is collecting packets:**
   ```bash
   sqlite3 ../traffic_history.db "SELECT COUNT(*) FROM neighbors;"
   ```
4. **Use hybrid mode for complete data:**
   ```bash
   # See HYBRID_MODE_GUIDE.md for details
   ./export_neighbors_from_db.py --tcp-query 192.168.1.38
   ```

### Database locked error

**Problem:** "database is locked" when running export

**Solutions:**
1. Bot has the database open - this is normal and safe
2. SQLite allows concurrent reads - script should work anyway
3. If persistent, stop bot temporarily and retry

### Old data showing

**Problem:** Maps show outdated neighbor relationships

**Solutions:**
1. Increase hours parameter: `./export_neighbors_from_db.py ../traffic_history.db 72`
2. Check database retention: `SELECT MIN(timestamp) FROM neighbors;`
3. Verify nodes are still broadcasting: check bot logs for NEIGHBORINFO_APP

## Future Improvements

- [ ] Add `/neighbors json` command to export via Telegram
- [ ] Web UI for browsing neighbor history
- [ ] Automatic map regeneration on neighbor updates
- [ ] Graph evolution over time

## See Also

- `HYBRID_MODE_GUIDE.md` - Complete guide for hybrid mode (database + TCP query)
- `/neighbors` command - Display neighbors via mesh/Telegram
- `CLAUDE.md` - Full architecture documentation
- `traffic_persistence.py` - Database schema
- Issue #97 - Map visualization and neighbor data discussion
