# /propag Command Telegram Integration

## Summary

The `/propag` command (radio propagation report) has been successfully integrated into Telegram. Previously, the command only worked via CLI but was ignored by Telegram.

## Problem

- `/propag` command existed in mesh handlers but was not accessible via Telegram
- Command was not listed in `/start` menu
- No Telegram command handler was registered

## Solution

### Files Modified

1. **telegram_bot/commands/network_commands.py**
   - Added `propag_command()` async method
   - Implements proper argument parsing (hours, top_n)
   - Uses `compact=False` for detailed Telegram output
   - Includes authorization check
   - Executes in separate thread via `asyncio.to_thread()`

2. **telegram_integration.py**
   - Added `CommandHandler("propag", self.network_commands.propag_command)` registration

3. **telegram_bot/commands/basic_commands.py**
   - Added `/propag [h] [top] - Longues liaisons radio` to `/start` menu

## Features

### Command Usage

```
/propag          → Top 5 liaisons des dernières 24h
/propag 48       → Top 5 liaisons des dernières 48h
/propag 24 10    → Top 10 liaisons des dernières 24h
```

### Parameters

- `hours`: Time window (1-72 hours, default: 24)
- `top_n`: Number of top links to show (1-10, default: 5)
- `max_distance_km`: Fixed at 100km radius

### Output Format

- **Telegram**: Detailed format (`compact=False`)
- **Mesh/CLI**: Compact format (`compact=True`)

## Testing

All integration tests pass:

```bash
$ python test_propag_telegram_integration.py
✅ Méthode propag_command existe dans NetworkCommands
✅ Handler enregistré dans telegram_integration.py
✅ /propag dans la liste /start
✅ Documentation dans le texte d'aide
```

## Implementation Details

The command:
1. ✅ Validates user authorization
2. ✅ Parses optional arguments with validation
3. ✅ Calls `traffic_monitor.get_propagation_report()` with correct parameters
4. ✅ Returns detailed output suitable for Telegram
5. ✅ Handles errors gracefully
6. ✅ Logs requests for debugging

## Documentation

The command is documented in:
- `/start` command list
- `/help` text (handlers/command_handlers/utility_commands.py)
- Method docstrings

## Next Steps

The feature is ready to deploy. Users can now:
1. Send `/start` to see `/propag` in the command list
2. Use `/propag` to see the longest radio links
3. Customize results with time window and top-N parameters
