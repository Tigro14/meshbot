# Quick Fix: NameError - 'logger' is not defined

## Problem
```
NameError: name 'logger' is not defined
```

## What Was Wrong
Code used `logger.info()` without importing `logger`.

## Fix Applied
Replaced `logger.info()` with `info_print()` (already imported from utils).

## Deploy
```bash
cd /home/dietpi/bot
git checkout copilot/update-sqlite-data-cleanup
git pull
sudo systemctl restart meshtastic-bot
```

## Verify
```bash
journalctl -u meshtastic-bot -f | grep "on_message CALLED"
```

Should see:
```
[INFO] 🔔🔔🔔 on_message CALLED (info1) [] | from=0x12345678
[INFO] 🔔🔔🔔 on_message CALLED (info2) [] | from=0x12345678 | interface=SerialInterface
```

Should NOT see:
```
NameError: name 'logger' is not defined
```

## Status
✅ Fixed in main_bot.py lines 461-465
✅ Tested with regression test
✅ Ready to deploy

---

See `FIX_LOGGER_UNDEFINED.md` for complete details.
