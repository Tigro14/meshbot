# MeshCore Diagnostic Flow - Identifying Where Packets Are Blocked

## User Situation

**User feedback:** "No, i AM in debug mode already and cannot see any meshcore traffic in the debug log, please rollback info_print for those logs"

**Key facts:**
1. User IS in DEBUG_MODE=True
2. STILL no MeshCore traffic visible
3. Previous info_print changes did not help

## Conclusion

The problem is NOT that logs are hidden by DEBUG_MODE. The problem is that **packets are not reaching the logging code at all**, or something is blocking them before they get logged.

## Rollback Complete ✅

All `info_print` changes have been rolled back to `debug_print`:
- `traffic_monitor.py` line 909: `📊 Paquet enregistré` → debug_print
- `traffic_monitor.py` line 946: `📦 TEXT_MESSAGE_APP` → debug_print  
- `meshcore_serial_interface.py` line 141: `📨 [MESHCORE-TEXT] Reçu` → debug_print
- `meshcore_serial_interface.py` line 145: `📨 [MESHCORE-BINARY] Reçu` → debug_print

## New Diagnostic Approach

Instead of changing all logs to info_print, we added **strategic entry-point diagnostics** that use `info_print()` to trace packet flow, even without DEBUG_MODE.

### 3 Strategic Entry Points

#### 1. add_packet() Entry (Line 631)
```python
info_print(f"🔵 add_packet ENTRY | source={source} | from=0x{from_id:08x} | interface={type(interface).__name__}")
```
**Purpose:** Confirm packets are reaching traffic_monitor.add_packet()

#### 2. Before Comprehensive Debug (Line 976)
```python
info_print(f"🔍 About to call _log_comprehensive_packet_debug for source={packet_entry.get('source')} type={packet_type}")
```
**Purpose:** Confirm packet processing completed, about to show comprehensive debug

#### 3. Inside Comprehensive Debug (Line 1013)
```python
info_print(f"🔷 _log_comprehensive_packet_debug CALLED | type={packet_type} | from=0x{from_id:08x}")
```
**Purpose:** Confirm comprehensive debug method was actually called

## Diagnostic Flow Chart

```
Message arrives → MeshCore Interface
                     ↓
         📨 Reçu (debug_print - DEBUG_MODE only)
                     ↓
         Callback invoked → main_bot.on_message()
                     ↓
         🔔 on_message CALLED (info_print - ALWAYS visible)
                     ↓
         traffic_monitor.add_packet()
                     ↓
         🔵 add_packet ENTRY (info_print - ALWAYS visible) ← ENTRY POINT #1
                     ↓
         Process packet, save to SQLite
                     ↓
         📊 Paquet enregistré (debug_print - DEBUG_MODE only)
                     ↓
         🔍 About to call comprehensive debug (info_print) ← ENTRY POINT #2
                     ↓
         _log_comprehensive_packet_debug()
                     ↓
         🔷 Called (info_print - ALWAYS visible) ← ENTRY POINT #3
                     ↓
         ╔═══════════════════
         ║ PACKET DEBUG (debug_print - DEBUG_MODE only)
         ╚═══════════════════
```

## How to Use Diagnostics

### Step 1: Enable DEBUG_MODE
```python
# config.py
DEBUG_MODE = True
MESHCORE_ENABLED = True
```

### Step 2: Watch Logs
```bash
journalctl -u meshbot -f
```

### Step 3: Send Test Message
Send a test message through MeshCore.

### Step 4: Check Which Markers Appear

#### Scenario A: No logs at all
```
(nothing)
```
**Problem:** MeshCore interface not receiving messages
**Check:**
- Is MeshCore serial port correct?
- Is device connected?
- Is MeshCore firmware running?
- Use `cat /dev/ttyUSB0` to see raw serial data

#### Scenario B: Callback never reaches add_packet
```
[INFO] 🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
(nothing else)
```
**Problem:** Issue in main_bot.py between on_message and add_packet
**Check:**
- Is source determination working? (should set source='meshcore')
- Is there early return in on_message?
- Are there exceptions being caught?

#### Scenario C: add_packet called but stops inside
```
[INFO] 🔔 on_message CALLED | from=0x12345678
[INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x12345678
(nothing else - no "About to call")
```
**Problem:** Packet blocked inside add_packet
**Possible causes:**
- Deduplication filtered it (check packet ID)
- Exception during processing (check for error logs)
- Early return due to filtering logic
- Packet from self (from_id == my_node_id)

#### Scenario D: Everything reaches comprehensive debug
```
[INFO] 🔔 on_message CALLED | from=0x12345678
[INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x12345678
[INFO] 🔍 About to call _log_comprehensive_packet_debug for source=meshcore
[INFO] 🔷 _log_comprehensive_packet_debug CALLED | type=TEXT_MESSAGE_APP
(no DEBUG box output)
```
**Problem:** DEBUG_MODE not actually True at runtime
**Check:**
- Restart bot after changing DEBUG_MODE
- Check `globals().get('DEBUG_MODE', False)` in utils.py
- Verify config.py is being loaded

#### Scenario E: Success! (Everything works)
```
[INFO] 🔔 on_message CALLED | from=0x12345678 | interface=MeshCoreSerialInterface
[INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x12345678 | interface=MeshCoreSerialInterface
[DEBUG] 📨 [MESHCORE-TEXT] Reçu: DM:12345678:Hello bot
[DEBUG] 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de NodeName
[DEBUG] 📦 TEXT_MESSAGE_APP de NodeName 45678 [direct] (SNR:n/a)
[INFO] 🔍 About to call _log_comprehensive_packet_debug for source=meshcore type=TEXT_MESSAGE_APP
[INFO] 🔷 _log_comprehensive_packet_debug CALLED | type=TEXT_MESSAGE_APP | from=0x12345678
[DEBUG] ╔═══════════════════════════════════════════════════════════════
[DEBUG] ║ 📦 MESHCORE PACKET DEBUG - TEXT_MESSAGE_APP
[DEBUG] ╠═══════════════════════════════════════════════════════════════
[DEBUG] ║ Packet ID: 865992
[DEBUG] ║ RX Time:   14:23:45
... (full comprehensive debug output)
```
**Status:** ✅ WORKING! MeshCore packets fully visible!

## Filtering Logs

### Show only entry-point diagnostics
```bash
journalctl -u meshbot -f | grep -E "🔵|🔍|🔷|🔔"
```

### Show MeshCore flow
```bash
journalctl -u meshbot -f | grep -E "meshcore|MESHCORE"
```

### Show complete diagnostic flow
```bash
journalctl -u meshbot -f | grep -E "🔔|🔵|📨|🔍|🔷|📊|📦|╔"
```

## What User Should Report

If packets still don't appear, report:

1. **Which diagnostic markers appear?**
   - 🔔 on_message CALLED? YES/NO
   - 🔵 add_packet ENTRY? YES/NO
   - 🔍 About to call? YES/NO
   - 🔷 comprehensive debug CALLED? YES/NO

2. **Share the actual log output**
   ```bash
   journalctl -u meshbot --since "5 minutes ago" | grep -E "meshcore|MESHCORE|🔔|🔵|🔍|🔷"
   ```

3. **Confirm DEBUG_MODE is True**
   ```bash
   grep DEBUG_MODE /path/to/config.py
   ```

4. **Confirm MeshCore is enabled**
   ```bash
   grep MESHCORE_ENABLED /path/to/config.py
   ```

5. **Check if serial port receives data**
   ```bash
   cat /dev/ttyUSB0  # (replace with your MeshCore serial port)
   ```

## Summary

✅ **Rollback complete** - All debug logs use debug_print (DEBUG_MODE required)
✅ **Strategic diagnostics** - Entry points use info_print (ALWAYS visible)
✅ **Flow tracing** - Can identify exact blocking point
✅ **User empowered** - Can self-diagnose where packets are lost

The diagnostics will show EXACTLY where in the flow packets stop appearing, allowing targeted fixes.
