# Debugging /keys Command Issue

## Problem Report
User @Tigro14 reported: "still no response to telegram command /keys a76f40d"

## Investigation Summary

### What Was Already Fixed
The original issue was that `_check_node_keys()` only tried one key format when looking up nodes in `interface.nodes`. This was fixed in commit 2b9faeb by implementing multi-format search:

```python
# Now tries all 4 possible formats:
search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
```

### What I Added (commit e3b8fdd)
Since the user still reports no response, I added comprehensive debug logging to the Telegram `/keys` command handler to help diagnose where the issue occurs:

**Debug logging now shows:**
1. When `get_keys_info()` starts and which node_name is requested
2. Whether `message_handler.router` exists
3. Whether `router.network_handler` exists  
4. When `_check_node_keys()` is called
5. Response length
6. When response is sent to Telegram

### Expected Debug Output
When user runs `/keys a76f40d`, the logs should show:

```
📱 Telegram /keys a76f40d: username
🔍 DEBUG /keys: Starting get_keys_info() for node_name=a76f40d
✅ DEBUG /keys: network_handler found
🔍 DEBUG /keys: Calling _check_node_keys('a76f40d', compact=False)
DEBUG /keys a76f40d: Trying keys [2809086170, '2809086170']... for node_id=2809086170
DEBUG /keys a76f40d: FOUND with key=2809086170 (type=str)
✅ DEBUG /keys: Got response (len=123)
📤 DEBUG /keys: Sending response (len=123)
✅ DEBUG /keys: Response sent successfully
```

### Possible Failure Points
If any of these messages are missing, it indicates where the failure occurs:

1. **No logs at all** → Command not being registered/triggered
2. **Stops at "Starting get_keys_info()"** → Exception in router access
3. **Stops at network_handler check** → Router or network_handler not available
4. **Stops at method call** → Exception in _check_node_keys()
5. **Gets response but doesn't send** → Exception in Telegram API

### Next Steps for User
1. **Restart the bot** to load the new debug logging
2. **Run `/keys a76f40d` via Telegram**
3. **Check the bot logs** for the debug messages
4. **Report which debug message is the last one seen**

This will pinpoint exactly where the failure occurs.

## Test Results
All unit tests pass with the fix:
- ✅ `test_keys_command.py` 
- ✅ `test_keys_multiformat.py`
- ✅ `test_keys_string_fix.py`
- ✅ `test_keys_decimal_fix.py`
- ✅ `test_keys_telegram_flow.py` (simulation)

The logic is correct. The debug logging will help identify if there's a deployment or runtime issue.
