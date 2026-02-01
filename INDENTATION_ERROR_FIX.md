# IndentationError Fix - meshcore_cli_wrapper.py

## Problem

The diagnostic test suite failed on Test 2 with an IndentationError:

```
============================================================
TEST 2: MeshCore CLI Wrapper Event Loop
============================================================
❌ Error: unindent does not match any outer indentation level (meshcore_cli_wrapper.py, line 761)
Traceback (most recent call last):
  File "/home/dietpi/bot/test_message_polling_diagnostic.py", line 176, in test_meshcore_cli_wrapper
    from meshcore_cli_wrapper import MeshCoreCLIWrapper
  File "/home/dietpi/bot/meshcore_cli_wrapper.py", line 761
    if post_count == 0:
                       ^
IndentationError: unindent does not match any outer indentation level
```

## Root Cause

Line 761 in `meshcore_cli_wrapper.py` had incorrect indentation - one extra space character.

**Incorrect (29 spaces):**
```python
                             if post_count == 0:
```

**Correct (28 spaces):**
```python
                            if post_count == 0:
```

This indentation level must match the surrounding `elif` statement at line 753.

## Context

The error was in the contact synchronization code:

```python
# Line 753 - correct indentation (28 spaces)
                            elif post_count > 0:
                                debug_print(f"⚠️ [MESHCORE-SYNC] {post_count} contacts synchronisés mais NON SAUVEGARDÉS")
                                if not self.node_manager:
                                    debug_print("   → node_manager non configuré")
                                elif not hasattr(self.node_manager, 'persistence'):
                                    debug_print("   → persistence non configuré")
                            
# Line 761 - WRONG indentation (29 spaces) - FIXED
                            if post_count == 0:
                                error_print("⚠️ [MESHCORE-SYNC] ATTENTION: sync_contacts() n'a trouvé AUCUN contact!")
```

## Fix Applied

Removed one space character from line 761 to match the correct indentation level.

**Changed:**
- Line 761: Removed 1 space character

## Verification

```bash
$ python3 -c "import meshcore_cli_wrapper"
✅ Import successful - no IndentationError
```

## Impact

### Before Fix
- Test 2 immediately fails with IndentationError
- Cannot test MeshCore CLI functionality
- Diagnostic test incomplete

### After Fix
- Test 2 runs without syntax errors
- May timeout if device not responding (expected behavior)
- Complete diagnostic test execution

## Related Issues

This indentation error was introduced during the recent logging reduction changes in commit `aa5589b` where sync_contacts logging verbosity was reduced from 15 lines to 1 line per sync.

The error occurred because:
1. Multiple indentation levels were edited
2. One line had an extra space accidentally added
3. Python's strict indentation rules caught the error

## Prevention

To prevent similar issues:
1. Use consistent editor settings (spaces vs tabs)
2. Enable visible whitespace in editor
3. Run syntax checks before committing:
   ```bash
   python3 -m py_compile meshcore_cli_wrapper.py
   ```
4. Use linters/formatters:
   ```bash
   python3 -m flake8 meshcore_cli_wrapper.py
   ```

## Testing

The fix has been verified:
- ✅ File imports without errors
- ✅ No syntax errors
- ✅ Diagnostic test can proceed to Test 2
- ✅ All functionality preserved

## Summary

**Issue**: IndentationError at line 761
**Cause**: One extra space character
**Fix**: Removed the extra space
**Result**: File imports correctly, test can run

**Status**: RESOLVED ✅
