# /propag Command Fix Summary

## Issue
Radio links command (`/propag`) was showing duplicate entries for the same node pairs, making the report less useful. Each packet between two nodes created a separate "link" entry.

## Root Cause
The `load_radio_links_with_positions()` method in `traffic_persistence.py` returns **all packets** with SNR/RSSI data between nodes. Without deduplication, multiple packets between the same pair appeared as separate links in the top N list.

## Solution

### 1. Deduplication Logic
Added deduplication in `get_propagation_report()` after GPS validation:

```python
# Group by bidirectional pair
pair_key = tuple(sorted([from_id, to_id]))

# Keep best link per pair based on:
# 1. SNR quality (higher is better)
# 2. SNR presence (prefer links with SNR)
# 3. Recency (newer timestamp)
```

### 2. Altitude Display
Enhanced output with altitude information:
- Fetched from database (30-day retention) or node_manager
- Format: `Alt: 45m`
- Defaults to 0m if unavailable

## Changes

### Modified Files
- **traffic_monitor.py** (55 lines changed)
  - `get_propagation_report()` method
  - Added altitude variables and fetching
  - Added deduplication logic
  - Updated display format

### Added Files
- **test_propag_deduplication.py** - Tests basic deduplication (4→2 links)
- **test_propag_bidirectional.py** - Tests bidirectional handling (A→B = B→A)
- **PROPAG_DEDUPLICATION_FIX.md** - Detailed documentation
- **PROPAG_FIX_SUMMARY.md** - This summary

## Test Results

### Test 1: Basic Deduplication
```
✅ Test de déduplication réussi!
   - 4 liens réduits à 2 liens uniques
   - Meilleur SNR conservé pour liaison A->B (-5.5)
```

### Test 2: Bidirectional Deduplication
```
✅ Test de déduplication bidirectionnelle réussi!
   - A→B et B→A correctement fusionnés
   - Meilleur SNR conservé (-5.5 de B→A)
   - 3 liens réduits à 2 liens uniques
```

## Impact

### Before
- Top 5 list could show 5 packets from 2 node pairs
- Duplicate entries reduced report usefulness
- No altitude information

### After
- Top N shows N **unique** node pairs
- Best signal quality kept for each pair
- Altitude context helps understand propagation
- Statistics reflect unique pairs count

## Backward Compatibility
✅ Compact format (LoRa, 180 chars) - Compatible
✅ Detailed format (Telegram) - Enhanced
✅ No breaking changes to command interface
✅ Graceful handling of missing data

## Benefits
1. 📊 **Clearer reports** - No duplicate node pairs
2. 📶 **Better signal info** - Best SNR for each link
3. 🎯 **More useful** - Top N = N unique links
4. 🏔️ **Altitude context** - Understand propagation
5. 📈 **Accurate stats** - True unique pairs count

## Commands to Test
```bash
# Run deduplication tests
python3 test_propag_deduplication.py
python3 test_propag_bidirectional.py

# Test in bot (once deployed)
/propag            # Default 24h, top 5
/propag 48         # 48h window
/propag 24 10      # Top 10 links
```

## Deployment Notes
- No database migration required
- No configuration changes needed
- No breaking changes to existing functionality
- Safe to deploy immediately

## Related Documentation
- `PROPAG_DEDUPLICATION_FIX.md` - Detailed fix documentation
- `CLAUDE.md` - AI assistant guide (section on Traffic Monitor)
- `README.md` - User documentation (mentions /propag command)
