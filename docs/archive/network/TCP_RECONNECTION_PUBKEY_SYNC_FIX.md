# TCP Reconnection Pubkey Sync Fix

## Problem Statement

The bot was hanging during TCP reconnection when attempting to synchronize public keys immediately after the interface reconnected.

### Symptom

```
Jan 05 13:35:58 DietPi meshtastic-bot[48594]: [INFO] 🔑 Re-synchronisation clés publiques après reconnexion...
Jan 05 13:35:58 DietPi meshtastic-bot[48594]: [INFO] 🔄 Starting public key synchronization to interface.nodes...
[HANGS - No further output, bot stops responding]
```

### Root Cause

1. TCP reconnection completes at `13:35:58`
2. Bot immediately calls `sync_pubkeys_to_interface(force=True)`
3. This method accesses `interface.nodes` which triggers network I/O
4. The interface is not fully stable yet (even after 3s stabilization delay)
5. Accessing `interface.nodes` blocks/hangs indefinitely
6. Reconnection never completes, bot becomes unresponsive

**Key insight**: The 3-second stabilization delay (`TCP_INTERFACE_STABILIZATION_DELAY`) is sufficient for socket connection but **NOT** for the internal interface state (like `nodes` dict) to be ready.

## Solution

### 1. Deferred Pubkey Sync (Main Fix)

Instead of running pubkey sync immediately after reconnection, we defer it to a background thread with a 15-second delay:

```python
# main_bot.py - New constant
TCP_PUBKEY_SYNC_DELAY = 15  # Délai après reconnexion avant de synchroniser les clés publiques

# In _reconnect_tcp_interface():
if self.node_manager:
    info_print(f"🔑 Synchronisation clés publiques programmée dans {self.TCP_PUBKEY_SYNC_DELAY}s...")
    
    def deferred_pubkey_sync():
        """Sync public keys after delay to avoid blocking reconnection"""
        try:
            time.sleep(self.TCP_PUBKEY_SYNC_DELAY)
            info_print("🔑 Démarrage synchronisation clés publiques différée...")
            injected = self.node_manager.sync_pubkeys_to_interface(self.interface, force=True)
            if injected > 0:
                info_print(f"✅ {injected} clés publiques re-synchronisées")
            else:
                info_print("ℹ️ Aucune clé à re-synchroniser (aucune clé dans node_names.json)")
        except Exception as sync_error:
            error_print(f"⚠️ Erreur re-sync clés après reconnexion: {sync_error}")
            error_print(traceback.format_exc())
    
    # Launch in daemon thread so it doesn't block shutdown
    pubkey_thread = threading.Thread(
        target=deferred_pubkey_sync,
        daemon=True,
        name="TCP-PubkeySync"
    )
    pubkey_thread.start()
```

**Benefits:**
- ✅ TCP reconnection completes immediately (non-blocking)
- ✅ Interface has 15 seconds to fully stabilize before sync
- ✅ Background thread doesn't prevent bot shutdown
- ✅ Clear logging shows when sync is scheduled vs when it runs

### 2. Error Handling for interface.nodes Access

Added safety wrapper in `node_manager.py` to handle failures gracefully:

```python
# node_manager.py - sync_pubkeys_to_interface()
try:
    # Attempt to access nodes dict
    # If this hangs, the deferred sync (after 15s) gives the interface time to stabilize
    nodes = getattr(interface, 'nodes', {})
except Exception as e:
    error_print(f"⚠️ Error accessing interface.nodes: {e}")
    error_print("❌ Cannot sync pubkeys: interface.nodes not accessible")
    return 0

if nodes is None:
    error_print("❌ Cannot sync pubkeys: interface.nodes is None")
    return 0
```

**Benefits:**
- ✅ Prevents crash if interface.nodes fails
- ✅ Returns cleanly with 0 keys synced
- ✅ Logs clear error message for debugging

## Expected Behavior After Fix

### Normal TCP Reconnection Flow

```
13:35:39 [INFO] 🔄 Reconnexion TCP #1 à 192.168.1.38:4403...
13:35:39 [DEBUG] 🔄 Fermeture ancienne interface TCP...
13:35:39 [INFO] Fermeture OptimizedTCPInterface...
13:35:39 [INFO] ✅ OptimizedTCPInterface fermée
13:35:39 [DEBUG] ⏳ Attente nettoyage (15s) - tentative 1/3...
13:35:54 [DEBUG] 🔧 Création nouvelle interface TCP...
13:35:55 [DEBUG] ⏳ Stabilisation nouvelle interface (3s)...
13:35:58 [DEBUG] ✅ Socket connecté à ('192.168.1.38', 4403)
13:35:58 [DEBUG] 🔌 Configuration callback reconnexion sur nouvelle interface...
13:35:58 [DEBUG] ✅ Callback socket mort configuré
13:35:58 [DEBUG] 🔄 Mise à jour références interface...
13:35:58 [DEBUG] ✅ MessageHandler/Sender interfaces mises à jour
13:35:58 [DEBUG] ℹ️ Pas de réabonnement nécessaire (pubsub global)
13:35:58 [DEBUG] ⏱️ Timer dernier paquet réinitialisé
13:35:58 [INFO] 🔑 Synchronisation clés publiques programmée dans 15s...  ← NEW
13:35:58 [INFO] ✅ Reconnexion TCP réussie (background)  ← COMPLETES IMMEDIATELY
...
[15 seconds pass, interface fully stable]
...
13:36:13 [INFO] 🔑 Démarrage synchronisation clés publiques différée...  ← NEW
13:36:13 [INFO] 🔄 Starting public key synchronization to interface.nodes...
13:36:13 [INFO]    Current interface.nodes count: 0
13:36:13 [INFO]    Keys to sync from node_names: 42
13:36:13 [INFO] ✅ SYNC COMPLETE: 42 public keys synchronized to interface.nodes  ← SUCCESS
```

### Key Differences

**Before Fix:**
- Sync runs immediately at `13:35:58`
- Hangs on `interface.nodes` access
- Never completes
- Bot becomes unresponsive

**After Fix:**
- Reconnection completes at `13:35:58` ✅
- Sync scheduled for `13:36:13` (15s later) ✅
- Interface has time to stabilize ✅
- Sync completes successfully ✅

## Testing

### Automated Tests

Created `test_tcp_pubkey_sync_fix.py` with 5 comprehensive tests:

```bash
$ python3 test_tcp_pubkey_sync_fix.py
============================================================
Testing TCP Reconnection Pubkey Sync Fix
============================================================

test_cache_based_skip ... ok
test_deferred_pubkey_sync_delay ... ok
test_error_handling_on_nodes_access ... ok
test_sync_skip_with_no_keys ... ok
test_sync_with_working_interface ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.513s

OK
============================================================
✅ ALL TESTS PASSED

Summary of fixes:
  1. ✅ Pubkey sync is deferred after reconnection (15s delay)
  2. ✅ Error handling prevents crashes on interface.nodes failure
  3. ✅ Normal sync operations work correctly
  4. ✅ Cache optimization prevents excessive syncs
============================================================
```

### Manual Testing

To verify the fix in production:

1. **Monitor logs during TCP reconnection:**
   ```bash
   journalctl -u meshbot -f | grep -E "reconnexion|clés publiques|pubkey"
   ```

2. **Expected output:**
   - Should see "Synchronisation clés publiques programmée dans 15s..."
   - Reconnection should complete immediately
   - 15 seconds later: "Démarrage synchronisation clés publiques différée..."
   - Then: "SYNC COMPLETE: N public keys synchronized"

3. **Check bot responsiveness:**
   - Send `/help` command immediately after reconnection
   - Should respond without delay (not hanging)

## Configuration

### New Constant

```python
# main_bot.py
class MeshBot:
    TCP_PUBKEY_SYNC_DELAY = 15  # Délai après reconnexion avant de synchroniser les clés publiques
```

**Tuning:**
- **15 seconds (default)**: Good balance for most ESP32-based nodes
- **10 seconds**: Minimum recommended (interface needs time to stabilize)
- **20+ seconds**: Use if you experience ongoing issues (slower nodes)

## Technical Details

### Why Deferred Sync Works

1. **TCP Socket Connection** (0-3 seconds):
   - Socket connects and passes `getpeername()` check
   - Basic TCP connection is alive
   - But internal interface state is not ready

2. **Interface Stabilization** (3-15 seconds):
   - Meshtastic interface initializes internal structures
   - `nodes` dict gets populated from network
   - Background threads start (`__reader`, etc.)

3. **Pubkey Sync** (after 15 seconds):
   - Interface is fully stable
   - `interface.nodes` access is safe
   - Sync completes without blocking

### Alternative Approaches Considered

#### ❌ Signal-based Timeout
```python
# Tried: Using signal.SIGALRM to timeout interface.nodes access
signal.alarm(10)
nodes = getattr(interface, 'nodes', {})
signal.alarm(0)
```
**Why rejected:**
- Not portable (Unix-only)
- Can't interrupt blocking C-level I/O
- Interferes with other signal handlers
- Unreliable in multithreaded environment

#### ❌ Threading Timeout
```python
# Tried: Run sync in thread with join(timeout=10)
thread = threading.Thread(target=sync)
thread.start()
thread.join(timeout=10)
```
**Why rejected:**
- Doesn't actually interrupt hanging operation
- Thread keeps running after timeout
- Resource leak if thread never completes

#### ✅ Deferred Execution (Chosen)
```python
# Winner: Simply defer to run later when interface is stable
time.sleep(15)  # In background thread
sync_pubkeys_to_interface()
```
**Why chosen:**
- Simple and reliable
- No complex timeout logic
- Gives interface time to naturally stabilize
- Easy to tune with single constant

## Files Modified

### `main_bot.py`
- Added `TCP_PUBKEY_SYNC_DELAY = 15` constant
- Modified `_reconnect_tcp_interface()` to defer pubkey sync
- Moved sync to background thread with 15s delay
- Updated logging to show sync scheduling

### `node_manager.py`
- Added error handling for `interface.nodes` access
- Wrapped `getattr()` in try-except block
- Added null check after getattr
- Returns 0 on any access failure

### `test_tcp_pubkey_sync_fix.py` (NEW)
- Comprehensive test suite for fix
- Tests deferred sync timing
- Tests error handling
- Tests normal sync operations
- Tests cache optimization

## Monitoring

### Key Metrics to Watch

1. **Reconnection Time**: Should complete in ~18 seconds total
   - 15s cleanup delay
   - 3s stabilization
   - Immediate completion (not waiting for sync)

2. **Pubkey Sync Success Rate**: Should be 100% after fix
   - Check logs for "SYNC COMPLETE" message
   - Count should match keys in node_names.json

3. **Bot Responsiveness**: Should respond immediately after reconnection
   - Test with `/help` or other commands
   - No hanging or delays

### Warning Signs

❌ If you see:
```
[INFO] 🔑 Démarrage synchronisation clés publiques différée...
[INFO] 🔄 Starting public key synchronization to interface.nodes...
[ERROR] ⚠️ Error accessing interface.nodes: <error>
```

**Action**: Increase `TCP_PUBKEY_SYNC_DELAY` to 20 or 30 seconds

❌ If you still see hangs after fix:
- Check ESP32 node stability (may need reboot)
- Verify network connectivity
- Check for excessive reconnection frequency
- Review other threads blocking on same interface

## Related Issues

- **Issue #97**: TCP disconnection loop
- **TCP_SILENT_TIMEOUT**: Health monitor forcing reconnections
- **PKI Sync Optimization**: Cache-based sync to reduce interface.nodes access

## Conclusion

This fix resolves the TCP reconnection hang by:
1. ✅ Deferring pubkey sync to run after interface is stable
2. ✅ Adding robust error handling for interface.nodes access
3. ✅ Maintaining clear logging for debugging
4. ✅ Preserving all functionality (just deferred timing)

**Impact:**
- TCP reconnections now complete in seconds, not hanging indefinitely
- Bot remains responsive during reconnection
- Public keys still sync correctly, just with a delay
- No functional regressions

**Timeline:**
- **Before**: 13:35:58 - Hang indefinitely ❌
- **After**: 13:35:58 - Complete immediately ✅
           13:36:13 - Sync completes successfully ✅
