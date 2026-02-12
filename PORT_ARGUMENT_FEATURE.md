# Port Argument Feature - Complete Guide

## Overview

Both diagnostic scripts now support configurable USB ports via command-line arguments.

## The Issue

**Before:**
- Scripts had hardcoded `/dev/ttyACM2`
- User's device changed to `/dev/ttyACM1`
- Required code modification to change port

**After:**
- Port is command-line argument
- Default to `/dev/ttyACM2` for backward compatibility
- Easy to use any USB port

## Usage

### Basic Usage

```bash
# Use default port (/dev/ttyACM2)
python3 listen_meshcore_public.py

# Specify custom port
python3 listen_meshcore_public.py /dev/ttyACM1
```

### Get Help

```bash
python3 listen_meshcore_public.py --help
```

Output:
```
Usage: python listen_meshcore_public.py [PORT]

Arguments:
  PORT    Serial port (default: /dev/ttyACM2)

Examples:
  python listen_meshcore_public.py
  python listen_meshcore_public.py /dev/ttyACM1
  python listen_meshcore_public.py /dev/ttyACM0
```

## Finding Your USB Device

### Check available devices

```bash
ls /dev/ttyACM*
```

Output example:
```
/dev/ttyACM0  /dev/ttyACM1
```

### Check USB device info

```bash
dmesg | grep -i usb | tail -20
```

Look for lines like:
```
[51273.522737] cdc_acm 3-1:1.0: ttyACM1: USB ACM device
[51273.484698] usb 3-1: Product: XIAO nRF52840
```

This tells you the device is on `/dev/ttyACM1`.

## Scripts Updated

### 1. listen_meshcore_public.py

**Meshtastic-based diagnostic tool**

```bash
# Default
python3 listen_meshcore_public.py

# Custom port
python3 listen_meshcore_public.py /dev/ttyACM1

# Help
python3 listen_meshcore_public.py --help
```

### 2. listen_meshcore_channel.py

**MeshCore-based diagnostic tool**

```bash
# Default
python3 listen_meshcore_channel.py

# Custom port
python3 listen_meshcore_channel.py /dev/ttyACM1

# Help
python3 listen_meshcore_channel.py --help
```

## Common Use Cases

### Device on /dev/ttyACM1 (User's case)

```bash
python3 listen_meshcore_public.py /dev/ttyACM1
```

### Device on /dev/ttyACM0

```bash
python3 listen_meshcore_public.py /dev/ttyACM0
```

### Device on USB serial adapter

```bash
python3 listen_meshcore_public.py /dev/ttyUSB0
```

## Output Examples

### Successful Connection

```
🎯 MeshCore Public Channel Listener
================================================================================
Device: /dev/ttyACM1 @ 115200 baud
Started: 2026-02-12 21:36:19.161

🔌 Connecting to /dev/ttyACM1...
✅ Connected successfully
📡 My node ID: 0x12345678
🎧 Listening for messages...
```

### Connection Error

```
🔌 Connecting to /dev/ttyACM3...
❌ ERROR: [Errno 2] No such file or directory: '/dev/ttyACM3'
```

**Solution:** Check device with `ls /dev/ttyACM*` and use correct port.

### Timeout Error

```
🔌 Connecting to /dev/ttyACM1...
❌ ERROR: Timed out waiting for connection completion
```

**Possible causes:**
1. Wrong device (try other port)
2. Device is busy (close other programs using it)
3. Permission issue (try with `sudo`)

## Backward Compatibility

**Default behavior unchanged:**
```bash
python3 listen_meshcore_public.py
# Still uses /dev/ttyACM2 by default
```

**Existing scripts still work:**
- No changes needed for current users
- Old documentation still valid
- New users get flexibility

## Documentation Updated

All guides updated with port examples:

1. **MESHCORE_QUICK_START.md**
   - Port configuration section
   - Device discovery
   - Examples

2. **QUICK_START_DIAGNOSTIC.md**
   - Port usage
   - Help command
   - Common cases

## Benefits

✅ **Flexible** - Any USB port supported  
✅ **Easy** - Single command-line argument  
✅ **Clear** - Help messages explain usage  
✅ **Compatible** - Defaults to original port  
✅ **Documented** - Complete guides with examples  

## Implementation Details

### Argument Parsing

```python
# Default port
port = "/dev/ttyACM2"

# Check command-line arguments
if len(sys.argv) > 1:
    if sys.argv[1] in ['-h', '--help', 'help']:
        # Show help
        print_help()
        return 0
    else:
        # Use specified port
        port = sys.argv[1]

# Connect using port variable
interface = SerialInterface(port)
```

### Help Message

Both scripts support:
- `-h`
- `--help`
- `help`

All show usage information and examples.

## Troubleshooting

### "No such file or directory"

**Problem:** Port doesn't exist

**Solution:**
```bash
# Check available devices
ls /dev/ttyACM*
ls /dev/ttyUSB*

# Use correct port
python3 listen_meshcore_public.py /dev/ttyACM1
```

### "Permission denied"

**Problem:** No permission to access device

**Solution:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Or run with sudo (temporary)
sudo python3 listen_meshcore_public.py /dev/ttyACM1
```

### "Timed out waiting for connection"

**Problem:** Device not responding

**Solutions:**
1. Try different port
2. Check device is Meshtastic/MeshCore node
3. Verify baudrate (115200)
4. Close other programs using device
5. Unplug and replug USB

## Summary

**Feature:** USB port as command-line argument  
**Scripts:** Both diagnostic tools  
**Default:** `/dev/ttyACM2` (backward compatible)  
**Usage:** `python3 script.py /dev/ttyACM1`  
**Status:** ✅ Complete and documented  

User can now specify any USB port without modifying code!
