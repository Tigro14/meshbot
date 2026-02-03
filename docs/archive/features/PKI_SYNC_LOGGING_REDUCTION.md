# PKI Sync Logging Reduction

**Date**: 2026-01-04  
**Issue**: Excessive INFO logging during TCP reconnections when MQTT disabled  
**Solution**: Move per-key processing logs from INFO to DEBUG level

---

## Problem Statement

When MQTT neighbor collection is disabled (`MQTT_NEIGHBOR_ENABLED = False`), the bot experiences more frequent TCP disconnections and reconnections. Each reconnection triggers a full PKI (Public Key Infrastructure) sync to restore all public keys to the new `interface.nodes` object.

### Log Spam Example

During each reconnection, the following pattern was logged at INFO level for **every node** with a public key:

```
Jan 04 21:16:57 DietPi meshtastic-bot[10276]: [INFO] ✅ Reconnexion TCP réussie (background)
Jan 04 21:16:57 DietPi meshtastic-bot[10276]: [INFO]    Processing Meshtastic 5071 (0x2bde5071): has key in DB
Jan 04 21:16:57 DietPi meshtastic-bot[10276]: [INFO]       Not in interface.nodes yet - creating entry
Jan 04 21:16:57 DietPi meshtastic-bot[10276]: [INFO]       ✅ Created node in interface.nodes with key
Jan 04 21:16:57 DietPi meshtastic-bot[10276]: [INFO]    Processing Node2 (0x12345678): has key in DB
Jan 04 21:16:57 DietPi meshtastic-bot[10276]: [INFO]       Key already present and matches
... [repeated for every node] ...
```

### Impact

With 20-30 nodes in the database:
- **60-90+ INFO log lines per reconnection**
- Reconnections every 5-10 minutes when MQTT disabled
- **720-1080 INFO log lines per hour** from PKI sync alone
- Logs become difficult to read and troubleshoot
- Increased log storage usage

---

## Root Cause

The PKI sync process (`node_manager.py::sync_pubkeys_to_interface()`) was logging at INFO level for:
1. Each node being processed (line 707)
2. Whether node was found in interface.nodes (line 721)
3. Whether key was injected or already present (lines 735, 737)
4. Whether new node entry was created (lines 751, 764)

This verbose logging was originally added for diagnostic purposes during development of the DM decryption feature, but became excessive in production with frequent reconnections.

---

## Solution

### Approach: Debug-Level Per-Node Logging

Move per-node processing logs from INFO to DEBUG level while preserving summary information at INFO level.

### Changes Made

**File**: `node_manager.py`

Changed 6 log statements from `info_print` to `debug_print`:

```python
# Line 707: Node processing
- info_print(f"   Processing {node_name} (0x{node_id:08x}): has key in DB")
+ debug_print(f"   Processing {node_name} (0x{node_id:08x}): has key in DB")

# Line 721: Node lookup
- info_print(f"      Found in interface.nodes with key: {key}")
+ debug_print(f"      Found in interface.nodes with key: {key}")

# Line 735: Key injection
- info_print(f"      ✅ Injected key into existing node")
+ debug_print(f"      ✅ Injected key into existing node")

# Line 737: Key already present
- info_print(f"      ℹ️ Key already present and matches")
+ debug_print(f"      ℹ️ Key already present and matches")

# Line 751: Creating new entry
- info_print(f"      Not in interface.nodes yet - creating entry")
+ debug_print(f"      Not in interface.nodes yet - creating entry")

# Line 764: Node created
- info_print(f"      ✅ Created node in interface.nodes with key")
+ debug_print(f"      ✅ Created node in interface.nodes with key")
```

**Preserved at INFO level**:
- Sync start message
- Current interface.nodes count
- Total keys to sync
- Sync completion summary

---

## Results

### Before vs After

#### BEFORE (20 nodes):
```
[INFO] 🔄 Starting public key synchronization to interface.nodes...
[INFO]    Current interface.nodes count: 0
[INFO]    Keys to sync from node_names: 20
[INFO]    Processing Node1 (0x12345678): has key in DB
[INFO]       Not in interface.nodes yet - creating entry
[INFO]       ✅ Created node in interface.nodes with key
[INFO]    Processing Node2 (0x87654321): has key in DB
[INFO]       Not in interface.nodes yet - creating entry
[INFO]       ✅ Created node in interface.nodes with key
... [56+ more INFO lines] ...
[INFO] ✅ SYNC COMPLETE: 20 public keys synchronized to interface.nodes
```
**Total**: ~63 INFO lines per reconnection

#### AFTER (20 nodes):
```
[INFO] 🔄 Starting public key synchronization to interface.nodes...
[INFO]    Current interface.nodes count: 0
[INFO]    Keys to sync from node_names: 20
[DEBUG]   Processing Node1 (0x12345678): has key in DB
[DEBUG]      Not in interface.nodes yet - creating entry
[DEBUG]      ✅ Created node in interface.nodes with key
... [56+ DEBUG lines] ...
[INFO] ✅ SYNC COMPLETE: 20 public keys synchronized to interface.nodes
```
**Total**: 4 INFO lines + 60 DEBUG lines per reconnection

### Improvement Metrics

- **INFO log lines reduced**: 63 → 4 (**93.7% reduction**)
- **Per-node processing**: Moved to DEBUG (invisible in normal logs)
- **Summary information**: Preserved at INFO level
- **Hourly impact**: 720 INFO lines/hour → 48 INFO lines/hour (with reconnections every 5 min)

---

## Benefits

1. **Cleaner Logs**
   - Only essential summary at INFO level
   - Per-node details moved to DEBUG
   - Easier to spot actual issues

2. **Reduced Storage**
   - Less disk usage for logs
   - Lower log rotation frequency
   - Better for embedded systems (Raspberry Pi)

3. **Better Signal-to-Noise**
   - Important events stand out
   - Not buried in PKI sync details
   - Faster troubleshooting

4. **Debug Mode Available**
   - Full details when needed
   - Enable with `DEBUG_MODE = True`
   - No loss of diagnostic capability

5. **Performance**
   - No change (logging is fast)
   - Only affects what gets printed
   - Same sync efficiency

---

## Testing

### Test Suite: `test_pki_sync_logging.py`

Verifies the logging reduction:

```bash
$ python3 test_pki_sync_logging.py
======================================================================
TEST: PKI Sync Logging Reduction
======================================================================

✓ Summary INFO logs found: 4
✓ Per-key processing DEBUG logs: 3
✓ Key injection DEBUG logs: 3
✓ Per-key INFO logs (should be 0): 0

======================================================================
✅ TEST PASSED: PKI sync logging reduced successfully
======================================================================
```

**Test Coverage**:
- Verifies per-key processing at DEBUG level
- Confirms summary at INFO level
- Validates no excessive INFO logging
- Tests with multiple keys

### Demonstration: `demo_pki_sync_logging_reduction.py`

Shows before/after comparison with real-world scenarios:
- 20-node network example
- Hourly log volume calculations
- Improvement metrics
- Impact analysis

---

## Usage

### Normal Operation

Default behavior (recommended):
```python
# config.py
DEBUG_MODE = False
```

Logs will show:
```
[INFO] 🔄 Starting public key synchronization...
[INFO]    Current interface.nodes count: 0
[INFO]    Keys to sync from node_names: 20
[INFO] ✅ SYNC COMPLETE: 20 public keys synchronized
```

### Debug Mode

When troubleshooting:
```python
# config.py
DEBUG_MODE = True
```

Logs will show all details:
```
[INFO] 🔄 Starting public key synchronization...
[DEBUG]   Processing Node1 (0x12345678): has key in DB
[DEBUG]      Not in interface.nodes yet - creating entry
[DEBUG]      ✅ Created node in interface.nodes with key
... [full details for all nodes] ...
[INFO] ✅ SYNC COMPLETE: 20 public keys synchronized
```

---

## When to Use DEBUG Mode

Enable `DEBUG_MODE = True` when:
- Troubleshooting DM decryption issues
- Investigating key sync problems
- Diagnosing TCP reconnection behavior
- Validating node database contents
- Verifying PKI sync correctness

Normal operation: Keep `DEBUG_MODE = False`

---

## Real-World Impact

### Scenario: Bot with 25 nodes, MQTT disabled, TCP reconnects every 5 minutes

#### BEFORE:
- 12 reconnections/hour × 70 INFO lines = **840 INFO lines/hour**
- Logs difficult to read due to PKI sync spam
- Hard to spot actual issues

#### AFTER:
- 12 reconnections/hour × 4 INFO lines = **48 INFO lines/hour**
- Clean, readable logs with essential information
- **94.3% reduction** in PKI-related INFO log volume
- Easy to identify real problems

---

## Related Files

- `node_manager.py` - PKI sync implementation
- `main_bot.py` - TCP reconnection logic (calls sync with force=True)
- `test_pki_sync_logging.py` - Test suite
- `demo_pki_sync_logging_reduction.py` - Before/after demonstration
- `PUBKEY_SYNC_OPTIMIZATION.md` - Related optimization (periodic sync skip)

---

## Backward Compatibility

✅ **Fully backward compatible**:
- No changes to sync logic or functionality
- Only log level changes
- DEBUG mode provides same detail as before
- Summary information still at INFO level
- No config changes required

---

## Future Considerations

This change is part of a broader effort to reduce log spam:

1. **PUBKEY_SYNC_OPTIMIZATION.md**: Skip periodic sync when keys already present
2. **This fix**: Reduce per-key logging during forced syncs
3. **Future**: Consider configurable log levels per-component

Combined with the periodic sync optimization, these changes significantly improve log readability in production.

---

## Conclusion

The PKI sync logging reduction successfully addresses excessive INFO logging during TCP reconnections:

✅ **Problem Solved**: 93.7% reduction in PKI-related INFO log volume  
✅ **Summary Preserved**: Essential information still at INFO level  
✅ **Debug Available**: Full details accessible when needed  
✅ **Production Ready**: Cleaner logs for easier troubleshooting  
✅ **Tested**: Comprehensive test suite validates behavior

The bot now produces clean, readable logs during TCP reconnections while maintaining full diagnostic capability in DEBUG mode.

---

**Status**: ✅ Implemented and Tested  
**Version**: 1.0  
**Date**: 2026-01-04
