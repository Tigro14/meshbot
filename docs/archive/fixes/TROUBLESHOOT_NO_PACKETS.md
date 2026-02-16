# Troubleshooting: No Packet Logs Appearing (mc/mt)

## Symptom

Bot is running but NO packet logs appear in debug mode:
- No "[DEBUG][MC]" logs (MeshCore packets)
- No "[DEBUG][MT]" logs (Meshtastic packets)  
- No "📦" packet indicators
- No "📡" RF packet logs

## Root Cause Analysis

Based on log analysis, the issue is **NO RF PACKETS are being received** by the bot's radio interface.

### Evidence from Logs

```
Feb 03 22:24:33 DietPi meshtastic-bot[18158]: [DEBUG] 🔄 Mise à jour périodique...
Feb 03 22:25:35 DietPi meshtastic-bot[18158]: INFO:httpx:HTTP Request: POST https://api.telegram.org/...
Feb 03 22:38:33 DietPi meshtastic-bot[18158]: [INFO] ⚠️ Interface doesn't have nodes attribute
```

**What's MISSING:**
- No "🔔 on_message CALLED" logs
- No "🔵 add_packet ENTRY" logs  
- No "📦" packet reception logs
- No "📡 [RX_LOG]" MeshCore logs

This indicates the interface is connected but **receiving ZERO packets from the mesh network**.

## Diagnostic Steps

### 1. Check Configuration Mode

Run the diagnostic script:
```bash
python3 diagnose_packet_reception.py
```

This will show:
- Current mode (Meshtastic/MeshCore/Dual)
- DEBUG_MODE status
- Interface subscription status
- Recent log analysis

### 2. Verify DEBUG_MODE is Enabled

Check `config.py`:
```python
DEBUG_MODE = True  # MUST be True to see packet logs
```

If False, set to True and restart:
```bash
sudo systemctl restart meshtastic-bot
```

### 3. Check Interface Connection

Look for startup messages in logs:
```bash
journalctl -u meshtastic-bot --since '10 minutes ago' | grep -E "✅|❌|⚠️"
```

**Expected Meshtastic messages:**
```
[INFO] ✅ Interface série créée
[INFO] ✅ Abonné aux messages Meshtastic (receive)
```

**Expected MeshCore messages:**
```
[INFO][MC] ✅ Device connecté sur /dev/ttyUSB0
[INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
[INFO][MC] ✅ Thread événements démarré
```

### 4. Check Hardware Connection

#### For Serial Connection (CONNECTION_MODE='serial')

Check device is connected:
```bash
ls -la /dev/ttyACM* /dev/ttyUSB*
```

Check if port is locked:
```bash
sudo lsof /dev/ttyACM0
```

Check USB connection:
```bash
dmesg | tail -20 | grep tty
```

#### For TCP Connection (CONNECTION_MODE='tcp')

Test connectivity:
```bash
ping 192.168.1.38  # Replace with your TCP_HOST
```

Test port:
```bash
nc -zv 192.168.1.38 4403  # Replace with TCP_HOST:TCP_PORT
```

### 5. Check Radio is Receiving

**Important**: The bot can only log packets that the radio receives.

#### Meshtastic Device Check

Connect to device directly:
```bash
meshtastic --port /dev/ttyACM0 --info
```

Monitor RF activity:
```bash
meshtastic --port /dev/ttyACM0 --listen
```

If you see packets here but NOT in bot logs, it's a software issue.
If you see NO packets here, it's a hardware/RF issue.

#### MeshCore Device Check

Use the monitoring script:
```bash
python3 meshcore-serial-monitor.py /dev/ttyUSB0
```

Watch for packet reception. If no packets appear, check:
- Device is powered on
- Antenna is connected
- Device firmware is recent
- Device is in RF range of other nodes

### 6. Check Mesh Network Activity

**Critical**: If there are NO OTHER NODES transmitting in range, the bot will receive ZERO packets.

Verify mesh network is active:
- Check other nodes are powered on
- Check nodes are in RF range (< 2-5 km typical)
- Check nodes are on same frequency/channel
- Check nodes are actively transmitting (telemetry, messages, etc.)

## Common Causes

### 1. No Mesh Activity in Range

**Symptom**: Bot runs fine, but no packets appear  
**Cause**: No other nodes are transmitting in RF range  
**Solution**: 
- Move bot closer to mesh network
- Add more active nodes
- Send test messages from another node

### 2. DEBUG_MODE Disabled

**Symptom**: Bot works, commands work, but no debug logs  
**Cause**: `DEBUG_MODE = False` in config  
**Solution**: Set `DEBUG_MODE = True` and restart

### 3. RX_LOG Disabled (MeshCore only)

**Symptom**: DMs work, but no broadcast/telemetry logs  
**Cause**: `MESHCORE_RX_LOG_ENABLED = False`  
**Solution**: Set `MESHCORE_RX_LOG_ENABLED = True` and restart

### 4. Hardware Disconnected

**Symptom**: Bot starts, but no interface messages  
**Cause**: Radio device unplugged or powered off  
**Solution**: 
- Check USB cable
- Check power supply
- Check device LED indicators

### 5. Wrong Serial Port

**Symptom**: Bot starts, but "Port not found" errors  
**Cause**: Device on different port than configured  
**Solution**: 
- Run `ls -la /dev/tty*` to find correct port
- Update `SERIAL_PORT` or `MESHCORE_SERIAL_PORT` in config.py

## Expected Log Output

### Normal Meshtastic Packet Reception

With DEBUG_MODE=True, you should see:
```
[DEBUG][MT] 📦 TEXT_MESSAGE_APP de Node1 ad3dc [direct] (SNR:12.0dB)
[DEBUG][MT] 🌐 LOCAL TEXTMESSAGE from Node1 (ad3dc) | Hops:0/3 | SNR:12.0dB(🟢) | RSSI:-45dBm | Ch:0
[DEBUG][MT]   └─ ID:2f39d8a2 | RX:14:23:45 | Size:42B | Msg:"Hello mesh"
```

### Normal MeshCore Packet Reception

With DEBUG_MODE=True and MESHCORE_RX_LOG_ENABLED=True:
```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662...
[DEBUG][MC] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hops: 0 | Status: ✅
```

### No Packets (Current Issue)

What you're seeing now (ABNORMAL):
```
[DEBUG] 🔄 Mise à jour périodique...
[DEBUG] ✅ Mise à jour périodique terminée
INFO:httpx:HTTP Request: POST https://api.telegram.org/...
```

**Missing**: Any packet reception logs.

## Solution Steps

### Quick Fix (If DEBUG_MODE was False)

1. Edit config.py:
   ```bash
   nano config.py
   ```

2. Set DEBUG_MODE:
   ```python
   DEBUG_MODE = True
   ```

3. Restart bot:
   ```bash
   sudo systemctl restart meshtastic-bot
   ```

4. Watch logs:
   ```bash
   journalctl -u meshtastic-bot -f
   ```

### Hardware Fix (If No RF Activity)

1. Check physical connection:
   ```bash
   ls -la /dev/ttyACM* /dev/ttyUSB*
   ```

2. Test device directly:
   ```bash
   meshtastic --port /dev/ttyACM0 --info
   meshtastic --port /dev/ttyACM0 --listen
   ```

3. If no packets appear in `--listen`, check:
   - Device antenna connected
   - Device powered on (LED indicators)
   - Other nodes in range and transmitting
   - Correct frequency/region setting

4. Restart device:
   ```bash
   # Unplug and replug USB cable
   # Or reboot device via Meshtastic app
   ```

### Mesh Network Fix (If No Other Nodes)

If you're the only node or others are powered off:

1. Power on additional nodes in range

2. Generate test traffic from another node:
   ```bash
   meshtastic --port /dev/ttyACM1 --sendtext "Test message"
   ```

3. Verify packets appear in bot logs

## Verification

After fixing, you should see:

1. **Startup logs show subscription:**
   ```
   [INFO] ✅ Abonné aux messages Meshtastic (receive)
   ```
   OR (for MeshCore):
   ```
   [INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
   ```

2. **Debug logs show packets:**
   ```
   [DEBUG][MT] 📦 POSITION_APP de Node1...
   [DEBUG][MT] 📦 TELEMETRY_APP de Node2...
   [DEBUG][MT] 📦 TEXT_MESSAGE_APP de Node3...
   ```

3. **Activity counter increases:**
   ```
   [INFO] 📥 10 paquets reçus dans add_packet()
   [INFO] 💾 25 paquets enregistrés dans all_packets
   ```

## Still Not Working?

If packets still don't appear after these steps:

1. **Run full diagnostic:**
   ```bash
   python3 diagnose_packet_reception.py > diagnostic.txt
   ```

2. **Collect logs:**
   ```bash
   journalctl -u meshtastic-bot --since '1 hour ago' > recent_logs.txt
   ```

3. **Check device logs:**
   ```bash
   meshtastic --port /dev/ttyACM0 --info > device_info.txt
   ```

4. **Share diagnostic files** with support or on Discord/GitHub

## Related Files

- `config.py` - Bot configuration
- `traffic_monitor.py` - Packet logging logic
- `main_bot.py` - Interface subscription
- `meshcore_cli_wrapper.py` - MeshCore RX_LOG subscription
- `utils.py` - Logging functions (debug_print_mt, debug_print_mc)
- `diagnose_packet_reception.py` - Diagnostic script (NEW)

## Prevention

To avoid this issue in the future:

1. **Always enable DEBUG_MODE during setup:**
   ```python
   DEBUG_MODE = True  # Essential for troubleshooting
   ```

2. **Monitor logs regularly:**
   ```bash
   journalctl -u meshtastic-bot -f | grep -E "📦|📡|❌|⚠️"
   ```

3. **Check mesh activity:**
   - Ensure at least 2-3 active nodes in range
   - Verify nodes transmit periodically (telemetry, etc.)

4. **Hardware checks:**
   - Verify antenna connections
   - Check power supply stability
   - Monitor USB connection reliability

## Summary

**The issue is NOT a software bug** - the bot is working correctly.

The issue is **NO RF PACKETS are being received** by the radio interface.

**Most likely cause**: No mesh network activity in radio range.

**Solution**: 
1. Verify DEBUG_MODE = True
2. Check hardware connection
3. Ensure other nodes are active and in range
4. Monitor RF activity with `meshtastic --listen`
