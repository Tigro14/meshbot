# Investigation: No Logs for /keys with Argument

## Critical Observation

User reports:
- ✅ `/keys` (no argument) works perfectly
- ❌ `/keys a76f40d` (with argument) shows **NO logs at all**

This includes NO logs from the entry-point logging at line 461:
```python
info_print(f"🚨 DEBUG /keys: Command handler CALLED! update={update is not None}, context={context is not None}")
```

## Why This Is Impossible

If the command handler is registered and working for `/keys`, it MUST also trigger for `/keys a76f40d`. The CommandHandler in python-telegram-bot matches the command regardless of arguments.

The only way this can happen is if:

## Hypothesis 1: Multiple Bot Instances

**Scenario**: Two bot processes are running
- Old bot (without logging) handles some commands
- New bot (with logging) handles other commands

**How to check**:
```bash
# Find all python processes related to meshbot
ps aux | grep python | grep -E 'main_script|meshbot|telegram'

# Check if meshbot service is running
systemctl status meshbot

# Check if there are multiple processes
pgrep -fa python | grep -E 'main_script|meshbot'
```

**Expected**: Should see only ONE bot process

**If multiple processes**: Stop and restart:
```bash
# Stop service
systemctl stop meshbot

# Find and kill any remaining processes (replace PID with actual process ID)
ps aux | grep main_script.py
kill <PID>

# Verify none running
ps aux | grep python | grep mesh

# Start fresh
systemctl start meshbot
```

## Hypothesis 2: Command Parsing Crash

**Scenario**: Bot crashes when parsing arguments, before reaching handler

**How to check**:
Look for crash logs immediately after trying `/keys a76f40d`:
```bash
# Check system logs
journalctl -u meshbot -n 50 --no-pager

# Look for:
# - Python tracebacks
# - "Restarting service"
# - segfault errors
```

**If bot crashes**: Shows traceback before reaching our handler

## Hypothesis 3: Different Bot Token

**Scenario**: `/keys` and `/keys a76f40d` going to different bots

**How to check**:
- Both commands should respond from same bot account
- Check bot username in Telegram responses
- Verify `TELEGRAM_BOT_TOKEN` in config.py

## Hypothesis 4: Command Interception

**Scenario**: Another handler registered that catches `/keys` with arguments

**How to check**:
Test other commands WITH arguments:
```
/nodes 2
/stats top 24
/weather Paris
/trace tigro
```

**If those work**: Something specific to `/keys` is intercepting
**If those also fail**: Global issue with argument handling

## Diagnostic Commands

Run these in Telegram and report results:

1. **Test basic commands**:
   ```
   /help
   /status
   ```

2. **Test commands with arguments**:
   ```
   /nodes 2
   /stats top 24
   ```

3. **Test /keys variations**:
   ```
   /keys
   /keys tigro
   /keys F547F
   /keys a76f40da
   ```

4. **Check bot logs after EACH command**:
   ```bash
   tail -f /var/log/syslog | grep -E '🚨|📱|🔍'
   ```

## Expected Behavior

**Working correctly**:
```
# Logs after /keys
🚨 DEBUG /keys: Command handler CALLED!
🚨 DEBUG /keys: User ID=123456, Username=user
🚨 DEBUG /keys: Authorization OK
📱 Telegram /keys: user
🔍 DEBUG /keys: Starting get_keys_info() for node_name=None

# Logs after /keys a76f40d
🚨 DEBUG /keys: Command handler CALLED!
🚨 DEBUG /keys: User ID=123456, Username=user
🚨 DEBUG /keys: Authorization OK
📱 Telegram /keys a76f40d: user
🔍 DEBUG /keys: Starting get_keys_info() for node_name=a76f40d
```

## What to Report

1. **Process check**: How many bot processes are running?
2. **Other commands**: Do other commands with arguments work?
3. **Crash logs**: Any tracebacks or crashes in logs?
4. **Startup logs**: Do you see both these logs at startup?
   ```
   🔍 DEBUG: Enregistrement du handler /keys...
   ✅ DEBUG: Handler /keys enregistré
   ```

This information will definitively identify why the command isn't reaching our handler.
