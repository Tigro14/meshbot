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

**TCP Keepalive (Socket Level) - DISABLED BY DEFAULT**

⚠️ **Warning:** TCP keepalive was found to cause connection instability with some
ESP32-based Meshtastic devices. It is **disabled by default** since v2025.11.26.

If needed for debugging, it can be enabled via constructor:
```python
interface = OptimizedTCPInterface(
    hostname="192.168.1.38",
    tcp_keepalive=True,  # Enable keepalive (not recommended)
    tcp_keepalive_idle=60,    # Start after 60s idle
    tcp_keepalive_interval=30, # Probe every 30s
    tcp_keepalive_count=5      # Dead after 5 failures
)
```

**Dead Socket Callback (Immediate Reconnection)**
When `recv()` returns empty bytes (connection closed by server), the 
`OptimizedTCPInterface` now triggers an immediate reconnection callback
instead of waiting for the health monitor to detect silence:

```python
# main_bot.py sets the callback:
interface.set_dead_socket_callback(self._reconnect_tcp_interface)

# When socket death is detected, callback is triggered immediately
# Reduces downtime from ~60s (waiting for health monitor) to ~10s
```

## Known Issues & Fixes

### 2-Minute Silence / ~3-Minute Disconnect Problem

**Symptom:** Every ~3 minutes, the TCP connection dies.

**Root Cause Found (v2025.11.26):**
The `OptimizedTCPInterface` was enabling TCP keepalive by default and setting
a socket timeout. These settings caused the ESP32-based Meshtastic node to
close the connection prematurely.

**Fix:**
- Disabled TCP keepalive by default
- Removed socket timeout setting (keep default blocking behavior)
- Keep only the `select()` optimization for CPU efficiency
- The standard `meshtastic.TCPInterface` works fine without these settings

**Verification:**
Use the diagnostic tool to compare modes:
```bash
# Standard TCPInterface (like CLI) - should work
python3 diag_tcp_connection.py 192.168.1.38 --duration 600

# OptimizedTCPInterface (like bot) - should also work now
python3 diag_tcp_connection.py 192.168.1.38 --optimized --duration 600
```

**Current Mitigations:**
- **Immediate reconnection callback** - Triggers reconnection as soon as socket death is detected
- Health monitor with 60s silence detection (backup)
- 30s health check interval

**Previous Recommendations (if issue persists):**
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
