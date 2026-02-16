# MeshCore Connection Verification - Visual Guide

## Problem Statement
**"i do not see any Meshcore activity in the log, how could we be sure a meshcore companion is well connected to the serial port?"**

## Solution: Enhanced Logging & Status Command

This document shows exactly what logs you'll see when MeshCore is properly connected.

---

## ✅ What You SHOULD See When MeshCore Connects

### 1. Connection Startup Logs

When the bot starts with `MESHCORE_ENABLED = True`, you'll immediately see:

```
[INFO] 🔗 Mode MESHCORE COMPANION: Connexion série /dev/ttyUSB0
[INFO]    → Fonctionnalités disponibles: /bot, /weather, /power, /sys, /help
[INFO]    → Fonctionnalités désactivées: /nodes, /my, /trace, /stats (Meshtastic requis)
[INFO] 🔧 [MESHCORE] Initialisation interface série: /dev/ttyUSB0
[INFO] ✅ [MESHCORE] Connexion série établie: /dev/ttyUSB0
```

### 2. Connection Verification Banner (NEW! ⭐)

Immediately after connection, you'll see a **prominent verification banner**:

```
================================================================================
🔧 [MESHCORE] DÉMARRAGE DIAGNOSTICS
================================================================================
   Port série: /dev/ttyUSB0
   Baudrate: 115200
   Port ouvert: True
   Message callback: True
================================================================================
[INFO] ✅ [MESHCORE] Thread de lecture démarré
[INFO] ✅ [MESHCORE] Thread de polling démarré
[INFO] ✅ [MESHCORE] Read thread confirmed running
[INFO] ✅ [MESHCORE] Poll thread confirmed running

================================================================================
✅ [MESHCORE] CONNECTION VERIFICATION
================================================================================
   Port série: /dev/ttyUSB0
   Baudrate: 115200
   Port ouvert: True
   Read thread: ✅ RUNNING
   Poll thread: ✅ RUNNING
   Callback configuré: ✅ YES

   📊 MONITORING ACTIF:
   → Heartbeat: Toutes les 60 secondes
   → Polling: Toutes les 5 secondes
   → Logs: [MESHCORE-DATA] quand paquets arrivent

   ✅ MeshCore companion prêt à recevoir des messages
================================================================================
```

**What this means:**
- ✅ **Port ouvert: True** → Serial port is accessible
- ✅ **Read thread: RUNNING** → Thread listening for incoming data is active
- ✅ **Poll thread: RUNNING** → Thread requesting messages is active
- ✅ **Callback configuré: YES** → Messages will be processed by the bot

If ANY of these show ❌, the connection is NOT working!

### 3. Heartbeat Logs (Every 60 seconds - NEW! Always Visible ⭐)

Previously, heartbeat logs were only visible in DEBUG mode. Now they're **ALWAYS visible**:

```
[INFO] ✅ [MESHCORE-HEARTBEAT] Connexion active | Iterations: 2400 | Paquets reçus: 15
```

**Status indicators:**
- ✅ = Packets received (connection healthy)
- ⏸️ = No packets received (warning)

If you see:
```
[INFO] ⏸️ [MESHCORE-HEARTBEAT] Connexion active | Iterations: 2400 | Paquets reçus: 0
[INFO]    ⚠️  Aucun paquet reçu depuis 60s - Vérifier radio MeshCore
```

This means the serial port is open but **no data is coming from the MeshCore device**.

### 4. Data Reception Logs

When packets arrive, you'll see:

```
[INFO] 📥 [MESHCORE-DATA] 47 bytes waiting (packet #1)
[INFO] 📦 [MESHCORE-RAW] Read 47 bytes: 3c2f0001...
```

### 5. Message Processing Logs

When actual messages are decoded:

```
[INFO] 📨 [MESHCORE-TEXT] Reçu: DM:12345678:Hello from MeshCore
[INFO] 📬 [MESHCORE-DM] De: 0x12345678 | Message: Hello from MeshCore
[INFO] 📞 [MESHCORE-TEXT] Calling message_callback for message from 0x12345678
[INFO] ✅ [MESHCORE-TEXT] Callback completed successfully
```

---

## 🔍 New `/meshcore` Command (⭐)

Users can now check connection status at any time:

### Command: `/meshcore`

**Response (when connected):**
```
📡 STATUT MESHCORE COMPANION
========================================
Port: /dev/ttyUSB0
Baudrate: 115200
Connecté: ✅
Running: ✅
Read thread: ✅
Poll thread: ✅
Callback: ✅

Type: MeshCoreSerialInterface (basic)

✅ Connexion active
→ Attendre ~60s pour heartbeat
→ Logs: [MESHCORE-HEARTBEAT]
```

**Response (when NOT connected):**
```
⚠️ MeshCore désactivé

📝 Pour activer:
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = '/dev/ttyUSB0'
```

---

## 🔴 What You'll See If Connection FAILS

### Scenario 1: Port Doesn't Exist
```
[ERROR] ❌ [MESHCORE] Erreur connexion série: [Errno 2] could not open port /dev/ttyUSB0
[INFO] ❌ [MESHCORE] Read thread NOT running!
[INFO] ❌ [MESHCORE] Poll thread NOT running!
```

### Scenario 2: Port Already in Use
```
[ERROR] ❌ [MESHCORE] Erreur connexion série: [Errno 11] Could not exclusively lock port /dev/ttyUSB0
```

### Scenario 3: Connection Established But No Data
```
[INFO] ✅ [MESHCORE] Read thread confirmed running
[INFO] ✅ [MESHCORE] Poll thread confirmed running
...
[INFO] ⏸️ [MESHCORE-HEARTBEAT] Connexion active | Iterations: 3600 | Paquets reçus: 0
[INFO]    ⚠️  Aucun paquet reçu depuis 60s - Vérifier radio MeshCore
```

This means:
- ✅ Serial port is open
- ✅ Threads are running
- ❌ MeshCore device is not sending data
- 🔍 Check: Is the radio powered on? Is the firmware running?

---

## 🎯 Quick Diagnosis Checklist

Use this checklist to diagnose MeshCore connection issues:

### ✅ Step 1: Check Startup Logs
- [ ] See `✅ [MESHCORE] Connexion série établie`?
- [ ] See `✅ [MESHCORE] Read thread confirmed running`?
- [ ] See `✅ [MESHCORE] Poll thread confirmed running`?
- [ ] See `CONNECTION VERIFICATION` banner with all ✅?

### ✅ Step 2: Wait 60 Seconds and Check Heartbeat
- [ ] See `[MESHCORE-HEARTBEAT]` log after 60 seconds?
- [ ] Does it show "Paquets reçus: N" with N > 0?

### ✅ Step 3: Send a Test Message
- [ ] Send `/meshcore` command from another node
- [ ] See `📥 [MESHCORE-DATA]` logs?
- [ ] See `📨 [MESHCORE-TEXT]` or `📨 [MESHCORE-BINARY]` logs?

### ✅ Step 4: Use Status Command
- [ ] Send `/meshcore` command
- [ ] Response shows all ✅?

---

## 📚 Help Text Updated

The `/help` command now includes `/meshcore`:

```
📡 RÉSEAU MESHTASTIC
• /nodes - Liste nœuds (auto-détection mode)
• /meshcore - Statut connexion MeshCore
  Vérifier: port, threads, santé connexion
  Aide: diagnostic "aucun paquet MeshCore"
• /nodesmc [page|full] - Liste contacts MeshCore
  ...
```

---

## 🔧 For Developers: Implementation Details

### Files Modified:
1. **meshcore_serial_interface.py**
   - Added `CONNECTION VERIFICATION` banner
   - Made heartbeat INFO level (always visible)
   - Added `get_connection_status()` method

2. **meshcore_cli_wrapper.py**
   - Added `get_connection_status()` method
   - Returns: port, threads, health status, last message time

3. **handlers/command_handlers/network_commands.py**
   - Added `handle_meshcore()` method
   - Supports single and dual mode
   - Shows detailed connection diagnostics

4. **handlers/message_router.py**
   - Added routing for `/meshcore` command

5. **handlers/command_handlers/utility_commands.py**
   - Added `/meshcore` to help text

---

## 🎉 Benefits

### Before:
- ❌ No visibility into MeshCore connection status
- ❌ Heartbeat only visible in DEBUG mode
- ❌ No way for users to check if connection is working
- ❌ Had to guess from absence of packet logs

### After:
- ✅ **Immediate verification banner** at startup
- ✅ **Heartbeat always visible** (every 60 seconds)
- ✅ **User command** to check status anytime
- ✅ **Clear indicators** for healthy/unhealthy connections
- ✅ **Diagnostic guidance** built into logs

---

## 💡 Pro Tips

1. **First Startup:**
   - Look for the `CONNECTION VERIFICATION` banner
   - All ✅ means good to go
   - Any ❌ needs investigation

2. **Ongoing Monitoring:**
   - Watch for `[MESHCORE-HEARTBEAT]` every 60 seconds
   - If you see ⏸️ icon, no data is arriving
   - If you see ✅ icon, packets are being received

3. **User Verification:**
   - Send `/meshcore` command anytime
   - Instant diagnostic without checking logs

4. **Troubleshooting:**
   - No heartbeat → Thread crashed or port closed
   - Heartbeat but 0 packets → Device not sending
   - See data logs → Connection working perfectly

---

## 📸 Expected Log Pattern (Healthy Connection)

```
[startup]
[INFO] ✅ [MESHCORE] CONNECTION VERIFICATION
[INFO]    All systems ✅

[60 seconds later]
[INFO] ✅ [MESHCORE-HEARTBEAT] Connexion active | Iterations: 600 | Paquets reçus: 3

[120 seconds later]
[INFO] ✅ [MESHCORE-HEARTBEAT] Connexion active | Iterations: 1200 | Paquets reçus: 8

[when message arrives]
[INFO] 📥 [MESHCORE-DATA] 47 bytes waiting
[INFO] 📨 [MESHCORE-TEXT] Reçu: /help
[INFO] 📞 [MESHCORE-TEXT] Calling message_callback
[INFO] ✅ [MESHCORE-TEXT] Callback completed
```

This is the **golden pattern** you want to see! 🏆

---

## 🚀 Next Steps

If you still don't see MeshCore activity after these improvements:

1. **Check Configuration:**
   ```python
   MESHCORE_ENABLED = True
   MESHCORE_SERIAL_PORT = '/dev/ttyUSB0'  # Correct port?
   ```

2. **Check Hardware:**
   - Is the MeshCore device powered on?
   - Is the USB cable connected?
   - Does `/dev/ttyUSB0` exist? (`ls -la /dev/ttyUSB*`)

3. **Check Permissions:**
   - Can the bot user access the serial port?
   - `sudo usermod -a -G dialout $USER`

4. **Test with meshcore-cli:**
   ```bash
   pip install meshcore meshcoredecoder
   meshcore-cli -s /dev/ttyUSB0 chat
   ```

5. **Use the /meshcore command:**
   - Send `/meshcore` from another node
   - Check the status response

---

**End of Guide**
