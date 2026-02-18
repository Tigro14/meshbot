# MeshCore Help Text Simplification

**Date:** 2026-02-18  
**Status:** ✅ Implemented

## Problem Statement

On MeshCore (MC) side, the `/help` command listed commands that were not implemented:
- **Net:** `/my` and `/trace` (Meshtastic-only features)
- **Stats:** `/stats` and `/top` (Meshtastic-only features)

This caused confusion for MeshCore users who would see commands in help that didn't work.

## Solution

The help text now adapts dynamically based on which network the user is on:
- **MeshCore users** see only commands that work on MeshCore
- **Meshtastic users** see the full command list

## Implementation

### Network Detection

The system already detects network source via the `source` field in packets:
- `'meshcore'` → MeshCore network
- `'local'`, `'tcp'`, `'tigrog2'` → Meshtastic network

This detection was implemented in previous work on network isolation.

### Help Method Changes

**File:** `handlers/command_handlers/utility_commands.py`

```python
def handle_help(self, sender_id, sender_info, is_from_meshcore=False):
    """Gérer la commande /help"""
    help_text = self._format_help(is_from_meshcore=is_from_meshcore)
    # ... send help text

def _format_help(self, is_from_meshcore=False):
    """Formater l'aide compacte pour mesh (contrainte <180 chars/msg)"""
    if is_from_meshcore:
        # MeshCore: Remove unimplemented commands
        help_text = (
            "🤖 BOT MESH\n"
            "IA: /bot (alias: /ia)\n"
            "Sys: /power /sys /weather\n"
            "Net: /nodesmc\n"
            "Stats: /trafic /trafficmc\n"
            "DB: /db\n"
            "Util: /echo /legend /help\n"
            "Doc: README.md sur GitHub"
        )
    else:
        # Meshtastic: All commands available
        help_text = (
            "🤖 BOT MESH\n"
            "IA: /bot (alias: /ia)\n"
            "Sys: /power /sys /weather\n"
            "Net: /nodes /my /trace\n"
            "Stats: /stats /top /trafic\n"
            "DB: /db\n"
            "Util: /echo /legend /help\n"
            "Doc: README.md sur GitHub"
        )
    return help_text
```

### Router Changes

**File:** `handlers/message_router.py`

```python
# Pass network source flag to help handler
elif message.startswith('/help') or message.startswith('/?'):
    self.utility_handler.handle_help(sender_id, sender_info, is_from_meshcore=is_from_meshcore)
```

## Help Text Comparison

### Meshtastic Network (168 chars)

```
🤖 BOT MESH
IA: /bot (alias: /ia)
Sys: /power /sys /weather
Net: /nodes /my /trace
Stats: /stats /top /trafic
DB: /db
Util: /echo /legend /help
Doc: README.md sur GitHub
```

**Available commands:**
- `/nodes` - List all Meshtastic nodes
- `/my` - Show your signal strength
- `/trace` - Trace route to a node
- `/stats` - Unified statistics system
- `/top` - Top talkers on network
- `/trafic` - All public messages

### MeshCore Network (158 chars)

```
🤖 BOT MESH
IA: /bot (alias: /ia)
Sys: /power /sys /weather
Net: /nodesmc
Stats: /trafic /trafficmc
DB: /db
Util: /echo /legend /help
Doc: README.md sur GitHub
```

**Available commands:**
- `/nodesmc` - List MeshCore contacts
- `/trafic` - All public messages (both networks)
- `/trafficmc` - MeshCore messages only

## Commands Removed from MeshCore Help

| Command | Reason |
|---------|--------|
| `/my` | Not implemented - requires Meshtastic radio signal data |
| `/trace` | Not implemented - requires Meshtastic routing information |
| `/stats` | Not implemented - requires Meshtastic packet statistics |
| `/top` | Not implemented - requires Meshtastic packet history |
| `/nodes` | MeshCore uses `/nodesmc` instead |

## Commands Available on Both Networks

These commands work identically on both Meshtastic and MeshCore:

**Chat AI:**
- `/bot` - Chat with AI
- `/ia` - Alias for `/bot`

**System:**
- `/power` - Battery and solar data
- `/sys` - System status (CPU, RAM, uptime)
- `/weather` - Weather forecast

**Database:**
- `/db` - Database operations

**Utilities:**
- `/echo` - Broadcast a message
- `/legend` - Signal strength legend
- `/help` - This help text

**Traffic (common):**
- `/trafic` - Show all public messages (from both networks)

## Network-Specific Commands

### Meshtastic Only

| Command | Description |
|---------|-------------|
| `/nodes` | List Meshtastic nodes |
| `/nodemt` | Explicit Meshtastic nodes (dual mode) |
| `/neighbors` | Show mesh topology |
| `/my` | Signal strength info |
| `/trace` | Route tracing |
| `/stats` | Unified statistics |
| `/top` | Top talkers |
| `/trafficmt` | Meshtastic messages only |

### MeshCore Only

| Command | Description |
|---------|-------------|
| `/nodesmc` | List MeshCore contacts |
| `/trafficmc` | MeshCore messages only |

## Testing

**Demo:** `demos/demo_meshcore_help.py`

```bash
$ python3 demos/demo_meshcore_help.py
```

**Output:**
- ✅ Shows Meshtastic help (168 chars)
- ✅ Shows MeshCore help (158 chars)
- ✅ Highlights differences
- ✅ Validates both fit in LoRa packets

## Benefits

### For MeshCore Users
- ✅ No confusion about unavailable commands
- ✅ See only what they can actually use
- ✅ Cleaner, more relevant help text

### For Meshtastic Users
- ✅ Full command list as before
- ✅ No functionality removed

### For System
- ✅ Both help texts fit in LoRa packets (<180 chars)
- ✅ Dynamic adaptation based on network
- ✅ No configuration needed
- ✅ Consistent with network isolation feature

## Related Features

This change complements other network isolation features:

1. **Command Blocking** - MeshCore commands blocked from Meshtastic, and vice versa
2. **Network-Specific Commands** - `/echomt`, `/echomc`, `/trafficmt`, `/trafficmc`
3. **Help Text Adaptation** - This feature (context-aware help)

## Migration Impact

- **Breaking Changes:** NONE
- **User Action:** NONE required
- **Backward Compatibility:** ✅ Fully compatible

Existing users will automatically see network-appropriate help text.

## Documentation

- **Implementation:** `MESHCORE_HELP_SIMPLIFICATION.md` (this file)
- **Demo:** `demos/demo_meshcore_help.py`
- **Related:** `NETWORK_ISOLATION.md`

## Future Improvements

Potential enhancements:
1. Add `/help full` for detailed command explanations
2. Add `/help <command>` for command-specific help
3. Create network-specific help in Telegram as well

## Files Changed

| File | Changes | Lines |
|------|---------|-------|
| `handlers/command_handlers/utility_commands.py` | Network-aware help formatting | +23 -8 |
| `handlers/message_router.py` | Pass network flag to help | +2 -2 |
| `demos/demo_meshcore_help.py` | Demo and validation | +110 new |

**Total:** +135 lines, -10 lines = +125 net

## Testing Checklist

- [x] Demo shows correct help for Meshtastic
- [x] Demo shows correct help for MeshCore
- [x] Both help texts fit in LoRa packets
- [x] Commands removed from MeshCore help
- [x] MeshCore-specific commands shown
- [x] Common commands available on both
- [x] Documentation complete

## Status

✅ **COMPLETE** - Ready for production use

---

*Last updated: 2026-02-18*
