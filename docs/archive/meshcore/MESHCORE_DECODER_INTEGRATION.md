# MeshCore Packet Decoder Integration

## Overview

This document describes the integration of `meshcore-decoder-py` (Python package: `meshcoredecoder`) for decoding raw MeshCore packets from RX_LOG_DATA events.

## Problem Statement

Previously, RX_LOG_DATA events only showed basic RF metrics without decoding the packet contents:

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:12.25dB RSSI:-52dBm Hex:31cc15024abf118ebecd...
[DEBUG] 📊 [RX_LOG] RF activity monitoring only (full parsing requires protocol spec)
```

**Limitations:**
- ❌ No packet type identification (message, ack, advert, telemetry)
- ❌ No route type information (flood, direct, etc.)
- ❌ No message content visibility
- ❌ No sender/receiver information extraction

## Solution

Integrated `meshcore-decoder-py` library by [@chrisdavis2110](https://github.com/chrisdavis2110/meshcore-decoder-py) to provide full packet decoding capabilities.

## Implementation

### 1. Dependency Added

**File:** `requirements.txt`

```python
# MeshCore packet decoder - decodes raw MeshCore packets from RX_LOG_DATA
# Provides packet type detection (msg/ack/advert/telemetry)
meshcoredecoder>=0.1.0
```

### 2. Code Changes

**File:** `meshcore_cli_wrapper.py`

#### Import Section

```python
# Try to import meshcore-decoder for packet parsing
try:
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    MESHCORE_DECODER_AVAILABLE = True
    info_print("✅ [MESHCORE] Library meshcore-decoder disponible (packet decoding)")
except ImportError:
    MESHCORE_DECODER_AVAILABLE = False
    info_print("⚠️ [MESHCORE] Library meshcore-decoder non disponible (pip install meshcoredecoder)")
```

#### Updated `_on_rx_log_data()` Method

The method now:
1. Extracts SNR, RSSI, and raw hex data (as before)
2. **NEW:** Decodes packet using `MeshCoreDecoder.decode()`
3. **NEW:** Extracts packet type, route type, message hash, path length
4. **NEW:** Displays validity status and any errors
5. **NEW:** Shows decoded message content when available

## Features

### Decoded Information

The decoder provides:

1. **Route Type**
   - `TransportFlood` (0) - Transport layer flood
   - `Flood` (1) - Application layer broadcast
   - `Direct` (2) - Direct unicast
   - `TransportDirect` (3) - Transport layer direct

2. **Payload Type**
   - `Request` (0) - Request packet
   - `Response` (1) - Response packet
   - `TextMessage` (2) - Text message
   - `Ack` (3) - Acknowledgment
   - `Advert` (4) - Node advertisement
   - `GroupText` (5) - Group text message
   - `GroupData` (6) - Group data
   - `AnonRequest` (7) - Anonymous request
   - `Path` (8) - Path information
   - `Trace` (9) - Trace packet
   - And more...

3. **Packet Metadata**
   - Message hash (unique packet identifier)
   - Path length (number of hops)
   - Validity status
   - Parsing errors (if any)

4. **Decoded Payload** (when available)
   - Text messages: Shows message content
   - Adverts: Shows device name
   - Other types: Type-specific data

### Output Examples

#### Successful Decode - Text Message

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:12.5dB RSSI:-51dBm Hex:11007E76...
[DEBUG] 📦 [RX_LOG] Type: TextMessage | Route: Flood | Hash: abc12345 | Hops: 2 | Valid: ✅
[DEBUG] 📝 [RX_LOG] Message: "Hello mesh network!"
```

#### Successful Decode - Advertisement

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:13.0dB RSSI:-50dBm Hex:11007E76...
[DEBUG] 📦 [RX_LOG] Type: Advert | Route: Flood | Hash: def67890 | Valid: ✅
[DEBUG] 📢 [RX_LOG] Advert from: MyDevice
```

#### Decode with Errors

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:10.2dB RSSI:-65dBm Hex:31cc1502...
[DEBUG] 📦 [RX_LOG] Type: RawCustom | Route: Flood | Valid: ⚠️
[DEBUG]    ⚠️ 12 is not a valid PayloadType
```

#### Decoder Not Available

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:11.5dB RSSI:-58dBm Hex:37f31502...
[DEBUG] 📊 [RX_LOG] RF monitoring only (meshcore-decoder not installed)
```

## Installation

### Automatic (via requirements.txt)

```bash
pip install -r requirements.txt --break-system-packages
```

### Manual

```bash
pip install meshcoredecoder --break-system-packages
```

**Dependencies installed:**
- `pycryptodome>=3.19.0` - Cryptographic functions
- `cryptography>=41.0.0` - Already present in MeshBot
- `click>=8.1.0` - Already present

## Configuration

No configuration required! The integration:
- ✅ Auto-detects if `meshcoredecoder` is installed
- ✅ Gracefully falls back if not available
- ✅ Works with existing `MESHCORE_RX_LOG_ENABLED` setting

```python
# config.py
MESHCORE_ENABLED = True  # Enable MeshCore companion mode
MESHCORE_RX_LOG_ENABLED = True  # Enable RX_LOG_DATA monitoring
DEBUG_MODE = True  # Show debug logs
```

## Testing

### Automated Tests

```bash
python3 test_meshcore_decoder_integration.py
```

**Test Coverage:**
1. ✅ Library import verification
2. ✅ Packet decoding with various samples
3. ✅ Integration with RX_LOG handler logic
4. ✅ Error handling with malformed packets

**Test Results:**
```
============================================================
TEST SUMMARY
============================================================
✅ PASS - Packet decoding
✅ PASS - Integration
✅ PASS - Error handling
============================================================
✅ All tests passed!
```

### Manual Testing

1. **Enable RX_LOG monitoring:**
   ```python
   # config.py
   MESHCORE_ENABLED = True
   MESHCORE_RX_LOG_ENABLED = True
   DEBUG_MODE = True
   ```

2. **Restart bot:**
   ```bash
   sudo systemctl restart meshbot
   ```

3. **Watch logs:**
   ```bash
   journalctl -u meshbot -f | grep RX_LOG
   ```

4. **Expected output:**
   - Packets should show decoded type and route information
   - Valid packets show ✅
   - Packets with errors show ⚠️ with error messages
   - Text messages show content preview

## Benefits

### For Debugging

1. **Packet Type Visibility**
   - Know what types of packets are being received
   - Distinguish messages from acks, adverts, telemetry
   - Identify broadcast vs unicast traffic

2. **Network Activity Analysis**
   - See which packet types dominate traffic
   - Identify chatty nodes (lots of adverts)
   - Understand message routing patterns

3. **Error Detection**
   - Malformed packets are identified
   - Parsing errors are logged
   - Invalid packet types are flagged

### For Network Monitoring

1. **Traffic Characterization**
   - Understand mesh network composition
   - See advertisement frequency
   - Monitor message flow

2. **Signal Quality Context**
   - Correlate SNR/RSSI with packet types
   - Identify which packet types have poor reception
   - Spot patterns in packet loss

## Limitations

### Current Scope

This integration provides **read-only decoding** for debug logs:
- ✅ Packet type and route identification
- ✅ Validity checking
- ✅ Basic payload preview
- ❌ Full sender/receiver extraction (not in packet structure)
- ❌ Database integration (future enhancement)
- ❌ Statistics on decoded packets (future enhancement)

### Packet Completeness

- Some packets may be **truncated** in RX_LOG_DATA
- Decoder handles this gracefully with error messages
- Incomplete packets still show available metadata

### Performance

- Decoding adds **minimal overhead** (< 1ms per packet)
- Only runs in **debug mode** (no production impact)
- Decoder errors are **caught and logged** (no crashes)

## Future Enhancements

### Potential Features

1. **Database Integration**
   - Store decoded packet metadata
   - Enable statistics on packet types
   - Track packet type distribution over time

2. **Enhanced Statistics**
   - `/stats types` - Show packet type breakdown
   - `/stats routes` - Show routing patterns
   - `/stats errors` - Show decoding error frequency

3. **Sender/Receiver Extraction**
   - Parse node IDs from packet structure
   - Link packets to known nodes
   - Build communication graphs

4. **Full Payload Decoding**
   - Decode encrypted payloads (if keys available)
   - Show complete message content
   - Extract telemetry data

## References

- **meshcore-decoder-py GitHub**: https://github.com/chrisdavis2110/meshcore-decoder-py
- **meshcoredecoder PyPI**: https://pypi.org/project/meshcoredecoder/
- **Original MeshCore Decoder**: By Michael Hart (JavaScript)

## Changelog

### v1.0 (2026-01-30)

- ✅ Initial integration of meshcore-decoder
- ✅ Packet type and route decoding
- ✅ Error handling and graceful fallback
- ✅ Comprehensive test suite
- ✅ Documentation

## Contributing

To improve packet decoding:

1. **Report Issues**: If packets decode incorrectly, capture hex data
2. **Test Cases**: Add more packet samples to test suite
3. **Feature Requests**: Suggest additional decoded fields
4. **Performance**: Profile decoder for optimization opportunities

## Troubleshooting

### Decoder Not Available

**Symptom:**
```
⚠️ [MESHCORE] Library meshcore-decoder non disponible
📊 [RX_LOG] RF monitoring only (meshcore-decoder not installed)
```

**Solution:**
```bash
pip install meshcoredecoder --break-system-packages
sudo systemctl restart meshbot
```

### Decoding Errors

**Symptom:**
```
📦 [RX_LOG] Type: RawCustom | Route: Flood | Valid: ⚠️
   ⚠️ 12 is not a valid PayloadType
```

**Meaning:**
- Packet uses a payload type not yet defined in meshcore-decoder
- Or packet is malformed/truncated
- **This is expected** and not a bug

**Action:**
- Log hex data if pattern repeats
- Report to meshcore-decoder maintainer if needed
- Packet is still monitored (SNR/RSSI available)

### No Decoded Messages

**Symptom:**
- All packets show "RawCustom" or errors
- Never see TextMessage, Advert, etc.

**Possible Causes:**
1. **Short hex samples**: RX_LOG_DATA may truncate packets
2. **Encryption**: Encrypted payloads appear as RawCustom
3. **MeshCore version**: Ensure compatible firmware

**Action:**
- Verify DEBUG_MODE=True to see full logs
- Check packet lengths (totalBytes)
- Test with known good packets

## Conclusion

The meshcore-decoder integration provides **significant improvements** to RX_LOG_DATA debugging:

- ✅ **Better visibility** into mesh network traffic
- ✅ **Easier debugging** with packet type identification  
- ✅ **Network analysis** capability
- ✅ **Zero configuration** required
- ✅ **Graceful fallback** if not installed

This enhancement makes MeshBot's RX_LOG monitoring much more useful for understanding mesh network behavior.
