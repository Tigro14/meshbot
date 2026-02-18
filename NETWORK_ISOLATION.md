# Network Isolation for Commands

## Overview

This document describes the network isolation feature that prevents cross-network command execution between Meshtastic (MT) and MeshCore (MC) networks.

## Problem Statement

In dual network mode (Meshtastic + MeshCore), certain commands are network-specific:
- MeshCore commands (e.g., `/nodesmc`, `/trafficmc`) query MeshCore-specific data
- Meshtastic commands (e.g., `/nodemt`, `/nodes`, `/my`) query Meshtastic-specific data

Without isolation, users could mistakenly call a MeshCore command from the Meshtastic network (or vice versa), leading to confusion or errors.

## Solution

Network isolation prevents cross-network command execution by:
1. Tracking the source network of each message
2. Validating commands against network-specific lists
3. Blocking inappropriate commands with helpful error messages

## Network-Specific Commands

### MeshCore-Only Commands
Cannot be used from Meshtastic network:
- `/nodesmc` - List MeshCore contacts
- `/trafficmc` - Show MeshCore message history

### Meshtastic-Only Commands
Cannot be used from MeshCore network:
- `/nodemt` - List Meshtastic nodes
- `/trafficmt` - Show Meshtastic message history
- `/nodes` - List all nodes (Meshtastic database)
- `/neighbors` - Show mesh neighbors
- `/my` - Show signal info
- `/trace` - Trace route to node

### Neutral Commands
Available on all networks:
- `/help` - Show help
- `/bot` - AI chat
- `/weather` - Weather forecast
- `/power` - Power/battery status
- `/sys` - System info
- `/trafic` - Show all traffic (both networks)
- All other commands not listed above

## Technical Implementation

### Network Source Detection

The system identifies the source network from the packet's `source` field:

```python
# Meshtastic sources
meshtastic_sources = ['local', 'tcp', 'tigrog2']

# MeshCore sources
meshcore_sources = ['meshcore']
```

### Validation Logic

In `handlers/message_router.py`, the `_route_command()` method validates commands:

```python
# Determine network source
packet_source = packet.get('source', 'local')
is_from_meshcore = (packet_source == 'meshcore')
is_from_meshtastic = (packet_source in ['local', 'tcp', 'tigrog2'])

# Block MeshCore commands from Meshtastic
if is_from_meshtastic:
    for mc_cmd in meshcore_only_commands:
        if message.startswith(mc_cmd):
            # Send error message and return
            
# Block Meshtastic commands from MeshCore
if is_from_meshcore:
    for mt_cmd in meshtastic_only_commands:
        if message == mt_cmd or message.startswith(mt_cmd + ' '):
            # Send error message and return
```

### Word Boundary Check

The Meshtastic command validation uses word boundary checking to prevent false matches:

```python
# Correct: Matches "/nodes" but not "/nodesmc"
if message == mt_cmd or message.startswith(mt_cmd + ' '):
```

This prevents:
- `/nodes` from matching `/nodesmc`
- `/node` from matching `/nodes`

## Error Messages

### MeshCore Command from Meshtastic

When a user tries to use a MeshCore command from Meshtastic:

```
🚫 /nodesmc est réservé au réseau MeshCore.
Utilisez /nodemt ou /trafficmt pour Meshtastic.
```

### Meshtastic Command from MeshCore

When a user tries to use a Meshtastic command from MeshCore:

```
🚫 /nodemt est réservé au réseau Meshtastic.
Utilisez /nodesmc ou /trafficmc pour MeshCore.
```

## Usage Examples

### Example 1: MeshCore Command from Meshtastic (Blocked)

```
# User on Meshtastic sends:
/nodesmc

# Bot responds:
🚫 /nodesmc est réservé au réseau MeshCore.
Utilisez /nodemt ou /trafficmt pour Meshtastic.
```

### Example 2: Meshtastic Command from MeshCore (Blocked)

```
# User on MeshCore sends:
/nodemt

# Bot responds:
🚫 /nodemt est réservé au réseau Meshtastic.
Utilisez /nodesmc ou /trafficmc pour MeshCore.
```

### Example 3: Correct Network (Allowed)

```
# User on Meshtastic sends:
/nodemt

# Bot responds with Meshtastic node list
# (Command executes normally)
```

### Example 4: Neutral Command (Allowed Everywhere)

```
# User on any network sends:
/help

# Bot responds with help text
# (Command executes on both networks)
```

## Testing

### Demo Script

Run `demos/demo_network_isolation.py` to validate the isolation logic:

```bash
python3 demos/demo_network_isolation.py
```

### Test Coverage

The demo tests:
1. ✅ MeshCore commands from Meshtastic (4 tests) - All blocked
2. ✅ Meshtastic commands from MeshCore (8 tests) - All blocked
3. ✅ Commands on appropriate network (8 tests) - All allowed
4. ✅ Neutral commands (8 tests) - All allowed

**Total: 28 test cases, all passing**

### Test Output

```
✅ TOUS LES TESTS RÉUSSIS

Tests d'isolation réseau:
  ✅ Commandes MC (/nodesmc, /trafficmc) bloquées depuis MT
  ✅ Commandes MT (/nodemt, /trafficmt, /nodes, /neighbors, /my, /trace) bloquées depuis MC
  ✅ Commandes autorisées sur leur réseau respectif
  ✅ Commandes neutres (/help, /bot, /weather, etc.) disponibles partout

🎯 OBJECTIF ATTEINT:
   • Les commandes MeshCore ne peuvent pas être appelées depuis Meshtastic
   • Les commandes Meshtastic ne peuvent pas être appelées depuis MeshCore
   • Les utilisateurs reçoivent des messages d'erreur clairs et utiles
```

## Files Modified

### handlers/message_router.py

**Changes:**
1. `process_text_message()`: Added network source detection
   - Extract `source` from packet
   - Determine `is_from_meshcore` and `is_from_meshtastic`
   - Pass to `_route_command()`

2. `_route_command()`: Added network isolation validation
   - Check MC commands from MT → Block
   - Check MT commands from MC → Block
   - Use word boundary check for accurate matching
   - Send helpful error messages

### demos/demo_network_isolation.py

**Purpose:** Comprehensive test of network isolation logic

**Tests:**
- Cross-network blocking
- Same-network allowing
- Neutral command allowing
- Edge cases (substring matching, parameters)

## Benefits

### For Users
✅ Clear error messages guide to correct commands
✅ Prevents confusion from calling wrong network commands
✅ Consistent user experience across networks

### For Developers
✅ Centralized validation logic
✅ Easy to add new network-specific commands
✅ Well-tested with demo script

### For System
✅ Prevents invalid queries
✅ Reduces error conditions
✅ Better separation of network concerns

## Configuration

No configuration needed. Network isolation is:
- **Automatic**: Detects network from packet source
- **Always-on**: Applies in dual network mode
- **Transparent**: Users only see helpful error messages

## Extending

### Adding New Network-Specific Commands

To add a new network-specific command:

1. Add to appropriate list in `message_router.py`:

```python
# For MeshCore-only
meshcore_only_commands = ['/nodesmc', '/trafficmc', '/newmccmd']

# For Meshtastic-only
meshtastic_only_commands = ['/nodemt', '/trafficmt', '/newmtcmd', ...]
```

2. Update error messages if needed

3. Add test cases to demo

### Making a Command Network-Neutral

If a command should work on both networks:
1. Don't add it to either list
2. It will automatically be allowed on both networks

## Future Enhancements

Possible improvements:

1. **Per-command error messages**: Customize guidance per command
2. **Auto-correction**: Suggest correct command automatically
3. **Help integration**: Show network context in `/help`
4. **Admin override**: Allow admins to bypass restrictions

## See Also

- `TRAFFIC_COMMANDS_UPDATE.md` - Network-specific traffic commands
- `ECHO_COMMANDS_UPDATE.md` - Network-specific echo commands
- `handlers/message_router.py` - Implementation source
- `demos/demo_network_isolation.py` - Test demonstration
