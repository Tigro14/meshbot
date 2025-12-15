# Node Stats Retention Implementation

## Overview

This document describes the implementation of automatic retention cleanup for the `node_stats` table, ensuring that metrics from inactive nodes don't accumulate indefinitely in the database.

## Problem Statement

After PR #173 merged node metrics display functionality, the `node_stats` table was being populated with aggregated metrics for each node (total packets, bytes, packet types, telemetry, etc.). However, there was no cleanup mechanism, meaning:

1. **Database bloat**: Stats for nodes that disappeared from the network persisted forever
2. **Stale data**: The map would show metrics for nodes not seen in weeks/months
3. **Inconsistent retention**: Other tables had retention policies (packets: 48h, neighbors: 30d) but node_stats did not

## Solution

Implemented a configurable retention policy that automatically removes node_stats entries for nodes that haven't been updated in over 7 days (configurable).

### Key Design Decisions

1. **Retention Period**: 7 days (168 hours) - Balance between keeping useful data and preventing bloat
2. **Configurable**: `NODE_STATS_RETENTION_HOURS` in config.py allows easy adjustment
3. **Based on last_updated**: Uses existing `last_updated` timestamp column
4. **Non-breaking**: Backward compatible, no schema changes required

## Implementation Details

### 1. Configuration (`config.py.sample`)

```python
# Configuration rétention des statistiques de nœuds dans SQLite
# Durée de conservation des métriques agrégées par nœud (en heures)
# 168h = 7 jours (1 semaine) - Recommandé pour garder les métriques récentes
# Les statistiques de nœuds inactifs depuis plus de 7 jours seront supprimées
NODE_STATS_RETENTION_HOURS = 168  # 7 jours de rétention
```

**Default**: 168 hours (7 days)  
**Recommended Range**: 72-336 hours (3-14 days)

### 2. Database Cleanup (`traffic_persistence.py`)

Modified the `cleanup_old_data()` method to include node_stats cleanup:

```python
def cleanup_old_data(self, hours: int = 48, node_stats_hours: int = None):
    """
    Supprime les données plus anciennes que le nombre d'heures spécifié.

    Args:
        hours: Nombre d'heures à conserver pour packets/messages/neighbors
        node_stats_hours: Nombre d'heures à conserver pour node_stats (défaut: 168 = 7 jours)
    """
    # ... existing cleanup for packets, messages, neighbors ...
    
    # Clean up stale node_stats entries (default: 7 days retention)
    if node_stats_hours is None:
        # Try to get from config, fallback to 168 hours (7 days)
        try:
            import config
            node_stats_hours = getattr(config, 'NODE_STATS_RETENTION_HOURS', 168)
        except:
            node_stats_hours = 168
    
    node_stats_cutoff = (datetime.now() - timedelta(hours=node_stats_hours)).timestamp()
    cursor.execute('DELETE FROM node_stats WHERE last_updated < ?', (node_stats_cutoff,))
    node_stats_deleted = cursor.rowcount
```

**Key Features:**
- Separate retention period from packets/neighbors
- Auto-loads from config if available
- Fallback to 168h if config unavailable
- Logs number of deleted entries

### 3. Test Suite (`test_node_stats_retention.py`)

Comprehensive test coverage with 3 test scenarios:

#### Test 1: Basic Retention
- Tests nodes at different ages (1h, 6.5d, 8d, 30d)
- Verifies nodes within 7 days are kept
- Verifies nodes older than 7 days are deleted

#### Test 2: Edge Cases
- Empty database (no crash)
- All fresh nodes (all kept)
- All stale nodes (all deleted)

#### Test 3: Config Integration
- Verifies default 168h value is used
- Tests config fallback mechanism

**Test Results:**
```
============================================================
TEST SUITE SUMMARY
============================================================
  ✅ PASSED: Basic Retention
  ✅ PASSED: Edge Cases
  ✅ PASSED: Config Integration
============================================================
✅ ALL TESTS PASSED
```

## Usage

### Automatic Cleanup

The cleanup runs automatically via the bot's periodic cleanup cycle:

1. **main_bot.py** calls `traffic_monitor.save_aggregate_stats()` periodically
2. **Traffic persistence** saves node_stats with current timestamp
3. **Periodic cleanup** (every 5 minutes) calls `cleanup_old_data()`
4. **Stale entries** (>7 days old) are automatically deleted

### Manual Cleanup

You can also manually trigger cleanup:

```python
from traffic_persistence import TrafficPersistence

persistence = TrafficPersistence()

# Use default retention (168h for node_stats)
persistence.cleanup_old_data(hours=48)

# Use custom retention for node_stats
persistence.cleanup_old_data(hours=48, node_stats_hours=336)  # 14 days

persistence.close()
```

## Impact on Map Export

The map export script (`map/export_nodes_from_db.py`) is **not affected** by this change:

- It calls `persistence.load_node_stats()` which loads ALL node_stats (no time filter)
- Only nodes with stats will have metrics displayed
- Nodes without stats gracefully show no metrics section
- Backward compatible with existing maps

## Database Schema

No schema changes required. The existing `node_stats` table already has:

```sql
CREATE TABLE IF NOT EXISTS node_stats (
    node_id TEXT PRIMARY KEY,
    total_packets INTEGER,
    total_bytes INTEGER,
    packet_types TEXT,
    hourly_activity TEXT,
    message_stats TEXT,
    telemetry_stats TEXT,
    position_stats TEXT,
    routing_stats TEXT,
    last_updated REAL,          -- Used for retention cleanup
    last_battery_level INTEGER,
    last_battery_voltage REAL,
    last_telemetry_update REAL,
    last_temperature REAL,
    last_humidity REAL,
    last_pressure REAL,
    last_air_quality REAL
)
```

The `last_updated` column is used to determine which entries to delete.

## Benefits

1. **Prevents Database Bloat**
   - Old stats from inactive nodes are removed
   - Database size stays manageable

2. **Shows Relevant Data**
   - Map metrics only show for active/recent nodes
   - Users see current network state

3. **Configurable Retention**
   - Easy to adjust via `config.py`
   - Different deployments can use different retention periods

4. **Consistent with Other Data**
   - Aligns with retention policies for packets, neighbors, etc.
   - Unified data lifecycle management

5. **Well Tested**
   - Comprehensive test suite
   - Edge cases covered
   - Config integration verified

## Monitoring

After deployment, monitor the cleanup logs:

```
INFO: Nettoyage : 150 paquets, 45 messages, 12 voisins, 3 node_stats supprimés (packets/messages/neighbors > 48h, node_stats > 168h)
```

The log shows:
- Number of node_stats entries deleted
- Retention periods used for each data type

## Troubleshooting

### Issue: Too many node_stats being deleted

**Solution**: Increase `NODE_STATS_RETENTION_HOURS` in `config.py`:
```python
NODE_STATS_RETENTION_HOURS = 336  # 14 days instead of 7
```

### Issue: node_stats table still growing

**Possible causes:**
1. Cleanup not running - Check `periodic_cleanup()` is being called
2. Config not loaded - Verify `config.py` exists and is readable
3. Database locked - Check for concurrent access issues

**Debug:**
```python
# Check when cleanup last ran
persistence = TrafficPersistence()
cursor = persistence.conn.cursor()
cursor.execute("SELECT MAX(last_updated) FROM node_stats")
print(f"Most recent node_stats update: {cursor.fetchone()[0]}")
```

### Issue: Map shows no metrics

**Possible causes:**
1. Retention period too short - All nodes being deleted before map regeneration
2. No recent node activity - Network truly has no active nodes

**Solution**: 
- Increase retention period
- Check network activity with `/stats` command

## Related Documentation

- `CLAUDE.md` - Overall bot architecture and conventions
- `NODE_METRICS_FEATURE.md` - Original metrics display feature (PR #173)
- `IMPLEMENTATION_SUMMARY_NODE_METRICS.md` - PR #173 implementation details
- `BROWSE_TRAFFIC_DB.md` - Database browsing and inspection

## Version History

- **v1.0** (2025-12-15): Initial implementation
  - 7-day retention policy for node_stats
  - Configurable via `NODE_STATS_RETENTION_HOURS`
  - Comprehensive test suite
  - Documentation

## Future Enhancements

Possible improvements for future versions:

1. **Historical Metrics Table**
   - Create `node_stats_history` table for time-series data
   - Keep hourly/daily snapshots for trend analysis

2. **Selective Retention**
   - Keep stats longer for "important" nodes (high traffic, routers, etc.)
   - Short retention for low-activity nodes

3. **Metrics Dashboard**
   - Web UI to visualize node stats trends over time
   - Export metrics to Grafana/Prometheus

4. **Retention Policies by Type**
   - Different retention for telemetry vs traffic stats
   - Configurable per packet type

## Conclusion

The node_stats retention implementation ensures the database remains manageable while keeping relevant metrics for active nodes. The 7-day default strikes a good balance between data retention and storage efficiency, with full configurability for different use cases.
