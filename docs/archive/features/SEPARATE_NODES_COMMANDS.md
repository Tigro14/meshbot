# Separate Commands for MeshCore and Meshtastic Nodes

## Problem
When running in MeshCore mode without `REMOTE_NODE_HOST` configured, the `/nodes` command would fail with:
```
❌ REMOTE_NODE_HOST non configuré dans config.py
```

This happened because the command tried to auto-detect the mode and route to either MeshCore or Meshtastic, but Meshtastic requires `REMOTE_NODE_HOST` to be configured.

## Solution
Added two dedicated commands to avoid configuration conflicts:

### `/nodesmc [page]`
**MeshCore Contacts**
- Retrieves contacts from `meshcore_contacts` SQLite table
- Works independently of `REMOTE_NODE_HOST` configuration
- Shows contacts synced from `sync_contacts()`
- Paginated display (7 contacts per page)

Example output:
```
📡 Contacts MeshCore (<30j) (15):
• Node-Alpha 5m
• Node-Bravo 12m
• Node-Charlie 1h
1/3
```

### `/nodemt [page]`
**Meshtastic Nodes**
- Queries Meshtastic nodes via remote node connection
- Requires `REMOTE_NODE_HOST` to be configured
- Shows nodes from Meshtastic network topology
- Paginated display (7 nodes per page)

Example output:
```
📡 Nœuds DIRECTS de tigrog2 (<3j) (15):
🟢 NodeA 8dB 5m 2.5km
🟡 NodeB 6dB 12m 5.1km
1/3
```

### `/nodes [page]`
**Auto-Detection (Backward Compatibility)**
- Automatically detects connection mode
- Routes to MeshCore or Meshtastic based on `CONNECTION_MODE` or `MESHCORE_ENABLED`
- Maintains backward compatibility with existing usage

## Implementation Details

### Files Modified

#### 1. `handlers/command_handlers/network_commands.py`
Added two new handler methods:
```python
def handle_nodesmc(self, message, sender_id, sender_info):
    """Liste des contacts MeshCore avec pagination"""
    report = self.remote_nodes_client.get_meshcore_paginated(page)
    # ...

def handle_nodemt(self, message, sender_id, sender_info):
    """Liste des nœuds Meshtastic avec pagination"""
    report = self.remote_nodes_client.get_tigrog2_paginated(page)
    # ...
```

#### 2. `handlers/message_router.py`
Added command routing (order matters - more specific before general):
```python
elif message.startswith('/nodesmc'):
    self.network_handler.handle_nodesmc(message, sender_id, sender_info)
elif message.startswith('/nodemt'):
    self.network_handler.handle_nodemt(message, sender_id, sender_info)
elif message.startswith('/nodes'):  
    self.network_handler.handle_nodes(message, sender_id, sender_info)
```

#### 3. `handlers/command_handlers/utility_commands.py`
Updated help text to include new commands:
```python
help_lines = [
    "/nodes",
    "/nodesmc",
    "/nodemt",
    # ...
]
```

## Benefits

1. **No Configuration Conflicts**: `/nodesmc` works without `REMOTE_NODE_HOST`
2. **Explicit Control**: Users can choose which source to query
3. **Dual-Mode Support**: Users can see both MeshCore and Meshtastic nodes
4. **Backward Compatible**: Existing `/nodes` usage still works
5. **Clear Intent**: Command name indicates the source

## Usage Scenarios

### Scenario 1: MeshCore Only
User running bot in MeshCore mode without Meshtastic:
```bash
/nodesmc     # ✅ Shows MeshCore contacts
/nodemt      # ❌ Fails (no REMOTE_NODE_HOST)
/nodes       # ✅ Auto-routes to MeshCore
```

### Scenario 2: Meshtastic Only
User running bot with Meshtastic:
```bash
/nodesmc     # Shows "Aucun contact MeshCore" (empty)
/nodemt      # ✅ Shows Meshtastic nodes
/nodes       # ✅ Auto-routes to Meshtastic
```

### Scenario 3: Hybrid Setup
User with both MeshCore and Meshtastic:
```bash
/nodesmc     # ✅ Shows MeshCore contacts
/nodemt      # ✅ Shows Meshtastic nodes
/nodes       # ✅ Shows whichever is configured as primary
```

## Configuration

No additional configuration needed. The commands work based on existing settings:

```python
# config.py
CONNECTION_MODE = 'meshcore'    # For /nodes auto-detection
MESHCORE_ENABLED = True         # Alternative flag
REMOTE_NODE_HOST = "192.168.1.38"  # Required only for /nodemt
```

## Testing

Commands have been tested to verify:
- ✅ All three handlers exist and are callable
- ✅ Routing order is correct (specific before general)
- ✅ Help text includes all commands
- ✅ Error handling is consistent across commands

## User Feedback
Original request from @Tigro14:
> "We may get two separates commands: /nodesmc and /nodemt for meshcore or meshtastic, now I got: ❌ REMOTE_NODE_HOST non configuré dans config.py because for the moment no meshtastic node is connected to the bot"

**Resolution**: Implemented as requested in commit 915fd22

---
**Date**: 2026-01-21
**Commit**: 915fd22
**Status**: ✅ Complete
