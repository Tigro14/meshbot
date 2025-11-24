# Fix Summary: TCP Reconnection AttributeError

## Problem Description

The bot was experiencing crashes during TCP reconnection with the following error:

```
Nov 24 14:51:36 DietPi meshtastic-bot[1446295]: [ERROR] 14:51:36 - ❌ Échec reconnexion TCP: 'MeshBot' object has no attribute 'mesh_traceroute_manager'
Nov 24 14:51:36 DietPi meshtastic-bot[1446295]: [ERROR] Traceback complet:
Nov 24 14:51:36 DietPi meshtastic-bot[1446295]: Traceback (most recent call last):
Nov 24 14:51:36 DietPi meshtastic-bot[1446295]:   File "/home/dietpi/bot/main_bot.py", line 506, in _reconnect_tcp_interface
Nov 24 14:51:36 DietPi meshtastic-bot[1446295]:     if self.mesh_traceroute_manager:
Nov 24 14:51:36 DietPi meshtastic-bot[1446295]:        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Nov 24 14:51:36 DietPi meshtastic-bot[1446295]: AttributeError: 'MeshBot' object has no attribute 'mesh_traceroute_manager'
```

## Root Cause

In the `_reconnect_tcp_interface()` method at line 506-507 of `main_bot.py`, the code was using an incorrect attribute name:

**INCORRECT:**
```python
if self.mesh_traceroute_manager:
    self.mesh_traceroute_manager.interface = self.interface
```

However, throughout the rest of the codebase, the attribute is consistently named `self.mesh_traceroute`:

```python
# Line 79: Initialization
self.mesh_traceroute = None

# Line 301-303: Usage in on_message
if self.mesh_traceroute:
    handled = self.mesh_traceroute.handle_traceroute_response(packet)

# Line 608-610: Usage in cleanup_cache
if self.mesh_traceroute:
    self.mesh_traceroute.cleanup_expired_traces()

# Line 952-958: Initialization in start()
self.mesh_traceroute = MeshTracerouteManager(...)
self.message_handler.router.mesh_traceroute = self.mesh_traceroute
self.message_handler.router.network_handler.mesh_traceroute = self.mesh_traceroute
```

## Solution

Changed lines 506-507 in `main_bot.py` to use the correct attribute name:

**CORRECT:**
```python
if self.mesh_traceroute:
    self.mesh_traceroute.interface = self.interface
```

## Impact

- **Minimal Change**: Only 1 line changed (the conditional and assignment)
- **Fixes Crash**: TCP reconnection no longer fails with AttributeError
- **Consistency**: Now consistent with all other usages of `mesh_traceroute` in the codebase
- **No Breaking Changes**: No impact on existing functionality

## Testing

Created `test_tcp_reconnection_fix.py` to verify:
1. `mesh_traceroute_manager` is no longer used in `_reconnect_tcp_interface()`
2. `mesh_traceroute` is correctly used instead
3. The interface update logic is correct
4. Consistency across the entire codebase (10 usages of `self.mesh_traceroute`, 0 usages of `self.mesh_traceroute_manager`)

All tests pass:
```
✅ mesh_traceroute_manager n'est plus utilisé dans _reconnect_tcp_interface
✅ mesh_traceroute est correctement utilisé
✅ mesh_traceroute.interface est correctement mis à jour
✅ self.mesh_traceroute utilisé 10 fois (consistent throughout codebase)
✅ self.mesh_traceroute_manager n'est plus utilisé (0 occurrences)
```

## Note on Module Name vs Attribute Name

The **module** is still correctly named `mesh_traceroute_manager.py` and the class `MeshTracerouteManager`:
```python
from mesh_traceroute_manager import MeshTracerouteManager
```

The fix was only for the **instance attribute** in the `MeshBot` class, which should be `self.mesh_traceroute`, not `self.mesh_traceroute_manager`.

## Files Modified

1. `main_bot.py` - Line 506-507 (TCP reconnection interface update)
2. `test_tcp_reconnection_fix.py` - New test to verify the fix

## Verification

The fix has been verified through:
1. Code review and consistency check across the codebase
2. Syntax validation of `main_bot.py`
3. Existing tests still pass (`test_traceroute_brokenpipe.py`)
4. New test passes (`test_tcp_reconnection_fix.py`)
