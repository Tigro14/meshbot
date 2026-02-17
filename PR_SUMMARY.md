# Pull Request Summary: Fix /echo Command and Add Network-Specific Variants

## Problem Solved

The `/echo` command from Telegram had a critical issue: it required `REMOTE_NODE_HOST` to be configured in `config.py`, even when using a serial-attached node. The error message was:

```
❌ REMOTE_NODE_HOST non configuré dans config.py
```

This was because the code tried to create a new TCP connection instead of using the bot's existing serial interface.

## Solution Overview

Rewrote the Telegram echo commands to:
1. Use the bot's **shared interface** (serial or TCP) instead of creating new connections
2. Add **network-specific commands** (`/echomt`, `/echomc`) for dual mode
3. Remove dependency on `REMOTE_NODE_HOST` configuration

## Changes Made

### Files Modified (7 files, +1012 -85 lines)

1. **`telegram_bot/command_base.py`** (+2 lines)
   - Added `self.dual_interface` access to all Telegram commands
   
2. **`telegram_bot/commands/mesh_commands.py`** (+127 -85 lines)
   - Removed imports: `REMOTE_NODE_HOST`, `CONNECTION_MODE`
   - Removed logic that creates new TCP connections
   - Added `_send_echo_to_network()` helper method
   - Implemented 3 commands: `/echo`, `/echomt`, `/echomc`
   - All use shared interface via `self.interface`
   
3. **`telegram_integration.py`** (+2 lines)
   - Registered `/echomt` and `/echomc` command handlers
   
4. **`telegram_bot/commands/basic_commands.py`** (+4 -1 lines)
   - Updated help text to show new commands

### Files Added

5. **`ECHO_COMMANDS_UPDATE.md`** (+333 lines)
   - Complete documentation of changes
   - Usage examples for all configurations
   - Migration guide
   - Troubleshooting
   
6. **`demos/demo_echo_commands.py`** (+253 lines)
   - Interactive demo showing routing logic
   - Tests 5 scenarios (single/dual mode)
   - Validates all command variants
   
7. **`tests/test_echo_commands.py`** (+291 lines)
   - Unit tests for echo command logic
   - Validates interface usage
   - Tests dual mode routing

## New Commands

### `/echo <message>`
- **Before**: Required REMOTE_NODE_HOST, created new TCP connection
- **After**: Uses shared interface (serial or TCP), no extra config needed
- **Behavior**: Auto-detects network type (Meshtastic or MeshCore)

### `/echomt <message>` (NEW)
- Explicitly sends to Meshtastic network
- Useful in dual mode to force Meshtastic
- Returns error if Meshtastic not available

### `/echomc <message>` (NEW)
- Explicitly sends to MeshCore network
- Useful in dual mode to force MeshCore
- Returns error if MeshCore not available

## Technical Architecture

### Old Flow (BROKEN)
```
Telegram /echo → Check CONNECTION_MODE
  ├─ serial → Create NEW TCP connection → Requires REMOTE_NODE_HOST ❌
  └─ tcp    → Use shared interface ✅
```

### New Flow (FIXED)
```
Telegram /echo → Use shared interface (self.interface) ✅
  ├─ Detect interface type (Meshtastic vs MeshCore)
  ├─ In dual mode: Route via dual_interface if network_type specified
  └─ Send via appropriate method (with/without destinationId)
```

## Testing Results

### Demo Output
```bash
$ python3 demos/demo_echo_commands.py
```

**All 5 scenarios passed:**
1. ✅ Single mode Meshtastic - uses Meshtastic interface
2. ✅ Single mode MeshCore - uses MeshCore interface
3. ✅ Dual mode /echo - uses primary interface (Meshtastic)
4. ✅ Dual mode /echomt - forces Meshtastic network
5. ✅ Dual mode /echomc - forces MeshCore network

## Benefits

### For Users
✅ **No configuration needed** - Works out of the box with serial nodes
✅ **No more errors** - Removes REMOTE_NODE_HOST requirement
✅ **Network control** - Explicit targeting in dual mode

### For Developers  
✅ **Cleaner code** - Removed 85 lines of connection management
✅ **Better architecture** - Reuses existing interface
✅ **No conflicts** - Respects ESP32 single TCP connection limit

### For System
✅ **No new connections** - Uses shared bot interface
✅ **Lower resource usage** - No temporary TCP connections
✅ **More reliable** - No connection setup/teardown overhead

## Migration Impact

### Breaking Changes
**None!** Backward compatible with all existing configurations.

### New Requirements
**None!** Actually removes the REMOTE_NODE_HOST requirement.

### Configuration Changes
Optional: Users can now remove `REMOTE_NODE_HOST` if only using it for `/echo`.

## Use Cases

### Use Case 1: Serial-only Meshtastic
```python
# config.py
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"
# REMOTE_NODE_HOST not needed anymore! ✅
```

**Result**: `/echo` works via serial connection

### Use Case 2: TCP-only Meshtastic
```python
# config.py
CONNECTION_MODE = 'tcp'
TCP_HOST = "192.168.1.38"
```

**Result**: `/echo` reuses bot's TCP connection (no second connection)

### Use Case 3: Dual Mode
```python
# config.py
DUAL_NETWORK_MODE = True
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
```

**Result**:
- `/echo` → Broadcasts on Meshtastic (primary)
- `/echomt` → Explicitly on Meshtastic
- `/echomc` → Explicitly on MeshCore

## Documentation

- **`ECHO_COMMANDS_UPDATE.md`** - Complete technical documentation
- **`demos/demo_echo_commands.py`** - Interactive demonstration
- **`tests/test_echo_commands.py`** - Unit tests

## Verification Checklist

- [x] Code compiles without errors
- [x] Demo runs successfully (5/5 scenarios pass)
- [x] No new dependencies added
- [x] Backward compatible
- [x] Documentation complete
- [x] Help text updated
- [x] Commands registered in Telegram integration

## Security Considerations

✅ **No new security issues**
✅ Uses existing bot authorization
✅ No new network connections
✅ Same broadcast permissions as before

## Performance Impact

✅ **Positive impact**:
- Faster execution (no connection setup)
- Lower memory usage (no temporary objects)
- More reliable (reuses stable connection)

## Related Issues

Fixes: "❌ REMOTE_NODE_HOST non configuré dans config.py" error
Addresses: Need to split echo into `/echomt` and `/echomc` for network targeting

## Future Enhancements

Possible follow-ups (not in this PR):
1. Add channel parameter: `/echo 2 message`
2. Add DM support: `/echoto @user message`
3. Add scheduling: `/echo --delay 60 message`
4. Add multi-broadcast: `/echoall message`
