# MeshCore Logging Fix - Critical Logs Now Always Visible

## Problem Resolved

**Issue**: "no, the meshcore packet traffic still does not show in the debug log"

**Root Cause**: All packet logging used `debug_print()` which requires `DEBUG_MODE=True`. With `DEBUG_MODE=False`, NO logs appeared at all.

**Solution**: Changed critical logs to use `info_print()` so they're **ALWAYS visible**, regardless of DEBUG_MODE setting.

---

## What Changed

### Before This Fix
```python
# traffic_monitor.py - line 909
debug_print(f"📊 Paquet enregistré...")  # ❌ Only visible with DEBUG_MODE=True

# meshcore_serial_interface.py - line 141
debug_print(f"📨 [MESHCORE-TEXT] Reçu...")  # ❌ Only visible with DEBUG_MODE=True
```

**Result**: With `DEBUG_MODE=False`, you saw **NOTHING** in logs.

### After This Fix
```python
# traffic_monitor.py - line 909
info_print(f"📊 Paquet enregistré...")  # ✅ ALWAYS visible

# traffic_monitor.py - line 946 (NEW)
info_print(f"📦 {packet_type} de {sender_name}...")  # ✅ ALWAYS visible

# meshcore_serial_interface.py - line 141
info_print(f"📨 [MESHCORE-TEXT] Reçu...")  # ✅ ALWAYS visible
```

**Result**: With `DEBUG_MODE=False`, you now see **ALL critical packet logs**.

---

## Two-Tier Logging Architecture

### Tier 1: Critical Logs (info_print - ALWAYS visible)

These logs appear **regardless of DEBUG_MODE**:

1. **Message Reception** (serial interface)
   ```
   [INFO] 📨 [MESHCORE-TEXT] Reçu: DM:12345678:Hello bot
   [INFO] 📨 [MESHCORE-BINARY] Reçu: 256 octets (protocole binaire MeshCore)
   ```

2. **Message Processing** (serial interface)
   ```
   [INFO] 🔍 [MESHCORE-SERIAL] _process_meshcore_line CALLED with: DM:12345678:Hello
   [INFO] 📬 [MESHCORE-DM] De: 0x12345678 | Message: Hello bot
   ```

3. **Callback Chain** (both interfaces)
   ```
   [INFO] 📞 [MESHCORE-TEXT] Calling message_callback for message from 0x12345678
   [INFO] ✅ [MESHCORE-TEXT] Callback completed successfully
   ```
   OR for CLI wrapper:
   ```
   [INFO] 🔔🔔🔔 [MESHCORE-CLI] _on_contact_message CALLED! Event received!
   [INFO] 📞 [MESHCORE-CLI] Calling message_callback for message from 0x12345678
   [INFO] ✅ [MESHCORE-CLI] Callback completed successfully
   ```

4. **main_bot.py on_message** (entry point)
   ```
   [INFO] 🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
   ```

5. **Traffic Monitor** (packet saved)
   ```
   [INFO] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de NodeName
   [INFO] 📦 TEXT_MESSAGE_APP de NodeName 45678 [direct] (SNR:n/a)
   ```

### Tier 2: Detailed Debug (debug_print - DEBUG_MODE=True only)

These logs appear **ONLY when DEBUG_MODE=True**:

1. **Comprehensive Packet Debug**
   ```
   [DEBUG] ╔═══════════════════════════════════════════════════════════════
   [DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
   [DEBUG] ╠═══════════════════════════════════════════════════════════════
   [DEBUG] ║ Packet ID: 865992
   [DEBUG] ║ RX Time:   14:23:45 (1769645025)
   [DEBUG] ╟───────────────────────────────────────────────────────────────
   [DEBUG] ║ 🔀 ROUTING
   [DEBUG] ║   From:      NodeName (0x12345678)
   [DEBUG] ║   To:        0x87654321
   [DEBUG] ║   Hops:      0/0 (limit: 0)
   [DEBUG] ╟───────────────────────────────────────────────────────────────
   [DEBUG] ║ 📋 PACKET METADATA
   [DEBUG] ║   Family:    DIRECT (unicast)
   [DEBUG] ║   Channel:   0 (Primary)
   [DEBUG] ║   Priority:  DEFAULT (0)
   [DEBUG] ║   Via MQTT:  No
   [DEBUG] ║   Want ACK:  No
   [DEBUG] ║   Want Resp: No
   [DEBUG] ║   PublicKey: Not available
   [DEBUG] ╟───────────────────────────────────────────────────────────────
   [DEBUG] ║ 📡 RADIO METRICS
   [DEBUG] ║   RSSI:      0 dBm
   [DEBUG] ║   SNR:       0.0 dB (🟠 Fair)
   [DEBUG] ╟───────────────────────────────────────────────────────────────
   [DEBUG] ║ 📄 DECODED CONTENT
   [DEBUG] ║   Message:   "Hello bot"
   [DEBUG] ╚═══════════════════════════════════════════════════════════════
   ```

---

## How to Verify MeshCore Packets Are Now Visible

### Step 1: Check Your Configuration

```python
# config.py
DEBUG_MODE = False  # Can be False now!
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # Your MeshCore device
```

### Step 2: Run the Bot

```bash
# Stop existing bot
sudo systemctl stop meshbot

# Run manually to see logs
python3 main_script.py

# OR view systemd logs
sudo systemctl start meshbot
journalctl -u meshbot -f
```

### Step 3: Send Test Message

From your MeshCore device, send a message to the bot.

### Step 4: Check Logs

You should now see (even with DEBUG_MODE=False):

```
[INFO] ✅ Connexion MeshCore établie
[INFO] 📝 [MESHCORE-SERIAL] Setting message_callback to <method>
[INFO] ✅ [MESHCORE-SERIAL] message_callback set successfully

... when message arrives ...

[INFO] 📨 [MESHCORE-TEXT] Reçu: DM:12345678:Test message
[INFO] 🔍 [MESHCORE-SERIAL] _process_meshcore_line CALLED with: DM:12345678:Test
[INFO] 📬 [MESHCORE-DM] De: 0x12345678 | Message: Test message
[INFO] 📞 [MESHCORE-TEXT] Calling message_callback for message from 0x12345678
[INFO] 🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
[INFO] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de NodeName
[INFO] 📦 TEXT_MESSAGE_APP de NodeName 45678 [direct] (SNR:n/a)
[INFO] ✅ [MESHCORE-TEXT] Callback completed successfully
```

### Step 5: Enable DEBUG_MODE for Details (Optional)

If you want the comprehensive packet debug (╔═══ box display):

```python
# config.py
DEBUG_MODE = True  # Enable comprehensive debug
```

Then you'll see BOTH tiers of logging.

---

## Filtering Logs

### View All MeshCore Activity
```bash
journalctl -u meshbot -f | grep -E "MESHCORE|meshcore"
```

### View Just Packet Reception
```bash
journalctl -u meshbot -f | grep "📨"
```

### View Just Saved Packets
```bash
journalctl -u meshbot -f | grep "📊"
```

### View Complete Packet Flow
```bash
journalctl -u meshbot -f | grep -E "📨|🔍|📞|🔔|📊|📦|✅"
```

---

## Troubleshooting

### Issue: Still No Logs Appearing

**Check 1: Is MeshCore connection established?**
Look for:
```
[INFO] ✅ Connexion MeshCore établie
[INFO] 📝 [MESHCORE-SERIAL] Setting message_callback to <method>
```

If NOT present:
- Check `MESHCORE_ENABLED = True` in config.py
- Check `MESHCORE_SERIAL_PORT` is correct
- Verify device permissions: `ls -l /dev/ttyUSB0`
- Check device is connected: `lsusb` or `dmesg | tail`

**Check 2: Are messages being received?**
Look for:
```
[INFO] 📨 [MESHCORE-TEXT] Reçu: <message>
```

If NOT present:
- MeshCore device is not sending data
- Wrong serial port
- Wrong baud rate
- Test with: `cat /dev/ttyUSB0` (should show output)

**Check 3: Is message format recognized?**
Look for:
```
[INFO] 📬 [MESHCORE-DM] De: 0x... | Message: ...
```

If you see:
```
[INFO] ⚠️ [MESHCORE] Ligne non reconnue: <line>
```

Then:
- Message format doesn't match expected "DM:<hex_id>:<message>"
- Need to update `_process_meshcore_line()` parser
- Share the unrecognized line format for parser update

**Check 4: Is callback being called?**
Look for:
```
[INFO] 📞 [MESHCORE-TEXT] Calling message_callback
```

If NOT present:
- Callback was never set
- Check Step 1 logs for callback setup

**Check 5: Does on_message receive packet?**
Look for:
```
[INFO] 🔔 on_message CALLED | from=0x...
```

If NOT present:
- Exception in callback
- Look for error messages

---

## Summary

**✅ FIXED**: MeshCore packets now appear in logs **WITHOUT requiring DEBUG_MODE**.

**Key Changes:**
1. Critical logs use `info_print()` → ALWAYS visible
2. Detailed debug uses `debug_print()` → DEBUG_MODE only
3. Two-tier architecture for production vs development

**User Experience:**
- Production: See essential packet info without spam
- Development: Enable DEBUG_MODE for comprehensive details

**Verification:**
- Run test: `python3 test_info_print_logging.py`
- Check logs: `journalctl -u meshbot -f | grep "📊"`
- Send message: Should see packet flow immediately

---

## Related Files

- `traffic_monitor.py` - Packet logging (lines 909, 946)
- `meshcore_serial_interface.py` - Message reception (lines 141, 145)
- `test_info_print_logging.py` - Test suite (NEW)
- `MESHCORE_TROUBLESHOOTING.md` - Complete diagnostic guide

---

**If you still don't see packets after this fix, follow the troubleshooting steps above and share the logs showing which step fails.**
