# Fix #11: Convert publicKey to Hex String for meshcore-cli API

## Problem

After fixing the field name from `publicKey` to `public_key` (Fix #10), a new error appeared:

```
❌ [MESHCORE-DM] Async send error: fromhex() argument must be str, not bytes
```

## Root Cause

The `contact_data['publicKey']` field contains **bytes** (returned from SQLite BLOB), but the meshcore-cli API expects a **hex string**.

### Data Flow

1. **SQLite Storage:**
   - `publicKey` column is BLOB type
   - Returns bytes in Python: `b'\x14\x3b\xcd\x7f\x1b\x1f...'`

2. **Our Code:**
   ```python
   'public_key': contact_data['publicKey']  # Passes bytes directly ❌
   ```

3. **meshcore-cli API:**
   - Expects hex string: `'143bcd7f1b1f...'`
   - Internally calls `bytes.fromhex(hex_string)`
   - **Fails** when passed bytes: `bytes.fromhex(bytes)` → TypeError

## Solution

Convert bytes to hex string using `.hex()` method:

```python
# Before (broken):
'public_key': contact_data['publicKey']  # bytes

# After (fixed):
'public_key': contact_data['publicKey'].hex()  # hex string
```

## Code Changes

**File:** `meshcore_cli_wrapper.py`  
**Method:** `_add_contact_to_meshcore()`  
**Line:** ~210

```python
contact = {
    'node_id': contact_data['node_id'],
    'adv_name': contact_data.get('name', f"Node-{contact_data['node_id']:08x}"),
    'public_key': contact_data['publicKey'].hex(),  # Convert bytes to hex string
}
```

## Before vs After

### Before Fix
```
[DEBUG] ✅ Contact trouvé via dict direct: Node-143bcd7f
[DEBUG] 🔄 Submitting coroutine to event loop...
[DEBUG] ✅ Message submitted to event loop (fire-and-forget)
[Later, asynchronously:]
[ERROR] ❌ Async send error: fromhex() argument must be str, not bytes
❌ Message not transmitted
```

### After Fix
```
[DEBUG] ✅ Contact trouvé via dict direct: Node-143bcd7f
[DEBUG] 🔄 Submitting coroutine to event loop...
[DEBUG] ✅ Message submitted to event loop (fire-and-forget)
[Later, asynchronously:]
[DEBUG] ✅ Async send completed successfully
✅ Message transmitted to MeshCore network
✅ Client receives response
```

## Technical Details

### Python bytes.hex() Method

```python
>>> b'\x14\x3b\xcd\x7f'.hex()
'143bcd7f'
```

Converts bytes to lowercase hex string without separators.

### meshcore-cli API Expectation

The API expects:
- Type: `str`
- Format: Hex string (lowercase, no separators)
- Example: `'143bcd7f1b1f4a2e...'`

Internally converts to bytes:
```python
public_key_bytes = bytes.fromhex(hex_string)
```

## Impact

- ✅ meshcore-cli API now receives correct data type
- ✅ No more `fromhex()` type error
- ✅ Messages successfully transmitted over MeshCore network
- ✅ **Clients receive DM responses** ✅

## Lessons Learned

1. **Type matters:** APIs may expect specific types (str vs bytes)
2. **Check data sources:** SQLite BLOBs return bytes, not strings
3. **Read error messages carefully:** "fromhex() argument must be str" was very clear
4. **Async callbacks are essential:** Without the callback, this error would have been silent

## Status

✅ **FIXED** - Messages now transmit successfully over MeshCore network.

This was Fix #11 in the complete MeshCore DM implementation chain.
