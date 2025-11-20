# Bot Restart Fix - Verification Checklist

## Pre-Deployment Checklist

Before deploying this fix to production, verify:

- [x] All changes compile without syntax errors
- [x] All tests pass (6/6 tests passing)
- [x] Code review completed with no critical issues
- [x] Security scan completed (0 vulnerabilities)
- [x] Documentation created and comprehensive

## Deployment Steps

### 1. Backup Current Configuration

```bash
# Backup the current service file
sudo cp /etc/systemd/system/meshtastic-bot.service /etc/systemd/system/meshtastic-bot.service.backup

# Backup current code
cd /home/dietpi/bot
git stash  # If you have local changes
git branch backup-before-fix  # Create backup branch
```

### 2. Deploy Changes

```bash
# Pull latest changes
cd /home/dietpi/bot
git checkout main
git pull origin main

# Verify files were updated
git log --oneline -5
# Should show recent commits:
# - Fix: Add missing return statement and signal handlers
# - Improve: Add exception handling in main loop
# - Add: Tests for bot lifecycle fixes
# - Add: Comprehensive documentation
```

### 3. Update Systemd Service

```bash
# Copy new service file
sudo cp meshbot.service /etc/systemd/system/meshtastic-bot.service

# Verify the file was copied correctly
sudo cat /etc/systemd/system/meshtastic-bot.service | grep "Restart="
# Should show: Restart=on-failure

# Reload systemd
sudo systemctl daemon-reload

# Check service status
sudo systemctl status meshtastic-bot
```

### 4. Restart Service

```bash
# Stop the service first (to verify clean shutdown)
sudo systemctl stop meshtastic-bot

# Wait a few seconds
sleep 3

# Check it's actually stopped
sudo systemctl is-active meshtastic-bot
# Should show: inactive

# Start the service
sudo systemctl start meshtastic-bot

# Check it started successfully
sudo systemctl is-active meshtastic-bot
# Should show: active
```

### 5. Monitor Logs

```bash
# Watch logs in real-time
sudo journalctl -u meshtastic-bot -f

# Look for these success messages:
# ✅ Gestionnaires de signaux installés (SIGTERM, SIGINT)
# ✅ Bot Meshtastic-Llama avec architecture modulaire
# ✅ Interface TCP/Serial créée
# ✅ Bot en service - type /help
```

## Post-Deployment Verification

### Immediate Verification (First 5 Minutes)

- [ ] Service started successfully
- [ ] No error messages in logs
- [ ] Signal handlers installed message appears
- [ ] Bot is responding to commands

```bash
# Check if bot is running
sudo systemctl is-active meshtastic-bot
# Should show: active

# Check for errors
sudo journalctl -u meshtastic-bot --since "5 minutes ago" | grep ERROR
# Should show no critical errors

# Send a test command via mesh
# /help or /sys command should respond
```

### Short-term Verification (First Hour)

- [ ] Bot has been running continuously for 1 hour
- [ ] No unexpected restarts
- [ ] No error messages in logs
- [ ] Commands still working

```bash
# Check uptime
sudo systemctl status meshtastic-bot | grep Active
# Should show: Active: active (running) since [recent time]

# Check for restarts
sudo journalctl -u meshtastic-bot --since "1 hour ago" | grep "Started meshtastic-bot"
# Should only show ONE start message (the one from deployment)

# Count restarts
sudo journalctl -u meshtastic-bot --since "1 hour ago" | grep -c "Started meshtastic-bot"
# Should show: 1
```

### Long-term Verification (First 24 Hours)

- [ ] Bot has been running for 24 hours without restart
- [ ] No unexpected restarts
- [ ] No error accumulation
- [ ] Normal operation confirmed

```bash
# Check uptime after 24 hours
sudo systemctl status meshtastic-bot | grep Active
# Active time should show ~24 hours

# Count restarts in 24h
sudo journalctl -u meshtastic-bot --since "24 hours ago" | grep -c "Started meshtastic-bot"
# Should show: 1 (only the initial start)

# Check for any restart patterns
sudo journalctl -u meshtastic-bot --since "24 hours ago" | grep "Stopping\|Started"
# Should only show the initial start, no stops/restarts
```

## Verification Commands

### Check Service Status

```bash
# Full status
sudo systemctl status meshtastic-bot

# Is it active?
sudo systemctl is-active meshtastic-bot

# How long has it been running?
sudo systemctl status meshtastic-bot | grep "Active:"

# What's the restart count?
sudo systemctl show meshtastic-bot -p NRestarts
# Should stay at 0 or very low
```

### Check Logs

```bash
# Last 100 lines
sudo journalctl -u meshtastic-bot -n 100

# Follow logs live
sudo journalctl -u meshtastic-bot -f

# Since last boot
sudo journalctl -u meshtastic-bot -b

# Only errors
sudo journalctl -u meshtastic-bot -p err

# Count restarts today
sudo journalctl -u meshtastic-bot --since today | grep -c "Started meshtastic-bot"
```

### Test Clean Shutdown

```bash
# Stop the service
sudo systemctl stop meshtastic-bot

# Check the logs for clean shutdown message
sudo journalctl -u meshtastic-bot -n 20 | grep "Sortie de la boucle principale"
# Should show: 🛑 Sortie de la boucle principale (arrêt intentionnel)

# Verify it didn't restart
sleep 15
sudo systemctl is-active meshtastic-bot
# Should show: inactive

# Start it again
sudo systemctl start meshtastic-bot
```

### Test Signal Handler

```bash
# Send SIGTERM to the process
sudo systemctl kill -s TERM meshtastic-bot

# Check logs for signal handling
sudo journalctl -u meshtastic-bot -n 20 | grep "Signal"
# Should show: 🛑 Signal SIGTERM reçu - arrêt propre du bot...

# Verify clean shutdown
sudo journalctl -u meshtastic-bot -n 20 | grep "Sortie de la boucle principale"
# Should show: 🛑 Sortie de la boucle principale (arrêt intentionnel)
```

## Success Criteria

### ✅ Fix is Successful If:

1. **No Unexpected Restarts**
   - Bot runs continuously for 24+ hours
   - Restart count stays at 0 or only increases on intentional restarts
   - No "Stopping" messages followed by "Started" in logs

2. **Clean Shutdown Works**
   - `systemctl stop` shows "arrêt intentionnel" message
   - Service stops without restarting
   - Exit code is 0

3. **Signal Handlers Work**
   - "Gestionnaires de signaux installés" appears on startup
   - SIGTERM is caught and handled gracefully
   - Bot doesn't crash when receiving signals

4. **Error Resilience**
   - Bot continues running even if cleanup_cache() fails
   - Errors are logged but don't crash the bot
   - Service doesn't enter restart loop

5. **Normal Operation**
   - Commands still work (/help, /sys, /bot, etc.)
   - Messages are received and processed
   - No degradation in functionality

## Failure Scenarios

### ❌ If Bot Still Restarting:

1. **Check if using old service file**
   ```bash
   sudo cat /etc/systemd/system/meshtastic-bot.service | grep Restart
   # Must show: Restart=on-failure (not Restart=always)
   ```

2. **Check if code was updated**
   ```bash
   cd /home/dietpi/bot
   grep -n "return True" main_bot.py | grep "Sortie de la boucle principale"
   # Should show the line with return True after loop exit
   ```

3. **Check for actual errors**
   ```bash
   sudo journalctl -u meshtastic-bot -p err --since "1 hour ago"
   # Look for real errors that might cause restarts
   ```

### ❌ If Bot Won't Start:

1. **Check for syntax errors**
   ```bash
   cd /home/dietpi/bot
   python3 -m py_compile main_bot.py main_script.py
   ```

2. **Check dependencies**
   ```bash
   python3 -c "import meshtastic, signal, sys"
   ```

3. **Check service file**
   ```bash
   sudo systemctl cat meshtastic-bot
   # Verify paths and configuration
   ```

## Rollback Procedure

If the fix causes issues:

```bash
# Stop the service
sudo systemctl stop meshtastic-bot

# Restore backup service file
sudo cp /etc/systemd/system/meshtastic-bot.service.backup /etc/systemd/system/meshtastic-bot.service
sudo systemctl daemon-reload

# Restore backup code
cd /home/dietpi/bot
git checkout backup-before-fix

# Start the service
sudo systemctl start meshtastic-bot

# Monitor
sudo journalctl -u meshtastic-bot -f
```

## Contact

If you encounter any issues:

1. **Capture logs**
   ```bash
   sudo journalctl -u meshtastic-bot --since "1 hour ago" > /tmp/bot-logs.txt
   ```

2. **Check service status**
   ```bash
   sudo systemctl status meshtastic-bot > /tmp/bot-status.txt
   ```

3. **Report issue with:**
   - Log file (`/tmp/bot-logs.txt`)
   - Status file (`/tmp/bot-status.txt`)
   - Description of what you observed
   - Steps you took before the issue

## Summary

This fix addresses the root cause of frequent restarts by:
- Adding proper return statements (exit code 0)
- Installing signal handlers (clean shutdown)
- Adding exception handling (error resilience)
- Changing restart policy (only on failures)

Follow this checklist to ensure successful deployment and verification.
