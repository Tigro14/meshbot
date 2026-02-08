# Fix: SOURCE-DEBUG Logs Not Appearing

## Problem

After `git pull` and bot restart, command `journalctl -u meshbot -n 10000 | grep "SOURCE-DEBUG"` displays nothing.

## Root Cause

The SOURCE-DEBUG logging added in the previous commit has a critical limitation:

**SOURCE-DEBUG logs only appear WHEN PACKETS ARE RECEIVED.**

The logs are inside the `on_message()` method, which is only called when packets arrive. If no packets are coming in, no SOURCE-DEBUG logs will be generated.

This made it impossible to distinguish between:
1. Bot not running / old code deployed
2. Bot running correctly but not receiving packets
3. Logging mechanism broken

## Solution

Added **unconditional startup and periodic status logging** that appears even when no packets arrive.

### 1. Startup Diagnostic Banner

Added immediately on bot startup (main_bot.py `__init__` method):

```python
info_print("=" * 80)
info_print("🚀 MESHBOT STARTUP - SOURCE-DEBUG DIAGNOSTICS ENABLED")
info_print("=" * 80)
info_print(f"📅 Startup time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
info_print(f"📦 Git commit: {git_commit}")
info_print(f"🔍 DEBUG_MODE: {debug_mode_status}")
info_print("✅ SOURCE-DEBUG logging: ACTIVE (will log on packet reception)")
debug_print("🔍 [SOURCE-DEBUG] Diagnostic logging initialized")
debug_print("🔍 [SOURCE-DEBUG] Waiting for packets to trace source determination...")
info_print("=" * 80)
```

**Benefits:**
- Appears IMMEDIATELY on startup
- Confirms new code is deployed
- Shows git commit hash
- Confirms DEBUG_MODE status
- Logs appear even if zero packets arrive

### 2. Periodic Status Logging

Added every 2 minutes in main loop (main_bot.py main loop):

```python
# Every 2 minutes (4 x 30s)
info_print("=" * 80)
info_print(f"📊 BOT STATUS - Uptime: {uptime_str}")
info_print(f"📦 Packets this session: {self._packets_this_session}")
info_print(f"🔍 SOURCE-DEBUG: {'Active' if DEBUG_MODE else 'Inactive'}")

if self._packets_this_session == 0:
    info_print("⚠️  WARNING: No packets received yet!")
    info_print("   → SOURCE-DEBUG logs will only appear when packets arrive")
    info_print("   → Check Meshtastic connection if packets expected")
else:
    info_print(f"✅ Packets flowing normally ({self._packets_this_session} total)")

info_print("=" * 80)
```

**Benefits:**
- Shows bot is alive and running
- Shows packet reception status
- Warns if no packets (explains why no SOURCE-DEBUG logs)
- Confirms packets are flowing (so SOURCE-DEBUG should be logging)

## How to Verify After Deployment

### 1. Check Startup Logs (Immediate)

```bash
journalctl -u meshbot -n 100 | grep "MESHBOT STARTUP"
```

**Expected output:**
```
[INFO] ================================================================================
[INFO] 🚀 MESHBOT STARTUP - SOURCE-DEBUG DIAGNOSTICS ENABLED
[INFO] ================================================================================
[INFO] 📅 Startup time: 2026-02-08 19:15:30
[INFO] 📦 Git commit: abc1234
[INFO] 🔍 DEBUG_MODE: ENABLED ✅
[INFO] ✅ SOURCE-DEBUG logging: ACTIVE (will log on packet reception)
[INFO] ================================================================================
```

**If you see this:** New code is deployed ✅

### 2. Check Periodic Status (After 2 minutes)

```bash
journalctl -u meshbot -n 100 | grep "BOT STATUS"
```

**Expected output (no packets):**
```
[INFO] ================================================================================
[INFO] 📊 BOT STATUS - Uptime: 2m 15s
[INFO] 📦 Packets this session: 0
[INFO] 🔍 SOURCE-DEBUG: Active (logs on packet reception)
[INFO] ⚠️  WARNING: No packets received yet!
[INFO]    → SOURCE-DEBUG logs will only appear when packets arrive
[INFO]    → Check Meshtastic connection if packets expected
[INFO] ================================================================================
```

**If you see "No packets received":** This is why SOURCE-DEBUG logs don't appear. The bot is working, but no packets are arriving.

**Expected output (with packets):**
```
[INFO] ================================================================================
[INFO] 📊 BOT STATUS - Uptime: 4m 30s
[INFO] 📦 Packets this session: 42
[INFO] 🔍 SOURCE-DEBUG: Active (logs on packet reception)
[INFO] ✅ Packets flowing normally (42 total)
[INFO] ================================================================================
```

**If you see "Packets flowing normally":** SOURCE-DEBUG logs should be appearing. Check:
```bash
journalctl -u meshbot -n 1000 | grep "SOURCE-DEBUG"
```

### 3. Check SOURCE-DEBUG Logs (When Packets Arrive)

```bash
journalctl -u meshbot -f | grep "SOURCE-DEBUG"
```

**Expected when packets arrive:**
```
[DEBUG] 🔍 [SOURCE-DEBUG] Determining packet source:
[DEBUG]    _dual_mode_active=False
[DEBUG]    network_source=None
[DEBUG]    MESHCORE_ENABLED=False
[DEBUG]    is_from_our_interface=True
[DEBUG] 🔍 Source détectée: Serial/local mode
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'
```

## Troubleshooting

### Scenario 1: No Startup Logs

**Symptom:**
```bash
journalctl -u meshbot -n 100 | grep "MESHBOT STARTUP"
# No output
```

**Diagnosis:** Bot not running or old code still deployed

**Solution:**
```bash
sudo systemctl status meshbot  # Check if running
cd /home/dietpi/bot  # or wherever bot is
git log --oneline -5  # Check commits
git pull  # Get latest code
sudo systemctl restart meshbot
```

### Scenario 2: Startup Logs but No Status Logs

**Symptom:** Startup banner appears, but no "BOT STATUS" logs after 2 minutes

**Diagnosis:** Bot crashed or stuck in startup

**Solution:**
```bash
journalctl -u meshbot -n 200  # Check for errors
sudo systemctl restart meshbot
```

### Scenario 3: Status Shows "No packets received"

**Symptom:**
```
⚠️  WARNING: No packets received yet!
```

**Diagnosis:** Bot working correctly, but Meshtastic interface not receiving packets

**Root causes:**
- Serial device disconnected
- TCP connection down
- Radio off or no mesh activity
- Wrong SERIAL_PORT or TCP host/port

**Solution:**
```bash
# Check serial connection
ls -la /dev/ttyUSB* /dev/ttyACM*

# Check config
grep -E "SERIAL_PORT|REMOTE_NODE" config.py

# Check if device is connected
meshtastic --info  # If meshtastic CLI installed

# Check logs for connection errors
journalctl -u meshbot -n 200 | grep -E "Device|connect|interface"
```

### Scenario 4: Status Shows Packets but No SOURCE-DEBUG

**Symptom:**
```
📦 Packets this session: 42
✅ Packets flowing normally (42 total)
```

But no SOURCE-DEBUG logs when grepping.

**Diagnosis:** Very rare - possible logging issue

**Solution:**
```bash
# Check DEBUG_MODE
grep DEBUG_MODE config.py

# Check if debug_print is working
journalctl -u meshbot -n 200 | grep "\[DEBUG\]"

# If no [DEBUG] logs at all, DEBUG_MODE might be False
```

## Testing

Run the test suite to verify logging works:

```bash
cd /home/runner/work/meshbot/meshbot
python3 test_startup_diagnostics.py
```

Expected: All tests pass ✅

## Files Modified

1. **main_bot.py** - `__init__` method (+37 lines)
   - Added startup diagnostic banner
   - Git commit logging
   - DEBUG_MODE status logging
   - SOURCE-DEBUG availability confirmation

2. **main_bot.py** - main loop (+22 lines)
   - Added periodic status logging every 2 minutes
   - Packet reception counter
   - Warning when no packets received
   - Confirmation when packets flowing

3. **test_startup_diagnostics.py** - New test file
   - Tests all log types
   - Verifies visibility

## Summary

**Before:** SOURCE-DEBUG logs only appear when packets arrive (invisible if no packets)

**After:** 
- Startup logs appear immediately (confirms code deployed)
- Status logs every 2 minutes (shows if packets arriving)
- Clear warnings when no packets (explains why no SOURCE-DEBUG)

**User can now:**
1. Confirm new code is deployed (startup banner)
2. Confirm bot is running (status every 2 min)
3. See if packets are arriving (packet counter)
4. Understand why SOURCE-DEBUG logs missing (no packets warning)
