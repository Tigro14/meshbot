# Quick Reference: MeshCore Diagnostic Markers

## What Was Changed

✅ **Rollback:** All `info_print` → `debug_print` (as requested)
✅ **Added:** 3 strategic entry-point diagnostics (always visible)

## Quick Test

```bash
# Watch logs for diagnostic markers
journalctl -u meshbot -f | grep -E "🔔|🔵|🔍|🔷"
```

## Diagnostic Markers (What to Look For)

### ✅ SUCCESS - All Markers Present
```
[INFO] 🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
[INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x12345678
[INFO] 🔍 About to call _log_comprehensive_packet_debug for source=meshcore
[INFO] 🔷 _log_comprehensive_packet_debug CALLED | type=TEXT_MESSAGE_APP
[DEBUG] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP
[DEBUG] 📦 TEXT_MESSAGE_APP de NodeName [direct] (SNR:n/a)
[DEBUG] ╔═══════════════════════════════════════
[DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
```
**Status:** ✅ WORKING! MeshCore packets fully visible!

---

### ❌ NO LOGS AT ALL
```
(nothing)
```
**Problem:** MeshCore interface not receiving messages
**Solutions:**
- Check serial port: `ls -la /dev/ttyUSB*`
- Test raw serial: `cat /dev/ttyUSB0`
- Verify MESHCORE_SERIAL_PORT in config.py
- Check device is connected
- Verify MeshCore firmware is running

---

### ❌ CALLBACK CALLED BUT add_packet NOT REACHED
```
[INFO] 🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
(nothing else - no 🔵)
```
**Problem:** Issue in main_bot.py between on_message and add_packet
**Solutions:**
- Check source determination (should be 'meshcore')
- Look for exceptions in logs
- Check if MESHCORE_ENABLED is True
- Verify no early return in on_message

---

### ❌ add_packet CALLED BUT STOPS INSIDE
```
[INFO] 🔔 on_message CALLED | from=0x12345678
[INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x12345678
(nothing else - no 🔍)
```
**Problem:** Packet blocked inside add_packet
**Possible causes:**
- **Deduplication:** Check packet has unique ID
- **Self-filtering:** from_id == my_node_id (packet from self)
- **Exception:** Check for error logs
- **Early return:** Some filter condition met

**Solutions:**
- Check logs for "Paquet dupliqué ignoré"
- Verify packet 'id' field is present and unique
- Ensure from_id != bot's own node ID
- Look for exception traces

---

### ❌ COMPREHENSIVE DEBUG REACHED BUT NO OUTPUT
```
[INFO] 🔔 on_message CALLED | from=0x12345678
[INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x12345678
[INFO] 🔍 About to call _log_comprehensive_packet_debug
[INFO] 🔷 _log_comprehensive_packet_debug CALLED | type=TEXT_MESSAGE_APP
(no [DEBUG] ╔═══ box)
```
**Problem:** DEBUG_MODE not actually True at runtime
**Solutions:**
- Restart bot after changing config: `sudo systemctl restart meshbot`
- Verify config.py: `grep DEBUG_MODE /path/to/config.py`
- Check if config.py is being loaded
- Look for "DEBUG_MODE = False" override elsewhere

---

## Quick Filter Commands

```bash
# Show only diagnostic entry points
journalctl -u meshbot -f | grep -E "🔔|🔵|🔍|🔷"

# Show MeshCore specific
journalctl -u meshbot -f | grep -E "meshcore|MESHCORE"

# Show complete packet flow
journalctl -u meshbot -f | grep -E "🔔|🔵|📨|🔍|🔷|📊|📦|╔"

# Last 5 minutes of MeshCore activity
journalctl -u meshbot --since "5 minutes ago" | grep -E "meshcore|MESHCORE"
```

## What to Report

If packets still don't appear, report:

1. **Which markers appear?**
   ```
   🔔 on_message CALLED: YES/NO
   🔵 add_packet ENTRY: YES/NO
   🔍 About to call: YES/NO
   🔷 comprehensive debug CALLED: YES/NO
   [DEBUG] ╔═══ box: YES/NO
   ```

2. **Share filtered logs:**
   ```bash
   journalctl -u meshbot --since "5 minutes ago" | grep -E "🔔|🔵|🔍|🔷|ERROR|Exception"
   ```

3. **Confirm configuration:**
   ```bash
   grep -E "DEBUG_MODE|MESHCORE_ENABLED|MESHCORE_SERIAL_PORT" config.py
   ```

4. **Check serial port:**
   ```bash
   ls -la /dev/ttyUSB*
   # Try reading raw data:
   cat /dev/ttyUSB0  # Ctrl+C after a few seconds
   ```

## Full Documentation

For complete diagnostic guide with all scenarios: **MESHCORE_DIAGNOSTIC_FLOW.md**
