# Rollback: RX_LOG Messages Back to debug_print_mc

## User Feedback

> "It make no sense, I was in DEBUG mode the WHOLE time of course, rollback!"

## Issue

The previous fix (commit 965f266) changed RX_LOG messages from `debug_print_mc()` to `info_print_mc()` assuming the user couldn't see packet messages. However, the user had `DEBUG_MODE = True` the entire time, so `debug_print_mc()` messages WERE already visible.

The change to `info_print_mc()` was unnecessary and should be rolled back.

## Root Cause of Confusion

The real issue was **NOT** that messages were at debug level. The user must have had a different problem:
- No packets arriving at all
- Subscription not working
- Callback not being invoked
- Something else unrelated to log level

## Rollback Changes

Reverted all RX_LOG packet messages from `info_print_mc()` back to `debug_print_mc()`:

### File: `meshcore_cli_wrapper.py`

**9 locations reverted:**

1. Line ~1331: Payload validation error
   ```python
   # Reverted to
   debug_print_mc(f"⚠️ [RX_LOG] Payload non-dict: {type(payload).__name__}")
   ```

2. Line ~1343: Packet arrival notification
   ```python
   # Reverted to
   debug_print_mc(f"📡 [RX_LOG] Paquet RF reçu ({hex_len}B)...")
   ```

3. Line ~1414: Decoded packet details
   ```python
   # Reverted to
   debug_print_mc(f"📦 [RX_LOG] {' | '.join(info_parts)}")
   ```

4. Line ~1458: Message content
   ```python
   # Reverted to
   debug_print_mc(f"📝 [RX_LOG] {msg_type} Message: \"{text_preview}\"")
   ```

5. Line ~1494: Advertisements
   ```python
   # Reverted to
   debug_print_mc(f"📢 [RX_LOG] Advert {' | '.join(advert_parts)}")
   ```

6. Line ~1499: Group messages
   ```python
   # Reverted to
   debug_print_mc(f"👥 [RX_LOG] {content_type} (public broadcast)")
   ```

7. Line ~1503: Trace packets
   ```python
   # Reverted to
   debug_print_mc(f"🔍 [RX_LOG] Trace packet (routing diagnostic)")
   ```

8. Line ~1505: Path packets
   ```python
   # Reverted to
   debug_print_mc(f"🛣️  [RX_LOG] Path packet (routing info)")
   ```

9. Line ~1524: Exception handling
   ```python
   # Reverted to
   debug_print_mc(f"⚠️ [RX_LOG] Erreur traitement RX_LOG_DATA: {e}")
   ```

## What Was Kept

**Subscription messages remain as `info_print_mc()`** (from commit 1e69e07):
- ✅ `info_print_mc("✅ Souscription aux messages DM (events.subscribe)")`
- ✅ `info_print_mc("✅ Souscription à RX_LOG_DATA (tous les paquets RF)")`
- ✅ `info_print_mc("   → Monitoring actif: broadcasts, télémétrie, DMs, etc.")`

These are important operational status messages and should always be visible.

## Files Removed

- `test_rx_log_always_visible.py` - No longer needed
- `FIX_RX_LOG_PACKETS_NOT_VISIBLE.md` - No longer applicable

## Expected Behavior After Rollback

With `DEBUG_MODE = True`:
```
[INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
[INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm...
[DEBUG][MC] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B...
[DEBUG][MC] 📢 [RX_LOG] Advert from: Node | Node: 0x7e766267...
```

With `DEBUG_MODE = False`:
```
[INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
[INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.
(no packet messages - as originally designed)
```

## Rationale

1. **Original design was correct**: Packet details are debug-level information
2. **User had DEBUG_MODE=True**: Messages WERE visible all along
3. **Unnecessary change**: Moving to info_print_mc added noise for non-debug users
4. **Proper separation**: 
   - **info_print_mc**: Operational status (subscriptions, connections)
   - **debug_print_mc**: Detailed packet activity (only needed for debugging)

## Testing

Run test to verify rollback:
```bash
python3 test_rollback_debug_print.py
```

Expected results:
- ✅ Subscription messages visible with [INFO][MC]
- ✅ RX_LOG packet messages visible with [DEBUG][MC] when DEBUG_MODE=True
- ✅ Original behavior restored

## Lesson Learned

The issue was **NOT** the log level. If user reports not seeing packets while in DEBUG mode, investigate:
1. Are packets actually arriving?
2. Is the subscription working?
3. Is the callback being invoked?
4. Is there an exception in the callback?
5. Is there an early return before the log statement?

Don't assume it's a logging level issue without verifying DEBUG_MODE first.
