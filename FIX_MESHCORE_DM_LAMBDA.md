# Fix: MeshCore DM Reception Lambda Parameter Mismatch

## Problem

When receiving a DM (Direct Message) on the MeshCore side, the bot crashed with the error:

```
[ERROR] ❌ [MESHCORE-CLI] Erreur traitement message: DualInterfaceManager.setup_message_callbacks.
```

The full error was a `TypeError` indicating a lambda parameter mismatch.

## Root Cause

### Lambda Registration

In `dual_interface_manager.py` line 199-201:
```python
self.meshcore_interface.set_message_callback(
    lambda packet: self.on_meshcore_message(packet, self.meshcore_interface)
)
```

The lambda accepts **1 parameter** (`packet`).

### Callback Invocation

In `meshcore_cli_wrapper.py` line 1158:
```python
self.message_callback(packet, None)  # Calls with 2 arguments
```

The callback is called with **2 parameters** (`packet`, `None`).

### The Error

```
TypeError: <lambda>() takes 1 positional argument but 2 were given
```

This error occurred because:
1. MeshCore DM is received
2. `_on_contact_message()` processes it
3. Calls `self.message_callback(packet, None)` with 2 args
4. Lambda expects only 1 arg → **TypeError**

## The Fix

### Changed Line

**File**: `dual_interface_manager.py`  
**Line**: 199-201

**Before** (BUGGY):
```python
self.meshcore_interface.set_message_callback(
    lambda packet: self.on_meshcore_message(packet, self.meshcore_interface)
)
```

**After** (FIXED):
```python
# FIX: Lambda must accept 2 parameters (packet, interface) 
# meshcore_cli_wrapper calls callback with 2 args: callback(packet, None)
self.meshcore_interface.set_message_callback(
    lambda packet, interface=None: self.on_meshcore_message(packet, self.meshcore_interface)
)
```

### What Changed

Added `interface=None` parameter to the lambda:
- **Before**: `lambda packet:`
- **After**: `lambda packet, interface=None:`

The `interface=None` makes the second parameter optional with a default value, so the lambda now accepts:
- 1 parameter: `callback(packet)` ✅
- 2 parameters: `callback(packet, None)` ✅

## Test Results

Created `test_meshcore_dm_lambda_fix.py` to verify the fix:

```
======================================================================
TEST SUMMARY
======================================================================

✅ PASS       Lambda Parameter Fix
✅ PASS       Complete Callback Flow
✅ PASS       Original Error Scenario

Results: 3/3 tests passed

🎉 ALL TESTS PASSED!
```

### Test Scenarios

1. **Lambda Parameter Fix**
   - Verifies old lambda fails with 2 parameters
   - Verifies new lambda accepts both 1 and 2 parameters

2. **Complete Callback Flow**
   - Simulates full DM reception flow
   - Verifies packet is passed correctly through callback

3. **Original Error Scenario**
   - Documents the original error
   - Confirms fix resolves the TypeError

## Impact

**Before Fix:**
- ❌ MeshCore DMs crash the bot
- ❌ Error: `TypeError: <lambda>() takes 1 positional argument but 2 were given`
- ❌ Bot cannot process MeshCore DMs

**After Fix:**
- ✅ MeshCore DMs processed successfully
- ✅ No TypeError
- ✅ Bot handles DMs from MeshCore network

## Backward Compatibility

The fix is **fully backward compatible**:
- If callback is ever called with 1 parameter, `interface` defaults to `None`
- Existing code that calls with 1 parameter continues to work
- New code can call with 2 parameters

## Related Issues

While investigating this bug, we also identified:

1. **Empty Contacts Database**
   - Logs show: `📊 [MESHCORE-QUERY] Nombre de contacts disponibles: 0`
   - Contacts are not being loaded properly
   - This is a separate issue to be addressed

2. **Fallback to 0xFFFFFFFF**
   - When `sender_id` is None, code falls back to broadcast ID
   - This can cause confusion downstream
   - Warning is logged but doesn't prevent processing

These are orthogonal issues that should be addressed separately.

## Files Modified

1. **`dual_interface_manager.py`** (Line 199-201)
   - Changed lambda to accept 2 parameters

2. **`test_meshcore_dm_lambda_fix.py`** (NEW)
   - Comprehensive test suite
   - 3/3 tests passing

3. **`FIX_MESHCORE_DM_LAMBDA.md`** (NEW - this file)
   - Complete documentation

## Summary

**Root Cause**: Lambda parameter mismatch  
**Fix**: Added `interface=None` parameter to lambda  
**Result**: MeshCore DMs now work correctly  
**Tests**: 3/3 passing  
**Status**: ✅ **RESOLVED**
