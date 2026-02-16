# Fix: MeshCore Messages in Meshtastic View

## Problem Description

**Issue Reported:**
The Meshtastic messages view was displaying MeshCore messages with incorrect source IDs showing as "Node-ffffffff". This caused confusion as MeshCore traffic appeared mixed with Meshtastic traffic.

**Example of the problem:**
```
02-16 20:10:45 Node-ffffffff 🐈Gaius: rien              ❌ MESHCORE!
02-16 20:10:05 Ted mobile Bizarre ça.
02-16 20:09:23 Gros bec v4 👋
...
02-16 19:30:42 Node-ffffffff Étienne T-Deck: Idem rien ici  ❌ MESHCORE!
02-16 19:28:38 oni Tonio MC Companion: Non rien ici
02-16 19:22:13 Node-ffffffff glu 📟: Coupure            ❌ MESHCORE!
```

## Root Cause Analysis

### Database Structure
The `public_messages` table contains messages from both protocols:
- **Meshtastic messages**: source = 'local', 'tcp', 'tigrog2', or NULL
- **MeshCore messages**: source = 'meshcore'

```sql
CREATE TABLE public_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    from_id TEXT NOT NULL,
    sender_name TEXT,
    message TEXT,
    rssi INTEGER,
    snr REAL,
    message_length INTEGER,
    source TEXT  -- ← This field distinguishes the protocols
)
```

### The Bug
The `load_messages()` method in `browse_traffic_db.py` was loading **all messages** without filtering by source:

```python
# OLD CODE (buggy)
def load_messages(self):
    cursor = self.conn.cursor()
    query = 'SELECT * FROM public_messages'  # ← No filtering!
    params = []
    
    if self.search_term:
        query += ' WHERE message LIKE ?'
        params.append(f'%{self.search_term}%')
    
    order = 'DESC' if self.sort_order == 'desc' else 'ASC'
    query += f' ORDER BY timestamp {order} LIMIT 1000'
    
    cursor.execute(query, params)
    self.items = [dict(row) for row in cursor.fetchall()]
```

This meant:
1. Meshtastic mode showed both Meshtastic AND MeshCore messages
2. MeshCore messages appeared with "Node-ffffffff" as sender_name
3. Users saw mixed protocol traffic in a single view

## Solution

### Implementation
Added source filtering to `load_messages()` to exclude MeshCore messages when in Meshtastic mode:

```python
# NEW CODE (fixed)
def load_messages(self):
    """Charge les messages publics depuis la DB (Meshtastic uniquement)"""
    cursor = self.conn.cursor()

    query = 'SELECT * FROM public_messages'
    params = []
    conditions = []

    # Filtrer par source pour exclure les messages MeshCore en mode Meshtastic
    # En mode Meshtastic, on ne veut que les messages Meshtastic (source != 'meshcore')
    conditions.append("(source IS NULL OR source != 'meshcore')")  # ← Key fix!

    # Appliquer la recherche
    if self.search_term:
        conditions.append('message LIKE ?')
        params.append(f'%{self.search_term}%')

    # Construire la clause WHERE
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    # Appliquer l'ordre de tri
    order = 'DESC' if self.sort_order == 'desc' else 'ASC'
    query += f' ORDER BY timestamp {order} LIMIT 1000'

    cursor.execute(query, params)
    self.items = [dict(row) for row in cursor.fetchall()]
```

### Key Changes
1. **Added conditions list** to build WHERE clause properly
2. **Source filter**: `(source IS NULL OR source != 'meshcore')`
   - Includes messages with NULL source (backward compatibility)
   - Includes messages with source='local', 'tcp', 'tigrog2' (Meshtastic)
   - Excludes messages with source='meshcore' (MeshCore)
3. **Preserved search functionality** - works together with source filter

## Testing

### Test Setup
Created test database with mixed messages:
- 4 Meshtastic messages (source: 'local', 'tcp', 'tigrog2', NULL)
- 3 MeshCore messages (source: 'meshcore', sender: 'Node-ffffffff')

### Test Results

**Before Fix:**
```
Total messages in public_messages: 7
Meshtastic view loaded: 7 items (including 3 MeshCore ❌)
- Shows Node-ffffffff entries
- Mixed protocol traffic
```

**After Fix:**
```
Total messages in public_messages: 7
Meshtastic view loaded: 4 items (only Meshtastic ✅)
- No Node-ffffffff entries
- Clean Meshtastic-only view
- MeshCore messages properly filtered out
```

### SQL Query Comparison

**Before (no filtering):**
```sql
SELECT * FROM public_messages 
ORDER BY timestamp DESC 
LIMIT 1000
-- Returns: 7 messages (Meshtastic + MeshCore mixed)
```

**After (with filtering):**
```sql
SELECT * FROM public_messages 
WHERE (source IS NULL OR source != 'meshcore')
ORDER BY timestamp DESC 
LIMIT 1000
-- Returns: 4 messages (Meshtastic only)
```

## Impact Analysis

### What Changed
- **File**: `browse_traffic_db.py`
- **Method**: `load_messages()`
- **Lines**: ~10 lines modified

### What Stayed the Same
- `load_meshcore_messages()` - Unchanged (already correct)
- MeshCore mode behavior - Unchanged
- All other views - Unchanged
- Filter/search functionality - Enhanced (works with source filter)

### Backward Compatibility
✅ **Fully backward compatible**:
- Messages with NULL source are preserved (legacy data)
- Existing search/filter features work as before
- No breaking changes to database schema
- No impact on MeshCore view

## Verification Checklist

- [x] Syntax validation passed
- [x] No Python import errors
- [x] Test with sample data passed
- [x] Meshtastic messages exclude MeshCore (source='meshcore')
- [x] Meshtastic messages include NULL source (backward compatibility)
- [x] Search functionality works with source filter
- [x] MeshCore view unaffected
- [x] No regression in other views

## Expected User Experience

### Before Fix
User in Meshtastic messages view sees:
```
💬 MESSAGES (Meshtastic Mode)
- Ted mobile: Bizarre ça.        ← Meshtastic
- Node-ffffffff: 🐈Gaius: rien   ← MeshCore (wrong!)
- Gros bec v4: 👋                ← Meshtastic
- Node-ffffffff: Étienne T-Deck  ← MeshCore (wrong!)
```

### After Fix
User in Meshtastic messages view sees:
```
💬 MESSAGES (Meshtastic Mode)
- Ted mobile: Bizarre ça.        ← Meshtastic ✓
- Gros bec v4: 👋                ← Meshtastic ✓
- RR92S1P: Bonsoir              ← Meshtastic ✓
- (No Node-ffffffff entries)     ← Clean! ✓
```

User in MeshCore messages view sees:
```
💬 MC MESSAGES (MeshCore Mode)
- MCNode1: MeshCore message 1    ← MeshCore ✓
- MCNode2: MeshCore message 2    ← MeshCore ✓
- (Loaded from meshcore_packets) ← Correct source ✓
```

## Related Documentation

- **Main feature**: `BROWSE_MESHCORE_DEMO.md`
- **Implementation**: `IMPLEMENTATION_SUMMARY.md`
- **Database schema**: `traffic_persistence.py`

## Conclusion

This fix ensures clean separation between Meshtastic and MeshCore message views by properly filtering the `public_messages` table by source. The solution is minimal, backward compatible, and thoroughly tested.

**Status**: ✅ **FIXED** - Meshtastic messages view now correctly excludes MeshCore messages
