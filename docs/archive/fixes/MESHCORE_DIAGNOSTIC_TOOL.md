# MeshCore Public Channel Diagnostic Tool

## The Correct Tool for MeshCore

This tool debugs **MeshCore**, not Meshtastic!

## Installation

```bash
# Required
pip install meshcore

# Optional but recommended
pip install meshcoredecoder
```

## Usage

```bash
python3 listen_meshcore_channel.py
```

## What It Does

**Connects to MeshCore:**
- Uses `meshcore.MeshCore` library (NOT Meshtastic!)
- Connects to /dev/ttyACM2 @ 115200 baud
- Subscribes to CHANNEL_MSG_RECV events

**Logs Everything:**
- Raw MeshCore events
- Event types
- Packet data (raw bytes)
- Decoded packet fields (if decoder available)
- Payload hex dumps

## Expected Output

```
🎯 MeshCore Public Channel Listener
Device: /dev/ttyACM2 @ 115200 baud

🔌 Connecting to MeshCore on /dev/ttyACM2...
✅ Connected to MeshCore
📡 Subscribing to CHANNEL_MSG_RECV...
✅ Subscribed successfully

🎧 Listening for messages...
   Send /echo test on MeshCore Public channel to see output!
```

## When You Send /echo test

```
================================================================================
📡 MESHCORE EVENT RECEIVED
================================================================================
Event Type: EventType.CHANNEL_MSG_RECV
✅ This is a CHANNEL_MSG_RECV (Public channel message)

📋 RAW DATA:
  Type: <class 'dict'>
  Keys: ['raw_packet', 'decoded', ...]
  raw_packet: 40 bytes
    Hex: 39 e7 15 00 11 93 a0 56 d3 a2 51 e1 a8 33 51 0d ...
    Raw: b'9\xe7\x15\x00\x11\x93\xa0V...'

🔍 DECODED PACKET (meshcore-decoder):
  From: 0x56a09311
  To: 0xe151a2d3
  Type: 15 (encrypted TEXT_MESSAGE_APP)
  Payload: 39 bytes
    Hex: 39 e7 15 00 11 93 a0 56 ...
    Raw: b'9\xe7\x15\x00...'
    
================================================================================
```

## What to Look For

### 1. Event Type
- Should be `CHANNEL_MSG_RECV` for public channel messages
- Confirms MeshCore is receiving the message

### 2. Raw Packet Data
- The actual bytes MeshCore received over RF
- This is what needs to be decrypted

### 3. Decoded Fields
- From/To addresses
- Packet type (15 = encrypted TEXT_MESSAGE_APP)
- Payload bytes (the encrypted message)

### 4. Payload Hex
- First 20-30 bytes show encryption pattern
- Share this with encryption analysis

## Key Questions This Answers

1. **Does MeshCore receive the message?**
   - Look for CHANNEL_MSG_RECV event

2. **Is the payload encrypted?**
   - Check if payload contains readable text or binary data

3. **What does MeshCore forward to bot?**
   - The raw_packet and decoded fields
   - This is exactly what bot receives

4. **Does MeshCore decrypt?**
   - If text field is present and readable → Yes
   - If only encrypted payload → No, bot must decrypt

## Troubleshooting

### meshcore not installed
```bash
pip install meshcore
```

### Permission denied on /dev/ttyACM2
```bash
sudo chmod 666 /dev/ttyACM2
# Or add user to dialout group
sudo usermod -a -G dialout $USER
```

### No CHANNEL_MSG_RECV events
The script will automatically subscribe to all available events if CHANNEL_MSG_RECV is not available.

## Comparison: MeshCore vs Meshtastic

| Aspect | Meshtastic | MeshCore |
|--------|-----------|----------|
| Library | `meshtastic` | `meshcore` |
| Connection | SerialInterface | MeshCore class |
| Events | onReceive callback | subscribe(EventType) |
| Use case | Standard Meshtastic | MeshCore protocol |
| This tool | ❌ Wrong tool | ✅ Correct tool |

## What This Shows

This diagnostic tool shows:
- ✅ Raw MeshCore packets (binary protocol)
- ✅ How MeshCore forwards data to bot
- ✅ Whether payload is encrypted
- ✅ Exact packet structure
- ✅ What bot actually receives

**This is the data we need to understand MeshCore encryption and make /echo work!**

## Next Steps

After running this tool and sending `/echo test`:

1. **Copy the output** (especially payload hex)
2. **Share findings** - we need to see the payload structure
3. **Analyze encryption** - determine PSK and method
4. **Implement decryption** - in bot or MeshCore
5. **Make /echo work!** 🎉

## Files

- `listen_meshcore_channel.py` - This tool (MeshCore)
- `listen_meshcore_public.py` - Old tool (Meshtastic - WRONG)

Use `listen_meshcore_channel.py` to debug MeshCore!
