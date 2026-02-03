# MeshCore RX_LOG Improvements - Quick Reference

## What Changed?

Enhanced the RX_LOG_DATA packet display to show more diagnostic information using the existing `meshcoredecoder` library.

## Quick Examples

### Short Packet
```diff
- [DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:13.0dB RSSI:-56dBm Hex:34c81101bf143bcd7f1b...
+ [DEBUG] 📡 [RX_LOG] Paquet RF reçu (10B) - SNR:13.0dB RSSI:-56dBm Hex:34c81101bf143bcd7f1b...

- [DEBUG] 📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Status: ℹ️
+ [DEBUG] 📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Size: 10B | Status: ℹ️
```

### Error Packet
```diff
- [DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:-11.5dB RSSI:-116dBm Hex:d28c1102bf34143bcd7f...
+ [DEBUG] 📡 [RX_LOG] Paquet RF reçu (10B) - SNR:-11.5dB RSSI:-116dBm Hex:d28c1102bf34143bcd7f...

- [DEBUG] 📦 [RX_LOG] Type: RawCustom | Route: Flood | Status: ⚠️
+ [DEBUG] 📦 [RX_LOG] Type: RawCustom | Route: Flood | Size: 10B | Status: ⚠️
```

### Large Packet
```diff
- [DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:11.5dB RSSI:-58dBm Hex:11007E7662676F7F0850...
+ [DEBUG] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662676F7F0850A8A355BAAFBFC1EB7B41...

- [DEBUG] 📦 [RX_LOG] Type: Advert | Route: Flood | Hash: F9C060FE | Status: ✅
+ [DEBUG] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hash: F9C060FE | Status: ✅
```

## New Fields

| Field | Location | Example | When Shown |
|-------|----------|---------|------------|
| **Packet Size** | First line, in parentheses | `(10B)`, `(134B)` | Always |
| **Size Field** | Decoded line | `Size: 10B` | Always if total_bytes > 0 |
| **Extended Hex** | First line | 40 chars instead of 20 | Always |
| **Payload Version** | Decoded line | `Ver: Version2` | Only if not Version1 |
| **Transport Codes** | Decoded line | `Transport: [codes]` | Only if available |

## Benefits

✅ **Immediate size visibility** - No manual calculation needed
✅ **More hex context** - 2x preview for debugging
✅ **Better error priority** - Structural errors highlighted
✅ **Complete diagnostics** - Transport & version info available

## Files Modified

- `meshcore_cli_wrapper.py` - Enhanced `_on_rx_log_data()` method

## Files Added

- `MESHCORE_RX_LOG_IMPROVEMENTS.md` - Detailed documentation
- `MESHCORE_RX_LOG_VISUAL_COMPARISON.md` - Side-by-side comparison
- `demo_meshcore_rx_log_improvements.py` - Interactive demo
- `test_meshcore_rx_log_improvements.py` - Test suite

## Testing

Run the demo to see improvements in action:
```bash
python3 demo_meshcore_rx_log_improvements.py
```

## Configuration

No configuration changes needed! The improvements are automatic when:
- MeshCore companion mode is enabled
- `meshcoredecoder` package is installed (already in requirements.txt)
- Debug mode is active (DEBUG_MODE=True)

## Backward Compatibility

✅ **100% backward compatible**
- No breaking changes
- No new dependencies
- Works with existing setup
- Gracefully handles missing fields

## Performance Impact

✅ **Zero overhead**
- Display-only changes
- No additional computation
- Same number of log lines
- Slightly longer lines (packet size + extended hex)

## Future Enhancements

Possible future additions:
- Packet timestamp deltas
- Sender/receiver node IDs
- Hop-by-hop path visualization
- Packet rate statistics
