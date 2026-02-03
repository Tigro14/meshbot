# Fix for /keys Command with Node Argument

## Issue
The bot command `/keys a76f40d` (or any node ID/name) did not give any response, while `/keys` alone worked fine.

## Root Cause
The `_check_node_keys()` method in `handlers/command_handlers/network_commands.py` was only trying one key format when looking up nodes in `interface.nodes`:

```python
# BEFORE (line 1229)
node_info = nodes.get(node_id)
```

However, Meshtastic's `interface.nodes` dictionary can use different key formats:
- **Integer**: `2809086170` or `0xa76f40da`
- **String (decimal)**: `"2809086170"`
- **String (hex with !)**: `"!a76f40da"`
- **String (hex without !)**: `"a76f40da"`

When `_find_node()` returned a node_id in one format (e.g., integer), but `interface.nodes` used a different format (e.g., string), the lookup would fail silently, and no response would be sent to the user.

## Solution
Applied the same multi-format key search logic that was already working in `_check_all_keys()` to `_check_node_keys()`:

```python
# AFTER (lines 1227-1242)
# Vérifier les clés dans interface.nodes - essayer plusieurs formats de clés
nodes = getattr(self.interface, 'nodes', {})
node_info = None
search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]

debug_print(f"DEBUG /keys {search_term}: Trying keys {search_keys[:2]}... for node_id={node_id}")

for key in search_keys:
    if key in nodes:
        node_info = nodes[key]
        debug_print(f"DEBUG /keys {search_term}: FOUND with key={key} (type={type(key).__name__})")
        break

if node_info is None:
    debug_print(f"DEBUG /keys {search_term}: NOT FOUND in interface.nodes with any key format")
```

This ensures the node is found regardless of which key format `interface.nodes` uses.

## Files Changed
1. **handlers/command_handlers/network_commands.py**
   - Modified `_check_node_keys()` method (lines 1227-1242)
   - Replaced single `nodes.get(node_id)` with multi-format search loop
   - Added debug logging to track which format matched

## New Test File
1. **test_keys_multiformat.py** (new)
   - Comprehensive test suite for multi-format key lookup
   - Tests all 4 key formats individually
   - Verifies node is found with any format
   - Tests missing node case

## Test Results
All existing and new tests pass:

### test_keys_command.py ✅
- Basic key checking logic
- Missing key detection
- Message formatting
- Error handling

### test_keys_multiformat.py ✅ (NEW)
- Integer key format: `2809086170` → ✅ FOUND
- String key format: `"2809086170"` → ✅ FOUND
- Hex with ! format: `"!a76f40da"` → ✅ FOUND
- Hex without ! format: `"a76f40da"` → ✅ FOUND
- Missing node: → ✅ Correctly returns None

### test_keys_string_fix.py ✅
- String key format compatibility
- Traffic database decimal string handling

### test_keys_decimal_fix.py ✅
- Decimal vs hex parsing from SQLite
- Conversion to correct hex format

## Impact
- ✅ `/keys <node_id>` now works with any node ID format
- ✅ No breaking changes to existing functionality
- ✅ Consistent behavior with `/keys` (without argument)
- ✅ Users receive proper responses instead of silence
- ✅ Debug logging helps troubleshoot format issues

## Example Usage
```
User: /keys a76f40d
Bot: ✅ tigro t1000E: Clé OK (lMLv2Yk1...)

User: /keys tigro
Bot: ✅ tigro t1000E: Clé OK (lMLv2Yk1...)

User: /keys 2809086170
Bot: ✅ tigro t1000E: Clé OK (lMLv2Yk1...)
```

All formats now work correctly!

## Technical Details
The fix mirrors the same pattern used in `_check_all_keys()` (lines 1378-1393), ensuring consistency across the codebase. This approach:
1. Tries the node_id as-is first (fastest path for common case)
2. Falls back to string representation
3. Tries hex format with "!" prefix (Meshtastic convention)
4. Finally tries hex format without prefix

The order is optimized for the most common formats first, minimizing iteration overhead.
