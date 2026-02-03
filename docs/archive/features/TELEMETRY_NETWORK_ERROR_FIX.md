# ESPHome Telemetry Network Error Handling Fix

**Date**: 2025-11-20
**Issue**: BrokenPipeError spam in logs during telemetry broadcast
**Fix**: Graceful handling of network errors in telemetry transmission

---

## Problem Statement

When the bot attempts to broadcast ESPHome telemetry data and the TCP connection to the mesh node is temporarily broken, a `BrokenPipeError` is raised and logged with a full traceback:

```
Nov 20 14:53:04 DietPi meshtastic-bot[1166277]: [ERROR] 14:53:04 - Erreur envoi télémétrie ESPHome: [Errno 32] Broken pipe
Nov 20 14:53:04 DietPi meshtastic-bot[1166277]: [ERROR] Traceback complet:
Nov 20 14:53:04 DietPi meshtastic-bot[1166277]: Traceback (most recent call last):
  File "/home/dietpi/bot/main_bot.py", line 541, in send_esphome_telemetry
    self.interface.sendData(
    ~~~~~~~~~~~~~~~~~~~~~~~^
        env_telemetry,
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        wantResponse=False
        ^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/dist-packages/meshtastic/mesh_interface.py", line 573, in sendData
    p = self._sendPacket(meshPacket, destinationId, wantAck=wantAck, hopLimit=hopLimit, pkiEncrypted=pkiEncrypted, publicKey=publicKey)
  File "/usr/local/lib/python3.13/dist-packages/meshtastic/mesh_interface.py", line 1011, in _sendPacket
    self._sendToRadio(toRadio)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "/usr/local/lib/python3.13/dist-packages/meshtastic/mesh_interface.py", line 1242, in _sendToRadio
    self._sendToRadioImpl(packet)
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/dist-packages/meshtastic/stream_interface.py", line 129, in _sendToRadioImpl
    self._writeBytes(header + b)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/dist-packages/meshtastic/tcp_interface.py", line 94, in _writeBytes
    self.socket.send(b)
    ~~~~~~~~~~~~~~~~^^^
BrokenPipeError: [Errno 32] Broken pipe
```

**Impact**:
- Log spam (15+ lines per error, every telemetry broadcast attempt during network issues)
- Makes debugging other issues difficult
- Appears as critical errors but is actually a normal network condition
- No functional impact (bot continues working after reconnection)

---

## Root Cause Analysis

### Why BrokenPipeError Occurs

1. **ESPHome Telemetry Broadcast**: The bot periodically broadcasts telemetry data (default: every 3600 seconds)
2. **TCP Connection**: Uses TCP interface to connect to mesh node (e.g., tigrog2 at 192.168.1.38)
3. **Network Instability**: The remote mesh node may disconnect, restart, or lose connectivity
4. **Direct sendData() Call**: `send_esphome_telemetry()` calls `self.interface.sendData()` directly
5. **Unhandled Network Error**: When connection is broken, `sendData()` raises `BrokenPipeError`
6. **Generic Exception Handler**: The outer try-except catches all exceptions and logs full traceback

### Why Existing Threading Filter Doesn't Help

The threading exception filter in `tcp_interface_patch.py` only applies to:
- Meshtastic library's internal threads (heartbeat, reader threads)
- Threads named `Thread-*`, `MainThread`, or `Dummy-*`

But `send_esphome_telemetry()` runs in the bot's **periodic cleanup thread**, which is NOT filtered by the threading hook. Therefore, the BrokenPipeError is caught by the method's own try-except block and logged.

---

## Solution

### Design Principles

1. **Network errors are normal** - Connections drop, nodes restart, networks fail
2. **Fail gracefully** - Don't spam logs with expected network errors
3. **Auto-reconnect** - Let the interface reconnect automatically on next use
4. **Preserve debugging** - Still log unexpected errors fully

### Implementation

#### New Helper Method: `_send_telemetry_packet()`

```python
def _send_telemetry_packet(self, telemetry_data, packet_type):
    """
    Envoyer un paquet de télémétrie avec gestion robuste des erreurs réseau
    
    Args:
        telemetry_data: Données de télémétrie (protobuf Telemetry)
        packet_type: Type de paquet pour les logs ("environment_metrics" ou "device_metrics")
    
    Returns:
        bool: True si envoyé avec succès, False sinon
    """
    try:
        info_print(f"📡 Envoi télémétrie ESPHome ({packet_type})...")
        self.interface.sendData(
            telemetry_data,
            destinationId=0xFFFFFFFF,  # Broadcast
            portNum=portnums_pb2.PortNum.TELEMETRY_APP,
            wantResponse=False
        )
        info_print(f"✅ Télémétrie {packet_type} envoyée")
        return True
        
    except BrokenPipeError as e:
        # Erreur réseau normale - connexion TCP temporairement cassée
        # L'interface se reconnectera automatiquement au prochain usage
        debug_print(f"⚠️ Connexion réseau perdue lors de l'envoi télémétrie ({packet_type}): {e}")
        debug_print("L'interface se reconnectera automatiquement au prochain usage")
        return False
        
    except (ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError) as e:
        # Autres erreurs réseau normales
        debug_print(f"⚠️ Erreur réseau lors de l'envoi télémétrie ({packet_type}): {e}")
        debug_print("L'interface se reconnectera automatiquement au prochain usage")
        return False
        
    except Exception as e:
        # Erreurs inattendues - logger complètement pour debug
        error_print(f"❌ Erreur inattendue lors de l'envoi télémétrie ({packet_type}): {e}")
        error_print(traceback.format_exc())
        return False
```

#### Modified `send_esphome_telemetry()`

```python
# Before (direct sendData call)
if has_env_data:
    info_print("📡 Envoi télémétrie ESPHome (environment_metrics)...")
    self.interface.sendData(
        env_telemetry,
        destinationId=0xFFFFFFFF,
        portNum=portnums_pb2.PortNum.TELEMETRY_APP,
        wantResponse=False
    )
    packets_sent += 1
    info_print("✅ Télémétrie environment_metrics envoyée")

# After (with error handling)
if has_env_data:
    if self._send_telemetry_packet(env_telemetry, "environment_metrics"):
        packets_sent += 1
        time.sleep(0.5)
```

### Error Handling Strategy

| Error Type | Handling | Logging |
|-----------|----------|---------|
| `BrokenPipeError` | Return False, skip packet | Debug-level concise message |
| `ConnectionResetError` | Return False, skip packet | Debug-level concise message |
| `ConnectionRefusedError` | Return False, skip packet | Debug-level concise message |
| `ConnectionAbortedError` | Return False, skip packet | Debug-level concise message |
| Other exceptions | Return False, skip packet | Error-level with full traceback |

### Benefits

1. **No log spam** - Network errors logged at debug level (1 line instead of 15+)
2. **Graceful degradation** - Skips failed packets, continues with others
3. **Auto-recovery** - Interface reconnects automatically on next sendData()
4. **Debugging preserved** - Unexpected errors still get full traceback
5. **Clear intent** - Separate method makes error handling explicit

---

## Testing

### Test Suite: `test_telemetry_network_errors.py`

Three comprehensive tests verify the fix:

#### Test 1: BrokenPipeError Handling
```python
def test_broken_pipe_error_handling():
    """Test que BrokenPipeError est géré gracieusement"""
```
**Verifies**:
- BrokenPipeError caught and handled
- Only debug_print called (not error_print)
- No full traceback logged
- Network error message logged in debug

**Result**: ✅ PASS

#### Test 2: Other Network Errors
```python
def test_other_network_errors():
    """Test que les autres erreurs réseau sont aussi gérées"""
```
**Verifies**:
- ConnectionResetError handled gracefully
- ConnectionRefusedError handled gracefully
- ConnectionAbortedError handled gracefully
- No tracebacks for any network error

**Result**: ✅ PASS

#### Test 3: Unexpected Errors Still Logged
```python
def test_unexpected_errors_still_logged():
    """Test que les erreurs non-réseau sont toujours loggées complètement"""
```
**Verifies**:
- ValueError (non-network error) logged with traceback
- error_print called for unexpected errors
- Full debugging information preserved

**Result**: ✅ PASS

### Regression Testing

All existing tests continue to pass:

```bash
$ python3 test_esphome_telemetry.py
✅ Test 1 réussi: Valeurs correctes et pression convertie en Pa
✅ Test 2 réussi: 2 paquets télémétrie envoyés séparément (conforme au standard)
✅ Test 3 réussi: Gestion capteurs manquants
✅ Test 4 réussi: Gestion données partielles
✅ TOUS LES TESTS RÉUSSIS
```

---

## Behavior Comparison

### Before Fix

**Normal mode** (DEBUG_MODE=False):
```
[ERROR] 14:53:04 - Erreur envoi télémétrie ESPHome: [Errno 32] Broken pipe
[ERROR] Traceback complet:
Traceback (most recent call last):
  File "/home/dietpi/bot/main_bot.py", line 541, in send_esphome_telemetry
    self.interface.sendData(
    ... (15+ lines) ...
BrokenPipeError: [Errno 32] Broken pipe
```

**Impact**: 15+ lines of error logs every telemetry broadcast during network issues

### After Fix

**Normal mode** (DEBUG_MODE=False):
```
# Silent - no error logs
```

**Debug mode** (DEBUG_MODE=True):
```
[DEBUG] ⚠️ Connexion réseau perdue lors de l'envoi télémétrie (environment_metrics): [Errno 32] Broken pipe
[DEBUG] L'interface se reconnectera automatiquement au prochain usage
```

**Impact**: 2 concise debug lines, only visible when debugging

---

## Files Modified

### Core Implementation
- **`main_bot.py`**
  - Added `_send_telemetry_packet()` method (~30 lines)
  - Modified `send_esphome_telemetry()` to use new method
  - Changed sensor value logging to debug level
  - Total changes: ~60 lines

### Test Suite
- **`test_telemetry_network_errors.py`** (NEW)
  - 3 comprehensive test scenarios
  - ~450 lines of test code
  - Tests all error handling paths

### Documentation
- **`TELEMETRY_NETWORK_ERROR_FIX.md`** (THIS FILE)
  - Complete fix documentation
  - Design rationale
  - Testing results

---

## Deployment Considerations

### Backward Compatibility
- ✅ No breaking changes
- ✅ No API changes
- ✅ No configuration changes required
- ✅ All existing functionality preserved

### Configuration
No configuration changes needed. Respects existing `DEBUG_MODE` setting:
- `DEBUG_MODE=False` (production): Silent network error handling
- `DEBUG_MODE=True` (development): Verbose debug logging

### Monitoring
After deployment, monitor logs for:
- ✅ Absence of BrokenPipeError tracebacks (success indicator)
- ⚠️ Frequent network errors in DEBUG mode (may indicate network issues)
- ℹ️ Successful telemetry broadcasts continue as normal

### Rollback Plan
If issues arise:
1. Revert `main_bot.py` to previous version
2. No configuration changes needed
3. Restart bot service

---

## Related Issues & Documentation

- **BROKENPIPE_FIX.md**: TCP interface heartbeat BrokenPipeError fix (different issue)
- **ESPHOME_TELEMETRY_FIX.md**: Protobuf oneof constraint fix (separate packets)
- **ESPHOME_TELEMETRY.md**: General ESPHome telemetry documentation
- **tcp_interface_patch.py**: Threading exception filter for Meshtastic library threads

---

## Security Analysis

✅ **CodeQL Security Check**: No security issues detected

**Analysis**:
- No new attack vectors introduced
- Only catches and silences expected network errors
- No data leakage or information exposure
- Maintains existing security posture
- Proper exception hierarchy (specific before general)

---

## Conclusion

This fix demonstrates proper error handling for network operations:

### Key Principles Applied

1. **Distinguish Expected from Unexpected**
   - Network errors are expected → debug logging
   - Other errors are unexpected → full error logging

2. **Fail Gracefully**
   - Skip failed packet transmission
   - Continue with remaining packets
   - Let interface auto-reconnect

3. **Preserve Debugging**
   - Network errors: concise debug messages
   - Unexpected errors: full traceback
   - Clear distinction in logging

4. **Test Thoroughly**
   - Test expected errors (network)
   - Test unexpected errors (other)
   - Verify no regressions

### Best Practices Demonstrated

```python
# ✅ GOOD: Specific exception handling
try:
    risky_network_operation()
except BrokenPipeError:
    debug_print("Network error (expected)")
except Exception as e:
    error_print(f"Unexpected error: {e}")
    error_print(traceback.format_exc())

# ❌ BAD: Generic exception handling
try:
    risky_network_operation()
except Exception as e:
    error_print(f"Error: {e}")  # Can't distinguish expected from unexpected
    error_print(traceback.format_exc())  # Logs everything
```

### Impact Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Log lines per network error | 15+ | 0 (normal) / 2 (debug) | 7.5x - ∞ reduction |
| Log noise | High | Minimal | Significantly improved |
| Debugging clarity | Obscured by spam | Clear | Much better |
| Network resilience | Good | Good | Maintained |
| Error visibility | Too much | Appropriate | Balanced |

---

**Date**: 2025-11-20  
**Issue**: BrokenPipeError spam in telemetry logs  
**Commit**: a4c283c  
**Files Modified**: 2 (main_bot.py, test_telemetry_network_errors.py)  
**Tests**: 3 new tests, all existing tests pass  
**Impact**: Cleaner logs, maintained functionality  
**Security**: No issues detected
