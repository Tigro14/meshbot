# Fix for TypeError: sender_id is None in meshcore_cli_wrapper.py

## Issue Summary

**Error**: `TypeError: unsupported format string passed to NoneType.__format__`  
**Location**: `meshcore_cli_wrapper.py`, line 366  
**Date**: 2025-01-20

### Error Log
```
Jan 20 15:18:14 DietPi meshtastic-bot[36604]: [ERROR] 15:18:14 - ❌ [MESHCORE-CLI] Erreur traitement message: unsupported format string passed to NoneType.__format__
Jan 20 15:18:14 DietPi meshtastic-bot[36604]: Traceback (most recent call last):
Jan 20 15:18:14 DietPi meshtastic-bot[36604]:   File "/home/dietpi/bot/meshcore_cli_wrapper.py", line 366, in _on_contact_message
Jan 20 15:18:14 DietPi meshtastic-bot[36604]:     info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {text[:50]}{'...' if len(text) > 50 else ''}")
Jan 20 15:18:14 DietPi meshtastic-bot[36604]:                                         ^^^^^^^^^^^^^^^
Jan 20 15:18:14 DietPi meshtastic-bot[36604]: TypeError: unsupported format string passed to NoneType.__format__
```

## Root Cause

The `_on_contact_message()` method in `meshcore_cli_wrapper.py` was attempting to format `sender_id` as a hexadecimal value (`:08x`) without checking if it was `None` first.

### Event Payload Structure
The event from meshcore-cli had the following structure:
```python
Event(
    type=<EventType.CONTACT_MSG_RECV: 'contact_message'>,
    payload={
        'type': 'PRIV',
        'SNR': 12.5,
        'pubkey_prefix': '143bcd7f1b1f',  # Only this, no sender_id!
        'path_len': 255,
        'txt_type': 0,
        'sender_timestamp': 1768922280,
        'text': '/help'
    },
    attributes={
        'pubkey_prefix': '143bcd7f1b1f',
        'txt_type': 0
    }
)
```

Notice that the payload contains `pubkey_prefix` but **NOT** `contact_id` or `sender_id`.

### Original Code Problem
```python
# Line 363: Both are None in this case
sender_id = payload.get('contact_id') or payload.get('sender_id')

# Line 366: Crashes when sender_id is None
info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | ...")  # ❌ TypeError!
```

## Solution

The fix implements a **multi-source extraction strategy** with **safe formatting**:

### 1. Multi-Source Extraction
Try multiple sources to find sender_id:
```python
sender_id = None

# Method 1: Look in payload dict
if isinstance(payload, dict):
    sender_id = payload.get('contact_id') or payload.get('sender_id')

# Method 2: Look in event attributes
if sender_id is None and hasattr(event, 'attributes'):
    attributes = event.attributes
    if isinstance(attributes, dict):
        sender_id = attributes.get('contact_id') or attributes.get('sender_id')

# Method 3: Look directly on event object
if sender_id is None and hasattr(event, 'contact_id'):
    sender_id = event.contact_id
```

### 2. Safe Formatting with Fallback
Check if sender_id is None before formatting:
```python
if sender_id is not None:
    # Normal case: format as hex
    info_print(f"📬 [MESHCORE-DM] De: 0x{sender_id:08x} | Message: {text[:50]}...")
else:
    # Fallback: use pubkey_prefix if available
    pubkey_prefix = payload.get('pubkey_prefix')
    if pubkey_prefix:
        info_print(f"📬 [MESHCORE-DM] De: {pubkey_prefix} | Message: {text[:50]}...")
    else:
        info_print(f"📬 [MESHCORE-DM] De: <inconnu> | Message: {text[:50]}...")
```

### 3. Safe Packet Creation
Use a default value when sender_id is None:
```python
packet = {
    'from': sender_id if sender_id is not None else 0xFFFFFFFF,  # Default: broadcast
    'to': self.localNode.nodeNum,
    'decoded': {
        'portnum': 'TEXT_MESSAGE_APP',
        'payload': text.encode('utf-8')
    }
}
```

## Test Results

### Test 1: Original Bug Case
**Input**: Event with `pubkey_prefix` but no `sender_id`
```
✅ No crash
📬 [MESHCORE-DM] De: 143bcd7f1b1f | Message: /help
Packet from: 0xffffffff (default)
```

### Test 2: Normal Case
**Input**: Event with `contact_id`
```
✅ Works as before
📬 [MESHCORE-DM] De: 0x16fad3dc | Message: /nodes
Packet from: 0x16fad3dc
```

### Test 3: Unknown Case
**Input**: Event with neither `sender_id` nor `pubkey_prefix`
```
✅ Graceful fallback
📬 [MESHCORE-DM] De: <inconnu> | Message: /status
Packet from: 0xffffffff (default)
```

## Benefits

1. ✅ **No More Crashes**: TypeError is completely avoided
2. ✅ **Graceful Degradation**: Uses pubkey_prefix as fallback identifier
3. ✅ **Backward Compatible**: Normal cases (with sender_id) work exactly as before
4. ✅ **Safe Packet Creation**: Default value (0xFFFFFFFF) used when sender_id unavailable
5. ✅ **Better Diagnostics**: User can see pubkey_prefix in logs even without sender_id

## Files Changed

1. **meshcore_cli_wrapper.py** - Enhanced `_on_contact_message()` method
2. **test_meshcore_sender_id_fix.py** - Unit tests for extraction logic
3. **test_meshcore_integration_fix.py** - Integration test with exact log event

## Verification

Run the tests to verify the fix:
```bash
python test_meshcore_sender_id_fix.py
python test_meshcore_integration_fix.py
```

Both tests should pass with all green checkmarks ✅
