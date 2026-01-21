# Implementation Summary: /rebootpi in Companion Mode

## Additional Request
**User comment**: "@copilot also enable /rebootpi"

**Description**: Following the implementation of `/ia` command in companion mode, the user requested that `/rebootpi` command also be enabled in companion mode.

## Analysis

### Why `/rebootpi` Works in Companion Mode
The `/rebootpi` command **does not depend on Meshtastic**. It only requires:
1. **Node authentication** - Works with `node_manager` (available in companion mode)
2. **RebootSemaphore** - System-level signaling mechanism using `/dev/shm`
3. **Password verification** - Pure logic, no Meshtastic dependency

### What About `/rebootnode`?
`/rebootnode` **cannot** work in companion mode because:
- It requires sending commands to target Meshtastic nodes via the interface
- This needs active Meshtastic TCP/serial connection
- Not available in MeshCore-only companion mode

## Implementation

### Changes Made

1. **Message Router** (`handlers/message_router.py`)
   - Added `/rebootpi` to `companion_commands` list
   
   ```python
   self.companion_commands = [
       '/bot',      # AI
       '/ia',       # AI (alias français)
       '/weather',  # Météo
       '/rain',     # Graphiques pluie
       '/power',    # ESPHome telemetry
       '/sys',      # Système (CPU, RAM, uptime)
       '/help',     # Aide
       '/blitz',    # Lightning (si activé)
       '/vigilance',# Vigilance météo (si activé)
       '/rebootpi'  # Redémarrage Pi (authentifié) ← ADDED
   ]
   ```

2. **Documentation** (`MESHCORE_COMPANION.md`)
   - Added `/rebootpi <password>` to available commands table
   - Added `/rebootnode` to disabled commands table (requires Meshtastic)

3. **Tests**
   - Updated `test_meshcore_companion.py` to verify `/rebootpi` in companion_commands
   - Created `test_rebootpi_companion.py` with 2 specific tests

## Security Note

`/rebootpi` remains **fully secured** in companion mode:
- Requires password authentication
- Checks authorized user list (`REBOOT_AUTHORIZED_USERS`)
- Uses RebootSemaphore for safe signaling
- No bypass of existing security mechanisms

## Test Results

```bash
$ python3 test_rebootpi_companion.py -v
test_rebootpi_in_companion_commands ... ok ✅
test_rebootpi_not_filtered_in_companion_mode ... ok ✅

Ran 2 tests in 0.009s
OK
```

## Verification

### Companion Mode Commands (Updated)
- [x] `/bot` - AI
- [x] `/ia` - AI (French)
- [x] `/weather` - Weather
- [x] `/rain` - Rain graphs
- [x] `/power` - ESPHome telemetry
- [x] `/sys` - System info
- [x] `/help` - Help
- [x] `/blitz` - Lightning
- [x] `/vigilance` - Weather alerts
- [x] `/rebootpi` - **Reboot Pi5** ← NEWLY ADDED

### Still Disabled (Require Meshtastic)
- `/nodes`, `/my`, `/trace`, `/neighbors`
- `/info`, `/stats`, `/top`, `/histo`
- `/keys`, `/propag`, `/hop`, `/db`
- `/rebootnode` - Requires sending commands to target nodes

## Usage Example

### MeshCore Companion Mode
```
MeshCore → DM:12345678:/rebootpi mypassword
Bot      → ✅ Redémarrage Pi5 programmé

# Authorization check performed
# RebootSemaphore activated
# Pi5 will reboot via watcher daemon
```

## Files Modified

1. `handlers/message_router.py` - Added `/rebootpi` to companion_commands
2. `MESHCORE_COMPANION.md` - Updated command tables
3. `test_meshcore_companion.py` - Added `/rebootpi` assertion
4. `test_rebootpi_companion.py` - Created new test file (2 tests)

## Summary

**Change**: Added `/rebootpi` to companion mode
**Security**: Fully maintained (password + authorization)
**Tests**: All passing ✅
**Documentation**: Updated
**Status**: ✅ Complete
