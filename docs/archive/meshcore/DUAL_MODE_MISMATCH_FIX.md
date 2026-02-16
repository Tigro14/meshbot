# Dual Mode Mismatch Fix

## Problem

User asked: "Why `dual_mode=False` but dual_mode set to True?"

Log showed:
```
[DEBUG] 🔍 [FILTER] dual_mode=False
```

But `DUAL_NETWORK_MODE = True` in config.

## Answer

**The log is CORRECT - dual mode initialization FAILED.**

### What Happens

1. **Config**: `DUAL_NETWORK_MODE = True` (what you configured)
2. **Startup**: Bot tries to initialize both Meshtastic + MeshCore
3. **Failure**: One of the interfaces fails to initialize
4. **Fallback**: `self._dual_mode_active = False` (runtime state)
5. **Result**: Bot runs in single interface mode

### Why It Fails

Dual mode initialization can fail at three points:

#### 1. Meshtastic Interface Creation Fails (line 2081)
```python
if not meshtastic_interface:
    error_print("❌ Échec création interface Meshtastic - Mode dual désactivé")
    self._dual_mode_active = False
```

**Causes:**
- Serial port doesn't exist
- USB device unplugged
- Serial timeout (device not responding)
- Permission denied

#### 2. MeshCore Connection Fails (line 2114)
```python
if not meshcore_interface.connect():
    error_print("❌ MESHCORE CONNECTION FAILED - Dual mode désactivé")
    self._dual_mode_active = False
```

**Causes:**
- Serial port doesn't exist
- Port already in use
- Device not in correct mode
- Permission denied

#### 3. MeshCore Start Reading Fails (line 2141)
```python
if not meshcore_interface.start_reading():
    error_print("❌ MESHCORE START_READING FAILED - Dual mode désactivé")
    self._dual_mode_active = False
```

**Causes:**
- Thread creation failed
- Serial communication error
- Device hung or crashed

## Solution

### Enhanced Warning Banner

Added ultra-visible warning when config != runtime:

```
⚠️  DUAL MODE MISMATCH DETECTED!
================================================================================
   Config: DUAL_NETWORK_MODE = True
   Runtime: dual_mode_active = False

   ❌ Dual mode initialization FAILED during startup
   → Check logs above for error messages:
      - 'Échec création interface Meshtastic'
      - 'MESHCORE CONNECTION FAILED'
      - 'MESHCORE START_READING FAILED'

   📋 Bot running in FALLBACK mode:
      → Using MeshCore ONLY (Meshtastic failed)
      (or)
      → Using Meshtastic ONLY (MeshCore failed)
================================================================================
```

### Clarified Filter Log

Changed variable name from:
```
dual_mode={self._dual_mode_active}
```

To:
```
dual_mode_active={self._dual_mode_active}
```

Makes it clear this is **runtime state**, not config value.

## Expected Output

### Success (No Warning)

```
🔔 SUBSCRIPTION SETUP - CRITICAL FOR PACKET RECEPTION
   meshtastic_enabled = True
   meshcore_enabled = True
   dual_mode (config) = True
   dual_mode (active) = True
   connection_mode = serial
   interface type = DualInterfaceManager

   📡 ACTIVE NETWORKS:
      ✅ Meshtastic (via primary interface)
      ✅ MeshCore (via dual interface)
      → Will see [DEBUG][MT] AND [DEBUG][MC] packets
```

### Failure (With Warning)

```
🔔 SUBSCRIPTION SETUP - CRITICAL FOR PACKET RECEPTION
   meshtastic_enabled = True
   meshcore_enabled = True
   dual_mode (config) = True
   dual_mode (active) = False
   connection_mode = serial
   interface type = MeshCoreCLIWrapper

⚠️  DUAL MODE MISMATCH DETECTED!
================================================================================
   Config: DUAL_NETWORK_MODE = True
   Runtime: dual_mode_active = False

   ❌ Dual mode initialization FAILED during startup
   → Check logs above for error messages:
      - 'Échec création interface Meshtastic'
      - 'MESHCORE CONNECTION FAILED'
      - 'MESHCORE START_READING FAILED'

   📋 Bot running in FALLBACK mode:
      → Using MeshCore ONLY (Meshtastic failed)
================================================================================

   📡 ACTIVE NETWORK:
      ✅ MeshCore ONLY
      → Will see [DEBUG][MC] packets only
```

## Troubleshooting

### If Warning Appears

1. **Check startup logs for errors:**
```bash
journalctl -u meshtastic-bot -n 500 | grep -E "FAILED|Échec"
```

2. **Verify serial ports exist:**
```bash
ls -la /dev/ttyACM* /dev/ttyUSB*
```

3. **Check which ports are configured:**
```bash
grep -E "SERIAL_PORT|MESHCORE_SERIAL_PORT" config.py
```

4. **Test interfaces individually:**

Test Meshtastic only:
```python
# In config.py
DUAL_NETWORK_MODE = False
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
```

Test MeshCore only:
```python
# In config.py
DUAL_NETWORK_MODE = False
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True
```

5. **Check device responding:**

Meshtastic:
```bash
python3 -m meshtastic --port /dev/ttyACM0 --info
```

MeshCore:
```bash
# Device should respond to serial commands
# Check MeshCore documentation for specific tests
```

### Common Issues

#### Both Interfaces on Same Port
```python
# BAD - Both using same port!
SERIAL_PORT = "/dev/ttyACM0"
MESHCORE_SERIAL_PORT = "/dev/ttyACM0"
```

Fix: Use different ports
```python
SERIAL_PORT = "/dev/ttyACM0"  # Meshtastic
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore
```

#### Port Permissions
```bash
# Check permissions
ls -la /dev/ttyACM0

# Add user to dialout group
sudo usermod -a -G dialout $USER

# Reboot required
sudo reboot
```

#### USB Device Unplugged
- Check USB cables
- Check power to devices
- Try different USB port

#### Port Already in Use
```bash
# Check what's using the port
sudo lsof /dev/ttyACM0

# Kill process if needed
sudo kill <PID>
```

## Benefits

1. ✅ **Immediate visibility** - See mismatch at startup
2. ✅ **Clear explanation** - Why config != runtime
3. ✅ **Actionable info** - Where to look for errors
4. ✅ **Fallback mode shown** - Know which interface active
5. ✅ **No confusion** - Config vs runtime clarified

## Summary

- **Config value** (`DUAL_NETWORK_MODE`) = What you want
- **Runtime value** (`dual_mode_active`) = What you got
- **Warning appears** when they don't match
- **Bot still works** in fallback single-interface mode
- **Fix the initialization** to enable true dual mode

## Files Modified

1. **main_bot.py** (+24 lines, -1 line)
   - Added mismatch detection at subscription setup
   - Added warning banner with diagnostic info
   - Clarified filter log variable name
