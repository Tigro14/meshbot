# Fix: Telemetry Broadcast for MeshCore Interface

**Date:** 2026-01-20  
**Issue:** AttributeError when sending telemetry with MeshCoreCLIWrapper

## Problem

The bot crashed when attempting to send ESPHome telemetry over a MeshCore interface:

```
AttributeError: 'MeshCoreCLIWrapper' object has no attribute 'sendData'
```

Error occurred in `main_bot.py` at line 1327 in `_send_telemetry_packet()` method.

## Root Cause

The MeshBot supports two types of interfaces:
1. **Standard Meshtastic interfaces** (SerialInterface, TCPInterface) - have `sendData()` method
2. **MeshCoreCLIWrapper** (MeshCore companion mode) - only has `sendText()` method, no `sendData()`

The `_send_telemetry_packet()` method unconditionally called `self.interface.sendData()`, which doesn't exist on MeshCoreCLIWrapper.

## Solution

Added interface capability check before attempting to send telemetry:

```python
def _send_telemetry_packet(self, telemetry_data, packet_type):
    # Check if interface supports sendData() (MeshCoreCLIWrapper doesn't have this method)
    if not hasattr(self.interface, 'sendData'):
        debug_print(f"⚠️ Interface type {type(self.interface).__name__} ne supporte pas sendData()")
        debug_print("   Télémétrie broadcast désactivée pour ce type d'interface")
        return False
    
    try:
        info_print(f"📡 Envoi télémétrie ESPHome ({packet_type})...")
        self.interface.sendData(...)
        # ... rest of the code
```

## Changes Made

### File: `main_bot.py`
- **Line 1325-1329**: Added interface capability check
- **Location**: `_send_telemetry_packet()` method
- **Impact**: Telemetry broadcast now safely skipped for MeshCore interfaces

### File: `test_meshcore_telemetry_fix.py` (NEW)
- Comprehensive test suite for the fix
- Tests:
  1. MeshCoreCLIWrapper correctly skips telemetry without crash
  2. Standard interfaces continue to work normally
  3. Interface type detection works correctly

## Test Results

All tests pass successfully:

```
✅ Test réussi: Télémétrie correctement skippée pour MeshCoreCLIWrapper
✅ Test réussi: Télémétrie fonctionne pour interface standard
✅ Test réussi: Détection d'interface fonctionne
🎉 TOUS LES TESTS RÉUSSIS
```

## Behavior

### Before Fix
- ❌ Bot crashes with AttributeError when using MeshCore
- ❌ No telemetry sent (crash before attempt)

### After Fix
- ✅ No crash with MeshCore interfaces
- ✅ Debug message logged when telemetry is skipped
- ✅ Standard Meshtastic interfaces continue to work normally

## Configuration

Users can still control telemetry via `config.py`:

```python
ESPHOME_TELEMETRY_ENABLED = True  # Enable/disable telemetry broadcast
ESPHOME_TELEMETRY_INTERVAL = 3600  # Interval in seconds (1 hour)
```

When `ESPHOME_TELEMETRY_ENABLED = False`, telemetry is disabled for all interfaces.

When using MeshCore (even if enabled), telemetry is automatically skipped.

## Future Considerations

### Other sendData Usage

The following components also use `sendData()` and may need similar fixes if MeshCore support is required:

1. **mesh_traceroute_manager.py** (line 95)
   - Used for `/trace` command (TRACEROUTE_APP packets)
   - Currently would fail on MeshCore interfaces
   - Not critical as traceroute is a diagnostic feature

### Recommendation

If MeshCore support is needed for traceroute or other features using `sendData()`:
1. Apply similar capability check before calling `sendData()`
2. Provide appropriate fallback or error message
3. Consider implementing alternative methods for MeshCore

## Minimal Impact

This fix is surgical and minimal:
- **Only 5 lines added** to `main_bot.py`
- **No configuration changes** required
- **No breaking changes** to existing functionality
- **Backward compatible** with all interface types

## References

- Issue log: Jan 20 16:00:35 - AttributeError in telemetry send
- MeshCore library: https://github.com/meshtastic/python
- Related file: `meshcore_cli_wrapper.py`
