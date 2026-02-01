# Diagnostic Test Configuration Guide

## Problem Fixed

The diagnostic test script (`test_message_polling_diagnostic.py`) previously failed with:
```
❌ Import error: cannot import name 'TCP_HOST' from 'config'
```

This occurred when users had only serial Meshtastic configuration and didn't define TCP variables.

## Solution

The script now uses graceful imports with `getattr()` and provides helpful error messages.

---

## Supported Configurations

### 1. Serial-Only Meshtastic (Most Common)

**Minimal config.py:**
```python
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'serial'
SERIAL_PORT = '/dev/ttyACM0'

# TCP_HOST and TCP_PORT are NOT needed for serial mode
```

**Test Output:**
```
============================================================
TEST 1: Meshtastic pub.subscribe System
============================================================
✅ Imports successful
   CONNECTION_MODE: serial
   Creating serial interface: /dev/ttyACM0
✅ Interface created
```

---

### 2. TCP Meshtastic

**Full config.py:**
```python
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'tcp'
SERIAL_PORT = '/dev/ttyACM0'
TCP_HOST = '192.168.1.38'
TCP_PORT = 4403
```

**Test Output:**
```
============================================================
TEST 1: Meshtastic pub.subscribe System
============================================================
✅ Imports successful
   CONNECTION_MODE: tcp
   Creating TCP interface: 192.168.1.38:4403
✅ Interface created
```

---

### 3. TCP Mode with Missing Configuration

**Incorrect config.py:**
```python
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'tcp'
# Missing TCP_HOST and TCP_PORT!
```

**Test Output:**
```
============================================================
TEST 1: Meshtastic pub.subscribe System
============================================================
✅ Imports successful
   CONNECTION_MODE: tcp
❌ TCP mode selected but TCP_HOST or TCP_PORT not configured in config.py
   Please add TCP_HOST and TCP_PORT to your config.py or use CONNECTION_MODE='serial'
```

---

### 4. MeshCore-Only (No Meshtastic)

**config.py:**
```python
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = '/dev/ttyUSB0'
```

**Test Output:**
```
============================================================
TEST 1: Meshtastic pub.subscribe System
============================================================
❌ MESHTASTIC_ENABLED=False - Test skipped

============================================================
TEST 2: MeshCore CLI Wrapper Event Loop
============================================================
✅ Imports successful
   MESHCORE_SERIAL_PORT: /dev/ttyUSB0
```

---

## Configuration Variables

### Required for All Modes
- `MESHTASTIC_ENABLED` (default: True)
- `MESHCORE_ENABLED` (default: False)

### Serial Meshtastic Mode
Required:
- `CONNECTION_MODE = 'serial'`
- `SERIAL_PORT` (default: '/dev/ttyACM0')

Optional:
- TCP_HOST - Not needed
- TCP_PORT - Not needed

### TCP Meshtastic Mode
Required:
- `CONNECTION_MODE = 'tcp'`
- `TCP_HOST` (e.g., '192.168.1.38')
- `TCP_PORT` (e.g., 4403)

Optional:
- `SERIAL_PORT` - Not used in TCP mode

### MeshCore Mode
Required:
- `MESHCORE_ENABLED = True`
- `MESHCORE_SERIAL_PORT` (default: '/dev/ttyUSB0')

---

## Troubleshooting

### Error: "cannot import name 'TCP_HOST'"
**Fixed in this update!** The test now handles missing TCP config gracefully.

### Error: "TCP mode selected but TCP_HOST or TCP_PORT not configured"
**Solution:** Add to your config.py:
```python
TCP_HOST = '192.168.1.38'  # Your Meshtastic node's IP
TCP_PORT = 4403            # Default Meshtastic TCP port
```

Or switch to serial mode:
```python
CONNECTION_MODE = 'serial'
```

### Test Skipped: "MESHTASTIC_ENABLED=False"
**Solution:** If you want to test Meshtastic, set:
```python
MESHTASTIC_ENABLED = True
```

### Test Skipped: "MESHCORE_ENABLED=False"
**Solution:** If you want to test MeshCore, set:
```python
MESHCORE_ENABLED = True
```

---

## Running the Tests

### Full Diagnostic
```bash
cd /home/runner/work/meshbot/meshbot
python3 test_message_polling_diagnostic.py
```

### Test Config Import Pattern Only
```bash
python3 test_config_import_graceful.py
```

Expected output:
```
✅ Serial-only config (no TCP vars): PASS
✅ Full TCP config: PASS
✅ All tests PASSED!
```

---

## Migration Guide

### Before (Broken)
Users with serial-only config got import errors.

### After (Fixed)
All configurations work, with helpful error messages for misconfigurations.

**No action needed** - existing configs continue to work!

---

## Technical Details

### Import Pattern Change

**Before (Broke with missing TCP vars):**
```python
from config import MESHTASTIC_ENABLED, CONNECTION_MODE, SERIAL_PORT, TCP_HOST, TCP_PORT
```

**After (Graceful fallback):**
```python
import config
MESHTASTIC_ENABLED = getattr(config, 'MESHTASTIC_ENABLED', True)
CONNECTION_MODE = getattr(config, 'CONNECTION_MODE', 'serial')
SERIAL_PORT = getattr(config, 'SERIAL_PORT', '/dev/ttyACM0')
TCP_HOST = getattr(config, 'TCP_HOST', None)
TCP_PORT = getattr(config, 'TCP_PORT', None)
```

### Validation Added
```python
if CONNECTION_MODE.lower() == 'tcp':
    if TCP_HOST is None or TCP_PORT is None:
        print("❌ TCP mode requires TCP_HOST and TCP_PORT")
        return False
```

This ensures users get clear feedback when configuration is incomplete.
