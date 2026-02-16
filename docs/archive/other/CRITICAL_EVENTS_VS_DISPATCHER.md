# CRITICAL: MeshCore Events vs Dispatcher APIs

**Date**: 2026-02-12  
**Issue**: Messages not appearing  
**Solution**: Use correct subscription API  
**Status**: ✅ **FIXED**

---

## The Critical Discovery

MeshCore has **TWO different subscription systems** with different APIs:

### 1. Events API (`.events.subscribe()`)
**For:** CHANNEL_MSG_RECV (Public channel messages)

### 2. Dispatcher API (`.dispatcher.subscribe()`)
**For:** Other events (CONTACT_MSG_RECV, RX_LOG_DATA)

---

## The Wrong Attempts

### Attempt 1: Direct subscribe() ❌
```python
meshcore.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
```
**Result:** No such method, subscription fails silently

### Attempt 2: Dispatcher subscribe() ❌
```python
meshcore.dispatcher.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
```
**Result:** Wrong API, callback never invoked

---

## The Correct Solution ✅

### For CHANNEL_MSG_RECV (Public Channel)
```python
meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
```

### For Other Events
```python
meshcore.dispatcher.subscribe(EventType.CONTACT_MSG_RECV, on_dm)
meshcore.dispatcher.subscribe(EventType.RX_LOG_DATA, on_rx_log)
```

---

## From Bot Code

**meshcore_cli_wrapper.py lines 842-843:**
```python
self.meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_message)
info_print_mc("✅ Souscription aux messages de canal public (CHANNEL_MSG_RECV)")
```

**meshcore_cli_wrapper.py line 881:**
```python
self.meshcore.dispatcher.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_message)
```

**Wait, both are used?** Yes! The bot checks which API is available:
- If `meshcore.events` exists → use `events.subscribe()`
- If only `meshcore.dispatcher` exists → use `dispatcher.subscribe()`

---

## Why This Matters

### Events API (Preferred)
- Modern MeshCore versions
- Separate event system for channel messages
- Used for CHANNEL_MSG_RECV

### Dispatcher API (Fallback/Legacy)
- Older MeshCore versions
- Unified dispatcher for all events
- Used for DM, RX_LOG, etc.

---

## The Complete Working Code

```python
#!/usr/bin/env python3
import sys
import asyncio
from datetime import datetime
from meshcore import MeshCore, EventType

def on_message(event):
    """Callback for CHANNEL_MSG_RECV events"""
    print(f"\n{'='*80}")
    print(f"📡 MESHCORE EVENT RECEIVED")
    print(f"{'='*80}")
    # ... process event ...

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM2"
    
    try:
        # 1. Create with async factory
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        meshcore = loop.run_until_complete(
            MeshCore.create_serial(port, baudrate=115200)
        )
        
        print(f"✅ Connected to MeshCore on {port}")
        
        # 2. Subscribe with EVENTS API (not dispatcher!)
        meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
        print("✅ Subscribed successfully")
        
        # 3. Run event loop
        print("🎧 Listening for messages...")
        loop.run_forever()
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == '__main__':
    main()
```

---

## Testing

```bash
python3 listen_meshcore_debug.py /dev/ttyACM1
```

Send `/echo test` on MeshCore Public channel.

### Expected Output

```
✅ Connected to MeshCore on /dev/ttyACM1
🎧 Subscribing to CHANNEL_MSG_RECV events...
✅ Subscribed successfully

🎧 Listening for messages...

================================================================================
📡 MESHCORE EVENT RECEIVED
================================================================================
Event Type: CHANNEL_MSG_RECV
✅ This is a CHANNEL_MSG_RECV (Public channel message)

📋 RAW HEX DATA (40 bytes):
    Hex: 39 e7 15 00 11 93 a0 56...

🔍 DECODED PACKET:
  From: 0x56a09311
  To: 0xe151a2d3
  Payload Type: 15 (Encrypted)
```

---

## Key Takeaways

### 1. Two Different APIs
- `events.subscribe()` for CHANNEL_MSG_RECV
- `dispatcher.subscribe()` for other events

### 2. Check Bot Code
- Bot uses `events.subscribe()` first (line 842)
- Falls back to `dispatcher.subscribe()` (line 881)

### 3. Not Interchangeable
- Using wrong API = callback never invoked
- Must use correct API for each event type

### 4. Callback Signature
```python
def on_message(event):
    # event is the full event object
    # event.payload contains the actual data
```

---

## Summary

**Problem:** Used `dispatcher.subscribe()` for CHANNEL_MSG_RECV  
**Solution:** Use `events.subscribe()` for CHANNEL_MSG_RECV  
**Result:** Messages now appear! ✅

This was the **5th and final fix** - using the correct subscription API for channel messages.

---

## The Complete Journey

1. ✅ Script selection (meshcore vs meshtastic)
2. ✅ Initialization (async factory method)
3. ✅ Event loop (run_forever)
4. ❌ Subscription attempt 1 (direct subscribe)
5. ✅ **Subscription final (events.subscribe)** ← THIS FIX!

**Status: COMPLETE** 🎉
