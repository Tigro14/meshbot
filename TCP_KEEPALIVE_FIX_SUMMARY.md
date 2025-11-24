# TCP Keepalive Fix - Dead Connection Detection

## Problem Description

After applying the timeout fix, users reported the bot still becomes unresponsive after ~3 minutes of use. The TCP connection appears "alive" to the OS but is actually dead (half-open connection), causing the bot to hang.

## Root Cause

**Half-Open TCP Connections**: When a TCP connection dies ungracefully (network cable unplugged, remote node crash, etc.), the local socket doesn't know the connection is dead. Without keepalive:

- The socket appears "connected" to the OS
- `select()` doesn't report any errors
- Reads block indefinitely waiting for data that will never come
- The connection can stay in this zombie state for **hours** or even **days**
- The health check (`getpeername()`) still succeeds because the socket is technically open

**Timeline of the problem:**
1. Remote node crashes or network connection dies
2. Bot's socket enters half-open state (thinks it's connected)
3. `select()` in `_readBytes()` blocks waiting for data
4. Bot appears frozen, no log output
5. Health check runs every 5 minutes but `getpeername()` succeeds (socket is "open")
6. Bot stays frozen until OS TCP timeout (many hours)

## Solution

Implemented **TCP Keepalive** to proactively detect dead connections:

### 1. Enable SO_KEEPALIVE

```python
self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
```

### 2. Configure Keepalive Parameters (Linux)

```python
# Start sending keepalive probes after 60 seconds of inactivity
self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)

# Send keepalive probe every 10 seconds
self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)

# Declare connection dead after 6 failed probes
self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)
```

**Detection timeline:**
- 60 seconds: First keepalive probe sent
- 70 seconds: Second probe (if no response)
- 80 seconds: Third probe
- 90 seconds: Fourth probe
- 100 seconds: Fifth probe
- 110 seconds: Sixth probe
- **120 seconds: Connection declared dead** (socket error triggered)

Total: **~2 minutes** to detect dead connection (vs hours without keepalive)

### 3. Monitor Socket Exceptions in select()

```python
# OLD: Only monitor readability
ready, _, _ = select.select([self.socket], [], [], timeout)

# NEW: Also monitor exceptions
ready, _, exception = select.select([self.socket], [], [self.socket], timeout)

if exception:
    # Socket has error - connection probably dead
    return b''
```

This allows `select()` to wake up immediately when the socket enters error state (triggered by keepalive failure).

## How It Works

1. **Normal Operation**: 
   - Keepalive probes sent every 10s after 60s idle
   - Remote responds to probes
   - Connection stays healthy

2. **Connection Dies**:
   - Remote stops responding to keepalive probes
   - After 6 failed probes (60 seconds), TCP stack marks connection as dead
   - Socket enters error state
   - `select()` detects exception and returns
   - Next health check detects dead socket
   - Reconnection triggered

3. **Recovery**:
   - Health check runs every 5 minutes
   - Dead connection detected in 2 minutes by keepalive
   - Next health check (within 3 minutes) triggers reconnection
   - **Total recovery time: 2-7 minutes** (much better than hours!)

## Behavior Comparison

### Without Keepalive (Before)
```
T+0:00  Remote node crashes
T+0:01  Bot continues thinking it's connected
T+0:03  Bot becomes unresponsive (select() blocks)
T+0:05  Health check runs - socket appears OK (getpeername succeeds)
T+0:10  Health check runs - still OK
T+2:00  Bot still frozen
T+24:00 Still frozen (OS TCP timeout not reached)
```

### With Keepalive (After)
```
T+0:00  Remote node crashes
T+0:01  Bot continues thinking it's connected
T+1:00  First keepalive probe sent (no response)
T+1:10  Second probe (no response)
T+1:20  Third probe (no response)
T+1:30  Fourth probe (no response)
T+1:40  Fifth probe (no response)
T+1:50  Sixth probe (no response)
T+2:00  Connection declared DEAD by TCP stack
T+2:00  select() wakes up with exception
T+2:00  _readBytes returns empty
T+5:00  Next health check detects dead socket
T+5:00  Reconnection triggered
T+5:05  Bot back online!
```

## Platform Compatibility

**Linux**: Full support for all keepalive parameters (TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT)

**macOS/BSD**: May not support all parameters, falls back to basic SO_KEEPALIVE

**Windows**: Different parameter names, basic SO_KEEPALIVE works

The code gracefully handles platforms without advanced keepalive support - basic keepalive (SO_KEEPALIVE) is still enabled.

## Testing

Created `test_tcp_keepalive.py` to verify:
1. SO_KEEPALIVE is enabled
2. TCP_KEEPIDLE configured (60s)
3. TCP_KEEPINTVL configured (10s)
4. TCP_KEEPCNT configured (6 probes)
5. select() monitors exception list
6. Exception handling in _readBytes

All tests pass ✅

## Impact

**Before:**
- Dead connections undetected for hours
- Bot appears frozen/unresponsive
- Manual restart required

**After:**
- Dead connections detected in ~2 minutes
- Automatic recovery in 2-7 minutes
- No manual intervention needed
- Bot stays responsive

## Related Fixes

This fix works together with:
1. **AttributeError fix**: Correct attribute name usage
2. **Timeout fix**: 30s timeout on reconnection attempts
3. **Keepalive fix**: Fast detection of dead connections

All three combined provide robust TCP connection management.

## Files Modified

- `tcp_interface_patch.py` - Added keepalive configuration + select() improvement
- `test_tcp_keepalive.py` - Test suite for keepalive functionality
