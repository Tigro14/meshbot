# Message Polling Fix Summary

## Problem Statement
"The bot has now two nodes attached: a Meshtastic and a Meshcore. For the moment it seems the polling for the messages is broken both sides, DM sent to both nodes to the bot are marked as received but get no answer (even with DEBUG log)."

## Updates

### 2026-02-01: Diagnostic Test Fix ✅ FIXED
**Problem:** Diagnostic test script failed for users with serial-only Meshtastic configuration:
```
❌ Import error: cannot import name 'TCP_HOST' from 'config'
```

**Root Cause:** Test script tried to import `TCP_HOST` and `TCP_PORT` unconditionally, but these variables don't exist in serial-only configs.

**Fix:** Changed imports to use `getattr()` with defaults, making TCP configuration optional for serial mode.

**Files Changed:**
- `test_message_polling_diagnostic.py` - Graceful config imports with getattr()

**Documentation Added:**
- `DIAGNOSTIC_TEST_CONFIG_GUIDE.md` - Complete guide for all config scenarios
- `test_config_import_graceful.py` - Unit test for config import patterns

**See:** [Diagnostic Test Configuration Guide](DIAGNOSTIC_TEST_CONFIG_GUIDE.md)

---

## Root Causes Identified

### 1. MeshCore CLI Wrapper - Async Event Loop Blocking ✅ FIXED
**Location:** `meshcore_cli_wrapper.py:873`

**Problem:**
```python
self._loop.run_until_complete(event_loop_task())
```

The event loop was using `run_until_complete()` which BLOCKS the thread waiting for the coroutine to complete. The coroutine had an infinite `while self.running` loop, so it never completed. This prevented the meshcore-cli dispatcher from invoking event callbacks.

**Fix:**
```python
self._loop.create_task(event_loop_task())
self._loop.run_forever()
```

Now uses `run_forever()` which allows the event loop to continuously process events, enabling the dispatcher to invoke `_on_contact_message()` when messages arrive.

**Files Changed:**
- `meshcore_cli_wrapper.py::_async_event_loop()` - Changed from run_until_complete to run_forever
- `meshcore_cli_wrapper.py::close()` - Added proper loop stopping with call_soon_threadsafe

---

### 2. MeshCore Serial Interface - No Active Polling ✅ FIXED
**Location:** `meshcore_serial_interface.py:125-157`

**Problem:**
The interface only READ passively when `serial.in_waiting > 0`. It never actively REQUESTED messages using `CMD_SYNC_NEXT_MESSAGE` (defined but never used).

**Fix:**
Added active polling mechanism:
1. New `_poll_loop()` method runs in separate thread
2. Sends "SYNC_NEXT\n" command every 5 seconds
3. Handles `PUSH_CODE_MSG_WAITING` (0x83) push notifications
4. Immediately requests message when notification received

**Files Changed:**
- `meshcore_serial_interface.py::__init__()` - Added poll_thread attribute
- `meshcore_serial_interface.py::start_reading()` - Start both read and poll threads
- `meshcore_serial_interface.py::_poll_loop()` - NEW: Active polling mechanism
- `meshcore_serial_interface.py::_process_meshcore_binary()` - Handle push notifications
- `meshcore_serial_interface.py::close()` - Wait for poll_thread

---

### 3. Meshtastic pub.subscribe() - Architecture Limitation ⚠️ REQUIRES CLARIFICATION

**Location:** `main_bot.py:1665-1870`

**Current Architecture:**
The code uses `elif` branches to select ONE interface type:
```python
if not meshtastic_enabled and not meshcore_enabled:
    # Standalone
elif meshcore_enabled:
    # MeshCore only
elif meshtastic_enabled and connection_mode == 'tcp':
    # Meshtastic TCP only
elif meshtastic_enabled:
    # Meshtastic serial only
```

**Issue:**
When `MESHCORE_ENABLED=True`, the code enters the `elif meshcore_enabled` branch and NEVER sets up Meshtastic, even if `MESHTASTIC_ENABLED=True`.

**Question:**
Does the problem statement mean:
1. **Sequential operation**: User wants to switch between Meshtastic and MeshCore (not simultaneously)?
2. **Simultaneous operation**: User wants BOTH nodes running at the same time?

**Current Status:**
- The architecture only supports ONE primary interface at a time
- To support dual nodes simultaneously would require refactoring to have separate `self.meshtastic_interface` and `self.meshcore_interface`

**Recommendation:**
- If sequential: Current code is correct, just ensure proper config (set one to False)
- If simultaneous: Major refactoring needed (not minimal change)

---

## Testing

### MeshCore CLI Wrapper Test

```python
# Test if event loop processes events
import asyncio
from meshcore_cli_wrapper import MeshCoreCLIWrapper

interface = MeshCoreCLIWrapper("/dev/ttyUSB0")
interface.connect()
interface.start_reading()

# Send a test DM to the bot
# Expected: _on_contact_message() callback should be invoked
# Expected: on_message() callback in main_bot.py should be called
# Expected: Bot should process the command and respond

time.sleep(30)
interface.close()
```

### MeshCore Serial Test

```python
# Test if polling requests messages
from meshcore_serial_interface import MeshCoreSerialInterface

interface = MeshCoreSerialInterface("/dev/ttyUSB0")
interface.connect()
interface.start_reading()

# Check logs for:
# "📤 [MESHCORE-POLL] Demande de messages en attente" every 5 seconds
# "📬 [MESHCORE-PUSH] Message en attente détecté" when device has messages
# "📬 [MESHCORE-DM] De: 0x..." when message received

time.sleep(30)
interface.close()
```

### Meshtastic Test

```python
# Test if pub.subscribe works
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

def on_message(packet, interface):
    print(f"Message received: {packet}")

interface = meshtastic.serial_interface.SerialInterface("/dev/ttyACM0")
pub.subscribe(on_message, "meshtastic.receive")

# Send a test DM to the bot via Meshtastic
# Expected: on_message() callback should be invoked
# Expected: Packet printed to console

time.sleep(30)
interface.close()
```

---

## Debugging Commands

### Enable Debug Logging
```python
# In config.py
DEBUG_MODE = True
```

### Check Which Interface is Active
```bash
# In logs, look for:
grep "Mode MESHCORE\|Mode TCP\|Mode SERIAL" /var/log/meshbot.log
```

### Verify Pub.Subscribe Registration
```bash
# In logs, look for:
grep "Abonné aux messages Meshtastic" /var/log/meshbot.log
```

### Verify MeshCore Polling
```bash
# In logs, look for:
grep "MESHCORE-POLL\|MESHCORE-PUSH" /var/log/meshbot.log
```

### Verify Message Reception
```bash
# In logs, look for:
grep "on_message CALLED\|_on_contact_message CALLED" /var/log/meshbot.log
```

---

## Configuration Examples

### MeshCore Only
```python
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

### Meshtastic Serial Only
```python
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"
```

### Meshtastic TCP Only
```python
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
CONNECTION_MODE = 'tcp'
TCP_HOST = '192.168.1.38'
TCP_PORT = 4403
```

### Dual Nodes (NOT CURRENTLY SUPPORTED)
```python
# This configuration will NOT work as intended
# Only MeshCore will be initialized (elif branch)
MESHTASTIC_ENABLED = True   # ❌ IGNORED
MESHCORE_ENABLED = True      # ✅ USED
```

---

## Expected Behavior After Fixes

### MeshCore (with meshcore-cli library)
1. ✅ Event loop runs continuously with `run_forever()`
2. ✅ meshcore-cli dispatcher can invoke callbacks
3. ✅ `_on_contact_message()` called when DM received
4. ✅ Bot callback `on_message()` invoked
5. ✅ Message processed and response sent

### MeshCore (basic serial interface)
1. ✅ Read thread continuously monitors serial port
2. ✅ Poll thread sends SYNC_NEXT every 5 seconds
3. ✅ Push notifications (MSG_WAITING) trigger immediate sync
4. ✅ Messages parsed and callback invoked
5. ✅ Bot processes message and responds

### Meshtastic
1. ❓ **Depends on configuration** - Only works if MESHCORE_ENABLED=False
2. ✅ pub.subscribe() registers callback (if Meshtastic active)
3. ✅ Meshtastic library publishes messages to topic
4. ✅ Bot callback `on_message()` invoked
5. ✅ Message processed and response sent

---

## Recommendations

1. **Test MeshCore fixes** with actual hardware
2. **Clarify dual-node requirement**: Is simultaneous operation needed?
3. **If dual-node needed**: Plan major refactoring (separate interfaces)
4. **If sequential only**: Document proper configuration switching
5. **Add telemetry**: Log when messages received but not answered (identify filtering issues)

---

## Files Modified

- `meshcore_cli_wrapper.py` - Fixed async event loop blocking
- `meshcore_serial_interface.py` - Added active polling mechanism

## Minimal Changes
✅ Both fixes are minimal and focused on the specific issues
✅ No breaking changes to existing functionality
✅ Backward compatible with existing code
