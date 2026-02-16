# Before/After Comparison: [MC]/[MT] Log Prefixes

## Visual Comparison

### BEFORE (Generic Logging)

```
[INFO] ✅ Callback MeshCore configuré: <bound method>
[INFO]    Interface type: MeshCoreCLIWrapper
[INFO]    Callback set to: on_message method
[INFO] ✅ Connexion MeshCore établie

[INFO] 🔔🔔🔔 ========== on_message() CALLED ==========
[INFO] 🔔 Packet: True
[INFO] 🔔 Interface: SerialInterface
[INFO] 🔔 network_source: None
[INFO] 🔔 From ID: 0x12345678
[INFO] 🔔🔔🔔 ==========================================

[INFO] 📡 Subscribing to Meshtastic messages via pubsub...
[INFO] ✅ ✅ ✅ SUBSCRIBED TO meshtastic.receive ✅ ✅ ✅
[INFO]    Callback: <bound method>
[INFO]    Topic: 'meshtastic.receive'

[INFO] 🔍 [INTERFACE-HEALTH] Checking interface status:
[INFO]    ✅ Primary interface exists: SerialInterface
[INFO]    ✅ Interface connected (localNode exists)
[INFO]    ✅ Callback registered
[INFO]    📡 Serial port: /dev/ttyACM0
```

❌ **Problem:** Can't tell which interface the logs relate to!

---

### AFTER (Interface-Specific Prefixes)

#### MeshCore Logs

```
[INFO][MC] ✅ Callback MeshCore configuré: <bound method>
[INFO][MC]    Interface type: MeshCoreCLIWrapper
[INFO][MC]    Callback set to: on_message method
[INFO][MC] ✅ Connexion MeshCore établie

[INFO][MC] 🔔🔔🔔 ========== on_message() CALLED ==========
[INFO][MC] 🔔 Packet: True
[INFO][MC] 🔔 Interface: MeshCoreCLIWrapper
[INFO][MC] 🔔 network_source: meshcore
[INFO][MC] 🔔 From ID: 0xaabbccdd
[INFO][MC] 🔔🔔🔔 ==========================================

[INFO][MC] ℹ️  ℹ️  ℹ️  Mode companion: Messages gérés par interface MeshCore
[INFO][MC]    → MeshCore callback already configured
[INFO][MC]    → Packets will arrive via MeshCore, not pubsub

[INFO][MC] 🔍 [INTERFACE-HEALTH] Checking interface status:
[INFO][MC]    ✅ Primary interface exists: MeshCoreCLIWrapper
[INFO][MC]    ✅ Interface connected (localNode exists)
[INFO][MC]    ✅ Callback registered
```

✅ **Clear:** All logs show [MC] prefix!

#### Meshtastic Logs

```
[INFO][MT] 📡 Subscribing to Meshtastic messages via pubsub...
[INFO][MT] ✅ ✅ ✅ SUBSCRIBED TO meshtastic.receive ✅ ✅ ✅
[INFO][MT]    Callback: <bound method>
[INFO][MT]    Topic: 'meshtastic.receive'
[INFO][MT]    → Meshtastic interface should now publish packets to this callback

[INFO][MT] 🔔🔔🔔 ========== on_message() CALLED ==========
[INFO][MT] 🔔 Packet: True
[INFO][MT] 🔔 Interface: SerialInterface
[INFO][MT] 🔔 network_source: None
[INFO][MT] 🔔 From ID: 0x12345678
[INFO][MT] 🔔🔔🔔 ==========================================

[INFO][MT] 🔍 [INTERFACE-HEALTH] Checking interface status:
[INFO][MT]    ✅ Primary interface exists: SerialInterface
[INFO][MT]    ✅ Interface connected (localNode exists)
[INFO][MT]    ✅ Callback registered
[INFO][MT]    📡 Serial port: /dev/ttyACM0
[INFO][MT]    ✅ Serial stream exists
[INFO][MT]    ✅ Serial port is OPEN
```

✅ **Clear:** All logs show [MT] prefix!

---

## Filtering Examples

### Filter MeshCore Logs Only

```bash
journalctl -u meshtastic-bot -f | grep "\[MC\]"
```

**Output:**
```
[INFO][MC] ✅ Callback MeshCore configuré
[INFO][MC] 🔔 on_message() CALLED
[INFO][MC] 🔔 network_source: meshcore
[INFO][MC] 🔍 [INTERFACE-HEALTH] Checking interface status:
```

### Filter Meshtastic Logs Only

```bash
journalctl -u meshtastic-bot -f | grep "\[MT\]"
```

**Output:**
```
[INFO][MT] 📡 Subscribing to Meshtastic messages
[INFO][MT] ✅ SUBSCRIBED TO meshtastic.receive
[INFO][MT] 🔔 on_message() CALLED
[INFO][MT] 🔍 [INTERFACE-HEALTH] Checking interface status:
```

### Show Both (All Interface Logs)

```bash
journalctl -u meshtastic-bot -f | grep -E "\[MC\]|\[MT\]"
```

**Output:**
```
[INFO][MC] ✅ Callback MeshCore configuré
[INFO][MT] 📡 Subscribing to Meshtastic messages
[INFO][MT] 🔔 on_message() CALLED
[INFO][MC] 🔔 on_message() CALLED
```

---

## Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Interface identification** | ❌ Unclear | ✅ Immediate ([MC]/[MT]) |
| **Log filtering** | ❌ Manual search | ✅ Simple grep |
| **Debugging** | ❌ Confused logs | ✅ Clear separation |
| **Context awareness** | ❌ None | ✅ Automatic |
| **Consistency** | ❌ Mixed | ✅ All prefixed |

---

## Summary

**Before:** Generic [INFO] logs - hard to identify which interface  
**After:** Clear [INFO][MC] or [INFO][MT] - immediately visible  

**Impact:** Much easier debugging and log analysis!
