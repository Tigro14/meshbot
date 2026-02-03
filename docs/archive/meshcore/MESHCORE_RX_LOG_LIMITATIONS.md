# MeshCore RX_LOG_DATA Limitations and Protocol Parsing

## ⚠️ UPDATE (2026-01-30): LIMITATIONS RESOLVED ⚠️

**The packet parsing limitation described below has been resolved!**

We now integrate `meshcore-decoder-py` library which provides full packet decoding:
- ✅ Packet type identification (TextMessage, Ack, Advert, etc.)
- ✅ Route type detection (Flood, Direct, etc.)
- ✅ Message content preview
- ✅ Validity checking and error reporting

**See:** `MESHCORE_DECODER_INTEGRATION.md` for complete documentation.

---

## Historical Context (Pre-2026-01-30)

This document describes the **original limitation** that existed before meshcore-decoder integration.

## Current Status

RX_LOG_DATA monitoring is **working** but **limited** due to lack of MeshCore protocol specification.

### What Works ✅

1. **RF Activity Detection**
   - Bot receives RX_LOG_DATA events for ALL RF packets
   - Includes broadcasts, telemetry, position updates, etc.
   - Not limited to DMs only

2. **Signal Quality Metrics**
   - SNR (Signal-to-Noise Ratio) in dB
   - RSSI (Received Signal Strength Indicator) in dBm
   - Useful for network diagnostics

3. **Raw Packet Data**
   - Raw hex representation of packet
   - Can be manually analyzed if protocol is known
   - First 20 characters logged for visibility

4. **Network Activity Monitoring**
   - Confirms mesh network is active
   - Shows when packets are received
   - Updates connection healthcheck

### What Doesn't Work ❌

1. **Packet Parsing**
   - Cannot extract sender ID (from)
   - Cannot extract recipient ID (to)
   - Cannot determine packet type (TEXT_MESSAGE_APP, TELEMETRY_APP, etc.)
   - Cannot decode payload/message content

2. **Database Integration**
   - RX_LOG_DATA packets not saved to database
   - Only CONTACT_MSG_RECV (DMs) create packet entries
   - Statistics commands don't include RF traffic

3. **Command Processing**
   - Broadcast commands not recognized
   - Only DMs trigger bot commands
   - No visibility into general mesh conversations

## Why This Limitation Exists

### Missing: MeshCore Protocol Specification

To parse RX_LOG_DATA packets, we need documentation for:

1. **Packet Header Format**
   - Byte positions for sender ID
   - Byte positions for recipient ID
   - Packet type field location
   - Length fields and delimiters

2. **Packet Type Definitions**
   - Type codes (e.g., 0x01 = TEXT_MESSAGE_APP)
   - Type-specific payload formats
   - Encryption indicators

3. **Field Encoding**
   - ID encoding (4-byte hex, little-endian?)
   - Length prefixes
   - CRC/checksum locations

4. **Payload Decoding**
   - Text encoding (UTF-8?)
   - Structured data formats
   - Encryption methods

### What We Currently Have

```python
# RX_LOG_DATA event payload:
{
    'snr': 12.5,           # ✅ Available
    'rssi': -51,           # ✅ Available
    'raw_hex': '32cd2e...' # ✅ Available but unparseable
}
```

### What We Need

```python
# Hypothetical parsed packet (if we had protocol spec):
{
    'from_id': 0x12345678,    # ❌ Not available (need protocol parsing)
    'to_id': 0xFFFFFFFF,      # ❌ Not available
    'packet_type': 'TEXT_MESSAGE_APP',  # ❌ Not available
    'payload': 'Hello world', # ❌ Not available
    'hop_limit': 3,           # ❌ Not available
    'hop_start': 5,           # ❌ Not available
}
```

## Current Log Output

### With RX_LOG_ENABLED=True

```bash
journalctl -u meshbot -f | grep RX_LOG
```

Output:
```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:12.5dB RSSI:-51dBm Hex:32cd2e009211066609cf...
[DEBUG] 📊 [RX_LOG] RF activity monitoring only (full parsing requires protocol spec)
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:13.0dB RSSI:-50dBm Hex:34ce1101bf4bef9661d6...
[DEBUG] 📊 [RX_LOG] RF activity monitoring only (full parsing requires protocol spec)
```

**Meaning:**
- ✅ RF packets are being received
- ✅ Network is active
- ✅ Signal quality is good (SNR >10dB)
- ℹ️  Packets cannot be fully parsed (expected)

## Use Cases

### When to Enable RX_LOG_ENABLED

**Enable (`True`)** if you want to:
- ✅ Monitor RF activity (debugging)
- ✅ Track signal quality across all packets
- ✅ Verify mesh network is working
- ✅ Diagnose connectivity issues
- ✅ See raw hex data for manual analysis

**Disable (`False`)** if you:
- Want less log spam (debug mode only)
- Only care about DMs (CONTACT_MSG_RECV)
- Don't need RF monitoring

### Current Recommendations

For most users: **Leave ENABLED**
- Provides visibility into network activity
- Confirms mesh is working
- Useful for troubleshooting
- Minimal overhead (debug-only logs)

## Comparison: CONTACT_MSG_RECV vs RX_LOG_DATA

| Aspect | CONTACT_MSG_RECV | RX_LOG_DATA |
|--------|------------------|-------------|
| **Availability** | ✅ Fully parsed | ✅ Raw data only |
| **Message Type** | DMs only | All RF packets |
| **Sender ID** | ✅ Yes | ❌ No (needs parsing) |
| **Recipient ID** | ✅ Yes | ❌ No (needs parsing) |
| **Message Content** | ✅ Decoded text | ❌ Raw hex only |
| **Signal Quality** | ❌ No | ✅ SNR, RSSI |
| **Packet Type** | ✅ Always TEXT_MESSAGE | ❌ Unknown |
| **Database Entry** | ✅ Created | ❌ Not created |
| **Command Processing** | ✅ Yes | ❌ No |

## Why Database Shows "0 Packets"

This is **EXPECTED** with current implementation:

1. **RX_LOG_DATA** shows RF activity but **doesn't create packet entries**
   - No parsing → no database insertion
   - Logs show activity but database remains empty

2. **CONTACT_MSG_RECV** creates packet entries but **only for DMs**
   - In companion mode, only DMs to/from user trigger this event
   - If only 1 DM sent → 1 packet in database
   - After 48h cleanup → "0 packets"

3. **This is not a bug** - it's the current limitation
   - To see database fill up: send more DMs
   - To see all packets in database: need protocol parsing

## Workarounds

### Option 1: Use CONTACT_MSG_RECV (Current)

**Best for:** Testing DM functionality
```python
# config.py
MESHCORE_RX_LOG_ENABLED = False  # DMs only
```

Send DMs via companion app to test:
- Message delivery
- Command processing
- Database persistence
- Statistics (for DMs)

### Option 2: Use RX_LOG_DATA for Monitoring (Current)

**Best for:** Network diagnostics
```python
# config.py
MESHCORE_RX_LOG_ENABLED = True   # RF monitoring
DEBUG_MODE = True                 # See logs
```

Monitor logs to verify:
- RF activity present
- Signal quality acceptable
- Network operational

### Option 3: Wait for Protocol Spec (Future)

Once MeshCore protocol documentation is available:
- Implement packet parsing
- Extract from/to/type from raw_hex
- Create database entries for all packets
- Enable full statistics

## Future Enhancement Path

### Step 1: Obtain Protocol Specification

Need documentation for:
- MeshCore packet format
- Header structure
- Type definitions
- Payload encoding

**Possible sources:**
- MeshCore official documentation
- Reverse engineering (ethical/legal considerations)
- Community contributions
- MeshCore source code analysis

### Step 2: Implement Parser

```python
def parse_meshcore_packet(raw_hex):
    """
    Parse MeshCore packet from raw hex string
    
    Returns:
        dict with from_id, to_id, packet_type, payload
    """
    # Extract header (bytes 0-N)
    header = bytes.fromhex(raw_hex[:20])
    
    # Parse sender ID (hypothetical)
    from_id = int.from_bytes(header[0:4], byteorder='little')
    
    # Parse recipient ID
    to_id = int.from_bytes(header[4:8], byteorder='little')
    
    # Parse packet type
    packet_type_code = header[8]
    packet_type = PACKET_TYPE_MAP.get(packet_type_code, 'UNKNOWN_APP')
    
    # Parse payload
    payload_hex = raw_hex[20:]  # After header
    payload = bytes.fromhex(payload_hex).decode('utf-8')
    
    return {
        'from_id': from_id,
        'to_id': to_id,
        'packet_type': packet_type,
        'payload': payload
    }
```

### Step 3: Integrate Parser

Update `_on_rx_log_data()`:
```python
def _on_rx_log_data(self, event):
    # Extract RF data
    raw_hex = payload.get('raw_hex', '')
    snr = payload.get('snr', 0.0)
    rssi = payload.get('rssi', 0)
    
    # Parse packet (NEW)
    parsed = parse_meshcore_packet(raw_hex)
    
    # Create packet entry (NEW)
    packet = {
        'from': parsed['from_id'],
        'to': parsed['to_id'],
        'id': random.randint(100000, 999999),
        'rxTime': int(time.time()),
        'rssi': rssi,
        'snr': snr,
        'decoded': {
            'portnum': parsed['packet_type'],
            'payload': parsed['payload'].encode('utf-8')
        }
    }
    
    # Call message_callback (NEW)
    if self.message_callback:
        self.message_callback(packet, self)
```

### Step 4: Test and Verify

- Verify from/to IDs match known nodes
- Verify packet types are correct
- Verify payload decoding works
- Test with broadcasts, DMs, telemetry
- Validate database entries

## Summary

### Current State ✅

- RX_LOG_DATA **works** for RF monitoring
- Provides valuable signal quality data
- Shows network activity
- Limited by lack of protocol spec

### What You'll See Now 👀

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:12.5dB RSSI:-51dBm
[DEBUG] 📊 [RX_LOG] RF activity monitoring only
```

**Meaning:** Network is active, but full parsing not available

### What's Coming 🔮

Once protocol spec is available:
- Full packet parsing
- Database integration
- Complete statistics
- Broadcast command processing

### Recommendation 💡

**Leave RX_LOG_ENABLED=True** to:
- Confirm network activity
- Monitor signal quality
- Aid debugging

**Use CONTACT_MSG_RECV** for:
- Sending/receiving DMs
- Command processing
- Database population (DMs only)

## Questions?

If you have MeshCore protocol documentation or insights, please share!
This would enable full packet parsing and unlock RX_LOG_DATA's potential.
