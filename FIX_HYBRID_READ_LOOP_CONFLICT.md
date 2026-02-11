# Fix: Hybrid Interface Read Loop Conflict

**Date**: 2026-02-10
**Issue**: Bot receiving constant `UnicodeDecodeError` when MeshCore sends binary protocol data
**Status**: ✅ Fixed

---

## Problem Description

### Symptom

Bot was crashing repeatedly with errors like:

```
[ERROR] UnicodeDecodeError: 'utf-8' codec can't decode byte 0x88 in position 3: invalid start byte
[ERROR] ❌ [MESHCORE-BINARY] PROTOCOLE BINAIRE NON SUPPORTÉ!
[ERROR]    PROBLÈME: Données binaires MeshCore reçues mais non décodées
[ERROR]    TAILLE: 45 octets ignorés
[ERROR]    TOTAL REJETÉ: 17 packet(s)
[ERROR]    IMPACT: Pas de logs [DEBUG][MC], pas de réponse aux DM
```

### Root Cause

The `MeshCoreHybridInterface` was connecting **BOTH** interfaces simultaneously:

1. **MeshCoreSerialInterface** (serial) - Started read loop
2. **MeshCoreCLIWrapper** (CLI) - Started read loop

**Problem**: Both interfaces were trying to read from the same serial port at the same time!

```
Serial Port (/dev/ttyACM1)
    ↓
    ├─→ MeshCoreSerialInterface._read_loop() → Tries to decode as UTF-8 → ❌ Crashes
    └─→ MeshCoreCLIWrapper read loop → Handles binary protocol → ✅ Works
```

The serial interface's `_read_loop` tried to decode binary data as UTF-8 text, causing constant errors.

---

## Solution

### Implementation

Added `enable_read_loop` parameter to `MeshCoreSerialInterface`:

**File: `meshcore_serial_interface.py`**

```python
def __init__(self, port, baudrate=115200, enable_read_loop=True):
    """
    Args:
        enable_read_loop: Si False, ne démarre pas le read loop (utile en mode hybride)
    """
    self.enable_read_loop = enable_read_loop
    # ...

def start_reading(self):
    """Démarre la lecture en arrière-plan des messages MeshCore"""
    # Check if read loop is disabled (hybrid mode with CLI wrapper)
    if not self.enable_read_loop:
        info_print("🔧 [MESHCORE-SERIAL] Read loop disabled (hybrid mode)")
        info_print("   Usage: SEND ONLY (broadcasts via binary protocol)")
        info_print("   Receiving: Handled by MeshCoreCLIWrapper")
        return True
    
    # Normal read loop startup...
```

**File: `main_bot.py`**

Updated `MeshCoreHybridInterface` to disable serial read loop when CLI is available:

```python
def __init__(self, port, baudrate=115200):
    # Check if CLI wrapper will be available
    will_use_cli_wrapper = MESHCORE_CLI_AVAILABLE and MeshCoreCLIWrapper
    
    # Disable read loop if CLI wrapper available (avoids conflicts)
    self.serial_interface = MeshCoreSerialBase(
        port, 
        baudrate, 
        enable_read_loop=not will_use_cli_wrapper  # ← Key change
    )
    
    if will_use_cli_wrapper:
        self.cli_wrapper = MeshCoreCLIWrapper(port, baudrate)
        # CLI handles ALL receiving
```

### Architecture After Fix

```
Serial Port (/dev/ttyACM1)
    ↓
    ├─→ MeshCoreSerialInterface (SEND ONLY)
    │   └─→ sendText() for broadcasts (binary protocol)
    │
    └─→ MeshCoreCLIWrapper (RECEIVE + SEND)
        └─→ Handles ALL incoming binary data
        └─→ Handles DM encryption/decryption
        └─→ Generates [DEBUG][MC] logs
```

**Result:** No conflicts, no UTF-8 errors!

---

## Changes Made

### Files Modified

1. **`meshcore_serial_interface.py`**
   - Added `enable_read_loop` parameter to `__init__()`
   - Updated `start_reading()` to skip read loop when disabled
   - Added diagnostic messages

2. **`main_bot.py`**
   - Updated `MeshCoreHybridInterface.__init__()`
   - Passes `enable_read_loop=False` when CLI wrapper available
   - Fallback: Re-enables read loop if CLI init fails

3. **`tests/test_hybrid_read_loop_fix.py`** (NEW)
   - Tests read loop control
   - Tests hybrid interface behavior
   - Tests fallback scenario

---

## Test Results

```bash
$ python tests/test_hybrid_read_loop_fix.py

================================================================================
Testing MeshCore Hybrid Interface Read Loop Fix
================================================================================

test_hybrid_interface_disables_serial_read_loop (__main__.TestHybridReadLoopFix)
Test that hybrid interface disables serial read loop when CLI available ... ok

test_hybrid_interface_enables_serial_read_loop_when_cli_fails (__main__.TestHybridReadLoopFix)
Test that serial read loop is re-enabled if CLI wrapper fails to initialize ... ok

test_serial_interface_read_loop_disabled_when_cli_available (__main__.TestHybridReadLoopFix)
Test that serial interface read loop is disabled when CLI wrapper is available ... ok

test_serial_interface_read_loop_enabled_by_default (__main__.TestHybridReadLoopFix)
Test that serial interface read loop is enabled by default ... ok

test_start_reading_skips_when_read_loop_disabled (__main__.TestHybridReadLoopFix)
Test that start_reading() returns early when read loop is disabled ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.002s

OK

✅ ALL TESTS PASSED
```

---

## Expected Behavior After Fix

### Startup Logs

```
[INFO][MC] ✅ MESHCORE: Using HYBRID mode (BEST OF BOTH)
[INFO][MC]    ✅ MeshCoreSerialInterface for broadcasts (binary protocol)
[INFO][MC]    ✅ MeshCoreCLIWrapper for DM messages (meshcore-cli API)
[DEBUG] ✅ Hybrid interface: Both serial and CLI wrappers initialized
[DEBUG]    Serial interface: SEND ONLY (read loop disabled)
[DEBUG]    CLI wrapper: RECEIVE + DM handling
[INFO] ✅ [MESHCORE] Connexion série établie: /dev/ttyACM1
[INFO] 🔧 [MESHCORE-SERIAL] Read loop disabled (hybrid mode)
[INFO]    Usage: SEND ONLY (broadcasts via binary protocol)
[INFO]    Receiving: Handled by MeshCoreCLIWrapper
[INFO][MC] ✅ MeshCore connection successful
```

### Runtime Behavior

**Before Fix:**
```
❌ UnicodeDecodeError: 'utf-8' codec can't decode byte 0x88
❌ 17 packets rejected
❌ No [DEBUG][MC] logs
❌ No DM responses
```

**After Fix:**
```
✅ No UnicodeDecodeError
✅ All packets processed by CLI wrapper
✅ [DEBUG][MC] logs appear correctly
✅ DM messages work
✅ Broadcasts work via serial interface
```

---

## Benefits

1. ✅ **No More Crashes**: UnicodeDecodeError eliminated
2. ✅ **Clean Separation**: Serial for sending, CLI for receiving
3. ✅ **Binary Protocol Support**: CLI handles all incoming binary data
4. ✅ **DM Support**: Full encryption/decryption via CLI
5. ✅ **Broadcast Support**: Binary protocol via serial interface
6. ✅ **Graceful Fallback**: Re-enables serial read loop if CLI fails

---

## Backward Compatibility

✅ **Fully Compatible**

- Default behavior unchanged (`enable_read_loop=True` by default)
- Only affects hybrid mode with CLI wrapper
- Fallback to serial-only if CLI unavailable
- No API changes

---

## Alternative Approaches Considered

### ❌ Option 1: Modify CLI wrapper to not start read loop
**Rejected**: Would require changes to external meshcore-cli library

### ❌ Option 2: Use separate serial ports
**Rejected**: Both interfaces need same physical port for sending/receiving

### ✅ Option 3: Disable serial read loop (CHOSEN)
**Advantages**:
- Minimal code changes
- Clear separation of responsibilities
- Works with existing CLI wrapper
- Backward compatible

---

## Deployment

### Steps

1. Pull latest from branch
2. Restart bot: `sudo systemctl restart meshtastic-bot`
3. Verify no UnicodeDecodeError in logs
4. Verify [DEBUG][MC] logs appear

### Verification

Check logs for:
```
✅ [MESHCORE-SERIAL] Read loop disabled (hybrid mode)
✅ No UnicodeDecodeError messages
✅ [DEBUG][MC] logs from CLI wrapper
```

### Success Criteria

- ✅ Bot starts without errors
- ✅ No UnicodeDecodeError in logs
- ✅ `/echo` command works on public channel
- ✅ DM messages processed correctly
- ✅ [DEBUG][MC] logs visible

---

## Summary

**Problem**: Both serial and CLI interfaces reading from same port → conflicts and UTF-8 errors

**Solution**: Disable serial read loop in hybrid mode → CLI handles all receiving

**Result**: Clean, conflict-free operation with full binary protocol support

This fix completes the hybrid interface implementation and resolves the last remaining issue with MeshCore integration.
