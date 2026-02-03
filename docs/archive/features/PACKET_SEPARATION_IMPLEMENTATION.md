# MeshCore and Meshtastic Packet Separation - Implementation Summary

## Overview

This document describes the implementation of separate database tables for MeshCore and Meshtastic packets, fulfilling the requirement: **"We do not want to mix Meshcore and Meshtastic packets in the same tables"**.

## Problem Statement

Previously, all packets (both Meshtastic and MeshCore) were stored in a single `packets` table, differentiated only by the `source` field. This mixing made it difficult to:
- Query packets by source separately
- Maintain clear separation between MeshCore and Meshtastic data
- Ensure statistics were calculated independently

## Solution

### Separate Tables

**Two independent tables with identical schemas:**

1. **`packets` table** - Meshtastic packets ONLY
   - Source: 'local' (serial interface)
   - Source: 'tcp' (TCP interface)
   - Source: 'tigrog2' (legacy dual-node)

2. **`meshcore_packets` table** - MeshCore packets ONLY
   - Source: 'meshcore' (MeshCore companion mode)

### Schema

Both tables share the same structure for consistency:

```sql
CREATE TABLE [packets|meshcore_packets] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    from_id TEXT NOT NULL,
    to_id TEXT,
    source TEXT,
    sender_name TEXT,
    packet_type TEXT NOT NULL,
    message TEXT,
    rssi INTEGER,
    snr REAL,
    hops INTEGER,
    size INTEGER,
    is_broadcast INTEGER,
    is_encrypted INTEGER DEFAULT 0,
    telemetry TEXT,
    position TEXT,
    hop_limit INTEGER,
    hop_start INTEGER,
    channel INTEGER DEFAULT 0,
    via_mqtt INTEGER DEFAULT 0,
    want_ack INTEGER DEFAULT 0,
    want_response INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    family TEXT,
    public_key TEXT
);
```

## Implementation Details

### 1. traffic_persistence.py

#### New Table Creation

Added `meshcore_packets` table in `_init_database()` method:
- Identical schema to `packets` table
- Source defaults to 'meshcore'
- Three indexes for performance (timestamp, from_id, packet_type)

#### New Save Method

```python
def save_meshcore_packet(self, packet: Dict[str, Any]):
    """
    Sauvegarde un paquet MeshCore dans la table meshcore_packets.
    Force source='meshcore' pour la cohérence.
    """
    # Save to meshcore_packets table only
    # Force source to 'meshcore'
```

#### Automatic Migration

On first run with new code:
1. Checks for meshcore packets in `packets` table
2. Copies them to `meshcore_packets` table
3. Deletes them from `packets` table
4. Logs migration progress

```python
# Migration logic in _init_database()
cursor.execute("SELECT COUNT(*) FROM packets WHERE source = 'meshcore'")
meshcore_count = cursor.fetchone()[0]

if meshcore_count > 0:
    # Copy to meshcore_packets
    cursor.execute('''INSERT INTO meshcore_packets (...) 
                      SELECT ... FROM packets WHERE source = 'meshcore' ''')
    
    # Delete from packets
    cursor.execute("DELETE FROM packets WHERE source = 'meshcore'")
```

### 2. traffic_monitor.py

#### Routing Logic

Updated `add_packet()` method to route packets based on source:

```python
# In add_packet() after creating packet_entry:
packet_source = packet_entry.get('source', 'unknown')

if packet_source == 'meshcore':
    # MeshCore → meshcore_packets table
    self.persistence.save_meshcore_packet(packet_entry)
    logger.debug(f"📦 Paquet MeshCore sauvegardé: {packet_type} de {sender_name}")
else:
    # Meshtastic (local, tcp, tigrog2) → packets table
    self.persistence.save_packet(packet_entry)
    logger.debug(f"📡 Paquet Meshtastic sauvegardé: {packet_type} de {sender_name}")
```

### 3. Test Suite (test_packet_separation.py)

#### Test 1: Separate Tables

Tests that new packets go to correct tables:
- Creates Meshtastic packet (source='local')
- Creates MeshCore packet (source='meshcore')
- Verifies Meshtastic → `packets` table
- Verifies MeshCore → `meshcore_packets` table
- Confirms no mixing

#### Test 2: Migration

Tests automatic migration of existing data:
- Creates old-style database with mixed packets
- Initializes TrafficPersistence (triggers migration)
- Verifies meshcore packets moved to meshcore_packets
- Verifies meshtastic packets remain in packets
- Confirms no data loss

**Result:** ✅ Both tests pass

## Migration Process

### Before Migration

```
packets table (MIXED):
+----+------------+-----------+----------+----------+----------+
| id | from_id    | source    | message  | type     | ...      |
+----+------------+-----------+----------+----------+----------+
| 1  | 305419896  | local     | Mesh 1   | TEXT_... | ...      |
| 2  | 2271560481 | meshcore  | Core 1   | TEXT_... | ...      | ❌
| 3  | 305419897  | tcp       | Mesh 2   | TEXT_... | ...      |
| 4  | 2271560482 | meshcore  | Core 2   | TEXT_... | ...      | ❌
+----+------------+-----------+----------+----------+----------+
```

### After Migration

```
packets table (MESHTASTIC ONLY):
+----+------------+-----------+----------+----------+----------+
| id | from_id    | source    | message  | type     | ...      |
+----+------------+-----------+----------+----------+----------+
| 1  | 305419896  | local     | Mesh 1   | TEXT_... | ...      | ✅
| 3  | 305419897  | tcp       | Mesh 2   | TEXT_... | ...      | ✅
+----+------------+-----------+----------+----------+----------+

meshcore_packets table (MESHCORE ONLY):
+----+------------+-----------+----------+----------+----------+
| id | from_id    | source    | message  | type     | ...      |
+----+------------+-----------+----------+----------+----------+
| 1  | 2271560481 | meshcore  | Core 1   | TEXT_... | ...      | ✅
| 2  | 2271560482 | meshcore  | Core 2   | TEXT_... | ...      | ✅
+----+------------+-----------+----------+----------+----------+
```

## Usage Examples

### Query Meshtastic Packets Only

```sql
-- Recent Meshtastic messages
SELECT 
    datetime(timestamp, 'unixepoch') as time,
    sender_name, message
FROM packets
WHERE packet_type = 'TEXT_MESSAGE_APP'
ORDER BY timestamp DESC
LIMIT 10;
```

### Query MeshCore Packets Only

```sql
-- Recent MeshCore messages
SELECT 
    datetime(timestamp, 'unixepoch') as time,
    sender_name, message
FROM meshcore_packets
WHERE packet_type = 'TEXT_MESSAGE_APP'
ORDER BY timestamp DESC
LIMIT 10;
```

### Query Both (if needed)

```sql
-- All messages from both sources
SELECT 'Meshtastic' as origin, timestamp, sender_name, message
FROM packets
WHERE packet_type = 'TEXT_MESSAGE_APP'
UNION ALL
SELECT 'MeshCore' as origin, timestamp, sender_name, message
FROM meshcore_packets
WHERE packet_type = 'TEXT_MESSAGE_APP'
ORDER BY timestamp DESC
LIMIT 20;
```

### Statistics by Source

```sql
-- Packet count by source
SELECT 'Meshtastic' as source, COUNT(*) as count FROM packets
UNION ALL
SELECT 'MeshCore' as source, COUNT(*) as count FROM meshcore_packets;

-- Message types by source
SELECT 'Meshtastic' as source, packet_type, COUNT(*) as count
FROM packets
GROUP BY packet_type
UNION ALL
SELECT 'MeshCore' as source, packet_type, COUNT(*) as count
FROM meshcore_packets
GROUP BY packet_type
ORDER BY source, count DESC;
```

## Benefits

### 1. Clean Separation
- No mixing between MeshCore and Meshtastic data
- Clear semantic distinction
- Independent management

### 2. Performance
- Smaller table sizes (each table only contains relevant data)
- Faster queries (no need to filter by source)
- Independent indexes

### 3. Maintainability
- Easier to understand which data comes from which source
- Simpler queries (no source filtering needed)
- Clear separation of concerns

### 4. Statistics
- Can calculate independent statistics for each source
- No confusion about which data to include
- Better analytics

### 5. Backward Compatibility
- Automatic migration (no manual intervention)
- No data loss
- Legacy queries on `packets` table still work (now returns only Meshtastic)

## Migration Safety

### No Data Loss
- All packets are copied before deletion
- Transaction-based (atomic operation)
- Logged at every step

### Idempotent
- Can be run multiple times safely
- Only migrates if meshcore packets exist in packets table
- Skips if already migrated

### Error Handling
- Migration wrapped in try/except
- Failures don't block bot startup
- Errors logged for debugging

## Testing

### Test Results

```
======================================================================
✅ ALL TESTS PASSED!
======================================================================

✨ Verification complete:
  • MeshCore and Meshtastic packets separated
  • New packets go to correct tables
  • Migration of existing data works
  • No mixing between tables
```

### Test Coverage

1. ✅ New Meshtastic packet → packets table
2. ✅ New MeshCore packet → meshcore_packets table
3. ✅ No MeshCore in packets table
4. ✅ No Meshtastic in meshcore_packets table
5. ✅ Migration moves old meshcore packets
6. ✅ Migration preserves meshtastic packets
7. ✅ Message content verified in both tables

## Files Modified

1. **traffic_persistence.py**
   - Added `meshcore_packets` table schema (+40 lines)
   - Added `save_meshcore_packet()` method (+70 lines)
   - Added migration logic in `_init_database()` (+50 lines)

2. **traffic_monitor.py**
   - Updated packet routing in `add_packet()` (+12 lines)
   - Added debug logging for separation

3. **test_packet_separation.py** (NEW)
   - Comprehensive test suite (420 lines)
   - Tests separation and migration
   - All tests pass

## Future Considerations

### Independent Statistics
With separated tables, we can now:
- Calculate Meshtastic-only statistics
- Calculate MeshCore-only statistics
- Compare traffic patterns between sources
- Identify which source is more active

### Separate Cleanup
Different retention policies could be applied:
```python
# Clean old Meshtastic packets (48h)
DELETE FROM packets WHERE timestamp < ?

# Clean old MeshCore packets (24h - different policy)
DELETE FROM meshcore_packets WHERE timestamp < ?
```

### Source-Specific Analysis
Easier to analyze each source independently:
- Meshtastic: Radio network analysis
- MeshCore: Companion mode usage patterns

## Conclusion

The separation of MeshCore and Meshtastic packets into dedicated tables provides:
- ✅ Clean data separation (requirement fulfilled)
- ✅ Better performance
- ✅ Easier maintenance
- ✅ Independent statistics
- ✅ Automatic migration
- ✅ No data loss
- ✅ Backward compatibility

All requirements met and thoroughly tested.

## References

- Issue requirement: "We do not want to mix Meshcore and Meshtastic packets in the same tables"
- Implementation: traffic_persistence.py, traffic_monitor.py
- Tests: test_packet_separation.py (2 tests, all passing)
- Original packet metadata implementation: PACKET_METADATA_IMPLEMENTATION.md

## Author

Implementation completed by GitHub Copilot on 2026-01-28 in response to user requirement.
