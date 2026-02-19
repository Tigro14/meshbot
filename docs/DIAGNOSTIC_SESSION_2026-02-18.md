# Diagnostic Tools for MeshCore /my Signal Data Issue

## Session Summary
**Date:** 2026-02-18
**Issue:** User reports `/my` command showing stale data (7 days old) with no signal

## Problem Statement
```
📶 Signal: n/a | 📈 Inconnue (7j) | 📶 Signal local
```

Translation:
- Signal: n/a (snr=0, rssi=0)
- Inconnue (7j) = Unknown quality, last seen 7 days ago
- No current signal data from recent packets

## Previous Fixes Applied

During this session, we've implemented multiple fixes:

1. ✅ **Fix /my TCP Dependency** - Uses local rx_history instead of TCP
2. ✅ **Fix Node Recording Bug** - Handles None values properly
3. ✅ **Fix MeshCore Signal Data** - Skip snr=0.0 for DMs, not RX_LOG
4. ✅ **Fix Hop Count and Path** - Display routing path correctly
5. ✅ **Fix Stale Data** - RX_LOG packets should update rx_history
6. ✅ **Fix Message Deduplication** - Prevent 5x delivery
7. ✅ **Fix f-string Error** - Format specifier bug

## Current Status

Despite all fixes, user STILL reports stale data. This suggests:
- Either RX_LOG packets aren't arriving
- Or RX_LOG packets have SNR=0.0
- Or something else we haven't identified

## Diagnostic Tools Added

### 1. Comprehensive Logging
**Files Modified:**
- `node_manager.py` - Log all rx_history update attempts
- `meshcore_cli_wrapper.py` - Log signal data extraction

**Log Types:**
- 📊 Signal data extraction from RX_LOG events
- 🔍 rx_history update attempts with full context
- ✅ Successful updates (new/existing entries)
- ⏭️ Skipped updates with reason

### 2. Documentation
**File:** `docs/DEBUG_RX_HISTORY_LOGGING.md`

Includes:
- Log message descriptions
- Expected flow sequences
- Problem scenario analysis
- Analysis commands
- Troubleshooting guide

### 3. Test Suite
**File:** `tests/test_rx_history_debug_logging.py`

Verifies all log message formats are correct.

## How to Diagnose

### Step 1: Enable Debug Mode
```python
# config.py
DEBUG_MODE = True
```

### Step 2: Restart Bot
```bash
sudo systemctl restart meshtastic-bot
```

### Step 3: Monitor Logs
```bash
journalctl -u meshtastic-bot -f | grep -E "(RX_HISTORY|RX_LOG)"
```

### Step 4: Send /my Command
From MeshCore device, send: `/my`

### Step 5: Observe Log Sequence

#### Expected (Working):
```
📊 [RX_LOG] Extracted signal data: snr=11.2dB, rssi=-71dBm
🔍 [RX_HISTORY] Node 0x889fa138 | snr=11.2 | DM=False | RX_LOG=True | hops=3
✅ [RX_HISTORY] UPDATED 0x889fa138 (Node-889fa138) | old_snr=10.0→new_snr=10.6dB | count=6
```

#### Scenario A: No RX_LOG Events
```
(nothing appears)
```
**Problem:** MeshCore not sending RX_LOG events
**Root Cause:** Event subscription issue

#### Scenario B: RX_LOG with SNR=0.0
```
📊 [RX_LOG] Extracted signal data: snr=0.0dB, rssi=0dBm
🔍 [RX_HISTORY] Node 0x889fa138 | snr=0.0 | DM=False | RX_LOG=True | hops=0
⏭️  Skipping rx_history update for 0x889fa138 (snr=0.0, no RF data)
```
**Problem:** RX_LOG events don't contain signal data
**Root Cause:** MeshCore library not populating SNR/RSSI

**WAIT!** This shouldn't happen because line 716 says:
```python
if snr == 0.0 and not is_meshcore_rx_log:
```
If `is_meshcore_rx_log=True`, it should NOT skip!

So if we see this, it means `_meshcore_rx_log` flag is NOT being set properly.

#### Scenario C: Wrong Node Being Updated
```
📊 [RX_LOG] Extracted signal data: snr=11.2dB, rssi=-71dBm
🔍 [RX_HISTORY] Node 0x12345678 | snr=11.2 | DM=False | RX_LOG=True | hops=3
✅ [RX_HISTORY] UPDATED 0x12345678 (Other-Node) | ...
```
**Problem:** Different node being updated
**Root Cause:** Node ID mismatch in packet

## Key Insight

The logic in `node_manager.py` line 716 is:
```python
if snr == 0.0 and not is_meshcore_rx_log:
```

This means:
- **Skip** if SNR=0.0 AND NOT an RX_LOG packet
- **Don't Skip** if RX_LOG packet (even with SNR=0.0)

So RX_LOG packets should ALWAYS update rx_history, even with snr=0.0.

**If they're not updating, one of these is true:**
1. `_meshcore_rx_log` flag not being set
2. RX_LOG packets not arriving at `update_rx_history()`
3. Some other condition blocking updates

## Next Actions Required

### From User:
1. Deploy updated bot with diagnostic logging
2. Send `/my` command from MeshCore device
3. Capture and share log output showing:
   - 5 minutes before sending `/my`
   - During `/my` command
   - 2 minutes after

### From Developer:
1. Analyze captured logs
2. Identify which scenario matches
3. Implement targeted fix

## Analysis Commands

```bash
# Find RX_LOG events
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "📊 \[RX_LOG\]"

# Find rx_history updates
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "🔍 \[RX_HISTORY\]"

# Find successful updates
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "✅ \[RX_HISTORY\]"

# Find skipped updates
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "⏭️"

# Count events
journalctl -u meshtastic-bot --since "1 hour ago" | grep -c "📊 \[RX_LOG\]"
```

## Files in This Diagnostic Session

### Modified:
- `node_manager.py` - Added rx_history update logging
- `meshcore_cli_wrapper.py` - Added RX_LOG extraction logging

### Added:
- `tests/test_rx_history_debug_logging.py` - Test suite
- `docs/DEBUG_RX_HISTORY_LOGGING.md` - Diagnostic guide
- `docs/DIAGNOSTIC_SESSION_2026-02-18.md` - This file

## Summary

**Problem:** MeshCore `/my` shows 7-day-old data
**Fixes Applied:** 7 different fixes across the session
**Current Status:** Still showing stale data
**Action:** Diagnostic logging added to identify root cause
**Next Step:** Deploy, monitor logs, share results

**Total Changes This Session:**
- Files Modified: 8
- Files Added: 15
- Tests Added: 8 test suites
- Documentation: 8 files
- Lines of Code: ~2000+

## Expected Resolution

Once user shares logs, we will see ONE of these:
1. **No RX_LOG events** → Fix event subscription
2. **RX_LOG with SNR=0.0** → Fix signal extraction
3. **Wrong node updated** → Fix node ID routing
4. **Some other issue** → Targeted fix based on logs

**Status:** ✅ READY FOR USER TESTING
