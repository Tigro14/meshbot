# MeshCore Packet Persistence Diagnostic Guide

## Problem

User reported: **"I run this PR for 1h, all I got was ... 0 paquets, 0 messages, 0 neighbors, 0 node_stats supprimés"**

This means NO packets are being saved to the database after 1 hour, despite the bot running and processing at least one DM.

## Diagnostic Logs Added

Comprehensive logging has been added at every stage of packet persistence to identify exactly where packets might be lost.

## Log Flow

### Expected Complete Flow (SUCCESS)

```
[INFO] 🔔 on_message CALLED | from=0x143bcd7f | interface=MeshCoreCLIWrapper
[INFO] �� add_packet ENTRY | source=meshcore | from=0x143bcd7f
[INFO] 💿 [ROUTE-SAVE] Routage paquet: source=meshcore, type=TEXT_MESSAGE_APP, from=Tigro T1000E
[INFO] 💾 [SAVE-MESHCORE] Tentative sauvegarde: TEXT_MESSAGE_APP de Tigro T1000E (0x143bcd7f)
[INFO] ✅ [SAVE-MESHCORE] Paquet sauvegardé avec succès dans meshcore_packets
[DEBUG] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de Tigro T1000E
[DEBUG] 📦 TEXT_MESSAGE_APP de Tigro T1000E [direct] (SNR:n/a)
[INFO] 🔍 About to call _log_comprehensive_packet_debug for source=meshcore
[INFO] 🔷 _log_comprehensive_packet_debug CALLED | type=TEXT_MESSAGE_APP
[DEBUG] ╔═══════════════════════════════════════
[DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
... (comprehensive debug output)
```

### Every 10 Packets Saved

```
[INFO] 📦 [SAVE-MESHCORE] Total: 10 paquets MeshCore sauvegardés dans SQLite
[INFO] 📦 [SAVE-MESHCORE] Total: 20 paquets MeshCore sauvegardés dans SQLite
[INFO] 📦 [SAVE-MESHCORE] Total: 30 paquets MeshCore sauvegardés dans SQLite
```

## Diagnostic Scenarios

### Scenario 1: No Logs at All

**Symptoms:**
```
(no ROUTE-SAVE or SAVE-MESHCORE logs)
```

**Diagnosis:** MeshCore is not receiving any traffic

**Possible Causes:**
- MeshCore companion mode doesn't receive broadcasts (only DMs)
- User only sent 1 DM for testing, then no other traffic
- MeshCore app not running or disconnected
- Phone app not paired with MeshCore

**Solutions:**
- Send more test messages via companion app
- Check if MeshCore CLI shows any received packets
- Verify companion app pairing
- Check if MeshCore sees any network activity

### Scenario 2: Route Log But No Save Attempt

**Symptoms:**
```
[INFO] 💿 [ROUTE-SAVE] Routage paquet: source=meshcore
(but no 💾 [SAVE-MESHCORE] Tentative sauvegarde)
```

**Diagnosis:** Exception before `save_meshcore_packet()` is called

**Possible Causes:**
- `self.persistence` is None
- Exception in routing logic

**Solutions:**
- Check for error messages before ROUTE-SAVE log
- Verify TrafficPersistence was initialized

### Scenario 3: Save Attempt But No Success

**Symptoms:**
```
[INFO] 💿 [ROUTE-SAVE] Routage paquet: source=meshcore
[INFO] 💾 [SAVE-MESHCORE] Tentative sauvegarde: TEXT_MESSAGE_APP
(but no ✅ success message)
```

**Diagnosis:** Exception during database INSERT

**Possible Causes:**
- SQLite connection lost
- Database file permissions
- Table doesn't exist (migration failed)
- Disk full

**Solutions:**
- Look for error messages after tentative sauvegarde
- Check database file: `ls -lh traffic_history.db`
- Check disk space: `df -h`
- Try manual database access: `sqlite3 traffic_history.db "SELECT COUNT(*) FROM meshcore_packets;"`

### Scenario 4: Connection Error

**Symptoms:**
```
[INFO] 💾 [SAVE-MESHCORE] Tentative sauvegarde...
[ERROR] ❌ [SAVE-MESHCORE] Connexion SQLite non initialisée
[ERROR] ❌ [SAVE-MESHCORE] Impossible d'initialiser la connexion SQLite
```

**Diagnosis:** Database connection issue

**Possible Causes:**
- Database file locked by another process
- File permissions
- Corrupted database file

**Solutions:**
```bash
# Check if database exists and is accessible
ls -lh /home/dietpi/bot/traffic_history.db

# Check permissions
chmod 644 /home/dietpi/bot/traffic_history.db

# Check if another process has it locked
lsof /home/dietpi/bot/traffic_history.db

# Try accessing manually
sqlite3 /home/dietpi/bot/traffic_history.db "SELECT COUNT(*) FROM meshcore_packets;"

# If corrupted, backup and recreate
mv traffic_history.db traffic_history.db.backup
# Restart bot (will create new database)
```

### Scenario 5: Success (Working Correctly)

**Symptoms:**
```
[INFO] 💿 [ROUTE-SAVE] Routage paquet: source=meshcore
[INFO] 💾 [SAVE-MESHCORE] Tentative sauvegarde: TEXT_MESSAGE_APP
[INFO] ✅ [SAVE-MESHCORE] Paquet sauvegardé avec succès
[INFO] 📦 [SAVE-MESHCORE] Total: 10 paquets sauvegardés
```

**Diagnosis:** Everything working correctly!

**Verification:**
```bash
# Check database has packets
sqlite3 /home/dietpi/bot/traffic_history.db "SELECT COUNT(*) FROM meshcore_packets;"

# View recent packets
sqlite3 /home/dietpi/bot/traffic_history.db "SELECT datetime(timestamp, 'unixepoch'), sender_name, packet_type FROM meshcore_packets ORDER BY timestamp DESC LIMIT 10;"
```

## User Testing Instructions

### Step 1: Pull Latest Changes

```bash
cd /home/dietpi/bot
git pull
sudo systemctl restart meshbot
```

### Step 2: Monitor Logs

```bash
# Real-time logs filtered for diagnostic markers
journalctl -u meshbot -f | grep -E "ROUTE-SAVE|SAVE-MESHCORE|🔔|🔵"
```

### Step 3: Send Test Message

Send a message via MeshCore companion app (or meshcore-cli).

### Step 4: Check Which Logs Appear

Based on which logs appear, identify the scenario above.

### Step 5: Verify Database

After sending a few messages:

```bash
# Count packets in database
sqlite3 /home/dietpi/bot/traffic_history.db "SELECT COUNT(*) FROM meshcore_packets;"

# Should show number > 0 if working

# View saved packets
sqlite3 /home/dietpi/bot/traffic_history.db "SELECT sender_name, packet_type, message FROM meshcore_packets ORDER BY timestamp DESC LIMIT 5;"
```

## Common Issues

### Issue 1: MeshCore Companion Mode Doesn't Receive Broadcasts

**Symptom:** Only DMs are received, no broadcast traffic

**Explanation:** In companion mode, the bot doesn't have its own radio. It relies on the phone app to forward messages. The phone app typically only forwards:
- DMs to/from the user
- Messages the user participates in

**Expected Behavior:** This is NORMAL for companion mode. The bot will only see:
- Direct messages to the user
- Messages sent by the user
- NOT general broadcast traffic from other nodes

**Solution:** This is not a bug. If you need to see ALL mesh traffic, use a dedicated Meshtastic node connected via serial or TCP, not companion mode.

### Issue 2: Only 1 Packet Ever Seen

**Symptom:** User sent 1 DM for testing, then no more packets for 1 hour

**Explanation:** If user only sent 1 test message and then didn't send any more, the database will have 1 packet. After 48 hours, cleanup will remove it.

**Verification:**
```bash
# Check if packet was saved
sqlite3 /home/dietpi/bot/traffic_history.db "SELECT * FROM meshcore_packets LIMIT 1;"

# If returns 1 row → packet WAS saved but was deleted by cleanup after 48h
# If returns nothing → packet was never saved
```

**Solution:** Send more test messages regularly to verify persistence is working.

## Summary

With these diagnostic logs, we can pinpoint EXACTLY where packets are lost:

1. **No logs** → MeshCore not receiving traffic (expected in companion mode)
2. **Route log only** → Exception before save
3. **Save attempt only** → Database connection/permission issue
4. **Success logs** → Everything working!

Report which scenario you see, and we can provide targeted solution.
