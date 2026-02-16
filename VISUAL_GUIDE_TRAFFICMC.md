# Visual Guide: /trafficmc Command

## Command Overview

The `/trafficmc` command displays MeshCore traffic history on Telegram, filtering out Meshtastic traffic.

## Usage Examples

### Basic Usage
```
/trafficmc
```
Shows last 8 hours of MeshCore traffic (default)

### With Time Parameter
```
/trafficmc 4
```
Shows last 4 hours of MeshCore traffic

```
/trafficmc 24
```
Shows last 24 hours of MeshCore traffic (maximum)

## Output Examples

### Example 1: Normal MeshCore Traffic

**Input:** `/trafficmc 8`

**Output:**
```
🔗 **MESSAGES PUBLICS MESHCORE (8h)**
========================================
Total: 5 messages

[10:44:18] [Node1] Hello from MeshCore
[10:45:23] [Node2] Testing connectivity
[10:46:45] [Node3] Signal check
[11:23:12] [Node1] Weather update
[11:45:38] [Node4] All systems operational
```

### Example 2: No MeshCore Traffic

**Input:** `/trafficmc`

**Output:**
```
📭 Aucun message public MeshCore dans les 8h
```

## Comparison with /trafic

### /trafic - Shows ALL Traffic (Meshtastic + MeshCore)
```
📨 **MESSAGES PUBLICS (8h)**
========================================
Total: 10 messages

[10:44:18] [MTNode1] Meshtastic message 1
[10:44:18] [MCNode1] MeshCore message 1
[10:44:18] [MTNode2] Meshtastic message 2
[10:44:18] [MCNode2] MeshCore message 2
...
```

### /trafficmc - Shows ONLY MeshCore Traffic
```
🔗 **MESSAGES PUBLICS MESHCORE (8h)**
========================================
Total: 5 messages

[10:44:18] [MCNode1] MeshCore message 1
[10:44:18] [MCNode2] MeshCore message 2
[10:44:18] [MCNode3] MeshCore message 3
...
```

## Icon Legend

- 🔗 = MeshCore traffic header
- 📨 = All traffic header (Meshtastic + MeshCore)
- 📭 = No messages found

## Message Format

Each message shows:
1. **Time** - HH:MM:SS format
2. **Sender** - Node name
3. **Content** - Message text

```
[10:44:18] [NodeName] Message content here
└─────┬───┘ └────┬───┘ └────────┬────────┘
      │          │               │
    Time      Sender          Content
```

## Feature Highlights

### 1. Automatic Filtering
- Only shows messages with `source='meshcore'`
- Excludes Meshtastic traffic (`source='local'`, `source='tcp'`)

### 2. Time Validation
- Hours parameter: 1-24
- Invalid values default to 8
- Examples: `/trafficmc abc` → uses 8h

### 3. Smart Truncation
- If output > 3800 chars, shows only last 20 messages
- Prevents Telegram message length errors
- Indicates total message count

### 4. Chronological Order
- Messages sorted by timestamp
- Oldest to newest
- Easy to follow conversation flow

## Use Cases

### Network Monitoring
Track MeshCore network activity separately from Meshtastic:
```
/trafficmc 24
```
Review full day of MeshCore traffic

### Troubleshooting
Check recent MeshCore connectivity:
```
/trafficmc 1
```
See last hour for immediate issues

### Activity Analysis
Compare traffic patterns:
```
/trafic 8       # All traffic
/trafficmc 8    # MeshCore only
```
Understand network usage distribution

## Command Location

Available in Telegram help via:
- `/help` - Full command list
- `/start` - Quick command reference

Listed under **📊 STATISTIQUES** section:
```
📊 STATISTIQUES
• /stats [sub] [params] - Statistiques réseau
• /trafic [heures] - Historique messages publics
• /trafficmc [heures] - Historique messages publics MeshCore
• /top [heures] [nombre] - Top talkers
```

## Technical Details

### Data Source
- Uses `TrafficMonitor.public_messages` deque
- Filters by `source` field at display time
- No additional storage required

### Performance
- Fast filtering (in-memory deque)
- No database queries for recent data
- Minimal CPU overhead

### Integration
- Works in dual-mode operation
- Compatible with existing traffic commands
- No conflicts with other commands

## Error Handling

### Traffic Monitor Unavailable
```
❌ Traffic monitor non disponible
```
System issue - check bot status

### Invalid Parameters
```
/trafficmc -5    → Uses default 8h
/trafficmc 100   → Capped at 24h
/trafficmc abc   → Uses default 8h
```

## Related Commands

- `/trafic [hours]` - All traffic (Meshtastic + MeshCore)
- `/stats traffic [hours]` - Alternative syntax for all traffic
- `/top [hours]` - Top talkers across both networks
- `/packets [hours]` - Packet distribution by type

## Developer Notes

- Method: `TrafficMonitor.get_traffic_report_mc(hours=8)`
- Telegram handler: `StatsCommands.trafficmc_command()`
- Business logic: `BusinessStatsCommands.get_traffic_report_mc()`
- Tests: `tests/test_trafficmc_command.py`
