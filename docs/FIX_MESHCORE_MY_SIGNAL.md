# Fix: MeshCore /my Signal Data Missing

## Problem Statement

The `/my` command was showing different responses for Meshtastic vs MeshCore networks:

### Meshtastic Response (Working)
```
⚫ ~-71dBm SNR:11.2dB | 📈 Excellente | 📍 ~<100m (estimé) | 📶 Signal local
```

### MeshCore Response (Broken)
```
📶 Signal: n/a | 📈 Inconnue | 📶 Signal local
```

MeshCore users were seeing "Signal: n/a" even though their radio was receiving packets with valid signal measurements.

## Root Cause Analysis

### The Signal Flow

1. **MeshCore CLI Wrapper** receives RF packets via RX_LOG_DATA events
2. RX_LOG packets contain **real signal data** (SNR, RSSI) extracted from the radio
3. These packets are forwarded to the bot with signal data intact

**meshcore_cli_wrapper.py, lines 1768-1769, 2244-2245:**
```python
snr = payload.get('snr', 0.0)
rssi = payload.get('rssi', 0)

bot_packet = {
    'from': sender_id,
    'snr': snr,      # Real RF data from radio
    'rssi': rssi,    # Real RF data from radio
    ...
}
```

4. **Direct Messages (DMs)** are handled separately
5. DM packets have **hardcoded** `snr=0.0` since they're not RF events

**meshcore_cli_wrapper.py, lines 1427-1428:**
```python
packet = {
    'from': sender_id,
    'rssi': 0,      # No RF data for DMs
    'snr': 0.0,     # No RF data for DMs
    ...
}
```

### The Bug

The `update_rx_history()` method was calculating a **running average** of SNR values:

**node_manager.py, lines 722-725 (OLD):**
```python
# Moyenne mobile du SNR
old_snr = self.rx_history[from_id]['snr']
count = self.rx_history[from_id]['count']
new_snr = (old_snr * count + snr) / (count + 1)  # ❌ Averages with 0.0!
```

**Example scenario:**
```
Step 1: RX_LOG packet arrives
  → snr = 11.2dB
  → rx_history[node]['snr'] = 11.2dB ✅

Step 2: User sends /my command via DM
  → DM packet has snr = 0.0dB
  → new_snr = (11.2 * 1 + 0.0) / 2 = 5.6dB ❌

Step 3: User sends another DM
  → DM packet has snr = 0.0dB
  → new_snr = (5.6 * 2 + 0.0) / 3 = 3.7dB ❌

Step 4: User runs /my command
  → Shows "Signal: n/a" (snr < 5dB threshold) ❌
```

Over time, with more DMs than RX_LOG packets, the average SNR approaches 0, making the signal data useless.

## Solution

**Skip rx_history updates when `snr=0.0`** to preserve real RF signal data.

### Code Changes

**node_manager.py, lines 716-721 (NEW):**
```python
# ✅ FIX: Ne pas mettre à jour rx_history si SNR=0.0
# Les paquets DM (MeshCore/Telegram) ont snr=0.0 par défaut
# On veut seulement stocker les données réelles des paquets RF (RX_LOG)
if snr == 0.0:
    debug_print(f"⏭️  Skipping rx_history update for 0x{from_id:08x} (snr=0.0, no RF data)")
    return
```

### How It Works Now

```
Step 1: RX_LOG packet arrives
  → snr = 11.2dB
  → rx_history[node]['snr'] = 11.2dB ✅

Step 2: User sends /my command via DM
  → DM packet has snr = 0.0dB
  → ⏭️  SKIPPED (no update) ✅
  → rx_history[node]['snr'] = 11.2dB (preserved)

Step 3: User sends another DM
  → DM packet has snr = 0.0dB
  → ⏭️  SKIPPED (no update) ✅
  → rx_history[node]['snr'] = 11.2dB (preserved)

Step 4: User runs /my command
  → Shows "SNR:11.2dB | Excellente" ✅
```

## Testing

### Test Suite

Created `tests/test_meshcore_my_signal.py` with three scenarios:

1. **Old Behavior Test**: Demonstrates the bug
2. **RF Data Preservation**: Verifies the fix
3. **Multiple Packets**: Complex real-world scenario

```bash
$ python3 tests/test_meshcore_my_signal.py

✅ ALL TESTS PASSED (3/3)
```

### Test Scenarios

**Scenario 1: Old behavior (broken)**
```
RX_LOG: SNR=11.2dB → rx_history: 11.2dB
DM:     SNR=0.0dB  → rx_history: 5.6dB (averaged, corrupted!)
```

**Scenario 2: New behavior (fixed)**
```
RX_LOG: SNR=11.2dB → rx_history: 11.2dB ✅
DM:     SNR=0.0dB  → rx_history: 11.2dB (skipped, preserved!)
```

**Scenario 3: Multiple packets**
```
Processing packets:
  RF packet: SNR=11.2dB → Updated (avg=11.2dB)
  RF packet: SNR=10.8dB → Updated (avg=11.0dB)
  DM packet: SNR=0.0dB  → Skipped (no RF data)
  RF packet: SNR=11.5dB → Updated (avg=11.2dB)
  DM packet: SNR=0.0dB  → Skipped (no RF data)
  DM packet: SNR=0.0dB  → Skipped (no RF data)
  RF packet: SNR=11.0dB → Updated (avg=11.1dB)

Final: snr=11.1dB (based on 4 RF packets, 3 DMs skipped)
```

## Impact

### Before (Broken)

**User Experience:**
- MeshCore users see "Signal: n/a" for `/my` command
- No way to check signal quality
- Frustrating for users trying to optimize antenna placement

**Technical:**
- rx_history gets corrupted by DM packets
- Real RF signal data is lost
- SNR averages approach 0 over time

### After (Fixed)

**User Experience:**
- MeshCore users see real signal data: "SNR:11.2dB | Excellente"
- Can check signal quality with `/my` command
- Same experience as Meshtastic users

**Technical:**
- rx_history preserves RF signal data
- DM packets don't corrupt measurements
- SNR averages remain accurate

## Verification

### Manual Testing

To verify the fix works:

1. **Connect MeshCore device** with CLI wrapper
2. **Wait for RX_LOG packets** to arrive (automatic)
3. **Send `/my` command** via DM
4. **Check response** - should show signal data

**Expected output:**
```
⚫ ~-71dBm SNR:11.2dB | 📈 Excellente | 📍 ~<100m (estimé) | 📶 Signal local
```

### Log Verification

Check logs for skip messages:
```bash
journalctl -u meshtastic-bot -f | grep "Skipping rx_history"

# Should see:
⏭️  Skipping rx_history update for 0x889fa138 (snr=0.0, no RF data)
```

## Files Modified

### Core Change

- **`node_manager.py`** (lines 716-721)
  - Added check to skip rx_history update when snr=0.0
  - Added debug logging for skipped updates

### Test & Documentation

- **`tests/test_meshcore_my_signal.py`** (NEW)
  - Comprehensive test suite
  - 3 test scenarios
  - Demonstrates bug and verifies fix

- **`docs/FIX_MESHCORE_MY_SIGNAL.md`** (THIS FILE)
  - Complete documentation
  - Root cause analysis
  - Solution explanation

## Technical Details

### Why SNR=0.0 Means "No Data"

In the MeshCore ecosystem:
- **RX_LOG packets** contain actual RF measurements from the radio
- **DM packets** are application-level messages without RF context
- Using `snr=0.0` as a sentinel value for "no RF data" is appropriate

### Why Not Use None?

We could use `snr=None` for DM packets, but:
1. Would require changes to CLI wrapper
2. Would require changes to serial interface
3. Using 0.0 as sentinel is simpler and backward compatible
4. The fix at the rx_history level is more robust

### Alternative Approaches Considered

**Option 1: Mark packets with `_no_rf_data` flag**
- Pros: More explicit
- Cons: Requires changes to multiple files

**Option 2: Separate rx_history for RF and DM**
- Pros: Complete separation
- Cons: More complex data structure

**Option 3: Current approach (skip snr=0.0)**
- Pros: Simple, minimal change, backward compatible
- Cons: Assumes 0.0 always means "no data"

We chose Option 3 because:
- SNR=0.0 is unlikely to occur naturally in RF (would be extreme noise)
- Minimal code changes
- Preserves existing packet format
- Easy to understand and maintain

## Benefits

| Benefit | Description |
|---------|-------------|
| 🎯 **Fixes User Issue** | MeshCore `/my` now shows signal data |
| 🔧 **Minimal Change** | Only 6 lines changed |
| ✅ **Well Tested** | 3 comprehensive test scenarios |
| 🔄 **Backward Compatible** | No breaking changes |
| 📊 **Accurate Data** | Preserves real RF measurements |
| 🌐 **Both Networks** | Works for MT and MC |

## Related Components

### MeshCore CLI Wrapper

**RX_LOG Processing** (`meshcore_cli_wrapper.py`):
- Lines 1760-1795: RX_LOG_DATA event handling
- Lines 2239-2252: Packet creation with SNR/RSSI

### Node Manager

**Signal History** (`node_manager.py`):
- Lines 691-740: update_rx_history() method
- Lines 714-730: rx_history data structure

### /my Command

**Signal Display** (`network_commands.py`):
- Lines 290-360: handle_my() method
- Lines 362-420: _format_my_response() method

## Summary

### Problem
- MeshCore `/my` showed "Signal: n/a"
- DM packets with snr=0.0 were corrupting RF signal data
- Running average pulled SNR toward zero

### Solution
- Skip rx_history updates when snr=0.0
- Preserve real RF signal data from RX_LOG packets
- Simple, minimal, effective fix

### Result
- ✅ MeshCore users see real signal data
- ✅ Both MT and MC networks work identically
- ✅ No breaking changes
- ✅ Fully tested and documented

**Status: ✅ FIXED**
