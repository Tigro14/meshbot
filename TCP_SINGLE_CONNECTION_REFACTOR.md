# TCP Single Connection Refactor Summary

**Date**: 2025-11-27
**Issue**: Periodic packet loss (2 minutes every 3 minutes) due to multiple TCP connections

## Root Cause Analysis

### The Problem
ESP32-based Meshtastic nodes only support **ONE TCP connection at a time**. When a new TCP connection is established to the same node, the existing connection is dropped immediately, causing:
- Complete loss of packet reception
- Bot appears unresponsive
- The pattern repeats every time certain commands are executed

### Identified Connection Sources
Multiple places in the code were creating NEW TCP connections to the same ESP32 node:

1. **utility_commands.py (echo command)** - Created a direct `TCPInterface` for every `/echo` command
2. **system_monitor.py (tigrog2 check)** - Created new `OptimizedTCPInterface` for status monitoring
3. **remote_nodes_client.py** - Created `SafeTCPConnection` when shared interface was not set

## Solution Implemented

### Architecture: Single Shared Interface

All code now MUST use the single shared interface when connecting to the same host:

```
┌─────────────────────────────────────────────────────────────┐
│                       MeshBot                               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Single OptimizedTCPInterface             │   │
│  │                   (main_bot.py)                     │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                  │
│          ┌───────────────┼───────────────┐                 │
│          ▼               ▼               ▼                 │
│  ┌───────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ /echo cmd │  │ remote_nodes   │  │ message_sender   │  │
│  │ (utility  │  │ _client.py     │  │ (all responses)  │  │
│  │ _commands)│  │ (node queries) │  │                  │  │
│  └───────────┘  └────────────────┘  └──────────────────┘  │
│                                                             │
│  ✅ All components share same interface                    │
│  ❌ No new connections to same host allowed                │
└─────────────────────────────────────────────────────────────┘
```

### Changes Made

#### 1. utility_commands.py (Echo Command)
**Before:**
```python
# Created NEW TCP connection (BROKE main connection!)
remote_interface = meshtastic.tcp_interface.TCPInterface(
    hostname=REMOTE_NODE_HOST, 
    portNumber=4403
)
```

**After:**
```python
# Uses shared interface from sender
interface = current_sender._get_interface()
interface.sendText(echo_response)  # No new connection!
```

#### 2. system_monitor.py (Tigrog2 Check)
**Before:**
```python
# Always created new connection
remote_interface = OptimizedTCPInterface(
    hostname=REMOTE_NODE_HOST,
    portNumber=4403
)
```

**After:**
```python
# Skip check if same host as main TCP connection
if connection_mode == 'tcp' and tcp_host == remote_host:
    debug_print("tigrog2 check skipped: same host as main TCP connection")
    self.tigrog2_was_online = True  # We're already connected
    return
```

#### 3. remote_nodes_client.py
**Before:**
```python
# Could create new connections when interface not set
remote_interface = SafeTCPConnection(remote_host, remote_port).__enter__()
```

**After:**
```python
# Must use shared interface in TCP mode for same host
must_use_shared = self._must_use_shared_interface(remote_host)
if must_use_shared:
    if self.interface is None:
        error_print("Interface non disponible mais mode TCP actif")
        return []
    remote_interface = self.interface  # Reuse shared interface
```

### Helper Methods Added
```python
class RemoteNodesClient:
    def _get_connection_mode(self):
        """Get connection mode from config or constructor"""
        
    def _get_tcp_host(self):
        """Get TCP host from config or constructor"""
        
    def _must_use_shared_interface(self, remote_host):
        """Check if shared interface MUST be used for this host"""
```

## Documentation Updates

- **TCP_ARCHITECTURE.md**: Added ESP32 single-connection limitation section
- **tcp_interface_patch.py**: Updated header documentation
- **remote_nodes_client.py**: Added ESP32 limitation warning in docstrings
- **test_tcp_keepalive.py**: Rewritten to test actual architecture

## Testing

All tests pass:
- `test_tcp_keepalive.py` - 5/5 tests passed
- `test_tcp_reconnection_fix.py` - 2/2 tests passed  
- `test_tcp_interface_fix.py` - 2/2 tests passed

## Recommendations for Future Work

1. **Consider dependency injection**: Pass the shared interface explicitly to all components that need it, rather than relying on `set_interface()` calls.

2. **Add runtime validation**: Consider adding a debug mode that logs warnings when multiple connections are detected to the same host.

3. **Document in config.py.sample**: Add a note about the ESP32 limitation near the TCP configuration options.

4. **Multi-node support**: If future use cases require connecting to multiple different ESP32 nodes simultaneously, consider a connection pool pattern with host-based routing.

## Security Summary

CodeQL security scan: **0 alerts** - No security vulnerabilities introduced.

## Files Modified

- `tcp_interface_patch.py` - Updated documentation
- `handlers/command_handlers/utility_commands.py` - Echo command uses shared interface
- `system_monitor.py` - Tigrog2 check skips when same host
- `remote_nodes_client.py` - Added helper methods, enforces shared interface
- `TCP_ARCHITECTURE.md` - Comprehensive ESP32 limitation documentation
- `test_tcp_keepalive.py` - Rewritten to match actual architecture
