# Broadcast Loop Fix - Technical Summary

## Problem Description

When a user sends a broadcast command like `/rain`, the bot would:
1. ✅ Receive and process the command
2. ✅ Generate a response and send it via tigrog2 (TCP interface)
3. ❌ Receive its own broadcast message back from the mesh network
4. ❌ Process the message AGAIN (infinite loop)
5. ❌ Attempt a second TCP connection, which times out after 30 seconds

This caused the error:
```
meshtastic.mesh_interface.MeshInterface.MeshInterfaceError: 
Timed out waiting for connection completion
```

## Root Cause Analysis

### Why the bot didn't recognize its own messages

The bot uses two different Meshtastic nodes:
- **Serial interface** (tigrobot): Local node ID (e.g., 0x12345678)
- **TCP interface** (tigrog2): Remote node ID (e.g., 0x87654321)

When sending a broadcast:
1. Bot generates response
2. Sends via `broadcast_message(tigrog2_ip, message)`
3. Message is broadcast FROM tigrog2's node ID
4. Bot receives broadcast with `from_id = tigrog2_id`
5. Existing check: `is_from_me = (from_id == my_id)` → FALSE
6. Message is processed again → loop!

### Why existing deduplication didn't work

The existing `is_from_me` check in `main_bot.py:208-210` only compares:
```python
my_id = self.interface.localNode.nodeNum  # Serial interface ID
is_from_me = (from_id == my_id)  # tigrog2_id != serial_id
```

This doesn't catch broadcasts sent via tigrog2.

## Solution: Content-Based Deduplication

Instead of relying on node IDs, we track the **content** of sent broadcasts:

### 1. Track Outgoing Broadcasts
```python
def _track_broadcast(self, message):
    """Record a broadcast we're about to send"""
    msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
    self._recent_broadcasts[msg_hash] = time.time()
```

### 2. Check Incoming Broadcasts
```python
def _is_recent_broadcast(self, message):
    """Check if this message is one we sent recently"""
    msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
    if msg_hash in self._recent_broadcasts:
        age = time.time() - self._recent_broadcasts[msg_hash]
        if age < 60:  # 60 second window
            return True
    return False
```

### 3. Filter in on_message()
```python
if is_broadcast and self._is_recent_broadcast(message):
    debug_print(f"🔄 Broadcast ignoré (envoyé par nous): {message[:30]}")
    return  # Don't process
```

## Implementation Details

### Call Chain

```
User sends /rain
    ↓
main_bot.on_message(packet)
    ↓
message_handler.process_text_message()
    ↓
message_router.process_text_message()
    ↓
utility_handler.handle_rain()
    ↓
utility_handler.handle_weather(..., is_broadcast=True)
    ↓
utility_handler._send_broadcast_via_tigrog2()
    ↓
[Thread starts]
    ↓
broadcast_tracker(message)  ← TRACK BEFORE SENDING
    ↓
broadcast_message(tigrog2, message)
    ↓
[Message sent to mesh network]
    ↓
[Bot receives own broadcast back]
    ↓
main_bot.on_message(packet)
    ↓
_is_recent_broadcast(message)  ← CHECK HASH
    ↓
return (filtered)  ← LOOP PREVENTED!
```

### Key Features

1. **Content Hashing**: MD5 hash of message content
2. **Time Window**: 60 second deduplication window
3. **Auto-Cleanup**: Old hashes removed automatically
4. **Thread-Safe**: Tracking happens in broadcast thread
5. **Callback Pattern**: No tight coupling to MeshBot

## Files Modified

1. **main_bot.py**
   - Added `_recent_broadcasts` dict
   - Added `_track_broadcast()` method
   - Added `_is_recent_broadcast()` method
   - Modified `on_message()` to filter broadcasts
   - Pass tracker callback to MessageHandler

2. **message_handler.py**
   - Accept and forward `broadcast_tracker` callback

3. **handlers/message_router.py**
   - Accept and forward `broadcast_tracker` callback

4. **handlers/command_handlers/utility_commands.py**
   - Accept `broadcast_tracker` in `__init__`
   - Call tracker in `_send_broadcast_via_tigrog2()`

5. **handlers/command_handlers/network_commands.py**
   - Accept `broadcast_tracker` in `__init__`
   - Call tracker in `_send_broadcast_via_tigrog2()`

## Testing

### Unit Tests (test_broadcast_dedup.py)
- ✅ Hash tracking works
- ✅ Recent messages recognized
- ✅ Old messages expire
- ✅ Different messages not confused

### Integration Tests (test_broadcast_integration.py)
- ✅ Full flow simulation
- ✅ User → Bot → Broadcast → Receipt → Filter
- ✅ No false positives
- ✅ Expiration works correctly

## Performance Impact

- **Memory**: Minimal (~100 bytes per broadcast, auto-cleanup)
- **CPU**: Negligible (single MD5 hash per broadcast)
- **Network**: None (prevents extra TCP connections)
- **Latency**: None (hash check is microseconds)

## Edge Cases Handled

1. **Multiple broadcasts in succession**: Each tracked separately
2. **Identical messages**: Only first instance tracked
3. **Expiration**: 60s window prevents stale hashes
4. **Thread safety**: Callback executes in broadcast thread
5. **Cleanup**: Old hashes removed on each track call

## Deployment Notes

No configuration changes needed. The fix is transparent and automatic.

### Monitoring

Look for these log messages:
- `🔖 Broadcast tracké: <hash>... (N actifs)` - Broadcast tracked
- `🔍 Reconnu (Xs): <hash>...` - Own broadcast recognized
- `🔄 Broadcast ignoré (envoyé par nous): <msg>` - Loop prevented

### Expected Behavior After Fix

User sends `/rain`:
1. Bot processes command
2. Bot generates response
3. Bot tracks response hash
4. Bot sends via tigrog2
5. Bot receives own broadcast
6. Bot recognizes hash
7. Bot filters message
8. ✅ No loop, no timeout!

## Related Issues

- Prevents TCP timeout errors on broadcast commands
- Reduces unnecessary network traffic
- Improves bot responsiveness
- Prevents duplicate responses to users

## Future Improvements

Potential enhancements (not needed now):
1. Make window configurable
2. Add metrics for filtered broadcasts
3. Log hash collisions (very unlikely)
4. Persist hashes across bot restarts (optional)
