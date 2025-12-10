# Fix Summary: TypeError in /neighbors Command

## Issue
The `/neighbors` Telegram command was crashing with:
```
Dec 10 15:20:22 DietPi meshtastic-bot[26236]: TypeError: '<' not supported between instances of 'NoneType' and 'float'
```

When user "Clickyluke" ran the command, the bot encountered neighbors with `None` SNR values in the database, causing a sorting failure.

## Root Cause Analysis

### The Problem
Python 3 cannot compare `None` with numeric values. The sorting lambda:
```python
key=lambda x: x.get('snr', -999)
```

Only provides a default value when the key is **missing**. When the key **exists** but has value `None`, it returns `None` directly, causing the TypeError during comparison.

### Why SNR Can Be None
1. Database stores SNR as nullable column
2. NEIGHBORINFO_APP packets can have missing or null SNR values
3. MQTT neighbor data may not include SNR for all neighbors
4. Radio conditions may prevent SNR measurement

## Solution

### Lambda Fix Pattern
Changed from:
```python
key=lambda x: x.get('snr', -999)
```

To:
```python
key=lambda x: x.get('snr') if x.get('snr') is not None else -999
```

This explicitly checks for `None` and converts it to a numeric value for sorting.

## Files Modified

### Production Code (7 files)

1. **traffic_monitor.py** (line 2457)
   - Main fix for `get_neighbors_report()` detailed format
   - Neighbors sorted by SNR for display

2. **node_manager.py** (3 changes)
   - Fixed SNR extraction from packets (lines 495-499)
   - Fixed `format_rx_report()` sorting (line 398)
   - Fixed duplicate `format_rx_report()` sorting (line 603)

3. **remote_nodes_client.py** (line 557)
   - Fixed remote node SNR sorting

4. **telegram_bot/commands/network_commands.py** (line 113)
   - Fixed Telegram node listing SNR sorting

### Test Files (3 files)

5. **test_mqtt_nodeinfo_translation.py** (line 113)
   - Updated to use correct pattern

6. **test_mqtt_nodeinfo_integration.py** (lines 107, 128)
   - Updated 2 instances to use correct pattern

7. **test_neighbors_snr_none.py** (NEW)
   - Comprehensive test validating the fix
   - Tests old vs new lambda behavior
   - Verifies sorting order with mixed None/float values

## Testing

### Test Coverage
- ✅ Old lambda correctly fails with TypeError
- ✅ New lambda sorts correctly with None values at end
- ✅ Sorting order verified with mixed None/float values
- ✅ Display formatting works correctly
- ✅ All existing tests still pass

### Test Output
```
======================================================================
✅ ALL TESTS PASSED!
======================================================================
Test 1: Lambda sorting with None values - PASSED
Test 2: Integration test with sorting logic - PASSED
```

## Impact Analysis

### User Impact
- **Before**: `/neighbors` command crashed when any neighbor had None SNR
- **After**: Command works correctly, None SNR values sorted to end of list

### Performance
- No performance impact
- Same O(n log n) sorting complexity
- Slightly more explicit None check (negligible overhead)

### Backward Compatibility
- Fully backward compatible
- No API changes
- No database schema changes
- Existing data handled correctly

## Verification Steps

To verify the fix works:

1. **Manual Test**:
   ```bash
   # Send via Telegram or Mesh
   /neighbors
   ```
   Should display all neighbors without crashing, even with None SNR values

2. **Automated Test**:
   ```bash
   python3 test_neighbors_snr_none.py
   ```
   Should show "ALL TESTS PASSED"

3. **Database Check**:
   ```bash
   sqlite3 traffic_history.db "SELECT COUNT(*) FROM neighbors WHERE snr IS NULL;"
   ```
   Shows how many neighbors have None SNR (common in real data)

## Prevention

### Code Review Guidelines
When sorting by numeric fields:
- ✅ **DO**: Use explicit None checks: `x.get('field') if x.get('field') is not None else default`
- ❌ **DON'T**: Rely on dict.get() default alone: `x.get('field', default)`

### Future Improvements
Consider:
1. Database constraint to prevent None SNR (store 0.0 instead)
2. Data validation at insertion point
3. Type hints for better static analysis
4. Unit tests for all sorting operations

## Related Issues

This fix also prevents similar issues in:
- Remote node listings
- RX history reports
- MQTT neighbor data processing

## Commits

1. `831eb8d` - Fix TypeError when sorting neighbors with None SNR values
2. `2f4843d` - Fix all SNR sorting to handle None values correctly

## Author
GitHub Copilot - 2025-12-10

## Reviewed By
(To be filled by code reviewer)
