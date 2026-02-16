# Which Diagnostic Script to Use?

## Quick Answer

**Does the bot work with your node?**
- ✅ **YES** → Your node runs **MeshCore** firmware → Use `listen_meshcore_debug.py`
- ❌ **NO** → Your node runs **Meshtastic** firmware → Use `listen_meshcore_public.py`

## User's Case

User said: *"the node works well with the bot"*

**This means:**
- ✅ Node is running MeshCore firmware
- ✅ Must use MeshCore diagnostic script
- ❌ Meshtastic script will timeout

**Command to run:**
```bash
python3 listen_meshcore_debug.py /dev/ttyACM1
```

## The Problem

**Timeout Error:**
```
❌ ERROR: Timed out waiting for connection completion
```

**Cause:** Using wrong script for firmware type!

## Decision Tree

```
What firmware is on your node?
├─ MeshCore (bot works)
│  └─ Use: listen_meshcore_debug.py ✅
│     └─ Library: meshcore + meshcoredecoder
│
└─ Meshtastic (standard firmware)
   └─ Use: listen_meshcore_public.py
      └─ Library: meshtastic
```

## Scripts Comparison

| Script | Library | Firmware | When to Use |
|--------|---------|----------|-------------|
| **listen_meshcore_debug.py** | `meshcore` + `meshcoredecoder` | MeshCore | Bot works ✅ |
| **listen_meshcore_public.py** | `meshtastic` | Meshtastic | Bot doesn't work |

## Why Timeout Happens

**Protocol Mismatch:**

1. **Meshtastic library** expects standard Meshtastic protocol
2. **MeshCore firmware** uses different binary protocol
3. When mismatched → timeout waiting for expected response
4. Solution: Use matching library and firmware

## How to Identify Your Firmware

### Method 1: Check if Bot Works
- **Bot works** → MeshCore firmware ✅
- **Bot doesn't work** → Meshtastic firmware

### Method 2: Check Bot Configuration
Look at `meshcore_cli_wrapper.py` usage in bot:
- If bot imports `meshcore` → Node is MeshCore
- If bot imports `meshtastic` → Node is Meshtastic

### Method 3: Try Both Scripts
- **listen_meshcore_debug.py** connects → MeshCore
- **listen_meshcore_public.py** connects → Meshtastic

## Installation Requirements

### For MeshCore (User's Case)
```bash
pip install meshcore meshcoredecoder
```

### For Meshtastic
```bash
pip install meshtastic
```

## Usage

### MeshCore Node (Bot Works)
```bash
# Install dependencies
pip install meshcore meshcoredecoder

# Run diagnostic tool
python3 listen_meshcore_debug.py /dev/ttyACM1
```

### Meshtastic Node (Standard Firmware)
```bash
# Install dependencies
pip install meshtastic

# Run diagnostic tool
python3 listen_meshcore_public.py /dev/ttyACM1
```

## Expected Output

### MeshCore (listen_meshcore_debug.py)
```
🎯 MeshCore Debug Listener (Pure MeshCore - No Meshtastic!)
Device: /dev/ttyACM1 @ 115200 baud

🔌 Connecting to MeshCore...
✅ Connected to MeshCore
🎧 Subscribed to CHANNEL_MSG_RECV events
🎧 Listening for messages...

================================================================================
📡 MESHCORE EVENT RECEIVED
================================================================================
Event Type: CHANNEL_MSG_RECV
...
```

### Meshtastic (listen_meshcore_public.py)
```
🎯 MeshCore Public Channel Listener
Device: /dev/ttyACM1 @ 115200 baud

🔌 Connecting to /dev/ttyACM1...
✅ Connected successfully
📡 My node ID: 0x...
🎧 Listening for messages...
...
```

## Troubleshooting

### Timeout Error
**Error:** `Timed out waiting for connection completion`

**Solutions:**
1. ✅ **Use correct script** for your firmware type
2. Check USB port (`ls /dev/ttyACM*`)
3. Stop the bot (only one connection allowed)
4. Check USB permissions

### Wrong Script Symptoms
- Timeout after 30 seconds
- No connection established
- No packets received

### Correct Script Symptoms
- Connects within seconds
- Shows node information
- Receives packets
- No timeout errors

## Summary

**Simple Rule:**
- **Bot works with MeshCore** → Use `listen_meshcore_debug.py` ✅
- **Bot uses Meshtastic** → Use `listen_meshcore_public.py`

**User's Case:**
- Bot works ✅
- Node is MeshCore ✅
- Use: `listen_meshcore_debug.py` ✅

**Command:**
```bash
python3 listen_meshcore_debug.py /dev/ttyACM1
```

## Files in Repository

| File | Purpose | Library | Use When |
|------|---------|---------|----------|
| `listen_meshcore_debug.py` | MeshCore diagnostics | meshcore | Bot works ✅ |
| `listen_meshcore_public.py` | Meshtastic diagnostics | meshtastic | Standard firmware |
| `listen_meshcore_channel.py` | Old mixed approach | Mixed | Deprecated |

**Use `listen_meshcore_debug.py` for MeshCore nodes!**
