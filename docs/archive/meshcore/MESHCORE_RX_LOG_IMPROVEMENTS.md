# MeshCore RX_LOG Traffic Debug Improvements

## Overview

Enhanced the RX_LOG_DATA debug display in `meshcore_cli_wrapper.py` to provide more detailed and useful diagnostic information using the `meshcoredecoder` library.

## Problem Statement

The previous RX_LOG display showed basic information but lacked some useful details that meshcoredecoder can provide:

```
Feb 02 13:57:06 [DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:13.0dB RSSI:-56dBm Hex:34c81101bf143bcd7f1b...
Feb 02 13:57:06 [DEBUG] 📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Status: ℹ️
```

## Improvements Implemented

### 1. Packet Size in First Line

**Before:**
```
📡 [RX_LOG] Paquet RF reçu - SNR:13.0dB RSSI:-56dBm Hex:34c81101bf143bcd7f1b...
```

**After:**
```
📡 [RX_LOG] Paquet RF reçu (10B) - SNR:13.0dB RSSI:-56dBm Hex:34c81101bf143bcd7f1b...
```

**Benefit:** Immediately see if packet is truncated or incomplete without manual calculation.

### 2. Extended Hex Preview

**Before:** Shows first 20 hex characters
```
Hex:34c81101bf143bcd7f1b...
```

**After:** Shows first 40 hex characters
```
Hex:34c81101bf143bcd7f1b34c81101bf143bcd7f1b...
```

**Benefit:** More visibility into packet structure for debugging.

### 3. Size Field in Decoded Info

**Before:**
```
📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Status: ℹ️
```

**After:**
```
📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Size: 10B | Status: ℹ️
```

**Benefit:** Quick reference to packet size without scrolling back to first line.

### 4. Better Error Categorization

**Before:** All errors shown the same way
```
   ⚠️ 13 is not a valid PayloadType
   ⚠️ Packet too short for path data
```

**After:** Errors categorized and prioritized
```
   ⚠️ Packet too short for path data  (structural - shown first)
   ℹ️  13 is not a valid PayloadType  (unknown type - info only, debug mode)
```

**Benefit:** Critical structural errors are immediately visible; unknown types don't clutter output.

### 5. Transport Codes Display

**New:** Shows transport layer codes when available
```
📦 [RX_LOG] ... | Transport: [codes] | ...
```

**Benefit:** Helps debug routing and transport layer issues.

### 6. Payload Version Display

**New:** Shows protocol version if non-default
```
📦 [RX_LOG] ... | Ver: Version2 | ...
```

**Benefit:** Identifies firmware version mismatches in mixed networks.

### 7. Debug Mode Enhancements

In debug mode, additional information is displayed:
- Raw payload hex data
- Unknown type validation errors (normally hidden)
- More detailed error messages

## Example Output Comparison

### Short Packet with Unknown Type

**Before:**
```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:13.0dB RSSI:-56dBm Hex:34c81101bf143bcd7f1b...
[DEBUG] 📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Status: ℹ️
```

**After:**
```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (10B) - SNR:13.0dB RSSI:-56dBm Hex:34c81101bf143bcd7f1b...
[DEBUG] 📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Size: 10B | Status: ℹ️
```

### Packet with Structural Error

**Before:**
```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:-11.5dB RSSI:-116dBm Hex:d28c1102bf34143bcd7f...
[DEBUG] 📦 [RX_LOG] Type: RawCustom | Route: Flood | Status: ⚠️
[DEBUG]    ⚠️ Packet too short for path data
```

**After:**
```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (10B) - SNR:-11.5dB RSSI:-116dBm Hex:d28c1102bf34143bcd7f...
[DEBUG] 📦 [RX_LOG] Type: RawCustom | Route: Flood | Size: 10B | Status: ⚠️
[DEBUG]    ⚠️ Packet too short for path data
```

### Valid Advertisement Packet

**Before:**
```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:11.5dB RSSI:-58dBm Hex:11007E7662676F7F0850...
[DEBUG] 📦 [RX_LOG] Type: Advert | Route: Flood | Hash: F9C060FE | Status: ✅
[DEBUG] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar
```

**After:**
```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662676F7F0850A8A355BAAFBFC1EB7B41...
[DEBUG] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hash: F9C060FE | Status: ✅
[DEBUG] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar
```

## Technical Implementation

### Files Modified

- **meshcore_cli_wrapper.py** - Enhanced `_on_rx_log_data()` method (lines 1334-1447)

### Key Changes

1. **Line 1339:** Calculate packet size from hex length
2. **Line 1342:** Display packet size in first RF line with 40 chars of hex
3. **Lines 1377-1381:** Add Size field to decoded info
4. **Lines 1383-1387:** Add payload version display (if non-default)
5. **Lines 1394-1397:** Add transport codes display (if available)
6. **Lines 1403-1427:** Improved error categorization and display
7. **Lines 1435-1438:** Debug mode raw payload display

### Backward Compatibility

All changes are backward compatible:
- No configuration changes required
- Works with existing meshcoredecoder installation
- Gracefully handles missing fields (packet.total_bytes, packet.transport_codes, etc.)
- Falls back to previous behavior if decoder not available

## Testing

### Demo Script

Run `demo_meshcore_rx_log_improvements.py` to see before/after comparison:

```bash
python3 demo_meshcore_rx_log_improvements.py
```

### Manual Testing

1. Start bot with MeshCore interface in debug mode
2. Observe RX_LOG_DATA events
3. Verify new fields are displayed:
   - Packet size in first line: `(10B)`, `(134B)`, etc.
   - Size field in decoded line: `Size: 10B`
   - Extended hex preview (40 chars)
   - Categorized errors

## Dependencies

- **meshcoredecoder >= 0.1.0** (already in requirements.txt)
- No new dependencies added

## Benefits

### For Debugging

1. **Faster Diagnosis**: Packet size immediately visible
2. **Better Context**: More hex data reduces need to check full packet
3. **Error Priority**: Structural errors highlighted, unknown types de-emphasized
4. **Complete Picture**: Transport layer and version info available

### For Network Analysis

1. **Packet Size Distribution**: Easily see size patterns
2. **Version Detection**: Identify firmware mismatches
3. **Transport Analysis**: Debug routing issues with transport codes
4. **Error Patterns**: Categorized errors help identify systematic issues

## Future Enhancements

Possible future improvements:
- Add packet timestamp delta (time between packets)
- Show sender/receiver node IDs when available
- Add hop-by-hop path visualization for multi-hop packets
- Compute and display packet rate statistics

## References

- **meshcoredecoder**: https://github.com/chrisdavis2110/meshcore-decoder-py
- **MeshCore Protocol**: MeshCore packet specification
- **Original Issue**: "Improve Meshcore traffic debug display using installed pip module meshcoredecoder"
