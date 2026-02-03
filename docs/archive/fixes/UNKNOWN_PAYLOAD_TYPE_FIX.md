# Unknown Payload Type Handling Fix

## Problem

Production logs showed noisy warnings for packet types 12 and 14 that aren't defined in meshcoredecoder v0.2.3:

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:12.0dB RSSI:-45dBm Hex:30d31502e1bf11f52547...
[DEBUG] 📦 [RX_LOG] Type: RawCustom | Route: Flood | Valid: ⚠️
[DEBUG]    ⚠️ 12 is not a valid PayloadType

[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:14.0dB RSSI:-13dBm Hex:38f31503e1bf6e11f525...
[DEBUG] 📦 [RX_LOG] Type: RawCustom | Route: Flood | Valid: ⚠️
[DEBUG]    ⚠️ 14 is not a valid PayloadType
```

**Issues:**
- ⚠️ Warning icons suggest errors (they're legitimate packets)
- 'RawCustom' is cryptic (doesn't show the actual type ID)
- Extra error lines clutter logs
- Looks broken when it's not

## Root Cause

meshcoredecoder v0.2.3 has gaps in PayloadType enum:
- Defines types: 0-10, 15
- Missing types: 11, 12, 13, 14

When packets with these types are received, the decoder:
1. Classifies them as "RawCustom"
2. Marks as invalid (`is_valid = False`)
3. Adds error: "X is not a valid PayloadType"

These are legitimate packets using payload types not yet defined in the decoder library, not actual errors.

## Solution

Modified `meshcore_cli_wrapper.py::_on_rx_log_data()` to handle unknown payload types gracefully:

### Changes

1. **Detect unknown type errors**
   ```python
   unknown_type_error = None
   if packet.errors:
       for error in packet.errors:
           if "is not a valid PayloadType" in error:
               import re
               match = re.search(r'(\d+) is not a valid PayloadType', error)
               if match:
                   unknown_type_error = match.group(1)
               break
   ```

2. **Display with numeric ID**
   ```python
   if unknown_type_error:
       info_parts.append(f"Type: Unknown({unknown_type_error})")
   else:
       info_parts.append(f"Type: {payload_name}")
   ```

3. **Use info icon instead of warning**
   ```python
   if unknown_type_error:
       validity = "ℹ️"  # Info icon (not alarming)
   else:
       validity = "✅" if packet.is_valid else "⚠️"
   ```

4. **Filter out redundant errors**
   ```python
   # Log non-unknown-type errors only
   other_errors = [e for e in packet.errors 
                   if "is not a valid PayloadType" not in e]
   for error in other_errors[:3]:
       debug_print(f"   ⚠️ {error}")
   ```

## Result

### After (clean and informative)

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:12.0dB RSSI:-45dBm Hex:30d31502e1bf11f52547...
[DEBUG] 📦 [RX_LOG] Type: Unknown(12) | Route: Flood | Status: ℹ️

[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:14.0dB RSSI:-13dBm Hex:38f31503e1bf6e11f525...
[DEBUG] 📦 [RX_LOG] Type: Unknown(14) | Route: Flood | Status: ℹ️
```

### Improvements

✅ **Clear identification**: Shows actual type number (Unknown(12), Unknown(14))  
✅ **Non-alarming**: ℹ️ info icon instead of ⚠️ warning  
✅ **Clean logs**: Single line per packet, no redundant errors  
✅ **Informative**: Users know the packet type even if decoder doesn't support it  
✅ **Backward compatible**: Known types unchanged  

## Testing

### Test Suite

`test_unknown_payload_types.py` verifies:
- Unknown types 12 and 14 are detected and displayed correctly
- No redundant error messages logged
- Known payload types (like Advert) still work normally

**Results:**
```
✅ All test suites passed!
```

### Demo

`demo_unknown_payload_types.py` shows before/after comparison interactively.

## Impact

### Production Logs

**Before:** Noisy, looks like errors  
**After:** Clean, informative, non-alarming

### User Experience

- Less confusion (clear that these are just unsupported types)
- Better debugging (can see exact type ID)
- Reduced log noise (no multi-line errors)

### Known Payload Types

No impact - existing behavior preserved for:
- TextMessage (2)
- Ack (3)
- Advert (4)
- And all other defined types

## Future

When meshcoredecoder adds support for types 11-14:
- These packets will decode fully
- Status will change from ℹ️ to ✅
- No code changes needed (graceful transition)

## Files Modified

- `meshcore_cli_wrapper.py` - Unknown type detection and display
- `test_unknown_payload_types.py` - Test suite (NEW)
- `demo_unknown_payload_types.py` - Demo script (NEW)
- `UNKNOWN_PAYLOAD_TYPE_FIX.md` - This documentation (NEW)

## References

- Issue: Noisy logs for payload types 12 and 14
- meshcoredecoder version: 0.2.3
- Missing types: 11, 12, 13, 14
- Production hex samples: 30d31502e1bf11f52547, 38f31503e1bf6e11f525
