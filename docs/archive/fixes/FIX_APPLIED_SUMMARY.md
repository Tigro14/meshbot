# Fix Applied: Remove non-existent auto_update_contacts Parameter

## Issue Reported
Bot crashed on startup with:
```
TypeError: MeshCore.create_serial() got an unexpected keyword argument 'auto_update_contacts'
```

## Root Cause
The initial fix assumed that `auto_update_contacts` was a parameter accepted by `MeshCore.create_serial()`, but this parameter doesn't exist in the current meshcore-cli library API.

## Fix Applied (Commit a44fef5)

### Code Changes
**File**: `meshcore_cli_wrapper.py`

**Before**:
```python
self.meshcore = loop.run_until_complete(
    MeshCore.create_serial(
        self.port, 
        baudrate=self.baudrate, 
        debug=self.debug,
        auto_update_contacts=True  # ❌ Doesn't exist!
    )
)
```

**After**:
```python
self.meshcore = loop.run_until_complete(
    MeshCore.create_serial(self.port, baudrate=self.baudrate, debug=self.debug)
)
```

### Documentation Updates
Updated all documentation files to remove references to `auto_update_contacts`:
- ✅ `MESHCORE_CONTACTS_ENSURE_FIX.md` - Removed Fix #2 section
- ✅ `FIX_SUMMARY_CONTACTS.md` - Removed auto_update_contacts references
- ✅ `demo_meshcore_contacts_ensure_fix.py` - Updated demo output

## What Remains
The **main fix is still intact and functional**:

✅ `query_contact_by_pubkey_prefix()` now explicitly calls `ensure_contacts()` before querying
✅ Handles both async and sync implementations
✅ 10-second timeout prevents hanging
✅ Comprehensive error handling

## Expected Behavior
After pulling the latest changes:

1. ✅ Bot starts successfully (no more TypeError)
2. ✅ Bot calls `ensure_contacts()` when querying contacts
3. ✅ Bot should see all 19 contacts
4. ✅ Bot can resolve pubkey_prefix to sender_id
5. ✅ Bot can respond to DM messages

## Testing
User should:
1. Pull latest: `git pull origin copilot/investigate-bot-contact-issue`
2. Restart bot: `sudo systemctl restart meshbot`
3. Check logs: `journalctl -u meshbot -f`
4. Look for: `🔄 [MESHCORE-QUERY] Appel ensure_contacts()...`
5. Verify: `📊 [MESHCORE-QUERY] Nombre de contacts: 19`
6. Test DM: Send `/power` from mobile app
7. Confirm: Bot responds correctly

## Summary
- ❌ Removed: `auto_update_contacts=True` (doesn't exist in API)
- ✅ Kept: `ensure_contacts()` call (the actual fix)
- ✅ Result: Bot should now work correctly
