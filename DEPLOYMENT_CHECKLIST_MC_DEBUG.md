# MeshCore DEBUG Logging - Deployment Checklist

## Pre-Deployment

- [x] Code changes implemented
- [x] Tests created and passing
- [x] Documentation written
- [x] Code review requested (via PR)
- [ ] Code review approved
- [ ] Merge to main branch

## Deployment Steps

### 1. Stop the Bot
```bash
sudo systemctl stop meshbot
```

### 2. Backup Current Code
```bash
cd /home/user/meshbot
git stash  # Save any local changes
git branch backup-$(date +%Y%m%d)  # Create backup branch
```

### 3. Pull New Code
```bash
git fetch origin
git checkout main
git pull origin main
```

### 4. Verify Changes
```bash
# Check that MC DEBUG logging is present
grep -r "MC DEBUG" main_bot.py traffic_monitor.py dual_interface_manager.py meshcore_serial_interface.py

# Should see multiple matches
```

### 5. Test Configuration
```bash
# Verify MESHCORE_ENABLED and DUAL_NETWORK_MODE are set
grep "MESHCORE_ENABLED\|DUAL_NETWORK_MODE" config.py
```

### 6. Run Test Suite
```bash
python3 test_mc_debug_logging.py

# Expected: ✅ ALL TESTS PASSED
```

### 7. Start the Bot
```bash
sudo systemctl start meshbot
```

### 8. Check Bot Status
```bash
sudo systemctl status meshbot

# Expected: active (running)
```

## Post-Deployment Verification

### Immediate Checks (First 5 Minutes)

- [ ] Bot is running: `sudo systemctl status meshbot`
- [ ] No startup errors: `journalctl -u meshbot -n 50`
- [ ] Meshtastic connection OK: Look for "✅ Device connecté" or similar
- [ ] MeshCore connection OK (if dual mode): Look for "[MESHCORE]" logs

### MeshCore Packet Verification (First 30 Minutes)

- [ ] Watch for MC DEBUG logs:
```bash
journalctl -u meshbot -f | grep "\[MC\]"
```

Expected when MeshCore packet arrives:
```
[INFO][MC] 🔗 MC DEBUG: CALLING message_callback FROM meshcore_serial_interface
[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN on_meshcore_message()
[INFO][MC] 🔗🔗🔗 MC DEBUG: MESHCORE PACKET RECEIVED IN on_message()
[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN add_packet()
```

### DM Processing Verification (First Hour)

- [ ] Send a DM to bot via MeshCore: `/help`
- [ ] Verify all 5 stages log:
```bash
# Stage 1-4: As above
# Stage 5: Command processing
[INFO][MC] 📨 MC DEBUG: TEXT_MESSAGE_APP FROM MESHCORE
[INFO][MC] 🎯 MC DEBUG: CALLING process_text_message() FOR MESHCORE
[INFO][MC] ✅ MC DEBUG: process_text_message() returned
```
- [ ] Verify bot responds to DM

### Diagnostic Verification (If Issues)

Use the 5-stage diagnostic:

**Stage 1: Serial reception**
```bash
journalctl -u meshbot -f | grep "CALLING message_callback FROM meshcore"
```
- [ ] Present → Serial OK, check Stage 2
- [ ] Absent → Serial/radio issue, troubleshoot hardware

**Stage 2: Network forwarding**
```bash
journalctl -u meshbot -f | grep "MESHCORE PACKET IN on_meshcore_message"
```
- [ ] Present → Callback OK, check Stage 3
- [ ] Absent → Callback not registered, check dual_interface_manager

**Stage 3: Main entry**
```bash
journalctl -u meshbot -f | grep "MESHCORE PACKET RECEIVED IN on_message"
```
- [ ] Present → Main callback OK, check Stage 4
- [ ] Absent → Callback chain broken, check configuration

**Stage 4: Packet processing**
```bash
journalctl -u meshbot -f | grep "MESHCORE PACKET IN add_packet"
```
- [ ] Present → Traffic monitor OK, check Stage 5
- [ ] Absent → Packet validation issue, check packet structure

**Stage 5: Command routing**
```bash
journalctl -u meshbot -f | grep "CALLING process_text_message.*FOR MESHCORE"
```
- [ ] Present → Routing OK, check command handler
- [ ] Absent → Message routing issue, check message_router.py

## Success Criteria

### Must Have (Critical)
- [ ] Bot starts without errors
- [ ] Existing Meshtastic functionality still works
- [ ] MC DEBUG logs appear when MeshCore packets arrive
- [ ] Can trace packet flow through all 5 stages

### Should Have (Important)
- [ ] Bot responds to MeshCore DMs
- [ ] Commands execute correctly from MeshCore
- [ ] No performance degradation

### Nice to Have (Optional)
- [ ] Complete logs for debugging sessions
- [ ] Easy troubleshooting using diagnostic flow

## Rollback Plan

If critical issues occur:

### Quick Rollback
```bash
sudo systemctl stop meshbot
cd /home/user/meshbot
git checkout backup-$(date +%Y%m%d)  # Use today's backup branch
sudo systemctl start meshbot
```

### Full Rollback
```bash
sudo systemctl stop meshbot
cd /home/user/meshbot
git stash  # Save any changes
git checkout main
git reset --hard origin/main  # Reset to last known good state
sudo systemctl start meshbot
```

## Monitoring

### First 24 Hours

Monitor logs continuously:
```bash
journalctl -u meshbot -f
```

**Look for:**
- ✅ Regular packet flow (both Meshtastic and MeshCore)
- ✅ MC DEBUG logs when MeshCore packets arrive
- ✅ Successful command processing
- ❌ Any errors or exceptions
- ❌ Missing stages in packet flow

### First Week

Check daily:
```bash
# Overall bot health
sudo systemctl status meshbot

# Recent errors
journalctl -u meshbot --since "24 hours ago" | grep -i error

# MC DEBUG log count
journalctl -u meshbot --since "24 hours ago" | grep -c "\[MC\]"
```

## Support

### Documentation
- **MC_DEBUG_IMPLEMENTATION_SUMMARY.md** - Executive summary
- **MC_DEBUG_LOGGING_ENHANCEMENT.md** - Full implementation details
- **MC_DEBUG_LOGGING_QUICK_REF.md** - Quick diagnostic guide

### Test Suite
```bash
python3 test_mc_debug_logging.py
```

### Log Filters
```bash
# All MC logs
journalctl -u meshbot -f | grep "\[MC\]"

# Specific stage
journalctl -u meshbot -f | grep "MESHCORE PACKET IN add_packet"

# Error logs only
journalctl -u meshbot -f | grep -E "\[ERROR\]|\[MC\].*ERROR"
```

## Sign-Off

**Deployed by:** ___________________  
**Date:** ___________________  
**Time:** ___________________  

**Verification completed:** [ ] Yes [ ] No  
**Issues found:** [ ] Yes [ ] No  
**Rollback needed:** [ ] Yes [ ] No  

**Notes:**
```
_________________________________________________
_________________________________________________
_________________________________________________
```

---

**Status:** Ready for deployment  
**Risk Level:** Low (only logging added, no logic changes)  
**Estimated Downtime:** < 1 minute (restart only)
