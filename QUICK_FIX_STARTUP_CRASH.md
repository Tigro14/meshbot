# QUICK FIX: Bot Startup Crash

## Problem
Bot crashed with: `UnboundLocalError: cannot access local variable 'pub'`

## Cause
Redundant import inside function made Python treat `pub` as local variable.

## Fix Applied
✅ Removed redundant `from pubsub import pub` at line 2209
✅ Now uses module-level import from line 18

## Deploy
```bash
cd /home/dietpi/bot
git pull
sudo systemctl restart meshtastic-bot
```

## Verify
```bash
journalctl -u meshtastic-bot -f
```

You should see:
```
✅ ✅ ✅ SUBSCRIBED TO meshtastic.receive ✅ ✅ ✅
```

**No more crash!**

See `FIXED_UNBOUND_LOCAL_ERROR.md` for full details.
