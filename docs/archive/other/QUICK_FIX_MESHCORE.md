# Quick Fix: MeshCore Not Visible

## Problem
No MeshCore traffic displayed, bot not responding to MeshCore DMs.

## Solution Applied

### 1. Fixed Logging (traffic_monitor.py)
- Changed from always using `[DEBUG][MT]` to dynamic selection
- MeshCore packets now use `[DEBUG][MC]` tag
- Easy to distinguish which network each packet came from

### 2. Enhanced Diagnostics (meshcore_serial_interface.py)
- Startup diagnostics banner shows port/thread status
- Periodic heartbeat every 60 seconds
- Hex dumps of received data
- Clear indicators if data arriving or not

## Deploy (30 seconds)

```bash
cd /home/dietpi/bot
git checkout copilot/update-sqlite-data-cleanup
git pull
sudo systemctl restart meshtastic-bot
```

## Quick Checks

### Check Threads Running
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep "confirmed running"
```
**Expected:**
```
✅ [MESHCORE] Read thread confirmed running
✅ [MESHCORE] Poll thread confirmed running
```

### Monitor Activity (60s updates)
```bash
journalctl -u meshtastic-bot -f | grep "HEARTBEAT"
```
**Expected:**
```
🔄 [MESHCORE-HEARTBEAT] Read loop active: 600 iterations, 0 data packets received
```
- Iterations increase = thread running ✅
- Data packets > 0 = receiving data ✅
- Data packets = 0 = no data arriving ⚠️

### Watch for MC Packets
```bash
journalctl -u meshtastic-bot -f | grep "\[MC\]"
```
**Expected (when data arrives):**
```
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de User...
[DEBUG][MC] 🔗 MESHCORE TEXTMESSAGE from User...
```

## Troubleshooting

### No Data Packets After 2 Minutes

**Check port:**
```bash
ls -la /dev/ttyUSB*
grep MESHCORE_SERIAL_PORT config.py
```

**Check permissions:**
```bash
groups dietpi
# Should include: dialout
```

**Fix permissions:**
```bash
sudo usermod -a -G dialout dietpi
sudo reboot
```

### No Threads Confirmed Running

**Check errors:**
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep -i "error\|exception"
```

### No Heartbeat Messages

**Check dual mode active:**
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep "MODE DUAL"
```
Should see: `🔄 MODE DUAL: Connexion simultanée`

## Configuration Checklist

```python
# config.py
DUAL_NETWORK_MODE = True           # ✅ Both networks
MESHTASTIC_ENABLED = True          # ✅ Primary
MESHCORE_ENABLED = True            # ✅ Secondary
SERIAL_PORT = "/dev/ttyACM0"       # ✅ Meshtastic
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # ✅ MeshCore (DIFFERENT!)
```

## Expected Behavior

**When working:**
- Diagnostics banner at startup
- Heartbeat every 60s (with data count)
- `[DEBUG][MC]` logs when MeshCore data arrives
- Hex dumps of serial data

**When no data:**
- Diagnostics banner at startup  
- Heartbeat every 60s (0 data packets)
- No `[DEBUG][MC]` logs (normal if no traffic)

---

**Complete docs:** `FIX_MESHCORE_VISIBILITY.md` (11 KB)
