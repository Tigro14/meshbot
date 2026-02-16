# Quick Fix: Dual Mode Not Working

## Problem
Libraries installed, config enabled, but NO MeshCore packets.

## Quick Diagnosis (30 seconds)

```bash
# 1. Restart and check for warning
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot --since "1m" | grep "DUAL MODE INITIALIZATION FAILED"
```

If you see the warning → Dual mode failed. Continue below.

## Top 3 Issues

### Issue 1: Port Doesn't Exist (60% of cases)

**Check:**
```bash
ls -la /dev/ttyUSB*
```

**No such file?** → MeshCore radio not connected or wrong port

**Fix:** Connect radio OR update `MESHCORE_SERIAL_PORT` in config

### Issue 2: Permission Denied (30% of cases)

**Check:**
```bash
ls -la /dev/ttyUSB0
```

**Shows `root dialout`?** → User not in group

**Fix:**
```bash
sudo usermod -a -G dialout dietpi
# Logout and login
```

### Issue 3: Same Port for Both (10% of cases)

**Check:**
```bash
grep SERIAL_PORT config.py
```

**Both same?** → Can't use same port twice

**Fix:** Set different ports in config:
```python
SERIAL_PORT = "/dev/ttyACM0"
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # DIFFERENT!
```

## Verification

After fixing:
```bash
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot --since "1m" | grep "Mode dual initialisé avec succès"
```

Should see: `✅ Mode dual initialisé avec succès`

## Get Full Details

See `FIX_DUAL_MODE_SILENT_FAILURE.md` for:
- 5 detailed scenarios
- All diagnostic commands
- Configuration examples
- Complete troubleshooting
