# MeshCore Packet Troubleshooting Guide

## Problem
Despite all fixes, user reports: "still not a single packet displayed in the log despite a significant local traffic"

This guide helps identify WHY packets are not appearing.

## Diagnostic Logging Added

Comprehensive logging has been added at every critical point in the packet flow. These logs use `info_print()` so they're ALWAYS visible (not just in DEBUG mode).

## Step-by-Step Troubleshooting

### Step 1: Verify MeshCore Connection

Look for this in your logs:
```
✅ Connexion MeshCore établie
✅ Callback MeshCore configuré: <bound method>
   Interface type: MeshCoreSerialInterface (or MeshCoreCLIWrapper)
   Callback set to: on_message method
```

**If you DON'T see this:**
- MeshCore connection failed
- Check MESHCORE_ENABLED = True in config.py
- Check MESHCORE_SERIAL_PORT is correct
- Check serial device permissions

**If you DO see this:** Continue to Step 2

### Step 2: Check if Messages Are Being Received

#### For Serial Interface (MeshCoreSerialInterface)

Look for:
```
📨 [MESHCORE-TEXT] Reçu: <message content>
```

**If you DON'T see this:**
- **PROBLEM**: No data coming from serial port
- **SOLUTIONS**:
  1. Check if MeshCore device is actually sending data
  2. Verify correct serial port (ls -l /dev/tty*)
  3. Check baud rate matches (default: 115200)
  4. Test serial connection: `cat /dev/ttyUSB0` (should show output)
  5. Check if device is powered on and transmitting

**If you DO see this:** Continue to Step 3

#### For CLI Wrapper (MeshCoreCLIWrapper)

Look for:
```
🔔🔔🔔 [MESHCORE-CLI] _on_contact_message CALLED! Event received!
```

**If you DON'T see this:**
- **PROBLEM**: meshcore-cli events not firing
- **SOLUTIONS**:
  1. Check if meshcore-cli is properly installed: `pip list | grep meshcore`
  2. Verify event subscription succeeded: Look for "✅ Souscription aux messages DM"
  3. Check if meshcore-cli is in companion mode (needs mobile app pairing)
  4. Verify meshcore-cli has contacts: Run `sync_contacts()` manually
  5. Check meshcore-cli logs for errors

**If you DO see this:** Continue to Step 3

### Step 3: Check if Line/Event Is Being Processed

Look for:
```
🔍 [MESHCORE-SERIAL] _process_meshcore_line CALLED with: <line>
```

**If you DON'T see this after Step 2:**
- **PROBLEM**: Received data but not processed
- **SOLUTIONS**:
  1. Check message format - serial interface expects "DM:<sender_id>:<message>"
  2. If format is different, need to update _process_meshcore_line()
  3. Check if exception is being thrown (look for ERROR messages)

**If you DO see this:** Continue to Step 4

### Step 4: Check if Message Format Is Recognized

For serial interface, look for either:
```
📬 [MESHCORE-DM] De: 0x12345678 | Message: <text>
```

OR:
```
⚠️ [MESHCORE] Ligne non reconnue: <line>
```

**If you see "Ligne non reconnue":**
- **PROBLEM**: Message format doesn't match expected "DM:" format
- **SOLUTION**: Need to update _process_meshcore_line() to handle actual format
- **ACTION**: Share the full line content so we can update the parser

**If you see the DM message:** Continue to Step 5

### Step 5: Check if Callback Is Being Called

Look for:
```
📞 [MESHCORE-TEXT] Calling message_callback for message from 0x12345678
```
OR:
```
📞 [MESHCORE-CLI] Calling message_callback for message from 0x12345678
```

**If you DON'T see this:**
- **PROBLEM**: Callback not set or lost
- **SOLUTION**: Check earlier logs for callback setup (Step 1)

**If you DO see this:** Continue to Step 6

### Step 6: Check if on_message Is Reached

Look for:
```
🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
```

**If you DON'T see this:**
- **PROBLEM**: Exception in callback or callback lost
- **SOLUTION**: Look for "Erreur on_message" or "❌" error messages

**If you DO see this:** Continue to Step 7

### Step 7: Check if Callback Completes

Look for:
```
✅ [MESHCORE-TEXT] Callback completed successfully
```
OR:
```
✅ [MESHCORE-CLI] Callback completed successfully
```

**If you DON'T see this:**
- **PROBLEM**: Exception in on_message processing
- **SOLUTION**: Look for "Erreur on_message" error message with traceback

**If you DO see this:** Continue to Step 8

### Step 8: Check if Packet Reaches Traffic Monitor

Look for:
```
📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de <name>
```

**If you DON'T see this:**
- **PROBLEM**: Packet filtered or exception in traffic_monitor
- **POSSIBLE CAUSES**:
  1. Source not set to 'meshcore' (check source determination)
  2. Packet missing required fields
  3. Exception in add_packet()
- **SOLUTION**: Check for error messages in logs

**If you DO see this:** Continue to Step 9

### Step 9: Check for Comprehensive DEBUG Output

If DEBUG_MODE = True, you should see:
```
╔═══════════════════════════════════════════════════════════════
║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
╠═══════════════════════════════════════════════════════════════
║ Packet ID: 865992
║ RX Time:   20:07:06 (1769630826)
╟───────────────────────────────────────────────────────────────
...
```

**If you DON'T see this:**
- Check DEBUG_MODE = True in config.py
- Check if running with --debug flag

## Common Issues and Solutions

### Issue 1: No messages received at all
**Symptom**: No "📨 Reçu" logs
**Cause**: MeshCore device not sending, wrong serial port, or no data
**Fix**: 
- Test with `cat /dev/ttyUSB0` to see raw data
- Check device is powered and transmitting
- Verify serial port in config

### Issue 2: Messages received but format not recognized
**Symptom**: "⚠️ Ligne non reconnue" appears
**Cause**: Message format doesn't match "DM:" format
**Fix**: 
- Share actual message format in logs
- Update _process_meshcore_line() to parse actual format
- May need to handle different message types (channel messages, etc.)

### Issue 3: CLI events not firing
**Symptom**: No "🔔🔔🔔 _on_contact_message CALLED"
**Cause**: meshcore-cli not properly configured
**Fix**:
- Ensure companion mode is active
- Pair with mobile app
- Run sync_contacts() to populate contact database
- Check meshcore-cli has valid private key

### Issue 4: Callback completes but no packet logged
**Symptom**: "✅ Callback completed" but no "📊 Paquet enregistré"
**Cause**: Source not 'meshcore' or packet filtered
**Fix**:
- Verify source determination logging shows source='meshcore'
- Check packet has all required fields (id, rxTime, etc.)
- Look for exceptions in traffic_monitor

## Collecting Diagnostic Information

To help diagnose the issue, collect these logs:

```bash
# Run bot with full logging
sudo systemctl stop meshbot
python3 main_script.py --debug

# Or view systemd logs
journalctl -u meshbot -f --since "5 minutes ago"

# Filter for MeshCore messages
journalctl -u meshbot | grep -E "MESHCORE|🔔|📨|📞|📊"
```

Look for the pattern from Steps 1-9 above and identify where it stops.

## Example Successful Flow

```
[INFO] ✅ Connexion MeshCore établie
[INFO] 📝 [MESHCORE-SERIAL] Setting message_callback to <bound method>
[INFO] ✅ [MESHCORE-SERIAL] message_callback set successfully
[INFO] 📨 [MESHCORE-TEXT] Reçu: DM:12345678:Hello bot
[INFO] 🔍 [MESHCORE-SERIAL] _process_meshcore_line CALLED with: DM:12345678:Hello bot
[INFO] 📬 [MESHCORE-DM] De: 0x12345678 | Message: Hello bot
[INFO] 📞 [MESHCORE-TEXT] Calling message_callback for message from 0x12345678
[INFO] 🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
[DEBUG] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de NodeName
[DEBUG] 📦 TEXT_MESSAGE_APP de NodeName 45678 [direct] (SNR:n/a)
[DEBUG] ╔═══════════════════════════════════════════════════════════════
[DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
...
[INFO] ✅ [MESHCORE-TEXT] Callback completed successfully
```

## Conclusion

The diagnostic logging allows us to pinpoint EXACTLY where packets are being lost:
- If stopping at Step 2: No data from device
- If stopping at Step 4: Format mismatch
- If stopping at Step 6: Callback issue
- If stopping at Step 8: Traffic monitor issue

Share the logs showing which step you reach, and we can provide targeted fixes.
