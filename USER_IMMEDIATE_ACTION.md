# 🚨 IMMEDIATE ACTION REQUIRED 🚨

## You're Using the WRONG Script!

### Current Error

You're running:
```bash
python3 listen_meshcore_public.py /dev/ttyACM1  # ❌ WRONG!
```

Getting:
```
❌ ERROR: Timed out waiting for connection completion
```

## The Fix

**Run this instead:**
```bash
python3 listen_meshcore_debug.py /dev/ttyACM1  # ✅ CORRECT!
```

## Why You Got Timeout

| What You Did | What Happened |
|--------------|---------------|
| Used `listen_meshcore_public.py` | ❌ Uses meshtastic library |
| Your node runs MeshCore | ✅ You said "bot works well" |
| Library ≠ Firmware | ❌ Protocol mismatch → timeout |

## The Solution

### Step 1: Install Dependencies (if needed)
```bash
pip install meshcore meshcoredecoder
```

### Step 2: Run CORRECT Script
```bash
cd /home/dietpi/bot
python3 listen_meshcore_debug.py /dev/ttyACM1
```

### Step 3: Test
Send `/echo test` on MeshCore Public channel and watch the output!

## Why This Works

**Simple logic:**
1. You said: "the node works well with the bot"
2. Bot uses MeshCore library
3. Therefore: Your node runs MeshCore firmware
4. Therefore: Must use MeshCore diagnostic script
5. That script is: `listen_meshcore_debug.py` ✅

## Expected Result

When you run the CORRECT script:

```
🎯 MeshCore Debug Listener (Pure MeshCore - No Meshtastic!)
Device: /dev/ttyACM1 @ 115200 baud
Started: 2026-02-12 21:XX:XX

🔌 Connecting to MeshCore...
✅ Connected to MeshCore
🎧 Subscribed to CHANNEL_MSG_RECV events
🎧 Listening for messages...

Press Ctrl+C to stop

================================================================================
📡 MESHCORE EVENT RECEIVED
================================================================================
Event Type: CHANNEL_MSG_RECV
...
```

## Scripts Available

| Script | Library | For Firmware | Your Case |
|--------|---------|--------------|-----------|
| `listen_meshcore_debug.py` | meshcore | MeshCore | ✅ YES |
| `listen_meshcore_public.py` | meshtastic | Meshtastic | ❌ NO |

## Quick Reference

### WRONG (causes timeout):
```bash
python3 listen_meshcore_public.py /dev/ttyACM1  # ❌
```

### CORRECT (works):
```bash
python3 listen_meshcore_debug.py /dev/ttyACM1  # ✅
```

## Summary

- ❌ **Old script:** Uses meshtastic → Timeout on MeshCore
- ✅ **New script:** Uses meshcore → Works on MeshCore
- 🎯 **Your node:** MeshCore (bot works)
- ✅ **Solution:** Use listen_meshcore_debug.py

## Command to Run NOW

```bash
cd /home/dietpi/bot
python3 listen_meshcore_debug.py /dev/ttyACM1
```

**No more timeout - uses correct protocol!** 🎉
