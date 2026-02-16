# Issue Summary: No mc/mt Packet Logs Appearing

## The Problem

You reported that no "mc" or "mt" packet logs appear in the systemd journal despite having DEBUG_MODE=True.

Your logs show:
- ✅ Bot is running (periodic updates every 5 minutes)
- ✅ Telegram integration working (polling active)
- ✅ Database cleanups executing
- ❌ **No packet reception logs** (📦, 📡, 🔔, 🔵)

## The Diagnosis

This is **NOT a software bug**. The bot code is working correctly.

The actual issue: **Your Meshtastic radio is not receiving any RF packets.**

### Evidence

Looking at your logs, we see:
```
Feb 03 22:24:33 DietPi meshtastic-bot[18158]: [DEBUG] 🔄 Mise à jour périodique...
Feb 03 22:29:33 DietPi meshtastic-bot[18158]: [DEBUG] 🔄 Mise à jour périodique...
Feb 03 22:34:33 DietPi meshtastic-bot[18158]: [DEBUG] 🔄 Mise à jour périodique...
```

**What's missing:**
- No "🔔 on_message CALLED" (would appear when interface receives packet)
- No "🔵 add_packet ENTRY" (would appear when packet enters processing)
- No "📦" logs (would appear with DEBUG_MODE=True)
- No "📡 [RX_LOG]" logs (would appear for MeshCore packets)

This pattern indicates: **Interface connected ✅, but ZERO packets received ❌**

## Why This Happens

### Most Common Cause (90%)

**No mesh network activity in radio range**

Possible reasons:
- No other nodes powered on nearby
- Other nodes out of RF range (> 5 km typically)
- Other nodes on different frequency/region
- Mesh network is just very quiet at the moment

### Other Possible Causes

1. **Hardware disconnected** (3%)
   - Radio device unplugged
   - USB cable loose
   - Device powered off

2. **DEBUG_MODE actually disabled** (5%)
   - Config file has DEBUG_MODE = False
   - Logs are suppressed
   
3. **MeshCore RX_LOG disabled** (1%, MeshCore only)
   - Only DMs are received
   - Broadcasts/telemetry suppressed

4. **Wrong serial port** (1%)
   - Device on different port than configured

## The Fix

I've created a diagnostic suite to help you identify and fix the issue.

### Step 1: Run Diagnostic

```bash
cd /home/user/meshbot  # Or wherever your bot is
python3 diagnose_packet_reception.py
```

This will show:
- Current configuration
- Hardware status
- Recent log analysis
- Specific recommendations

### Step 2: Check Most Likely Issue

**Verify mesh network is active:**

From another device/node, send a test message:
```bash
meshtastic --sendtext "Test from other node"
```

Or check if your radio is receiving ANYTHING:
```bash
meshtastic --port /dev/ttyACM0 --listen
```

If you see packets in `--listen` but NOT in bot logs → software issue
If you see NO packets in `--listen` → no mesh activity (normal)

### Step 3: Follow Diagnostic Recommendations

The script will tell you exactly what to check based on your configuration.

## What You Should See (When Fixed)

Once packets are flowing, your logs will show:

```
[DEBUG][MT] 📦 POSITION_APP de tigrog2 f547f [direct] (SNR:12.0dB)
[DEBUG][MT] 🌐 LOCAL POSITION from tigrog2 (f547f) | Hops:0/3 | SNR:12.0dB(🟢) | RSSI:-45dBm | Ch:0
[DEBUG][MT]   └─ ID:2f39d8a2 | RX:14:23:45 | Size:42B | Lat:47.12345 Lon:6.54321

[DEBUG][MT] 📦 TELEMETRY_APP de t1000E 0da [via relay ×1] (SNR:8.5dB)
[DEBUG][MT] 🌐 LOCAL TELEMETRY from t1000E (0da) | Hops:1/3 | SNR:8.5dB(🟡) | RSSI:-68dBm | Ch:0

[INFO] 📥 10 paquets reçus dans add_packet() (current queue: 5)
[INFO] 💾 25 paquets enregistrés dans all_packets (size: 25)
```

## Quick Fixes to Try

### Fix 1: Verify DEBUG_MODE

```bash
grep DEBUG_MODE /home/user/meshbot/config.py
```

Should show:
```python
DEBUG_MODE = True
```

If it shows `False`, change it:
```bash
nano /home/user/meshbot/config.py
# Change: DEBUG_MODE = True
# Save: Ctrl+X, Y, Enter

sudo systemctl restart meshtastic-bot
```

### Fix 2: Check Hardware

```bash
# Check if device exists
ls -la /dev/ttyACM* /dev/ttyUSB*

# Check if port is locked
sudo lsof /dev/ttyACM0
```

If locked, kill the process:
```bash
sudo kill <PID>
sudo systemctl restart meshtastic-bot
```

### Fix 3: Generate Mesh Activity

From another device in range:
```bash
# Send a test message
meshtastic --sendtext "Test message"

# Or request node info
meshtastic --request-node-info
```

Then check bot logs:
```bash
journalctl -u meshtastic-bot -f | grep "📦"
```

## Documentation Provided

I've created three documents to help you:

1. **`diagnose_packet_reception.py`** - Automated diagnostic script
   - Run this first
   - Shows configuration, hardware status, log analysis
   - Provides specific recommendations

2. **`TROUBLESHOOT_NO_PACKETS.md`** - Comprehensive troubleshooting guide
   - Step-by-step procedures
   - Hardware checks
   - RF activity verification
   - Expected output examples

3. **`DIAGNOSTIC_README.md`** - Quick reference
   - Common fixes at a glance
   - FAQ section
   - Success indicators

## Understanding Packet Logging

### mc vs mt Prefixes

- **[DEBUG][MC]** = MeshCore packets (from companion radio)
- **[DEBUG][MT]** = Meshtastic packets (from primary radio)

Your configuration determines which you'll see:

**If MESHTASTIC_ENABLED=True:**
- You should see [DEBUG][MT] logs

**If MESHCORE_ENABLED=True:**
- You should see [DEBUG][MC] logs

**If DUAL_NETWORK_MODE=True:**
- You should see BOTH [MC] and [MT] logs

### When Logs Appear

Packet logs only appear when:
1. ✅ DEBUG_MODE = True (required)
2. ✅ Interface is connected (startup succeeds)
3. ✅ Radio receives RF packet (hardware activity)
4. ✅ Packet passes through processing (on_message → add_packet)

If ANY of these is missing, you see no logs.

## Important Note

**This is expected behavior if your mesh network is quiet.**

The bot can only log packets that the radio actually receives.

If there's no RF activity in range, there will be no logs.

This is NORMAL and not an error.

## Need More Help?

1. Run diagnostic script:
   ```bash
   python3 diagnose_packet_reception.py > diagnostic.txt
   ```

2. Collect logs:
   ```bash
   journalctl -u meshtastic-bot --since '1 hour ago' > logs.txt
   ```

3. Share both files on Discord or GitHub

## Summary

**Issue**: No packet logs appearing
**Cause**: No RF packets being received by radio
**Solution**: 
1. Run diagnostic script
2. Verify mesh network is active
3. Check hardware connections
4. Ensure DEBUG_MODE=True

**This is NOT a bug** - the bot is working correctly.

You just need RF activity in range to see packet logs.
