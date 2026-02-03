# Bot Restarting Issue - Fix Documentation

## Problem Summary

The Meshtastic bot was restarting every 5-46 minutes, as observed in the systemd logs:

```
Nov 20 19:26:50 DietPi systemd[1]: Stopping meshtastic-bot.service - Bot Meshtastic...
Nov 20 19:26:50 DietPi systemd[1]: Stopped meshtastic-bot.service - Bot Meshtastic.
Nov 20 19:26:50 DietPi systemd[1]: Started meshtastic-bot.service - Bot Meshtastic.
```

This pattern repeated every few minutes, causing:
- Interrupted service
- Lost connections
- Incomplete conversations
- Wasted resources

## Root Cause Analysis

### Issue 1: Missing Return Statement

**File**: `main_bot.py::start()`

The `start()` method was missing an explicit `return True` after the main loop:

```python
# BEFORE (incorrect)
def start(self):
    # ... initialization ...
    while self.running:
        time.sleep(30)
        # ... cleanup ...
    
    # Missing return statement - implicitly returns None!

# In main_script.py:
success = bot.start()  # Returns None
if not success:        # None is falsy, so this triggers
    return 1           # Exit with error code
```

**Impact**: Bot would exit with code 1 even on normal shutdown, causing systemd to restart it.

### Issue 2: No Signal Handlers

**File**: `main_bot.py`

The bot had no handlers for SIGTERM (systemd stop) or SIGINT (Ctrl+C):

```python
# BEFORE (incorrect)
# No signal handlers registered
# SIGTERM would cause immediate exit
```

**Impact**: When systemd sent SIGTERM, the bot would exit ungracefully, potentially leaving resources in inconsistent state.

### Issue 3: Aggressive Restart Policy

**File**: `meshbot.service`

The systemd service used `Restart=always`:

```ini
# BEFORE (incorrect)
Restart=always  # Restarts even on intentional stops!
```

**Impact**: 
- Bot would restart even when stopped intentionally
- No protection against restart loops
- Difficult to actually stop the service

### Issue 4: No Exception Handling in Main Loop

**File**: `main_bot.py::start()`

The main loop had no exception handling:

```python
# BEFORE (incorrect)
while self.running:
    time.sleep(30)
    cleanup_counter += 1
    if cleanup_counter % 10 == 0:
        self.cleanup_cache()  # Any error here crashes the bot!
```

**Impact**: A single error in `cleanup_cache()` would crash the entire bot.

## Solution Implemented

### Fix 1: Add Return Statement

```python
# AFTER (correct)
def start(self):
    # ... initialization ...
    while self.running:
        time.sleep(30)
        # ... cleanup ...
    
    # Explicit return statement
    info_print("🛑 Sortie de la boucle principale (arrêt intentionnel)")
    return True  # ✅ Now returns True on successful run
```

**Benefit**: Bot exits with code 0 on normal shutdown, systemd doesn't restart unnecessarily.

### Fix 2: Add Signal Handlers

```python
# AFTER (correct)
import signal

class MeshBot:
    def _signal_handler(self, signum, frame):
        """Handle SIGTERM and SIGINT gracefully"""
        signal_name = signal.Signals(signum).name
        info_print(f"🛑 Signal {signal_name} reçu - arrêt propre du bot...")
        self.running = False
    
    def start(self):
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        info_print("✅ Gestionnaires de signaux installés")
        # ... rest of start() ...
```

**Benefit**: 
- Clean shutdown on SIGTERM (systemd stop)
- Clean shutdown on SIGINT (Ctrl+C)
- Resources cleaned up properly

### Fix 3: Update Restart Policy

```ini
# AFTER (correct)
Restart=on-failure
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=300
```

**Benefit**:
- Only restarts on actual failures (non-zero exit code)
- Limits to 5 restarts in 5 minutes
- Prevents infinite restart loops
- Can be stopped normally with `systemctl stop`

### Fix 4: Add Exception Handling

```python
# AFTER (correct)
while self.running:
    try:
        time.sleep(30)
        cleanup_counter += 1
        if cleanup_counter % 10 == 0:
            self.cleanup_cache()
    except Exception as loop_error:
        error_print(f"⚠️ Erreur dans la boucle principale: {loop_error}")
        error_print(traceback.format_exc())
        time.sleep(5)  # Pause before continuing
```

**Benefit**:
- Errors in cleanup don't crash the bot
- Bot continues running despite transient issues
- Errors are logged for debugging

## Deployment Instructions

### 1. Update the Bot Code

```bash
cd /home/dietpi/bot
git pull origin main
```

### 2. Update Systemd Service

```bash
# Copy new service file
sudo cp meshbot.service /etc/systemd/system/meshtastic-bot.service

# Reload systemd configuration
sudo systemctl daemon-reload
```

### 3. Restart the Service

```bash
sudo systemctl restart meshtastic-bot
```

### 4. Verify the Fix

Monitor the logs to confirm no more unexpected restarts:

```bash
sudo journalctl -u meshtastic-bot -f
```

Look for:
- ✅ `✅ Gestionnaires de signaux installés (SIGTERM, SIGINT)` on startup
- ✅ No more unexpected "Stopping" messages
- ✅ `🛑 Sortie de la boucle principale (arrêt intentionnel)` on clean shutdown
- ✅ Bot stays running for hours without restart

## Testing

Run the comprehensive test suite:

```bash
cd /home/dietpi/bot
python3 test_bot_lifecycle.py
```

Expected output:
```
============================================================
Testing Bot Lifecycle Fixes
============================================================
test_main_loop_exception_handling ... ok
test_signal_handler_exists ... ok
test_signal_handlers_registered ... ok
test_signal_imports_present ... ok
test_start_returns_true_on_clean_exit ... ok
test_service_file_restart_policy ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.002s

OK
```

## Expected Behavior After Fix

### Normal Operation
- Bot starts successfully
- Runs continuously without unexpected restarts
- Logs show normal activity

### Intentional Stop
```bash
sudo systemctl stop meshtastic-bot
```
Logs will show:
```
INFO: 🛑 Signal SIGTERM reçu - arrêt propre du bot...
INFO: 🛑 Sortie de la boucle principale (arrêt intentionnel)
INFO: Bot arrêté
```
Exit code: 0 (success)
Result: Service stops and **does not restart**

### Error During Operation
If an error occurs in cleanup:
```
ERROR: ⚠️ Erreur dans la boucle principale: <error message>
```
Result: Bot **continues running**, error logged

### Critical Failure
If start() fails (e.g., llama.cpp not available):
```
ERROR: Erreur: <critical error>
```
Exit code: 1 (failure)
Result: Service **restarts** after 10 seconds (up to 5 times in 5 minutes)

## Troubleshooting

### Bot Still Restarting?

1. Check if it's an intentional restart:
   ```bash
   sudo journalctl -u meshtastic-bot | grep "Signal.*reçu"
   ```
   If you see signal messages, something external is stopping it.

2. Check for errors causing restarts:
   ```bash
   sudo journalctl -u meshtastic-bot | grep "ERROR"
   ```
   If you see errors, fix the underlying issue.

3. Verify service file was updated:
   ```bash
   sudo systemctl cat meshtastic-bot | grep "Restart="
   ```
   Should show `Restart=on-failure`, not `Restart=always`

### Service Won't Start?

1. Check syntax errors:
   ```bash
   cd /home/dietpi/bot
   python3 -m py_compile main_bot.py main_script.py
   ```

2. Check dependencies:
   ```bash
   python3 -c "import meshtastic, signal, sys"
   ```

3. Check service status:
   ```bash
   sudo systemctl status meshtastic-bot
   ```

### Need to Temporarily Disable Restarts?

```bash
sudo systemctl set-property meshtastic-bot Restart=no
sudo systemctl daemon-reload
```

To re-enable:
```bash
sudo systemctl set-property meshtastic-bot Restart=on-failure
sudo systemctl daemon-reload
```

## Technical Details

### Signal Flow

```
systemd sends SIGTERM
    ↓
_signal_handler() called
    ↓
self.running = False
    ↓
while self.running: exits
    ↓
return True (exit code 0)
    ↓
systemd sees success, doesn't restart
```

### Exit Code Mapping

| Scenario | Return Value | Exit Code | Systemd Action |
|----------|--------------|-----------|----------------|
| Normal shutdown | True | 0 | No restart |
| Critical error | False | 1 | Restart (if < 5 in 5min) |
| Signal received | True | 0 | No restart |
| Exception in start() | False | 1 | Restart (if < 5 in 5min) |

### Main Loop Lifecycle

```
start()
    ↓
Set self.running = True
    ↓
while self.running:
    ├── sleep(30)
    ├── cleanup (with exception handling)
    └── repeat
    ↓
Loop exits when self.running = False
    ↓
return True
    ↓
Exit with code 0
```

## Files Changed

1. `main_bot.py` - Core fixes
   - Added signal handlers
   - Added return statement
   - Added main loop exception handling

2. `meshbot.service` - Service configuration
   - Changed restart policy
   - Added restart limits

3. `test_bot_lifecycle.py` - Test suite (new file)
   - Tests for all fixes
   - Regression prevention

## Rollback Instructions

If you need to rollback for any reason:

```bash
cd /home/dietpi/bot
git log --oneline | head -5  # Find commit before fix
git checkout <commit-hash>
sudo systemctl restart meshtastic-bot
```

## Summary

This fix addresses the root causes of unexpected restarts:

✅ **Added return statement** - Bot exits with correct code
✅ **Added signal handlers** - Clean shutdown on SIGTERM/SIGINT  
✅ **Improved restart policy** - Only restart on failures
✅ **Added exception handling** - Resilient to transient errors

The bot should now run continuously without unexpected restarts, only restarting when there's an actual failure.
