# QUICK FIX: Bot Not Receiving Packets (0 Packets)

## Problem
Bot shows: `Packets this session: 0` despite messages being sent.

## Root Cause
Missing callback configuration when dual mode fails.

## Quick Fix

### Deploy
```bash
cd /home/dietpi/bot
git pull
sudo systemctl restart meshtastic-bot
```

### Verify Fix Applied
```bash
journalctl -u meshtastic-bot -n 100 | grep "Meshtastic callback"
```

**Expected:**
```
[INFO] ✅ Meshtastic callback configured
[INFO] ✅ Meshtastic interface active (fallback from dual mode)
```

### Test Packet Reception
Send a DM to the bot, then check:
```bash
journalctl -u meshtastic-bot -n 50 | grep "Packets this session"
```

**Expected:**
```
[INFO] 📦 Packets this session: 1  (or higher)
```

## What Was Fixed

**Before:**
- Dual mode enabled, MeshCore fails
- Falls back to Meshtastic
- **Callback never configured** ❌
- Bot deaf to all messages

**After:**
- Dual mode enabled, MeshCore fails
- Falls back to Meshtastic
- **Callback configured automatically** ✅
- Bot receives all messages

## Verification Checklist

- [ ] Deploy updated code
- [ ] Restart bot
- [ ] Check startup logs show callback configured
- [ ] Send test DM to bot
- [ ] Verify packet counter increases
- [ ] Verify bot responds to commands

## Expected Logs

**Startup:**
```
[INFO] 🔗 MESHCORE DUAL MODE INITIALIZATION
[ERROR] ❌ MESHCORE CONNECTION FAILED
[INFO] 🔍 Configuring Meshtastic callback (dual mode failed)...
[INFO] ✅ Meshtastic callback configured
```

**Status (after receiving messages):**
```
[INFO] 📦 Packets this session: 4
[INFO] ✅ Packets flowing normally
```

**Packet logs:**
```
[DEBUG][MT] 📦 TEXT_MESSAGE_APP de UserNode 12345
[INFO] 📨 Command detected: /help
```

## If Still No Packets

### Check 1: Interface Connected
```bash
journalctl -u meshtastic-bot -n 200 | grep "Meshtastic Serial"
```

Should see: `✅ Meshtastic Serial: /dev/ttyACM0`

### Check 2: Callback Configured
```bash
journalctl -u meshtastic-bot -n 200 | grep "callback"
```

Should see: `✅ Meshtastic callback configured`

### Check 3: Device Responding
```bash
python3 -m meshtastic --port /dev/ttyACM0 --info
```

Should show device info without hanging.

### Check 4: Serial Port Accessible
```bash
ls -la /dev/ttyACM* /dev/ttyUSB*
```

Should show devices with correct permissions.

## Related Issues

- **Serial freeze**: Fixed with timeout wrapper
- **MeshCore binary protocol**: Needs meshcore-cli library
- **SOURCE-DEBUG visibility**: Enhanced logging

## Summary

**Issue**: Bot received zero packets  
**Fix**: Configure callback at fallback points  
**Time to fix**: < 2 minutes (git pull + restart)  
**Status**: ✅ READY FOR DEPLOYMENT
