# MeshCore Packet Source Detection - Diagnostic Guide

## Problem

User reports that MeshCore packets are not being logged with classification in DEBUG mode, despite `DEBUG_MODE = True`.

## Investigation Summary

After comprehensive analysis, we confirmed:
1. ✅ **DEBUG_MODE is enabled** - config.py has DEBUG_MODE = True
2. ✅ **Logging functions work** - debug_print_mc() and debug_print_mt() are functional
3. ✅ **Classification logic exists** - _log_packet_debug uses correct debug_print_mc when source='meshcore'
4. ❓ **Root cause: Packets may not be assigned source='meshcore'**

## How Packet Source Detection Works

### Source Assignment Flow

```
Packet arrives → on_message(network_source) → Source Detection Logic → add_packet(source) → _log_packet_debug(source)
```

**Key source detection logic (main_bot.py:543-570):**

```python
if self._dual_mode_active and network_source:
    # Dual mode: Use network_source parameter
    if network_source == NetworkSource.MESHCORE:
        source = 'meshcore'  # ← MeshCore packets
    elif network_source == NetworkSource.MESHTASTIC:
        source = 'meshtastic'  # ← Meshtastic packets
        
elif globals().get('MESHCORE_ENABLED', False) and not self._dual_mode_active:
    # Single MeshCore mode: All packets are MeshCore
    source = 'meshcore'
    
elif self._is_tcp_mode():
    source = 'tcp'
    
elif CONNECTION_MODE == 'serial':
    source = 'local'  # ← Most common for non-dual mode

else:
    source = 'local' if is_from_our_interface else 'tigrog2'
```

## Expected Logging Behavior

### When Source IS 'meshcore' (Correct)

```
[DEBUG] 🔍 [SOURCE-DEBUG] Determining packet source:
[DEBUG]    _dual_mode_active=True
[DEBUG]    network_source=meshcore
[DEBUG] 🔍 [SOURCE-DEBUG] In dual mode, checking network_source
[DEBUG] 🔍 Source détectée: MeshCore (dual mode)
[INFO][MC] 🔗 MC DEBUG: Source détectée comme MeshCore (dual mode)
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'meshcore'

[INFO][MC] ================================================================================
[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN add_packet()
[INFO][MC] ================================================================================
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de NodeName abcde [direct] (SNR:12.5dB)
```

### When Source is NOT 'meshcore' (Problem)

```
[DEBUG] 🔍 [SOURCE-DEBUG] Determining packet source:
[DEBUG]    _dual_mode_active=False
[DEBUG]    network_source=None
[DEBUG]    MESHCORE_ENABLED=False
[DEBUG] 🔍 Source détectée: Serial/local mode
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'  ← NOT meshcore!

[DEBUG] 🔍 [PACKET-SOURCE] Non-MeshCore packet: source='local'
[DEBUG][MT] 📦 TEXT_MESSAGE_APP de NodeName abcde [direct] (SNR:12.5dB)
```

## Diagnostic Commands

### 1. Check Current Source Assignment

```bash
journalctl -u meshbot -f | grep "SOURCE-DEBUG"
```

Look for lines like:
```
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'xxx'
```

If it shows anything other than `'meshcore'`, that's the problem.

### 2. Check Network Source Parameter

```bash
journalctl -u meshbot -f | grep "network_source"
```

Look for:
```
[DEBUG]    network_source=meshcore (type=str)
```

If it shows `network_source=None` or something else, the network_source parameter is not being set correctly.

### 3. Check Mode Configuration

```bash
journalctl -u meshbot -f | grep "dual_mode_active\|MESHCORE_ENABLED"
```

Look for:
```
[DEBUG]    _dual_mode_active=True
[DEBUG]    MESHCORE_ENABLED=True
```

### 4. Check All MeshCore Logs

```bash
journalctl -u meshbot -f | grep '\[MC\]'
```

Should show:
- `[INFO][MC]` - Always visible MeshCore logs
- `[DEBUG][MC]` - DEBUG mode MeshCore logs

## Common Scenarios

### Scenario 1: Dual Mode Not Active

**Symptom:**
```
[DEBUG]    _dual_mode_active=False
[DEBUG]    network_source=meshcore
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'
```

**Cause:** Dual mode is disabled, so network_source parameter is ignored.

**Solution:** 
- Check config: `DUAL_NETWORK_MODE = True`
- Verify dual_interface_manager is initialized

### Scenario 2: network_source is None

**Symptom:**
```
[DEBUG]    _dual_mode_active=True
[DEBUG]    network_source=None
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'
```

**Cause:** network_source parameter is not being passed to on_message().

**Solution:**
- Check dual_interface_manager.py::on_meshcore_message()
- Verify it calls `self.message_callback(packet, interface, NetworkSource.MESHCORE)`

### Scenario 3: network_source is Wrong Value

**Symptom:**
```
[DEBUG]    network_source=Unknown (type=str)
[DEBUG] 🔍 Source détectée: Unknown (Unknown)
```

**Cause:** network_source has unexpected value (not 'meshcore' or 'meshtastic').

**Solution:**
- Check NetworkSource class definition
- Verify NetworkSource.MESHCORE = 'meshcore' (lowercase)

### Scenario 4: Single MeshCore Mode

**Symptom:**
```
[DEBUG]    _dual_mode_active=False
[DEBUG]    MESHCORE_ENABLED=True
[DEBUG] 🔍 Source détectée: MeshCore (MESHCORE_ENABLED=True, single mode)
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'meshcore'
```

**Status:** ✅ This is correct for single MeshCore mode (no dual interface).

## Testing

Run the test suite to verify logging mechanism:

```bash
cd /home/runner/work/meshbot/meshbot
python3 test_meshcore_source_detection.py
```

Expected output:
```
✅ MeshCore source detected and logged with [DEBUG][MC] prefix
✅ Non-MeshCore source detected and logged with [DEBUG][MT] prefix
✅ All source detection scenarios pass
```

## Configuration Check

Check your config.py for:

```python
# Required for MeshCore packet logging
DEBUG_MODE = True

# For dual mode (both Meshtastic + MeshCore)
DUAL_NETWORK_MODE = True
MESHCORE_ENABLED = True

# For single MeshCore mode (MeshCore only)
MESHCORE_ENABLED = True
CONNECTION_MODE = 'serial'  # or wherever MeshCore is connected
```

## What to Report

If packets still not showing as MeshCore, provide:

1. **Source detection logs:**
   ```bash
   journalctl -u meshbot -n 100 | grep "SOURCE-DEBUG"
   ```

2. **Configuration:**
   ```bash
   grep -E "DUAL_NETWORK_MODE|MESHCORE_ENABLED|DEBUG_MODE" config.py
   ```

3. **Network source values:**
   ```bash
   journalctl -u meshbot -n 100 | grep "network_source="
   ```

4. **Actual packet logs:**
   ```bash
   journalctl -u meshbot -n 100 | grep "PACKET-SOURCE"
   ```

## Quick Fix Checklist

- [ ] Verify DEBUG_MODE = True in config.py
- [ ] Check if _dual_mode_active = True (for dual mode)
- [ ] Check if network_source parameter is 'meshcore' (not None)
- [ ] Verify NetworkSource.MESHCORE = 'meshcore' (lowercase)
- [ ] Check MESHCORE_ENABLED = True (for single mode)
- [ ] Review diagnostic logs with grep "SOURCE-DEBUG"

## Summary

The logging mechanism works correctly. If you're not seeing `[DEBUG][MC]` logs, the issue is that `source` is not being set to `'meshcore'`. Use the diagnostic commands above to determine why.
