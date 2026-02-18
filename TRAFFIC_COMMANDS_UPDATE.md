# Traffic Commands Update

## Overview

This document describes the addition of network-specific traffic commands to complement the existing traffic reporting functionality.

## Problem Statement

Following the pattern established with the `/echo` command split, we needed network-specific variants for traffic commands to allow users to view messages from specific networks in dual mode.

## Solution

### New Commands

Three commands are now available for viewing public message history:

1. **`/trafic [hours]`** - Show all public messages (existing, unchanged)
   - Shows messages from both Meshtastic and MeshCore networks
   - Default: 8 hours, max: 24 hours
   
2. **`/trafficmt [hours]`** - Show only Meshtastic public messages (NEW)
   - Filters to show only Meshtastic sources: `'local'`, `'tcp'`, `'tigrog2'`
   - Shows source breakdown (Serial vs TCP)
   - Visual icons: 📻 (Serial), 📡 (TCP)
   
3. **`/trafficmc [hours]`** - Show only MeshCore public messages (existing)
   - Filters to show only MeshCore source: `'meshcore'`
   - Already existed, unchanged

## Technical Implementation

### File Changes

#### 1. `traffic_monitor.py`
Added new method `get_traffic_report_mt()`:

```python
def get_traffic_report_mt(self, hours=8):
    """
    Afficher l'historique complet des messages publics Meshtastic
    
    Filters messages by Meshtastic sources: 'local', 'tcp', 'tigrog2'
    Returns formatted report with source breakdown and icons
    """
    # Filter to Meshtastic sources only
    meshtastic_sources = {'local', 'tcp', 'tigrog2'}
    recent_messages = [
        msg for msg in self.public_messages
        if msg['timestamp'] >= cutoff_time 
        and msg.get('source') in meshtastic_sources
    ]
    
    # Format with source icons
    # 📻 = Serial (local)
    # 📡 = TCP (tcp, tigrog2)
```

**Key features:**
- Filters by source using set membership check
- Shows per-source counts (Serial, TCP, TCP-tigrog2)
- Adds visual icons for quick identification
- Handles long reports (>3800 chars) by limiting to last 20 messages

#### 2. `handlers/command_handlers/stats_commands.py`
Added business logic wrapper:

```python
def get_traffic_report_mt(self, hours=8):
    """
    Générer le rapport de trafic public Meshtastic
    
    Wrapper around traffic_monitor with error handling
    """
    if not self.traffic_monitor:
        return "❌ Traffic monitor non disponible"
    
    return self.traffic_monitor.get_traffic_report_mt(hours)
```

#### 3. `telegram_bot/commands/stats_commands.py`
Added Telegram command handler:

```python
async def trafficmt_command(self, update: Update, 
                            context: ContextTypes.DEFAULT_TYPE):
    """Commande /trafficmt pour historique messages publics Meshtastic"""
    # Parse hours parameter (default 8, max 24)
    # Execute in thread to avoid blocking
    # Return formatted response
```

#### 4. `telegram_integration.py`
Registered new command:

```python
self.application.add_handler(
    CommandHandler("trafficmt", self.stats_commands.trafficmt_command)
)
```

#### 5. `telegram_bot/commands/basic_commands.py`
Updated help text:

```python
f"• /trafic [heures] - Tous messages publics\n"
f"• /trafficmt [heures] - Messages Meshtastic\n"
f"• /trafficmc [heures] - Messages MeshCore\n"
```

## Source Classification

Messages are categorized by their source:

### Meshtastic Sources
- **`'local'`** - Messages from serial-connected node (📻 icon)
- **`'tcp'`** - Messages from TCP-connected router (📡 icon)
- **`'tigrog2'`** - Messages from specific TCP node tigrog2 (📡 icon)

### MeshCore Sources
- **`'meshcore'`** - Messages from MeshCore network (🔗 icon)

## Usage Examples

### Example 1: View All Messages
```
/trafic
/trafic 12
```

Output shows all messages from all networks:
```
📊 **MESSAGES PUBLICS (8h)**
========================================
Total: 10 messages

Par source:
  📻 Serial (Meshtastic): 3
  📡 TCP (Meshtastic): 3
  🔗 MeshCore: 4

[21:38:18] 📻 [tigro] Test serial 1
[22:31:38] 📡 [router1] Test TCP 1
[23:08:18] 🔗 [mcnode1] Test MeshCore 1
...
```

### Example 2: View Only Meshtastic Messages
```
/trafficmt
/trafficmt 12
```

Output shows only Meshtastic messages:
```
📡 **MESSAGES PUBLICS MESHTASTIC (8h)**
========================================
Total: 6 messages

  📻 Serial: 3
  📡 TCP: 3

[21:38:18] 📻 [tigro] Test serial 1
[22:31:38] 📡 [router1] Test TCP 1
[22:48:18] 📡 [router2] Hello from TCP
...
```

### Example 3: View Only MeshCore Messages
```
/trafficmc
/trafficmc 12
```

Output shows only MeshCore messages:
```
🔗 **MESSAGES PUBLICS MESHCORE (8h)**
========================================
Total: 4 messages

[23:08:18] [mcnode1] Test MeshCore 1
[23:18:18] [mcnode2] Hello from MeshCore
...
```

## Use Cases

### Use Case 1: Debugging Network Issues
When troubleshooting Meshtastic connectivity issues, use `/trafficmt` to see only Meshtastic messages and verify which sources are working.

### Use Case 2: Monitoring Specific Network
In dual mode, monitor activity on a specific network without noise from the other network.

### Use Case 3: Source Analysis
Use `/trafficmt` to see the breakdown between Serial and TCP sources to understand your network topology.

### Use Case 4: Complete Overview
Use `/trafic` to see all messages from all networks for a complete picture.

## Benefits

### 1. Network-Specific Visibility
✅ Can view messages from each network independently
✅ Useful for debugging and monitoring specific networks
✅ Reduces noise when analyzing a specific network

### 2. Source Breakdown
✅ Shows which Meshtastic sources are active (Serial vs TCP)
✅ Helps understand network topology
✅ Identifies which connection methods are working

### 3. Visual Icons
✅ Quick visual identification of source type
✅ 📻 = Serial, 📡 = TCP, 🔗 = MeshCore
✅ Easier to scan large message lists

### 4. Consistent with Echo Commands
✅ Follows same pattern as `/echo`, `/echomt`, `/echomc`
✅ Predictable user experience
✅ Easy to understand for users familiar with echo commands

## Key Differences from Echo Commands

Unlike the echo commands which had issues with REMOTE_NODE_HOST and connection management:

1. **Read-Only**: Traffic commands only READ data, don't send anything
2. **No Connection Issues**: No need to create or manage connections
3. **Simpler Implementation**: Just filtering existing data by source
4. **No Interface Routing**: Don't need dual_interface routing logic
5. **Data Already Categorized**: Source tracking already existed

## Testing

### Demo Script
Run `demos/demo_traffic_commands.py` to see the filtering in action:

```bash
python3 demos/demo_traffic_commands.py
```

Output demonstrates:
1. `/trafic` - Shows all 10 messages (6 Meshtastic + 4 MeshCore)
2. `/trafficmt` - Shows only 6 Meshtastic messages
3. `/trafficmc` - Shows only 4 MeshCore messages

## Configuration

No configuration changes needed. Commands work with any setup:
- Serial-only Meshtastic
- TCP-only Meshtastic
- MeshCore-only
- Dual mode (Meshtastic + MeshCore)

## Migration

### For Users
No action needed. New command is additive:
- Existing `/trafic` still works the same
- Existing `/trafficmc` unchanged
- New `/trafficmt` available for Meshtastic filtering

### For Developers
If extending traffic reporting:
- Follow same pattern: filter by `msg.get('source')`
- Meshtastic sources: `{'local', 'tcp', 'tigrog2'}`
- MeshCore sources: `{'meshcore'}`

## Troubleshooting

### "📭 Aucun message public Meshtastic dans les Xh"

**Cause:** No Meshtastic messages received in the time period
**Solution:** 
- Check Meshtastic node is connected
- Verify time period is long enough
- Try `/trafic` to see if MeshCore messages exist

### "📭 Aucun message public MeshCore dans les Xh"

**Cause:** No MeshCore messages received in the time period
**Solution:**
- Check MeshCore is enabled and connected
- Verify time period is long enough
- Try `/trafic` to see if Meshtastic messages exist

## Future Enhancements

Possible improvements:

1. **Source-Specific Commands**: `/trafficserial`, `/traffictcp`
2. **Combined Filters**: `/trafficmt --source=tcp`
3. **Export Options**: `/trafficmt --export`
4. **Search/Filter**: `/trafficmt --search="keyword"`

## See Also

- `ECHO_COMMANDS_UPDATE.md` - Similar pattern for echo commands
- `demos/demo_traffic_commands.py` - Interactive demonstration
- `traffic_monitor.py` - Implementation source code
- `CLAUDE.md` - Overall bot architecture
