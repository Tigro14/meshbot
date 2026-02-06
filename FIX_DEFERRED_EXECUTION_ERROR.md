# FIX: "Unexpected error in deferred execution" Error

## Problem

User reported error on bot shutdown:
```
Feb 04 20:02:59 DietPi meshtastic-bot[24808]: ERROR:meshtastic.util:Unexpected error in deferred execution
```

## Root Cause

In `main_bot.py` `stop()` method, the `self.interface` was being set to `None` **without properly closing it first**:

```python
# BEFORE (BROKEN):
def stop(self):
    ...
    # 7. Nettoyage final
    try:
        self.interface = None  # ❌ Direct assignment without close()
        gc.collect()
    except Exception as e:
        error_print(f"⚠️ Erreur nettoyage final: {e}")
```

### Why This Caused the Error

The meshtastic library (both `serial_interface` and `tcp_interface`) maintains internal:
- Background threads for receiving data
- Callback handlers
- Pubsub message queues
- Deferred operations

When `self.interface` is set to `None` or garbage collected **without calling `close()`**, these internal components continue trying to execute but find the interface object is gone, causing:

```
ERROR:meshtastic.util:Unexpected error in deferred execution
```

## Solution

Added proper shutdown sequence:

```python
# AFTER (FIXED):
def stop(self):
    ...
    # 6. Fermer dual interface manager (si utilisé)
    try:
        if hasattr(self, 'dual_interface') and self.dual_interface:
            self.dual_interface.close()  # ✅ Close dual interface first
            self.dual_interface = None
            debug_print("✅ Dual interface fermée")
    except Exception as e:
        error_print(f"⚠️ Erreur fermeture dual_interface: {e}")

    # 7. Fermer l'interface principale (Meshtastic/MeshCore)
    try:
        if self.interface:
            # Close the interface properly to stop internal threads and callbacks
            if hasattr(self.interface, 'close'):
                self.interface.close()  # ✅ Call close() FIRST
                debug_print("✅ Interface principale fermée")
            self.interface = None  # ✅ Then set to None
    except Exception as e:
        error_print(f"⚠️ Erreur fermeture interface: {e}")
    ...
```

### What `interface.close()` Does

When you call `interface.close()` on a meshtastic interface, it:
1. Stops the receive thread
2. Closes the serial port or TCP socket
3. Cleans up pubsub subscriptions
4. Cancels pending operations
5. Ensures all callbacks complete

Only after these cleanup operations is it safe to set `self.interface = None`.

## Changes Made

**File:** `main_bot.py`
- Line 2622-2629: Added dual_interface closing
- Line 2631-2640: Added proper interface.close() before setting to None
- Renumbered comments (6→7→8→9 instead of 6→7)

**Test:** `test_interface_shutdown.py`
- Verifies interface.close() is called before interface = None
- Checks proper order of operations
- Ensures exception handling is present

## Testing

```bash
cd /home/runner/work/meshbot/meshbot
python3 test_interface_shutdown.py
```

Output:
```
✅ Found stop() method at line 2561
✅ Found interface.close() at line 2636
✅ Found interface = None at line 2638
✅ Correct order: close() at line 2636 before None at line 2638
✅ Found dual_interface.close() at line 2625
✅ Exception handling present in stop()
✅ interface.close() properly wrapped in try/except
```

## Expected Behavior After Fix

**Before:**
- Bot shutdown logs show: `ERROR:meshtastic.util:Unexpected error in deferred execution`
- Internal threads may not stop cleanly
- Potential resource leaks

**After:**
- Clean shutdown: `✅ Interface principale fermée`
- No deferred execution errors
- All internal threads stopped properly
- Clean resource cleanup

## User Action

```bash
cd /home/dietpi/bot
git checkout copilot/update-sqlite-data-cleanup
git pull
sudo systemctl restart meshtastic-bot
```

To verify the fix when shutting down:
```bash
sudo systemctl stop meshtastic-bot
journalctl -u meshtastic-bot --since "1 minute ago" | grep -i "error\|fermée"
```

Should see:
- `✅ Interface principale fermée` or `✅ Dual interface fermée`
- NO `ERROR:meshtastic.util:Unexpected error in deferred execution`

## Related Issues

This is a common pattern in Python when working with objects that have internal threads:
- Always call `close()` or `shutdown()` methods before destroying objects
- Don't rely on `__del__()` or garbage collection to clean up threads
- Use try/except around close() calls to handle errors gracefully

## Prevention

To prevent similar issues in the future:
1. Always call `close()` on objects with internal threads before setting to None
2. Wrap close operations in try/except for safety
3. Test shutdown sequences explicitly
4. Use linters that detect resource management issues
