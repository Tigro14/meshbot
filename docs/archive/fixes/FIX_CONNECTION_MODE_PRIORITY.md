# Fix: Meshtastic Traffic Not Working (Connection Mode Priority)

## Problem Statement
Users reported that "meshstastic traffic & DM to the bot seems not working now on the meshtastic node side. Nothing show related to meshtastic in the debug log"

## Root Cause Analysis

### Configuration Discovery
The configuration file had:
```python
MESHTASTIC_ENABLED = True  # Connect to Meshtastic for full mesh
MESHCORE_ENABLED = True    # Also enable MeshCore companion mode
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM2"        # Meshtastic node
MESHCORE_SERIAL_PORT = "/dev/ttyACM0"  # MeshCore serial
```

### The Bug
In `main_bot.py::start()` (lines 1665-1695 before fix), the connection logic was:

```python
if not meshtastic_enabled and not meshcore_enabled:
    # Standalone mode
    self.interface = MeshCoreStandaloneInterface()
    
elif meshcore_enabled:  # ❌ BUG: This fires when BOTH are enabled!
    # MeshCore connection
    self.interface = MeshCoreSerialInterface(meshcore_port)
    # ... connect to /dev/ttyACM0
    
elif meshtastic_enabled and connection_mode == 'tcp':
    # TCP mode
    
elif meshtastic_enabled:  # ❌ NEVER REACHED when MeshCore is enabled!
    # Serial mode
    self.interface = meshtastic.serial_interface.SerialInterface(serial_port)
```

**Problem:** When both `MESHTASTIC_ENABLED=True` and `MESHCORE_ENABLED=True`, the second `elif` block catches first, connecting to MeshCore instead of Meshtastic.

**Impact:**
- Bot connects to MeshCore on `/dev/ttyACM0` 
- MeshCore only provides Direct Messages (DMs), not full mesh traffic
- No broadcast messages or network topology visible
- Debug logs show no Meshtastic activity

## The Fix

### Code Changes

Changed the connection priority logic in `main_bot.py::start()`:

```python
# Priority order when both are enabled:
# 1. Meshtastic (if enabled) - Full mesh capabilities
# 2. MeshCore (if Meshtastic disabled) - Companion mode for DMs only
# 3. Standalone (neither enabled) - Test mode

if not meshtastic_enabled and not meshcore_enabled:
    # Standalone mode
    self.interface = MeshCoreStandaloneInterface()
    
elif meshtastic_enabled and meshcore_enabled:
    # ✅ NEW: Both enabled - warn user and prioritize Meshtastic
    info_print("⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés")
    info_print("   → Priorité donnée à Meshtastic (capacités mesh complètes)")
    info_print("   → MeshCore sera ignoré. Pour utiliser MeshCore:")
    info_print("   →   Définir MESHTASTIC_ENABLED = False dans config.py")
    # Continue to Meshtastic connection blocks below
    
if meshtastic_enabled and connection_mode == 'tcp':
    # TCP mode
    self.interface = OptimizedTCPInterface(hostname=tcp_host, portNumber=tcp_port)
    
elif meshtastic_enabled:
    # Serial mode
    self.interface = meshtastic.serial_interface.SerialInterface(serial_port)
    
elif meshcore_enabled and not meshtastic_enabled:  # ✅ FIXED: Only if Meshtastic disabled
    # MeshCore companion mode
    self.interface = MeshCoreSerialInterface(meshcore_port)
```

### Key Changes
1. **Added explicit check** for both modes enabled with warning message
2. **Changed MeshCore condition** from `elif meshcore_enabled:` to `elif meshcore_enabled and not meshtastic_enabled:`
3. **Added priority documentation** in code comments
4. **Updated config.py.sample** with priority documentation

## Testing

### Test Coverage

Created two test files:

1. **`test_mode_priority.py`** - Simple priority logic verification
2. **`test_connection_logic_fix.py`** - Comprehensive integration test

All 6 test scenarios pass:

| Scenario | MESHTASTIC | MESHCORE | Expected Mode | Status |
|----------|------------|----------|---------------|--------|
| Standalone | False | False | STANDALONE | ✅ PASS |
| MeshCore only | False | True | MESHCORE | ✅ PASS |
| Meshtastic Serial | True | False | MESHTASTIC_SERIAL | ✅ PASS |
| Meshtastic TCP | True | False (TCP) | MESHTASTIC_TCP | ✅ PASS |
| **Both (Serial)** | **True** | **True** | **MESHTASTIC_SERIAL** | **✅ PASS (FIX)** |
| **Both (TCP)** | **True** | **True (TCP)** | **MESHTASTIC_TCP** | **✅ PASS (FIX)** |

## Result

### Before Fix
```
Config: MESHTASTIC_ENABLED=True, MESHCORE_ENABLED=True
→ Bot connects to MeshCore (/dev/ttyACM0)
→ Only DMs received
→ No mesh traffic visible
→ No debug logs for Meshtastic
```

### After Fix
```
Config: MESHTASTIC_ENABLED=True, MESHCORE_ENABLED=True
⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés
   → Priorité donnée à Meshtastic (capacités mesh complètes)
   → MeshCore sera ignoré. Pour utiliser MeshCore:
   →   Définir MESHTASTIC_ENABLED = False dans config.py

→ Bot connects to Meshtastic (/dev/ttyACM2)
→ Full mesh traffic received
→ Broadcasts, DMs, and network topology visible
→ Debug logs show Meshtastic activity
```

## Recommended Configuration

For users who want full Meshtastic capabilities:

```python
# config.py
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False  # ← Set to False when using Meshtastic
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM2"
```

For users who want MeshCore companion mode only:

```python
# config.py
MESHTASTIC_ENABLED = False  # ← Disable Meshtastic
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyACM0"
```

## Priority Order (Clarified)

1. **Meshtastic** (if enabled) - Full mesh capabilities
   - Broadcast messages
   - Direct messages
   - Network topology (/nodes, /neighbors)
   - Statistics (/stats)
   - Traceroute (/trace)

2. **MeshCore** (if Meshtastic disabled) - Companion mode
   - Direct messages only
   - Limited commands: /bot, /weather, /power, /sys
   - No network topology or statistics

3. **Standalone** (neither enabled) - Test mode
   - No radio connection
   - Platform commands only (Telegram, CLI)

## Files Changed

- `main_bot.py` - Fixed connection priority logic
- `config.py.sample` - Added priority documentation
- `test_mode_priority.py` - New test file
- `test_connection_logic_fix.py` - New comprehensive test
- `FIX_CONNECTION_MODE_PRIORITY.md` - This documentation

## Verification Steps

To verify the fix is working:

1. **Check logs at startup:**
   ```bash
   journalctl -u meshbot -f
   ```

2. **Look for connection messages:**
   - ✅ Good: `🔌 Mode SERIAL MESHTASTIC: Connexion série /dev/ttyACM2`
   - ✅ Good: `✅ Abonné aux messages Meshtastic (receive)`
   - ❌ Bad: `🔗 Mode MESHCORE COMPANION: Connexion série /dev/ttyACM0`

3. **Check for warning if both enabled:**
   - Should see: `⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés`

4. **Test mesh traffic:**
   - Send a broadcast: `/echo test`
   - Check you receive broadcasts from other nodes
   - Try `/nodes` command (should show network)

## Related Issues

This fix resolves scenarios where:
- Users enable both modes and lose mesh traffic
- Configuration is unclear about mode priority
- No warning given when conflicting modes enabled

## Backward Compatibility

✅ **Fully backward compatible**
- Existing configs with only one mode enabled work unchanged
- New warning helps users with conflicting configs
- No breaking changes to API or behavior
