# Fix: /echo Command for MeshCore

## Problem Statement

The `/echo` command was not working on the MeshCore side because packets were not being issued to the mesh network.

## Root Cause

The `/echo` command implementation in `handlers/command_handlers/utility_commands.py` called `interface.sendText()` with different signatures for different interfaces:

- **Meshtastic API**: `sendText(text, channelIndex=0)` - broadcasts by default
- **MeshCore API**: `sendText(text, destinationId, wantAck=False, channelIndex=0)` - requires destinationId parameter

The original code only passed the text parameter:
```python
interface.sendText(echo_response)  # ❌ Fails for MeshCore
```

This worked for Meshtastic but failed for MeshCore because MeshCore requires the `destinationId` parameter.

## Solution

Implemented interface type detection to call the appropriate `sendText` signature:

```python
# Detect interface type
is_meshcore = hasattr(interface, '__class__') and 'MeshCore' in interface.__class__.__name__

if is_meshcore:
    # MeshCore: Send as broadcast on public channel
    interface.sendText(echo_response, destinationId=0xFFFFFFFF, channelIndex=0)
else:
    # Meshtastic: Broadcast on public channel
    interface.sendText(echo_response, channelIndex=0)
```

### Key Parameters

- **destinationId**: `0xFFFFFFFF` (4294967295) = broadcast to all nodes
- **channelIndex**: `0` = public/default channel
- **wantAck**: `False` (default) = no acknowledgment required for broadcasts

## Files Modified

1. **`handlers/command_handlers/utility_commands.py`**
   - `handle_echo()` - Line ~220
   - `_send_broadcast_via_tigrog2()` - Line ~1030

2. **`handlers/command_handlers/ai_commands.py`**
   - `_send_broadcast_via_tigrog2()` - Line ~85

3. **`handlers/command_handlers/network_commands.py`**
   - `_send_broadcast_via_tigrog2()` - Line ~390

4. **`telegram_bot/commands/mesh_commands.py`**
   - `handle_echo()` - Line ~75

## Testing

Created test file `test_echo_meshcore_fix.py` that verifies:

1. ✅ Meshtastic interface: `sendText(text, channelIndex=0)`
2. ✅ MeshCore interface: `sendText(text, destinationId=0xFFFFFFFF, channelIndex=0)`

## Benefits

1. ✅ **MeshCore Support**: `/echo` now works with MeshCore companion mode
2. ✅ **Backward Compatible**: Existing Meshtastic functionality unchanged
3. ✅ **Explicit Channel**: Always uses public channel (index 0)
4. ✅ **Consistent Behavior**: All broadcast commands use same pattern

## Broadcast Behavior

### Meshtastic Mode
```
/echo Hello World
→ sendText("tigroX: Hello World", channelIndex=0)
→ Broadcasts on Public channel to all nodes
```

### MeshCore Mode
```
/echo Hello World
→ sendText("tigroX: Hello World", destinationId=0xFFFFFFFF, channelIndex=0)
→ Broadcasts on Public channel to all nodes
```

## Related Commands

The same fix pattern applies to other broadcast commands:
- `/bot` (AI queries)
- `/ia` (AI queries, French alias)
- `/my` (Signal info)
- `/weather` (Weather info)
- `/rain` (Rain forecast)
- `/info` (Node info)
- `/propag` (Propagation stats)
- `/hop` (Hop analysis)

---

# Help Code Location for MeshCore

## Question: "Where is the /help code for meshcore so I can rework it a bit?"

The `/help` command code is located in:

### Main Implementation
**File**: `handlers/command_handlers/utility_commands.py`

**Two format methods**:

1. **`_format_help()`** - Line 575
   - **Purpose**: Compact help text for mesh/LoRa (180 char limit)
   - **Used by**: Meshtastic and MeshCore mesh commands
   - **Format**: Simple list of commands
   
   ```python
   def _format_help(self):
       """Formater l'aide des commandes"""
       help_lines = [
           "/bot IA",
           "/ia IA",
           "/power",
           "/sys",
           "/echo",
           "/nodes",
           "/nodesmc",
           "/nodemt",
           # ... etc
       ]
       return "\n".join(help_lines)
   ```

2. **`_format_help_telegram()`** - Line 602
   - **Purpose**: Detailed help text for Telegram (no size limit)
   - **Used by**: Telegram bot commands
   - **Format**: Rich text with sections, descriptions, examples
   
   ```python
   def _format_help_telegram(self):
       """Format aide détaillée pour Telegram (sans contrainte de taille)"""
       help_text = textwrap.dedent("""
           📖 AIDE COMPLÈTE - BOT MESHTASTIC
           
           🤖 CHAT IA
           • /bot <question> → Conversation avec l'IA
           # ... detailed help
       """)
       return help_text
   ```

### Handler Method
**`handle_help()`** - Line 536
- Routes to appropriate format based on channel (mesh vs Telegram)
- Handles throttling
- Sends response via MessageSender

```python
def handle_help(self, sender_id, sender_info):
    """Gérer la commande /help"""
    if not self.sender.check_throttling(sender_id, sender_info):
        return
    
    help_text = self._format_help()  # Mesh format
    self.sender.send_single(help_text, sender_id, sender_info)
```

### Companion Mode Commands

The list of commands supported in MeshCore companion mode (when Meshtastic is not available) is defined in `handlers/message_router.py` - Line 34:

```python
# Commandes supportées en mode companion (non-Meshtastic)
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
    '/rebootpi', # Redémarrage Pi (authentifié)
    '/nodesmc'   # Contacts MeshCore (base SQLite, pas Meshtastic)
]
```

## Customization Guide

### To modify MeshCore help text:

1. **Edit compact help** (for mesh/LoRa):
   - File: `handlers/command_handlers/utility_commands.py`
   - Method: `_format_help()` at line 575
   - Keep under 180 characters total for LoRa compatibility

2. **Edit detailed help** (for Telegram):
   - File: `handlers/command_handlers/utility_commands.py`
   - Method: `_format_help_telegram()` at line 602
   - No size limit, can be detailed

3. **Modify companion mode commands**:
   - File: `handlers/message_router.py`
   - Variable: `companion_commands` at line 34
   - Add/remove commands supported without Meshtastic

### Example Customization

To add a note about MeshCore mode to help text:

```python
def _format_help(self):
    """Formater l'aide des commandes"""
    help_lines = [
        "=== AIDE BOT ===",
        "/bot - Chat IA",
        "/echo - Diffuser msg",
        "/sys - Info système",
        "/help - Cette aide",
        "",
        "Mode: MeshCore",  # ← Add mode indicator
    ]
    return "\n".join(help_lines)
```

## Architecture Notes

- **MessageRouter** (`handlers/message_router.py`) orchestrates all command routing
- **UtilityCommands** handles help, echo, weather, etc.
- **NetworkCommands** handles nodes, neighbors, trace, etc.
- **AICommands** handles bot/IA AI queries
- **SystemCommands** handles sys, reboot, etc.

All command handlers share the same **MessageSender** for consistent throttling and chunking behavior.
