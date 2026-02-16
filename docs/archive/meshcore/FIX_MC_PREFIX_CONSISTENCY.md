# Fix: No Traffic Visible - MeshCore Messages Missing [MC] Prefix

## Problem

User reports getting NO traffic anymore. Log analysis revealed:
- NO [INFO][MC] or [DEBUG][MC] messages visible
- No subscription confirmations
- No RX_LOG packet activity
- No healthcheck alerts

### Root Cause

Many critical MeshCore operational messages used `info_print()` or `error_print()` WITHOUT the `[MC]` prefix:
- Connection messages: `info_print(f"🔌 [MESHCORE-CLI] Connexion...")`
- Thread startup: `info_print("✅ [MESHCORE-CLI] Thread événements démarré")`
- Healthcheck alerts: `error_print(f"⚠️ [MESHCORE-HEALTHCHECK] ALERTE...")`

When users filter logs with `journalctl -u meshtastic-bot | grep MC`, these messages are **invisible**.

### The Real Issue

The user's logs show:
```
[DEBUG] 🧹 2659 paquets anciens expirés
INFO:traffic_persistence:Nettoyage : 0 paquets... supprimés
```

- **2659 old packets expired from memory** = Packets WERE being received earlier
- **0 packets in database cleanup** = No recent packets (> 720h ago)
- **No healthcheck alerts visible** = Connection loss not visible when filtering for [MC]

This indicates:
1. MeshCore connection was established initially
2. Packets were received and stored in memory (deque)
3. Connection was lost at some point
4. Healthcheck detected it BUT alert wasn't visible with `grep MC`
5. User thinks nothing is happening because critical messages aren't showing

## Solution

Changed all critical MeshCore operational messages to use `info_print_mc()` or include `[MC]` prefix:

### Changes Made

**File:** `meshcore_cli_wrapper.py`

#### 1. Initialization Message (line ~103)
```python
# Before
info_print(f"🔧 [MESHCORE-CLI] Initialisation: {port}...")

# After
info_print_mc(f"🔧 Initialisation: {port}...")
```

#### 2. Connection Message (line ~108)
```python
# Before
info_print(f"🔌 [MESHCORE-CLI] Connexion à {self.port}...")

# After
info_print_mc(f"🔌 Connexion à {self.port}...")
```

#### 3. Node ID Message (line ~136)
```python
# Before
info_print(f"   Node ID: 0x{self.localNode.nodeNum:08x}")
debug_print(f"⚠️ [MESHCORE-CLI] Impossible de récupérer node_id: {e}")

# After
info_print_mc(f"   Node ID: 0x{self.localNode.nodeNum:08x}")
debug_print_mc(f"⚠️ Impossible de récupérer node_id: {e}")
```

#### 4. Connection Error (line ~143)
```python
# Before
error_print(f"❌ [MESHCORE-CLI] Erreur connexion: {e}")

# After
error_print(f"❌ [MC] Erreur connexion: {e}")
```

#### 5. Message Callback Setup (line ~155)
```python
# Before
info_print(f"📝 [MESHCORE-CLI] Setting message_callback to {callback}")

# After
debug_print_mc(f"📝 Setting message_callback to {callback}")
```

#### 6. Thread Startup Messages (lines ~871, ~880)
```python
# Before
info_print("✅ [MESHCORE-CLI] Thread événements démarré")
info_print("✅ [MESHCORE-CLI] Healthcheck monitoring démarré")

# After
info_print_mc("✅ Thread événements démarré")
info_print_mc("✅ Healthcheck monitoring démarré")
```

#### 7. Healthcheck Alert Messages (lines ~905-909)
```python
# Before
error_print(f"⚠️ [MESHCORE-HEALTHCHECK] ALERTE: Aucun message reçu depuis {int(time_since_last_message)}s")
error_print(f"   → La connexion au nœud semble perdue")
error_print(f"   → Vérifiez: 1) Le nœud est allumé")
# ... etc

# After
error_print(f"⚠️ [MC] ALERTE HEALTHCHECK: Aucun message reçu depuis {int(time_since_last_message)}s")
error_print(f"   [MC] → La connexion au nœud semble perdue")
error_print(f"   [MC] → Vérifiez: 1) Le nœud est allumé")
# ... etc
```

#### 8. Connection Recovery Message (line ~914)
```python
# Before
info_print(f"✅ [MESHCORE-HEALTHCHECK] Connexion rétablie...")

# After
info_print_mc(f"✅ Connexion rétablie (message reçu il y a {int(time_since_last_message)}s)")
```

#### 9. Healthcheck Debug Message (line ~918)
```python
# Before
debug_print(f"🏥 [MESHCORE-HEALTHCHECK] OK - dernier message: {int(time_since_last_message)}s")

# After
debug_print_mc(f"🏥 Healthcheck OK - dernier message: {int(time_since_last_message)}s")
```

## Before/After

### BEFORE (Invisible with grep MC)
```bash
journalctl -u meshtastic-bot | grep MC
# Empty or very limited output
# Missing:
# - Connection status
# - Thread startup
# - Healthcheck alerts
```

### AFTER (All Critical Messages Visible)
```bash
journalctl -u meshtastic-bot | grep MC

[INFO][MC] 🔧 Initialisation: /dev/ttyACM0 (debug=True)
[INFO][MC] 🔌 Connexion à /dev/ttyACM0...
[INFO][MC] ✅  Device connecté sur /dev/ttyACM0
[INFO][MC] ✅ Thread événements démarré
[INFO][MC] ✅ Healthcheck monitoring démarré
[INFO][MC] ✅  message_callback set successfully
[INFO][MC] ✅ Souscription aux messages DM (events.subscribe)
[INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
[INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (134B)...
[DEBUG][MC] 📦 [RX_LOG] Type: Advert...
# ... packet activity ...

# If connection is lost:
[ERROR] ⚠️ [MC] ALERTE HEALTHCHECK: Aucun message reçu depuis 305s
[ERROR]    [MC] → La connexion au nœud semble perdue
[ERROR]    [MC] → Vérifiez: 1) Le nœud est allumé
[ERROR]    [MC] →          2) Le câble série est connecté (/dev/ttyACM0)

# If connection recovers:
[INFO][MC] ✅ Connexion rétablie (message reçu il y a 45s)
```

## Benefits

1. **Complete Visibility**: All critical MeshCore status visible with `grep MC`
2. **Troubleshooting**: Users immediately see connection issues
3. **Consistency**: All MeshCore messages use same [MC] prefix
4. **Early Detection**: Healthcheck alerts now visible
5. **User Confidence**: See full MeshCore lifecycle (startup → running → issues → recovery)

## Testing

Run test to verify:
```bash
python3 test_mc_prefix_consistency.py
```

Expected results:
- ✅ All connection messages show [INFO][MC]
- ✅ All thread startup messages show [INFO][MC]
- ✅ All healthcheck alerts show [ERROR] with [MC] prefix
- ✅ All recovery messages show [INFO][MC]

## Impact on User's Issue

With these changes, when filtering logs with `grep MC`, the user will now see:
1. ✅ **MeshCore startup** - Confirms bot initialized MeshCore
2. ✅ **Connection status** - Confirms device connected
3. ✅ **Thread startup** - Confirms background threads started
4. ✅ **Subscription confirmations** - Confirms RX_LOG monitoring enabled
5. ✅ **Healthcheck alerts** - **CRITICAL**: Shows when connection is lost!
6. ✅ **Packet activity** - Shows when packets arrive (if DEBUG_MODE=True)

**Most importantly**: If the MeshCore connection drops (as likely happened in user's case), they will now see:
```
[ERROR] ⚠️ [MC] ALERTE HEALTHCHECK: Aucun message reçu depuis 305s
[ERROR]    [MC] → La connexion au nœud semble perdue
```

This immediately tells them the problem is a connection issue, not a logging issue.

## Related Issues

- Connection loss detection: Healthcheck monitors for messages
- Timeout: 300 seconds (5 minutes) without messages triggers alert
- No auto-reconnect: User must restart bot or fix hardware issue
- Memory cleanup: Old packets expire from deque after certain time

## Future Improvements

Consider adding:
- Auto-reconnect on connection loss
- Configurable healthcheck timeout
- More detailed connection diagnostics
- Connection state monitoring in /stats command
