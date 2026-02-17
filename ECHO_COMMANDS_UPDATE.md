# Echo Commands Update

## Overview

This document describes the improvements made to the `/echo` command system to fix the REMOTE_NODE_HOST requirement issue and add support for explicit network targeting in dual mode.

## Problem Statement

The original `/echo` command from Telegram had several issues:

1. **Required REMOTE_NODE_HOST**: When bot was in serial mode, `/echo` tried to create a new TCP connection, requiring `REMOTE_NODE_HOST` to be configured
2. **TCP Connection Conflicts**: Creating a new TCP connection could conflict with the bot's main connection
3. **No Serial Support**: Didn't work properly with serial-attached nodes
4. **No Network Selection**: In dual mode, couldn't explicitly choose which network to send to

## Solution

### New Architecture

The solution uses the bot's **shared interface** instead of creating new connections:

```python
# OLD: Try to create new TCP connection (requires REMOTE_NODE_HOST)
from safe_tcp_connection import send_text_to_remote
success, result = send_text_to_remote(REMOTE_NODE_HOST, message)

# NEW: Use bot's existing interface
self.interface.sendText(message, channelIndex=0)
```

### New Commands

Three commands are now available:

1. **`/echo <message>`** - Send to current network (auto-detect)
   - In single mode: Uses the primary interface (Meshtastic or MeshCore)
   - In dual mode: Uses the primary interface (typically Meshtastic)
   
2. **`/echomt <message>`** - Send to Meshtastic network explicitly
   - In single Meshtastic mode: Same as `/echo`
   - In dual mode: Forces message to Meshtastic network
   - In MeshCore-only mode: Returns error (no Meshtastic available)
   
3. **`/echomc <message>`** - Send to MeshCore network explicitly
   - In single MeshCore mode: Same as `/echo`
   - In dual mode: Forces message to MeshCore network
   - In Meshtastic-only mode: Returns error (no MeshCore available)

## Technical Implementation

### File Changes

#### 1. `telegram_bot/command_base.py`
Added `self.dual_interface` property to give all Telegram commands access to the dual interface manager:

```python
self.dual_interface = getattr(telegram_integration.message_handler, 'dual_interface', None)
```

#### 2. `telegram_bot/commands/mesh_commands.py`
Complete rewrite with three main changes:

**a) Removed dependencies:**
```python
# REMOVED:
from config import REMOTE_NODE_HOST, CONNECTION_MODE
```

**b) Added helper method:**
```python
def _send_echo_to_network(self, message, network_type=None):
    """
    Send echo via shared interface.
    
    Args:
        message: Formatted message to send
        network_type: 'meshtastic', 'meshcore', or None for auto-detect
    """
    # Dual mode routing
    if network_type and self.dual_interface and self.dual_interface.is_dual_mode():
        # Route to specific network
        
    # Single mode - use direct interface
    # Auto-detect Meshtastic vs MeshCore
```

**c) Implemented three commands:**
```python
async def echo_command(self, update, context):
    """Auto-detect network"""
    await self._execute_echo_command(update, context, network_type=None)

async def echomt_command(self, update, context):
    """Force Meshtastic"""
    await self._execute_echo_command(update, context, network_type='meshtastic')

async def echomc_command(self, update, context):
    """Force MeshCore"""
    await self._execute_echo_command(update, context, network_type='meshcore')
```

#### 3. `telegram_integration.py`
Registered new command handlers:

```python
# Commandes mesh
self.application.add_handler(CommandHandler("echo", self.mesh_commands.echo_command))
self.application.add_handler(CommandHandler("echomt", self.mesh_commands.echomt_command))
self.application.add_handler(CommandHandler("echomc", self.mesh_commands.echomc_command))
```

#### 4. `telegram_bot/commands/basic_commands.py`
Updated help text:

```python
f"• /echo <msg> - Diffuser sur mesh actuel\n"
f"• /echomt <msg> - Diffuser sur Meshtastic\n"
f"• /echomc <msg> - Diffuser sur MeshCore\n"
```

### Routing Logic

The routing logic in `_send_echo_to_network()` follows this decision tree:

```
┌─────────────────────────────────────┐
│ _send_echo_to_network(message,     │
│                        network_type)│
└───────────┬─────────────────────────┘
            │
            ├─ network_type specified?
            │  └─ YES ─→ ┌─────────────────────────┐
            │            │ Dual mode active?       │
            │            └──┬──────────────────────┘
            │               │
            │               ├─ YES ─→ Route to specific network
            │               │         via dual_interface.send_message()
            │               │
            │               └─ NO ──→ Error: network_type requires dual mode
            │
            └─ network_type = None (auto-detect)
               └─→ ┌─────────────────────────┐
                   │ Detect interface type   │
                   └──┬──────────────────────┘
                      │
                      ├─ MeshCore? ─→ sendText(..., destinationId=0xFFFFFFFF)
                      │
                      └─ Meshtastic? ─→ sendText(..., channelIndex=0)
```

## Usage Examples

### Example 1: Serial-only Meshtastic Configuration

```python
# config.py
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"
# No REMOTE_NODE_HOST needed!
```

**Telegram commands:**
- `/echo hello` → Broadcasts on Meshtastic via serial
- `/echomt hello` → Same (only network available)
- `/echomc hello` → Error: MeshCore not available

### Example 2: TCP-only Meshtastic Configuration

```python
# config.py
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
CONNECTION_MODE = 'tcp'
TCP_HOST = "192.168.1.38"
TCP_PORT = 4403
```

**Telegram commands:**
- `/echo hello` → Broadcasts on Meshtastic via TCP (reuses bot's connection)
- `/echomt hello` → Same
- `/echomc hello` → Error: MeshCore not available

### Example 3: MeshCore-only Configuration

```python
# config.py
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

**Telegram commands:**
- `/echo hello` → Broadcasts on MeshCore
- `/echomt hello` → Error: Meshtastic not available
- `/echomc hello` → Broadcasts on MeshCore

### Example 4: Dual Mode Configuration

```python
# config.py
DUAL_NETWORK_MODE = True
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
SERIAL_PORT = "/dev/ttyACM0"  # Meshtastic
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore
```

**Telegram commands:**
- `/echo hello` → Broadcasts on Meshtastic (primary network)
- `/echomt hello` → Explicitly broadcasts on Meshtastic
- `/echomc hello` → Explicitly broadcasts on MeshCore

## Benefits

### 1. No REMOTE_NODE_HOST Required
✅ Works with serial-attached nodes without any TCP configuration
✅ Simpler configuration for serial-only setups

### 2. No TCP Connection Conflicts
✅ Reuses bot's existing interface
✅ No risk of disconnecting main bot connection
✅ ESP32 single TCP connection limit respected

### 3. Explicit Network Selection
✅ In dual mode, can target specific network
✅ Useful for testing/debugging
✅ Clear intent in commands

### 4. Backward Compatibility
✅ `/echo` still works in all existing configurations
✅ No breaking changes for single-network setups
✅ New commands are additive

## Testing

### Demo Script
Run `demos/demo_echo_commands.py` to see the routing logic in action:

```bash
python3 demos/demo_echo_commands.py
```

Output shows 5 scenarios:
1. Single mode Meshtastic
2. Single mode MeshCore
3. Dual mode /echo (auto)
4. Dual mode /echomt (explicit)
5. Dual mode /echomc (explicit)

### Unit Tests
Run `tests/test_echo_commands.py` for comprehensive testing:

```bash
python3 tests/test_echo_commands.py
```

Tests cover:
- Shared interface usage
- MeshCore detection
- REMOTE_NODE_HOST not required
- Dual mode routing
- Error handling

## Migration Guide

### If you're using serial mode:

**Before:**
```python
# config.py
REMOTE_NODE_HOST = "192.168.1.38"  # Was required for /echo
CONNECTION_MODE = 'serial'
```

**After:**
```python
# config.py
# REMOTE_NODE_HOST not needed anymore!
CONNECTION_MODE = 'serial'  # or just remove, default is serial
```

### If you're using TCP mode:

**No changes needed!** The new implementation works exactly the same, but uses the bot's existing TCP connection instead of creating a new one.

### If you're using dual mode:

**New capabilities available!**
- `/echo` works as before (uses primary network)
- `/echomt` explicitly targets Meshtastic
- `/echomc` explicitly targets MeshCore

## Troubleshooting

### "❌ Interface bot non disponible"

**Cause:** Bot's interface is not initialized
**Solution:** Check that bot is connected to a node (serial or TCP)

### "❌ Réseau Meshtastic non disponible"

**Cause:** `/echomt` used but Meshtastic is not enabled
**Solution:** Either use `/echo` or enable Meshtastic in config

### "❌ Réseau MeshCore non disponible"

**Cause:** `/echomc` used but MeshCore is not enabled
**Solution:** Either use `/echo` or enable MeshCore in config

## Future Enhancements

Possible future improvements:

1. **Channel Selection**: Add parameter to specify channel number
   - `/echo 2 message` → Send to channel 2
   
2. **DM Support**: Add option to send DM instead of broadcast
   - `/echoto @user message` → Send DM to user
   
3. **Delayed Send**: Add scheduling capability
   - `/echo --delay 60 message` → Send after 60 seconds
   
4. **Multi-network Broadcast**: Send to both networks in dual mode
   - `/echoall message` → Broadcast on both Meshtastic and MeshCore

## See Also

- `DUAL_NETWORK_MODE.md` - Dual mode architecture documentation
- `CLAUDE.md` - Overall bot architecture
- `telegram_bot/commands/mesh_commands.py` - Implementation source code
- `demos/demo_echo_commands.py` - Interactive demonstration
