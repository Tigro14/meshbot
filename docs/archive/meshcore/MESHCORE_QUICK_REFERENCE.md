# MeshCore Connection Verification - Quick Visual Reference

## 🔍 How to Know MeshCore is Connected

```
┌─────────────────────────────────────────────────────────────┐
│                    AT STARTUP (Immediate)                    │
└─────────────────────────────────────────────────────────────┘

✅ GOOD CONNECTION:
════════════════════════════════════════════════════════════════
✅ [MESHCORE] CONNECTION VERIFICATION
════════════════════════════════════════════════════════════════
   Port série: /dev/ttyUSB0
   Baudrate: 115200
   Port ouvert: True
   Read thread: ✅ RUNNING
   Poll thread: ✅ RUNNING
   Callback configuré: ✅ YES
   
   ✅ MeshCore companion prêt à recevoir des messages
════════════════════════════════════════════════════════════════

❌ BAD CONNECTION:
════════════════════════════════════════════════════════════════
❌ [MESHCORE] CONNECTION VERIFICATION
════════════════════════════════════════════════════════════════
   Port série: /dev/ttyUSB0
   Baudrate: 115200
   Port ouvert: False          ← ❌ Problem!
   Read thread: ❌ STOPPED      ← ❌ Problem!
   Poll thread: ❌ STOPPED      ← ❌ Problem!
   Callback configuré: ❌ NO   ← ❌ Problem!
   
   ⚠️  PROBLÈME: Vérifier les threads et le callback ci-dessus
════════════════════════════════════════════════════════════════


┌─────────────────────────────────────────────────────────────┐
│                EVERY 60 SECONDS (Heartbeat)                  │
└─────────────────────────────────────────────────────────────┘

✅ HEALTHY (Data Flowing):
[INFO] ✅ [MESHCORE-HEARTBEAT] Connexion active | Iterations: 2400 | Paquets reçus: 15
       └── Green checkmark = Data received!

⚠️  WARNING (No Data):
[INFO] ⏸️ [MESHCORE-HEARTBEAT] Connexion active | Iterations: 2400 | Paquets reçus: 0
[INFO]    ⚠️  Aucun paquet reçu depuis 60s - Vérifier radio MeshCore
       └── Pause icon = No packets received!


┌─────────────────────────────────────────────────────────────┐
│               WHEN MESSAGES ARRIVE (Real-time)               │
└─────────────────────────────────────────────────────────────┘

[INFO] 📥 [MESHCORE-DATA] 47 bytes waiting (packet #1)
[INFO] 📦 [MESHCORE-RAW] Read 47 bytes: 3c2f0001...
[INFO] 📨 [MESHCORE-TEXT] Reçu: DM:12345678:Hello
[INFO] 📬 [MESHCORE-DM] De: 0x12345678 | Message: Hello
[INFO] 📞 [MESHCORE-TEXT] Calling message_callback
[INFO] ✅ [MESHCORE-TEXT] Callback completed successfully


┌─────────────────────────────────────────────────────────────┐
│                    USER STATUS COMMAND                       │
│                      (Anytime Check)                         │
└─────────────────────────────────────────────────────────────┘

Send: /meshcore

Response (Connected):
─────────────────────────
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
─────────────────────────

Response (Not Connected):
─────────────────────────
⚠️ MeshCore désactivé

📝 Pour activer:
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = '/dev/ttyUSB0'
─────────────────────────
```

## 🎯 3-Second Diagnosis

```
┌────────────────────────────────────────────────────────┐
│  QUESTION: Is MeshCore connected?                      │
├────────────────────────────────────────────────────────┤
│                                                         │
│  1. At startup, do you see:                            │
│     "✅ MeshCore companion prêt"?                       │
│     └── YES → Connected ✅                              │
│     └── NO → Not connected ❌                           │
│                                                         │
│  2. After 60 seconds, do you see:                      │
│     "[MESHCORE-HEARTBEAT]" with packets > 0?           │
│     └── YES → Data flowing ✅                           │
│     └── NO → No data ⚠️                                 │
│                                                         │
│  3. Send /meshcore command:                            │
│     Shows all ✅?                                       │
│     └── YES → Everything OK ✅                          │
│     └── NO → Check which ❌ to fix                      │
│                                                         │
└────────────────────────────────────────────────────────┘
```

## 📋 Troubleshooting Flowchart

```
┌─────────────────┐
│  Start Bot      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ See "CONNECTION VERIFICATION"?      │
└────────┬────────────────────────────┘
         │
    ┌────┴────┐
    │         │
   YES       NO ──────────────────────┐
    │                                 │
    ▼                                 ▼
┌────────────────┐          ┌──────────────────┐
│ All ✅?        │          │ Check config.py: │
└────┬───────────┘          │ MESHCORE_ENABLED │
     │                      └──────────────────┘
 ┌───┴───┐
YES     NO ───────────────────────────┐
 │                                    │
 ▼                                    ▼
┌──────────────────┐     ┌────────────────────────┐
│ Wait 60 seconds  │     │ Fix ❌ items:          │
└────────┬─────────┘     │ - Port doesn't exist   │
         │               │ - Permission denied    │
         ▼               │ - Port already in use  │
┌──────────────────┐     └────────────────────────┘
│ See HEARTBEAT?   │
└────────┬─────────┘
         │
    ┌────┴────┐
   YES       NO ─────────────────────┐
    │                                │
    ▼                                ▼
┌────────────────┐     ┌─────────────────────────┐
│ Packets > 0?   │     │ Thread crashed?         │
└────┬───────────┘     │ Check logs for errors   │
     │                 └─────────────────────────┘
 ┌───┴───┐
YES     NO ────────────────────────┐
 │                                 │
 ▼                                 ▼
┌──────────────┐    ┌──────────────────────────┐
│ ✅ CONNECTED │    │ Device not sending data: │
│ & WORKING!   │    │ - Power on?              │
└──────────────┘    │ - Firmware running?      │
                    │ - Cable connected?       │
                    └──────────────────────────┘
```

## 🔑 Key Indicators

| Log Pattern | Meaning | Action |
|-------------|---------|--------|
| `✅ CONNECTION VERIFICATION` + all ✅ | Perfect connection | None - enjoy! |
| `❌ Port ouvert: False` | Port doesn't exist or permission denied | Check `/dev/ttyUSB*` exists, check permissions |
| `❌ Read thread: STOPPED` | Thread failed to start | Check port not already in use |
| `⏸️ [MESHCORE-HEARTBEAT]` + 0 packets | Connected but no data | Check MeshCore device is on and transmitting |
| `✅ [MESHCORE-HEARTBEAT]` + N packets | Perfect! Data flowing | Connection healthy |
| No heartbeat after 60s | Thread crashed | Check logs for errors, restart bot |
| `📥 [MESHCORE-DATA]` | Data arriving | Perfect! |
| `/meshcore` shows all ✅ | Everything working | No issues |

## 🎨 Log Color Guide (if terminal supports colors)

```
[INFO]  = Standard messages (white/default)
[DEBUG] = Verbose details (gray) - only if DEBUG_MODE=True
[ERROR] = Problems (red)
✅      = Success/healthy (green)
❌      = Failure/error (red)
⚠️      = Warning (yellow/orange)
📡 📊 📥 = Informational icons
```

## 💡 Pro Tips

1. **Always wait 60 seconds after startup** to see the first heartbeat
2. **The heartbeat is your friend** - if you see it regularly, connection is alive
3. **Use `/meshcore` command** - instant status without digging through logs
4. **Look for the banner** - first thing to check at startup
5. **Check icons** - ✅ vs ❌ vs ⏸️ tells you everything

---

**Quick Summary:**

- ✅ Banner at startup = Connected
- ✅ Heartbeat every 60s = Alive
- 📥 Data logs = Messages arriving
- `/meshcore` command = Instant check

**That's it!** 🎉
