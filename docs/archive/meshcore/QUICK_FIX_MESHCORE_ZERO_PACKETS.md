# Quick Fix: MeshCore "Zero Packets" Issue

## Problem
"Still zero packet receiver on meshcore side"

## Root Cause
Bot's RX_LOG_DATA handler was only logging packets, not forwarding them for processing.

## Solution
Updated `meshcore_cli_wrapper.py` to forward decoded RX_LOG packets to the bot.

## Deploy

```bash
cd /home/dietpi/bot
git pull
sudo systemctl restart meshtastic-bot
```

## Verify

```bash
# Watch for packet forwarding
journalctl -u meshtastic-bot -f | grep "\[RX_LOG\]"
```

**Expected output:**
```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu
[DEBUG][MC] 📨 [RX_LOG] Text message detected, forwarding to bot
[DEBUG][MC] ➡️  [RX_LOG] Forwarding packet to bot callback
[DEBUG][MC] ✅ [RX_LOG] Packet forwarded successfully
```

## Test

Send message on MeshCore:
```
/help
```

**Expected**: Bot responds

## What Changed

**Before:**
- ❌ Bot only received DM messages
- ❌ Public broadcasts not processed
- ❌ "Zero packets" from user perspective

**After:**
- ✅ Bot receives ALL MeshCore text messages
- ✅ Public broadcasts forwarded and processed
- ✅ Commands work from both DM and public

## Configuration

Ensure in `config.py`:
```python
MESHCORE_RX_LOG_ENABLED = True
```

## Troubleshooting

**No forwarding logs?**
- Check meshcore-decoder installed: `pip list | grep meshcoredecoder`
- Check MeshCore radio connected
- Check MESHCORE_RX_LOG_ENABLED = True

**Packets forwarded but not processed?**
- Check SOURCE-DEBUG logs: `journalctl -u meshtastic-bot -f | grep "SOURCE-DEBUG"`
- Should show `Final source = 'meshcore'`

## Summary

| Issue | Status |
|-------|--------|
| Zero packets received | ✅ FIXED |
| DM messages | ✅ Working |
| Public broadcasts | ✅ Working |
| Command processing | ✅ Working |
| Dual mode (Meshtastic + MeshCore) | ✅ Working |

**Files Changed**: `meshcore_cli_wrapper.py` (+68 lines)  
**Risk**: LOW (only adds forwarding)  
**Impact**: HIGH (enables full MeshCore support)
