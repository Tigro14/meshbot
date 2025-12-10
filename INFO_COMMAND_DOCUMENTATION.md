# `/info` Command Implementation

## Overview

The `/info <node>` command provides comprehensive information about a specific Meshtastic node, including GPS position, signal metrics, and mesh statistics.

## Usage

### Basic Usage
```
/info <node_name_or_id>
```

### Examples
```
/info tigrog2          # By exact name
/info tigro            # By partial name
/info F547FABC         # By full hex ID
/info F547F            # By partial hex ID
/info !F547FABC        # With Meshtastic prefix
```

### Broadcast Support
The `/info` command can be used in broadcast mode to share node information publicly on the mesh network.

## Output Format

### Compact Format (Mesh - ≤180 chars)
Used for LoRa mesh transmission with strict character limits.

**Example:**
```
ℹ️ tigrog2 (!f547fabc) | 📍 47.2346,6.8901 | ⛰️ 520m | ↔️ 12.3km | 📶 -87dB SNR8.2 | ⏱️ 2h ago | 📊 1234pkt
```

**Fields (when available):**
- Node name and ID
- GPS coordinates (latitude, longitude)
- Altitude
- Distance from bot
- Signal strength (RSSI, SNR)
- Last heard time
- Total packets received

### Detailed Format (Telegram/CLI)
Used for platforms without character limits.

**Example:**
```
ℹ️ INFORMATIONS NŒUD
━━━━━━━━━━━━━━━━━━━━
📛 Nom: tigrog2
🆔 ID: !f547fabc (0xf547fabc)
🏷️ Short: TGR2
🖥️ Model: TLORA_V2_1_1P6

📍 POSITION GPS
   Latitude: 47.234567
   Longitude: 6.890123
   Altitude: 520m
   Distance: 12.3km

📶 SIGNAL
   RSSI: -87dBm 📶
   Qualité: Très bonne
   SNR: 8.2 dB
   Distance (est): 300m-1km

⏱️ DERNIÈRE RÉCEPTION: il y a 2h

📊 STATISTIQUES MESH
   Paquets totaux: 1234
   Types de paquets:
     • 💬 Messages: 456
     • 📍 Position: 123
     • ℹ️ NodeInfo: 45
     • 📊 Télémétrie: 67
   Télémétrie:
     • Batterie: 85%
     • Voltage: 4.15V
   Premier vu: il y a 7d
   Dernier vu: il y a 2h
```

## Information Displayed

### Always Available
- **Node Name**: LongName from node database
- **Node ID**: Hex format with Meshtastic prefix

### When Available
- **Short Name**: 4-character short identifier
- **Hardware Model**: Device hardware model (e.g., TLORA_V2_1_1P6)
- **GPS Position**: Latitude, longitude, altitude
- **Distance**: GPS-calculated or RSSI-estimated distance from bot
- **Signal Metrics**: RSSI, SNR, signal quality description
- **Last Heard**: Time since last packet received
- **Mesh Statistics**: 
  - Total packets received
  - Breakdown by packet type
  - Telemetry data (battery, voltage)
  - First/last seen timestamps

## Node Search Logic

The command uses a two-tier search strategy:

### Priority 1: Local Database (node_manager)
- Fast, no network overhead
- Searches node names database (SQLite)
- Supports exact and partial matching

### Priority 2: Remote TCP Query
- Fallback if node not found locally
- Queries remote node via TCP (tigrog2)
- Higher latency but broader coverage

### Search Matching
- **Exact Match**: Prioritized over partial matches
- **Partial Match**: Case-insensitive substring matching
- **ID Formats**: Supports with/without leading zeros, with/without `!` prefix

## Error Handling

### Missing Argument
```
Input: /info
Output: Usage: /info <node_name>
```

### Node Not Found
```
Input: /info NonExistent
Output: ❌ Nœud 'NonExistent' introuvable
```

### Multiple Matches
When multiple nodes match, the first match is used. Future enhancement could list all matches.

## Implementation Details

### Threading
- Uses daemon thread for non-blocking execution
- Prevents blocking the message processing loop
- Named thread: "NodeInfo" for debugging

### Format Detection
- Checks sender info string for "telegram" or "cli"
- Presence → Detailed format
- Absence → Compact format (mesh)

### Data Sources
1. **node_manager.node_names**: Local node database with GPS, names, hardware info
2. **remote_nodes_client**: TCP query to remote node for additional data
3. **traffic_monitor.node_packet_stats**: Mesh statistics (packets, telemetry)

### Signal Quality Icons
Uses SNR-based icons:
- 🟢 SNR ≥ 10 (Excellent)
- 🟡 SNR ≥ 5 (Good)
- 🟠 SNR ≥ 0 (Fair)
- 🔴 SNR ≥ -5 (Poor)
- ⚫ SNR < -5 (Very Poor)
- 📶 SNR unknown

## Code Structure

### Handler Method
```python
def handle_info(self, message, sender_id, sender_info, is_broadcast=False)
```

### Helper Methods
- `_find_node(search_term)`: Node lookup with exact/partial matching
- `_format_info_compact(node_data, node_stats)`: Compact output (≤180 chars)
- `_format_info_detailed(node_data, node_stats)`: Detailed output

### Integration Points
- **Message Router**: Routes `/info` messages to handler
- **Broadcast Support**: Included in `broadcast_commands` list
- **Help Text**: Listed in both compact and detailed help

## Testing

### Automated Checks
- Syntax validation: ✅
- Feature presence: ✅
- Routing configuration: ✅
- Help text inclusion: ✅

### Manual Testing Scenarios
1. Query by exact name
2. Query by partial name
3. Query by full hex ID
4. Query by partial hex ID
5. Query with Meshtastic prefix
6. Query non-existent node (error handling)
7. Command without argument (usage message)
8. Broadcast mode
9. Private message mode
10. Compact format verification (≤180 chars)
11. Detailed format verification

## Performance Considerations

- **Thread-based**: Non-blocking, doesn't delay message processing
- **Two-tier search**: Local DB first, TCP fallback
- **Cached data**: Uses existing node database, no extra polling
- **Minimal overhead**: Reuses existing data structures

## Future Enhancements

### Potential Improvements
1. **Multi-match listing**: Show all matching nodes when ambiguous
2. **Cache optimization**: TTL-based caching for remote queries
3. **Selective fields**: Allow users to request specific fields only
4. **Export format**: JSON/CSV export option
5. **Historical data**: Show node position/signal history over time
6. **Comparison mode**: Compare two nodes side-by-side

## Related Commands

- `/my`: Show your own signal metrics
- `/trace <node>`: Traceroute to a node
- `/nodes`: List all direct nodes
- `/neighbors [node]`: Show neighbor relationships
- `/propag`: Show longest radio links

## Security Considerations

- No authentication required (public information)
- No data modification (read-only)
- Thread-safe implementation
- Input sanitization (strips special characters)
- No SQL injection risk (uses parameterized queries internally)
- No remote code execution risk (no eval/exec)

## Dependencies

### External Libraries
- None (uses only standard library and existing bot modules)

### Internal Modules
- `node_manager`: Node database and GPS calculations
- `traffic_monitor`: Mesh statistics
- `remote_nodes_client`: TCP queries
- `utils`: Formatting utilities (truncate_text, format_elapsed_time, get_signal_quality_icon)
- `signal_utils`: Signal quality functions (estimate_rssi_from_snr, get_signal_quality_description)
