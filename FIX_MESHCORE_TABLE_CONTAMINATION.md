# Fix: MeshCore Messages in Meshtastic Table (Data Contamination)

## Problem Description

**Issue Reported:**
MeshCore messages were being saved to the Meshtastic `public_messages` table, causing database contamination where the two protocols' data was mixed together.

**Impact:**
- MeshCore messages appeared in Meshtastic views (fixed separately in browse_traffic_db.py)
- Database integrity compromised with mixed protocol data
- Incorrect source attribution for MeshCore messages

## Root Cause Analysis

### Issue 1: Hardcoded Source Parameter in main_bot.py

In `main_bot.py`, when calling `add_public_message()`, the code hardcoded `source='local'`:

```python
# Line 983 (WRONG)
self.traffic_monitor.add_public_message(packet, message, source='local')

# Line 1013 (WRONG)  
self.traffic_monitor.add_public_message(packet, message, source='local')
```

**The Problem:**
- Earlier in the code, `source` variable was correctly determined based on network type
- For MeshCore packets: `source = 'meshcore'`
- For Meshtastic packets: `source = 'local'`, 'tcp', or 'tigrog2'
- But when calling `add_public_message()`, the hardcoded 'local' overwrote the actual source
- Result: MeshCore messages were mislabeled as 'local' and saved to `public_messages` table

### Issue 2: No Guard in add_public_message()

The `add_public_message()` method in `traffic_monitor.py` had no protection against MeshCore messages:

```python
def add_public_message(self, packet, message_text, source='local'):
    # No check for source == 'meshcore'
    # Saved everything to public_messages regardless of protocol
    self.persistence.save_public_message(message_entry)
```

**The Problem:**
- Method was designed for Meshtastic messages only
- No validation of source parameter
- MeshCore messages should go to `meshcore_packets` table (handled elsewhere)
- Should NOT go to `public_messages` table

## Solution Implemented

### Fix 1: Use Actual Source in main_bot.py

**Changed two calls to use the actual `source` variable:**

```python
# Line 983 (FIXED)
self.traffic_monitor.add_public_message(packet, message, source=source)

# Line 1013 (FIXED)
self.traffic_monitor.add_public_message(packet, message, source=source)
```

**Benefits:**
- Correct source attribution for all messages
- MeshCore messages now passed with source='meshcore'
- Meshtastic messages keep their correct source ('local', 'tcp', 'tigrog2')

### Fix 2: Added Guard in traffic_monitor.py

**Added validation at the start of `add_public_message()`:**

```python
def add_public_message(self, packet, message_text, source='local'):
    """
    Enregistrer un message public avec collecte de statistiques avancées
    
    NOTE: Cette méthode est pour les messages Meshtastic UNIQUEMENT.
    Les messages MeshCore sont gérés séparément via meshcore_packets.

    Args:
        packet: Packet Meshtastic
        message_text: Texte du message
        source: 'local' (Serial), 'tcp' (TCP), 'tigrog2' (legacy), ou 'meshtastic'
               NOTE: 'meshcore' n'est PAS accepté ici
    """
    try:
        # GUARD: Ne pas sauvegarder les messages MeshCore dans public_messages
        # Les messages MeshCore vont dans meshcore_packets (gérés ailleurs)
        if source == 'meshcore':
            debug_print_mc(f"⚠️  Message MeshCore ignoré dans add_public_message (va dans meshcore_packets)")
            return
        
        # ... rest of method (saves to public_messages)
```

**Benefits:**
- Explicit protocol separation at data layer
- MeshCore messages blocked from wrong table
- Clear documentation of intent
- Debug message for monitoring

## Data Flow (Before vs After)

### BEFORE (Broken)

```
MeshCore Packet → source determined as 'meshcore'
                → add_public_message(..., source='local') ← HARDCODED!
                → Saved to public_messages with source='local' ❌
                → MeshCore data in Meshtastic table ❌
```

### AFTER (Fixed)

```
MeshCore Packet → source determined as 'meshcore'
                → add_public_message(..., source='meshcore') ← CORRECT!
                → Guard detects source='meshcore' ✓
                → Return early (not saved) ✓
                → Only saved to meshcore_packets (elsewhere) ✓
                → Clean table separation ✓
```

## Testing

### Code Verification

```bash
# Check for fixed calls in main_bot.py
✅ Fixed calls (source=source): 2
❌ Old calls (source='local'): 0

# Check for guard in traffic_monitor.py
✅ Guard code found: if source == 'meshcore': return
```

### Expected Behavior

**Meshtastic Messages:**
- Source: 'local', 'tcp', 'tigrog2', or 'meshtastic'
- Action: Saved to `public_messages` table ✓
- View: Appear in Meshtastic messages view ✓

**MeshCore Messages:**
- Source: 'meshcore'
- Action: Blocked from `public_messages` table ✓
- Action: Only saved to `meshcore_packets` table ✓
- View: Appear only in MeshCore messages view ✓

## Impact Analysis

### Database Changes

**public_messages table:**
- BEFORE: Contains both Meshtastic AND MeshCore messages
- AFTER: Contains only Meshtastic messages ✓

**meshcore_packets table:**
- BEFORE: Contains MeshCore packets (correct)
- AFTER: Still contains MeshCore packets (unchanged) ✓

### Application Behavior

**Meshtastic View:**
- BEFORE: Shows mixed protocol messages (with filtering workaround)
- AFTER: Shows only Meshtastic messages (clean data at source) ✓

**MeshCore View:**
- BEFORE: Works correctly (reads from meshcore_packets)
- AFTER: Still works correctly (unchanged) ✓

## Related Fixes

This fix complements the earlier fix in `browse_traffic_db.py`:

1. **browse_traffic_db.py fix (Previous):**
   - Added SQL filter: `WHERE (source IS NULL OR source != 'meshcore')`
   - Hides MeshCore messages in view layer
   - UI workaround for data contamination

2. **This fix (Current):**
   - Prevents MeshCore messages from entering `public_messages` table
   - Fixes root cause at data layer
   - Clean separation at source

**Together:** Complete solution with defense-in-depth:
- Data layer: MeshCore messages blocked at source
- View layer: Filter as additional safeguard

## Files Modified

**main_bot.py:**
- Line 983: Changed `source='local'` to `source=source`
- Line 1013: Changed `source='local'` to `source=source`

**traffic_monitor.py:**
- Added guard in `add_public_message()` to block source='meshcore'
- Enhanced documentation
- Added debug message for monitoring

## Migration Notes

### For Existing Data

If your database already has MeshCore messages in `public_messages`:

1. **Option A: Clean via browse UI**
   - The browse_traffic_db.py filter hides them from view
   - They won't affect new data

2. **Option B: Manual cleanup (optional)**
   ```sql
   -- Count contaminated messages
   SELECT COUNT(*) FROM public_messages WHERE source = 'meshcore';
   
   -- Remove contaminated messages (optional)
   DELETE FROM public_messages WHERE source = 'meshcore';
   ```

3. **Going Forward:**
   - New MeshCore messages will NOT enter public_messages
   - Database will stay clean automatically

## Verification Checklist

- [x] Fixed hardcoded source='local' in main_bot.py (2 occurrences)
- [x] Added guard in add_public_message() to block meshcore
- [x] Syntax validation passed
- [x] Code review completed
- [x] Expected behavior documented
- [x] Migration notes provided

## Conclusion

This fix ensures clean protocol separation at the database level:
- **MeshCore messages** → Only in `meshcore_packets` table
- **Meshtastic messages** → Only in `public_messages` table
- **No contamination** between protocol tables

Combined with the browse_traffic_db.py filter, this provides complete protection against protocol mixing at both data and view layers.

**Status:** ✅ **FIXED** - MeshCore messages will no longer contaminate the Meshtastic table
