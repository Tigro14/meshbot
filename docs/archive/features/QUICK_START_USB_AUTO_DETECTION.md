# Quick Start: USB Auto-Detection

## Quick Setup (30 seconds)

### 1. Discover Your Devices
```bash
cd /home/dietpi/bot
python3 usb_port_detector.py
```

Output shows your devices:
```
1. /dev/ttyACM0
   Product:      HT-n5262
   Manufacturer: Heltec
   Serial:       B5A131E366B43F18

2. /dev/ttyACM1
   Product:      XIAO nRF52840
   Manufacturer: Seeed Studio
   Serial:       7CEF06581293BD9C
```

### 2. Update config.py
```python
# Use product names from above
SERIAL_PORT = "auto:HT-n5262"
MESHCORE_SERIAL_PORT = "auto:XIAO nRF52"
```

### 3. Restart and Verify
```bash
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot --since "1m" | grep "Auto-detected"
```

Should see:
```
✅ Auto-detected port: /dev/ttyACM0
   Device: Heltec HT-n5262
```

## Common Configurations

### Single Device
```python
SERIAL_PORT = "auto:HT-n5262"  # Product name
# OR
SERIAL_PORT = "auto:serial=B5A131E366B43F18"  # Serial number
```

### Dual Device (Meshtastic + MeshCore)
```python
DUAL_NETWORK_MODE = True
SERIAL_PORT = "auto:HT-n5262"              # Heltec
MESHCORE_SERIAL_PORT = "auto:XIAO nRF52"   # XIAO
```

### Multiple Same Devices
```python
# Use serial numbers to distinguish
SERIAL_PORT = "auto:serial=B5A131E366B43F18"           # First device
MESHCORE_SERIAL_PORT = "auto:serial=7CEF06581293BD9C"  # Second device
```

## Formats

| Format | Example | Use Case |
|--------|---------|----------|
| `auto` | `"auto"` | First USB device found |
| Product name | `"auto:HT-n5262"` | **Recommended** for most cases |
| Serial number | `"auto:serial=B5A..."` | Multiple identical devices |
| Manufacturer | `"auto:manufacturer=Heltec"` | By vendor |
| Multiple | `"auto:product=X,serial=Y"` | Very specific |
| Fixed port | `"/dev/ttyACM0"` | Classic (backward compatible) |

## Troubleshooting

### No devices found?
```bash
# Check USB connections
ls -la /dev/ttyACM* /dev/ttyUSB*

# List USB devices
lsusb

# Run detector
python3 usb_port_detector.py
```

### Wrong device detected?
Use more specific criteria:
```python
# Too generic
SERIAL_PORT = "auto:nRF"  # Might match multiple!

# Better
SERIAL_PORT = "auto:XIAO nRF52840"

# Best (most specific)
SERIAL_PORT = "auto:serial=7CEF06581293BD9C"
```

### Detection failed?
Check bot logs:
```bash
journalctl -u meshtastic-bot --since "5m" | grep -A 5 "Auto-detection failed"
```

Fallback to manual:
```python
SERIAL_PORT = "/dev/ttyACM0"  # Manual port
```

## Verification Commands

```bash
# List devices
python3 usb_port_detector.py

# Check bot logs for detection
journalctl -u meshtastic-bot -f | grep "Auto-detecting"

# Full startup logs
journalctl -u meshtastic-bot --since "1m" | head -100
```

## Benefits

✅ Ports don't change after reboot
✅ Easy multi-device setup
✅ Self-documenting configuration
✅ Backward compatible with fixed ports

## Full Documentation

See `USB_AUTO_DETECTION.md` for complete guide.
