# MeshCore Monitor - RX_LOG_DATA Support

## Issue Analysis

The user reported that with `--debug` enabled, the monitor was receiving `RX_LOG_DATA` events showing RF packet activity, but DM messages were not being processed (counter remained at 0).

### Root Cause

The monitor was only subscribed to `CONTACT_MSG_RECV` events (for decoded DM messages), but not to `RX_LOG_DATA` events (raw RF packets). The debug output showed:

```
DEBUG:meshcore:Dispatching event: EventType.RX_LOG_DATA, {'raw_hex': '...', 'snr': 11.75, 'rssi': -52, ...}
```

This indicated:
1. RF packets were being received successfully
2. `RX_LOG_DATA` events were being dispatched
3. But `CONTACT_MSG_RECV` events were NOT being triggered (likely due to decryption/contact sync issues)

## Solution Implemented

### 1. Subscribe to RX_LOG_DATA Events

Added subscription to `RX_LOG_DATA` events in addition to `CONTACT_MSG_RECV`:

```python
# Subscribe to CONTACT_MSG_RECV for actual DM messages
self.meshcore.events.subscribe(self.EventType.CONTACT_MSG_RECV, self.on_message)

# Also subscribe to RX_LOG_DATA to track raw RF activity
if hasattr(self.EventType, 'RX_LOG_DATA'):
    self.meshcore.events.subscribe(self.EventType.RX_LOG_DATA, self.on_rx_log_data)
```

### 2. Separate Event Handlers

- `on_message()` - Handles CONTACT_MSG_RECV (decoded DM messages)
- `on_rx_log_data()` - Handles RX_LOG_DATA (raw RF packets)

### 3. Dual Counters

The heartbeat now shows both counters:

```
[09:32:46] 💓 Monitor active | DM messages: 0 | RF packets: 47
```

This clearly shows:
- RF activity is happening (packets being received)
- But DM messages are not being decoded/dispatched

### 4. RX_LOG_DATA Handler Behavior

- **Debug mode OFF**: Events are counted but not displayed (avoid spam)
- **Debug mode ON**: Events are shown with SNR, RSSI, and payload length

### 5. Enhanced Startup Info

Added explanation of event types:

```
📊 Event counters:
   - CONTACT_MSG_RECV: DM messages (shown in detail)
   - RX_LOG_DATA: Raw RF packets (counted, shown in debug mode)
```

### 6. Enhanced Statistics

Shutdown statistics now show both counters:

```
📊 Statistics:
   DM messages received: 0
   RF packets received: 47
```

## Benefits

1. **Visibility**: Users can now see RF activity even when DM messages aren't being decoded
2. **Diagnosis**: Clear distinction between "no RF activity" vs "RF active but DMs not decoded"
3. **Troubleshooting**: Helps identify contact sync or decryption issues
4. **Non-intrusive**: RX_LOG_DATA events don't spam output unless debug mode is on

## Expected Output

### Without Debug (default)
```
✅ Monitor ready! Waiting for messages...
   📊 Event counters:
      - CONTACT_MSG_RECV: DM messages (shown in detail)
      - RX_LOG_DATA: Raw RF packets (counted, shown in debug mode)
============================================================

[09:32:16] 💓 Monitor active | DM messages: 0 | RF packets: 0
[09:32:46] 💓 Monitor active | DM messages: 0 | RF packets: 47
[09:33:16] 💓 Monitor active | DM messages: 2 | RF packets: 89
```

### With Debug (--debug)
```
✅ Monitor ready! Waiting for messages...
============================================================

DEBUG:meshcore:Received data: 882fcc0a024b93...
DEBUG:meshcore:Dispatching event: EventType.RX_LOG_DATA, {...}

[09:32:16] 📡 RX_LOG_DATA #1
  Event: RxLogDataEvent
  SNR: 11.75
  RSSI: -52
  Payload length: 56

[09:32:16] 💓 Monitor active | DM messages: 0 | RF packets: 1

============================================================
[09:32:20] 📬 Message #1 received!
============================================================
Event type: ContactMessageEvent
  From: 0x12345678
  Text: Hello from mesh!
============================================================

[09:32:46] 💓 Monitor active | DM messages: 1 | RF packets: 47
```

## Next Steps for User

If RF packets are being received but DM messages are not (counter shows 0 DMs but >0 RF packets):

1. **Check contact sync**: Ensure `sync_contacts()` completed successfully
2. **Check auto message fetching**: Ensure `start_auto_message_fetching()` is running
3. **Check encryption**: Messages may be encrypted and need proper keys
4. **Check filters**: Verify the device is configured to accept DMs
5. **Check meshcore version**: Ensure using compatible meshcore-cli version

## Files Modified

- `meshcore-serial-monitor.py` - Added RX_LOG_DATA support and dual counters
