# Mesh Neighbors Feature - Implementation Summary

## Overview

Successfully implemented a comprehensive mesh neighbors feature that collects, stores, and displays network topology information. This eliminates the TCP connection conflict between the bot and map generation scripts.

## What Was Implemented

### 1. Database Infrastructure (Phase 1 ✅)

**File:** `traffic_persistence.py`

Added new `neighbors` table to SQLite:
```sql
CREATE TABLE neighbors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    node_id TEXT NOT NULL,
    neighbor_id TEXT NOT NULL,
    snr REAL,
    last_rx_time INTEGER,
    node_broadcast_interval INTEGER
)
```

**Features:**
- Automatic cleanup (48h retention)
- Indexed for performance (timestamp, node_id, composite)
- CRUD operations: `save_neighbor_info()`, `load_neighbors()`
- JSON export: `export_neighbors_to_json()`

### 2. Automatic Data Collection (Phase 2 ✅)

**File:** `traffic_monitor.py`

Added neighbor extraction from NEIGHBORINFO_APP packets:
- Method: `_extract_neighbor_info(decoded, from_id)`
- Supports both dict and protobuf formats
- Handles multiple field name variations (camelCase, snake_case)
- Automatic storage in SQLite during packet processing

**Data Collected:**
- Node ID (who has neighbors)
- Neighbor ID (who they can hear)
- SNR (signal quality)
- Last RX time (when last heard)
- Broadcast interval (how often they transmit)

### 3. User Command (Phase 3 ✅)

**File:** `handlers/command_handlers/network_commands.py`

New `/neighbors` command:
```
/neighbors              → All neighbors (compact format for LoRa)
/neighbors tigro        → Filter by node name
/neighbors F547F        → Filter by node ID (partial match)
```

**Output Formats:**
- **Compact (LoRa, 180 chars)**: Top 3 nodes with neighbor counts and average SNR
- **Detailed (Telegram)**: Full list with all neighbors and individual SNR values

### 4. Map Integration (Phase 4 ✅)

**New Files:**
- `map/export_neighbors_from_db.py` - Database-based export script
- `map/infoup_db.sh` - Updated map generation workflow
- `map/README_NEIGHBORS.md` - Complete migration guide

**Benefits:**
- No TCP connection needed for map export
- Compatible with existing HTML maps
- JSON format matches original export_neighbors.py
- Can run while bot is running (no conflicts)

### 5. Documentation (Phase 5 ✅)

**Updated:**
- `CLAUDE.md` - Added mesh neighbors section, updated command reference
- `handlers/command_handlers/utility_commands.py` - Updated help text
- Help command now shows `/neighbors` in both LoRa and Telegram formats

**Created:**
- `map/README_NEIGHBORS.md` - Migration guide, troubleshooting, how-it-works

## How to Test

### 1. Basic Functionality Test

Once deployed, verify neighbor data is being collected:

```bash
# SSH to Raspberry Pi
ssh dietpi@your-pi-ip

# Check database for neighbor data
sqlite3 /home/dietpi/bot/traffic_history.db "SELECT COUNT(*) FROM neighbors;"

# Should return a number > 0 after a few hours
# (Nodes broadcast neighbor info every 15-30 minutes)
```

### 2. Test /neighbors Command

**Via Mesh:**
```
/neighbors
```
Should return compact format (under 180 chars), showing top 3 nodes.

**Via Telegram:**
```
/neighbors
```
Should return detailed format with all nodes and their neighbors.

**Filtered:**
```
/neighbors tigro
```
Should show only nodes matching "tigro" (case-insensitive).

### 3. Test Map Export

```bash
# Run new export script
cd /home/dietpi/bot/map
./export_neighbors_from_db.py > test_output.json

# Check output
cat test_output.json | jq '.statistics'

# Should show:
# {
#   "nodes_with_neighbors": X,
#   "total_neighbor_entries": Y,
#   "average_neighbors": Z
# }
```

### 4. Test Map Update Workflow

```bash
# Update to new workflow
cd /home/dietpi/bot/map
./infoup_db.sh

# Should complete without TCP connection errors
# Check that info_neighbors.json was created/updated
ls -lh info_neighbors.json
```

## Migration from Old Workflow

### Update Cron Jobs

**Old cron (may conflict with bot):**
```cron
0 */6 * * * /home/dietpi/bot/map/infoup.sh
```

**New cron (safe to run anytime):**
```cron
0 */6 * * * /home/dietpi/bot/map/infoup_db.sh
```

### Manual Update

```bash
# Edit crontab
crontab -e

# Replace infoup.sh with infoup_db.sh
# Save and exit
```

## Troubleshooting

### No Neighbor Data

**Symptom:** `/neighbors` returns "❌ Aucune donnée de voisinage disponible"

**Causes:**
1. Nodes haven't broadcast NEIGHBORINFO_APP yet (wait 15-30 min)
2. Neighbor info module disabled on nodes
3. Bot hasn't been running long enough

**Solutions:**
```bash
# Check if neighbor_info is enabled on nodes
meshtastic --host 192.168.1.38 --get neighbor_info.enabled

# Should return: neighbor_info.enabled: True

# If false, enable it:
meshtastic --host 192.168.1.38 --set neighbor_info.enabled true
```

### Database Locked Errors

**Symptom:** "database is locked" when running export

**Cause:** Bot has database open (normal)

**Solution:** This is expected and safe - SQLite allows concurrent reads. The export should work anyway. If persistent, temporarily stop the bot:

```bash
sudo systemctl stop meshbot
./export_neighbors_from_db.py > output.json
sudo systemctl start meshbot
```

### Empty JSON Export

**Symptom:** `export_neighbors_from_db.py` returns `{"nodes": {}}`

**Cause:** No data in timeframe (default 48h)

**Solutions:**
```bash
# Increase time window
./export_neighbors_from_db.py /path/to/traffic_history.db 72

# Check what data exists
sqlite3 traffic_history.db "SELECT MIN(timestamp), MAX(timestamp) FROM neighbors;"
```

## Architecture Benefits

### Before (TCP-based)
```
┌──────────┐         ┌──────────────┐
│ MeshBot  │─────TCP─►│ tigrog2:4403 │
└──────────┘         └──────────────┘
     ❌                      ▲
     │                       │
     │                   ❌ TCP
     │                       │
     └─────Conflict!────┌────┴────────┐
                        │ export_     │
                        │ neighbors.py│
                        └─────────────┘
```

### After (Database-based)
```
┌──────────┐         ┌──────────────┐
│ MeshBot  │─────TCP─►│ tigrog2:4403 │
└────┬─────┘         └──────────────┘
     │ Save to DB
     ▼
┌────────────────┐
│ traffic_       │
│ history.db     │
│ (neighbors     │
│  table)        │
└────┬───────────┘
     │ Read from DB
     ▼
┌────────────────┐
│ export_        │
│ neighbors_     │
│ from_db.py     │
└────────────────┘
     ✅ No conflicts!
```

## Next Steps

1. **Deploy** the updated code to production
2. **Wait** for neighbor data collection (15-30 minutes)
3. **Test** the `/neighbors` command
4. **Update** cron jobs to use `infoup_db.sh`
5. **Monitor** logs for NEIGHBORINFO_APP packet processing
6. **Enjoy** conflict-free map generation! 🎉

## Files Changed

**Core Implementation:**
- `traffic_persistence.py` - Database schema and methods
- `traffic_monitor.py` - Packet extraction and reporting
- `handlers/command_handlers/network_commands.py` - Command handler
- `handlers/message_router.py` - Command routing
- `handlers/command_handlers/utility_commands.py` - Help text

**Map Integration:**
- `map/export_neighbors_from_db.py` - New export script
- `map/infoup_db.sh` - New update workflow

**Documentation:**
- `CLAUDE.md` - Architecture and command docs
- `map/README_NEIGHBORS.md` - Migration guide

## Support

For issues or questions:
1. Check `map/README_NEIGHBORS.md` for troubleshooting
2. Review logs: `journalctl -u meshbot -f | grep -i neighbor`
3. Query database: `sqlite3 traffic_history.db "SELECT * FROM neighbors LIMIT 10;"`
4. Check CLAUDE.md section "Mesh Neighbors Feature (December 2025)"

---

**Implementation Date:** 2025-12-02  
**Status:** ✅ Complete and Ready for Deployment  
**Issue:** Add mesh neighbors function (#TBD)
