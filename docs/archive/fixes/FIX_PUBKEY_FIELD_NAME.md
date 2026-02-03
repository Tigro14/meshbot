# Fix: Public Key Field Name Issue

## Problem Discovered

After 8 hours of traffic, the `/keys` command showed:
```
Nœuds actifs: 147
✅ Avec clé publique: 0
❌ Sans clé publique: 147
```

No public keys were being extracted from NODEINFO packets!

## Root Cause

The code was only checking for `publicKey` (camelCase), but the Meshtastic protobuf library uses `public_key` (snake_case with underscore).

### Protobuf Definition

From `mesh.proto`:
```protobuf
message User {
  string id = 1;
  string long_name = 2;
  string short_name = 3;
  bytes macaddr = 4;
  HardwareModel hw_model = 5;
  Role role = 6;
  bytes public_key = 7;  // <-- underscore, not camelCase!
}
```

### What Was Wrong

```python
# OLD CODE - Only checked camelCase
public_key = user_info.get('publicKey')  # ❌ Returns None!
```

When Meshtastic decodes a NODEINFO packet:
```python
packet = {
    'decoded': {
        'user': {
            'longName': 'TestNode',
            'public_key': b'\x01\x02\x03...'  # ← underscore field name!
        }
    }
}
```

Result: `user_info.get('publicKey')` returned `None` every time!

## The Fix

Check **both** field name variants:

```python
# NEW CODE - Try both field names
public_key = user_info.get('public_key') or user_info.get('publicKey')
```

This handles:
1. **Protobuf style**: `public_key` (underscore) - from NODEINFO packets
2. **Dict style**: `publicKey` (camelCase) - from JSON or manually created entries

### Files Modified

1. **node_manager.py** - 3 locations:
   - `update_node_from_packet()` - Extract from NODEINFO packets
   - `update_node_database()` - Extract from interface.nodes
   - `sync_pubkeys_to_interface()` - Inject into interface.nodes (set both!)

2. **handlers/command_handlers/network_commands.py** - 2 locations:
   - `_check_node_keys()` - Check key presence
   - `_check_all_keys()` - Count nodes with keys

### Injection Strategy

When injecting keys into `interface.nodes`, we set **both** field names:

```python
user_info['public_key'] = public_key   # For protobuf compatibility
user_info['publicKey'] = public_key    # For dict access compatibility
```

This ensures maximum compatibility with:
- Meshtastic library's internal use (expects `public_key`)
- Our own code accessing via dict (may use `publicKey`)

## Testing

Updated test suite to verify both field names work:

```python
# Test protobuf-style
packet1 = {'decoded': {'user': {'public_key': b'...'} } }
nm.update_node_from_packet(packet1)
assert nm.node_names[node_id]['publicKey'] == b'...'  # ✓

# Test dict-style  
packet2 = {'decoded': {'user': {'publicKey': 'ABC...'} } }
nm.update_node_from_packet(packet2)
assert nm.node_names[node_id]['publicKey'] == 'ABC...'  # ✓
```

## Expected Results After Fix

After deploying this fix and waiting for NODEINFO packets:

```
🔑 État des clés publiques PKI
   (Nœuds vus dans les 48h)

Nœuds actifs: 147
✅ Avec clé publique: 145  ← Keys now extracted!
❌ Sans clé publique: 2    ← Only nodes without NODEINFO
```

The bot should now:
1. ✅ Extract public keys from NODEINFO packets
2. ✅ Log "🔑 Clé publique extraite pour NodeName"
3. ✅ Store keys in `node_names.json`
4. ✅ Inject keys into `interface.nodes`
5. ✅ Enable DM decryption immediately

## Verification Steps

1. **Check logs for key extraction:**
   ```
   [DEBUG] 📱 Nouveau: NodeName (12345678)
   [DEBUG] 🔑 Clé publique extraite pour NodeName
   ```

2. **Check node_names.json:**
   ```json
   {
     "305419896": {
       "name": "NodeName",
       "publicKey": "..."  ← Should have data, not null
     }
   }
   ```

3. **Run /keys command:**
   ```
   ✅ Avec clé publique: > 0  ← Should show count
   ```

4. **Test DM decryption:**
   - Send DM to bot
   - Check logs - should show decrypted text, not "ENCRYPTED"

## Why This Wasn't Caught Earlier

1. **Test mocks used camelCase**: Test data had `publicKey`, which worked in tests
2. **No runtime validation**: No warning when field returned `None`
3. **Silent failure**: Code continued without error when no key found
4. **Documentation ambiguity**: Some Meshtastic docs show camelCase, others underscore

## Lessons Learned

1. **Always check protobuf definitions** for actual field names
2. **Test with real data**, not just mocks
3. **Add logging** when extracting critical data (key extraction now logs)
4. **Handle both variants** when dealing with protobuf/dict conversion

---

**Status**: ✅ Fixed  
**Commit**: See next commit  
**Impact**: HIGH - Enables public key extraction for all nodes
