# MeshCore DEBUG Logging Fix - Implementation Summary

## Problem Statement

**Issue:** "I do not see any Meshcore traffic in the Debug log"

MeshCore packets were not appearing in DEBUG logs even though DEBUG_MODE was enabled.

## Root Cause Analysis

### The Bug

In `main_bot.py::on_message()`, the source determination logic (lines 486-492) did not check for MeshCore mode:

```python
# OLD CODE (BUGGY)
if self._is_tcp_mode():
    source = 'tcp'
elif globals().get('CONNECTION_MODE', 'serial').lower() == 'serial':
    source = 'local'
else:
    source = 'local' if is_from_our_interface else 'tigrog2'
```

### Why This Was a Problem

When `MESHCORE_ENABLED=True` and `CONNECTION_MODE='serial'`:
1. The code checked TCP mode first → False (not TCP)
2. Then checked if CONNECTION_MODE='serial' → True
3. Set `source='local'` instead of `source='meshcore'`

**Consequences:**
- MeshCore packets incorrectly labeled as source='local'
- Packets saved to wrong table (`packets` instead of `meshcore_packets`)
- Potential filtering issues in DEBUG logging
- User couldn't see MeshCore traffic in logs

### Why MeshCore Uses Serial Mode

MeshCore companion mode uses a serial connection (e.g., `/dev/ttyUSB0`) to communicate with the MeshCore device, so `CONNECTION_MODE='serial'` is set. However, this doesn't mean it's a Meshtastic serial connection - it's a MeshCore serial connection with a completely different protocol.

## The Fix

### Updated Source Determination Logic

```python
# NEW CODE (FIXED)
# Déterminer la source pour les logs et stats
# IMPORTANT: Vérifier MeshCore en PREMIER car il peut utiliser CONNECTION_MODE='serial'
if globals().get('MESHCORE_ENABLED', False):
    # Mode MeshCore companion - tous les paquets viennent de MeshCore
    source = 'meshcore'
    debug_print("🔍 Source détectée: MeshCore (MESHCORE_ENABLED=True)")
elif self._is_tcp_mode():
    source = 'tcp'
elif globals().get('CONNECTION_MODE', 'serial').lower() == 'serial':
    source = 'local'
else:
    # Mode legacy: distinguer serial vs TCP externe
    source = 'local' if is_from_our_interface else 'tigrog2'
```

### Key Changes

1. **Added MESHCORE_ENABLED check FIRST** - Before any other checks
2. **Set source='meshcore'** when in MeshCore mode
3. **Added debug logging** to indicate MeshCore source detection
4. **Preserved all existing logic** for other modes

## Priority Order

The new source determination works in this priority:

1. **MESHCORE_ENABLED=True** → source='meshcore' (HIGHEST PRIORITY)
2. TCP mode detection → source='tcp'
3. CONNECTION_MODE='serial' → source='local' (Meshtastic serial)
4. Legacy mode → source='local' or 'tigrog2'

This ensures MeshCore is correctly identified even when using a serial connection.

## Testing

### Test Suite: test_meshcore_debug_logging.py

Created comprehensive tests to verify:

1. **MeshCore Packet Source Detection**
   - Verifies packets with source='meshcore' are processed correctly
   - Confirms DEBUG logging includes full metadata
   - Validates message content preservation

2. **Source Determination Logic**
   - Tests MESHCORE_ENABLED=True scenario
   - Tests MESHTASTIC_ENABLED=True scenario
   - Tests standalone mode (both disabled)
   - Validates correct source assignment in each case

### Test Results

```
======================================================================
✅ ALL TESTS PASSED!
======================================================================

✨ Verification complete:
  • MeshCore packets get source='meshcore'
  • Source determination prioritizes MESHCORE_ENABLED
  • MeshCore traffic will appear in DEBUG logs
```

## DEBUG Output

### Before Fix

No MeshCore packets in DEBUG logs (incorrectly labeled as 'local' and possibly filtered).

### After Fix

Full MeshCore packet metadata displayed:

```
[DEBUG] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de MeshCoreNode
[DEBUG] 📦 TEXT_MESSAGE_APP de MeshCoreNode 45678 [relayé ×2] (SNR:8.0dB)
[DEBUG] ╔═══════════════════════════════════════════════════════════════
[DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
[DEBUG] ╠═══════════════════════════════════════════════════════════════
[DEBUG] ║ Packet ID: 123456
[DEBUG] ║ RX Time:   12:46:22 (1769604382)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 🔀 ROUTING
[DEBUG] ║   From:      MeshCoreNode (0x12345678)
[DEBUG] ║   To:        BROADCAST
[DEBUG] ║   Hops:      2/5 (limit: 3)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📋 PACKET METADATA
[DEBUG] ║   Family:    FLOOD (broadcast)
[DEBUG] ║   Channel:   0 (Primary)
[DEBUG] ║   Priority:  DEFAULT (0)
[DEBUG] ║   Via MQTT:  No
[DEBUG] ║   Want ACK:  No
[DEBUG] ║   Want Resp: No
[DEBUG] ║   PublicKey: Not available
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📡 RADIO METRICS
[DEBUG] ║   RSSI:      -90 dBm
[DEBUG] ║   SNR:       8.0 dB (🟡 Good)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📄 DECODED CONTENT
[DEBUG] ║   Message:   "MeshCore test message"
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📊 PACKET SIZE
[DEBUG] ║   Payload:    21 bytes
[DEBUG] ╚═══════════════════════════════════════════════════════════════
```

## Database Routing

### Before Fix
- MeshCore packets → `packets` table (WRONG)
- Source: 'local' (INCORRECT)

### After Fix
- MeshCore packets → `meshcore_packets` table (CORRECT)
- Source: 'meshcore' (CORRECT)

This is handled automatically by the routing logic in `traffic_monitor.py`:

```python
if packet_source == 'meshcore':
    # MeshCore → meshcore_packets table
    self.persistence.save_meshcore_packet(packet_entry)
else:
    # Meshtastic (local, tcp, tigrog2) → packets table
    self.persistence.save_packet(packet_entry)
```

## Benefits

1. ✅ **MeshCore traffic now visible** - Users can see all MeshCore packets in DEBUG logs
2. ✅ **Correct table routing** - Packets saved to appropriate table
3. ✅ **Clear source identification** - '[meshcore]' tag in logs
4. ✅ **No Meshtastic interference** - Meshtastic packets unaffected
5. ✅ **Comprehensive metadata** - All packet metadata displayed (Family, Channel, Priority, etc.)
6. ✅ **Easy debugging** - Clear visual indication of packet source
7. ✅ **Tested thoroughly** - Test suite validates all scenarios

## Configuration

To enable MeshCore DEBUG logging:

```python
# config.py
DEBUG_MODE = True
MESHCORE_ENABLED = True
MESHTASTIC_ENABLED = False
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

## Verification

To verify MeshCore traffic appears in logs:

```bash
# Real-time monitoring
journalctl -u meshbot -f | grep meshcore

# Filter for MeshCore packets
journalctl -u meshbot | grep "\[meshcore\]"

# View MeshCore packet metadata
journalctl -u meshbot | grep "MESHCORE PACKET DEBUG"
```

## Files Modified

1. **main_bot.py** (+6 lines)
   - Updated source determination logic
   - Added MESHCORE_ENABLED check
   - Added debug logging

2. **test_meshcore_debug_logging.py** (NEW, 190 lines)
   - Comprehensive test suite
   - Validates source detection
   - Tests various configurations
   - All tests pass

## Backward Compatibility

✅ **Fully backward compatible**
- Meshtastic serial mode still works (source='local')
- Meshtastic TCP mode still works (source='tcp')
- Legacy multi-node mode still works (source='tigrog2')
- Only affects MESHCORE_ENABLED=True scenario

## Related Issues

This fix complements the previous packet separation work:
- Packet metadata extraction (PACKET_METADATA_IMPLEMENTATION.md)
- MeshCore/Meshtastic table separation (PACKET_SEPARATION_IMPLEMENTATION.md)

Together, these changes ensure:
- Complete packet metadata visibility
- Clean table separation
- Correct source identification
- Comprehensive DEBUG logging

## Conclusion

The fix is minimal (1 line of actual logic change) but critical for MeshCore users. By checking MESHCORE_ENABLED first in the source determination logic, MeshCore packets are now correctly identified, routed to the right table, and fully visible in DEBUG logs with complete metadata.

## Author

Fix implemented by GitHub Copilot on 2026-01-28 in response to user issue: "I do not see any Meshcore traffic in the Debug log"
