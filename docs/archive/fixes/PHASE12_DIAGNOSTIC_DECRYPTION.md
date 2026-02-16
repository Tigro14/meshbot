# Phase 12: Diagnostic Logging for Decryption Issue

## Problem Statement

After implementing Phase 11 (TEXT_MESSAGE_APP decryption), the message text still shows empty:

```
[DEBUG][MC] 📦 TEXT_MESSAGE_APP from Node-b1aa11bf (40B)
[DEBUG][MC]   └─ Msg:"  ← Still empty!
```

**Critical observation**: Phase 11 debug logs are NOT appearing:
- Missing: `🔐 Encrypted TEXT_MESSAGE_APP detected...`
- Missing: `✅ Decrypted TEXT_MESSAGE_APP...`

This indicates the decryption code path is not being executed!

## Root Cause Hypothesis

The Phase 11 condition at line 712 is NOT being met:

```python
if not message_text and 'payload' in decoded:
    payload = decoded.get('payload')
    if isinstance(payload, (bytes, bytearray)) and len(payload) > 0:
        # Decryption code never reaches here!
```

### Possible Causes

1. **`message_text` is not empty**
   - `_extract_message_text()` might be returning some value
   - Could be empty string `""` which is falsy but checking `not message_text`
   - Could be whitespace or other invisible characters

2. **`'payload'` key missing**
   - `decoded` dict might not have 'payload' key
   - MeshCore wrapper might be using different key name
   - Payload might be in different location

3. **`payload` wrong type**
   - Not bytes or bytearray
   - Could be string, dict, or other type
   - Type mismatch prevents decryption

4. **`payload` length zero**
   - Payload exists but empty
   - Would fail `len(payload) > 0` check

## Phase 12 Solution: Diagnostic Logging

Added comprehensive debug logging BEFORE the condition:

```python
if packet_type == 'TEXT_MESSAGE_APP':
    message_text = self._extract_message_text(decoded)
    
    # NEW: Diagnostic logging
    debug_print(f"🔍 [TEXT_MESSAGE_APP] message_text: {repr(message_text)}")
    debug_print(f"🔍 [TEXT_MESSAGE_APP] decoded keys: {list(decoded.keys())}")
    debug_print(f"🔍 [TEXT_MESSAGE_APP] decoded: {decoded}")
    
    # Check if message is encrypted (has payload bytes but no text)
    if not message_text and 'payload' in decoded:
        # Decryption code...
```

### What This Reveals

**Scenario A: message_text has unexpected value**
```
🔍 [TEXT_MESSAGE_APP] message_text: ' '  ← Whitespace!
```
Solution: Check for empty/whitespace, not just falsy

**Scenario B: payload key missing**
```
🔍 [TEXT_MESSAGE_APP] decoded keys: ['portnum', 'from', 'to', ...]  ← No 'payload'!
```
Solution: Check different key names or location

**Scenario C: payload wrong type**
```
🔍 [TEXT_MESSAGE_APP] decoded: {'payload': '<encrypted data>'}  ← String!
```
Solution: Handle string payload, convert to bytes

**Scenario D: payload in different structure**
```
🔍 [TEXT_MESSAGE_APP] decoded: {'portnum': 'TEXT_MESSAGE_APP', 'encrypted': True, ...}
```
Solution: Find actual payload location

## Expected Diagnostic Output

When user tests `/echo test` on encrypted channel:

```
[DEBUG][MC] 📦 [RX_LOG] Type: Unknown(12) | Route: Flood | Size: 40B
[DEBUG][MC] 🔐 [RX_LOG] Encrypted packet (type 15) → TEXT_MESSAGE_APP
[DEBUG][MC] ➡️  [RX_LOG] Forwarding TEXT_MESSAGE_APP packet
[DEBUG] 🔍 [TEXT_MESSAGE_APP] message_text: ''
[DEBUG] 🔍 [TEXT_MESSAGE_APP] decoded keys: ['portnum', 'payload', 'want_response', ...]
[DEBUG] 🔍 [TEXT_MESSAGE_APP] decoded: {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'\x1a\x05/echo...', ...}
```

## Testing Instructions

### Deploy Phase 12

```bash
cd /home/user/meshbot
git pull origin copilot/add-echo-command-listener
sudo systemctl restart meshbot
```

### Monitor Logs

```bash
journalctl -u meshbot -f | grep -E "(TEXT_MESSAGE|🔍|RX_LOG)"
```

### Test Command

Send `/echo test` on MeshCore public channel

### Capture Output

Look for the diagnostic lines:
- `🔍 [TEXT_MESSAGE_APP] message_text: ...`
- `🔍 [TEXT_MESSAGE_APP] decoded keys: ...`
- `🔍 [TEXT_MESSAGE_APP] decoded: ...`

### Report Findings

Share the diagnostic output showing:
1. What `message_text` contains
2. What keys are in `decoded`
3. The full `decoded` structure

This will identify exactly why the decryption code is not executing.

## Next Steps

Based on diagnostic output:
- **If message_text has value**: Adjust condition to check for meaningful text
- **If payload key missing**: Find correct location of payload data
- **If payload wrong type**: Add type conversion
- **If payload elsewhere**: Update extraction logic

Phase 13 will implement the fix based on Phase 12 diagnostic findings.

## Status

✅ Phase 12 deployed - Awaiting user diagnostic output
🔄 Phase 13 pending - Will implement fix based on findings
