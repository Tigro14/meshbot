# Mesh Network Mapping

This directory contains tools for visualizing the Meshtastic network topology.

## Files

### Data Export Scripts

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

- **`infoup_db.sh`** (NEW) - Update maps using database export
  - Uses `export_neighbors_from_db.py` instead of TCP
  - Recommended for use when bot is running
  - Avoids TCP connection conflicts

- **`infoup.sh`** (LEGACY) - Original update script using TCP
  - Uses `export_neighbors.py`
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
# Conflicts with bot if both try to connect
./export_neighbors.py > info_neighbors.json
```

**New workflow (no conflicts):**
```bash
# Uses bot's database - no TCP needed
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

1. **Bot collects NEIGHBORINFO_APP packets** automatically
2. **Traffic monitor extracts neighbor data** from packets
3. **SQLite database stores** node relationships with metadata:
   - Node ID
   - Neighbor ID
   - SNR (signal quality)
   - Last RX time
   - Broadcast interval

### Data Export

1. **export_neighbors_from_db.py** queries the database
2. Generates JSON compatible with HTML maps
3. Outputs to stdout for piping or redirection

### Benefits

✅ **No TCP conflicts** - bot and maps can both access data
✅ **Historical data** - 48 hours of neighbor relationships
✅ **Automatic updates** - data collected continuously by bot
✅ **Simplified architecture** - single data source

## Troubleshooting

### No neighbor data in database

**Problem:** `export_neighbors_from_db.py` returns empty JSON

**Solutions:**
1. Check if nodes have neighbor_info enabled:
   ```bash
   meshtastic --host 192.168.1.38 --get neighbor_info
   ```
2. Verify bot is collecting NEIGHBORINFO_APP packets:
   ```bash
   sqlite3 ../traffic_history.db "SELECT COUNT(*) FROM neighbors;"
   ```
3. Wait for neighbor broadcasts (typically every 15-30 minutes)

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

- `/neighbors` command - Display neighbors via mesh/Telegram
- `CLAUDE.md` - Full architecture documentation
- `traffic_persistence.py` - Database schema
