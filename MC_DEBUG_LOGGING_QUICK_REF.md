# MeshCore DEBUG Logging - Quick Reference

## What Was Added

Ultra-visible MC DEBUG logging at 5 critical points in packet flow:

1. **Serial Reception** → meshcore_serial_interface.py
2. **Network Forwarding** → dual_interface_manager.py
3. **Main Entry** → main_bot.py::on_message()
4. **Packet Processing** → traffic_monitor.py::add_packet()
5. **Command Routing** → main_bot.py (TEXT_MESSAGE_APP + command call)

## Log Prefix

All MeshCore logs use: `[INFO][MC]` or `[DEBUG][MC]`

## Quick Diagnostic

### Problem: No MC DEBUG logs at all

**Possible causes:**
- MESHCORE_ENABLED = False
- DUAL_NETWORK_MODE = False
- MeshCore radio not connected
- Serial port not accessible

**Check:**
```bash
grep "MESHCORE_ENABLED\|DUAL_NETWORK_MODE" config.py
ls -l /dev/ttyUSB* /dev/ttyACM*
```

### Problem: Packets received but not processed

**Trace packet flow:**

**Stage 1:** Serial reception
```bash
journalctl -u meshbot -f | grep "CALLING message_callback FROM meshcore_serial_interface"
```
✅ If present → Serial OK, continue to Stage 2  
❌ If absent → Serial connection or MeshCore radio issue

**Stage 2:** Network forwarding
```bash
journalctl -u meshbot -f | grep "MESHCORE PACKET IN on_meshcore_message"
```
✅ If present → Callback OK, continue to Stage 3  
❌ If absent → Callback not registered, check dual_interface_manager setup

**Stage 3:** Main entry
```bash
journalctl -u meshbot -f | grep "MESHCORE PACKET RECEIVED IN on_message"
```
✅ If present → Main callback OK, continue to Stage 4  
❌ If absent → Message callback chain broken

**Stage 4:** Packet processing
```bash
journalctl -u meshbot -f | grep "MESHCORE PACKET IN add_packet"
```
✅ If present → Traffic monitor OK, continue to Stage 5  
❌ If absent → Packet validation or filtering issue

**Stage 5:** Command routing
```bash
journalctl -u meshbot -f | grep "CALLING process_text_message.*FOR MESHCORE"
```
✅ If present → Command routing OK  
❌ If absent → Message type filtering or routing issue

### Problem: Packets processed but no response

**Check command handler:**
```bash
journalctl -u meshbot -f | grep "process_text_message\|message_router"
```

Investigate:
- Message parsing in message_router.py
- Command authorization
- Throttling limits
- Response generation

## Filter Examples

**See all MeshCore logs:**
```bash
journalctl -u meshbot -f | grep "\[MC\]"
```

**See packet flow for specific message:**
```bash
journalctl -u meshbot --since "1 minute ago" | grep -C 5 "MC DEBUG.*0x12345678"
```

**See only stage headers:**
```bash
journalctl -u meshbot -f | grep "MC DEBUG.*====="
```

**Count MeshCore packets received:**
```bash
journalctl -u meshbot --since "1 hour ago" | grep -c "MESHCORE PACKET IN add_packet"
```

## Expected Log Flow

For a MeshCore DM with `/help`:

```
[INFO][MC] 🔗 MC DEBUG: CALLING message_callback FROM meshcore_serial_interface
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] 📨 Message: /help

[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN on_meshcore_message()
[INFO][MC] ➡️  Forwarding to main callback with NetworkSource.MESHCORE

[INFO][MC] 🔗🔗🔗 MC DEBUG: MESHCORE PACKET RECEIVED IN on_message()
[INFO][MC] 🔗 Network source: NetworkSource.MESHCORE

[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN add_packet()
[INFO][MC] 📨 PortNum: TEXT_MESSAGE_APP
[INFO][MC] 💌 Is DM: True

[INFO][MC] 📨 MC DEBUG: TEXT_MESSAGE_APP FROM MESHCORE
[INFO][MC] 💬 Message: /help

[INFO][MC] 🎯 MC DEBUG: CALLING process_text_message() FOR MESHCORE
[INFO][MC] ✅ MC DEBUG: process_text_message() returned
```

## Test Script

Run diagnostic test:
```bash
cd /home/runner/work/meshbot/meshbot
python3 test_mc_debug_logging.py
```

Expected: All tests pass, MC DEBUG logs visible

## Key Files

| File | Function | MC DEBUG Logs |
|------|----------|---------------|
| meshcore_serial_interface.py | Serial reception | Stage 1 |
| dual_interface_manager.py | Network forwarding | Stage 2 |
| main_bot.py | Entry + routing | Stages 3, 5 |
| traffic_monitor.py | Packet processing | Stage 4 |

## Troubleshooting Matrix

| Symptom | Stage | Check |
|---------|-------|-------|
| No logs at all | 0 | Config, serial connection |
| Stage 1 only | 1→2 | Callback registration |
| Stage 1-2 only | 2→3 | Message callback chain |
| Stage 1-3 only | 3→4 | Packet validation |
| Stage 1-4 only | 4→5 | Message type routing |
| All stages but no response | 5+ | Command handler |

## Performance Impact

**Minimal:**
- Uses info_print_mc() which is fast
- Only logs when source='meshcore'
- No performance degradation in Meshtastic mode

## Disabling

To disable MC DEBUG logs (not recommended):
```python
# In utils.py, change:
def info_print_mc(message):
    # info_print(message, source='MC')  # Comment out
    pass
```

Or filter in journalctl:
```bash
journalctl -u meshbot -f | grep -v "\[MC\]"
```
