# FIXED: UnboundLocalError on Bot Startup

## Problem Resolved

Your bot was crashing on startup with:
```
UnboundLocalError: cannot access local variable 'pub' where it is not associated with a value
  File "/home/dietpi/bot/main_bot.py", line 2179, in start
    pub.subscribe(self.on_message, "meshtastic.receive")
```

## Root Cause

**Classic Python scoping bug:**

The code had `pub` imported twice:
1. ✅ At **module level** (line 18): `from pubsub import pub` 
2. ❌ **Inside start() function** (line 2209): `from pubsub import pub` (redundant!)

When Python sees the second import at line 2209, it treats `pub` as a **local variable** throughout the **entire function**, including BEFORE the import happens. This caused the error at line 2190 when trying to use `pub.subscribe()` before it was "defined" locally.

## The Fix

**Removed the redundant import at line 2209.**

Now `pub` is only imported once at the module level, and it's accessible everywhere it's needed.

```python
# BEFORE (BROKEN):
def start():
    pub.subscribe(...)  # Line 2190 - UnboundLocalError!
    # ... lots of code ...
    from pubsub import pub  # Line 2209 - Makes pub local!
    pub.getDefaultTopicMgr()

# AFTER (FIXED):
def start():
    pub.subscribe(...)  # Line 2190 - Works! Uses module-level pub
    # ... lots of code ...
    # Note: pub already imported at module level
    pub.getDefaultTopicMgr()  # Also works!
```

## What You'll See Now

After updating and restarting:

```
[INFO] ================================================================================
[INFO] 🔔 SUBSCRIPTION SETUP - CRITICAL FOR PACKET RECEPTION
[INFO] ================================================================================
[INFO]    meshtastic_enabled = True
[INFO]    meshcore_enabled = True
[INFO]    dual_mode = True
[INFO]    connection_mode = serial
[INFO]    interface type = MeshCoreCLIWrapper
[INFO] ================================================================================
[INFO] 📡 Subscribing to Meshtastic messages via pubsub...
[INFO] ✅ ✅ ✅ SUBSCRIBED TO meshtastic.receive ✅ ✅ ✅
[INFO]    Callback: <bound method MeshBot.on_message>
[INFO]    Topic: 'meshtastic.receive'
[INFO] ================================================================================
[INFO] 🧪 Testing pubsub mechanism...
[INFO]    Subscribers to 'meshtastic.receive': 1
[INFO]    ✅ Subscription verified - at least one listener registered
[INFO] ================================================================================
```

**No more crash!** Bot will start successfully and subscribe to messages.

## Deploy the Fix

```bash
cd /home/dietpi/bot
git checkout copilot/update-sqlite-data-cleanup
git pull origin copilot/update-sqlite-data-cleanup
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot -f
```

## Verification

After restart, you should see:
1. ✅ Startup banner appears
2. ✅ "✅ ✅ ✅ SUBSCRIBED TO meshtastic.receive ✅ ✅ ✅"
3. ✅ "Subscribers to 'meshtastic.receive': 1"
4. ✅ Bot keeps running (no crash)
5. ✅ When packets arrive: "🔔🔔🔔 on_message CALLED"

## Technical Details

This is a well-known Python behavior:

```python
# Example of the same issue:
x = "global"

def func():
    print(x)  # UnboundLocalError! 
    x = "local"  # Python sees this, makes x local throughout func
```

The solution is always: **Don't redefine/import a name locally if you need the module-level version.**

## Files Changed

- `main_bot.py` - Fixed (removed redundant import)
- `tests/test_pub_import_scoping.py` - Regression test (prevents recurrence)
- `demonstrate_unbound_local_fix.py` - Educational demo

## Status

🟢 **FIXED AND TESTED**

Your bot should now start normally and subscribe to pubsub correctly!

---

**If you still see issues after deploying, check:**
```bash
sudo systemctl status meshtastic-bot
journalctl -u meshtastic-bot --since "1 minute ago"
```
