# export_nodes_from_db.py - Node Information Export Tool

## Overview

Export node information from MeshBot's local files (`node_names.json` and `traffic_history.db`) to JSON format compatible with `meshtastic --info` output.

This script **replaces** the TCP-based `meshtastic --host <ip> --info` command, eliminating TCP connection conflicts when the bot is running.

## Features

- ✅ **No TCP connection needed** - Reads from local files maintained by the bot
- ✅ **Compatible output** - Generates JSON in the same format as `meshtastic --info`
- ✅ **Data enrichment** - Combines node names, GPS positions, SNR, lastHeard, hopsAway, and neighbors
- ✅ **Graceful degradation** - Works even if database is unavailable
- ✅ **Clean output** - JSON on stdout, logs on stderr
- ✅ **Map visualization** - Includes hopsAway for node coloring and neighbors for link drawing

## Data Sources

### Primary Source: `node_names.json`
Maintained by `NodeManager` in the bot, contains:
- Node ID (numeric)
- Long name (user-assigned name)
- GPS coordinates (latitude, longitude, altitude)
- Last update timestamp

### Secondary Source: `traffic_history.db` (optional)
SQLite database maintained by `TrafficPersistence`, provides enrichment:
- **SNR** (Signal-to-Noise Ratio) from recent direct packets
- **lastHeard** (timestamp of most recent packet)
- **hopsAway** (minimum hop count from packets table) - enables node color-coding on map
- **neighbors** (neighbor relationships from neighbors table) - enables link drawing on map

## Usage

### Basic Usage
```bash
# Export using default paths (relative to map/ directory)
./export_nodes_from_db.py > info.json

# Logs appear on stderr (can be redirected separately)
./export_nodes_from_db.py > info.json 2> export.log
```

### Custom Paths
```bash
# Specify custom paths
./export_nodes_from_db.py /path/to/node_names.json /path/to/traffic_history.db 48 > info.json

# Export with 72 hours of data (instead of default 48)
./export_nodes_from_db.py ../node_names.json ../traffic_history.db 72 > info.json
```

### Help
```bash
./export_nodes_from_db.py --help
```

## Output Format

The output is compatible with `meshtastic --info` format:

```json
{
  "Nodes in mesh": {
    "!16fad3dc": {
      "num": 385503196,
      "user": {
        "id": "!16fad3dc",
        "longName": "tigro G2 PV",
        "shortName": "TIGR",
        "hwModel": "UNKNOWN"
      },
      "position": {
        "latitude": 47.2496,
        "longitude": 6.0248,
        "altitude": 350
      },
      "snr": 9.75,
      "lastHeard": 1733175600,
      "hopsAway": 0,
      "neighbors": [
        {
          "nodeId": "!075bcd15",
          "snr": 8.5
        }
      ]
    }
  }
}
```

### Field Descriptions

- `num`: Node ID as integer
- `user.id`: Node ID in hex format with `!` prefix
- `user.longName`: Full node name
- `user.shortName`: Abbreviated name (first 4 chars)
- `user.hwModel`: Hardware model (always "UNKNOWN" from node_names.json)
- `position`: GPS coordinates (only if available)
  - `latitude`: Decimal degrees
  - `longitude`: Decimal degrees
  - `altitude`: Meters above sea level (optional)
- `snr`: Signal quality in dB (only if in database)
- `lastHeard`: Unix timestamp of last packet (only if in database)
- `hopsAway`: Minimum hop count to reach this node (only if in database) - **NEW**
  - 0 = direct connection
  - 1+ = relay through other nodes
  - Used by map.html to color-code nodes by distance
- `neighbors`: Array of neighbor nodes (only if in database) - **NEW**
  - `nodeId`: Neighbor node ID in hex format with `!` prefix
  - `snr`: Signal quality to neighbor in dB
  - Used by map.html to draw connection lines between nodes

## Integration with infoup_db.sh

The script is used in `infoup_db.sh` to generate map data:

```bash
# In infoup_db.sh
/home/dietpi/bot/map/export_nodes_from_db.py "$NODE_NAMES_FILE" "$DB_PATH" 48 > $JSON_FILE
```

## Error Handling

### node_names.json Not Found
```
❌ Fichier node_names.json introuvable: /path/to/node_names.json
⚠️  Le bot n'a peut-être pas encore créé ce fichier.
💡 Astuce: Attendez que le bot reçoive quelques paquets NODEINFO_APP
```

**Solution**: Wait for the bot to receive NODEINFO_APP packets and create the file.

### Database Not Found
```
⚠️  Base de données SQLite introuvable: /path/to/traffic_history.db
💡 Export uniquement depuis node_names.json
```

**Solution**: Script continues with node data only (no SNR/lastHeard enrichment).

### Empty node_names.json
If the bot has not yet collected any node information, the output will be:
```json
{
  "Nodes in mesh": {}
}
```

## Comparison with meshtastic --info

### Old Approach (TCP-based)
```bash
meshtastic --host 192.168.1.38 --info > info.json
```

**Problems:**
- ❌ Requires TCP connection to Meshtastic node
- ❌ Conflicts with bot's TCP connection (unique session limit)
- ❌ Requires meshtastic CLI tool installed
- ❌ Output needs cleaning with `info_json_clean.py`

### New Approach (File-based)
```bash
./export_nodes_from_db.py ../node_names.json ../traffic_history.db 48 > info.json
```

**Advantages:**
- ✅ No TCP connection needed
- ✅ No conflicts with bot
- ✅ No cleanup needed (direct JSON output)
- ✅ Enriched with historical SNR/lastHeard data
- ✅ Works even if meshtastic CLI not installed

## Testing

Run the test script to verify functionality:

```bash
./test_export_nodes.sh
```

This creates sample data and validates:
- JSON syntax
- Output structure
- Node count
- Required fields

## See Also

- `export_neighbors_from_db.py` - Export neighbor relationships
- `infoup_db.sh` - Complete map update script
- `README_NEIGHBORS.md` - Full documentation
- `node_manager.py` - Source code for node_names.json maintenance
