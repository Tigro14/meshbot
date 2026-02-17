# I/O Health Monitor - Manual Testing Guide

## Overview

This document describes how to manually test the I/O health monitoring and SysRq watchdog functionality on your Raspberry Pi.

## Prerequisites

- Raspberry Pi 5 with NVMe storage
- Root access (sudo)
- Bot installed and configured
- rebootpi-watcher.py running as systemd service

## Architecture

```
┌─────────────────────────────────────────────────┐
│  main_bot.py (Periodic Update Thread)           │
│  ├─ Every 5 minutes (NODE_UPDATE_INTERVAL)      │
│  ├─ Save SQLite statistics                      │
│  ├─ Cleanup old data (VACUUM)                   │
│  └─ I/O Health Check (NEW)                      │
│     ├─ Test filesystem write                    │
│     ├─ Check SQLite integrity                   │
│     └─ Track consecutive failures                │
└──────────────────┬──────────────────────────────┘
                   │ If 3 consecutive failures
                   │ (IO_HEALTH_CHECK_FAILURE_THRESHOLD)
                   ▼
         ┌─────────────────────┐
         │  RebootSemaphore     │
         │  /dev/shm/*.lock     │
         └──────────┬───────────┘
                    │ Detected every 5 seconds
                    ▼
         ┌─────────────────────┐
         │ rebootpi-watcher.py  │
         │ ├─ Detect trigger    │
         │ ├─ Read reason       │
         │ └─ Execute reboot    │
         │    └─ IOHealthWatchdog: SysRq REISUB
         │       └─ User: systemctl reboot
         └─────────────────────┘
```

## Configuration

Edit your `/home/user/meshbot/config.py` and ensure these settings are present:

```python
# I/O Health Monitoring
IO_HEALTH_CHECK_ENABLED = True
IO_HEALTH_CHECK_FAILURE_THRESHOLD = 3  # 3 consecutive failures
IO_HEALTH_CHECK_COOLDOWN = 900  # 15 minutes between checks
```

## Test Scenarios

### Test 1: Normal Operation (Health Checks Pass)

**Purpose**: Verify health checks run without triggering reboot

**Steps**:
1. Start the bot with debug mode:
   ```bash
   cd /home/user/meshbot
   python3 main_script.py --debug
   ```

2. Watch the logs for health check messages (every 5 minutes):
   ```
   [DEBUG] 🔍 Vérification santé I/O...
   [DEBUG] ✅ Health check passed: Filesystem write
   [DEBUG] ✅ Health check passed: Database integrity
   [DEBUG] ✅ DB writable check passed: journal_mode=wal, pages=1234
   [DEBUG] ✅ Health check passed: Database writable
   [DEBUG] ✅ I/O Health: All health checks passed
   ```

3. Verify no reboot signals:
   ```bash
   ls -la /dev/shm/meshbot_reboot.*
   # Should show "No such file or directory" if no reboot pending
   ```

**Expected Result**: Health checks pass every 5 minutes, no reboot triggered


### Test 2: Simulated I/O Failure (Read-Only Filesystem)

**⚠️ WARNING**: This test will remount your filesystem as read-only and trigger a reboot!

**Purpose**: Verify watchdog detects I/O failures and triggers safe reboot

**Steps**:

1. Create a backup of important data first!

2. Start the bot in debug mode

3. Wait for one successful health check cycle (5+ minutes)

4. Simulate read-only filesystem (in another terminal):
   ```bash
   # This will make the root filesystem read-only
   sudo mount -o remount,ro /
   ```

5. Wait for next health check cycle (up to 5 minutes)

6. Watch the logs for failure detection:
   ```
   [ERROR] ❌ Health check failed: Filesystem write - Filesystem write error: [Errno 30] Read-only file system
   [ERROR] ⚠️ I/O Health: Health check failed (1/3): Filesystem write: Filesystem write error
   ```

7. After 3 consecutive failures (~15 minutes), you should see:
   ```
   [ERROR] 🚨 WATCHDOG TRIGGER: I/O health check failed 3 consecutive times. Storage may be unreliable. Triggering safe reboot via SysRq.
   [ERROR] ✅ Reboot signalé au watchdog (rebootpi-watcher)
   ```

8. The watcher log (`/var/log/bot-reboot.log`) should show:
   ```
   [2024-XX-XX XX:XX:XX] Signal de redémarrage détecté via sémaphore (/dev/shm)
   [2024-XX-XX XX:XX:XX] ⚠️ REBOOT DÉCLENCHÉ PAR WATCHDOG I/O
   [2024-XX-XX XX:XX:XX]    Utilisation de la séquence SysRq REISUB pour reboot sûr
   [2024-XX-XX XX:XX:XX] ═══════════════════════════════════════
   [2024-XX-XX XX:XX:XX] 🔴 EXÉCUTION SÉQUENCE SYSRQ REISUB
   [2024-XX-XX XX:XX:XX] 1. Activation SysRq...
   [2024-XX-XX XX:XX:XX] 2. SysRq-R: unRaw (reprendre contrôle)
   [2024-XX-XX XX:XX:XX] 3. SysRq-E: tErminate (SIGTERM)
   [2024-XX-XX XX:XX:XX] 4. SysRq-I: kIll (SIGKILL)
   [2024-XX-XX XX:XX:XX] 5. SysRq-S: Sync (synchronisation FS)
   [2024-XX-XX XX:XX:XX] 6. SysRq-U: Unmount (remontage RO)
   [2024-XX-XX XX:XX:XX] 7. SysRq-B: reBoot (REDÉMARRAGE)
   ```

9. System should reboot safely

**Expected Result**: 
- Health checks detect I/O failure within 1 cycle
- After 3 consecutive failures, reboot is triggered
- SysRq REISUB sequence executes
- System reboots cleanly without filesystem corruption


### Test 3: Manual Reboot (Non-Watchdog)

**Purpose**: Verify user-initiated reboots still use standard systemctl

**Steps**:

1. Send reboot command via Meshtastic:
   ```
   /rebootpi <password>
   ```

2. Check watcher log:
   ```bash
   tail -f /var/log/bot-reboot.log
   ```

3. Should see standard reboot (not SysRq):
   ```
   [2024-XX-XX XX:XX:XX] Signal de redémarrage détecté via sémaphore (/dev/shm)
   [2024-XX-XX XX:XX:XX] Informations de redémarrage:
   [2024-XX-XX XX:XX:XX]   Demandé par: YourName
   [2024-XX-XX XX:XX:XX]   Node ID: 0xXXXXXXXX
   [2024-XX-XX XX:XX:XX] Exécution du redémarrage Pi...
   # Uses systemctl reboot first
   ```

**Expected Result**: User reboots go through standard systemctl, not SysRq


### Test 4: Threshold Not Reached

**Purpose**: Verify single failures don't trigger reboot

**Steps**:

1. Simulate temporary failure (1-2 failures)
2. Restore normal operation
3. Wait for next health check

**Expected Result**:
```
[INFO] ✅ I/O health restored after 2 failures
```

Failure counter resets on success, no reboot triggered


## Monitoring Commands

### Check Current Health Status

Query the I/O health monitor via bot command (if implemented):
```
/sys
```

Or check logs directly:
```bash
journalctl -u meshbot -f | grep "I/O Health"
```

### Check Reboot Semaphore Status

```bash
# Check if reboot is pending
ls -la /dev/shm/meshbot_reboot.*

# View reboot info (if pending)
cat /dev/shm/meshbot_reboot.info
```

### View Watcher Logs

```bash
# Real-time monitoring
tail -f /var/log/bot-reboot.log

# Recent entries
tail -50 /var/log/bot-reboot.log
```

### Check SysRq Capability

Verify SysRq is enabled on your system:
```bash
# Check current setting (should be > 0)
cat /proc/sys/kernel/sysrq

# Enable all SysRq functions (if disabled)
echo 1 | sudo tee /proc/sys/kernel/sysrq
```

### View Database Health

```bash
# Check database integrity manually
sqlite3 traffic_history.db "PRAGMA integrity_check;"
# Should return: ok

# Check database size
ls -lh traffic_history.db
```

## Troubleshooting

### Health Checks Not Running

**Symptom**: No health check messages in logs

**Possible Causes**:
1. `IO_HEALTH_CHECK_ENABLED = False` in config
2. Cooldown period active (wait 15 minutes)
3. Bot not running periodic update thread

**Solution**:
```bash
# Check config
grep IO_HEALTH_CHECK config.py

# Restart bot with debug
python3 main_script.py --debug
```

### Watcher Not Detecting Signal

**Symptom**: Reboot signal set but watcher doesn't execute

**Possible Causes**:
1. Watcher service not running
2. Watcher doesn't have root permissions

**Solution**:
```bash
# Check watcher status
sudo systemctl status rebootpi-watcher

# Restart watcher
sudo systemctl restart rebootpi-watcher

# Check watcher logs
sudo journalctl -u rebootpi-watcher -f
```

### SysRq Not Working

**Symptom**: SysRq commands don't trigger reboot

**Possible Causes**:
1. SysRq disabled in kernel
2. /proc/sysrq-trigger not accessible

**Solution**:
```bash
# Enable SysRq
echo 1 | sudo tee /proc/sys/kernel/sysrq

# Test SysRq manually (CAUTION: This will reboot!)
echo b | sudo tee /proc/sysrq-trigger
```

### False Positives

**Symptom**: Health checks fail but filesystem is actually working

**Possible Causes**:
1. Temporary network/database contention
2. Threshold too low

**Solution**:
```python
# Increase failure threshold in config.py
IO_HEALTH_CHECK_FAILURE_THRESHOLD = 5  # More lenient
```

## Performance Impact

The I/O health monitoring has minimal performance impact:

- **Frequency**: Once per NODE_UPDATE_INTERVAL (5 minutes)
- **Cooldown**: Additional 15-minute cooldown protection
- **Test Size**: <1KB filesystem write
- **Duration**: ~100ms total for all checks
- **Impact**: Negligible (0.03% duty cycle)

## Safety Features

1. **Threshold-based**: Requires 3 consecutive failures (not single)
2. **Cooldown**: 15-minute minimum between checks
3. **Graceful**: SysRq REISUB sequence ensures clean shutdown
4. **Logged**: All actions logged to /var/log/bot-reboot.log
5. **Tested**: 13 unit tests verify logic

## Disabling the Feature

If you want to disable I/O health monitoring:

```python
# In config.py
IO_HEALTH_CHECK_ENABLED = False
```

Then restart the bot:
```bash
sudo systemctl restart meshbot
```

## Next Steps

After validating the implementation:

1. Monitor logs for 24-48 hours in production
2. Adjust threshold if needed based on false positive rate
3. Document any storage failures detected
4. Verify reboot improves availability
