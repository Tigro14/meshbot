# Fix: Sender Prefix Stripping Regression

## Problem Statement

From production logs (Feb 15 08:18:39):
```
[INFO][MC] 📢 [CHANNEL] Message de 0x16fad3dc sur canal 0: Tigro: /echo pas encore de neige ici
[DEBUG] 🔍 [ROUTER-DEBUG] _meshcore_dm=False | is_for_me=False | is_broadcast=True | to=0xffffffff
[INFO] MESSAGE REÇU de tigro PVCavityABIOT: 'Tigro: /echo pas encore de neige ici'
[INFO][MC] ✅ [CHANNEL] Message transmis au bot pour traitement
```

**Bot did not respond** - Regression after sender ID extraction fix.

## Root Cause

After implementing the sender ID extraction fix, `sender_id` is now correctly set to the actual sender (e.g., `0x16fad3dc`) instead of always being `0xFFFFFFFF`. However, the prefix stripping logic in `message_router.py` line 95 was checking for:

```python
if is_broadcast and sender_id == 0xFFFFFFFF and ': ' in message:
```

This condition was **never true** after the sender ID fix, so prefixes were never stripped!

## The Broken Flow

```
Step 1: Message received
"Tigro: /echo pas encore de neige ici"

Step 2: Sender correctly identified (NEW behavior)
sender_id = 0x16fad3dc ✅

Step 3: Router checks prefix stripping condition (OLD logic)
is_broadcast: True
sender_id == 0xFFFFFFFF: FALSE ❌ (0x16fad3dc != 0xFFFFFFFF)
Condition: FALSE → Prefix NOT stripped

Step 4: Message unchanged
"Tigro: /echo pas encore de neige ici"

Step 5: Command recognition check
message.startswith('/echo'): FALSE ❌
"Tigro: /echo..." does NOT start with '/echo'

Step 6: Command not recognized
No handler called → No response ❌
```

## Why This Happened

The fix chain created an incompatibility:

1. **First fix:** Extract sender from prefix → `sender_id = 0x16fad3dc` ✅
2. **Side effect:** Prefix stripping condition now always false ❌
3. **Result:** Commands not recognized anymore ❌

The prefix stripping logic was written assuming `sender_id` would always be `0xFFFFFFFF` for broadcasts. After correctly identifying the sender, this assumption broke.

## The Fix

Changed the condition in `handlers/message_router.py` line 95:

**Before (BROKEN):**
```python
if is_broadcast and sender_id == 0xFFFFFFFF and ': ' in message:
    # Strip prefix
```

**After (FIXED):**
```python
if is_broadcast and ': ' in message:
    # Strip prefix
```

The `sender_id == 0xFFFFFFFF` check was unnecessary and broke after the sender ID fix. We should strip the prefix for **any** broadcast message with the "Name: /command" pattern, regardless of the sender_id value.

## The Working Flow Now

```
Step 1: Message received
"Tigro: /echo pas encore de neige ici"

Step 2: Sender correctly identified
sender_id = 0x16fad3dc ✅

Step 3: Router checks prefix stripping condition (NEW logic)
is_broadcast: True ✅
': ' in message: True ✅
Condition: TRUE → Check pattern

Step 4: Pattern check
parts = ["Tigro", "/echo pas encore de neige ici"]
parts[1].startswith('/'): True ✅

Step 5: Strip prefix
message = "/echo pas encore de neige ici" ✅

Step 6: Command recognition check
message.startswith('/echo'): TRUE ✅

Step 7: Command processed
handle_echo() called → Response sent ✅
```

## Code Changes

### handlers/message_router.py

```diff
- if is_broadcast and sender_id == 0xFFFFFFFF and ': ' in message:
+ if is_broadcast and ': ' in message:
      parts = message.split(': ', 1)
      if len(parts) == 2 and parts[1].startswith('/'):
          original_message = message
          message = parts[1]  # Use only the command part
```

**Change:** Removed `sender_id == 0xFFFFFFFF` condition

**Why:** This condition was incompatible with the sender ID extraction fix

**Result:** Prefix now stripped for all broadcasts with the pattern

## Test Coverage

### Test Suite: `test_sender_prefix_stripping.py`

Three comprehensive tests:

1. **test_prefix_stripped_with_correct_sender_id**
   - Message: `"Tigro: /echo pas encore de neige ici"`
   - sender_id: `0x16fad3dc` (NOT `0xFFFFFFFF`)
   - Old logic: Would NOT strip (FALSE)
   - New logic: Would strip (TRUE) ✅
   - Result: `"/echo pas encore de neige ici"`

2. **test_prefix_not_stripped_for_non_commands**
   - Message: `"Tigro: Bonjour tout le monde"`
   - Pattern check: Has `:` but doesn't start with `/`
   - Result: Prefix kept (correct behavior)

3. **test_prefix_stripped_for_various_commands**
   - Tests: `/echo`, `/my`, `/weather`, `/bot`
   - All prefixes correctly stripped

## Impact Analysis

### Before This Fix
- ❌ No commands recognized on public channel
- ❌ All `/echo`, `/my`, `/weather`, etc. commands ignored
- ❌ Bot completely non-functional for public channel
- ❌ 100% failure rate for broadcast commands

### After This Fix
- ✅ All commands recognized correctly
- ✅ Prefix stripping works for any sender_id
- ✅ Compatible with sender ID extraction fix
- ✅ Bot fully functional

## Edge Cases

1. **Command with correct sender ID:** ✅ Works
   - `"Tigro: /echo test"` (sender_id=0x16fad3dc)

2. **Command with broadcast sender ID:** ✅ Works
   - `"User: /echo test"` (sender_id=0xFFFFFFFF)

3. **Non-command message:** ✅ Prefix kept
   - `"Tigro: Hello world"` → stays unchanged

4. **Message without prefix:** ✅ Unchanged
   - `"/echo test"` → stays as-is

5. **Multiple colons:** ✅ Handled
   - `"User: /echo test: message"` → `"/echo test: message"`

## Dependency Chain

This fix completes a chain of fixes:

1. **Sender ID extraction** (`896d13c`)
   - Extract sender from prefix
   - Set correct sender_id

2. **Own node filtering** (`e4e34f9`)
   - Allow broadcasts from own node
   - Only filter DMs

3. **Prefix stripping** (THIS FIX)
   - Remove sender_id check
   - Strip for all broadcasts

All three fixes must work together for the bot to function correctly.

## Deployment Notes

### No Configuration Changes
This is a pure logic fix requiring no configuration changes.

### Monitoring
After deployment, verify these log patterns:

**Success:**
```
[DEBUG] 🔧 [ROUTER] Stripped sender prefix from Public channel message
   Original: 'Tigro: /echo test'
   Cleaned:  '/echo test'
[DEBUG] 🎯 [ROUTER] Broadcast command detected
[INFO] ECHO PUBLIC de tigro: '/echo test'
```

### Verification Steps
1. Send public channel command: `/echo test from public`
2. Check logs for prefix stripping
3. Verify command is recognized
4. Confirm response is sent

## Rollback Plan

If issues occur, revert to:
```python
if is_broadcast and sender_id == 0xFFFFFFFF and ': ' in message:
```

**Warning:** This breaks sender ID extraction but restores prefix stripping for old behavior.

## Lessons Learned

1. **Cascading changes:** Fixing one issue can break related code
2. **Implicit assumptions:** Code assumed sender_id would always be 0xFFFFFFFF
3. **Test coverage:** Need integration tests, not just unit tests
4. **Logging:** Good logging helped identify the exact issue quickly

## Summary

**Problem:** Sender prefix not stripped after sender ID extraction fix

**Cause:** Prefix stripping checked for `sender_id == 0xFFFFFFFF`, incompatible with new behavior

**Solution:** Remove sender_id check, strip prefix for all broadcasts with pattern

**Result:** Bot now fully functional with both correct sender identification AND command recognition
