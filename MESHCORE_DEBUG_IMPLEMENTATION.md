# MeshCore Debug Mode Support - Implementation Summary

## Problem

When `debug=False` in `meshcore-serial-monitor.py`, users experienced complete silence after the initial startup messages. There was:
- No way to tell if the monitor was still active
- No indication that messages were being waited for
- No visible activity to confirm the system was working
- No easy way to enable debug logging from the meshcore library

## Solution

Added comprehensive debug mode support with minimal changes:

### 1. Command-line Flag (`--debug`)

Added argparse-based command-line argument parsing:

```bash
# Without debug (default)
python meshcore-serial-monitor.py /dev/ttyACM0

# With debug enabled
python meshcore-serial-monitor.py /dev/ttyACM0 --debug

# Show help
python meshcore-serial-monitor.py --help
```

### 2. Debug Mode Indicator

Added clear indication of debug status at startup:

```
🔧 MeshCore Serial Monitor
   Port: /dev/ttyACM0
   Baudrate: 115200
   Debug mode: ENABLED   ← NEW
```

### 3. Heartbeat Messages

Added periodic heartbeat every 30 seconds to show the monitor is active:

```
[14:23:45] 💓 Monitor active | Messages received: 0
[14:24:15] 💓 Monitor active | Messages received: 2
```

### 4. Helpful Hints

When debug is disabled, the monitor now suggests enabling it:

```
✅ Monitor ready! Waiting for messages...
   Send a message to this device to test
   Press Ctrl+C to exit
   (Use --debug flag for verbose meshcore library output)   ← NEW
```

### 5. Pass Debug Flag to Library

The debug flag is now properly passed to `MeshCore.create_serial()`:

```python
self.meshcore = await self.MeshCore.create_serial(
    self.port,
    baudrate=self.baudrate,
    debug=self.debug  # ← Now dynamic based on --debug flag
)
```

When `debug=True`, the meshcore library itself will output verbose logging about:
- Serial port operations
- Connection management
- Message polling
- Event dispatching
- Internal state changes

### 6. Help Before Import

Refactored to parse arguments before importing meshcore, so `--help` works even without the library installed.

### 7. meshcore_cli_wrapper.py Support

Also updated `meshcore_cli_wrapper.py` to support debug mode:
- Added `debug` parameter to `__init__`
- Falls back to `DEBUG_MODE` from `config.py` if available
- Passes debug flag to `MeshCore.create_serial()`

## Files Modified

1. **meshcore-serial-monitor.py**
   - Added argparse for `--debug` flag
   - Added `_heartbeat_loop()` async method
   - Added debug mode indicator in startup
   - Added helpful hint about --debug flag
   - Refactored to defer meshcore import for help support
   - Pass debug flag to MeshCore library

2. **meshcore_cli_wrapper.py**
   - Added `debug` parameter to `__init__`
   - Auto-detect `DEBUG_MODE` from config.py
   - Pass debug flag to `MeshCore.create_serial()`

## Files Created

1. **test_meshcore_debug.py** - Comprehensive test suite
2. **demo_meshcore_debug.py** - Visual demonstration of improvements

## Testing

All changes tested with:
```bash
# Run test suite
python3 test_meshcore_debug.py

# Show demonstration
python3 demo_meshcore_debug.py

# Verify syntax
python3 -m py_compile meshcore-serial-monitor.py
python3 -m py_compile meshcore_cli_wrapper.py

# Test help output
python3 meshcore-serial-monitor.py --help
```

## Behavior Comparison

### Before (debug=False, hardcoded)
```
✅ Monitor ready! Waiting for messages...
   Send a message to this device to test
   Press Ctrl+C to exit
============================================================

[... complete silence ...]
```

User has no idea if:
- Monitor is still running
- Messages are expected
- System is working correctly

### After (debug=False, with improvements)
```
✅ Monitor ready! Waiting for messages...
   Send a message to this device to test
   Press Ctrl+C to exit
   (Use --debug flag for verbose meshcore library output)
============================================================

[14:23:45] 💓 Monitor active | Messages received: 0
[14:24:15] 💓 Monitor active | Messages received: 0
[14:24:45] 💓 Monitor active | Messages received: 1
```

User can see:
- Monitor is active (heartbeat)
- Message count updates
- How to enable debug mode

### After (debug=True, with --debug flag)
```
DEBUG:meshcore:Opening serial port /dev/ttyACM0
DEBUG:meshcore:Serial port opened successfully
...
✅ Monitor ready! Waiting for messages...
============================================================

[14:23:45] 💓 Monitor active | Messages received: 0
DEBUG:meshcore:Polling for messages...
DEBUG:meshcore:No new messages
[14:24:15] 💓 Monitor active | Messages received: 0
DEBUG:meshcore:Polling for messages...
```

User can see:
- All internal meshcore library activity
- Heartbeat messages
- Full debugging information

## Benefits

1. ✅ **User Feedback**: Heartbeat shows monitor is active
2. ✅ **Troubleshooting**: Easy to enable debug mode with --debug
3. ✅ **Discoverability**: Help hint suggests debug flag
4. ✅ **Flexibility**: Works with or without meshcore installed (--help)
5. ✅ **Integration**: meshcore_cli_wrapper respects DEBUG_MODE config
6. ✅ **Minimal Changes**: No breaking changes to existing functionality
7. ✅ **Backward Compatible**: Default behavior unchanged (debug=False)

## Usage Examples

```bash
# Basic usage - default port, no debug
python meshcore-serial-monitor.py

# Custom port, no debug
python meshcore-serial-monitor.py /dev/ttyUSB0

# Enable debug mode
python meshcore-serial-monitor.py --debug

# Custom port with debug
python meshcore-serial-monitor.py /dev/ttyUSB0 --debug

# Show help
python meshcore-serial-monitor.py --help
```

## Configuration (for main bot)

When using with the main bot via `meshcore_cli_wrapper.py`, set in `config.py`:

```python
DEBUG_MODE = True  # Enable debug logging
```

Or pass explicitly when creating the wrapper:

```python
wrapper = MeshCoreCLIWrapper(port="/dev/ttyUSB0", debug=True)
```

## Future Improvements

Possible enhancements for future consideration:
- Configurable heartbeat interval (currently 30s)
- Statistics display (uptime, packet rate, etc.)
- Color-coded output for different log levels
- Optional log file output
- Connection health monitoring

## Conclusion

This implementation solves the "nothing in debug=False" problem by:
1. Making debug mode easily toggleable via command-line
2. Adding periodic heartbeat to show activity
3. Providing helpful hints for troubleshooting
4. Enabling verbose internal logging when needed

Users now have full visibility into the monitor's operation, with or without debug mode enabled.
