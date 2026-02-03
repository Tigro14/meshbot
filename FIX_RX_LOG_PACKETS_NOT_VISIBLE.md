# Fix: RX_LOG Packets Not Visible - Change to info_print_mc

## Problem

After fixing the subscription message visibility, user reported:
> "Now i do not see any packet in the debug info"

The subscription messages are now visible with `[INFO][MC]` prefix, but packet activity is not showing up.

## Root Cause

RX_LOG packet messages were using `debug_print_mc()` which only displays when `DEBUG_MODE = True`. This meant:
- If DEBUG_MODE was False, no packets visible
- If there was any issue with DEBUG_MODE import, no packets visible
- Users had no way to confirm packets were actually arriving

### Previous Code
```python
# Line 1343
debug_print_mc(f"📡 [RX_LOG] Paquet RF reçu ({hex_len}B) - SNR:{snr}dB...")

# Line 1415
debug_print_mc(f"📦 [RX_LOG] {' | '.join(info_parts)}")

# Lines 1460, 1496, 1501, 1505, 1507
debug_print_mc(f"📝 [RX_LOG] ...")
debug_print_mc(f"📢 [RX_LOG] Advert...")
debug_print_mc(f"👥 [RX_LOG] ...")
debug_print_mc(f"🔍 [RX_LOG] ...")
debug_print_mc(f"🛣️  [RX_LOG] ...")
```

## Solution

Changed all key RX_LOG messages to use `info_print_mc()` so they're ALWAYS visible:

### Changes Made

**File:** `meshcore_cli_wrapper.py`

1. **Packet arrival notification** (line ~1343):
   ```python
   # Before
   debug_print_mc(f"📡 [RX_LOG] Paquet RF reçu ({hex_len}B)...")
   
   # After
   info_print_mc(f"📡 [RX_LOG] Paquet RF reçu ({hex_len}B)...")
   ```

2. **Payload validation error** (line ~1331):
   ```python
   # Before
   debug_print_mc(f"⚠️ [RX_LOG] Payload non-dict: {type(payload).__name__}")
   
   # After
   info_print_mc(f"⚠️ [RX_LOG] Payload non-dict: {type(payload).__name__}")
   ```

3. **Decoded packet details** (line ~1415):
   ```python
   # Before
   debug_print_mc(f"📦 [RX_LOG] {' | '.join(info_parts)}")
   
   # After
   info_print_mc(f"📦 [RX_LOG] {' | '.join(info_parts)}")
   ```

4. **Message content** (line ~1460):
   ```python
   # Before
   debug_print_mc(f"📝 [RX_LOG] {msg_type} Message: \"{text_preview}\"")
   
   # After
   info_print_mc(f"📝 [RX_LOG] {msg_type} Message: \"{text_preview}\"")
   ```

5. **Advertisements** (line ~1496):
   ```python
   # Before
   debug_print_mc(f"📢 [RX_LOG] Advert {' | '.join(advert_parts)}")
   
   # After
   info_print_mc(f"📢 [RX_LOG] Advert {' | '.join(advert_parts)}")
   ```

6. **Group messages** (line ~1501):
   ```python
   # Before
   debug_print_mc(f"👥 [RX_LOG] {content_type} (public broadcast)")
   
   # After
   info_print_mc(f"👥 [RX_LOG] {content_type} (public broadcast)")
   ```

7. **Routing packets** (lines ~1505, 1507):
   ```python
   # Before
   debug_print_mc(f"🔍 [RX_LOG] Trace packet (routing diagnostic)")
   debug_print_mc(f"🛣️  [RX_LOG] Path packet (routing info)")
   
   # After
   info_print_mc(f"🔍 [RX_LOG] Trace packet (routing diagnostic)")
   info_print_mc(f"🛣️  [RX_LOG] Path packet (routing info)")
   ```

8. **Exception handling** (line ~1526):
   ```python
   # Before
   debug_print_mc(f"⚠️ [RX_LOG] Erreur traitement RX_LOG_DATA: {e}")
   
   # After
   info_print_mc(f"⚠️ [RX_LOG] Erreur traitement RX_LOG_DATA: {e}")
   ```

### What Remains as debug_print_mc

The following less critical messages remain as debug_print_mc (only visible when DEBUG_MODE=True):
- Decode errors/failures (line 1517)
- RF monitoring fallback messages (lines 1521, 1523)
- Raw payload display in debug mode (line 1510+)

## Before/After

### BEFORE (Nothing Visible)
```
[INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
[INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.
(silence... no packets visible even when they arrive)
```

### AFTER (Packets Always Visible)
```
[INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
[INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.
[INFO][MC] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662...
[INFO][MC] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hash: F9C060FE | Hops: 0 | Status: ✅
[INFO][MC] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar | Node: 0x7e766267 | Role: Repeater | GPS: (47.5440, -122.1086)
[INFO][MC] 📡 [RX_LOG] Paquet RF reçu (65B) - SNR:10.0dB RSSI:-62dBm Hex:21007E7662...
[INFO][MC] 📦 [RX_LOG] Type: TextMessage | Route: Flood | Size: 65B | Hops: 1 | Status: ✅
[INFO][MC] 📝 [RX_LOG] 📢 Public Message: "Hello from the mesh network!"
```

## Rationale

### Why info_print_mc Instead of debug_print_mc?

1. **Consistency**: Subscription messages already use `info_print_mc()`
2. **Operational Information**: Packet arrival confirms monitoring is working
3. **User Experience**: Users need to see activity to know the system works
4. **Troubleshooting**: Always-visible packets help diagnose issues
5. **Not Just Debug**: This is core functionality status, not debug info

### What Is Operational vs Debug?

**Operational (info_print_mc):**
- ✅ Subscription status
- ✅ Packet arrival notification
- ✅ Decoded packet summary
- ✅ Message content preview
- ✅ Advertisement info
- ✅ Errors/warnings

**Debug Only (debug_print_mc):**
- Decoder implementation details
- Raw payload hex dumps
- Verbose parsing info
- Internal state dumps

## Testing

Run the test script:
```bash
python3 test_rx_log_always_visible.py
```

Expected output shows all messages with `[INFO][MC]` prefix.

## Verification

After deploying, check logs:
```bash
journalctl -u meshtastic-bot --no-pager -fn 1000 | grep MC
```

You should now see:
1. ✅ Subscription confirmation
2. ✅ Monitoring status
3. ✅ **Packet arrival** (NEW - always visible!)
4. ✅ **Packet details** (NEW - always visible!)
5. ✅ **Message content** (NEW - always visible!)

## Benefits

1. **Always Visible**: Packets show regardless of DEBUG_MODE setting
2. **User Confidence**: Users see packets arriving, confirming system works
3. **Easier Troubleshooting**: No need to enable DEBUG_MODE to see packets
4. **Consistent Logging**: All MC operational info uses same pattern
5. **Better UX**: Clear feedback that RX_LOG monitoring is active and working

## Impact

- **Risk**: Minimal - only changes log level, not functionality
- **Performance**: No impact - same number of messages
- **Compatibility**: Fully backward compatible
- **Value**: High - fixes user visibility issue immediately
