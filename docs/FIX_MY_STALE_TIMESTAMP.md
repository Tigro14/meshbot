# Fix: `/my` Command Showing Stale Timestamp

## Problem

User reports that after 12 hours, the `/my` command still shows 7-day-old data:

```
📶 Signal: n/a | 📈 Inconnue (7j) | 📶 Signal local
```

Breaking down the response:
- `📶 Signal: n/a` - No signal data (snr=0, rssi=0)
- `📈 Inconnue (7j)` - Unknown quality, last seen 7 DAYS ago
- `📶 Signal local` - Indicates local signal

Despite the user having just sent the `/my` command (proving they're active NOW), the system shows they were last seen 7 days ago.

## Root Cause

### The Scenario
1. User sends `/my` command via Direct Message (DM)
2. DM packet arrives with `snr=0.0` and `rssi=0` (no RF data)
3. Packet has `_meshcore_dm=True` flag

### The Bug
In `node_manager.py::update_rx_history()`:

```python
# OLD CODE (Broken)
if snr == 0.0 and not is_meshcore_rx_log:
    debug_print(f"⏭️  Skipping rx_history update...")
    return  # ❌ ENTIRE update skipped!
```

When this code executed:
- The entire `update_rx_history()` function returned early
- `last_seen` timestamp was NEVER updated
- Result: rx_history shows 7-day-old timestamp

### Why DM Packets Have snr=0.0
- Direct Messages are app-level packets, not RF packets
- They don't have radio signal metrics (SNR/RSSI)
- MeshCore sets `snr=0.0` and `rssi=0` by default
- This is CORRECT behavior - DMs don't represent RF signal quality

### The Fundamental Issue
The code was treating ALL packets with `snr=0.0` the same way:
- **DM Packets**: Should update timestamp but not SNR
- **Unknown Packets**: Should be skipped entirely

But it was skipping EVERYTHING with `snr=0.0`, including DMs.

## Solution

### The Fix
Always update `last_seen` timestamp, even for packets with `snr=0.0`:

```python
# NEW CODE (Fixed)
if snr == 0.0 and not is_meshcore_rx_log:
    # ✅ Update last_seen timestamp (even though SNR is zero)
    if from_id in self.rx_history:
        self.rx_history[from_id]['last_seen'] = time.time()
        self.rx_history[from_id]['name'] = name
        debug_print(f"✅ [RX_HISTORY] TIMESTAMP updated 0x{from_id:08x} (snr=0.0, no SNR update)")
    elif is_meshcore_dm:
        # Create new entry for DM from unknown node
        self.rx_history[from_id] = {
            'name': name,
            'snr': 0.0,
            'last_seen': time.time(),
            'count': 1
        }
        debug_print(f"✅ [RX_HISTORY] NEW entry 0x{from_id:08x} (snr=0.0 from DM)")
    return  # Still return (don't update SNR value)
```

### What This Does
1. **Existing Nodes**: Updates `last_seen` to current time, keeps old SNR
2. **New Nodes**: Creates entry with `snr=0.0`, current timestamp
3. **SNR Values**: Never updated from DM packets (correct!)
4. **RX_LOG Packets**: Still fully update both timestamp AND SNR

## Data Flow Comparison

### Before Fix (Broken)

```
User sends /my DM:
┌─────────────────────────────────────────┐
│ DM Packet arrives                       │
│   snr: 0.0                              │
│   rssi: 0                               │
│   _meshcore_dm: True                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ update_rx_history()                     │
│   Check: snr=0.0 and not RX_LOG?       │
│   → YES                                 │
│   → return  ❌ EXIT IMMEDIATELY         │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ rx_history[0x889fa138]                  │
│   snr: 10.0  (unchanged)                │
│   last_seen: 7 days ago  ❌ STALE!      │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ /my Response                            │
│ "📶 Signal: n/a | 📈 Inconnue (7j)"    │
└─────────────────────────────────────────┘
```

### After Fix (Working)

```
User sends /my DM:
┌─────────────────────────────────────────┐
│ DM Packet arrives                       │
│   snr: 0.0                              │
│   rssi: 0                               │
│   _meshcore_dm: True                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ update_rx_history()                     │
│   Check: snr=0.0 and not RX_LOG?       │
│   → YES                                 │
│   → Update last_seen to NOW ✅          │
│   → Keep SNR unchanged ✅               │
│   → return (don't update SNR)           │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ rx_history[0x889fa138]                  │
│   snr: 10.0  (unchanged, correct!)      │
│   last_seen: NOW  ✅ CURRENT!           │
└─────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ /my Response                            │
│ "📶 Signal: n/a | 📈 Inconnue (2m)"    │
└─────────────────────────────────────────┘
```

## Test Results

```bash
$ python3 tests/test_rx_history_timestamp_fix.py

TEST 1: Timestamp updates with snr=0.0
  Initial: snr=10.0, last_seen=1 day ago
  DM arrives with snr=0.0
  Result: snr=10.0 (preserved), last_seen=NOW ✅
✅ PASS

TEST 2: New entry creation with snr=0.0
  Unknown node sends DM with snr=0.0
  Result: Entry created with snr=0.0, last_seen=NOW ✅
✅ PASS

TEST 3: Full update with real SNR
  RX_LOG packet with snr=12.0
  Result: SNR averaged correctly ✅
✅ PASS

RESULTS: 3/3 passed
```

## Benefits

| Benefit | Before | After |
|---------|--------|-------|
| **Timestamp** | 7 days old ❌ | 2 minutes ago ✅ |
| **User Feedback** | Looks disconnected | Shows recent activity |
| **Signal Data** | n/a (correct) | n/a (still correct) |
| **Data Integrity** | Stale | Current |

## Deployment

### No Configuration Changes Required
This fix is fully backward compatible and requires no configuration changes.

### Expected Behavior After Deployment

**User sends `/my` via DM:**
```
Before: 📶 Signal: n/a | 📈 Inconnue (7j) | 📶 Signal local
After:  📶 Signal: n/a | 📈 Inconnue (2m) | 📶 Signal local
```

**User receives RF packet, then sends `/my`:**
```
RX_LOG: Updates SNR to 11.2dB
/my Response: ⚫ ~-71dBm SNR:11.2dB | 📈 Excellente (30s) | 📶 Signal local
```

## Technical Details

### Files Modified
- `node_manager.py` (lines 716-732)

### Files Added
- `tests/test_rx_history_timestamp_fix.py`
- `docs/FIX_MY_STALE_TIMESTAMP.md` (this file)

### Logic Changes

**Packet Handling:**
1. All packets go through `update_rx_history()`
2. If `snr=0.0` and NOT RX_LOG:
   - Update `last_seen` to NOW ✅
   - Keep existing SNR value ✅
   - Don't average SNR from this packet ✅
3. If `snr>0.0` OR RX_LOG:
   - Full update (timestamp AND SNR) ✅

### Edge Cases Handled
- **New node via DM**: Creates entry with `snr=0.0`, current timestamp
- **Existing node via DM**: Updates timestamp, keeps old SNR
- **RX_LOG with snr=0.0**: Full update (edge case but handled)
- **Normal RF packet**: Full update as before

## Summary

**Problem**: `/my` showed 7-day-old timestamp despite user being active NOW

**Cause**: DM packets with `snr=0.0` were completely skipped

**Fix**: Always update `last_seen` timestamp, skip only SNR value update

**Result**: User sees current activity time instead of stale data

**Status**: ✅ FIXED AND TESTED
