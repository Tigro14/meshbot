# Diagnostic Payload Logging (Phase 7)

## Issue
After implementing comprehensive payload extraction (Phase 6), packets still show 0 bytes payload:
```
Type: Unknown(12) | Size: 56B
Payload:0B  # ❌ Still empty!
```

**Phase 6 debug logs are NOT appearing** - suggesting the payload extraction code is not being executed.

## Problem Analysis

### Missing Debug Output
Expected logs from Phase 6:
- `🔍 [RX_LOG] Payload type: ...`
- `⚠️ [RX_LOG] Payload is not a dict: ...`
- `⚠️ [RX_LOG] No payload found ...`

**None of these appear** in the user's logs!

### Root Cause
Previous debug condition at line 1787:
```python
if self.debug and decoded_packet.payload:
    debug_print_mc(f"🔍 [RX_LOG] Payload type: ...")
```

**Problem**: If `decoded_packet.payload` is None, False, or missing, this condition fails **silently**. We get no debug info about WHY the payload is missing!

## Solution: Unconditional Diagnostic Logging

Added **always-on** debug logging to reveal the actual state:

```python
# Debug: Log payload structure ALWAYS for troubleshooting
debug_print_mc(f"🔍 [RX_LOG] Checking decoded_packet for payload...")
debug_print_mc(f"🔍 [RX_LOG] Has payload attribute: {hasattr(decoded_packet, 'payload')}")
if hasattr(decoded_packet, 'payload'):
    debug_print_mc(f"🔍 [RX_LOG] Payload value: {decoded_packet.payload}")
    debug_print_mc(f"🔍 [RX_LOG] Payload type: {type(decoded_packet.payload).__name__}")
    if isinstance(decoded_packet.payload, dict):
        debug_print_mc(f"🔍 [RX_LOG] Payload keys: {list(decoded_packet.payload.keys())}")
```

## Expected Diagnostic Output

### Scenario 1: Payload Attribute Missing
```
🔍 [RX_LOG] Checking decoded_packet for payload...
🔍 [RX_LOG] Has payload attribute: False
⚠️ [RX_LOG] No payload found in decoded_packet
```

**Action**: Need to check alternate attributes or different packet structure.

### Scenario 2: Payload is None
```
🔍 [RX_LOG] Checking decoded_packet for payload...
🔍 [RX_LOG] Has payload attribute: True
🔍 [RX_LOG] Payload value: None
🔍 [RX_LOG] Payload type: NoneType
⚠️ [RX_LOG] No payload found in decoded_packet
```

**Action**: Payload exists but is None - need to check raw data elsewhere.

### Scenario 3: Payload is Empty Dict
```
🔍 [RX_LOG] Checking decoded_packet for payload...
🔍 [RX_LOG] Has payload attribute: True
🔍 [RX_LOG] Payload value: {}
🔍 [RX_LOG] Payload type: dict
🔍 [RX_LOG] Payload keys: []
```

**Action**: Empty dict - no decoded or raw data.

### Scenario 4: Payload Has Raw Data (Expected for Encrypted)
```
🔍 [RX_LOG] Checking decoded_packet for payload...
🔍 [RX_LOG] Has payload attribute: True
🔍 [RX_LOG] Payload value: {'raw': '1a052f65636...'}
🔍 [RX_LOG] Payload type: dict
🔍 [RX_LOG] Payload keys: ['raw']
✅ [RX_LOG] Converted hex string to bytes: 56B
```

**Action**: Good! Phase 5 fix should extract the raw hex.

### Scenario 5: Payload is Bytes Directly
```
🔍 [RX_LOG] Checking decoded_packet for payload...
🔍 [RX_LOG] Has payload attribute: True
🔍 [RX_LOG] Payload value: b'\x1a\x05/echo...'
🔍 [RX_LOG] Payload type: bytes
✅ [RX_LOG] Using payload directly as bytes: 56B
```

**Action**: Good! Phase 6 fix should handle this.

## Testing Instructions

1. **Deploy the updated bot** with diagnostic logging
2. **Restart the meshbot service**:
   ```bash
   sudo systemctl restart meshbot
   ```
3. **Send `/echo test` on MeshCore public channel**
4. **Check logs** for diagnostic output:
   ```bash
   journalctl -u meshbot -f | grep "🔍 \[RX_LOG\]"
   ```

## What This Reveals

The diagnostic output will show:

1. ✅ **Does `decoded_packet.payload` exist?**
   - If False → need to check alternate packet attributes
   
2. ✅ **What is the payload value?**
   - None → check packet.raw_data, packet.data
   - {} → empty dict, no data available
   - {'raw': '...'} → encrypted, Phase 5 should work
   - bytes → Phase 6 should work
   
3. ✅ **Why is extraction failing?**
   - Missing attribute → add alternate checks
   - Wrong type → add type conversion
   - Empty value → check if data elsewhere in packet

## Next Steps

Based on diagnostic output, we can:
- Add support for alternate payload attributes
- Check parent packet object for raw data
- Investigate meshcore-cli packet structure
- Add fallback to packet decoder if payload missing

## Files Modified
- `meshcore_cli_wrapper.py` (lines 1786-1794)

## Phase
**Phase 7**: Diagnostic Logging for Payload Extraction Debugging
