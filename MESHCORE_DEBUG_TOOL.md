# Pure MeshCore Debug Tool

## Overview

**listen_meshcore_debug.py** - Pure MeshCore diagnostic tool with NO meshtastic imports.

This is the CORRECT tool for debugging MeshCore Public channel messages.

## User Request

> "No, no no you stil import meshtastic code ! We want a meshcore decoder !!!"

**Fulfilled!** This tool uses ONLY MeshCore libraries.

## The Right Libraries

### Uses ONLY:
- ✅ `meshcore` - MeshCore serial interface
- ✅ `meshcoredecoder` - MeshCore packet decoder

### Does NOT use:
- ❌ `meshtastic` - Wrong library for MeshCore

## Installation

```bash
pip install meshcore meshcoredecoder
```

## Usage

### Basic Usage

```bash
# With custom port
python3 listen_meshcore_debug.py /dev/ttyACM1

# With default port (/dev/ttyACM2)
python3 listen_meshcore_debug.py

# Show help
python3 listen_meshcore_debug.py --help
```

### Find Your USB Port

```bash
ls /dev/ttyACM*
# Output: /dev/ttyACM0  /dev/ttyACM1  /dev/ttyACM2
```

## Expected Output

### Connection

```
================================================================================
🎯 MeshCore Debug Listener (Pure MeshCore - No Meshtastic!)
================================================================================
Device: /dev/ttyACM1 @ 115200 baud
Started: 2026-02-12 21:39:45.123
Purpose: Listen to MeshCore messages and decode packets

Libraries used:
  ✅ meshcore - MeshCore serial interface
  ✅ meshcoredecoder - Packet decoder

Press Ctrl+C to stop
================================================================================

[2026-02-12 21:39:45.456] 🔌 Connecting to MeshCore...
✅ Connected to MeshCore on /dev/ttyACM1
🎧 Subscribing to CHANNEL_MSG_RECV events...
✅ Subscribed successfully

🎧 Listening for messages...
   Send '/echo test' on MeshCore Public channel to see output!
```

### Message Received

```
================================================================================
[2026-02-12 21:40:12.789] 📡 MESHCORE EVENT RECEIVED
================================================================================
Event Type: EventType.CHANNEL_MSG_RECV
✅ This is a CHANNEL_MSG_RECV (Public channel message)

📋 RAW DATA:
  Keys: ['raw_packet', 'data']
  raw_packet: 40 bytes
    Hex: 39 e7 15 00 11 93 a0 56 d3 a2 51 e1 a8 33 51 0d 2b 20 74 97 ac 02 3d ...

🔍 DECODED PACKET:
  From: 0x56a09311
  To: 0xe151a2d3
  Payload Type: 15 (Encrypted)
  Route: Flood
  Hops: 0

📦 PAYLOAD:
  Type: dict
  Keys: ['raw', 'decoded']
  Raw data: 39 bytes (hex string)
    Hex: 39 e7 15 00 11 93 a0 56 d3 a2 51 e1 a8 33 51 0d 2b 20 74 97 ac 02 3d ...
  ⚠️  ENCRYPTED: Has raw payload but no decoded text
     Payload may be encrypted with PSK
```

## What This Shows

For each MeshCore message, you'll see:

1. **Event Type** - CHANNEL_MSG_RECV for public messages
2. **Raw Hex Data** - Exact bytes received
3. **Decoded Packet Structure:**
   - From/To addresses (sender/receiver)
   - Payload type (1=text, 15=encrypted, etc.)
   - Route type (Flood, Direct, etc.)
   - Hop count
4. **Payload Details:**
   - Text (if decoded)
   - Raw hex (if encrypted)
   - Encryption indicator

## Use Cases

### Debug Encryption

**Question:** Why does `/echo test` show as `[ENCRYPTED]`?

**Answer:** This tool shows:
- Payload type is 15 (encrypted)
- Has raw hex but no decoded text
- Needs PSK decryption

### Identify Message Format

**Question:** What format does MeshCore use?

**Answer:** This tool shows:
- Exact hex bytes
- Packet structure
- Payload encoding

### Verify Connection

**Question:** Is MeshCore receiving messages?

**Answer:** This tool shows:
- Each CHANNEL_MSG_RECV event
- Sender/receiver IDs
- Message arrival time

## Comparison

### Tool Comparison

| Tool | Libraries | Correct for MeshCore? |
|------|-----------|----------------------|
| **listen_meshcore_debug.py** | meshcore + meshcoredecoder | ✅ **YES** |
| listen_meshcore_public.py | meshtastic | ❌ NO |
| listen_meshcore_channel.py | Mixed approach | ❌ NO |

### Library Comparison

| Library | Purpose | Use for |
|---------|---------|---------|
| **meshtastic** | Standard Meshtastic protocol | ❌ Not for MeshCore |
| **meshcore** | MeshCore serial interface | ✅ MeshCore connection |
| **meshcoredecoder** | MeshCore packet decoder | ✅ MeshCore packets |

## Benefits

1. ✅ **Pure MeshCore** - Uses correct libraries
2. ✅ **No meshtastic** - No wrong imports
3. ✅ **Raw hex visible** - Debug encryption
4. ✅ **Complete decoding** - Full packet structure
5. ✅ **Port argument** - Flexible configuration
6. ✅ **User-requested** - Exactly what was needed

## Troubleshooting

### Error: meshcore library not found

```
❌ ERROR: meshcore library not found
   Install with: pip install meshcore
```

**Solution:**
```bash
pip install meshcore
```

### Error: meshcoredecoder library not found

```
⚠️  WARNING: meshcoredecoder library not found
   Install with: pip install meshcoredecoder
   Will show raw data only
```

**Solution:**
```bash
pip install meshcoredecoder
```

Tool still works without decoder, but shows less detail.

### No messages received

**Check:**
1. Correct USB port? (`ls /dev/ttyACM*`)
2. MeshCore device connected?
3. Messages being sent on Public channel?

**Test:**
Send `/echo test` on MeshCore Public channel from another device.

### Connection timeout

**Check:**
1. Port exists: `ls /dev/ttyACM*`
2. Permission: `sudo chmod 666 /dev/ttyACM1`
3. Not in use: Close other programs using the port

## Example Session

```bash
# 1. Install dependencies
pip install meshcore meshcoredecoder

# 2. Find USB port
ls /dev/ttyACM*
# Output: /dev/ttyACM1

# 3. Run diagnostic tool
python3 listen_meshcore_debug.py /dev/ttyACM1

# 4. From another device, send on MeshCore Public:
#    /echo test

# 5. Observe detailed output showing:
#    - Raw hex payload
#    - Decoded packet structure
#    - Encryption status
#    - Sender/receiver IDs

# 6. Copy hex payload for analysis
# 7. Share findings
```

## Next Steps

After running this tool and observing output:

1. **Identify encryption method** - Check payload type
2. **Get hex payload** - Copy raw hex data
3. **Determine PSK** - What key is needed?
4. **Implement decryption** - In bot or MeshCore
5. **Make /echo work** - Process decrypted commands

## Summary

**This is the CORRECT diagnostic tool for MeshCore:**
- ✅ Uses pure MeshCore libraries
- ✅ No meshtastic imports
- ✅ Shows complete packet details
- ✅ Identifies encryption
- ✅ User-requested fix

**Use this tool to debug MeshCore Public channel encryption!**
