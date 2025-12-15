# PR Summary: Node Stats Retention (7 Days)

## Overview

Implements automatic retention cleanup for the `node_stats` table to prevent database bloat from inactive nodes. After PR #173 added node metrics display, stats were accumulating indefinitely. This PR adds a configurable 7-day retention policy.

## Problem Solved

**Before:**
- ✗ Node stats never cleaned up (accumulated forever)
- ✗ Stale data from inactive nodes persisted in database
- ✗ Database size grew unbounded
- ✗ Map showed metrics for nodes inactive for weeks/months

**After:**
- ✅ Node stats automatically cleaned up after 7 days (configurable)
- ✅ Only active/recent nodes have metrics
- ✅ Database size stays manageable
- ✅ Map shows relevant, current metrics

## Changes Summary

### 1. Configuration (`config.py.sample`)

Added new configuration option:

```python
NODE_STATS_RETENTION_HOURS = 168  # 7 days retention for node stats
```

**Location:** Line 104 (after `NEIGHBOR_RETENTION_HOURS`)  
**Default:** 168 hours (7 days)  
**Range:** Recommended 72-336 hours (3-14 days)

### 2. Database Cleanup (`traffic_persistence.py`)

Updated `cleanup_old_data()` method to include node_stats:

**Changes:**
- Added `node_stats_hours` parameter (default: None, auto-loads from config)
- Queries `DELETE FROM node_stats WHERE last_updated < ?`
- Logs number of deleted entries
- Fallback to 168h if config unavailable

**Code Added:** ~20 lines  
**Location:** Lines 806-844

### 3. Test Suite

**Unit Tests (`test_node_stats_retention.py`):**
- 350+ lines of comprehensive tests
- 3 test scenarios: basic retention, edge cases, config integration
- Tests nodes at ages: 1h, 6.5d, 8d, 30d
- Verifies correct retention behavior

**Integration Test (`test_node_stats_integration.py`):**
- 180+ lines of end-to-end testing
- Verifies full cleanup chain works
- Mimics actual bot behavior (periodic cleanup)
- Tests TrafficMonitor -> TrafficPersistence integration

**Test Results:**
```
============================================================
TEST SUITE SUMMARY
============================================================
  ✅ PASSED: Basic Retention
  ✅ PASSED: Edge Cases
  ✅ PASSED: Config Integration
============================================================
✅ INTEGRATION TEST PASSED
============================================================
```

### 4. Documentation

**`NODE_STATS_RETENTION_IMPLEMENTATION.md`:**
- 350+ lines of complete documentation
- Problem statement and solution design
- Implementation details with code examples
- Usage guide and troubleshooting
- Monitoring and debugging tips
- Future enhancement ideas

## Technical Architecture

### Data Flow

```
Meshtastic Packets
    ↓
TrafficMonitor.add_packet()
    ↓
node_packet_stats[node_id]  (in-memory accumulation)
    ↓
save_aggregate_stats()  (periodic)
    ↓
TrafficPersistence.save_node_stats()
    ↓
INSERT OR REPLACE INTO node_stats (last_updated = NOW)
    ↓
periodic_update_thread()  (every 5 min)
    ↓
TrafficMonitor.cleanup_old_persisted_data()
    ↓
TrafficPersistence.cleanup_old_data()
    ↓
DELETE FROM node_stats WHERE last_updated < (NOW - 168h)
```

### Database Schema

Uses existing `node_stats` table (no schema changes):

```sql
CREATE TABLE node_stats (
    node_id TEXT PRIMARY KEY,
    total_packets INTEGER,
    total_bytes INTEGER,
    packet_types TEXT,
    hourly_activity TEXT,
    message_stats TEXT,
    telemetry_stats TEXT,
    position_stats TEXT,
    routing_stats TEXT,
    last_updated REAL,  -- ← Used for retention
    ...
)
```

### Retention Logic

```python
# Calculate cutoff timestamp
cutoff = (datetime.now() - timedelta(hours=168)).timestamp()

# Delete old entries
DELETE FROM node_stats WHERE last_updated < ?
```

**Example:**
- Today: 2025-12-15 16:00:00
- Cutoff: 2025-12-08 16:00:00 (7 days ago)
- Deleted: All nodes with `last_updated` before 2025-12-08 16:00:00

## Integration with Existing Systems

### Main Bot (`main_bot.py`)

**No changes required.** Uses existing cleanup mechanism:

```python
def periodic_update_thread(self):
    # ... every 5 minutes ...
    retention_hours = globals().get('NEIGHBOR_RETENTION_HOURS', 48)
    self.traffic_monitor.cleanup_old_persisted_data(hours=retention_hours)
    # ↑ This now also cleans node_stats (uses NODE_STATS_RETENTION_HOURS)
```

### Map Export (`map/export_nodes_from_db.py`)

**No changes required.** Script is unaffected:

```python
# Loads ALL node_stats (no time filter)
node_stats_raw = persistence.load_node_stats()

# Gracefully handles missing data
if node_id_str in node_stats_data:
    node_entry["nodeStats"] = {...}  # Show metrics
else:
    # No metrics section (graceful degradation)
```

### Traffic Monitor (`traffic_monitor.py`)

**No changes required.** Uses existing persistence:

```python
def cleanup_old_persisted_data(self, hours: int = 48):
    self.persistence.cleanup_old_data(hours=hours)
    # ↑ Now includes node_stats cleanup
```

## Benefits

### 1. Database Health
- Prevents unbounded growth
- Removes stale data automatically
- Keeps database size manageable

### 2. Data Relevance
- Only recent nodes (≤7 days) have metrics
- Map shows current network state
- No confusion from old/inactive nodes

### 3. Configurability
- Easy to adjust via `config.py`
- Different deployments can use different retention
- Default (7 days) is sensible for most cases

### 4. Backward Compatibility
- No breaking changes
- Existing functionality unchanged
- Map export still works

### 5. Well Tested
- Comprehensive unit tests
- Integration test verifies full chain
- Edge cases covered

### 6. Self-Contained
- Uses existing cleanup mechanism
- No new dependencies
- No new scheduled tasks

## Deployment

### Steps to Deploy

1. **Merge PR** to main branch
2. **No config changes needed** - uses sensible default (168h)
3. **Restart bot** to load new code
4. **Monitor logs** for cleanup activity

### Post-Deployment Verification

**Check logs** (every 5 minutes):
```
INFO: Nettoyage : 150 paquets, 45 messages, 12 voisins, 3 node_stats supprimés 
      (packets/messages/neighbors > 48h, node_stats > 168h)
```

**Check database:**
```bash
sqlite3 traffic_history.db "SELECT COUNT(*) FROM node_stats"
sqlite3 traffic_history.db "SELECT MAX(last_updated) FROM node_stats"
```

**Expected behavior:**
- node_stats count stays stable (not growing unbounded)
- Most recent `last_updated` is current timestamp
- Older entries (>7 days) automatically removed

### Rollback Plan

If issues arise:

1. **Revert commit** containing this PR
2. **Restart bot** to load old code
3. **No data loss** - old node_stats entries still in database
4. **No schema changes** - database compatible

## Files Changed

| File | Purpose | Lines Added | Lines Modified |
|------|---------|-------------|----------------|
| `config.py.sample` | Add NODE_STATS_RETENTION_HOURS | +5 | 0 |
| `traffic_persistence.py` | Update cleanup_old_data() | +20 | +3 |
| `test_node_stats_retention.py` | Unit test suite | +350 | 0 |
| `test_node_stats_integration.py` | Integration test | +180 | 0 |
| `NODE_STATS_RETENTION_IMPLEMENTATION.md` | Documentation | +350 | 0 |
| `PR_SUMMARY_NODE_STATS_RETENTION.md` | This file | +250 | 0 |
| **Total** | **6 files** | **+1155 lines** | **+3 lines** |

## Testing

### Unit Tests

```bash
$ python3 test_node_stats_retention.py
✅ PASSED: Basic Retention
✅ PASSED: Edge Cases  
✅ PASSED: Config Integration
✅ ALL TESTS PASSED
```

### Integration Test

```bash
$ python3 test_node_stats_integration.py
✅ INTEGRATION TEST PASSED
```

### Manual Testing

1. Insert test data with varying ages
2. Run cleanup manually
3. Verify correct entries deleted
4. Check map export still works
5. Monitor production cleanup logs

## Monitoring

### Key Metrics

- **node_stats count**: Should stay stable (not growing)
- **Cleanup frequency**: Every 5 minutes via periodic_update_thread
- **Entries deleted**: Logged each cleanup cycle
- **Map export**: Should show metrics for active nodes only

### Alert Conditions

**Warning signs:**
- node_stats count growing unbounded → cleanup not running
- All node_stats deleted → retention period too short
- Map shows no metrics → no active nodes or retention too aggressive

**Debug commands:**
```bash
# Check node_stats age distribution
sqlite3 traffic_history.db "
  SELECT 
    ROUND((julianday('now') - julianday(last_updated, 'unixepoch')) * 24) as age_hours,
    COUNT(*) as count
  FROM node_stats 
  GROUP BY age_hours 
  ORDER BY age_hours
"

# Check cleanup logs
journalctl -u meshbot | grep "Nettoyage" | tail -10
```

## Configuration Options

### Default Configuration

```python
NODE_STATS_RETENTION_HOURS = 168  # 7 days (recommended)
```

### Alternative Configurations

```python
# Short retention (3 days) - for high-activity networks
NODE_STATS_RETENTION_HOURS = 72

# Medium retention (7 days) - default, balanced
NODE_STATS_RETENTION_HOURS = 168

# Long retention (14 days) - for low-activity networks
NODE_STATS_RETENTION_HOURS = 336

# Very long retention (30 days) - matches neighbor retention
NODE_STATS_RETENTION_HOURS = 720
```

**Recommendation:** Start with default (168h), adjust based on:
- Network activity level
- Storage constraints
- Desired historical visibility

## Future Enhancements

Possible improvements in future PRs:

1. **Historical Metrics Table**
   - Create `node_stats_history` for time-series data
   - Keep daily/hourly snapshots for trend analysis

2. **Selective Retention**
   - Longer retention for "important" nodes (routers, high-traffic)
   - Shorter retention for low-activity nodes

3. **Metrics Dashboard**
   - Web UI to visualize trends over time
   - Export to Grafana/Prometheus

4. **Retention by Type**
   - Different retention for telemetry vs traffic stats
   - Configurable per packet type

## Related PRs

- **PR #173**: Node metrics display on map.html (introduced node_stats usage)
- **This PR**: Adds retention cleanup for node_stats

## Conclusion

This PR successfully implements automatic retention cleanup for `node_stats`, ensuring the database stays healthy while keeping relevant metrics for active nodes. The 7-day default provides a good balance between data retention and storage efficiency, with full configurability for different deployment needs.

**Status:** ✅ Ready for merge  
**Breaking Changes:** None  
**Migration Required:** None  
**Testing:** Comprehensive (unit + integration)  
**Documentation:** Complete  
**Deployment:** Zero-effort (uses sensible defaults)
