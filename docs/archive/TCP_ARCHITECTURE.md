# TCP Architecture Documentation

## Overview

This document clarifies the network connection architecture used in MeshBot. The codebase uses **different network stacks for different purposes**, which is intentional and appropriate.

## ⚠️ CRITICAL: ESP32 Single TCP Connection Limitation

**ESP32-based Meshtastic nodes only support ONE TCP connection at a time.**

This is a hardware/firmware limitation. When a new TCP connection is established:
1. The existing connection is immediately dropped
2. The bot loses all packet reception until reconnection
3. This causes the "2 minutes of packet loss every 3 minutes" symptom when multiple connections are created

**MANDATORY RULE**: All code accessing a Meshtastic node via TCP MUST share the same interface.

### Correct Usage

```python
# In main_bot.py - create the single shared interface
self.interface = OptimizedTCPInterface(hostname=tcp_host, portNumber=tcp_port)

# Share it with all components
self.remote_nodes_client.set_interface(self.interface)
self.node_manager.interface = self.interface
```

### Forbidden Patterns

```python
# ❌ WRONG - Creating a new connection kills the main interface!
new_interface = TCPInterface(hostname=same_host)

# ❌ WRONG - SafeTCPConnection creates new connections!  
with SafeTCPConnection(same_host) as interface:
    interface.sendText("Hello")  # This kills main connection!
```

## Network Stack Separation

### 1. Meshtastic Node Connection Stack

**Files:**
- `tcp_interface_patch.py` - OptimizedTCPInterface with dead socket callback
- `safe_tcp_connection.py` - Context manager for **different hosts only**

**Purpose:** 
Dedicated to **Meshtastic protocol communication** on port 4403.

**Single Connection Enforcement:**
- `OptimizedTCPInterface`: Used for the main bot connection (ONE instance only)
- `SafeTCPConnection`: Only for connecting to DIFFERENT physical nodes
- All components MUST share the main interface for same-host operations

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
- These are different hosts, so no conflict with ESP32 limitation
- Standard Python libraries handle these protocols well
- No CPU optimization needed (short-lived requests)

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
├── Purpose: Safe temporary connections to DIFFERENT Meshtastic nodes
├── Uses: OptimizedTCPInterface internally
├── ⚠️ WARNING: Only use for hosts DIFFERENT from main bot connection!
└── Features:
    ├── Automatic connection/disconnection
    ├── Connection timing tracking
    └── Error handling with cleanup
```

**⚠️ ESP32 LIMITATION WARNING:**
SafeTCPConnection creates NEW TCP connections. If used with the same host
as the main bot connection, it will KILL the main connection!

**CORRECT Usage (different host):**
```python
# Querying a DIFFERENT physical node
with SafeTCPConnection("192.168.1.200") as interface:  # Different IP!
    nodes = interface.nodes
```

**FORBIDDEN Usage (same host):**
```python
# ❌ This kills the main bot connection!
with SafeTCPConnection("192.168.1.38") as interface:  # Same as TCP_HOST!
    interface.sendText("Hello")  # Main bot now disconnected!
```

**Used By:**
- `remote_nodes_client.py` - Only for querying DIFFERENT physical nodes
- Should NOT be used for same-host operations

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              MeshBot                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │            MESHTASTIC NODE CONNECTION (Port 4403)                 │ │
│  │                                                                   │ │
│  │   ⚠️ ESP32 LIMITATION: ONLY ONE TCP CONNECTION ALLOWED!          │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  OptimizedTCPInterface (tcp_interface_patch.py)             │ │ │
│  │  │  ├── SINGLE SHARED INSTANCE for main connection             │ │ │
│  │  │  ├── Dead socket callback for fast reconnection             │ │ │
│  │  │  └── Used by: main_bot, remote_nodes_client, utility_cmds   │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                           │                                       │ │
│  │                           │ shared                                │ │
│  │                           ▼                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  All Components Use Shared Interface                        │ │ │
│  │  │  ├── main_bot.py (packet reception, sending)                │ │ │
│  │  │  ├── remote_nodes_client.py (node queries)                  │ │ │
│  │  │  ├── utility_commands.py (/echo command)                    │ │ │
│  │  │  └── message_sender.py (all message sending)                │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  SafeTCPConnection (safe_tcp_connection.py)                 │ │ │
│  │  │  ⚠️ ONLY for DIFFERENT physical nodes!                      │ │ │
│  │  │  Creating new connection to same host kills main interface! │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │              EXTERNAL SERVICES (No ESP32 Conflict)                │ │
│  │                     (Different hosts/protocols)                   │ │
│  │                                                                   │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────────────────┐│ │
│  │  │  ESPHome   │ │  Weather   │ │   Blitzortung                  ││ │
│  │  │  (HTTP)    │ │  (HTTP)    │ │   (MQTT)                       ││ │
│  │  │  requests  │ │  curl      │ │   paho-mqtt                    ││ │
│  │  └────────────┘ └────────────┘ └────────────────────────────────┘│ │
│  │                                                                   │ │
│  │  ┌────────────────────────────────────────────────────────────┐  │ │
│  │  │               Météo-France Vigilance                       │  │ │
│  │  │               (HTTP + HTML scraping)                       │  │ │
│  │  │               beautifulsoup4 + lxml                        │  │ │
│  │  └────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Why Separate Files for TCP?

**The TCP files are organized by role:**

1. **tcp_interface_patch.py** - Single shared interface wrapper
   - Provides dead socket callback for fast reconnection
   - One instance shared by entire application
   
2. **safe_tcp_connection.py** - Context manager for DIFFERENT hosts
   - Only for connecting to physically different Meshtastic nodes
   - NOT for same-host operations (would kill main connection)

3. **External services** use standard libraries (requests, paho-mqtt)
   - Different protocols (HTTP, MQTT), different hosts
   - No conflict with ESP32 limitation

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

### ESP32 Single TCP Connection (v2025.11.27)

**Root Cause Found:**
ESP32-based Meshtastic nodes only support ONE TCP connection at a time.
Multiple connections to the same node cause the previous connection to drop.

**Symptoms:**
- Periodic packet loss (2 minutes every 3 minutes)
- Connection drops when running certain commands
- Bot becomes unresponsive after /echo or stats queries

**The Fix:**
All code MUST share the single TCP interface:

```python
# ✅ CORRECT - Use shared interface
interface = self.interface  # From main_bot
interface.sendText("Hello")

# ❌ WRONG - Creates new connection, kills main bot!
new_interface = TCPInterface(hostname=same_host)
```

### ESP32 Socket Sensitivity (v2025.11.27)

**Root Cause Found:**
ESP32-based Meshtastic nodes are extremely sensitive to ANY socket modifications:

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
- ✅ Socket state monitoring in background thread

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
