# Quick Start: MeshCore Diagnostic Tool

## The Correct Tool!

This debugs **MeshCore** (not Meshtastic).

## Install

```bash
pip install meshcore meshcoredecoder
```

## Run

```bash
cd /home/dietpi/bot

# Default port (/dev/ttyACM2)
python3 listen_meshcore_channel.py

# Or specify your USB port
python3 listen_meshcore_channel.py /dev/ttyACM1
```

## Port Configuration

**Check your device:**
```bash
ls /dev/ttyACM*
```

**Use the correct port:**
```bash
# Show help
python3 listen_meshcore_channel.py --help

# Specify port
python3 listen_meshcore_channel.py /dev/ttyACM1
```

## Test

Send `/echo test` on MeshCore Public channel and watch the output!

## What You'll See

```
🎯 MeshCore Public Channel Listener

🔌 Connecting to MeshCore on /dev/ttyACM2...
✅ Connected to MeshCore
📡 Subscribing to CHANNEL_MSG_RECV...
✅ Subscribed successfully

🎧 Listening for messages...

================================================================================
📡 MESHCORE EVENT RECEIVED
================================================================================
Event Type: EventType.CHANNEL_MSG_RECV

📋 RAW DATA:
  raw_packet: 40 bytes
    Hex: 39 e7 15 00 11 93 a0 56 d3 a2 51 e1 ...
    
🔍 DECODED PACKET:
  From: 0x56a09311
  To: 0xe151a2d3
  Type: 15 (TEXT_MESSAGE_APP encrypted)
  Payload: 39 bytes (the encrypted /echo test)
================================================================================
```

## Share This

Copy and share:
1. The complete output
2. The payload hex dump
3. Whether there's a "Text:" field with readable content

This will show us how to decrypt MeshCore messages!

## Full Docs

See `MESHCORE_DIAGNOSTIC_TOOL.md` for complete documentation.

## Status

✅ Correct tool for MeshCore  
✅ Ready to use  
⏳ Awaiting your test results!
