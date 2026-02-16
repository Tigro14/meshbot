# Diagnostic: Packet Reception Issues

## Quick Start

If you're not seeing packet logs (mc/mt) in debug mode:

```bash
python3 diagnose_packet_reception.py
```

This script will check:
- Configuration settings
- Serial port status
- Interface subscription
- Recent log analysis
- Common issues

## When to Use

Run this diagnostic if you see:
- No "[DEBUG][MC]" or "[DEBUG][MT]" logs
- No "📦" packet indicators
- No "📡" RF activity logs
- Bot running but silent on packets

## What It Checks

### 1. Configuration
- DEBUG_MODE status
- MESHTASTIC_ENABLED / MESHCORE_ENABLED
- CONNECTION_MODE (serial/tcp)
- MESHCORE_RX_LOG_ENABLED
- Serial port configuration

### 2. Hardware
- Serial port existence
- Port accessibility
- Port lock status
- USB device enumeration

### 3. Bot Status
- Process running check
- Recent log analysis
- Subscription status
- Error/warning detection

### 4. Common Issues
- DEBUG_MODE = False
- Serial port locked
- Device disconnected
- No mesh activity
- RX_LOG disabled

## Expected Output

The script will show:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MESHBOT PACKET RECEPTION DIAGNOSTIC                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

====================================================================================
CONFIGURATION CHECK
====================================================================================
DEBUG_MODE: True
DUAL_NETWORK_MODE: False
MESHTASTIC_ENABLED: True
MESHCORE_ENABLED: False
  → Mode: MESHTASTIC (serial)
     Serial port: /dev/ttyACM0

====================================================================================
SERIAL PORT CHECK
====================================================================================
Available serial ports:
crw-rw---- 1 root dialout 166, 0 Feb  3 22:00 /dev/ttyACM0
  ✅ /dev/ttyACM0 is available

====================================================================================
INTERFACE STATUS CHECK
====================================================================================
✅ Bot is running (PIDs: 18158)

====================================================================================
RECENT LOG CHECK (last 50 lines)
====================================================================================
Looking for key indicators:
  ✅ Meshtastic subscription: 1 occurrences
  ❌ MeshCore RX_LOG subscription: 0 occurrences
  ❌ Message reception: 0 occurrences
  ❌ Packet processing: 0 occurrences
  ❌ Packet logs (debug): 0 occurrences
  ⚠️ Warnings: 1 occurrences

Recent errors and warnings:
  [INFO] ⚠️ Interface doesn't have nodes attribute

====================================================================================
DIAGNOSTIC SUMMARY
====================================================================================

If you see NO packet logs (📦, 📡), check:
  1. DEBUG_MODE = True in config.py
  2. Interface is connected (✅ Abonné/Souscription messages)
  3. Serial port is accessible and not in use
  4. Device is powered on and transmitting
  5. If MeshCore: MESHCORE_RX_LOG_ENABLED = True
```

## Common Fixes

### Fix 1: DEBUG_MODE Disabled

If diagnostic shows `DEBUG_MODE: False`:

```bash
# Edit config
nano config.py

# Change to:
DEBUG_MODE = True

# Restart bot
sudo systemctl restart meshtastic-bot
```

### Fix 2: Port Locked

If diagnostic shows port is locked:

```bash
# Find what's using the port
sudo lsof /dev/ttyACM0

# Kill the process (replace PID)
sudo kill <PID>

# Restart bot
sudo systemctl restart meshtastic-bot
```

### Fix 3: Device Disconnected

If diagnostic shows port doesn't exist:

```bash
# List available ports
ls -la /dev/tty*

# Update config with correct port
nano config.py

# Restart bot
sudo systemctl restart meshtastic-bot
```

### Fix 4: No Mesh Activity

If all checks pass but no packets:

This is NORMAL if no other nodes are transmitting in range.

**Solution**: 
- Power on more nodes nearby
- Send test messages from another device
- Move bot closer to mesh network
- Wait for natural mesh activity

## Advanced Troubleshooting

For detailed steps, see:
- `TROUBLESHOOT_NO_PACKETS.md` - Complete troubleshooting guide
- `README.md` - General bot documentation
- `CLAUDE.md` - Developer documentation

## Manual Checks

### Test Meshtastic Device

```bash
# Check device info
meshtastic --port /dev/ttyACM0 --info

# Monitor RF activity
meshtastic --port /dev/ttyACM0 --listen
```

If packets appear in `--listen`, the device works. 
If bot still doesn't log packets, it's a software issue.

### Test MeshCore Device

```bash
# Monitor MeshCore
python3 meshcore-serial-monitor.py /dev/ttyUSB0
```

Watch for packet reception.

### Check Logs Manually

```bash
# Watch live logs
journalctl -u meshtastic-bot -f

# Filter for packets
journalctl -u meshtastic-bot -f | grep -E "📦|📡|🔔|🔵"

# Check startup logs
journalctl -u meshtastic-bot --since '10 minutes ago' | grep -E "✅|❌|⚠️"
```

## Need Help?

If diagnostic doesn't solve your issue:

1. Run diagnostic and save output:
   ```bash
   python3 diagnose_packet_reception.py > diagnostic.txt
   ```

2. Collect recent logs:
   ```bash
   journalctl -u meshtastic-bot --since '1 hour ago' > recent_logs.txt
   ```

3. Check device info:
   ```bash
   meshtastic --port /dev/ttyACM0 --info > device_info.txt
   ```

4. Share files on Discord or GitHub issues

## Related Tools

- `diagnose_packet_reception.py` - This diagnostic script
- `TROUBLESHOOT_NO_PACKETS.md` - Detailed troubleshooting
- `diagnostic_traffic.py` - Traffic analysis
- `view_traffic_db.py` - Database viewer
- `browse_traffic_db.py` - Web-based database browser

## Preventive Measures

To avoid packet reception issues:

1. **Always enable DEBUG_MODE during setup**
2. **Monitor logs regularly for RF activity**
3. **Verify hardware connections monthly**
4. **Keep at least 2-3 active nodes in range**
5. **Test with `meshtastic --listen` periodically**

## Success Indicators

After fixing, you should see:

**Startup logs:**
```
[INFO] ✅ Interface série créée
[INFO] ✅ Abonné aux messages Meshtastic (receive)
```

**Runtime logs:**
```
[DEBUG][MT] 📦 POSITION_APP de Node1 ad3dc [direct] (SNR:12.0dB)
[DEBUG][MT] 📦 TELEMETRY_APP de Node2 f547f [via relay ×1] (SNR:8.5dB)
[INFO] 📥 10 paquets reçus dans add_packet()
```

**Activity counters:**
```
[INFO] 💾 25 paquets enregistrés dans all_packets (size: 25)
[INFO] 📊 Nettoyage : 0 paquets, 0 messages expirés
```

## FAQ

**Q: Bot runs but no packet logs appear**  
A: Most likely no RF activity in range. Run diagnostic to verify.

**Q: Diagnostic shows DEBUG_MODE=False**  
A: Edit config.py, set DEBUG_MODE=True, restart bot.

**Q: Port shows as locked**  
A: Another process is using the port. Use `sudo lsof` to find and kill it.

**Q: All checks pass but still no packets**  
A: No mesh network activity in range. Add more active nodes nearby.

**Q: Packets visible in `meshtastic --listen` but not in bot**  
A: Software issue. Check pubsub subscription in logs.

**Q: MeshCore shows "RX_LOG désactivé"**  
A: Set MESHCORE_RX_LOG_ENABLED=True in config.py.
