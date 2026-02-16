# MeshCore Decryption Fix - User's Key Insight

## The Problem

The bot was trying to manually decrypt MeshCore Public channel messages using a PSK from the config file, but:
1. Decryption was producing garbage
2. Messages showed as `[ENCRYPTED]`
3. Bot couldn't process commands

## The User's Breakthrough

**"when I use the CLI i do not need to provide any key, so why a wrapper for the cli need a key/decipher?"**

This question revealed the fundamental issue: **meshcore-cli doesn't decrypt because the MeshCore library does it internally!**

## How MeshCore Library Works

### The Library Handles Decryption

The MeshCore library:
1. Reads PSK configuration from the **Meshtastic device** (not from Python config)
2. Automatically decrypts received messages using the device's configured keys
3. Provides decrypted text through clean events

### Events Provided by Library

**CONTACT_MSG_RECV** - Direct Messages (DMs)
- Library handles ECDH decryption internally
- Provides: `{'text': 'message', 'contact_id': 0xXXXXXXXX, ...}`
- Already decrypted!

**CHANNEL_MSG_RECV** - Public Channel Messages
- Library handles PSK decryption internally
- Provides: `{'text': 'message', 'sender_id': 0xXXXXXXXX, ...}`
- Already decrypted!

**RX_LOG_DATA** - Raw RF Packets
- Provides: Raw encrypted RF packet data
- Meant for RF monitoring and statistics
- **NOT** for message processing!

## What We Were Doing Wrong

### Using RX_LOG_DATA for Messages

```python
# WRONG APPROACH
meshcore.events.subscribe(EventType.RX_LOG_DATA, handler)
# → Receives encrypted RF packets
# → Try to manually decrypt with PSK from config
# → Wrong PSK / Wrong approach
# → Garbage output
# → Mark as [ENCRYPTED]
```

## The Correct Solution

### Use Library Events (meshcore-cli Way)

```python
# CORRECT APPROACH - For Public Channel
meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, handler)
# → Library decrypts with device's PSK
# → Receives: {'text': '/hello test', 'sender_id': ..., ...}
# → Already decrypted!
# → Just display it!

# CORRECT APPROACH - For DMs
meshcore.events.subscribe(EventType.CONTACT_MSG_RECV, handler)
# → Library decrypts with ECDH
# → Receives: {'text': 'hi!', 'contact_id': ..., ...}
# → Already decrypted!
# → Just display it!
```

**No PSK needed. No manual decryption. Just read the text!**

## Configuration Fix

### Step 1: Edit config.py

```python
# Change this line in config.py
MESHCORE_RX_LOG_ENABLED = False  # Disable RX_LOG for message processing
```

This will:
- ✅ Disable RX_LOG_DATA event subscription
- ✅ Enable CHANNEL_MSG_RECV event subscription (Public channel)
- ✅ Keep CONTACT_MSG_RECV event subscription (DMs)
- ✅ Use library-decrypted messages (like meshcore-cli!)

### Step 2: Restart Bot

```bash
sudo systemctl restart meshtastic-bot
```

### Step 3: Test

Send a message to the Public channel:
```
/hello test
```

Check logs:
```bash
sudo journalctl -u meshtastic-bot -f
```

**Expected logs:**
```
📢 [MESHCORE-CHANNEL] Canal public message reçu!
📦 [CHANNEL] Message text: "/hello test"
📦 [CHANNEL] Processing command: /hello test
✅ Command executed
```

**No decryption logs. No PSK. Just works!**

## Why This Works

### meshcore-cli Doesn't Decrypt

When you run:
```bash
meshcore-cli -s /dev/ttyACM1 -b 115200 ms
```

It displays:
```
public (1): RR92F1: /echo test
```

**No PSK provided. No decryption code. Just displays what the library gives!**

### Our Wrapper Should Do The Same

Instead of:
1. ❌ Subscribe to RX_LOG_DATA
2. ❌ Try to decrypt manually
3. ❌ Get garbage

We should:
1. ✅ Subscribe to CHANNEL_MSG_RECV
2. ✅ Read pre-decrypted text from library
3. ✅ Display it

**Exactly like meshcore-cli!**

## Summary

| Aspect | Wrong Way (RX_LOG_DATA) | Right Way (CHANNEL_MSG_RECV) |
|--------|------------------------|------------------------------|
| **Event** | RX_LOG_DATA | CHANNEL_MSG_RECV |
| **Data** | Encrypted RF packets | Pre-decrypted text |
| **Decryption** | Manual (with wrong PSK) | Library (with device PSK) |
| **Result** | Garbage / [ENCRYPTED] | Clean text |
| **PSK needed?** | Yes (but wrong one) | No (library has it) |
| **Like meshcore-cli?** | No | Yes! ✅ |

## Credits

**Thank you to the user for the key insight!** The question "why does meshcore-cli not need a key?" revealed the fundamental misunderstanding and led to the correct solution.

The answer: **Because the library does the decryption, not the application!**

## Testing Status

- ✅ Configuration change documented
- ⏳ Awaiting user testing with `MESHCORE_RX_LOG_ENABLED = False`
- ⏳ Expect Public channel messages to decrypt successfully
- ⏳ Expect bot to process commands correctly

**Just like meshcore-cli!** 🎉
