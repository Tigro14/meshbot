# Fix: MeshCore Traffic Not Visible

## Problem
Bot does not display any MeshCore traffic, nor respond to MeshCore DM messages.

Despite configuration:
- `DUAL_NETWORK_MODE = True`
- `MESHCORE_ENABLED = True`
- `MESHTASTIC_ENABLED = True`

## Root Causes Identified

### 1. Wrong Logging Function
All packet logging used `debug_print_mt()` (Meshtastic tag [DEBUG][MT]) for ALL packets, including MeshCore packets.

**Result:** MeshCore packets were logged with `[DEBUG][MT]` prefix instead of `[DEBUG][MC]`.

### 2. Insufficient Serial Diagnostics
No visibility into:
- Serial port data reception
- Thread status and activity
- Actual data received on serial port

**Result:** Impossible to determine if:
- Serial port receiving data
- Threads running properly
- Data format correct

## Solution Applied

### Enhanced Diagnostics (meshcore_serial_interface.py)

#### Startup Diagnostics
Added comprehensive startup banner in `start_reading()`:
```
================================================================================
🔧 [MESHCORE] DÉMARRAGE DIAGNOSTICS
================================================================================
   Port série: /dev/ttyUSB0
   Baudrate: 115200
   Port ouvert: True
   Message callback: True
================================================================================
✅ [MESHCORE] Thread de lecture démarré
✅ [MESHCORE] Thread de polling démarré
✅ [MESHCORE] Read thread confirmed running
✅ [MESHCORE] Poll thread confirmed running
```

#### Runtime Diagnostics
Enhanced `_read_loop()` with:
- **Loop iteration counter** - Tracks activity
- **Data reception counter** - Counts packets received
- **Periodic heartbeat** - Logs every 60 seconds:
  ```
  🔄 [MESHCORE-HEARTBEAT] Read loop active: 1200 iterations, 0 data packets received
  ```
- **Hex data dump** - Shows actual bytes received:
  ```
  📥 [MESHCORE-DATA] 45 bytes waiting (packet #1)
  📦 [MESHCORE-RAW] Read 45 bytes: 3e2d00010203...
  ```
- **Format detection** - Distinguishes text vs binary

### Fixed Packet Logging (traffic_monitor.py)

Changed all packet logging functions to use correct prefix based on source:

```python
# Before (BROKEN - always used MT):
debug_print_mt(f"📦 {packet_type} de {sender_name}...")

# After (FIXED - dynamic selection):
debug_func = debug_print_mc if source == 'meshcore' else debug_print_mt
debug_func(f"📦 {packet_type} de {sender_name}...")
```

**Fixed functions:**
- `add_packet()` - Line 931
- `_log_packet_debug()` - Line 980
- `_log_comprehensive_packet_debug()` - Lines 1093, 1177

## Expected Behavior After Fix

### Scenario A: MeshCore Receiving Data
```
🔧 [MESHCORE] DÉMARRAGE DIAGNOSTICS
   Port série: /dev/ttyUSB0
   Message callback: True
✅ [MESHCORE] Read thread confirmed running
✅ [MESHCORE] Poll thread confirmed running
📡 [MESHCORE] Début lecture messages MeshCore...

[When data arrives:]
📥 [MESHCORE-DATA] 45 bytes waiting (packet #1)
📦 [MESHCORE-RAW] Read 45 bytes: 3e2d00...
📨 [MESHCORE-TEXT] Reçu: DM:12345678:Hello bot
📬 [MESHCORE-DM] De: 0x12345678 | Message: Hello bot
📞 [MESHCORE-TEXT] Calling message_callback...
✅ [MESHCORE-TEXT] Callback completed successfully

[In traffic_monitor:]
🔵 add_packet ENTRY | source=meshcore | from=0x12345678
[DEBUG][MC] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de User
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de User 45678 [direct] (SNR:n/a)
[DEBUG][MC] 🔗 MESHCORE TEXTMESSAGE from User (45678) | Hops:0/0
[DEBUG][MC]   └─ Msg:"Hello bot" | Payload:9B | ID:123456
```

### Scenario B: No MeshCore Data (Diagnostic)
```
🔧 [MESHCORE] DÉMARRAGE DIAGNOSTICS
   Port série: /dev/ttyUSB0
✅ [MESHCORE] Read thread confirmed running
📡 [MESHCORE] Début lecture messages MeshCore...

[After 60 seconds:]
🔄 [MESHCORE-HEARTBEAT] Read loop active: 600 iterations, 0 data packets received

[After 120 seconds:]
🔄 [MESHCORE-HEARTBEAT] Read loop active: 1200 iterations, 0 data packets received
```

**This clearly indicates:**
- ✅ Interface connected
- ✅ Threads running
- ❌ But no data arriving on serial port

**Possible causes:**
1. Wrong serial port (e.g., /dev/ttyUSB0 when should be /dev/ttyUSB1)
2. Radio not connected to USB
3. Radio not powered
4. Radio not in companion mode
5. Wrong baudrate (should be 115200)

### Scenario C: Wrong Serial Port
```
❌ [MESHCORE] Erreur connexion série: [Errno 2] No such file or directory: '/dev/ttyUSB0'
❌ Échec connexion MeshCore - Mode dual désactivé
```

## Deployment

```bash
cd /home/dietpi/bot
git checkout copilot/update-sqlite-data-cleanup
git pull
sudo systemctl restart meshtastic-bot
```

## Verification Steps

### 1. Check Startup Diagnostics
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep -A 20 "DÉMARRAGE DIAGNOSTICS"
```

**Look for:**
- ✅ `Port ouvert: True`
- ✅ `Message callback: True`
- ✅ `Read thread confirmed running`
- ✅ `Poll thread confirmed running`

### 2. Monitor Heartbeat
```bash
journalctl -u meshtastic-bot -f | grep "HEARTBEAT"
```

**Expected:** One message every 60 seconds showing:
- Loop iteration count (should increase)
- Data packet count (shows if data received)

### 3. Watch for MeshCore Packets
```bash
journalctl -u meshtastic-bot -f | grep "\[MC\]"
```

**Expected:** Lines with `[DEBUG][MC]` prefix when MeshCore data arrives.

### 4. Check Raw Data Reception
```bash
journalctl -u meshtastic-bot -f | grep "MESHCORE-RAW"
```

**Expected:** Hex dumps of actual serial data when radio sends data.

## Troubleshooting

### No Diagnostics Banner
**Problem:** Startup diagnostics not appearing

**Cause:** MeshCore interface not being created

**Check:**
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep "MODE DUAL"
```

Should see: `🔄 MODE DUAL: Connexion simultanée Meshtastic + MeshCore`

### Heartbeat Shows 0 Data Packets
**Problem:** Thread running but no data received

**Possible causes:**
1. **Wrong port** - Check config: `MESHCORE_SERIAL_PORT`
2. **Radio not connected** - Check USB: `ls -la /dev/ttyUSB*`
3. **Radio not in companion mode** - Check radio firmware mode
4. **No mesh activity** - Wait for network traffic
5. **Permissions** - Check: `groups dietpi` (should include dialout)

**Verify port:**
```bash
ls -la /dev/ttyUSB*
# Expected: /dev/ttyUSB0 or similar
```

**Check permissions:**
```bash
sudo usermod -a -G dialout dietpi
sudo reboot
```

### Thread Not Confirmed Running
**Problem:** Thread start attempted but not running

**Cause:** Exception in thread startup

**Check:**
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep "ERROR\|Exception"
```

## Configuration Requirements

For MeshCore to work:

**config.py:**
```python
DUAL_NETWORK_MODE = True          # REQUIRED
MESHTASTIC_ENABLED = True         # REQUIRED
MESHCORE_ENABLED = True           # REQUIRED
SERIAL_PORT = "/dev/ttyACM0"      # Meshtastic radio
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore radio (DIFFERENT port!)
```

**Hardware:**
- Two separate radios (one Meshtastic, one MeshCore)
- Connected to different USB ports
- MeshCore radio must be in companion mode

## Summary of Changes

**meshcore_serial_interface.py:**
- Added startup diagnostics banner
- Added thread confirmation
- Added loop iteration/packet counters
- Added periodic heartbeat logging
- Added hex data dumps
- Enhanced logging throughout

**traffic_monitor.py:**
- Fixed packet logging to use `debug_print_mc()` for MeshCore
- Dynamic function selection based on source
- Consistent [MC] vs [MT] tagging

**Impact:**
- Clear visibility into MeshCore operation
- Easy diagnosis of connection issues
- Proper packet logging with correct tags
- No more confusion about which network packets came from

## Next Steps

After deployment, user should:

1. **Verify threads start** - Check diagnostics banner
2. **Monitor heartbeat** - Ensure thread running
3. **Check for data** - Look for MESHCORE-RAW logs
4. **If no data:**
   - Verify correct serial port
   - Check hardware connections
   - Confirm radio in companion mode
   - Test with known good radio

---

**Status:** Ready for deployment and testing
