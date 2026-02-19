# Debug Logging for rx_history Updates

## Problem
User reports `/my` command showing stale signal data (7 days old):
```
📶 Signal: n/a | 📈 Inconnue (7j) | 📶 Signal local
```

## Diagnostic Logging Added

Comprehensive logging has been added to trace why RX_LOG packets aren't updating rx_history.

### Log Locations

#### 1. MeshCore RX_LOG Event Handler
**File:** `meshcore_cli_wrapper.py` line ~1778

**Log Message:**
```
📊 [RX_LOG] Extracted signal data: snr=11.2dB, rssi=-71dBm
```

**What it shows:**
- SNR and RSSI values extracted from MeshCore RX_LOG event
- If values are 0.0/0, the RX_LOG event doesn't contain signal data

#### 2. rx_history Update Attempt
**File:** `node_manager.py` line ~716

**Log Message:**
```
🔍 [RX_HISTORY] Node 0x889fa138 | snr=11.2 | DM=False | RX_LOG=True | hops=3
```

**What it shows:**
- Node ID attempting to update
- SNR value received
- Packet type (DM vs RX_LOG)
- Number of hops taken

#### 3. rx_history Entry Created
**File:** `node_manager.py` line ~736

**Log Message:**
```
✅ [RX_HISTORY] NEW entry for 0x889fa138 (Node-889fa138) | snr=11.2dB
```

**What it shows:**
- New rx_history entry created
- Node name and ID
- Initial SNR value

#### 4. rx_history Entry Updated
**File:** `node_manager.py` line ~747

**Log Message:**
```
✅ [RX_HISTORY] UPDATED 0x889fa138 (Node-889fa138) | old_snr=10.0→new_snr=10.6dB | count=6
```

**What it shows:**
- Existing entry updated
- Old SNR → New SNR (averaged)
- Update count

#### 5. rx_history Update Skipped
**File:** `node_manager.py` line ~719-721

**Log Message:**
```
⏭️  Skipping rx_history update for 0x889fa138 (MeshCore DM, no RF data)
```
or
```
⏭️  Skipping rx_history update for 0x889fa138 (snr=0.0, no RF data)
```

**What it shows:**
- Update skipped because SNR=0.0
- Reason: DM packet or missing RF data

## How to Use Diagnostic Logs

### Step 1: Enable Debug Mode
```bash
# In config.py
DEBUG_MODE = True
```

### Step 2: Monitor Logs
```bash
# Follow bot logs
journalctl -u meshtastic-bot -f | grep -E "(RX_HISTORY|RX_LOG)"

# Or with systemd
tail -f /var/log/syslog | grep meshtastic-bot | grep -E "(RX_HISTORY|RX_LOG)"
```

### Step 3: Send Test Message
1. Send `/my` command from MeshCore device
2. Watch logs for the sequence

### Expected Good Flow
```
📊 [RX_LOG] Extracted signal data: snr=11.2dB, rssi=-71dBm
🔍 [RX_HISTORY] Node 0x889fa138 | snr=11.2 | DM=False | RX_LOG=True | hops=3
✅ [RX_HISTORY] UPDATED 0x889fa138 (Node-889fa138) | old_snr=10.0→new_snr=10.6dB | count=6
```

### Potential Problem Scenarios

#### Scenario 1: No RX_LOG Events
**Symptoms:**
- No `📊 [RX_LOG]` logs appearing
- No signal data updates

**Cause:**
- MeshCore isn't sending RX_LOG events
- Event subscription not working

**Solution:**
- Check MeshCore connection
- Verify event dispatcher is running

#### Scenario 2: RX_LOG with SNR=0.0
**Symptoms:**
```
📊 [RX_LOG] Extracted signal data: snr=0.0dB, rssi=0dBm
🔍 [RX_HISTORY] Node 0x889fa138 | snr=0.0 | DM=False | RX_LOG=True | hops=0
```

**BUT NO** ✅ update log

**Cause:**
- RX_LOG event doesn't contain signal data
- MeshCore library not populating SNR/RSSI
- Line 716 condition: `if snr == 0.0 and not is_meshcore_rx_log`

**Wait!** This should NOT skip RX_LOG packets! The condition is:
```python
if snr == 0.0 and not is_meshcore_rx_log:
```

If `is_meshcore_rx_log=True`, it should NOT skip even with `snr=0.0`.

**This means:**
1. Either `_meshcore_rx_log` flag is not set
2. Or SNR is not 0.0 but something else

#### Scenario 3: DM Packets Skipped (Expected)
**Symptoms:**
```
🔍 [RX_HISTORY] Node 0x889fa138 | snr=0.0 | DM=True | RX_LOG=False | hops=0
⏭️  Skipping rx_history update for 0x889fa138 (MeshCore DM, no RF data)
```

**Cause:**
- DM packet has no RF signal data (expected)
- Should be skipped (working correctly)

## Analysis Commands

### Find Updates for Specific Node
```bash
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "0x889fa138"
```

### Count RX_LOG Events
```bash
journalctl -u meshtastic-bot --since "1 hour ago" | grep -c "📊 \[RX_LOG\]"
```

### Check Last Update Time
```bash
journalctl -u meshtastic-bot --since "1 hour ago" | grep "✅ \[RX_HISTORY\]" | tail -5
```

### Find Skip Reasons
```bash
journalctl -u meshtastic-bot --since "1 hour ago" | grep "⏭️"
```

## Troubleshooting Guide

### Issue: No signal data updates
1. Check if RX_LOG events arriving: `grep "📊 \[RX_LOG\]"`
2. If NO: MeshCore event issue
3. If YES: Check SNR values in events

### Issue: SNR always 0.0 in RX_LOG
1. Check MeshCore library version
2. Verify RX_LOG event payload structure
3. May need to extract SNR differently

### Issue: Updates happening but /my still shows stale
1. Check if correct node ID updating
2. Verify rx_history not being cleared
3. Check /my command using correct rx_history field

## Next Steps

After deploying these logs:
1. Monitor for 10-15 minutes
2. Send `/my` command
3. Capture log sequence
4. Share logs showing the issue
5. We can then identify exact root cause

## Files Modified
- `node_manager.py` - rx_history update logging
- `meshcore_cli_wrapper.py` - RX_LOG extraction logging

## Test Suite
- `tests/test_rx_history_debug_logging.py` - Verify log formats
