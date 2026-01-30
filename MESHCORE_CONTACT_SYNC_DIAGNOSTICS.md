# MeshCore Contact Sync Diagnostic Logging

## Problem Statement

Users report: "Jan 30 10:16:31 DietPi meshtastic-bot[438810]: [DEBUG] ℹ️ Base à jour (0 nœuds)"

After many hours, still no nodes recorded into the contact database in MeshCore mode.

## Root Cause

MeshCore contacts are synced from the device but may fail to save to the SQLite database due to missing prerequisites. The failure was **silent** - no error messages indicated why contacts weren't saved.

## Solution: Enhanced Diagnostic Logging

Added comprehensive diagnostic logging to identify which save condition is failing.

### Save Conditions Checked (4 conditions)

```python
if post_count > 0 and self.node_manager and hasattr(self.node_manager, 'persistence') and self.node_manager.persistence:
```

1. ✅ `post_count > 0` - Contacts were synced from device
2. ✅ `self.node_manager` - NodeManager reference is set
3. ✅ `hasattr(self.node_manager, 'persistence')` - Persistence attribute exists
4. ✅ `self.node_manager.persistence` - Persistence is initialized

### New Diagnostic Messages

#### Before Save Attempt
```
🔍 [MESHCORE-SYNC] Check save conditions:
   post_count > 0: True (count=5)
   self.node_manager exists: True
   has persistence attr: True
   persistence is not None: True
```

#### Success
```
💾 [MESHCORE-SYNC] Sauvegarde 5 contacts dans SQLite...
💾 [MESHCORE-SYNC] 5/5 contacts sauvegardés dans meshcore_contacts
```

#### Failure
```
❌ [MESHCORE-SYNC] 5 contacts synchronisés mais NON SAUVEGARDÉS!
   → Causes possibles:
      ❌ node_manager n'est pas configuré (None)
         Solution: Appeler interface.set_node_manager(node_manager) AVANT start_reading()
```

## Common Failure Scenarios

### Scenario 1: No Contacts on Device (post_count = 0)

**Symptom:**
```
⚠️ [MESHCORE-SYNC] ATTENTION: sync_contacts() n'a trouvé AUCUN contact!
   → Raisons possibles:
   1. Mode companion: nécessite appairage avec app mobile
   2. Base de contacts vide dans meshcore-cli
   3. Problème de clé privée pour déchiffrement
```

**Root Cause:** Device has no contacts stored

**Solutions:**
- Pair with mobile app to sync contacts
- Manually add contacts via MeshCore CLI
- Verify private key is configured for DM decryption

### Scenario 2: NodeManager Not Set

**Symptom:**
```
❌ [MESHCORE-SYNC] 5 contacts synchronisés mais NON SAUVEGARDÉS!
   → Causes possibles:
      ❌ node_manager n'est pas configuré (None)
```

**Root Cause:** `interface.set_node_manager()` not called or called too late

**Solution in main_bot.py:**
```python
# CORRECT sequence:
interface = MeshCoreSerialInterface(port)
interface.connect()
interface.set_node_manager(self.node_manager)  # ← BEFORE start_reading
interface.start_reading()  # ← Triggers async sync
```

### Scenario 3: Persistence Not Initialized

**Symptom:**
```
❌ [MESHCORE-SYNC] 5 contacts synchronisés mais NON SAUVEGARDÉS!
   → Causes possibles:
      ❌ node_manager.persistence est None
```

**Root Cause:** TrafficPersistence not assigned to node_manager

**Solution in main_bot.py:**
```python
# Connect persistence to node_manager
self.node_manager.persistence = self.traffic_monitor.persistence
```

## Testing

### Enable Debug Mode

```python
# config.py
DEBUG_MODE = True
```

### Watch Logs During Startup

```bash
journalctl -u meshbot -f | grep "MESHCORE-SYNC"
```

### Expected Output (Success)

```
🔄 [MESHCORE-CLI] Synchronisation des contacts...
✅ [MESHCORE-CLI] Contacts synchronisés
📊 [MESHCORE-SYNC] Contacts APRÈS sync: 5
🔍 [MESHCORE-SYNC] Check save conditions:
   post_count > 0: True (count=5)
   self.node_manager exists: True
   has persistence attr: True
   persistence is not None: True
💾 [MESHCORE-SYNC] Sauvegarde 5 contacts dans SQLite...
💾 [MESHCORE-SYNC] 5/5 contacts sauvegardés dans meshcore_contacts
```

### Expected Output (Failure)

```
🔄 [MESHCORE-CLI] Synchronisation des contacts...
✅ [MESHCORE-CLI] Contacts synchronisés
📊 [MESHCORE-SYNC] Contacts APRÈS sync: 5
🔍 [MESHCORE-SYNC] Check save conditions:
   post_count > 0: True (count=5)
   self.node_manager exists: False
❌ [MESHCORE-SYNC] 5 contacts synchronisés mais NON SAUVEGARDÉS!
   → Causes possibles:
      ❌ node_manager n'est pas configuré (None)
         Solution: Appeler interface.set_node_manager(node_manager) AVANT start_reading()
```

## Verification

After deploying the fix, verify contacts are saved:

```bash
# Check SQLite database
sqlite3 traffic_history.db "SELECT COUNT(*) FROM meshcore_contacts;"

# List contacts
sqlite3 traffic_history.db "SELECT node_id, name FROM meshcore_contacts LIMIT 10;"

# Use /nodesmc command
# (via MeshCore radio or Telegram bot)
/nodesmc
```

## Files Modified

- `meshcore_cli_wrapper.py` (lines 740-800)
  - Added detailed condition checking
  - Added explicit error logging on save failure
  - Added solution hints for each failure type

## Tests Added

- `test_meshcore_contact_sync_diagnostics.py` - Verifies diagnostic messages present
- `demo_meshcore_contact_sync_diagnostics.py` - Demonstrates all failure scenarios

## Next Steps

1. ✅ Deploy updated `meshcore_cli_wrapper.py`
2. ✅ Enable `DEBUG_MODE=True`
3. ⏳ Restart bot and check logs
4. ⏳ Identify which condition is failing (if any)
5. ⏳ Apply specific fix based on diagnostic output
6. ⏳ Verify contacts are saved to database
7. ⏳ Test `/nodesmc` command shows contacts

## Related Commands

- `/nodesmc` - List MeshCore contacts (paginated, 30 days)
- `/nodesmc full` - List ALL MeshCore contacts
- `/nodesmc [page]` - List specific page of contacts

## Architecture Notes

MeshCore contacts are stored in separate `meshcore_contacts` table (not mixed with `meshtastic_nodes`):

```sql
CREATE TABLE meshcore_contacts (
    node_id TEXT PRIMARY KEY,
    name TEXT,
    shortName TEXT,
    hwModel TEXT,
    publicKey BLOB,
    lat REAL, lon REAL, alt INTEGER,
    last_updated REAL,
    source TEXT DEFAULT 'meshcore'
)
```

This separation is intentional because:
- MeshCore and Meshtastic use different contact formats
- MeshCore contacts come from companion mode (different data source)
- Allows independent management of each contact source

## References

- MeshCore Companion Radio Protocol: https://github.com/meshcore-dev/MeshCore/wiki/Companion-Radio-Protocol
- SQLite schema: `traffic_persistence.py` (lines 443-462)
- Contact sync logic: `meshcore_cli_wrapper.py` (lines 704-840)
- Main bot initialization: `main_bot.py` (lines 1663-1693)
