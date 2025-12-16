# Meshtastic 2.7.15 DM Decryption

## Overview

Starting with Meshtastic firmware version 2.7.15, **Direct Messages (DMs) are now encrypted** by default. This document explains how the MeshBot handles this change.

## The Problem

### Before Meshtastic 2.7.15
- DM messages were sent in plaintext (only broadcast on Primary channel)
- Bot could read any DM sent to it directly
- Only messages on secondary channels with different PSK were encrypted

### With Meshtastic 2.7.15+
- DMs are now encrypted using the channel PSK
- Packets arrive with `encrypted` field instead of `decoded` field
- Without decryption, DMs appeared as "ENCRYPTED" in logs and were not processed

### User Impact
```
❌ Log message (before fix):
[DEBUG] 📦 ENCRYPTED de tigro t1000E f40da [direct] (SNR:12.0dB)

✅ Log message (after fix):
[DEBUG] 🔐 Attempting to decrypt DM from 0x0de3331e to us
[DEBUG] ✅ Successfully decrypted DM packet from 0x0de3331e
[DEBUG] 📨 Decrypted DM message: /help
[DEBUG] 📦 TEXT_MESSAGE_APP de tigro t1000E f40da [direct] (SNR:12.0dB)
```

## The Solution

### Implementation Details

**File**: `traffic_monitor.py`

**Key Changes**:
1. Added cryptography imports for AES-128-CTR decryption
2. Added protobuf imports for parsing decrypted data
3. Implemented `_decrypt_packet()` method
4. Enhanced `add_packet()` to detect and decrypt DM packets

### Decryption Algorithm

Meshtastic uses **AES-128-CTR** encryption:

- **Key**: Channel PSK (default: `1PG7OiApB1nwvP+rz05pAQ==` in base64)
- **Nonce**: `packet_id (8 bytes LE) + from_id (4 bytes LE) + counter (4 bytes zeros)`
- **Mode**: CTR (Counter) mode

### Detection Logic

The bot attempts decryption when ALL conditions are met:
1. ✅ Packet has `encrypted` field (not `decoded`)
2. ✅ Packet is addressed to our node (`to_id == my_node_id`)
3. ✅ Packet has a valid `id` field

### Processing Flow

```
┌─────────────────────────────────────────────┐
│  Packet Received                            │
│  'encrypted' field present                  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │ Is DM to us?  │
         └───────┬───────┘
                 │
        ┌────────┴────────┐
        │ Yes             │ No
        ▼                 ▼
┌────────────────┐  ┌──────────────────┐
│ Try Decrypt    │  │ Keep ENCRYPTED   │
│ with PSK       │  │ (not for us)     │
└───────┬────────┘  └──────────────────┘
        │
   ┌────┴─────┐
   │ Success? │
   └────┬─────┘
        │
   ┌────┴────┐
   │ Yes     │ No
   ▼         ▼
┌────────┐  ┌─────────────┐
│ Parse  │  │ Keep as     │
│ Decode │  │ ENCRYPTED   │
│ Process│  │ (wrong PSK) │
└────────┘  └─────────────┘
```

## Privacy & Security

### What is Decrypted
- ✅ **DMs to our node**: Decrypted and processed
- ❌ **Broadcast messages**: NOT decrypted (even if encrypted)
- ❌ **DMs to other nodes**: NOT decrypted (respects privacy)

### Security Considerations
1. **Default PSK**: Uses Meshtastic's default channel 0 PSK
2. **Custom PSK**: If network uses custom PSK, decryption fails gracefully
3. **Backward Compatible**: Non-encrypted messages work as before
4. **Privacy Respected**: Only decrypts messages intended for us

## Configuration

### Requirements
- **Python Library**: `cryptography>=41.0.0` (already in requirements.txt)
- **Meshtastic**: `meshtastic>=2.2.0` with protobuf support
- **Firmware**: Works with Meshtastic 2.7.15+ (and earlier versions)

### Optional: Custom PSK

If your network uses a custom channel PSK, you can configure it:

```python
# In traffic_monitor.py, modify _decrypt_packet() method
# Replace the default PSK with your custom one:
psk = base64.b64decode("YOUR_CUSTOM_PSK_BASE64==")
```

**Note**: Future enhancement could add PSK configuration to `config.py`.

## Testing

### Run Tests
```bash
python3 test_dm_decryption.py
```

### Test Coverage
1. ✅ Decrypt method correctness
2. ✅ Full encrypted DM packet handling
3. ✅ Broadcast packets remain encrypted
4. ✅ Privacy: only our DMs are decrypted

### Demo Script
```bash
python3 demo_dm_decryption.py
```

Shows before/after comparison and explains how decryption works.

## Troubleshooting

### DMs Still Show as ENCRYPTED

**Possible Causes**:
1. **Custom PSK**: Network uses non-default channel PSK
2. **Missing Libraries**: `cryptography` or `meshtastic` not installed
3. **Wrong Channel**: DM sent on secondary channel we don't have

**Solutions**:
1. Configure custom PSK in `_decrypt_packet()` method
2. Install dependencies: `pip install -r requirements.txt`
3. Ensure sender uses Primary channel (channel 0)

### Decryption Fails

**Check Logs**:
```
[DEBUG] 🔐 Attempting to decrypt DM from 0xABCDEF to us
[DEBUG] ⚠️ Failed to decrypt packet from 0xABCDEF: <error>
```

**Common Issues**:
- Sender uses different channel PSK
- Packet corrupted in transit
- Missing packet ID field

## Performance Impact

### Minimal Overhead
- Decryption only attempted for DMs to our node
- AES-CTR is fast (~1ms per packet on Raspberry Pi 5)
- No impact on broadcast or relay performance

### Memory Usage
- Single additional protobuf object per decrypted DM
- Immediate cleanup after conversion to dict
- No persistent memory increase

## Future Enhancements

### Potential Improvements
1. **Configurable PSK**: Add PSK setting to `config.py`
2. **Multi-Channel Support**: Try multiple PSKs automatically
3. **PSK Detection**: Auto-detect PSK from interface channels
4. **Statistics**: Track decryption success/failure rates

## References

- **Meshtastic Encryption**: https://meshtastic.org/docs/overview/encryption/
- **Protobuf Format**: https://github.com/meshtastic/protobufs
- **AES-CTR Mode**: https://en.wikipedia.org/wiki/Block_cipher_mode_of_operation#Counter_(CTR)
- **Cryptography Library**: https://cryptography.io/

## Changelog

### 2025-12-16 - Initial Implementation
- Added DM decryption for Meshtastic 2.7.15+
- Implemented `_decrypt_packet()` method
- Enhanced `add_packet()` with decryption logic
- Added comprehensive tests
- Created demo and documentation

---

**Status**: ✅ Fully Implemented and Tested  
**Version**: 1.0  
**Last Updated**: 2025-12-16
