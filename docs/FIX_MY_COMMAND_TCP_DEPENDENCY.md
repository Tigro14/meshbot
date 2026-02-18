# Fix: /my Command TCP Dependency

## Problem Statement

The `/my` command was broken on both MeshCore (MC) and Meshtastic (MT) due to a deprecated TCP dependency that:

1. **Created separate TCP connections** to `REMOTE_NODE_HOST` to query node information
2. **Violated ESP32 limitation** - ESP32 Meshtastic nodes only support ONE TCP connection at a time
3. **Killed the main bot connection** when creating additional TCP connections
4. **Was completely disabled for MeshCore** due to network isolation rules
5. **Required REMOTE_NODE_HOST** configuration even when not needed

## Solution Overview

Refactored `/my` command to use **local data only** (no TCP connections):

### Key Changes

1. **Uses `node_manager.rx_history`** (local SQLite data) instead of TCP queries
2. **Falls back to `node_manager.node_names`** if not in rx_history
3. **Removed `/my` from `meshtastic_only_commands`** - now works on both MT and MC
4. **No REMOTE_NODE_HOST dependency** - works with local data only
5. **Instant response** - no network latency or timeout issues

## Architecture

### Before (Deprecated - TCP-dependent)

```
┌─────────────┐
│   Bot       │
└─────┬───────┘
      │ /my command
      ▼
┌─────────────────────┐
│ get_remote_nodes()  │  ❌ Creates new TCP connection
└─────┬───────────────┘
      │ TCP 4403
      ▼
┌─────────────────────┐
│  REMOTE_NODE_HOST   │  ❌ ESP32: Only 1 connection!
│   (tigrog2)         │     Kills main connection!
└─────────────────────┘
```

**Problems:**
- Creates separate TCP connection
- Violates ESP32 single-connection limitation
- Kills main bot connection
- Network latency and timeout issues
- Requires REMOTE_NODE_HOST configuration

### After (Fixed - Local-only)

```
┌─────────────────────┐
│   Bot               │
│   ┌──────────────┐  │
│   │ rx_history   │  │  ✅ Local SQLite data
│   │ node_names   │  │
│   └──────────────┘  │
└─────┬───────────────┘
      │ /my command
      │ Reads rx_history
      ▼
Instant response
(no network call)
```

**Benefits:**
- ✅ No TCP connections
- ✅ Works with MT and MC
- ✅ Instant response
- ✅ No connection conflicts
- ✅ No configuration required

## Code Changes

### 1. network_commands.py - handle_my()

**Before (TCP-dependent):**
```python
def handle_my(self, sender_id, sender_info, is_broadcast=False):
    """Gérer la commande /my - Afficher vos signaux vus par votre node"""
    
    def get_remote_signal_info():
        # ❌ DEPRECATED: Creates TCP connection
        remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
        
        if not remote_nodes:
            response = f"⚠️ {REMOTE_NODE_NAME} inaccessible"
            return
        
        # Search for sender in remote nodes
        for node in remote_nodes:
            if node['id'] == sender_id:
                sender_node_data = node
                break
```

**After (Local-only):**
```python
def handle_my(self, sender_id, sender_info, is_broadcast=False):
    """
    Gérer la commande /my - Afficher vos signaux vus localement
    
    ✅ NO TCP DEPENDENCY: Utilise node_manager.rx_history (local SQLite)
    ✅ Works for both Meshtastic and MeshCore networks
    """
    
    def get_local_signal_info():
        # ✅ STEP 1: Check local rx_history (no TCP!)
        if sender_id in self.node_manager.rx_history:
            rx_data = self.node_manager.rx_history[sender_id]
            sender_node_data = {
                'id': sender_id,
                'name': self.node_manager.get_node_name(sender_id),
                'snr': rx_data.get('snr', 0.0),
                'last_heard': rx_data.get('last_time', 0)
            }
            # ✅ No TCP connection!
        
        # ✅ STEP 2: Fallback to node_names (still no TCP!)
        elif sender_id in self.node_manager.node_names:
            node_info = self.node_manager.node_names[sender_id]
            sender_node_data = {
                'id': sender_id,
                'name': self.node_manager.get_node_name(sender_id),
                'snr': 0.0,
                'last_heard': node_info.get('last_update', 0)
            }
```

### 2. message_router.py - meshtastic_only_commands

**Before:**
```python
meshtastic_only_commands = [
    '/nodemt', '/trafficmt', 
    '/neighbors', '/nodes', 
    '/my',      # ❌ Blocked for MeshCore
    '/trace'
]
```

**After:**
```python
meshtastic_only_commands = [
    '/nodemt', '/trafficmt', 
    '/neighbors', '/nodes', 
    # /my REMOVED - now works with both MT and MC
    '/trace'
]
```

### 3. Updated Response Formatting

**_format_my_response():**
- Removed references to `REMOTE_NODE_NAME`
- Uses "Signal local" instead of "Direct → tigrog2"
- Works with local rx_history data format

**_format_my_not_found_local():**
- New method for nodes not in rx_history
- Provides helpful message to send packets
- No remote node references

## Usage

### Meshtastic (MT) Network
```
User → Bot: /my
Bot → User: 📶 ~-85dBm SNR:8.5dB | 📈 Bon (5m) | 📍 2.3km (GPS) | 📶 Signal local
```

### MeshCore (MC) Network
```
User → Bot: /my
Bot → User: 📶 ~-80dBm SNR:10.2dB | 📈 Excellent (2m) | 📍 1.5km (GPS) | 📶 Signal local
```

### Node Not in rx_history
```
User → Bot: /my
Bot → User: 📶 Signal non enregistré
            ⚠️ Aucun paquet reçu récemment
            💡 Envoyez un message pour être détecté
```

## Benefits

| Benefit | Description |
|---------|-------------|
| 🚀 **Performance** | Instant response (no network wait) |
| 🔒 **Stability** | No conflicts with main TCP connection |
| 🌐 **Compatibility** | Works with both MT and MC |
| 💾 **Local Data** | Uses rx_history (SQLite) |
| ⚡ **No Latency** | No network timeouts possible |
| 🔧 **Configuration** | No REMOTE_NODE_HOST needed |
| 📊 **History** | Maintains signal history |
| 🛡️ **ESP32-safe** | Respects 1 TCP connection limit |

## Testing

All tests pass successfully:

```bash
$ python3 tests/test_my_no_tcp_source.py

✅ PASS: meshtastic_only removal
✅ PASS: local rx_history usage
✅ PASS: no REMOTE_NODE refs
✅ PASS: local not_found method
✅ PASS: broadcast compatibility
```

## Files Modified

1. **handlers/command_handlers/network_commands.py**
   - Refactored `handle_my()` to use local data
   - Updated `_format_my_response()` to remove remote references
   - Added `_format_my_not_found_local()` method

2. **handlers/message_router.py**
   - Removed `/my` from `meshtastic_only_commands` list

## Files Added

1. **tests/test_my_command_no_tcp.py** - Unit tests (requires meshtastic module)
2. **tests/test_my_no_tcp_source.py** - Source code analysis tests (standalone)
3. **demos/demo_my_no_tcp.py** - Interactive demonstration

## Migration Notes

### For Existing Deployments

No configuration changes needed! The command now works better:
- **Works immediately** - no REMOTE_NODE_HOST required
- **Works on both networks** - MT and MC
- **Faster** - no network latency
- **More reliable** - no TCP connection issues

### For Users

The `/my` command now:
- Shows signal data based on **local reception history**
- Works on **both Meshtastic and MeshCore** networks
- Responds **instantly** (no network delay)
- Doesn't require the bot to have a remote node configured

## Technical Details

### Data Sources

The command uses two local data sources in priority order:

1. **`node_manager.rx_history`** - Signal metrics from received packets
   ```python
   {
       'snr': 8.5,           # Signal-to-noise ratio
       'last_time': 1234567890,  # Unix timestamp
       'count': 5            # Number of packets received
   }
   ```

2. **`node_manager.node_names`** - Node information cache
   ```python
   {
       'name': 'NodeName',
       'last_update': 1234567890,
       'lat': 48.8252,
       'lon': 2.3622
   }
   ```

### ESP32 Single-Connection Limitation

ESP32-based Meshtastic nodes (most hardware) only support **ONE TCP connection at a time**. When a second connection is created:
1. The first connection is immediately dropped
2. The bot loses all packet reception
3. This causes ~2 minutes of packet loss every 3 minutes if creating separate connections

By using local data only, this fix ensures:
- ✅ No additional TCP connections created
- ✅ Main bot connection remains stable
- ✅ Continuous packet reception

## Future Improvements

Potential enhancements (not required for this fix):

1. **Enhanced Metrics** - Add more signal quality indicators
2. **Historical Tracking** - Show signal trends over time
3. **Multi-hop Info** - Display hop count if available
4. **Network Health** - Overall connectivity status

## References

- **ESP32 TCP Limitation**: See `docs/archive/TCP_ARCHITECTURE.md`
- **Node Manager**: See `node_manager.py` - rx_history implementation
- **Network Isolation**: See `handlers/message_router.py` - MC/MT separation

## Summary

This fix resolves the deprecated TCP dependency in the `/my` command by:
- ✅ Using local rx_history data (no TCP)
- ✅ Enabling MeshCore support (removed from blocking list)
- ✅ Providing instant responses (no network latency)
- ✅ Eliminating ESP32 connection conflicts
- ✅ Removing REMOTE_NODE_HOST dependency

**Result**: The `/my` command now works reliably on both MC and MT networks without any TCP overhead.
