# Bug Fix: "153 sans clés" After Bot Restart

## Issue Report (Comment #3694064324)

**User:** @Tigro14  
**Date:** Dec 27 16:03:30  
**Problem:** `/keys` shows "153 sans clés" even though public keys ARE being extracted

### Logs Analysis
```
[INFO] publicKey value type: str, length: 44
[INFO] publicKey preview: /egCGEvYW20g2sW+wzTW
[INFO] Extracted public_key: YES
[INFO] ℹ️ Public key already stored for guilhembarpilotio - 🏢📡 (unchanged)
[INFO] ✓ Node guilhembarpilotio - 🏢📡 now has publicKey in DB (len=44)

but still 🔑 Vus: 153. 153 sans clés
```

**Key observation:** "ℹ️ Public key already stored for ... (unchanged)"

---

## Root Cause Analysis

### The Problem

1. **Bot Restart**: `interface.nodes` is cleared (in-memory only)
2. **Persistent Storage**: `node_names.json` still has all 153 keys
3. **NODEINFO Arrives**: Bot receives NODEINFO with public key
4. **Key Check**: Code compares key to `node_names.json` → "unchanged"
5. **NO SYNC**: Code path for "unchanged" did NOT call sync
6. **Result**: Key stays missing from `interface.nodes`
7. **`/keys` Command**: Checks `interface.nodes` → "153 sans clés"

### Code Flow (Before Fix)

```python
# node_manager.py, line 550-552
elif public_key and old_key:
    # Key already exists and matches - this is the common case
    info_print(f"ℹ️ Public key already stored for {name} (unchanged)")
    # ❌ NO SYNC TO interface.nodes
```

The sync was only called for:
- ✅ NEW keys (line 529)
- ✅ UPDATED keys (line 549)
- ❌ UNCHANGED keys (missing!)

---

## The Fix

### Code Change

Added sync call in "unchanged key" code path:

```python
# node_manager.py, lines 550-557
elif public_key and old_key:
    # Key already exists and matches - this is the common case
    info_print(f"ℹ️ Public key already stored for {name} (unchanged)")
    
    # CRITICAL: Still sync to interface.nodes even if unchanged
    # After bot restart, interface.nodes is empty but node_names.json has keys
    # Without this sync, /keys will report nodes as "without keys"
    self._sync_single_pubkey_to_interface(node_id, self.node_names[node_id])
```

**Lines changed:** 4 lines added at node_manager.py:557

---

## Why This Matters

### Bot Restart Scenario

```
T=0: Bot starts
     ├─ interface.nodes: {} (empty, in-memory)
     └─ node_names.json: {153 nodes with keys} (persistent)

T=1s: NODEINFO arrives for Node-1
      ├─ Extract key: "ABC123..."
      ├─ Compare to node_names.json: "unchanged"
      └─ ❌ BEFORE FIX: No sync → interface.nodes still empty

T=2s: NODEINFO arrives for Node-2
      ├─ Extract key: "DEF456..."
      ├─ Compare to node_names.json: "unchanged"
      └─ ❌ BEFORE FIX: No sync → interface.nodes still empty

...153 NODEINFO packets arrive, all "unchanged"...

T=300s: User runs /keys
        ├─ Check interface.nodes: {} (empty!)
        └─ Result: "🔑 Vus: 153. 153 sans clés" ❌
```

### After Fix

```
T=0: Bot starts
     ├─ interface.nodes: {} (empty, in-memory)
     └─ node_names.json: {153 nodes with keys} (persistent)

T=1s: NODEINFO arrives for Node-1
      ├─ Extract key: "ABC123..."
      ├─ Compare to node_names.json: "unchanged"
      └─ ✅ AFTER FIX: Sync to interface.nodes → 1 key available

T=2s: NODEINFO arrives for Node-2
      ├─ Extract key: "DEF456..."
      ├─ Compare to node_names.json: "unchanged"
      └─ ✅ AFTER FIX: Sync to interface.nodes → 2 keys available

...153 NODEINFO packets arrive, all "unchanged"...

T=300s: User runs /keys
        ├─ Check interface.nodes: {153 keys} ✓
        └─ Result: "🔑 153 nodes avec clés" ✅
```

---

## Testing

### Test Suite: test_unchanged_key_sync.py

**Test 1: Unchanged Key Still Synced**
- Simulates bot restart with key in node_names.json
- NODEINFO arrives with unchanged key
- Verifies key is synced to interface.nodes
- Result: ✅ PASSING

**Test 2: Bot Restart Scenario (153 nodes)**
- Simulates bot with 153 nodes in node_names.json
- Bot restarts, interface.nodes is empty
- 10 NODEINFO packets arrive with unchanged keys
- Verifies all 10 keys are synced
- Result: ✅ PASSING

### Log Output (After Fix)

```
[INFO] ℹ️ Public key already stored for guilhembarpilotio - 🏢📡 (unchanged)
[DEBUG]    🔑 Created interface.nodes entry with key for guilhembarpilotio - 🏢📡
```

**Key difference:** Now shows sync debug message even for unchanged keys!

---

## Impact

### Before Fix
- ❌ Bot restart → `/keys` shows "153 sans clés"
- ❌ Keys in JSON file but not accessible for DM decryption
- ❌ User confusion (keys ARE extracted but not visible)
- ❌ 5-minute wait for periodic sync to fix it

### After Fix
- ✅ Bot restart → `/keys` shows keys immediately
- ✅ Keys available for DM decryption instantly
- ✅ User sees accurate key count
- ✅ No waiting required

### Affected Scenarios
1. **Bot Restart** - Most common case
2. **TCP Mode** - `interface.nodes` starts empty
3. **Long-running Bots** - Many nodes with stable keys
4. **High-traffic Networks** - 153+ nodes is realistic

---

## Deployment

### Files Modified
- `node_manager.py` - 4 lines added at line 557
- `test_unchanged_key_sync.py` - New test file (210 lines)

### Commit
- Hash: `20825b6`
- Message: "Fix: Sync unchanged keys to interface.nodes after bot restart"

### Verification Steps
1. Deploy updated code
2. Restart bot
3. Wait for NODEINFO packets
4. Check logs for: `[DEBUG] 🔑 Created interface.nodes entry with key for ...`
5. Run `/keys` command
6. Verify: Shows correct key count (not "153 sans clés")

---

## Related Issues

This fix is part of a larger cleanup from PR #182:

1. ✅ **Issue 1**: KeySyncManager NameError (fixed in commit 899b040)
2. ✅ **Issue 2**: 5-minute delay for new keys (fixed in commit 899b040)
3. ✅ **Issue 3**: "153 sans clés" after restart (fixed in commit 20825b6) ← **THIS FIX**

All three issues are now resolved!

---

## Summary

**Problem:** After bot restart, `/keys` reports "153 sans clés" even though keys are stored in `node_names.json`.

**Root Cause:** "Unchanged key" code path did not sync to `interface.nodes`.

**Solution:** Always sync to `interface.nodes` for ANY public key, regardless of whether it's new, updated, or unchanged.

**Result:** Keys are available immediately after NODEINFO, even after bot restart.

**Status:** ✅ FIXED in commit 20825b6
