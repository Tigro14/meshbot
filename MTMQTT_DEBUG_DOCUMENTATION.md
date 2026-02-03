# MTMQTT_DEBUG: Meshtastic MQTT Traffic Debugging

## Overview

The `MTMQTT_DEBUG` flag provides granular control over Meshtastic MQTT traffic debugging without requiring full `DEBUG_MODE=True`. This allows you to troubleshoot MQTT neighbor collection issues independently.

## What is MTMQTT?

**MTMQTT** = **M**esh**t**astic **MQTT** traffic

This refers to MQTT messages from the Meshtastic network that the bot receives via `mqtt_neighbor_collector.py`. These messages contain:
- Neighbor information (NEIGHBORINFO_APP)
- Node information (NODEINFO_APP)
- Position data (POSITION_APP)
- Telemetry data (TELEMETRY_APP)

## Configuration

### Enable/Disable Flag

In `config.py`:

```python
# ========================================
# MTMQTT DEBUG (Meshtastic MQTT Traffic)
# ========================================
MTMQTT_DEBUG = False  # Default: disabled
```

**Options:**
- `False` (default): Minimal logging, only critical errors
- `True`: Detailed MQTT traffic debugging with `[MTMQTT]` prefix

### When to Enable

Enable `MTMQTT_DEBUG = True` when:
1. MQTT neighbor collection is not working
2. Debugging connection issues to MQTT server
3. Investigating why neighbor data is not being saved
4. Troubleshooting packet processing issues
5. Verifying MQTT message reception

## Debug Output Examples

### Connection Events

```
[MTMQTT] Starting connection to serveurperso.com:1883
[MTMQTT] Authentication configured for user: meshdev
👥 Connecté au serveur MQTT Meshtastic
[MTMQTT] Topic subscription: msh/EU_868/2/e/MediumFast/#
[MTMQTT] Connected to serveurperso.com:1883
[MTMQTT] Ready to receive Meshtastic MQTT traffic
```

### Message Reception

```
[MTMQTT] Received message on topic: msh/EU_868/2/e/MediumFast/!12345678
[MTMQTT] Packet from !1a2b3c4d (ID: 987654321) via gateway: !12345678
[MTMQTT] Processing NEIGHBORINFO_APP packet from !1a2b3c4d
```

### Neighbor Processing

```
[MTMQTT] Processing NEIGHBORINFO from !1a2b3c4d
[MTMQTT] Node !1a2b3c4d reports 3 neighbors
[MTMQTT]   → Neighbor !5e6f7g8h SNR=8.5dB
[MTMQTT]   → Neighbor !9i0j1k2l SNR=12.3dB
[MTMQTT]   → Neighbor !3m4n5o6p SNR=6.8dB
```

### Deduplication

```
[MTMQTT] Duplicate packet filtered: 987654321 from !1a2b3c4d
```

### Errors

```
[MTMQTT] Failed to parse ServiceEnvelope: invalid protobuf data
[MTMQTT] Error processing message: AttributeError: 'NoneType' object has no attribute 'portnum'
[MTMQTT] Traceback: ...
```

### Disconnection

```
[MTMQTT] Unexpected disconnect: reason_code=1
👥 Déconnexion MQTT inattendue: code 1
```

## Implementation Details

### Code Pattern

All debug logging follows this pattern:

```python
if MTMQTT_DEBUG:
    info_print("[MTMQTT] Debug message here")
```

**Why `info_print()` instead of `debug_print()`?**
- `debug_print()` only shows when `DEBUG_MODE=True`
- `info_print()` always shows (written to stdout)
- This allows MTMQTT debugging without full debug mode

### Debug Points

Debug logging is added at these key points:

1. **Connection lifecycle:**
   - Connection start
   - Authentication
   - Topic subscription
   - Connection success/failure
   - Disconnection

2. **Message processing:**
   - Message reception (topic info)
   - Envelope parsing
   - Packet metadata (from, ID, gateway)
   - Packet type identification
   - Deduplication

3. **Data processing:**
   - NEIGHBORINFO parsing
   - Neighbor count and details
   - SNR values per neighbor
   - Database saves

4. **Errors:**
   - Parsing failures
   - Processing errors
   - Traceback details

### Prefix Convention

All debug messages use the `[MTMQTT]` prefix for easy filtering:

```bash
# View only MTMQTT debug logs
journalctl -u meshbot | grep '\[MTMQTT\]'

# View last 100 MTMQTT logs
journalctl -u meshbot -n 100 | grep '\[MTMQTT\]'

# Follow live MTMQTT logs
journalctl -u meshbot -f | grep --line-buffered '\[MTMQTT\]'
```

## Comparison with DEBUG_MODE

| Feature | MTMQTT_DEBUG=True | DEBUG_MODE=True |
|---------|-------------------|-----------------|
| Scope | MQTT traffic only | All bot components |
| Visibility | Always visible | Only in debug mode |
| Prefix | `[MTMQTT]` | Various |
| Use case | MQTT troubleshooting | Full bot debug |
| Performance | Minimal impact | Higher impact |

## Comparison with MCMQTT (Future)

| Network | Flag | Status | Purpose |
|---------|------|--------|---------|
| Meshtastic MQTT | MTMQTT_DEBUG | ✅ Implemented | Debug Meshtastic MQTT traffic |
| Meshcore MQTT | MCMQTT_DEBUG | ⏳ Future | Debug Meshcore MQTT traffic (planned) |

**Note:** MCMQTT (Meshcore MQTT) debugging will be implemented separately in a future update.

## Troubleshooting Examples

### Problem: No neighbor data being saved

**Enable debug:**
```python
MTMQTT_DEBUG = True
```

**Check for:**
1. Connection established?
   ```
   [MTMQTT] Connected to serveurperso.com:1883
   ```

2. Messages received?
   ```
   [MTMQTT] Received message on topic: ...
   ```

3. Packets processed?
   ```
   [MTMQTT] Processing NEIGHBORINFO_APP packet
   ```

4. Neighbors found?
   ```
   [MTMQTT] Node !1a2b3c4d reports 3 neighbors
   ```

### Problem: Connection fails

**Check debug output:**
```
[MTMQTT] Starting connection to serveurperso.com:1883
[MTMQTT] Connection failed: rc=5
```

**Resolution code meanings:**
- `rc=1`: Connection refused (bad protocol)
- `rc=2`: Identifier rejected
- `rc=3`: Server unavailable
- `rc=4`: Bad username/password
- `rc=5`: Not authorized

### Problem: Duplicates filtered too aggressively

**Check deduplication:**
```
[MTMQTT] Duplicate packet filtered: 987654321 from !1a2b3c4d
```

If too many duplicates, check:
- Multiple gateways relaying same packet (expected)
- Deduplication window (20 seconds by default)

## Performance Impact

Enabling `MTMQTT_DEBUG = True` has **minimal performance impact** because:
1. Only affects MQTT message processing (not serial/TCP)
2. Uses simple conditional checks (`if MTMQTT_DEBUG:`)
3. Output is written asynchronously
4. No expensive operations added

**Recommendation:** Safe to enable in production for troubleshooting.

## Testing

Run the test suite to verify functionality:

```bash
python3 test_mtmqtt_debug.py
```

Expected output:
```
✅ ALL TESTS PASSED

MTMQTT_DEBUG implementation is working correctly!
```

## Related Files

- `config.py.sample` - Configuration template with MTMQTT_DEBUG
- `config.py` - Active configuration (gitignored)
- `mqtt_neighbor_collector.py` - MQTT collector with debug logging
- `test_mtmqtt_debug.py` - Test suite

## Future Enhancements

1. **MCMQTT_DEBUG flag** - Similar debugging for Meshcore MQTT traffic
2. **Log level control** - Fine-grained control (INFO, DEBUG, TRACE)
3. **Performance metrics** - Message rate, processing time
4. **Filtering options** - Debug specific nodes or packet types

## Summary

The `MTMQTT_DEBUG` flag provides:
- ✅ Granular control over Meshtastic MQTT debugging
- ✅ Independent from full DEBUG_MODE
- ✅ Easy filtering with `[MTMQTT]` prefix
- ✅ Minimal performance impact
- ✅ Comprehensive coverage of MQTT lifecycle
- ✅ Ready for production troubleshooting

Enable it when you need to debug MQTT neighbor collection without the noise of full debug mode!
