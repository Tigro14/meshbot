# Diagnostic Guide: Empty Debug Logs Issue

## Your Issue

You reported: "My debug log is nearly empty, despite active traffic"

Evidence from your logs:
- ✅ Bot running (periodic updates every 5 min)
- ✅ Packets received (count: 3879 → 3889 → 3901)
- ❌ NO individual packet debug logs

## What Was Fixed

Added **enhanced diagnostic logging** to identify exactly where packet processing stops.

## What to Look For After Deploying

### Expected Log Messages (every packet)

When packets are received, you should now see:

```
# 1. Entry point
INFO:traffic_monitor:🔵 add_packet ENTRY (logger) | source=local | from=0x12345678
[INFO] 🔵 add_packet ENTRY (print) | source=local | from=0x12345678

# 2. After append
INFO:traffic_monitor:✅ Paquet ajouté à all_packets: TEXT_MESSAGE_APP de NodeName (total: 3890)

# 3. Before database save
INFO:traffic_monitor:💿 [ROUTE-SAVE] (logger) source=local, type=TEXT_MESSAGE_APP, from=NodeName
[INFO][MT] 💿 [ROUTE-SAVE] (print) Routage paquet: source=local, type=TEXT_MESSAGE_APP

# 4. Debug logging (if DEBUG_MODE=True)
[DEBUG][MT] 📊 Paquet enregistré (print) ([local]): TEXT_MESSAGE_APP de NodeName
[DEBUG][MT] 📦 TEXT_MESSAGE_APP de NodeName ad3dc [direct] (SNR:12.0dB)
```

### Diagnostic Scenarios

#### Scenario 1: All Messages Appear ✅
**Meaning:** Logging works! You were running old code without these lines.
**Solution:** Update production to this version.

#### Scenario 2: Only logger.* Messages Appear
**Example:** You see `INFO:traffic_monitor:` but NOT `[INFO]` or `[INFO][MT]`
**Meaning:** Python logging works, but info_print/debug_print doesn't.
**Cause:** stdout/stderr not captured by systemd, or print() failing.
**Solution:** Check systemd service configuration.

#### Scenario 3: Only [INFO] Messages Appear  
**Example:** You see `[INFO]` but NOT `INFO:traffic_monitor:`
**Meaning:** print() works, but Python logging doesn't.
**Cause:** Logger not configured or suppressed.
**Solution:** Check logging configuration.

#### Scenario 4: Messages Stop at Specific Point
**Example:** You see entry point but nothing after
**Meaning:** Exception or early return between that point and next log.
**Solution:** Check for exception messages in logs.

#### Scenario 5: Exception Messages Appear
**Example:** You see `❌ Exception in add_packet:`
**Meaning:** Code is throwing exceptions.
**Solution:** Check exception details and fix the issue.

#### Scenario 6: Still NO Messages
**Meaning:** add_packet is NOT being called at all.
**Cause:** Message routing broken, or interface not publishing.
**Solution:** Check on_message() is being called.

## How to Deploy

1. **Pull latest code:**
   ```bash
   cd /home/dietpi/bot
   git fetch origin
   git checkout copilot/update-sqlite-data-cleanup
   git pull origin copilot/update-sqlite-data-cleanup
   ```

2. **Restart bot:**
   ```bash
   sudo systemctl restart meshtastic-bot
   ```

3. **Watch logs:**
   ```bash
   journalctl -u meshtastic-bot -f
   ```

4. **Wait for packets** (should arrive within minutes)

5. **Report results:** Which diagnostic messages appear?

## Interpreting Results

### If You See All Diagnostics:

Great! The issue was that you were running old code. The logging now works.

### If You See Some But Not Others:

This tells us exactly where the problem is:
- Entry point only → Exception in try block
- Entry + append → Exception in database save
- No [INFO][MT] → info_print_mt broken
- No logger.* → Python logging broken

### If You See Nothing:

The issue is earlier in the chain:
- Check if on_message() is being called
- Check if interface is connected
- Check if packets are actually received by hardware

## Additional Diagnostics

### Check systemd logs level:
```bash
journalctl -u meshtastic-bot -p debug -f
```

### Check for errors:
```bash
journalctl -u meshtastic-bot --since "5 minutes ago" | grep -E "ERROR|Exception|❌"
```

### Check packet reception:
```bash
# Should show increasing count
journalctl -u meshtastic-bot --since "5 minutes ago" | grep "paquets anciens expirés"
```

## What This Fixes

**Before:**
- Packets received but not logged
- No visibility into packet processing
- Can't tell if logging broken or code broken

**After:**
- Multiple diagnostic points
- Dual logging methods (redundancy)
- Clear indication of where processing stops
- Exception visibility

## Next Steps

After you deploy and report results, we can:
1. Identify exact failure point
2. Fix the root cause
3. Remove excess diagnostic logging
4. Restore normal operation

---

**Questions?** Report back with:
- Which diagnostic messages you see
- Which you don't see
- Any error messages
- Approximate time when you tested

This will help us pinpoint the exact issue!
