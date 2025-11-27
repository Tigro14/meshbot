# TCP Architecture Documentation

## Overview

This document clarifies the network connection architecture used in MeshBot. The codebase uses **different network stacks for different purposes**, which is intentional and appropriate.

## Network Stack Separation

### 1. Meshtastic Node Connection Stack

**Files:**
- `tcp_interface_patch.py` - TCPInterface with dead socket callback for fast reconnection
- `safe_tcp_connection.py` - Context manager wrapper for temporary connections

**Purpose:** 
Dedicated to **Meshtastic protocol communication** on port 4403.

**Why Separated:**
- Meshtastic uses a proprietary protocol over TCP (protobuf-based)
- Needs reconnection handling specific to mesh network behavior
- Long-lived connection that needs health monitoring
- Dead socket callback for immediate reconnection

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
├── Purpose: TCPInterface with dead socket callback
├── Key Addition: Callback for immediate reconnection on socket death
├── Socket Config: IDENTICAL to standard TCPInterface (no modifications)
└── Used By: main_bot.py (main interface), system_monitor.py
```

**CRITICAL DESIGN NOTE:**
After extensive testing, we found that ANY modification to socket behavior
(select(), timeouts, TCP_NODELAY, keepalive) causes the ESP32-based Meshtastic
node to close connections prematurely after ~2.5 minutes.

Therefore, this implementation uses the **EXACT same blocking recv() approach**
as the standard TCPInterface. The ONLY addition is the dead socket callback.

**Key Method:**
```python
def _readBytes(self, length):
    """
    Simple blocking recv() - IDENTICAL to standard TCPInterface.
    The ONLY addition: triggers callback when socket is dead.
    """
    data = self.socket.recv(length)
    if data == b'':
        # Trigger callback for immediate reconnection
        if self._dead_socket_callback:
            self._dead_socket_callback()
    return data if data != b'' else None
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
│  │  │ Dead socket callback│   │  Uses OptimizedTCPInterface│ │ │
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
2. **Different Requirements**: Meshtastic needs reconnection handling; HTTP requests don't
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

**Dead Socket Callback (Immediate Reconnection)**
When `recv()` returns empty bytes (connection closed by server), the 
`OptimizedTCPInterface` triggers an immediate reconnection callback
instead of waiting for the health monitor to detect silence:

```python
# main_bot.py sets the callback:
interface.set_dead_socket_callback(self._reconnect_tcp_interface)

# When socket death is detected, callback is triggered immediately
# Reduces downtime from ~60s (waiting for health monitor) to ~10s
```

## Known Issues & Fixes

### ESP32 Socket Sensitivity (v2025.11.27)

**Root Cause Found:**
After extensive testing with the diagnostic tool, we discovered that ESP32-based
Meshtastic nodes are extremely sensitive to ANY socket modifications:

| Modification | Result |
|-------------|--------|
| TCP keepalive | Connection dies after ~2.5 minutes |
| Socket timeout | Connection dies after ~2.5 minutes |
| TCP_NODELAY | Connection dies after ~10 seconds |
| select() before recv() | Connection dies after ~10 seconds |

**The Fix:**
Use the **EXACT same socket behavior** as the standard `meshtastic.TCPInterface`:
- Simple blocking `recv()` with no modifications
- No socket options changed
- No select() calls
- Only add the dead socket callback for faster reconnection

**What OptimizedTCPInterface DOES:**
- ✅ Dead socket callback for immediate reconnection notification

**What OptimizedTCPInterface does NOT do:**
- ❌ No select() calls
- ❌ No socket timeout modification
- ❌ No TCP_NODELAY
- ❌ No TCP keepalive
- ❌ No CPU optimization (stability > performance)

**CPU Usage Note:**
The standard TCPInterface does have higher CPU usage due to blocking recv().
However, stability is more important than CPU optimization. If CPU usage
becomes a problem, investigate upstream in the meshtastic library.

## Debugging

### Diagnostic Tool

Use `diag_tcp_connection.py` to compare connection stability:

```bash
# Standard TCPInterface (like CLI) - baseline
python3 diag_tcp_connection.py 192.168.1.38 --duration 600

# OptimizedTCPInterface (like bot)
python3 diag_tcp_connection.py 192.168.1.38 --optimized --duration 600

# Raw socket (expected to fail - no protocol)
python3 diag_tcp_connection.py 192.168.1.38 --raw --duration 60
```

**Expected Results:**
- Standard and Optimized modes should both work indefinitely
- Raw mode will fail quickly (no Meshtastic protocol)

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

### Check Network Path
```bash
# Verify TCP connectivity
nc -vz 192.168.1.38 4403
```

## Related Files

- `main_bot.py` - Main bot using OptimizedTCPInterface
- `system_monitor.py` - Uses OptimizedTCPInterface for tigrog2 monitoring
- `remote_nodes_client.py` - Uses SafeTCPConnection for node queries
- `esphome_client.py` - HTTP requests to ESPHome
- `utils_weather.py` - curl subprocess for weather
- `blitz_monitor.py` - MQTT client for lightning data
- `vigilance_scraper.py` - HTTP + BeautifulSoup for weather alerts
- `diag_tcp_connection.py` - Diagnostic tool for TCP connection testing
