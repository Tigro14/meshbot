# Debug Investigation: /keys Reports 0 Keys Despite Periodic Sync Success

## Problem Summary

- **Periodic sync logs** (22:39:25): Show keys ARE in `interface.nodes`
  ```
  Found in interface.nodes with key: !16ced5f8
  ℹ️ Key already present and matches
  ✓ DEBUG: Key verified present (len=44)
  ```

- **`/keys` command** (22:56:00): Reports "0 keys" 16 minutes later
  ```
  Nœuds actifs: 157
  ✅ Avec clé publique: 0
  ❌ Sans clé publique: 157
  ```

## Critical Debug Output Needed

When running `/keys` with `DEBUG_MODE=True`, we should see lines like:

```
[DEBUG] DEBUG /keys: interface.nodes has X entries
[DEBUG] DEBUG /keys: Checking Y nodes from traffic
[DEBUG] DEBUG /keys: Sample node IDs in interface.nodes: [...]
[DEBUG] DEBUG /keys: Node X has key: True/False
```

**These lines are NOT appearing in the logs provided!**

## Possible Root Causes

### Hypothesis A: interface.nodes is empty when /keys runs
- Periodic sync modifies one interface object
- `/keys` checks a DIFFERENT interface object
- Evidence needed: `/keys` debug should show "interface.nodes has 0 entries"

### Hypothesis B: Keys exist but field name mismatch
- Keys stored as 'publicKey' but `/keys` checks 'public_key' (or vice versa)
- Evidence needed: `/keys` debug should show "Node X has key: False" despite sync logs showing keys present

### Hypothesis C: Node ID format mismatch
- Sync creates keys with format A (e.g., integer 305419896)
- Traffic DB returns format B (e.g., string "305419896")
- `/keys` searches with formats C (e.g., "!16ced5f8")
- Evidence needed: `/keys` debug should show which node IDs it's searching for

### Hypothesis D: Traffic DB vs interface.nodes mismatch
- Traffic DB contains 157 nodes with IDs like "!16ced5f8"
- But interface.nodes only has ~13 nodes (from NODEINFO)
- The 144 other nodes never sent NODEINFO so don't have entries
- Evidence: Sync logs only show ~13 nodes processed

## Next Steps

1. **Run `/keys` in Telegram** (not mesh) to get full debug output
2. **Look for lines starting with "[DEBUG] DEBUG /keys:"**
3. **Share at least 20 lines of output** including:
   - How many entries in interface.nodes
   - Sample node IDs
   - Whether any keys are found

4. **If no debug lines appear**, it means:
   - `DEBUG_MODE` is not actually `True`, OR
   - The debug_print() calls are not executing, OR
   - Logs are being filtered/truncated

## Test Command

```bash
# Check DEBUG_MODE is enabled
grep "^DEBUG_MODE" /home/dietpi/bot/config.py

# Run /keys and capture ALL output
journalctl -u meshtastic-bot -f --no-pager | tee /tmp/keys_debug.log

# Then in Telegram, send: /keys

# After receiving response, stop journalctl (Ctrl+C) and check:
grep "DEBUG /keys" /tmp/keys_debug.log
```

## Expected vs Actual Behavior

### Expected (with DEBUG_MODE=True):
```
[DEBUG] DEBUG /keys: interface.nodes has 157 entries
[DEBUG] DEBUG /keys: Checking 157 nodes from traffic
[DEBUG] DEBUG /keys: Sample node IDs: [382653944, 305419896, ...]
[DEBUG] DEBUG /keys: Node 382653944 has key: True
[DEBUG] DEBUG /keys: Node 305419896 has key: True
```

### Actual (what we're seeing):
```
[No debug lines at all]
/keys returns: 157 nodes, 0 with keys
```

This strongly suggests either:
1. The debug code is not executing (check line 1343-1354 in network_commands.py)
2. Logs are being truncated by systemd
3. DEBUG_MODE is False despite what user thinks

## Verification Checklist

- [ ] Confirm `DEBUG_MODE = True` in `/home/dietpi/bot/config.py`
- [ ] Restart bot after setting DEBUG_MODE
- [ ] Run `/keys` in Telegram (NOT mesh - mesh truncates output)
- [ ] Check for "DEBUG /keys" in logs
- [ ] If no debug output, check if `debug_print()` function works at all
- [ ] Share COMPLETE journalctl output (not just snippets)
