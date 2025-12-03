# Hybrid Mode Guide - Complete Neighbor Data Collection

## Problem Statement

The database-based neighbor collection (implemented Dec 2025) only captures neighbor data from NEIGHBORINFO_APP packets that the bot receives. This is fundamentally different from the old TCP-based export which could query the full node database directly.

**Issue #97 Comment:** The neighbor data reduced from 500 nodes (TCP-based) to 42 nodes (database-based).

### Root Cause

**Old TCP-based system (`export_neighbors.py`):**
- Directly queries Meshtastic node via TCP
- Gets ALL neighbor data stored in node's database
- Result: 500 neighbor relationships

**New database-based system (`export_neighbors_from_db.py`):**
- Only collects neighbor data from NEIGHBORINFO_APP packets received by bot
- Passive collection - waits for broadcasts
- NEIGHBORINFO_APP packets:
  - Broadcast every 15-30 minutes per node
  - May not reach bot due to distance/signal
  - 48-hour window may miss infrequent broadcasters
- Result: 42 neighbor relationships (only from packets bot has received)

## Solution: Hybrid Mode

The updated `export_neighbors_from_db.py` now supports two modes:

### 1. DATABASE-ONLY Mode (Default, Safe)

```bash
./export_neighbors_from_db.py
```

**Characteristics:**
- ✅ Safe to run while bot is running (no TCP conflicts)
- ✅ No risk of "unique TCP session" violations
- ⚠️ May have incomplete neighbor data (only packets bot received)
- ⚠️ Depends on NEIGHBORINFO_APP broadcast frequency

**Use when:**
- Bot is running and using TCP connection
- You want guaranteed safety
- Partial neighbor data is acceptable

### 2. HYBRID Mode (Complete, May Conflict)

```bash
./export_neighbors_from_db.py --tcp-query 192.168.1.38
```

**Characteristics:**
- ✅ Gets complete neighbor data from node's database
- ✅ Merges with database data for maximum completeness
- ⚠️ May conflict with bot's TCP connection
- ⚠️ Requires bot to be stopped OR use a different node

**Use when:**
- You need complete neighbor data (all 500+ nodes)
- Bot is stopped temporarily
- Bot uses a different node for TCP connection

## Implementation Details

### How Hybrid Mode Works

1. **Query database** for neighbor data (packets bot received)
2. **Query TCP node** for complete neighbor data (full node database)
3. **Merge data:**
   - Prefer TCP data (more complete)
   - Add database-only nodes not in TCP data
   - Calculate combined statistics

### Merge Strategy

```
TCP data (500 nodes) + Database-only nodes (e.g., 5 unique) = 505 total nodes
```

The merge prefers TCP data when available and adds any unique nodes found only in the database.

## Usage Examples

### Example 1: Database-Only (Safe, Default)

```bash
cd /home/dietpi/bot/map
./export_neighbors_from_db.py > info_neighbors.json 2> export.log

# Check statistics
cat export.log | grep "Statistiques"
```

**Output:**
```
📊 Statistiques finales:
   • Source: meshbot_database
   • Nœuds avec voisins: 42/42
   • Total entrées voisins: 156
   • Moyenne voisins/nœud: 3.7
```

### Example 2: Hybrid Mode (Complete)

```bash
# Stop bot first to avoid conflicts
sudo systemctl stop meshbot

# Run hybrid mode
cd /home/dietpi/bot/map
./export_neighbors_from_db.py --tcp-query 192.168.1.38 > info_neighbors.json 2> export.log

# Restart bot
sudo systemctl start meshbot

# Check statistics
cat export.log | grep "Statistiques"
```

**Output:**
```
📊 Statistiques finales:
   • Source: hybrid_db+tcp
   • Nœuds avec voisins: 500/500
   • Total entrées voisins: 2145
   • Moyenne voisins/nœud: 4.3
   • Nœuds TCP: 495
   • Nœuds DB uniquement: 5
```

### Example 3: Hybrid with Different Node

```bash
# If bot uses 192.168.1.38, query a different node
./export_neighbors_from_db.py --tcp-query 192.168.1.39 > info_neighbors.json
```

## Configuration via `infoup_db.sh`

Edit `infoup_db.sh` to enable hybrid mode:

```bash
# Edit configuration section
nano /home/dietpi/bot/map/infoup_db.sh

# Set TCP_QUERY_HOST to enable hybrid mode
TCP_QUERY_HOST="192.168.1.38"  # Set to node IP
TCP_QUERY_PORT="4403"           # Default Meshtastic TCP port

# Or leave empty for database-only mode
TCP_QUERY_HOST=""  # Safe, no TCP query
```

## Recommendations

### For Production (Bot Running 24/7)

**Use DATABASE-ONLY mode:**
```bash
# In infoup_db.sh
TCP_QUERY_HOST=""  # Leave empty
```

**Rationale:**
- Safe, no TCP conflicts
- Bot will eventually collect most neighbor data
- Acceptable trade-off for safety

### For Complete Maps (Bot Can Be Stopped)

**Use HYBRID mode with scheduled stops:**
```bash
# Cron job: Stop bot, run hybrid export, restart bot
0 */6 * * * /home/dietpi/bot/map/infoup_hybrid_scheduled.sh
```

**Create `infoup_hybrid_scheduled.sh`:**
```bash
#!/bin/bash
# Stop bot
sudo systemctl stop meshbot

# Run hybrid export
cd /home/dietpi/bot/map
TCP_QUERY_HOST="192.168.1.38" ./infoup_db.sh

# Restart bot
sudo systemctl start meshbot
```

### For Multi-Node Setups

**Use different nodes for bot and export:**
```bash
# Bot uses: 192.168.1.38 (serial or TCP)
# Export uses: 192.168.1.39 (different node)

# In infoup_db.sh
TCP_QUERY_HOST="192.168.1.39"  # No conflict!
```

## Troubleshooting

### Issue: "database is locked"

**Cause:** Bot has database open (normal for concurrent reads)

**Solution:** SQLite allows concurrent reads - should work anyway. If persistent:
```bash
sudo systemctl stop meshbot
./export_neighbors_from_db.py > output.json
sudo systemctl start meshbot
```

### Issue: "Connection refused" on TCP query

**Cause:** Node not reachable or TCP interface disabled

**Solutions:**
1. Check node is reachable: `ping 192.168.1.38`
2. Check TCP interface enabled: `meshtastic --host 192.168.1.38 --info`
3. Check firewall: `sudo iptables -L | grep 4403`

### Issue: Still only 42 nodes in hybrid mode

**Cause:** TCP query failed, fell back to database-only

**Solutions:**
1. Check export.log for TCP errors
2. Verify node has neighbor data: `meshtastic --host 192.168.1.38 --info | grep neighbor`
3. Ensure neighbor_info module enabled on nodes

## Migration from Old Workflow

### Old Workflow (TCP-only, conflicts)

```bash
# In infoup.sh
./export_neighbors.py > info_neighbors.json
```

**Problems:**
- Conflicts with bot's TCP connection
- Bot must be stopped
- No historical data

### New Workflow (Hybrid, flexible)

```bash
# In infoup_db.sh
# Option 1: Safe, partial data
TCP_QUERY_HOST=""
./infoup_db.sh

# Option 2: Complete data, scheduled stops
# Stop bot, query TCP, restart bot
```

**Benefits:**
- Flexible modes (safe vs complete)
- Historical database data
- Clear conflict warnings

## Performance Considerations

### Database-Only Mode
- **Fast:** No TCP connection overhead
- **Safe:** No conflicts
- **Incomplete:** Only packets bot received

### Hybrid Mode
- **Slower:** TCP query + merge takes ~15 seconds
- **Complete:** Full neighbor data
- **Risk:** May conflict with bot

## Statistics Interpretation

### Database-Only Output
```json
{
  "source": "meshbot_database",
  "statistics": {
    "nodes_with_neighbors": 42,
    "total_neighbor_entries": 156,
    "average_neighbors": 3.7
  }
}
```

### Hybrid Output
```json
{
  "source": "hybrid_db+tcp",
  "statistics": {
    "nodes_with_neighbors": 500,
    "total_neighbor_entries": 2145,
    "average_neighbors": 4.3,
    "tcp_nodes": 495,
    "db_only_nodes": 5
  }
}
```

**Interpretation:**
- `tcp_nodes`: Nodes from TCP query (complete data)
- `db_only_nodes`: Unique nodes only in database (recent broadcasts)
- Total = tcp_nodes + db_only_nodes

## See Also

- `README_NEIGHBORS.md` - Original database-based neighbor collection
- `export_neighbors_from_db.py` - Export script with hybrid mode
- `infoup_db.sh` - Map update script with mode configuration
- Issue #97 - Map visualization improvements
- PR #93 - Database-based neighbor collection implementation

## Support

For questions or issues:
1. Check this guide for recommended mode
2. Review logs: `cat export.log | grep -E "(✅|⚠️|❌)"`
3. Test connectivity: `./export_neighbors_from_db.py --tcp-query <host> 2>&1 | head -20`
4. Check neighbor data in database: `sqlite3 traffic_history.db "SELECT COUNT(*) FROM neighbors;"`

---

**Implementation Date:** 2025-12-03  
**Status:** ✅ Complete and Ready for Deployment  
**Issue:** Neighbor data reduction (500 → 42 nodes) - #97 comment  
**Solution:** Hybrid mode with configurable TCP query option
