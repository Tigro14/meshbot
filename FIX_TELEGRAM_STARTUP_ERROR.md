# Fix: Telegram Bot Startup Error - start_polling() Timeout Parameters

## Problem Statement

The Telegram bot was failing to start with the following error:

```
TypeError: Updater.start_polling() got an unexpected keyword argument 'read_timeout'
```

The error occurred in `telegram_integration.py` at line 199:

```python
await self.application.updater.start_polling(
    poll_interval=5.0,
    timeout=30,
    read_timeout=180,        # ❌ Not supported in v20.0+
    write_timeout=180,       # ❌ Not supported in v20.0+
    connect_timeout=180,     # ❌ Not supported in v20.0+
    pool_timeout=180,        # ❌ Not supported in v20.0+
    allowed_updates=Update.ALL_TYPES,
    drop_pending_updates=True
)
```

## Root Cause

Starting with python-telegram-bot version **20.0**, the API for configuring timeouts changed:

- **Old way (v13.x and earlier)**: Pass timeout parameters directly to `start_polling()`
- **New way (v20.0+)**: Configure timeouts at the `Application.builder()` level

The parameters `read_timeout`, `write_timeout`, `connect_timeout`, and `pool_timeout` were removed from `start_polling()` and must now be set when building the Application object.

## Solution

### Changes Made to `telegram_integration.py`

1. **Configure timeouts at Application builder level** (lines 185-194):

```python
# Before:
self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# After:
self.application = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .read_timeout(180)
    .write_timeout(180)
    .connect_timeout(180)
    .pool_timeout(180)
    .build()
)
```

2. **Remove invalid parameters from start_polling()** (lines 210-215):

```python
# Before:
await self.application.updater.start_polling(
    poll_interval=5.0,
    timeout=30,
    read_timeout=180,        # ❌ Removed
    write_timeout=180,       # ❌ Removed
    connect_timeout=180,     # ❌ Removed
    pool_timeout=180,        # ❌ Removed
    allowed_updates=Update.ALL_TYPES,
    drop_pending_updates=True
)

# After:
await self.application.updater.start_polling(
    poll_interval=5.0,
    timeout=30,
    allowed_updates=Update.ALL_TYPES,
    drop_pending_updates=True
)
```

3. **Added explanatory comments** to help future developers understand the API change.

## Valid Parameters for start_polling()

According to python-telegram-bot v21.0+ documentation, `start_polling()` accepts:

- `poll_interval` (float, optional): Time between polling requests (default: 0.0)
- `timeout` (int | timedelta, optional): Long poll timeout (default: 10 seconds)
- `bootstrap_retries` (int, optional): Retry count for bootstrap phase (default: -1 = infinite)
- `allowed_updates` (Sequence[str], optional): List of update types to receive
- `drop_pending_updates` (bool, optional): Whether to drop pending updates on startup
- `error_callback` (Optional[Callable], optional): Async callback for polling errors

## Timeout Configuration Values

The timeout values remain the same as before:

- `read_timeout`: 180 seconds - Maximum time to wait for server response
- `write_timeout`: 180 seconds - Maximum time to wait for write operations
- `connect_timeout`: 180 seconds - Maximum time to establish connection
- `pool_timeout`: 180 seconds - Maximum time to get connection from pool

These values are appropriate for the bot's use case with potentially slow networks and large message processing.

## Testing

A test script `test_telegram_fix.py` was created to verify:

1. ✅ `Application.builder()` accepts all timeout configuration methods
2. ✅ `start_polling()` doesn't expect the deprecated timeout parameters

## Files Changed

1. **telegram_integration.py**: Fixed Application builder and start_polling call
2. **test_telegram_fix.py**: Added test script to verify the fix (new file)

## Impact

- ✅ **Zero functional changes**: The bot behaves exactly the same way
- ✅ **Maintains same timeout values**: 180 seconds for all timeout operations
- ✅ **Compatible with python-telegram-bot v21.0+**: Uses the correct modern API
- ✅ **Well-documented**: Comments explain the API change for future maintainers

## Migration Notes

This fix is necessary for anyone using python-telegram-bot version 20.0 or later. The error message is clear and the fix is straightforward:

1. Move all timeout parameters from `start_polling()` to `Application.builder()`
2. Use builder method chaining: `.read_timeout()`, `.write_timeout()`, etc.
3. Remove timeout parameters from `start_polling()` call

## References

- [python-telegram-bot v21.5 Updater documentation](https://docs.python-telegram-bot.org/en/v21.5/telegram.ext.updater.html)
- [python-telegram-bot v22.6 ApplicationBuilder documentation](https://docs.python-telegram-bot.org/en/stable/telegram.ext.applicationbuilder.html)
- [Migration guide to v20.0](https://docs.python-telegram-bot.org/en/stable/changelog.html)

## Verification

To verify the fix works in production:

1. Ensure python-telegram-bot>=21.0 is installed
2. Start the bot
3. Check for successful initialization: "Bot Telegram en écoute (polling optimisé)..."
4. Verify no `TypeError` about `read_timeout` parameter

The bot should now start without errors and maintain the same robust timeout configuration as before.
