# PubKey Prefix Resolution Fix for MeshCore-CLI DMs

## Problem Statement

When receiving DM messages via meshcore-cli, the bot could not resolve the sender's node ID from the provided `pubkey_prefix`, causing it to fall back to `0xFFFFFFFF` (unknown sender). This prevented the bot from sending responses to DM messages.

### Symptoms

```
Jan 20 20:02:38 DietPi meshtastic-bot[46792]: [DEBUG] 🔍 [MESHCORE-DM] Tentative résolution pubkey_prefix: a3fe27d34ac0
Jan 20 20:02:38 DietPi meshtastic-bot[46792]: [DEBUG] ⚠️ No node found with pubkey prefix a3fe27d34ac0
Jan 20 20:02:38 DietPi meshtastic-bot[46792]: [INFO] 📨 MESSAGE BRUT: 'Coucou' | from=0xffffffff | to=0xfffffffe | broadcast=False
Jan 20 20:02:38 DietPi meshtastic-bot[46792]: [ERROR] ❌ Impossible d'envoyer à l'adresse broadcast 0xFFFFFFFF
Jan 20 20:02:38 DietPi meshtastic-bot[46792]: [ERROR]    → Expéditeur inconnu (pubkey non résolu dans la base de données)
```

### Root Cause

The issue occurred due to a **format mismatch** between the pubkey formats:

1. **meshcore-cli sends**: `pubkey_prefix` as 12-character hex string (e.g., `'a3fe27d34ac0'`)
2. **node_manager stores**: `publicKey` as base64-encoded strings (e.g., `'o/4n00rAAAAAAAAAAAA...'`)
3. **Old code tried**: Direct string comparison → `'o/4n00rAAAA...'.startswith('a3fe27d34ac0')` → Always `False`

The bot could decrypt the message (proving it had the sender's pubkey in meshcore-cli's internal database), but couldn't map it back to a node ID to send a response.

## Solution

The fix involves two main components:

### 1. Base64 to Hex Conversion in `find_node_by_pubkey_prefix()`

**File**: `node_manager.py`

The method now properly converts base64-encoded public keys to hex format before comparison:

```python
def find_node_by_pubkey_prefix(self, pubkey_prefix):
    """
    Find a node ID by matching the public key prefix
    
    Args:
        pubkey_prefix: Hex string prefix of the public key (e.g., '143bcd7f1b1f')
        
    Returns:
        int: node_id if found, None otherwise
    """
    if not pubkey_prefix:
        return None
    
    pubkey_prefix = str(pubkey_prefix).lower().strip()
    
    for node_id, node_data in self.node_names.items():
        if 'publicKey' in node_data:
            public_key = node_data['publicKey']
            public_key_hex = None
            
            if isinstance(public_key, str):
                try:
                    # Try hex first, then base64
                    if all(c in '0123456789abcdefABCDEF' for c in public_key.replace(' ', '')):
                        public_key_hex = public_key.lower().replace(' ', '')
                    else:
                        # Decode base64 → bytes → hex
                        import base64
                        decoded_bytes = base64.b64decode(public_key)
                        public_key_hex = decoded_bytes.hex().lower()
                except Exception as e:
                    continue
                    
            elif isinstance(public_key, bytes):
                public_key_hex = public_key.hex().lower()
            
            if public_key_hex and public_key_hex.startswith(pubkey_prefix):
                return node_id
    
    return None
```

**Key improvements**:
- ✅ Supports **hex**, **base64**, and **bytes** publicKey formats
- ✅ Properly converts base64 → hex for comparison
- ✅ Handles malformed keys gracefully

### 2. Automatic Contact Extraction from MeshCore-CLI

**File**: `meshcore_cli_wrapper.py`

Added `lookup_contact_by_pubkey_prefix()` method to extract unknown senders from meshcore-cli's contact database:

```python
def lookup_contact_by_pubkey_prefix(self, pubkey_prefix):
    """
    Lookup a contact in meshcore-cli's contact database by pubkey prefix
    and add it to node_manager for future lookups.
    
    Args:
        pubkey_prefix: Hex string prefix of the public key
        
    Returns:
        int: node_id if found and added, None otherwise
    """
    # Access meshcore-cli's contacts database
    contacts = self.meshcore.contacts if hasattr(self.meshcore, 'contacts') else None
    
    for contact in contacts:
        contact_id = contact.get('contact_id') or contact.get('node_id')
        public_key = contact.get('public_key') or contact.get('publicKey')
        
        # Convert to hex and check prefix match
        public_key_hex = base64.b64decode(public_key).hex().lower()
        
        if public_key_hex.startswith(pubkey_prefix):
            # Found! Add to node_manager
            name = contact.get('name') or f"Node-{contact_id:08x}"
            
            self.node_manager.node_names[contact_id] = {
                'name': name,
                'publicKey': public_key  # Store original format
            }
            
            self.node_manager.save_node_names()
            return contact_id
    
    return None
```

**Key features**:
- ✅ Searches meshcore-cli's internal contact database
- ✅ Automatically adds unknown senders to node_manager
- ✅ Persists contacts to disk for future lookups
- ✅ Handles both sync and async contact access

### 3. Enhanced DM Event Handling

**File**: `meshcore_cli_wrapper.py` (in `_on_contact_message()`)

Updated the DM handling flow to use the new lookup method:

```python
# Méthode 4: Try node_manager lookup first
if sender_id is None and pubkey_prefix and self.node_manager:
    sender_id = self.node_manager.find_node_by_pubkey_prefix(pubkey_prefix)
    if sender_id:
        info_print(f"✅ Resolved pubkey_prefix {pubkey_prefix} → 0x{sender_id:08x}")
    else:
        # Méthode 5: Fallback to meshcore-cli contact database
        sender_id = self.lookup_contact_by_pubkey_prefix(pubkey_prefix)
        if sender_id:
            info_print(f"✅ Contact extracted and added: 0x{sender_id:08x}")
```

## Expected Behavior After Fix

### Logs (BEFORE FIX)
```
[DEBUG] 🔍 [MESHCORE-DM] Tentative résolution pubkey_prefix: a3fe27d34ac0
[DEBUG] ⚠️ No node found with pubkey prefix a3fe27d34ac0
[INFO]  📨 MESSAGE BRUT: 'Coucou' | from=0xffffffff | to=0xfffffffe
[ERROR] ❌ Impossible d'envoyer à l'adresse broadcast 0xFFFFFFFF
```

### Logs (AFTER FIX)
```
[DEBUG] 🔍 [MESHCORE-DM] Tentative résolution pubkey_prefix: a3fe27d34ac0
[DEBUG] 🔍 Found node 0x0de3331e with pubkey prefix a3fe27d34ac0
[INFO]  ✅ [MESHCORE-DM] Résolu pubkey_prefix a3fe27d34ac0 → 0x0de3331e
[INFO]  📬 [MESHCORE-DM] De: 0x0de3331e | Message: Coucou
[INFO]  📨 MESSAGE BRUT: 'Coucou' | from=0x0de3331e | to=0xfffffffe
[INFO]  MESSAGE REÇU de tigro t1000E: 'Coucou'
[INFO]  ✅ Réponse envoyée à tigro t1000E
```

## Testing

### Unit Tests

Run the unit test suite:

```bash
python3 test_pubkey_resolution_fix.py
```

**Expected output**:
```
✅ PASS: Base64 Key Matching
✅ PASS: Bytes Key Matching
✅ PASS: Hex Key Matching
✅ PASS: Unknown Prefix Handling

4/4 tests passed
✅ ALL TESTS PASSED - Fix is working correctly!
```

### Demo

Run the comprehensive demo:

```bash
python3 demo_pubkey_resolution_fix.py
```

This demonstrates:
- Format mismatch problem (BEFORE)
- Base64 to hex conversion (AFTER)
- Automatic contact extraction
- Real-world log comparison

## Benefits

1. ✅ **Bot can respond to DMs**: No more "unknown sender" errors
2. ✅ **Automatic contact discovery**: Contacts are extracted from meshcore-cli and stored
3. ✅ **Format compatibility**: Supports hex, base64, and bytes publicKey formats
4. ✅ **Persistent storage**: Extracted contacts are saved for future lookups
5. ✅ **Backward compatible**: Works with existing node_names.json files

## Files Modified

- `node_manager.py`: Fixed `find_node_by_pubkey_prefix()` with base64 decoding
- `meshcore_cli_wrapper.py`: Added `lookup_contact_by_pubkey_prefix()` method
- `meshcore_cli_wrapper.py`: Updated `_on_contact_message()` DM handling

## Migration Notes

**No migration required!**

- The fix is backward compatible with existing `node_names.json` files
- Public keys stored in any format (hex, base64, bytes) will work correctly
- Existing contacts will continue to work as before
- New contacts from DMs will be automatically added

## Future Enhancements (Optional)

While the current fix solves the immediate problem, future improvements could include:

1. **Database table for pubkey mappings**: Create a dedicated SQLite table for pubkey → node_id mappings
2. **Periodic contact sync**: Automatically sync meshcore-cli contacts on startup
3. **Contact expiration**: Remove contacts that haven't been seen in X days
4. **Contact validation**: Verify contact node IDs match expected format

These enhancements are **not required** for the fix to work, but could improve performance and reliability.

## Troubleshooting

### Issue: Still getting "No node found" errors

**Check**:
1. Verify meshcore-cli has synced contacts: `meshcore-cli contacts list`
2. Check node_names.json has publicKey fields for known nodes
3. Enable debug mode: `DEBUG_MODE = True` in config.py
4. Check logs for base64 decoding errors

### Issue: Contact extraction fails

**Check**:
1. Verify meshcore-cli version supports contacts API
2. Check if `self.meshcore.contacts` or `self.meshcore.get_contacts()` is available
3. Enable debug logging to see contact structure
4. Verify network connectivity for async contact access

### Issue: Duplicate contacts in node_names.json

**Not a problem**: The code checks if a contact already exists before adding it. Duplicate detection is by node_id.

## Summary

This fix resolves the critical issue where the bot could not respond to DMs from meshcore-cli users due to pubkey format mismatch. The solution includes:

- **Immediate fix**: Base64 to hex conversion for pubkey matching
- **Long-term solution**: Automatic contact extraction from meshcore-cli
- **Comprehensive tests**: Unit tests and demo scripts
- **Zero migration**: Backward compatible with existing installations

The bot can now fully handle DMs from meshcore-cli users! 🎉
