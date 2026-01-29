# NameError Fix: packet_entry not defined

## Problem Report

User reported receiving DM messages but with Python traceback, and still no other packets visible in debug logs.

### Error Log
```
Jan 29 09:53:06 DietPi meshtastic-bot[391513]: [DEBUG] Erreur log paquet: name 'packet_entry' is not defined
Jan 29 09:53:06 DietPi meshtastic-bot[391513]: [DEBUG] Traceback (most recent call last):
Jan 29 09:53:06 DietPi meshtastic-bot[391513]:   File "/home/dietpi/bot/traffic_monitor.py", line 976, in _log_packet_debug
Jan 29 09:53:06 DietPi meshtastic-bot[391513]:     info_print(f"🔍 About to call _log_comprehensive_packet_debug for source={packet_entry.get('source')} type={packet_type}")
Jan 29 09:53:06 DietPi meshtastic-bot[391513]:                                                                               ^^^^^^^^^^^^
Jan 29 09:53:06 DietPi meshtastic-bot[391513]: NameError: name 'packet_entry' is not defined
```

### Impact
- ✅ Packets were being received (callback working)
- ✅ Packets were being saved to database
- ❌ Comprehensive packet debug was crashing with NameError
- ❌ User could not see full packet metadata in debug logs

## Root Cause Analysis

### The Issue

In `traffic_monitor.py`:

1. **Line 806**: `packet_entry` is defined in `add_packet()` method
   ```python
   packet_entry = {
       'timestamp': timestamp,
       'from_id': from_id,
       'to_id': to_id,
       'source': source,  # <-- This is the value we need
       ...
   }
   ```

2. **Line 917-918**: `_log_packet_debug()` is called
   ```python
   self._log_packet_debug(
       packet_type, sender_name, from_id, hops_taken, snr, packet)
   ```
   
   **Problem**: `source` is NOT passed as parameter!

3. **Line 926**: `_log_packet_debug()` method signature
   ```python
   def _log_packet_debug(self, packet_type, sender_name, from_id, hops_taken, snr, packet):
   ```
   
   **Problem**: Method doesn't have `source` parameter!

4. **Line 976**: Inside `_log_packet_debug()`, code tries to access `packet_entry`
   ```python
   info_print(f"🔍 About to call _log_comprehensive_packet_debug for source={packet_entry.get('source')} type={packet_type}")
   ```
   
   **Problem**: `packet_entry` is not in scope! → NameError

### Why This Happened

During the diagnostic logging additions, a diagnostic line was added at line 976 that referenced `packet_entry.get('source')`. However, `packet_entry` is a local variable in the `add_packet()` method and is not accessible inside `_log_packet_debug()`.

## Solution

Add `source` parameter to `_log_packet_debug()` method and pass it from the call site.

### Changes Made

#### 1. Update Method Signature (Line 926)

**Before:**
```python
def _log_packet_debug(self, packet_type, sender_name, from_id, hops_taken, snr, packet):
```

**After:**
```python
def _log_packet_debug(self, packet_type, source, sender_name, from_id, hops_taken, snr, packet):
```

#### 2. Update Call Site (Line 917-918)

**Before:**
```python
self._log_packet_debug(
    packet_type, sender_name, from_id, hops_taken, snr, packet)
```

**After:**
```python
self._log_packet_debug(
    packet_type, source, sender_name, from_id, hops_taken, snr, packet)
```

#### 3. Update Diagnostic Line (Line 976)

**Before:**
```python
info_print(f"🔍 About to call _log_comprehensive_packet_debug for source={packet_entry.get('source')} type={packet_type}")
```

**After:**
```python
info_print(f"🔍 About to call _log_comprehensive_packet_debug for source={source} type={packet_type}")
```

## Testing

### Syntax Validation

Created automated test that verifies:
- ✅ Method signature includes `source` parameter
- ✅ Call site passes `source` parameter
- ✅ Diagnostic line uses `source` variable
- ✅ No invalid `packet_entry` references
- ✅ Python syntax is valid

All checks passed! ✅

### Expected Behavior

With this fix, user should now see complete debug output:

```
[INFO] 🔔 on_message CALLED | packet=True | interface=False
[INFO] 📨 MESSAGE BRUT: '/power' | from=0x143bcd7f | to=0xfffffffe
[DEBUG] 🔍 Source détectée: MeshCore (MESHCORE_ENABLED=True)
[INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x143bcd7f
[DEBUG] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de Tigro T1000E
[DEBUG] 📦 TEXT_MESSAGE_APP de Tigro T1000E bcd7f [direct] (SNR:n/a)
[INFO] 🔍 About to call _log_comprehensive_packet_debug for source=meshcore type=TEXT_MESSAGE_APP
[INFO] 🔷 _log_comprehensive_packet_debug CALLED | type=TEXT_MESSAGE_APP
[DEBUG] ╔═══════════════════════════════════════════════════════════════
[DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
[DEBUG] ╠═══════════════════════════════════════════════════════════════
[DEBUG] ║ Packet ID: 123456
[DEBUG] ║ RX Time:   09:53:06
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 🔀 ROUTING
[DEBUG] ║   From:      Tigro T1000E (0x143bcd7f)
[DEBUG] ║   To:        0xfffffffe
[DEBUG] ║   Hops:      0/0 (limit: 0)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📋 PACKET METADATA
[DEBUG] ║   Family:    DIRECT (unicast)
[DEBUG] ║   Channel:   0 (Primary)
[DEBUG] ║   Priority:  DEFAULT (0)
[DEBUG] ║   Via MQTT:  No
[DEBUG] ║   Want ACK:  No
[DEBUG] ║   Want Resp: No
[DEBUG] ║   PublicKey: Not available
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📡 RADIO METRICS
[DEBUG] ║   RSSI:      0 dBm
[DEBUG] ║   SNR:       0.0 dB (🟠 Fair)
[DEBUG] ╟───────────────────────────────────────────────────────────────
[DEBUG] ║ 📄 DECODED CONTENT
[DEBUG] ║   Message:   "/power"
[DEBUG] ╚═══════════════════════════════════════════════════════════════
```

**No more NameError!** 🎉

## Benefits

1. ✅ **No more crashes** - NameError is fixed
2. ✅ **Complete logging** - Comprehensive packet debug now works
3. ✅ **Better diagnostics** - Source is clearly shown in logs
4. ✅ **User visibility** - MeshCore packets fully visible with metadata
5. ✅ **Proper separation** - MeshCore vs Meshtastic clearly identified

## Files Modified

- **traffic_monitor.py**
  - Line 926: Method signature (added `source` parameter)
  - Line 917-918: Call site (pass `source` parameter)
  - Line 976: Diagnostic line (use `source` variable)

## Verification

After deploying this fix, user should:
1. Restart the bot
2. Send a MeshCore message
3. Check logs: `journalctl -u meshbot -f | grep -E "🔵|🔍|🔷|╔"`
4. Should see complete packet debug output without NameError

## Related Issues

This fix completes the MeshCore logging implementation chain:
1. ✅ Source determination (MESHCORE_ENABLED first)
2. ✅ Packet fields (id, rxTime, rssi, snr, etc.)
3. ✅ Diagnostic logging (callback chain tracing)
4. ✅ Rollback to debug_print (user preference)
5. ✅ **NameError fix** (this commit) - Critical bug fix

## Conclusion

The NameError was preventing comprehensive packet debug from executing, which is why the user couldn't see full MeshCore packet details despite DEBUG_MODE=True. This fix ensures the entire debug output chain works correctly.
