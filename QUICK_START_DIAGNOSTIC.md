# Quick Start: MeshCore Public Channel Diagnostic Tool

## Fixed and Ready!

The diagnostic script has been fixed and is ready to use.

## Quick Start

```bash
cd /home/dietpi/bot

# Default port (/dev/ttyACM2)
python3 listen_meshcore_public.py

# Or specify your USB port
python3 listen_meshcore_public.py /dev/ttyACM1
```

## Port Configuration

**Check your device:**
```bash
ls /dev/ttyACM*
```

**Use the correct port:**
```bash
# Show help
python3 listen_meshcore_public.py --help

# Specify port
python3 listen_meshcore_public.py /dev/ttyACM1
```

## What You'll See

```
🎯 MeshCore Public Channel Listener
Device: /dev/ttyACM1 @ 115200 baud

🔌 Connecting to /dev/ttyACM1...
✅ Connected successfully
📡 My node ID: 0x12345678
🎧 Listening for messages...
```

## Test It

1. **Run the script** (above)
2. **Send a message**: `/echo test` on MeshCore Public channel
3. **Watch the output**: Detailed packet information will appear

## Expected Output for /echo test

```
================================================================================
📡 PACKET RECEIVED
================================================================================
From: 0x56a09311
To: 0xe151a2d3
Channel: 0

📋 DECODED DATA:
  Portnum: TEXT_MESSAGE_APP
  Payload (bytes): 39 bytes
  Payload (hex): 39 e7 15 00 11 93 a0 56 d3 a2 51 e1 a8 33 51 0d ...
  
✅ This is a TEXT_MESSAGE_APP
⚠️  ENCRYPTED: Has payload but no text
   Payload may be encrypted data
```

## What to Look For

1. **Portnum**: Should be `TEXT_MESSAGE_APP` ✅
2. **Payload hex**: The encrypted message bytes
3. **Encryption status**: Will show if encrypted
4. **Text field**: Empty if encrypted

## Share These Details

When reporting findings, include:
- The complete packet output
- Payload hex dump (first 20-30 bytes is enough)
- Encryption status
- Whether text appears

## The Goal

This output will help determine:
- What encryption method MeshCore uses
- What PSK is needed (if any)
- How to decrypt the messages
- How to make /echo work!

## Problems?

See `LISTEN_MESHCORE_PUBLIC.md` for full documentation and troubleshooting.

## Status

✅ Script fixed and working  
✅ Ready for testing  
⏳ Awaiting your results!
