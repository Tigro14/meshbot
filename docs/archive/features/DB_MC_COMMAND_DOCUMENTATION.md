# `/db mc` Command Documentation

## Overview

The `/db mc` command displays the complete `meshcore_contacts` SQLite table with all stored attributes. This is an admin/diagnostic command that provides full visibility into the MeshCore contact database.

## Command Syntax

```
/db mc
/db meshcore
```

Both forms are equivalent. The command accepts no arguments and displays ALL contacts in the database.

## Purpose

**Admin/Diagnostic Tool** for:
- Database inspection and verification
- Data completeness checking
- Troubleshooting MeshCore data collection
- Understanding what's actually stored in SQLite

## Output Formats

### Mesh Channel (Compact)

Limited to ~160 characters, shows only statistics:

```
📡 MeshCore: 22
GPS:15 Keys:18
26/01 14:20-27/01 15:12
Use Telegram for full details
```

**Information displayed:**
- Total contacts count
- Contacts with GPS data
- Contacts with public keys
- Time range (oldest to newest)
- Redirect to Telegram for details

### Telegram Channel (Detailed)

Full table dump with all attributes for each contact:

```
📡 **TABLE MESHCORE CONTACTS**
==================================================

**Statistiques globales:**
• Total contacts: 22
• Avec GPS: 15
• Avec clé publique: 18

**Plage temporelle:**
• Plus ancien: 26/01 14:20
• Plus récent: 27/01 15:12
• Durée: 24.9 heures

**Contacts (détails complets):**
==================================================

**Tigro T1000E** (5m)
├─ Node ID: `143bcd7f`
├─ Short: T1000E
├─ Model: TBEAM
├─ GPS: 47.123456, 6.789012
│  └─ Alt: 450m
├─ PubKey: `a1b2c3d4...e5f6a7b8` (32 bytes)
├─ Source: meshcore
└─ Mise à jour: 2026-01-27 15:07:00

**Étienne T-Deck** (1j)
├─ Node ID: `a3fe27d3`
├─ Short: T-Deck
├─ Model: T-DECK
├─ GPS: 47.234567, 6.890123
│  └─ Alt: 520m
├─ PubKey: `b2c3d4e5...f6a7b8c9` (32 bytes)
├─ Source: meshcore
└─ Mise à jour: 2026-01-26 15:07:00

[... all 22 contacts ...]
```

## Attributes Displayed

### Node ID
- **Format**: Hexadecimal string (e.g., `143bcd7f`)
- **Source**: Primary key from SQLite table
- **Purpose**: Unique identifier for the node

### Name
- **Format**: Full node name (up to 40 characters)
- **Source**: NODEINFO packet or meshcore-cli
- **Purpose**: Human-readable node identifier

### Short Name
- **Format**: Abbreviated name (up to 4 characters)
- **Source**: NODEINFO packet
- **Purpose**: Compact node identifier

### Hardware Model
- **Format**: Model name (e.g., TBEAM, T-DECK, HELTEC_V3)
- **Source**: NODEINFO packet
- **Purpose**: Identify node hardware type

### GPS Coordinates
- **Format**: Latitude, Longitude (6 decimal precision)
- **Precision**: ~10cm accuracy
- **Display**: 
  - Present: `GPS: 47.123456, 6.789012`
  - Absent: `GPS: Non disponible`

### Altitude
- **Format**: Meters above sea level
- **Display**: Sub-item under GPS (if available)
  - Present: `└─ Alt: 450m`
  - Only shown if GPS coordinates exist

### Public Key
- **Format**: Hexadecimal string (typically 64 chars = 32 bytes)
- **Display**: Truncated to first 8 + last 8 hex chars
  - Present: `` `a1b2c3d4...e5f6a7b8` (32 bytes) ``
  - Absent: `Non disponible`
- **Purpose**: Node's cryptographic public key
- **Reason for truncation**: Prevents message overflow while showing enough to identify key

### Source
- **Format**: String indicating data source
- **Values**:
  - `meshcore` - From NODEINFO packets (companion mode)
  - `mqtt` - From MQTT neighbor collector
  - `meshcore-cli` - From manual meshcore-cli import
- **Purpose**: Track where data originated

### Last Updated
- **Format**: 
  - Elapsed time: `(5m)`, `(2h)`, `(1j)`
  - Full timestamp: `2026-01-27 15:07:00`
- **Purpose**: Know how recent the data is

## Empty Table Handling

If no contacts are stored:

### Mesh
```
📡 Aucun contact MeshCore
```

### Telegram
```
📡 **AUCUN CONTACT MESHCORE**

La table meshcore_contacts est vide. Les contacts MeshCore sont stockés:
• Depuis les paquets NODEINFO reçus (mode companion)
• Depuis meshcore-cli (si utilisé)

Vérifiez que:
• Le bot reçoit bien les paquets NODEINFO
• Les nœuds mesh envoient leurs informations
• Le mode companion MeshCore est actif
```

## Database Schema

The command queries this SQLite table:

```sql
CREATE TABLE meshcore_contacts (
    node_id TEXT PRIMARY KEY,      -- Unique node identifier
    name TEXT,                      -- Full node name
    shortName TEXT,                 -- Short name
    hwModel TEXT,                   -- Hardware model
    publicKey BLOB,                 -- Public key (binary)
    lat REAL,                       -- Latitude
    lon REAL,                       -- Longitude
    alt INTEGER,                    -- Altitude
    last_updated REAL,              -- Timestamp
    source TEXT DEFAULT 'meshcore'  -- Data source
);

CREATE INDEX idx_meshcore_contacts_last_updated 
ON meshcore_contacts(last_updated);
```

## Comparison: `/nodesmc` vs `/db mc`

| Feature | `/nodesmc` | `/db mc` |
|---------|------------|----------|
| **Purpose** | User-facing list | Admin diagnostic |
| **Output** | Contact list | Full DB table |
| **Time filter** | 30d or ALL | ALL (no filter) |
| **Pagination** | Yes (7/page) | No |
| **Message split** | Yes (160 char) | No (Telegram) |
| **Shows GPS** | No | Yes (full coords) |
| **Shows pubkey** | No | Yes (truncated) |
| **Shows hwModel** | No | Yes |
| **Shows source** | No | Yes |
| **Shows timestamp** | Elapsed only | Full datetime |
| **Use case** | Quick check | Full inspection |

### When to use `/nodesmc`:
- Quick contact list
- Check if node is known
- User-facing queries
- Paginated browsing

### When to use `/db mc`:
- Verify database contents
- Check data completeness
- Debug collection issues
- Inspect all attributes
- Admin/diagnostic needs

## Use Cases

### 1. Database Verification
**Problem**: Wondering if contacts are being saved correctly

**Solution**:
```
/db mc
```

**Result**: See exactly what's in the database, including all attributes

### 2. GPS Data Validation
**Problem**: Not sure which nodes have GPS coordinates

**Solution**:
```
/db mc
```

**Result**: Statistics show "Avec GPS: 15" and individual entries show GPS presence

### 3. Public Key Inspection
**Problem**: Need to verify which nodes have public keys

**Solution**:
```
/db mc
```

**Result**: Statistics show "Avec clé publique: 18" and individual entries show key status

### 4. Troubleshooting `/nodesmc`
**Problem**: `/nodesmc` shows only 2 contacts when expecting more

**Solution**:
```
/db mc
```

**Result**: See all 22 contacts in database, realize `/nodesmc` was filtering by time

### 5. Data Source Tracking
**Problem**: Need to know where contact data came from

**Solution**:
```
/db mc
```

**Result**: Each entry shows source (meshcore, mqtt, meshcore-cli)

### 6. Staleness Detection
**Problem**: Want to know which contacts haven't updated recently

**Solution**:
```
/db mc
```

**Result**: Timestamps show when each contact was last updated

## Integration with Other Commands

### `/db` Family
- `/db stats` - Database size and counts
- `/db info` - Table structure
- `/db nb` - Neighbor statistics
- **`/db mc` - MeshCore contacts table** ← NEW
- `/db clean` - Cleanup old data
- `/db vacuum` - Optimize database

### `/nodesmc` Family
- `/nodesmc` - Page 1 (30 days filter)
- `/nodesmc 2` - Page 2
- **`/nodesmc full` - All contacts (no time filter)**
- `/db mc` - Full table with all attributes

### Workflow Example

```
# 1. Quick check: How many contacts?
/nodesmc

# 2. Full list: Show all contacts
/nodesmc full

# 3. Detailed inspection: Check database
/db mc

# 4. Verify: Why are some missing GPS?
[Look at /db mc output - shows GPS: Non disponible]
```

## Technical Details

### Implementation
- **Handler**: `handlers/command_handlers/db_commands.py`
- **Method**: `_get_meshcore_table(channel)`
- **Telegram**: `telegram_bot/commands/db_commands.py`

### Query
```python
cursor.execute("""
    SELECT node_id, name, shortName, hwModel, publicKey, 
           lat, lon, alt, last_updated, source
    FROM meshcore_contacts
    ORDER BY last_updated DESC
""")
```

### Output Limits
- **Mesh**: ~160 characters (compact stats only)
- **Telegram**: Up to 4096 characters per message (chunked if needed)

### Performance
- **Index**: Uses `idx_meshcore_contacts_last_updated`
- **Order**: Newest first (ORDER BY last_updated DESC)
- **No pagination**: Shows ALL contacts (admin use case)

## Troubleshooting

### Issue: Table doesn't exist
**Symptom**: `❌ Table meshcore_contacts inexistante`

**Cause**: SQLite database not initialized or corrupted

**Solution**:
1. Check bot logs for initialization errors
2. Verify `traffic_history.db` exists
3. Check file permissions

### Issue: Table is empty
**Symptom**: `📡 Aucun contact MeshCore`

**Cause**: No NODEINFO packets received yet

**Solution**:
1. Verify MeshCore companion mode is active
2. Check if nodes are sending NODEINFO packets
3. Monitor bot logs for packet reception
4. Test with `/nodesmc` to see if any data exists

### Issue: Missing attributes
**Symptom**: Many contacts show "Non disponible" for GPS or keys

**Cause**: Nodes haven't sent complete NODEINFO packets

**Solution**:
1. Normal - not all nodes broadcast GPS
2. Not all nodes have public keys yet
3. Data will populate as nodes send updates
4. Check node configuration (GPS enabled, key generation)

### Issue: Output too long for Telegram
**Symptom**: Message truncated or split weirdly

**Cause**: Too many contacts (> 4096 chars per message)

**Solution**:
- Already handled! The Telegram command handler automatically chunks messages:
```python
if len(response) > 4000:
    chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
    for chunk in chunks:
        await update.message.reply_text(chunk)
```

## Examples

### Example 1: Small Network (2 contacts)

```
/db mc

📡 **TABLE MESHCORE CONTACTS**
==================================================

**Statistiques globales:**
• Total contacts: 2
• Avec GPS: 1
• Avec clé publique: 1

**Plage temporelle:**
• Plus ancien: 26/01 14:20
• Plus récent: 27/01 15:12
• Durée: 0.9 heures

**Contacts (détails complets):**
==================================================

**Tigro T1000E** (5m)
├─ Node ID: `143bcd7f`
├─ Short: T1000E
├─ Model: TBEAM
├─ GPS: 47.123456, 6.789012
│  └─ Alt: 450m
├─ PubKey: `a1b2c3d4...e5f6a7b8` (32 bytes)
├─ Source: meshcore
└─ Mise à jour: 2026-01-27 15:07:00

**Étienne T-Deck** (1j)
├─ Node ID: `a3fe27d3`
├─ Short: T-Deck
├─ Model: T-DECK
├─ GPS: Non disponible
├─ PubKey: Non disponible
├─ Source: meshcore
└─ Mise à jour: 2026-01-26 15:07:00
```

### Example 2: Large Network (22 contacts)

```
/db mc

[Global statistics: 22 total, 15 with GPS, 18 with keys]
[22 detailed contact entries...]
[Message automatically chunked if > 4000 chars]
```

### Example 3: Empty Database

```
/db mc

📡 **AUCUN CONTACT MESHCORE**

[Helpful troubleshooting message]
```

## Best Practices

### For Users
1. Use `/nodesmc` for quick checks
2. Use `/nodesmc full` for complete lists
3. Use `/db mc` for debugging and diagnostics
4. Check Telegram for full `/db mc` output

### For Admins
1. Run `/db mc` periodically to verify data collection
2. Compare with `meshcore-cli contacts` to identify missing data
3. Monitor "Avec GPS" and "Avec clé publique" counts
4. Track data staleness via last_updated timestamps
5. Use source field to debug collection issues

### For Developers
1. `/db mc` shows raw database contents
2. Useful for verifying NODEINFO packet parsing
3. Check publicKey format (should be 32 bytes)
4. Verify GPS precision (6 decimals)
5. Confirm source attribution is correct

## Security Considerations

### Public Key Truncation
- Full keys are **32 bytes (64 hex chars)**
- Displayed as `first8...last8` to prevent overflow
- Still enough to identify key uniquely
- Full key stored in database (not exposed)

### GPS Precision
- 6 decimal places = ~10cm accuracy
- Adequate for node location
- Not excessive precision (privacy)

### Access Control
- Available to **all authorized users**
- No special permissions required
- Consider restricting in production if needed

## Future Enhancements

Potential improvements (not yet implemented):

1. **Filtering**: `/db mc <filter>` (by GPS, by key, by source)
2. **Sorting**: `/db mc sort <field>` (by name, by time, by distance)
3. **Export**: `/db mc export` (JSON or CSV format)
4. **Pagination**: `/db mc page <n>` (for very large networks)
5. **Search**: `/db mc find <term>` (search by name or ID)

## Related Commands

- `/nodesmc` - User-facing contact list
- `/nodesmc full` - All contacts (no time filter)
- `/nodes` - Meshtastic nodes (different table)
- `/db nb` - Neighbor statistics
- `/db stats` - Database statistics
- `/db info` - Table structure

## Conclusion

The `/db mc` command is a powerful admin/diagnostic tool for inspecting the complete MeshCore contacts database. It provides full visibility into stored data, making it invaluable for troubleshooting, verification, and understanding what's actually in the SQLite database.

Use it alongside `/nodesmc` for a complete picture:
- `/nodesmc` for quick, user-friendly contact lists
- `/db mc` for detailed, admin-level database inspection
