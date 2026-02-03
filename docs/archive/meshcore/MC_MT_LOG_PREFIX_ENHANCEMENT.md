# MC/MT Log Prefix Enhancement

## Overview

Enhanced debug and info logging to clearly distinguish between MeshCore and Meshtastic component logs using prefixes `[MC]` and `[MT]`.

## Problem Statement

> "Could you identify better the debug log of the packets from Meshtastic and Meshcore, eventually with a prefix after like [DEBUG][MC] or [DEBUG][MT] for incoming/outgoing log. Also [INFO][MC] or [INFO][MT]"

Previously, all logs used generic prefixes like `[DEBUG]` or `[INFO]`, making it difficult to identify which component (MeshCore or Meshtastic) generated specific log entries.

## Solution Implemented

### 1. Enhanced Logging Functions

Updated `utils.py` with source parameter support:

```python
def debug_print(message, source=None):
    """Debug print with optional source prefix"""
    if DEBUG_MODE:
        if source:
            print(f"[DEBUG][{source}] {message}", ...)
        else:
            print(f"[DEBUG] {message}", ...)

def info_print(message, source=None):
    """Info print with optional source prefix"""
    if source:
        print(f"[INFO][{source}] {message}", ...)
    else:
        print(f"[INFO] {message}", ...)
```

### 2. Convenience Functions

Added specialized logging functions for each component:

```python
# MeshCore logging
def debug_print_mc(message):
    """MeshCore debug: [DEBUG][MC]"""
    debug_print(message, source='MC')

def info_print_mc(message):
    """MeshCore info: [INFO][MC]"""
    info_print(message, source='MC')

# Meshtastic logging
def debug_print_mt(message):
    """Meshtastic debug: [DEBUG][MT]"""
    debug_print(message, source='MT')

def info_print_mt(message):
    """Meshtastic info: [INFO][MT]"""
    info_print(message, source='MT')
```

### 3. Updated Components

#### MeshCore Components (MC prefix)
- **meshcore_cli_wrapper.py** - All MeshCore operations
  - Library initialization
  - Device connection
  - RX_LOG packet processing
  - DM handling
  - Contact management

#### Meshtastic Components (MT prefix)
- **safe_serial_connection.py** - Serial port management
  - Port locking/unlocking
  - Connection/reconnection
  - Event subscriptions
- **safe_tcp_connection.py** - TCP connection management
  - TCP connection states
  - Reconnection logic
  - Health checks

#### Main Bot (Context-specific)
- **main_bot.py** - Uses appropriate prefix based on context
  - MC prefix for MeshCore operations
  - MT prefix for Meshtastic operations
  - Generic prefix for general bot operations

## Log Format

### Before
```
[DEBUG] ✅ [MESHCORE] Library meshcore-cli disponible
[INFO] 🔌 [MESHCORE-CLI] Connexion à /dev/ttyUSB0...
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (134B)
[INFO] ✅ Port /dev/ttyACM0 disponible
[DEBUG] 🔌 Meshtastic signale une déconnexion
```

### After
```
[INFO][MC] ✅ Library meshcore-cli disponible
[INFO][MC] 🔌 Connexion à /dev/ttyUSB0...
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (134B)
[INFO][MT] ✅ Port /dev/ttyACM0 disponible
[DEBUG][MT] 🔌 Meshtastic signale une déconnexion
```

## Example Output

### MeshCore Logs (MC)
```
[INFO][MC] ✅ Library meshcore-cli disponible
[INFO][MC] 🔧 Initialisation: /dev/ttyUSB0 (debug=True)
[INFO][MC] 🔌 Connexion à /dev/ttyUSB0...
[INFO][MC] ✅ Device connecté sur /dev/ttyUSB0
[DEBUG][MC] ✅ PyNaCl disponible (validation clés)
[DEBUG][MC] ✅ NodeManager configuré
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm
[DEBUG][MC] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B
[DEBUG][MC] 📢 [RX_LOG] Advert from: Node | Role: Repeater | GPS: (47.54, -122.11)
```

### Meshtastic Logs (MT)
```
[INFO][MT] 🔧 Initialisation connexion série sur /dev/ttyACM0
[INFO][MT] ✅ Port /dev/ttyACM0 disponible
[INFO][MT] ✅ Connexion série établie
[DEBUG][MT] ✅ Abonné aux événements Meshtastic
[DEBUG][MT] 🔌 Meshtastic signale une déconnexion: DEVICE_RESTARTING
[INFO][MT] ⚠️ Connexion perdue, tentative de reconnexion...
[DEBUG][MT] Tentative de reconnexion (1/3)...
```

### Mixed Scenario
```
[INFO][MC] 🔧 Initialisation MeshCore companion mode
[INFO][MT] 🔌 Connexion série Meshtastic en cours...
[DEBUG][MT] ✅ Port série ouvert
[DEBUG][MC] ✅ MeshCore event handler configuré
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (45B)
[DEBUG][MC] 📝 [RX_LOG] 📢 Public Message: "Hello!"
[INFO] ✅ Bot démarré avec succès
```

## Benefits

### 1. Easy Component Identification
- **[MC]** = MeshCore operations (companion mode, packet decoding)
- **[MT]** = Meshtastic operations (serial/TCP connections)
- **No prefix** = Generic bot operations

### 2. Better Troubleshooting
Quick identification of issue source:
- Connection problems → Look for `[MT]` logs
- Packet decoding issues → Look for `[MC]` logs
- RX_LOG traffic → `[DEBUG][MC]` with `[RX_LOG]`

### 3. Simplified Log Analysis

```bash
# All MeshCore logs
journalctl -u meshbot | grep '\[MC\]'

# All Meshtastic logs
journalctl -u meshbot | grep '\[MT\]'

# MeshCore debug only
journalctl -u meshbot | grep '\[DEBUG\]\[MC\]'

# Meshtastic connection issues
journalctl -u meshbot | grep '\[INFO\]\[MT\].*connexion'

# RX_LOG packet traffic
journalctl -u meshbot | grep '\[DEBUG\]\[MC\].*RX_LOG'
```

### 4. Backward Compatibility
- Existing code without source parameter still works
- Generic logs use `[DEBUG]` or `[INFO]` as before
- No breaking changes to existing functionality

## Implementation Details

### Files Modified

1. **utils.py** (Core logging)
   - Added `source` parameter to `debug_print()` and `info_print()`
   - Added `debug_print_mc()`, `info_print_mc()`
   - Added `debug_print_mt()`, `info_print_mt()`

2. **meshcore_cli_wrapper.py** (MeshCore)
   - ~205 logging calls updated to use `_mc` functions
   - All RX_LOG messages now show `[DEBUG][MC]`
   - All initialization/connection logs now show `[INFO][MC]`

3. **safe_serial_connection.py** (Meshtastic Serial)
   - All logs updated to use `_mt` functions
   - Port management logs now show `[INFO][MT]`
   - Connection events now show `[DEBUG][MT]`

4. **safe_tcp_connection.py** (Meshtastic TCP)
   - All logs updated to use `_mt` functions
   - TCP connection logs now show `[INFO][MT]`
   - Reconnection logic now shows `[DEBUG][MT]`

5. **main_bot.py** (Main Orchestrator)
   - MeshCore-specific logs use `info_print_mc()`
   - Kept generic logs for general bot operations

### Statistics

- **205+ logs** updated in meshcore_cli_wrapper.py
- **30+ logs** updated in safe_serial_connection.py
- **25+ logs** updated in safe_tcp_connection.py
- **3 logs** updated in main_bot.py
- **6 new functions** added to utils.py

## Testing

### Demo Script
Run `demo_mc_mt_log_prefix.py` to see examples of all log types:
```bash
python3 demo_mc_mt_log_prefix.py
```

### Manual Testing
1. Start bot with DEBUG_MODE=True
2. Observe logs during:
   - MeshCore initialization → `[INFO][MC]`
   - Serial connection → `[INFO][MT]`
   - Packet reception → `[DEBUG][MC]` with `[RX_LOG]`
   - Reconnection → `[DEBUG][MT]`

## Use Cases

### Debugging Connection Issues
```bash
# Check Meshtastic serial connection
journalctl -u meshbot | grep '\[MT\].*ttyACM0'

# Check if MeshCore initialized
journalctl -u meshbot | grep '\[MC\].*Library meshcore-cli'
```

### Monitoring Packet Traffic
```bash
# All RX_LOG packets
journalctl -u meshbot | grep '\[DEBUG\]\[MC\].*RX_LOG'

# Advertisement packets only
journalctl -u meshbot | grep '\[DEBUG\]\[MC\].*Advert'

# Public messages
journalctl -u meshbot | grep '\[DEBUG\]\[MC\].*Public Message'
```

### Troubleshooting Disconnections
```bash
# Meshtastic disconnections
journalctl -u meshbot | grep '\[MT\].*déconnexion'

# MeshCore health checks
journalctl -u meshbot | grep '\[MC\].*health'
```

## Performance Impact

✅ **Zero performance impact**
- Logging functions just add prefix string
- No additional computation or I/O
- Backward compatible with existing code

## Future Enhancements

Possible additions:
- `[MQTT]` prefix for MQTT operations
- `[TG]` prefix for Telegram integration
- `[DB]` prefix for database operations
- Configurable prefix colors in terminal output
