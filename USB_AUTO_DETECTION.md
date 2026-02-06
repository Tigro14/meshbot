# USB Port Auto-Detection

## Overview

The bot now supports automatic USB port detection based on device attributes instead of hardcoded port paths. This makes configuration more robust when USB ports change after reboots or when multiple devices are connected.

## Problem Solved

**Before:** Configuration used fixed paths that could change:
```python
SERIAL_PORT = "/dev/ttyACM0"  # Might become /dev/ttyACM1 after reboot!
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

**After:** Configuration identifies devices by their attributes:
```python
SERIAL_PORT = "auto:HT-n5262"  # Always finds the Heltec device
MESHCORE_SERIAL_PORT = "auto:XIAO nRF52"  # Always finds the XIAO device
```

## Configuration Formats

### 1. Regular Fixed Port (Classic)
```python
SERIAL_PORT = "/dev/ttyACM0"
```
Works as before - no auto-detection.

### 2. Auto-Detect First Device
```python
SERIAL_PORT = "auto"
```
Uses the first USB serial device found.

### 3. Auto-Detect by Product Name (Recommended)
```python
SERIAL_PORT = "auto:HT-n5262"           # Heltec device
SERIAL_PORT = "auto:XIAO nRF52840"      # Seeed XIAO device
SERIAL_PORT = "auto:RAK"                # RAK device (partial match)
```
Matches devices containing the specified product name (case-insensitive, partial match).

### 4. Auto-Detect by Serial Number (Most Specific)
```python
SERIAL_PORT = "auto:serial=B5A131E366B43F18"
```
Matches exact serial number - best for multi-device setups with same product.

### 5. Auto-Detect by Manufacturer
```python
SERIAL_PORT = "auto:manufacturer=Heltec"
SERIAL_PORT = "auto:manufacturer=Seeed"
```
Matches by manufacturer name (partial match).

### 6. Auto-Detect with Multiple Criteria
```python
# Product + Serial (most specific)
SERIAL_PORT = "auto:product=HT-n5262,serial=B5A131E366B43F18"

# Product + Manufacturer
SERIAL_PORT = "auto:product=nRF52840,manufacturer=Seeed"

# Vendor ID + Product ID (USB identifiers)
SERIAL_PORT = "auto:vendor=239a,productid=4405"
```

## Usage Examples

### Single Device Setup
```python
# config.py
DUAL_NETWORK_MODE = False
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False

# Use product name for auto-detection
SERIAL_PORT = "auto:HT-n5262"
```

### Dual Device Setup (Meshtastic + MeshCore)
```python
# config.py
DUAL_NETWORK_MODE = True
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True

# Use different product names to identify each device
SERIAL_PORT = "auto:HT-n5262"              # Heltec for Meshtastic
MESHCORE_SERIAL_PORT = "auto:XIAO nRF52"   # XIAO for MeshCore
```

### Multiple Same Devices (Use Serial Numbers)
```python
# If you have two identical devices, use serial numbers
SERIAL_PORT = "auto:serial=B5A131E366B43F18"           # First Heltec
MESHCORE_SERIAL_PORT = "auto:serial=7CEF06581293BD9C"  # XIAO device
```

## How It Works

1. **Detection Process:**
   - Scans `/sys/class/tty/tty*/device/..` for USB serial devices
   - Reads product name, manufacturer, serial number from sysfs
   - Matches against configured criteria
   - Returns device path (e.g., `/dev/ttyACM0`)

2. **Startup Logging:**
   ```
   🔍 Auto-detecting USB port for Meshtastic...
      Configuration: auto:HT-n5262
      Found 2 USB serial device(s):
        - /dev/ttyACM0: Heltec HT-n5262 (SN: B5A131E366B43F18)
        - /dev/ttyACM1: Seeed Studio XIAO nRF52840 (SN: 7CEF06581293BD9C)
   ✅ Auto-detected port: /dev/ttyACM0
      Device: Heltec HT-n5262
      Serial: B5A131E366B43F18
   ```

3. **Fallback Behavior:**
   - If auto-detection fails, logs error with troubleshooting steps
   - Returns original configuration string
   - Bot will attempt to use it (may fail if invalid)

## Testing Your Configuration

### 1. List Connected Devices
```bash
# Run the detector utility
python3 usb_port_detector.py
```

Output:
```
================================================================================
USB Serial Device Detection Test
================================================================================

✅ Found 2 USB serial device(s):

1. /dev/ttyACM0
   Product:      HT-n5262
   Manufacturer: Heltec
   Serial:       B5A131E366B43F18
   Vendor ID:    239a
   Product ID:   4405

2. /dev/ttyACM1
   Product:      XIAO nRF52840
   Manufacturer: Seeed Studio
   Serial:       7CEF06581293BD9C
   Vendor ID:    2886
   Product ID:   8044
```

### 2. Test Detection Strings
The utility also tests various detection formats:
```
✅ HT-n5262 by product name → /dev/ttyACM0
✅ XIAO by partial product name → /dev/ttyACM1
✅ Heltec by serial number → /dev/ttyACM0
```

### 3. Check Bot Logs
```bash
# Start bot and check logs
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot -f | grep -A 5 "Auto-detecting"
```

Should see successful detection messages.

## Troubleshooting

### Issue: No devices found
```bash
# Check if devices are connected
ls -la /dev/ttyACM* /dev/ttyUSB*

# Check USB devices
lsusb

# Run detector utility
python3 usb_port_detector.py
```

### Issue: Wrong device detected
Use more specific criteria:
```python
# Too generic (might match wrong device)
SERIAL_PORT = "auto:nRF52"

# More specific (better)
SERIAL_PORT = "auto:XIAO nRF52840"

# Most specific (best)
SERIAL_PORT = "auto:serial=7CEF06581293BD9C"
```

### Issue: Auto-detection fails
Check bot logs:
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep -A 10 "Auto-detection failed"
```

Fallback to manual configuration:
```python
SERIAL_PORT = "/dev/ttyACM0"  # Manual fallback
```

## Technical Details

### Implementation
- **Module:** `usb_port_detector.py`
- **Integration:** `main_bot.py` calls `USBPortDetector.resolve_port()`
- **No External Dependencies:** Uses standard Python + sysfs
- **Fallback:** Graceful degradation to manual config

### USB Device Attributes
The detector reads from `/sys/class/tty/*/device/../`:
- `product` - Product name (e.g., "HT-n5262")
- `manufacturer` - Manufacturer (e.g., "Heltec")
- `serial` - Serial number (e.g., "B5A131E366B43F18")
- `idVendor` - USB Vendor ID (e.g., "239a")
- `idProduct` - USB Product ID (e.g., "4405")

### Matching Logic
- **Product/Manufacturer:** Case-insensitive partial match
- **Serial Number:** Exact match
- **Vendor/Product IDs:** Exact match (hex, lowercase)

## Benefits

✅ **Robust Configuration:** Ports won't change after reboot
✅ **Multi-Device Support:** Easily identify correct device
✅ **Self-Documenting:** Config shows what device is expected
✅ **Graceful Fallback:** Falls back to manual config if detection fails
✅ **No Dependencies:** Uses standard Python + sysfs
✅ **Easy Debugging:** Utility script shows all detected devices

## Migration Guide

### From Fixed Ports
```python
# Old way
SERIAL_PORT = "/dev/ttyACM0"
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"

# New way (after running usb_port_detector.py to see device names)
SERIAL_PORT = "auto:HT-n5262"
MESHCORE_SERIAL_PORT = "auto:XIAO nRF52"
```

### Testing Migration
1. Run `python3 usb_port_detector.py` to see your devices
2. Note the product names or serial numbers
3. Update config.py with auto-detection strings
4. Restart bot and verify detection works
5. Check logs for successful detection messages

## Future Enhancements

Possible future improvements:
- Support for Bluetooth devices
- USB hub path matching (for permanent port assignment)
- Device aliases in config file
- Hot-plug detection and reconnection
