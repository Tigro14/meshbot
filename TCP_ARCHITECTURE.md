# TCP Architecture Documentation

## Overview

This document clarifies the network connection architecture used in MeshBot. The codebase uses **different network stacks for different purposes**, which is intentional and appropriate.

## Network Stack Separation

### 1. Meshtastic Node Connection Stack

**Files:**
- `tcp_interface_patch.py` - CPU-optimized TCP interface for Meshtastic
- `safe_tcp_connection.py` - Context manager wrapper for temporary connections

**Purpose:** 
Dedicated to **Meshtastic protocol communication** on port 4403.

**Why Separated:**
- Meshtastic uses a proprietary protocol over TCP (protobuf-based)
- Requires CPU optimization (original meshtastic library had 78% CPU usage due to busy-waiting)
- Needs reconnection handling specific to mesh network behavior
- Long-lived connection that needs health monitoring

### 2. External Services Stack

**Different services use appropriate libraries:**

| Service | Library | Protocol | File |
|---------|---------|----------|------|
| ESPHome | `requests` | HTTP REST | `esphome_client.py` |
| Weather (wttr.in) | `curl` subprocess | HTTP | `utils_weather.py` |
| Blitzortung | `paho-mqtt` | MQTT | `blitz_monitor.py` |
| Météo-France | `beautifulsoup4` | HTTP + HTML scraping | `vigilance_scraper.py` |

**Why Different:**
- Each service uses its standard protocol (HTTP, MQTT)
- Standard Python libraries handle these protocols well
- No CPU optimization needed (short-lived requests)
- Retry logic is handled per-service as needed

## File Details

### tcp_interface_patch.py

```
OptimizedTCPInterface
├── Extends: meshtastic.tcp_interface.TCPInterface
├── Purpose: CPU-optimized Meshtastic TCP connection
├── Key Fix: Uses select() instead of busy-waiting in _readBytes()
├── CPU Impact: Reduces from 78% to <5%
└── Used By: main_bot.py (main interface), system_monitor.py
```

**Key Method:**
```python
def _readBytes(self, length):
    """
    Uses select() for efficient blocking reads.
    Returns empty bytes on timeout with small sleep to prevent tight loops.
    """
```

**Additional Features:**
- `install_threading_exception_filter()`: Suppresses normal network errors from Meshtastic threads
- Thread exception filtering for cleaner logs

### safe_tcp_connection.py

```
SafeTCPConnection
├── Type: Context Manager
├── Purpose: Safe temporary connections to Meshtastic nodes
├── Uses: OptimizedTCPInterface internally
└── Features:
    ├── Automatic connection/disconnection
    ├── Connection timing tracking
    └── Error handling with cleanup
```

**Usage Patterns:**
```python
# For temporary queries (e.g., getting remote node list)
with SafeTCPConnection("192.168.1.100") as interface:
    nodes = interface.nodes
    
# Helper functions
send_text_to_remote(hostname, text)
quick_tcp_command(hostname, command)
broadcast_message(hostname, message)
test_connection(hostname)
```

**Used By:**
- `remote_nodes_client.py` - Querying remote mesh nodes
- Temporary operations that don't need persistent connection

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         MeshBot                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │            MESHTASTIC NODE CONNECTION                     │ │
│  │                   (Port 4403)                             │ │
│  │                                                           │ │
│  │  ┌─────────────────────┐   ┌───────────────────────────┐ │ │
│  │  │ tcp_interface_patch │   │  safe_tcp_connection      │ │ │
│  │  │ OptimizedTCPInterface│   │  SafeTCPConnection        │ │ │
│  │  │                     │   │  (Context Manager)        │ │ │
│  │  │ CPU: 78% → <5%      │   │  Uses OptimizedTCPInterface│ │ │
│  │  └─────────────────────┘   └───────────────────────────┘ │ │
│  │            │                          │                   │ │
│  │            ▼                          ▼                   │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │           Meshtastic Protocol (protobuf)            │ │ │
│  │  │              meshtastic.tcp_interface               │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              EXTERNAL SERVICES                            │ │
│  │           (Standard Protocols)                            │ │
│  │                                                           │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────────┐│ │
│  │  │  ESPHome   │ │  Weather   │ │   Blitzortung          ││ │
│  │  │  (HTTP)    │ │  (HTTP)    │ │   (MQTT)               ││ │
│  │  │  requests  │ │  curl      │ │   paho-mqtt            ││ │
│  │  └────────────┘ └────────────┘ └────────────────────────┘│ │
│  │                                                           │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │               Météo-France Vigilance               │  │ │
│  │  │               (HTTP + HTML scraping)               │  │ │
│  │  │               beautifulsoup4 + lxml                │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Why Not Merge All TCP Code?

**The stacks are intentionally separated because:**

1. **Different Protocols**: Meshtastic uses protobuf over raw TCP; others use HTTP/MQTT
2. **Different Requirements**: Meshtastic needs CPU optimization; HTTP requests don't
3. **Different Libraries**: Each external service has its own well-tested Python library
4. **Maintainability**: Separation allows independent updates and debugging
5. **Reliability**: A bug in one stack doesn't affect others

## TCP Health Monitoring

The main Meshtastic TCP connection has dedicated health monitoring:

```
TCP_HEALTH_CHECK_INTERVAL = 30s   # Check every 30 seconds
TCP_SILENT_TIMEOUT = 60s          # Reconnect if no packet for 60s
```

**Thread: TCPHealthMonitor**
- Runs in background when CONNECTION_MODE='tcp'
- Monitors packet reception timestamps
- Forces reconnection on detected silence

**TCP Keepalive (Socket Level)**
Since v2025.11, OptimizedTCPInterface enables TCP keepalive by default:
```
tcp_keepalive_idle = 30s     # Start keepalive after 30s idle
tcp_keepalive_interval = 10s # Send probe every 10s
tcp_keepalive_count = 3      # Consider dead after 3 failed probes
```

This helps detect dead connections faster at the OS level, complementing
the application-level health monitor.

## Known Issues & Fixes

### 2-Minute Silence Problem (Issue Referenced)

**Symptom:** Every 3 minutes, 2 minutes of silence on TCP connection.

**Potential Causes:**
1. **Meshtastic node WiFi sleep** - The router node may have WiFi power saving enabled
2. **TCP keepalive not working** - Silent socket deaths not detected
3. **Network infrastructure issues** - Router/switch timeouts

**Current Mitigations:**
- TCP keepalive enabled (detects dead connections in ~60s)
- Health monitor with 60s silence detection
- Automatic reconnection on socket death
- 30s health check interval (reduced from 60s)

**Recommendations:**
1. Check router node settings: Disable WiFi sleep/power saving
2. Verify network path: No aggressive NAT timeouts
3. Monitor with `DEBUG_MODE=True` to see packet timestamps

## Future Considerations

### Potential Improvements

1. **Connection Pooling**: For RemoteNodesClient queries
2. **Metrics**: Track connection uptime and reconnection frequency
3. **Adaptive Keepalive**: Adjust keepalive parameters based on network conditions

### NOT Recommended

- Merging HTTP/MQTT into Meshtastic TCP stack (different protocols)
- Using raw sockets for HTTP services (reinventing the wheel)
- Sharing connection state between services (isolation is good)

## Related Files

- `main_bot.py` - Main bot using OptimizedTCPInterface
- `system_monitor.py` - Uses OptimizedTCPInterface for tigrog2 monitoring
- `remote_nodes_client.py` - Uses SafeTCPConnection for node queries
- `esphome_client.py` - HTTP requests to ESPHome
- `utils_weather.py` - curl subprocess for weather
- `blitz_monitor.py` - MQTT client for lightning data
- `vigilance_scraper.py` - HTTP + BeautifulSoup for weather alerts

## Debugging

### Enable Debug Mode
```python
# In config.py
DEBUG_MODE = True
```

### Monitor TCP Health
```bash
# Watch logs for TCP health checks
journalctl -u meshbot -f | grep -i "tcp\|socket\|health"
```

### Test TCP Connection
```bash
# Direct connection test
python3 tcp_interface_patch.py 192.168.1.38 4403
```

### Check Network Path
```bash
# Verify TCP connectivity
nc -vz 192.168.1.38 4403
```
