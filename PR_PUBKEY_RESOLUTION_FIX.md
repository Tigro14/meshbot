# Pull Request: Fix PubKey Prefix Resolution for MeshCore-CLI DMs

## Summary

This PR fixes a critical issue where the bot could not respond to DMs from meshcore-cli users because it couldn't resolve the sender's node ID from the provided `pubkey_prefix`.

## Problem

When receiving DMs via meshcore-cli, the bot received events with a `pubkey_prefix` field (12-character hex string like `'a3fe27d34ac0'`), but could not match it to a node ID because:

1. meshcore-cli sends: `pubkey_prefix = 'a3fe27d34ac0'` (hex format)
2. node_manager stores: `publicKey = 'o/4n00rAAAA...'` (base64 format)
3. Direct string comparison: `'o/4n00rAAAA...'.startswith('a3fe27d34ac0')` → Always `False`

This resulted in:
- Sender ID falling back to `0xFFFFFFFF` (unknown)
- Bot unable to send responses
- Error: "Impossible d'envoyer à l'adresse broadcast 0xFFFFFFFF"

## Solution

### 1. Fixed `find_node_by_pubkey_prefix()` (node_manager.py)

- **Before**: Direct string comparison between formats
- **After**: Convert base64 → bytes → hex before comparison
- **Support**: hex, base64, and bytes publicKey formats

### 2. Added `lookup_contact_by_pubkey_prefix()` (meshcore_cli_wrapper.py)

- Extracts unknown senders from meshcore-cli's contact database
- Automatically adds them to node_manager
- Persists to disk for future lookups

### 3. Enhanced DM Event Handling (meshcore_cli_wrapper.py)

- First tries local node_manager lookup
- Falls back to meshcore-cli contact extraction if not found
- Automatically populates missing contacts

## Changes

### Modified Files

1. **node_manager.py**
   - Fixed `find_node_by_pubkey_prefix()` method
   - Added base64 decoding logic
   - Added support for all publicKey formats

2. **meshcore_cli_wrapper.py**
   - Added `lookup_contact_by_pubkey_prefix()` method (144 lines)
   - Updated `_on_contact_message()` DM handling
   - Added automatic contact extraction fallback

### Test Files Added

1. **test_pubkey_resolution_fix.py**
   - 4 unit tests covering all scenarios
   - Tests base64, bytes, and hex key formats
   - All tests passing (4/4)

2. **demo_pubkey_resolution_fix.py**
   - Comprehensive demonstration script
   - Shows before/after behavior
   - Real-world log comparison

### Documentation Added

1. **PUBKEY_RESOLUTION_FIX.md**
   - Complete problem analysis
   - Solution architecture
   - Usage examples
   - Troubleshooting guide

## Testing

### Unit Tests

```bash
$ python3 test_pubkey_resolution_fix.py
✅ PASS: Base64 Key Matching
✅ PASS: Bytes Key Matching
✅ PASS: Hex Key Matching
✅ PASS: Unknown Prefix Handling

4/4 tests passed
✅ ALL TESTS PASSED
```

### Demo

```bash
$ python3 demo_pubkey_resolution_fix.py
# Shows detailed before/after comparison
```

## Expected Behavior

### Before Fix
```
[DEBUG] 🔍 [MESHCORE-DM] Tentative résolution pubkey_prefix: a3fe27d34ac0
[DEBUG] ⚠️ No node found with pubkey prefix a3fe27d34ac0
[INFO]  📨 MESSAGE BRUT: 'Coucou' | from=0xffffffff
[ERROR] ❌ Impossible d'envoyer à l'adresse broadcast 0xFFFFFFFF
```

### After Fix
```
[DEBUG] 🔍 [MESHCORE-DM] Tentative résolution pubkey_prefix: a3fe27d34ac0
[DEBUG] 🔍 Found node 0x0de3331e with pubkey prefix a3fe27d34ac0
[INFO]  ✅ [MESHCORE-DM] Résolu pubkey_prefix a3fe27d34ac0 → 0x0de3331e
[INFO]  📬 [MESHCORE-DM] De: 0x0de3331e | Message: Coucou
[INFO]  ✅ Réponse envoyée à tigro t1000E
```

## Benefits

✅ Bot can now respond to DMs from meshcore-cli users
✅ No more "unknown sender" errors
✅ Automatic contact discovery and storage
✅ Works with all publicKey storage formats
✅ Backward compatible with existing node_names.json
✅ Zero migration required

## Migration

**No migration needed!**

- Backward compatible with existing installations
- Works with existing node_names.json files
- Automatically handles all publicKey formats
- No configuration changes required

## Related Issues

Fixes the issue described in logs:
```
Jan 20 20:02:38 DietPi meshtastic-bot[46792]: [DEBUG] ⚠️ No node found with pubkey prefix a3fe27d34ac0
Jan 20 20:02:38 DietPi meshtastic-bot[46792]: [ERROR] ❌ Impossible d'envoyer à l'adresse broadcast 0xFFFFFFFF
```

## Checklist

- [x] Code changes implemented
- [x] Unit tests added and passing
- [x] Demo script created
- [x] Documentation written
- [x] Backward compatibility verified
- [x] No breaking changes
- [ ] Tested with real meshcore-cli DMs (requires production testing)

## Statistics

- **Files modified**: 2 (node_manager.py, meshcore_cli_wrapper.py)
- **Lines added**: 913 (including tests and docs)
- **Tests added**: 4 unit tests
- **Tests passing**: 4/4 (100%)
- **Documentation**: Complete

## Notes for Reviewers

1. The fix is **backward compatible** - existing installations will work without changes
2. The automatic contact extraction is **optional** - if meshcore-cli doesn't provide contacts, the fix still improves local lookups
3. All tests are **self-contained** and don't require external dependencies
4. The documentation includes **troubleshooting** for common issues

## Next Steps

After merging, users should:

1. Pull latest changes
2. Restart the bot
3. Test with DMs from meshcore-cli users
4. Verify no more "unknown sender" errors

The fix will automatically:
- Convert existing publicKeys for comparison
- Extract new contacts from meshcore-cli
- Store them for future lookups
