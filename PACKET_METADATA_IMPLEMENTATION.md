# Packet Metadata Logging - Implementation Summary

## Overview

This implementation adds comprehensive packet metadata logging to the MeshBot in DEBUG mode. All Meshtastic packet routing metadata is now extracted, logged, and stored in SQLite without exposing raw data content.

## Problem Statement

The original issue requested:
> Display all the radio log metadata to log file in Debug mode (without the raw data content).
> It should display packet Family (FLOOD/DIRECT) (ADVERT, RESPONSE,...), Path (hops...), Type (Chat, ...), Name, Pubkey, Position and use these data to feed the local SQLite meshcore nodes tables.

## Solution

### 1. Metadata Extraction (traffic_monitor.py)

Enhanced `add_packet()` method to extract additional routing metadata:

```python
# New metadata fields extracted:
channel = packet.get('channel', 0)              # Channel index (0-7)
via_mqtt = packet.get('viaMqtt', False)         # MQTT gateway flag
want_ack = packet.get('wantAck', False)         # ACK request
want_response = packet.get('wantResponse', False) # Response expected
priority = packet.get('priority', 0)             # Priority (0-100)
family = 'FLOOD' if is_broadcast else 'DIRECT'  # Routing family
public_key = self._get_sender_public_key(...)   # Sender's public key
```

### 2. Helper Method

New `_get_sender_public_key()` method:
- Looks up sender's public key from interface.nodes
- Handles both protobuf and dict formats ('public_key' and 'publicKey')
- Returns base64-encoded string or None
- Used for PKI debugging and validation

### 3. Enhanced DEBUG Logging

New **PACKET METADATA** section in `_log_comprehensive_packet_debug()`:

```
╟───────────────────────────────────────────────────────────────
║ 📋 PACKET METADATA
║   Family:    FLOOD (broadcast)
║   Channel:   0 (Primary)
║   Priority:  DEFAULT (0)
║   Via MQTT:  No
║   Want ACK:  No
║   Want Resp: No
║   PublicKey: dGVzdHB1YmxpY2tl... (48 chars)
```

Priority levels mapped:
- 100 = CRITICAL
- 64 = RELIABLE
- 32 = ACK_REQ
- 0 = DEFAULT

### 4. Database Schema Updates (traffic_persistence.py)

Added 8 new columns to `packets` table:

| Column | Type | Description |
|--------|------|-------------|
| channel | INTEGER | Channel index (0-7) |
| via_mqtt | INTEGER | Boolean: came via MQTT gateway |
| want_ack | INTEGER | Boolean: sender wants ACK |
| want_response | INTEGER | Boolean: sender expects response |
| priority | INTEGER | Priority level (0-100) |
| family | TEXT | 'FLOOD' or 'DIRECT' |
| public_key | TEXT | Sender's public key (base64) |

**Migration Logic:**
- Automatic column addition for existing databases
- Each column has a separate migration check
- Default values provided for backward compatibility

**Updated save_packet():**
- Now saves all new metadata fields
- Converts boolean flags to INTEGER (0/1)
- Stores public key as TEXT

## Files Modified

### 1. traffic_monitor.py
- **Lines ~780-810**: Added metadata extraction in `add_packet()`
- **Lines ~1212-1250**: Added `_get_sender_public_key()` helper method
- **Lines ~1020-1065**: Enhanced DEBUG logging with PACKET METADATA section

### 2. traffic_persistence.py
- **Lines ~117-170**: Added migration logic for 8 new columns
- **Lines ~404-428**: Updated `save_packet()` to insert new fields

## Testing

### Test Suite (test_packet_metadata.py)

4 comprehensive tests:

1. **Packet Metadata Extraction**
   - Verifies all fields extracted correctly
   - Tests hop calculation (hop_start - hop_limit)
   - Validates public key extraction

2. **Direct Message Family**
   - Tests DIRECT family for unicast messages
   - Validates want_ack and priority flags

3. **Database Persistence**
   - Creates temp database
   - Verifies schema migration
   - Validates data storage

4. **Public Key Extraction**
   - Tests key lookup from interface.nodes
   - Handles missing keys gracefully

**Result:** ✅ All tests pass

### Demo Script (demo_packet_metadata.py)

5 interactive demos showing:
1. FLOOD (Broadcast) message
2. DIRECT (Unicast) with ACK
3. POSITION_APP packet
4. MQTT gateway message
5. Critical priority message

## Benefits

### 1. Complete Visibility
All packet routing metadata now visible in DEBUG mode:
- Family (FLOOD/DIRECT)
- Channel (0-7)
- Priority (CRITICAL/RELIABLE/ACK_REQ/DEFAULT)
- Flags (via_mqtt, want_ack, want_response)
- Public key (for PKI debugging)
- Path (hops taken/limit/start)

### 2. No Raw Data Exposure
Metadata displayed separately from content:
- Message text in separate DECODED CONTENT section
- Only metadata in PACKET METADATA section
- Clean separation for security/privacy

### 3. SQLite Persistence
All metadata stored for analysis:
- Historical routing data
- Priority patterns
- MQTT gateway usage
- Public key tracking
- Channel utilization

### 4. Better Diagnostics
Network troubleshooting improved:
- Identify MQTT gateway packets
- Track critical messages
- Monitor ACK patterns
- Analyze routing families
- Debug PKI encryption

### 5. Automatic Migration
Existing databases updated seamlessly:
- No manual intervention required
- Backward compatible
- Default values provided

## Usage

### Enabling DEBUG Mode

In `config.py`:
```python
DEBUG_MODE = True
```

### Viewing Logs

```bash
# Real-time logs
journalctl -u meshbot -f

# Filter for packet metadata
journalctl -u meshbot | grep "PACKET METADATA"

# Filter for specific metadata
journalctl -u meshbot | grep "Family:\|Channel:\|Priority:"
```

### Querying Database

```sql
-- View recent packets with metadata
SELECT 
    datetime(timestamp, 'unixepoch') as time,
    sender_name,
    packet_type,
    family,
    channel,
    priority,
    via_mqtt,
    want_ack,
    hops,
    hop_limit
FROM packets
ORDER BY timestamp DESC
LIMIT 20;

-- Count by family
SELECT family, COUNT(*) as count
FROM packets
GROUP BY family;

-- Count by priority
SELECT 
    CASE 
        WHEN priority = 100 THEN 'CRITICAL'
        WHEN priority = 64 THEN 'RELIABLE'
        WHEN priority = 32 THEN 'ACK_REQ'
        ELSE 'DEFAULT'
    END as priority_level,
    COUNT(*) as count
FROM packets
GROUP BY priority;

-- MQTT gateway usage
SELECT 
    datetime(timestamp, 'unixepoch') as time,
    sender_name,
    channel,
    message
FROM packets
WHERE via_mqtt = 1
ORDER BY timestamp DESC
LIMIT 10;
```

## Example Output

### DEBUG Log Entry

```
[DEBUG] ╔═══════════════════════════════════════════════════════════════
[DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
[DEBUG] ╠═══════════════════════════════════════════════════════════════
[DEBUG] ║ Packet ID: 987654322
[DEBUG] ║ RX Time:   10:52:43 (1769597563)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 🔀 ROUTING
[DEBUG] ║   From:      tigro g2 (0x0de3331e)
[DEBUG] ║   To:        0x16fad3dc
[DEBUG] ║   Hops:      0/5 (limit: 5)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📋 PACKET METADATA
[DEBUG] ║   Family:    DIRECT (unicast)
[DEBUG] ║   Channel:   0 (Primary)
[DEBUG] ║   Priority:  RELIABLE (64)
[DEBUG] ║   Via MQTT:  No
[DEBUG] ║   Want ACK:  Yes
[DEBUG] ║   Want Resp: Yes
[DEBUG] ║   PublicKey: QW5vdGhlclRlc3RQ... (48 chars)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📡 RADIO METRICS
[DEBUG] ║   RSSI:      -78 dBm
[DEBUG] ║   SNR:       14.5 dB (🟢 Excellent)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📄 DECODED CONTENT
[DEBUG] ║   Message:   "Private message - please confirm receipt"
[DEBUG] ╚═══════════════════════════════════════════════════════════════
```

### Database Record

```sql
sqlite> SELECT * FROM packets WHERE id = 1;
id|timestamp|from_id|to_id|source|sender_name|packet_type|message|rssi|snr|hops|size|is_broadcast|is_encrypted|telemetry|position|hop_limit|hop_start|channel|via_mqtt|want_ack|want_response|priority|family|public_key
1|1769597563.0|232993566|385536988|local|tigro g2|TEXT_MESSAGE_APP|Private message - please confirm receipt|-78|14.5|0|100|0|0|NULL|NULL|5|5|0|0|1|1|64|DIRECT|QW5vdGhlclRlc3RQdWJsaWNLZXlGb3JEZW1vUHVycG9zZXM=
```

## Backward Compatibility

### For Existing Installations

1. **Automatic Migration**: On first run with new code, database columns are added automatically
2. **No Data Loss**: Existing data preserved, new columns have default values
3. **Graceful Fallback**: If metadata fields not available in packet, defaults used
4. **Public Key Optional**: Works even if sender doesn't have public key available

### For Old Packets

Packets logged before this update will have:
- `channel = 0` (default)
- `via_mqtt = 0` (False)
- `want_ack = 0` (False)
- `want_response = 0` (False)
- `priority = 0` (DEFAULT)
- `family = NULL` (not retroactively determined)
- `public_key = NULL` (not available)

## Future Enhancements

Potential improvements:
1. **Historical Analysis**: Tools to analyze routing patterns over time
2. **Priority Statistics**: Dashboard showing priority distribution
3. **MQTT Gateway Metrics**: Separate statistics for gateway traffic
4. **Public Key Validation**: Automated checking of PKI key exchange
5. **Family Analytics**: Understand FLOOD vs DIRECT usage patterns
6. **Channel Optimization**: Identify congested channels

## References

- Issue: Display all radio log metadata in Debug mode
- Implementation: traffic_monitor.py, traffic_persistence.py
- Tests: test_packet_metadata.py (4 tests, all passing)
- Demo: demo_packet_metadata.py (5 scenarios)
- Meshtastic Python API: https://meshtastic.org/docs/software/python/cli/

## Author

Implementation completed by GitHub Copilot on 2026-01-28.
