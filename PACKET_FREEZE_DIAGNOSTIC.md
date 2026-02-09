# Packet Freeze Diagnostic Guide

## Problem
Packet count frozen - not increasing despite bot running:
```
07:50:10 - Packets: 1820
07:52:10 - Packets: 1820 (no change)
07:58:10 - Packets: 1820 (no change)
```

Status says "Packets flowing normally" but counter frozen.

## Root Cause
**on_message() callback is NOT being invoked.**

The 1820 packets shown are from SQLite persistence loaded at startup, but no NEW packets are arriving.

## Solution - Ultra-Visible Diagnostics

Added ultra-visible logging at the very start of on_message():

```python
info_print("🔔🔔🔔 ========== on_message() CALLED ==========")
info_print(f"🔔 Packet: {packet is not None}")
info_print(f"🔔 Interface: {type(interface).__name__}")
info_print(f"🔔 network_source: {network_source}")
info_print(f"🔔 From ID: 0x{from_id:08x}")
info_print("🔔🔔🔔 ==========================================")
```

These logs will appear **every time** on_message() is called.

## Deployment

```bash
cd /home/dietpi/bot
git pull
sudo systemctl restart meshtastic-bot

# Monitor for callback invocation
journalctl -u meshtastic-bot -f | grep "🔔"
```

Then send a DM to the bot.

## Expected Results

### Scenario 1: Callback Works
```
🔔🔔🔔 ========== on_message() CALLED ==========
🔔 Packet: True
🔔 Interface: SerialInterface
🔔 network_source: None
🔔 From ID: 0x12345678
🔔🔔🔔 ==========================================
```

**Interpretation**: Callback is being invoked, issue is elsewhere in processing chain.

### Scenario 2: NO 🔔 Logs (Current Issue)

**No logs at all when sending DM.**

**Interpretation**: Callback is NOT being invoked.

## Troubleshooting Steps

If NO 🔔 logs appear, follow these steps:

### Step 1: Verify Callback Configuration

```bash
journalctl -u meshtastic-bot -n 500 | grep "callback configured"
```

**Expected:**
```
[INFO] ✅ Meshtastic callback configured
```

**If missing:** Callback was not configured during startup. Check dual mode initialization logs.

### Step 2: Check Interface State

```bash
journalctl -u meshtastic-bot -n 500 | grep -i "interface.*active\|serial.*connected"
```

**Expected:**
```
[INFO] ✅ Meshtastic interface active
```

**If missing:** Interface may have failed to start.

### Step 3: Check Serial Device

```bash
ls -la /dev/ttyACM*
```

**Expected:**
```
crw-rw---- 1 root dialout ... /dev/ttyACM0
```

**If missing:** Device not connected or recognized.

### Step 4: Test Device Directly

```bash
python3 -m meshtastic --port /dev/ttyACM0 --info
```

**Expected:** Shows node information

**If fails:** Device not responding or wrong port.

### Step 5: Check Startup Logs

```bash
journalctl -u meshtastic-bot -n 1000 | grep -A 10 "Creating Meshtastic SerialInterface"
```

Look for:
- ✅ Success message
- ❌ Timeout message
- ❌ Error message

## Common Issues

### Issue 1: Callback Never Configured

**Symptom:** No "callback configured" log

**Cause:** Dual mode initialization failed to configure callback

**Fix:** Check dual mode initialization logs for errors

### Issue 2: Interface Timed Out

**Symptom:** "TIMEOUT: SerialInterface creation exceeded 10s"

**Cause:** Device not responding

**Fix:**
- Power cycle device
- Reset device
- Check USB cable
- Try different USB port

### Issue 3: Wrong Port

**Symptom:** Callback configured but no packets

**Cause:** Configured wrong serial port

**Fix:** Check config.py SERIAL_PORT matches actual device

### Issue 4: Device in Wrong Mode

**Symptom:** Device exists but not sending packets

**Cause:** Device in bootloader or wrong mode

**Fix:**
- Reset device
- Check device firmware
- Verify device is in normal mode (not bootloader)

## Success Criteria

✅ 🔔 logs appear when sending DM  
✅ Packet count increases  
✅ Bot responds to commands  

## Files Modified

- main_bot.py - Added ultra-visible entry logging

## Summary

**Problem:** Packet count frozen  
**Root Cause:** on_message() not being called  
**Solution:** Ultra-visible diagnostics  
**Result:** Know immediately if callback works  

If 🔔 logs don't appear, callback is not being invoked - interface issue.
