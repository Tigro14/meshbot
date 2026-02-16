# Fix: NameError - 'logger' is not defined

## Problem

Bot crashed when processing messages with:

```
Feb 04 20:17:43 DietPi meshtastic-bot[25478]: Traceback (most recent call last):
Feb 04 20:17:43 DietPi meshtastic-bot[25478]:   File "/home/dietpi/bot/main_bot.py", line 461, in on_message
Feb 04 20:17:43 DietPi meshtastic-bot[25478]:     logger.info(f"🔔🔔🔔 on_message CALLED (logger) {network_tag} | from=0x{from_id:08x if from_id else 0:08x}")
Feb 04 20:17:43 DietPi meshtastic-bot[25478]:     ^^^^^^
Feb 04 20:17:43 DietPi meshtastic-bot[25478]: NameError: name 'logger' is not defined
```

## Root Cause

Lines 461 and 464 in `main_bot.py` attempted to use `logger.info()`, but:
- ❌ `logger` was never imported
- ❌ `logger` was never defined  
- ❌ No `import logging` statement existed

The code tried to use Python's standard logging module without importing it.

## Solution

Replaced `logger.info()` calls with `info_print()` which:
1. ✅ Is already imported from `utils.py`
2. ✅ Is used consistently throughout the codebase
3. ✅ Provides equivalent functionality

### Changes Made

**main_bot.py lines 461-465:**

```python
# BEFORE (BROKEN):
logger.info(f"🔔🔔🔔 on_message CALLED (logger) {network_tag} | from=0x{from_id:08x if from_id else 0:08x}")
info_print(f"🔔🔔🔔 on_message CALLED (print) {network_tag} | from=0x{from_id:08x if from_id else 0:08x} | interface={type(interface).__name__ if interface else 'None'}")

# Exception handler:
logger.info(f"🔔🔔🔔 on_message CALLED (logger) | packet={packet is not None} | interface={interface is not None}")
info_print(f"🔔🔔🔔 on_message CALLED (print) | packet={packet is not None} | interface={interface is not None}")

# AFTER (FIXED):
info_print(f"🔔🔔🔔 on_message CALLED (info1) {network_tag} | from=0x{from_id:08x if from_id else 0:08x}")
info_print(f"🔔🔔🔔 on_message CALLED (info2) {network_tag} | from=0x{from_id:08x if from_id else 0:08x} | interface={type(interface).__name__ if interface else 'None'}")

# Exception handler:
info_print(f"🔔🔔🔔 on_message CALLED (info1-fallback) | packet={packet is not None} | interface={interface is not None}")
info_print(f"🔔🔔🔔 on_message CALLED (info2-fallback) | packet={packet is not None} | interface={interface is not None}")
```

## About utils.py Logging Functions

The codebase uses custom logging functions from `utils.py`:

- **`info_print(message)`** - Always prints (equivalent to logger.info)
- **`debug_print(message)`** - Prints only when DEBUG_MODE=True
- **`error_print(message)`** - Prints errors with timestamp and traceback

These are simpler than Python's logging module and used consistently throughout the project.

## Testing

### Syntax Validation
```bash
python3 -m py_compile main_bot.py
✅ Syntax check passed
```

### Regression Test
Created `test_logger_undefined.py` to prevent this issue from recurring:

```bash
python3 test_logger_undefined.py
```

Output:
```
🔍 Checking for undefined 'logger' usage in main_bot.py...
✅ No uses of 'logger' found
✅ No 'logger' usage - using info_print() from utils instead
======================================================================
✅ Test PASSED: No undefined 'logger' usage
======================================================================
```

## Expected Behavior

**Before:** Bot crashed when receiving messages
```
NameError: name 'logger' is not defined
```

**After:** Bot processes messages normally and logs them
```
[INFO] 🔔🔔🔔 on_message CALLED (info1) [] | from=0x12345678
[INFO] 🔔🔔🔔 on_message CALLED (info2) [] | from=0x12345678 | interface=SerialInterface
```

## Verification

After deploying:
```bash
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot -f | grep "on_message CALLED"
```

Should see:
- ✅ `[INFO] 🔔🔔🔔 on_message CALLED (info1) ...`
- ✅ `[INFO] 🔔🔔🔔 on_message CALLED (info2) ...`
- ❌ NO `NameError: name 'logger' is not defined`

## Files Changed

1. **main_bot.py** - Fixed lines 461-465 (replaced logger.info with info_print)
2. **test_logger_undefined.py** - New regression test

---

**Status:** ✅ Fixed, tested, documented
