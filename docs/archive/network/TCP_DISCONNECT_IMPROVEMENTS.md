# TCP Reconnection Improvements - Response to Issue

## User Feedback

**Issue**: "still no change on tcp disconnect"

The TCP is still disconnecting despite the reconnection fix. This suggests the deferred pubkey sync might be causing the disconnections.

## Additional Improvements (Commit c5705ae)

### 1. Increased Sync Delay

**Changed**: `TCP_PUBKEY_SYNC_DELAY` from 15s to 30s

**Rationale**: Some ESP32 nodes need more time to fully stabilize their internal state. The 15-second delay may not be sufficient for slower or heavily-loaded nodes.

```python
# Before
TCP_PUBKEY_SYNC_DELAY = 15  # May be too short for some ESP32

# After
TCP_PUBKEY_SYNC_DELAY = 30  # More conservative, better stability
```

### 2. Added Skip Option

**New Flag**: `TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT`

**Purpose**: Completely disable the pubkey sync after reconnection if it's causing TCP disconnections.

```python
# Default behavior (sync after 30s delay)
TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT = False

# Skip immediate sync if causing issues
TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT = True
```

**When to use**: If you observe that TCP reconnections complete successfully but then disconnect again ~30 seconds later (during pubkey sync), enable this flag.

**Trade-off**: 
- ✅ Prevents potential TCP disconnections from sync
- ❌ DM decryption won't work for up to 5 minutes (until next periodic sync)

### 3. Race Condition Protection

**Problem**: The deferred sync was accessing `self.interface` which could have changed if another reconnection occurred during the 30-second delay.

**Solution**: Capture interface reference at scheduling time:

```python
# Capture reference
interface_ref = new_interface

def deferred_pubkey_sync():
    # Use captured reference, not self.interface
    injected = self.node_manager.sync_pubkeys_to_interface(interface_ref, force=True)
```

### 4. Validation Checks

Added pre-sync validation to avoid operating on stale interfaces:

```python
# Check if interface changed
if interface_ref != self.interface:
    info_print("ℹ️ Interface changée pendant le délai, skip sync")
    return

# Check if reconnection in progress
if self._tcp_reconnection_in_progress:
    info_print("ℹ️ Reconnexion en cours, skip sync différé")
    return
```

## Diagnostic Steps

### Step 1: Identify if Sync is Causing Disconnects

Monitor logs with current settings (30s delay):

```bash
journalctl -u meshbot -f | grep -E "Synchronisation clés|SYNC COMPLETE|SILENCE TCP|reconnexion"
```

**Look for this pattern**:
```
13:35:58 [INFO] ✅ Reconnexion TCP réussie (background)
13:35:58 [INFO] 🔑 Synchronisation clés publiques programmée dans 30s...
... (everything works fine) ...
13:36:28 [INFO] 🔑 Démarrage synchronisation clés publiques différée...
13:36:28 [INFO] 🔄 Starting public key synchronization to interface.nodes...
13:36:28 [INFO] ✅ SYNC COMPLETE: 42 public keys synchronized
... (~30-60 seconds later) ...
13:37:28 [INFO] ⚠️ SILENCE TCP: 130s sans paquet (max: 120s)  ← DISCONNECT!
```

**If you see this pattern**: The sync is likely causing the disconnect.

### Step 2: Test with Skip Option

Edit `main_bot.py` and change:

```python
class MeshBot:
    # ... other settings ...
    TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT = True  # ← Change this
```

Restart bot and monitor:

```bash
sudo systemctl restart meshbot
journalctl -u meshbot -f | grep -E "skip|reconnexion|SILENCE TCP"
```

**Expected logs**:
```
13:35:58 [INFO] ✅ Reconnexion TCP réussie (background)
13:35:58 [INFO] ℹ️ Synchronisation clés publiques skippée (TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT=True)
13:35:58 [INFO]    Prochaine sync au prochain cycle périodique (5min)
```

**If no more disconnects**: The sync was the culprit. Keep skip enabled.
**If still disconnects**: The issue is elsewhere (network, ESP32 firmware, etc.)

## Alternative Solutions

### Option A: Use Only Periodic Sync (Safest)

```python
TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT = True
```

**Pros**:
- ✅ Eliminates any risk from immediate sync
- ✅ Reconnection always succeeds
- ✅ Periodic sync (5min) handles keys eventually

**Cons**:
- ❌ DM decryption won't work for up to 5 minutes after reconnection

### Option B: Very Long Delay (Conservative)

```python
TCP_PUBKEY_SYNC_DELAY = 60  # Wait 1 full minute
TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT = False
```

**Pros**:
- ✅ DM decryption works after 60s (faster than 5min)
- ✅ Maximum time for interface to stabilize

**Cons**:
- ❌ Still might cause disconnect if sync itself is problematic

### Option C: Default (Current)

```python
TCP_PUBKEY_SYNC_DELAY = 30  # Wait 30 seconds
TCP_SKIP_PUBKEY_SYNC_ON_RECONNECT = False
```

**Pros**:
- ✅ Balanced approach
- ✅ DM decryption works after 30s
- ✅ Should work for most ESP32 nodes

**Cons**:
- ❌ May still cause issues on very slow nodes

## Root Cause Analysis

Why might the pubkey sync cause TCP disconnects?

### Theory 1: ESP32 Resource Exhaustion

Accessing `interface.nodes` triggers ESP32 to:
1. Query internal node list
2. Send data over TCP socket
3. Allocate memory for response

If ESP32 is low on memory or CPU, this operation might:
- Cause watchdog timer reset
- Drop TCP connection
- Restart network stack

### Theory 2: Single TCP Connection Limit

ESP32-based Meshtastic nodes often support only ONE TCP connection. If:
- Bot's connection is not fully established internally
- Sync triggers additional socket operations
- ESP32 sees it as a second connection attempt
- Drops the connection to enforce single-connection limit

### Theory 3: Firmware Bug

Some Meshtastic firmware versions have issues with:
- Rapid successive operations after connection
- Concurrent access to node list
- Memory fragmentation after reconnection

## Monitoring & Verification

### Key Metrics

Monitor these after applying fix:

1. **Reconnection frequency**:
   ```bash
   journalctl -u meshbot --since "1 hour ago" | grep "Reconnexion TCP" | wc -l
   ```
   Should be 0-2 per hour (not frequent)

2. **Sync completion rate**:
   ```bash
   journalctl -u meshbot --since "1 hour ago" | grep "SYNC COMPLETE"
   ```
   Should match reconnection count (if skip disabled)

3. **Disconnect timing**:
   ```bash
   journalctl -u meshbot --since "1 hour ago" | grep -E "reconnexion|SILENCE TCP" | tail -20
   ```
   Note: Time between reconnection and next silence

### Success Criteria

**With skip disabled (default)**:
- Reconnections complete in 18s
- Sync completes in 30s (T+48s total)
- No disconnect for at least 5 minutes after sync
- DM decryption works immediately

**With skip enabled**:
- Reconnections complete in 18s
- No disconnect for at least 10+ minutes
- DM decryption works after next periodic sync (≤5min)

## Next Steps

1. **Test with default settings** (30s delay, no skip)
   - Monitor for 24 hours
   - Check if disconnects still occur
   - Note timing relative to reconnection

2. **If still disconnecting**:
   - Enable skip option
   - Test for 24 hours
   - Compare disconnect frequency

3. **Report findings**:
   - Include log excerpts
   - Note timing patterns
   - Identify if sync-related or not

## Conclusion

The improvements provide two strategies:
1. **Conservative delay (30s)**: More time for stabilization
2. **Skip option**: Completely avoid sync if problematic

These should address TCP disconnect issues caused by the pubkey sync operation. If disconnects persist with skip enabled, the issue is unrelated to pubkey sync and requires different investigation (network quality, ESP32 firmware, power supply, etc.).

---

**Commit**: c5705ae
**Date**: January 5, 2025
**Status**: Ready for testing
