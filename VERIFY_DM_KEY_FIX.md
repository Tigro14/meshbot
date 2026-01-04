# DM Key Lookup Fix - Quick Verification Guide

This guide shows how to verify that the DM key lookup fix is working correctly in your deployment.

---

## Quick Test

### Step 1: Check You Have the Fix

```bash
cd /path/to/meshbot
git log --oneline -3
```

You should see:
```
1f6bcef Add comprehensive documentation for DM key lookup fix
a578434 Fix DM key lookup with multi-format search
```

### Step 2: Verify Code Changes

```bash
grep -A 5 "_find_node_in_interface" traffic_monitor.py | head -10
```

Should show:
```python
def _find_node_in_interface(self, node_id, interface):
    """
    Find node info in interface.nodes trying multiple key formats.
```

---

## Verification in Production

### What to Look For in Logs

**BEFORE the fix** (when encrypted DM arrives):
```
[DEBUG] 🔐 Encrypted DM from 0xa76f40da to us - likely PKI encrypted
[DEBUG] ❌ Missing public key for sender 0xa76f40da
```

**AFTER the fix** (when encrypted DM arrives):
```
[DEBUG] 🔐 Encrypted DM from 0xa76f40da to us - likely PKI encrypted
[DEBUG] 🔍 Found node 0xa76f40da in interface.nodes with key=!a76f40da (type=str)
[DEBUG] ✅ Sender's public key FOUND (matched with key format: !a76f40da)
[DEBUG]    Key preview: KzIbS2tRqpaFe45u...
```

### How to Test

1. **Find a node with public key**:
   ```
   Send to bot: /keys [node_name]
   ```
   Should show: `✅ Clé publique: PRÉSENTE`

2. **Have that node send you a DM**:
   ```
   From the node: Send "test" to bot
   ```

3. **Check bot logs**:
   ```bash
   journalctl -u meshbot -f | grep "Encrypted DM"
   ```

4. **Verify you see**:
   - ✅ `Found node 0x... in interface.nodes with key=...`
   - ✅ `Sender's public key FOUND (matched with key format: ...)`
   - ❌ NOT: `Missing public key for sender`

---

## Understanding the Fix

### What Was Wrong

The bot was looking for nodes in `interface.nodes` using only one key format (integer), but in TCP mode, nodes are stored with hex string keys like `"!a76f40da"`.

**Example**:
```python
# Old code - only tries integer
from_id = 0xa76f40da  # 2809086170 in decimal
node_info = nodes.get(from_id)  # ❌ Looks for key 2809086170

# But interface.nodes has:
interface.nodes = {
    "!a76f40da": { ... }  # Key is string, not int!
}
# Result: node_info is None (not found)
```

### What the Fix Does

The new code tries multiple key formats:

```python
# New code - tries all formats
search_keys = [
    2809086170,           # Integer
    "2809086170",         # String decimal
    "!a76f40da",          # Hex with prefix
    "a76f40da"            # Hex without prefix
]

for key in search_keys:
    if key in interface.nodes:
        node_info = interface.nodes[key]
        break  # Found it!
```

### Key Format by Connection Type

| Connection | Key Format | Example |
|------------|------------|---------|
| Serial | Integer | `2809086170` |
| TCP | Hex string | `"!a76f40da"` |
| Mixed | Varies | Both formats possible |

---

## Troubleshooting

### Still seeing "Missing public key"?

This is now CORRECT behavior if:

1. **Node hasn't broadcast NODEINFO yet**
   - Wait 15-30 minutes for automatic broadcast
   - Or manually request: `meshtastic --request-telemetry --dest a76f40da`

2. **Node firmware < 2.5.0**
   - Upgrade node firmware to 2.5.0+
   - Older firmware doesn't send public keys

3. **Interface connection issue**
   - Check `interface.nodes` is populated
   - Verify bot has network connectivity

### Verify key formats in your setup

Run the test script:
```bash
cd /path/to/meshbot
python3 test_dm_key_lookup_fix.py
```

Should show:
```
✅ ALL TESTS PASSED

Summary:
  • Multi-format key search works correctly
  • Real-world scenario from problem statement fixed
  • Backward compatibility maintained
```

### Check interface.nodes key format

Add temporary debug logging:
```python
# In traffic_monitor.py, after line 725:
interface = getattr(self.node_manager, 'interface', None)
if interface:
    nodes = getattr(interface, 'nodes', {})
    if nodes:
        sample_keys = list(nodes.keys())[:3]
        debug_print(f"🔍 Sample interface.nodes keys: {sample_keys}")
        debug_print(f"🔍 Key types: {[type(k).__name__ for k in sample_keys]}")
```

This shows what key format your interface uses.

---

## Rollback Instructions

If you need to revert this change (should not be necessary):

```bash
cd /path/to/meshbot
git revert 1f6bcef a578434
```

However, this fix has no known issues and is backward compatible.

---

## Related Commands

### Check `/keys` command still works

```
/keys
/keys [node_name]
```

Both should work correctly and show same results as before.

### Verify node database

```
/nodes
```

Should show all nodes including their names.

### Check encrypted packets

```
journalctl -u meshbot -f | grep -E "🔐|ENCRYPTED"
```

Watch for encrypted packet handling.

---

## FAQ

**Q: Will this fix decrypt my DMs automatically?**
A: No. This fix only helps the bot FIND public keys it already has. The Meshtastic library still handles actual decryption.

**Q: Do I need to change any config?**
A: No. This fix works automatically with existing configs.

**Q: Will this break existing functionality?**
A: No. The fix is backward compatible and maintains all existing behavior.

**Q: What if I don't use TCP mode?**
A: The fix works for both TCP and serial modes. In serial mode, it uses integer keys (as before).

**Q: How do I know if I need this fix?**
A: If `/keys` shows a node has a public key but DM decryption logs say "Missing public key", you need this fix.

---

## Success Indicators

✅ **Fix is working if you see**:
- Log line: `🔍 Found node 0x... in interface.nodes with key=...`
- Log line: `✅ Sender's public key FOUND (matched with key format: ...)`
- No more false "Missing public key" errors for nodes in `/keys`

❌ **Issue remains if you see**:
- Still: `❌ Missing public key for sender 0x...`
- When: `/keys [node]` shows `✅ Clé publique: PRÉSENTE`

If issue remains, check:
1. Is your code up to date? (`git pull`)
2. Did you restart the bot? (`sudo systemctl restart meshbot`)
3. Are you checking the right node?

---

## Additional Resources

- **DM_KEY_LOOKUP_FIX.md** - Complete technical documentation
- **demo_dm_key_lookup_fix.py** - Visual before/after demonstration
- **test_dm_key_lookup_fix.py** - Automated test suite
- **DM_DECRYPTION_2715.md** - DM encryption background

---

**Last Updated**: 2026-01-04  
**Fix Version**: a578434  
**Status**: ✅ Ready for production
