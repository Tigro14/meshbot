# TCP Reconnection Timeout Fix

## Problem Description

After fixing the initial AttributeError issue, users reported a new problem: the bot would freeze for 20+ minutes when the TCP connection died. The logs would stop showing any activity during this freeze period.

## Root Cause

The `_reconnect_tcp_interface()` method calls `OptimizedTCPInterface()` constructor which inherits from `meshtastic.tcp_interface.TCPInterface`. This constructor attempts to establish a TCP connection to the remote node.

**The issue:** If the remote node is unreachable (powered off, network issue, etc.), the TCP socket connection attempt can block for an extremely long time (potentially 20+ minutes) waiting for the TCP stack to timeout at the OS level.

During this time:
- The bot's periodic update thread is blocked
- No messages are processed
- The bot appears "frozen" with no log output
- The connection eventually times out, but only after a very long wait

## Solution

Added a **30-second timeout** using Python threading:

1. Create the TCP interface in a separate daemon thread
2. Use `thread.join(timeout=30)` to wait maximum 30 seconds
3. Check if the thread is still alive after timeout
4. If still alive, the connection is hanging - abort and return False
5. If completed, check for exceptions or success

### Code Changes

```python
# OLD CODE (blocks indefinitely):
self.interface = OptimizedTCPInterface(
    hostname=tcp_host,
    portNumber=tcp_port
)

# NEW CODE (30s timeout):
new_interface = [None]
exception_holder = [None]

def create_interface():
    try:
        new_interface[0] = OptimizedTCPInterface(
            hostname=tcp_host,
            portNumber=tcp_port
        )
    except Exception as e:
        exception_holder[0] = e

creation_thread = threading.Thread(target=create_interface, daemon=True)
creation_thread.start()
creation_thread.join(timeout=30)

if creation_thread.is_alive():
    error_print(f"⏱️ Timeout (30s) lors de la connexion TCP")
    return False
```

## Behavior

### Before Fix
- Connection attempt blocks for 20+ minutes
- Bot appears completely frozen
- No log output during freeze
- Eventually times out at OS level

### After Fix
- Connection attempt times out after 30 seconds
- Clear error message: "⏱️ Timeout (30s) lors de la connexion TCP à {host}:{port}"
- Explanation: "Le nœud distant est peut-être éteint ou inaccessible"
- Function returns False immediately
- Periodic update thread continues normally
- Bot retries connection on next periodic check (5 minutes later)

## Testing

Created `test_tcp_reconnection_timeout.py` to verify:
1. Code uses `threading.Thread` for timeout
2. Calls `join(timeout=30)` with 30-second timeout
3. Detects timeout with `is_alive()` check
4. Returns False on timeout
5. Logs appropriate error messages
6. Function is well documented

## Error Messages

**Timeout scenario:**
```
🔄 Reconnexion TCP à 192.168.1.38:4403...
⏱️ Timeout (30s) lors de la connexion TCP à 192.168.1.38:4403
Le nœud distant est peut-être éteint ou inaccessible
```

**Normal error scenario:**
```
🔄 Reconnexion TCP à 192.168.1.38:4403...
❌ Échec reconnexion TCP: [Errno 111] Connection refused
```

## Impact

- **Fixes freeze issue**: Bot no longer hangs for 20+ minutes
- **Fast failure**: Timeout after 30 seconds instead of indefinitely
- **Automatic retry**: Periodic update thread retries every 5 minutes
- **Better UX**: Clear error messages explaining what happened
- **No side effects**: Normal reconnection still works when node is available

## Related Issues

- Issue #64: TCP debug & error on mesh_traceroute_manager
- User report: "tcp dead state where the bot logs freeze +20mn with no activity"

## Files Modified

- `main_bot.py` - Added timeout mechanism to `_reconnect_tcp_interface()`
- `test_tcp_reconnection_timeout.py` - New test to verify timeout works
- `test_tcp_reconnection_fix.py` - Updated to handle longer function code
