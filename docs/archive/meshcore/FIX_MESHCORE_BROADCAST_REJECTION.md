# Fix: MeshCore Broadcast Rejection

## Problem
The `/echo` command was failing when routing through MeshCore in dual mode with the error:
```
❌ [MESHCORE-DM] Async send error: Destination must be a public key string or contact object, got:
```

## Root Cause
When sending a broadcast message (destinationId=0xFFFFFFFF) via MeshCore CLI wrapper:
1. The `sendText()` method tried to send it as a DM (Direct Message)
2. MeshCore's `commands.send_msg()` API expects a contact object or public key string
3. Passing `0xFFFFFFFF` (broadcast address) as the contact parameter caused the error

## Solution
Updated `meshcore_cli_wrapper.py::sendText()` to:
1. Detect broadcast addresses (`destinationId is None or destinationId == 0xFFFFFFFF`)
2. Return `False` with clear error messages explaining the limitation
3. Prevent the invalid `send_msg()` call

## Changes Made

### File: `meshcore_cli_wrapper.py`
**Lines 1746-1756**: Added broadcast detection before attempting to send:

```python
# Detect if this is a broadcast/channel message
is_broadcast = (destinationId is None or destinationId == 0xFFFFFFFF)

if is_broadcast:
    # MeshCore CLI doesn't support channel broadcasts via send_msg API
    # The send_msg API only supports direct messages to specific contacts
    error_print("❌ [MESHCORE] Broadcast messages not supported via meshcore-cli")
    error_print("   → MeshCore CLI library only supports DM (Direct Messages)")
    error_print("   → Use meshcore_serial_interface.py for channel broadcast support")
    info_print_mc(f"⚠️  [MESHCORE] Tentative d'envoi broadcast ignorée (canal {channelIndex})")
    return False
```

### File: `tests/test_meshcore_broadcast_fix.py` (NEW)
Comprehensive test suite with 4 tests:
1. ✅ Broadcast detection (0xFFFFFFFF)
2. ✅ Broadcast detection (None)
3. ✅ DM messages still work
4. ✅ Channel-specific broadcasts rejected

## Impact
**Before Fix:**
- `/echo` command failed with cryptic async error
- MeshCore tried to send broadcast as DM
- Error occurred after fire-and-forget, making it hard to debug

**After Fix:**
- Clear error message immediately when broadcast is attempted
- Graceful degradation - returns False instead of crashing
- DM messages continue to work normally
- Error is logged before async call, making it easier to understand

## Limitation
MeshCore CLI wrapper (`meshcore_cli_wrapper.py`) **does not support broadcast messages**. This is a known limitation of the `meshcore-cli` library's API which only provides `send_msg()` for direct messages.

**Workaround**: Use `meshcore_serial_interface.py` which implements the full binary protocol and supports channel broadcasts via `CMD_SEND_CHANNEL_TXT_MSG`.

## Testing
All 4 tests pass successfully:
```
Ran 4 tests in 0.005s
OK
✅ ALL TESTS PASSED
```

## Related Files
- `meshcore_cli_wrapper.py` - Main fix
- `tests/test_meshcore_broadcast_fix.py` - Test suite
- `dual_interface_manager.py` - Calls sendText with broadcast
- `handlers/command_handlers/utility_commands.py` - Echo command handler
