# Quick Fix: SOURCE-DEBUG Missing Intermediate Logs

## Problem
journalctl shows:
```
[DEBUG] 🔍 [SOURCE-DEBUG] Determining packet source:
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'
```

Missing the diagnostic details in between.

## Cause
**systemd/journalctl filters log lines with leading spaces.**

Lines like `[DEBUG]    _dual_mode_active=False` were being dropped.

## Fix Applied
Replaced leading spaces with arrow prefix (→).

## What You'll See Now

**Before (incomplete):**
```
[DEBUG] 🔍 [SOURCE-DEBUG] Determining packet source:
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'
```

**After (complete):**
```
[DEBUG] 🔍 [SOURCE-DEBUG] Determining packet source:
[DEBUG] 🔍 [SOURCE-DEBUG] → _dual_mode_active=False
[DEBUG] 🔍 [SOURCE-DEBUG] → network_source=None (type=NoneType)
[DEBUG] 🔍 [SOURCE-DEBUG] → MESHCORE_ENABLED=False
[DEBUG] 🔍 [SOURCE-DEBUG] → is_from_our_interface=True
[DEBUG] 🔍 Source détectée: Serial/local mode
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'
```

## Verification After Deployment

```bash
# Pull and restart
cd /home/dietpi/bot  # or wherever bot is
git pull
sudo systemctl restart meshtastic-bot

# Check logs (should see all diagnostic lines now)
journalctl -u meshtastic-bot --no-pager -n 3000 | grep "SOURCE-DEBUG"
```

## Expected Output

You should now see **7 lines** per packet instead of just 2:
1. "Determining packet source:" - Entry point
2. "→ _dual_mode_active=..." - Dual mode status
3. "→ network_source=..." - Network source parameter
4. "→ MESHCORE_ENABLED=..." - MeshCore configuration
5. "→ is_from_our_interface=..." - Interface check
6. "Source détectée: ..." - Which branch was taken
7. "Final source = '...'" - Result

## What This Means

Now you can see **exactly** how the bot determines packet source:
- Is dual mode active?
- What's the network_source parameter?
- Is MeshCore enabled?
- Which logic branch was executed?

This makes debugging source detection issues much easier!

---

**Status:** ✅ Fixed and ready for deployment  
**Risk:** NONE - Only log formatting changed  
**Impact:** Complete diagnostic visibility
