# Database Close Fix - Summary

## Problem Statement
The `infoup_db.sh` script was failing with the following error:
```
⚠️  Erreur enrichissement SQLite (non bloquant): Cannot operate on a closed database.
Traceback (most recent call last):
  File "/home/dietpi/bot/map/export_nodes_from_db.py", line 271, in export_nodes_from_files
    cursor.execute("""
        SELECT from_id, timestamp, telemetry
        ...
    """, (history_cutoff,))
sqlite3.ProgrammingError: Cannot operate on a closed database.
```

## Root Cause
In `export_nodes_from_db.py`:
1. Line 253: `persistence.close()` was called to close the database connection
2. Lines 264-332: Code attempted to extract 7-day telemetry history
3. Line 271: `cursor.execute()` was called on the **closed** database connection

The telemetry history extraction was happening **after** the database connection was closed, causing the error.

## Solution
Move the telemetry history extraction block (lines 253-321) to execute **before** the `persistence.close()` call.

### Changes Made
**File**: `map/export_nodes_from_db.py`
- Moved telemetry history extraction (lines 253-321) before database close
- Updated line 253 comment: "Extract 7-day telemetry history for graphing (BEFORE closing database)"
- Moved `persistence.close()` call to line 324 (after all database queries complete)
- All 5 cursor operations now execute before connection close

### Code Ordering (After Fix)
```python
# Lines 91-251: All database queries (SNR, last heard, hops, neighbors, etc.)
# Lines 253-321: Telemetry history extraction (NEW LOCATION)
# Line 324: persistence.close() (MOVED HERE)
# Lines 325-333: Log statistics
```

## Testing

### Test 1: Code Structure Verification
Created `test_database_close_fix.py` that verifies:
- ✅ All 5 `cursor.execute()` calls occur before `persistence.close()`
- ✅ No cursor operations after line 324 (close line)

### Test 2: Functional Testing
Test creates a temporary database with:
- 10 telemetry packets (one per day for 10 days)
- 1 test node with GPS coordinates
- Executes the export function
- Verifies:
  - ✅ No "Cannot operate on a closed database" errors
  - ✅ Telemetry history successfully extracted
  - ✅ JSON output is valid and complete

### Test Results
```bash
cd /home/runner/work/meshbot/meshbot/map
python3 test_database_close_fix.py
```

Output:
```
============================================================
Database Close Order - Unit Tests
============================================================

Testing cursor usage pattern...
✅ All 5 cursor operations occur before close (line 324)

Testing database operations order...
✅ Database operations complete without errors
   Exported 1 nodes
   ✅ Telemetry history extracted: 7 points

============================================================
✅ All tests passed!
============================================================
```

## Impact

### Fixed
- ✅ **"Cannot operate on a closed database" error** - Completely resolved
- ✅ **Telemetry history extraction** - Now works correctly
- ✅ **Database operation ordering** - All queries before close

### Not Changed
- ⚠️ **Locale warning** - System configuration issue, not code issue
  ```
  /bin/bash: warning: setlocale: LC_ALL: cannot change locale (en_US.UTF-8)
  ```
  This is harmless and occurs when the system doesn't have the en_US.UTF-8 locale installed.

- ⚠️ **"Aucune donnée de voisinage trouvée"** (No neighbor data found)
  This is expected behavior when no NEIGHBORINFO_APP packets have been collected.
  It's informational, not an error.

## Backward Compatibility
- ✅ No changes to function signatures
- ✅ No changes to output format
- ✅ No changes to behavior (except fixing the bug)
- ✅ All existing functionality preserved

## Files Modified
1. **map/export_nodes_from_db.py** (1 line moved, 1 comment updated)
2. **map/test_database_close_fix.py** (NEW - comprehensive test suite)

## Verification Steps
To verify this fix on the production system:

```bash
cd /home/dietpi/bot/map
./infoup_db.sh
```

Expected result:
- ✅ No "Cannot operate on a closed database" errors
- ✅ Telemetry history extracted successfully
- ✅ All exports complete without errors

The locale warning and "no neighbor data" messages are expected and not errors.
