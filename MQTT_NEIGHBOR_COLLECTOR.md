# MQTT Neighbor Collector

## Overview

The MQTT Neighbor Collector extends the bot's ability to map mesh network topology by subscribing to a Meshtastic MQTT server. This allows the bot to collect `NEIGHBORINFO_APP` packets from nodes beyond its direct radio range, creating a more complete picture of the network.

## Problem Statement

When relying solely on direct radio reception, the bot can only collect neighbor information from nodes within range. This limits network visibility and topology mapping. Many nodes in the mesh may be out of range but are still publishing their neighbor lists to MQTT.

## Solution

By subscribing to a Meshtastic MQTT server, the bot can:
1. Receive neighbor info from ALL nodes in the network (that publish to MQTT)
2. Build a complete network topology map
3. Complement direct radio-based neighbor collection
4. Store all data in the same SQLite `neighbors` table

## Architecture

```
┌─────────────────────────────────────────────┐
│           MeshBot (main_bot.py)             │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │   TrafficMonitor                   │    │
│  │   - Handles NEIGHBORINFO_APP       │    │
│  │     packets from radio             │    │
│  └───────────┬────────────────────────┘    │
│              │                               │
│              ▼                               │
│  ┌────────────────────────────────────┐    │
│  │   TrafficPersistence               │    │
│  │   - save_neighbor_info()           │◄───┼──┐
│  │   - load_neighbors()               │    │  │
│  │   - SQLite 'neighbors' table       │    │  │
│  └────────────────────────────────────┘    │  │
│              ▲                               │  │
│              │                               │  │
│  ┌───────────┴────────────────────────┐    │  │
│  │   MQTTNeighborCollector            │    │  │
│  │   - Subscribes to MQTT topics      │────┘  │
│  │   - Parses NEIGHBORINFO_APP JSON   │       │
│  │   - Background thread with retry   │       │
│  └────────────────────────────────────┘       │
│              ▲                                 │
└──────────────┼─────────────────────────────────┘
               │
        MQTT Connection
               │
               ▼
┌──────────────────────────────────────────────┐
│    Meshtastic MQTT Server                   │
│    (e.g., serveurperso.com:1883)            │
│                                              │
│  Topics: msh/+/+/2/json/+/NEIGHBORINFO_APP  │
└──────────────────────────────────────────────┘
```

## Configuration

Add to your `config.py`:

```python
# Configuration collecte voisins via MQTT Meshtastic
MQTT_NEIGHBOR_ENABLED = True  # Enable/disable MQTT neighbor collection
MQTT_NEIGHBOR_SERVER = "serveurperso.com"  # MQTT server address
MQTT_NEIGHBOR_PORT = 1883  # MQTT port (1883 standard, 8883 for TLS)
MQTT_NEIGHBOR_USER = "meshdev"  # MQTT username
MQTT_NEIGHBOR_PASSWORD = "your_password_here"  # MQTT password
MQTT_NEIGHBOR_TOPIC_ROOT = "msh"  # MQTT topic root (default: "msh")
```

## MQTT Topics

The collector subscribes to:

```
msh/+/+/2/json/+/NEIGHBORINFO_APP
```

This wildcard pattern matches:
- `msh` - Meshtastic topic root
- `+` - Any region (e.g., "eu_868", "us", "FR")
- `+` - Any channel (e.g., "LongFast", custom channels)
- `2` - Protocol version
- `json` - JSON format (not protobuf)
- `+` - Any node ID
- `NEIGHBORINFO_APP` - Neighbor info packet type

## Message Format

MQTT messages are in JSON format:

```json
{
  "from": 305419896,
  "to": 4294967295,
  "channel": 0,
  "type": "NEIGHBORINFO_APP",
  "sender": "!12345678",
  "payload": {
    "neighborinfo": {
      "nodeId": 305419896,
      "neighbors": [
        {
          "nodeId": 305419897,
          "snr": 8.5,
          "lastRxTime": 1234567890,
          "nodeBroadcastInterval": 900
        }
      ]
    }
  }
}
```

## Features

### 1. Automatic Connection Management
- Auto-connect on startup (if enabled)
- Auto-reconnect on connection loss
- Exponential backoff retry logic
- Graceful shutdown

### 2. Data Processing
- Parse JSON NEIGHBORINFO_APP messages
- Extract neighbor relationships
- Normalize node IDs to standard format (`!xxxxxxxx`)
- Save to SQLite via existing persistence layer

### 3. Statistics Tracking
```python
stats = mqtt_collector.get_stats()
# Returns:
{
    'connected': True/False,
    'messages_received': 42,
    'neighbor_packets': 38,
    'nodes_discovered': 15,
    'last_update': 1701234567.89
}
```

### 4. Status Reporting
```python
# Compact format (for LoRa)
report = mqtt_collector.get_status_report(compact=True)
# "👥 MQTT Neighbors 🟢 | Messages: 42 | Packets: 38 | Nœuds: 15"

# Detailed format (for Telegram)
report = mqtt_collector.get_status_report(compact=False)
# Multi-line detailed status with server info and stats
```

## Integration with Existing Features

### Database
The MQTT collector saves data to the same `neighbors` table used by direct radio collection:

```sql
CREATE TABLE neighbors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    node_id TEXT NOT NULL,
    neighbor_id TEXT NOT NULL,
    snr REAL,
    last_rx_time INTEGER,
    node_broadcast_interval INTEGER
)
```

### Commands
The `/neighbors` command shows data from both sources (radio + MQTT):

```
/neighbors           # All neighbors
/neighbors tigro     # Filter by node name
/neighbors F547F     # Filter by node ID
```

### Map Generation
The map generation scripts (`map/export_neighbors_from_db.py`) automatically include MQTT-collected data.

## Testing

Run the test suite:

```bash
python3 test_mqtt_neighbor_collector.py
```

Tests include:
1. JSON payload parsing
2. Database integration
3. Collector initialization
4. Message simulation

## Troubleshooting

### Connection Issues

If the collector fails to connect:

1. **Check server accessibility**:
   ```bash
   ping serveurperso.com
   telnet serveurperso.com 1883
   ```

2. **Verify credentials**:
   - Ensure `MQTT_NEIGHBOR_USER` and `MQTT_NEIGHBOR_PASSWORD` are correct
   - Check if the MQTT server requires authentication

3. **Check logs**:
   ```bash
   journalctl -u meshbot -f | grep "👥"
   ```

### No Data Received

If connected but no data:

1. **Verify topic subscription**:
   - Check that nodes are publishing to MQTT
   - Verify the topic pattern matches your network

2. **Enable debug mode**:
   ```python
   DEBUG_MODE = True  # in config.py
   ```

3. **Check node MQTT settings**:
   - Nodes must have MQTT uplink enabled
   - Verify JSON mode is enabled (not just protobuf)

### Performance

The MQTT collector is lightweight:
- Runs in background thread (daemon)
- Minimal CPU usage (event-driven)
- Memory bounded (deque with maxlen=100)
- No impact on main bot performance

## Benefits

1. **Extended Visibility**: See the entire network, not just nearby nodes
2. **Redundancy**: Complement direct radio collection
3. **Historical Data**: 48-hour retention in SQLite
4. **Automatic**: No manual intervention required
5. **Integration**: Works seamlessly with existing features

## Security Considerations

1. **Credentials**: Store MQTT password securely in `config.py` (not committed to git)
2. **Network**: MQTT traffic is typically unencrypted on port 1883
3. **Server Trust**: Only connect to trusted MQTT servers
4. **Data Validation**: All incoming messages are validated before processing

## Future Enhancements

Potential improvements:
- [ ] TLS/SSL support (port 8883)
- [ ] Protobuf message parsing (in addition to JSON)
- [ ] Filtering by region/channel
- [ ] Real-time topology visualization
- [ ] Alert on topology changes

## References

- **Meshtastic MQTT Documentation**: https://meshtastic.org/docs/software/mqtt/
- **Paho MQTT Python**: https://pypi.org/project/paho-mqtt/
- **Project Issue**: Collect MQTT info from neighbors

---

**Last Updated**: 2025-12-03
**Module**: `mqtt_neighbor_collector.py`
**Test Suite**: `test_mqtt_neighbor_collector.py`
