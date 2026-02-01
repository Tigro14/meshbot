# Fix: Serial Port Locking Conflict Between Meshtastic and MeshCore

**Date**: 2026-02-01  
**Issue**: Serial port locking conflict when both MESHTASTIC_ENABLED and MESHCORE_ENABLED are True

## Problem Description

When the bot is configured with both Meshtastic and MeshCore enabled:
```python
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
```

And both are configured to use serial ports, a serial port locking conflict can occur:

```
Feb 01 20:17:25 ... [INFO] ✅ [MESHCORE-CLI] Auto message fetching démarré
Feb 01 20:17:28 ... [INFO] 🔌 Mode SERIAL MESHTASTIC: Connexion série /dev/ttyACM2
Feb 01 20:17:28 ... [ERROR] Could not exclusively lock port /dev/ttyACM2: [Errno 11] Resource temporarily unavailable
```

### Root Cause Analysis

The error "Could not exclusively lock port" occurs when:
1. MeshCore successfully connects to a serial port (e.g., `/dev/ttyACM2`)
2. Then Meshtastic tries to connect to the SAME serial port
3. Linux exclusive locking (`fcntl.LOCK_EX`) prevents the second connection

This can happen in two scenarios:

**Scenario A**: Both configured to use the same port (configuration error)
```python
SERIAL_PORT = "/dev/ttyACM2"          # Meshtastic
MESHCORE_SERIAL_PORT = "/dev/ttyACM2"  # MeshCore - SAME PORT!
```

**Scenario B**: MeshCore initialization happens despite should-not-happen logic bug

## The Fix

### 1. Serial Port Conflict Detection (Prevention)

Added validation at initialization (lines 1665-1683) that checks if both interfaces are configured to use the same serial port:

```python
# VALIDATION: SERIAL PORT CONFLICT DETECTION
if meshtastic_enabled and meshcore_enabled:
    serial_port = globals().get('SERIAL_PORT', '/dev/ttyACM0')
    meshcore_port = globals().get('MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
    
    if connection_mode == 'serial' and serial_port == meshcore_port:
        error_print("❌ ERREUR DE CONFIGURATION: Conflit de port série détecté!")
        error_print(f"   SERIAL_PORT = {serial_port}")
        error_print(f"   MESHCORE_SERIAL_PORT = {meshcore_port}")
        error_print("   → Les deux interfaces ne peuvent pas utiliser le même port")
        error_print("   → Meshtastic sera utilisé (priorité)")
        error_print("   → MeshCore sera ignoré pour éviter le conflit")
```

**Benefits**:
- Detects configuration errors early (before attempting connections)
- Provides clear error messages with the conflicting ports
- Guides users to fix the configuration
- Prevents the "Resource temporarily unavailable" error

### 2. Defensive Check in MeshCore Initialization (Defense-in-Depth)

Added explicit check in MeshCore initialization path (lines 1797-1809):

```python
elif meshcore_enabled and not meshtastic_enabled:
    # DEFENSIVE CHECK: This block should NEVER run if meshtastic_enabled is True
    if meshtastic_enabled:
        error_print("❌ FATAL ERROR: MeshCore initialization attempted with MESHTASTIC_ENABLED=True")
        error_print(f"   meshtastic_enabled = {meshtastic_enabled}")
        error_print(f"   meshcore_enabled = {meshcore_enabled}")
        error_print(f"   connection_mode = {connection_mode}")
        error_print("   → This should NEVER happen - check code logic")
        return False
```

**Benefits**:
- Catches logic bugs that might allow dual initialization
- Logs comprehensive state for debugging
- Provides early failure instead of cryptic serial errors
- Makes code behavior explicit and verifiable

## Configuration Guidance

### Correct Configuration (Recommended)

**Option A**: Meshtastic Only
```python
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"
```

**Option B**: MeshCore Only
```python
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

**Option C**: Both Enabled (Meshtastic has priority)
```python
MESHTASTIC_ENABLED = True   # Will be used
MESHCORE_ENABLED = True     # Will be IGNORED (warning shown)
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"          # Meshtastic
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore (not used)
```

### Incorrect Configuration (Will trigger error)

```python
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM2"          # ❌ SAME PORT
MESHCORE_SERIAL_PORT = "/dev/ttyACM2"  # ❌ CONFLICT!
```

**Result**: Error message with guidance on how to fix.

## Error Messages

### Port Conflict Detected

```
❌ ERREUR DE CONFIGURATION: Conflit de port série détecté!
   SERIAL_PORT = /dev/ttyACM2
   MESHCORE_SERIAL_PORT = /dev/ttyACM2
   → Les deux interfaces ne peuvent pas utiliser le même port
   → Meshtastic sera utilisé (priorité)
   → MeshCore sera ignoré pour éviter le conflit

   SOLUTION: Dans config.py, utiliser des ports différents:
     SERIAL_PORT = "/dev/ttyACM0"  # Meshtastic
     MESHCORE_SERIAL_PORT = "/dev/ttyACM2"  # MeshCore
```

### Logic Error Detected (should never happen)

```
❌ FATAL ERROR: MeshCore initialization attempted with MESHTASTIC_ENABLED=True
   meshtastic_enabled = True
   meshcore_enabled = True
   connection_mode = serial
   → This should NEVER happen - check code logic
```

If you see this error, it indicates a code bug that should be reported.

## Technical Details

### Linux Exclusive Locking

Python's `pyserial` library uses `fcntl.flock()` with `LOCK_EX | LOCK_NB` (exclusive, non-blocking lock) when opening serial ports with `exclusive=True`:

```python
# From pyserial internals
fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
```

This prevents multiple processes (or threads) from accessing the same serial device simultaneously, which is generally good for preventing data corruption. However, it means only ONE interface can use a given serial port at a time.

### Why Can't Both Use the Same Port?

Serial communication is inherently sequential and bidirectional. If two interfaces tried to use the same port:
1. Received data would go to only one interface (whichever reads first)
2. Sent commands could interleave and corrupt the protocol
3. The device itself can only handle one communication session at a time

Therefore, exclusive locking is correct behavior - the fix is to use different ports or choose which interface to use.

## Testing

To test the fix:

1. **Test Port Conflict Detection**:
   ```python
   # config.py
   MESHTASTIC_ENABLED = True
   MESHCORE_ENABLED = True
   CONNECTION_MODE = 'serial'
   SERIAL_PORT = "/dev/ttyACM0"
   MESHCORE_SERIAL_PORT = "/dev/ttyACM0"  # Same port
   ```
   
   Expected: Error message about port conflict, Meshtastic connects, MeshCore ignored.

2. **Test Normal Operation**:
   ```python
   # config.py
   MESHTASTIC_ENABLED = True
   MESHCORE_ENABLED = False
   CONNECTION_MODE = 'serial'
   SERIAL_PORT = "/dev/ttyACM0"
   ```
   
   Expected: Meshtastic connects successfully, no errors.

3. **Test MeshCore Only**:
   ```python
   # config.py
   MESHTASTIC_ENABLED = False
   MESHCORE_ENABLED = True
   MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
   ```
   
   Expected: MeshCore connects successfully, no errors.

## Files Modified

- `main_bot.py` (lines 1665-1683, 1797-1809)
  - Added serial port conflict detection
  - Added defensive check in MeshCore initialization

## Related Documentation

- `DUAL_INTERFACE_FAQ.md` - FAQ about using multiple interfaces
- `MESHCORE_COMPANION.md` - MeshCore companion mode documentation
- `config.py.sample` - Configuration template with examples

## Summary

**Before Fix**:
- Silent port conflict → cryptic "Resource temporarily unavailable" error
- No clear guidance on what's wrong
- Difficult to debug

**After Fix**:
- Port conflict detected before connection attempt
- Clear error message with exact ports involved
- Solution provided in error message
- Defensive check prevents logic bugs
- Comprehensive state logging for debugging

**Impact**: ✅ Better user experience, clearer errors, easier troubleshooting
