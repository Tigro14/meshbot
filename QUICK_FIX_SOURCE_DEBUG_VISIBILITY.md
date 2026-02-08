# Quick Fix: SOURCE-DEBUG Logs Not Appearing

## Problem
`journalctl -u meshbot -n 10000 | grep "SOURCE-DEBUG"` displays nothing after git pull and restart.

## Why This Happens

**SOURCE-DEBUG logs only appear when packets are received.**

If no packets arrive → no SOURCE-DEBUG logs.

## Solution: Check These NEW Logs

### 1. Startup Confirmation (Immediate)

```bash
journalctl -u meshbot -n 100 | grep "MESHBOT STARTUP"
```

**Expected:**
```
[INFO] 🚀 MESHBOT STARTUP - SOURCE-DEBUG DIAGNOSTICS ENABLED
[INFO] 📅 Startup time: 2026-02-08 19:15:30
[INFO] 📦 Git commit: e14708f
[INFO] 🔍 DEBUG_MODE: ENABLED ✅
[DEBUG] 🔍 [SOURCE-DEBUG] Diagnostic logging initialized
```

✅ **If you see this:** New code is deployed and running

❌ **If nothing:** Bot not running or git pull didn't work

### 2. Status Check (After 2 Minutes)

```bash
journalctl -u meshbot -f | grep "BOT STATUS"
```

**Wait 2 minutes, then you'll see:**

**If NO packets:**
```
[INFO] 📊 BOT STATUS - Uptime: 2m 15s
[INFO] 📦 Packets this session: 0
[INFO] ⚠️  WARNING: No packets received yet!
[INFO]    → SOURCE-DEBUG logs will only appear when packets arrive
[INFO]    → Check Meshtastic connection if packets expected
```

✅ **This explains why no SOURCE-DEBUG logs**

**If packets ARE arriving:**
```
[INFO] 📊 BOT STATUS - Uptime: 4m 30s
[INFO] 📦 Packets this session: 42
[INFO] ✅ Packets flowing normally (42 total)
```

✅ **SOURCE-DEBUG logs should appear**

Check with:
```bash
journalctl -u meshbot -n 1000 | grep "SOURCE-DEBUG"
```

## Troubleshooting

### No Startup Logs

Bot not running:
```bash
sudo systemctl status meshbot
sudo systemctl restart meshbot
```

Old code still there:
```bash
cd /home/dietpi/bot  # or wherever bot is
git log --oneline -5
git pull
sudo systemctl restart meshbot
```

### Status Shows "No packets received"

Check connection:
```bash
# Serial
ls -la /dev/ttyUSB* /dev/ttyACM*

# Config
grep -E "SERIAL_PORT|REMOTE_NODE" config.py

# Logs
journalctl -u meshbot -n 200 | grep -i "connect\|device"
```

### Packets Flowing but No SOURCE-DEBUG

Very rare, check DEBUG_MODE:
```bash
grep DEBUG_MODE config.py  # Should be True
```

## Summary

**Before:** SOURCE-DEBUG only if packets arrive (invisible otherwise)

**After:** 
1. ✅ Startup banner confirms code deployed
2. ✅ Status every 2 min shows if packets arriving
3. ✅ Clear warning when no packets
4. ✅ Can diagnose issue immediately

---

**Quick diagnostic sequence:**
```bash
# 1. Check startup
journalctl -u meshbot -n 100 | grep "MESHBOT STARTUP"

# 2. Wait 2 minutes, check status
journalctl -u meshbot -f | grep "BOT STATUS"

# 3. If packets=0, check connection
# 4. If packets>0, check SOURCE-DEBUG
journalctl -u meshbot -n 1000 | grep "SOURCE-DEBUG"
```
