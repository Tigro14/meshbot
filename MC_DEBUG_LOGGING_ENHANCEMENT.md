# MeshCore DEBUG Logging Enhancement

## Problem

There were absolutely no MC DEBUG log lines appearing in production, making it impossible to debug MeshCore packet traffic. The bot was not responding to direct MeshCore DMs and not logging queries.

## Solution

Added ultra-visible MC DEBUG logging throughout the entire packet flow path, from serial reception to command processing.

## Changes Made

### 1. Entry Point Logging (main_bot.py::on_message)

**Added at packet entry:**
- Ultra-visible banner when MeshCore packet received
- Network source identification (dual mode vs single mode)
- Interface type logging
- DM detection with _meshcore_dm flag

**Example log output:**
```
[INFO][MC] ================================================================================
[INFO][MC] 🔗🔗🔗 MC DEBUG: MESHCORE PACKET RECEIVED IN on_message()
[INFO][MC] ================================================================================
[INFO][MC] 📍 Entry point: main_bot.py::on_message()
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] 🔗 Network source: NetworkSource.MESHCORE
[INFO][MC] 🔌 Interface: MeshCoreSerialInterface
[INFO][MC] ================================================================================
```

### 2. Source Detection Logging (main_bot.py::on_message)

**Added when source is detected as 'meshcore':**
- Confirmation of source detection logic
- Mode identification (dual vs single)

**Example log output:**
```
[INFO][MC] 🔗 MC DEBUG: Source détectée comme MeshCore (dual mode)
[INFO][MC]    → Packet sera traité avec source='meshcore'
```

### 3. Packet Processing Logging (traffic_monitor.py::add_packet)

**Added at add_packet entry:**
- Packet details (from, source, interface)
- PortNum identification
- DM status detection
- _meshcore_dm flag status

**Example log output:**
```
[INFO][MC] ================================================================================
[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN add_packet()
[INFO][MC] ================================================================================
[INFO][MC] 📍 Entry point: traffic_monitor.py::add_packet()
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] 🔗 Source: meshcore
[INFO][MC] 🔌 Interface: MeshCoreSerialInterface
[INFO][MC] 📨 PortNum: TEXT_MESSAGE_APP
[INFO][MC] 💌 Is DM: True
[INFO][MC] 🏷️  _meshcore_dm flag: True
[INFO][MC] ================================================================================
```

**Added at SQLite save:**
```
[INFO][MC] 💾 MC DEBUG: Packet sauvegardé dans table meshcore_packets
[INFO][MC]    → Type: TEXT_MESSAGE_APP
[INFO][MC]    → From: UserNode (0x12345678)
```

### 4. Network Forwarding Logging (dual_interface_manager.py)

**Added in on_meshcore_message:**
- Packet count tracking
- From/to IDs
- PortNum
- Forward confirmation

**Example log output:**
```
[INFO][MC] ================================================================================
[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN on_meshcore_message()
[INFO][MC] ================================================================================
[INFO][MC] 📍 Entry point: dual_interface_manager.py::on_meshcore_message()
[INFO][MC] 📦 Packet count: #42
[INFO][MC] 🔌 Interface: MeshCoreSerialInterface
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] 📬 To: 0x87654321
[INFO][MC] 📨 PortNum: TEXT_MESSAGE_APP
[INFO][MC] ➡️  Forwarding to main callback with NetworkSource.MESHCORE
[INFO][MC] ================================================================================
```

### 5. Serial Reception Logging (meshcore_serial_interface.py)

**Added in _process_meshcore_line:**
- Callback invocation banner
- From ID and message preview
- Callback function reference
- Success confirmation

**Example log output:**
```
[INFO][MC] ================================================================================
[INFO][MC] 🔗 MC DEBUG: CALLING message_callback FROM meshcore_serial_interface
[INFO][MC] ================================================================================
[INFO][MC] 📍 Entry point: meshcore_serial_interface.py::_process_meshcore_line()
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] 📨 Message: /help
[INFO][MC] ➡️  Calling callback: <function DualInterfaceManager.setup_message_callbacks...>
[INFO][MC] ================================================================================
[INFO][MC] ✅ MC DEBUG: Callback returned successfully
```

### 6. Command Processing Logging (main_bot.py)

**Added for TEXT_MESSAGE_APP:**
- Message type confirmation
- Message content preview
- Broadcast vs DM status
- Command processing call

**Example log output:**
```
[INFO][MC] ================================================================================
[INFO][MC] 📨 MC DEBUG: TEXT_MESSAGE_APP FROM MESHCORE
[INFO][MC] ================================================================================
[INFO][MC] 📍 Location: main_bot.py::on_message() - TEXT_MESSAGE_APP processing
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] 📬 To: 0x87654321
[INFO][MC] 💬 Message: /help
[INFO][MC] 📢 Is broadcast: False
[INFO][MC] 💌 Is DM: True
[INFO][MC] 🏷️  _meshcore_dm flag: True
[INFO][MC] ➡️  Will call process_text_message()
[INFO][MC] ================================================================================
```

**Added before command processing:**
```
[INFO][MC] ================================================================================
[INFO][MC] 🎯 MC DEBUG: CALLING process_text_message() FOR MESHCORE
[INFO][MC] ================================================================================
[INFO][MC] 📍 Location: main_bot.py::on_message() - before process_text_message()
[INFO][MC] 💬 Message: /help
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] ➡️  Calling: self.message_handler.process_text_message()
[INFO][MC] ================================================================================
[INFO][MC] ✅ MC DEBUG: process_text_message() returned
```

### 7. DM Detection Logging (main_bot.py)

**Added when _meshcore_dm flag detected:**
```
[INFO][MC] ================================================================================
[INFO][MC] 💌 MC DEBUG: MESHCORE DM DETECTED
[INFO][MC] ================================================================================
[INFO][MC] 📍 Location: main_bot.py::on_message() - DM detection
[INFO][MC] 📦 From: 0x12345678
[INFO][MC] 📬 To: 0x87654321
[INFO][MC] 🏷️  _meshcore_dm flag: True
[INFO][MC] ================================================================================
```

## Testing

Created comprehensive test script `test_mc_debug_logging.py`:

**Test 1: MC Logging Functions**
- Verifies info_print_mc() and debug_print_mc() work
- Checks [INFO][MC] and [DEBUG][MC] prefixes appear

**Test 2: Packet Flow Simulation**
- Simulates packet at each stage
- Verifies MC DEBUG banners appear at all 5 stages
- Confirms packet details are logged

**Test 3: Visibility Check**
- Confirms MC DEBUG logs are highly visible
- Verifies prefixes are correct

**All tests pass ✅**

## Benefits

1. **Complete Visibility**: MC DEBUG logs at every stage of packet flow
2. **Easy Debugging**: Can trace packets from serial reception to command processing
3. **Always Visible**: Uses info_print_mc() so logs appear even without DEBUG_MODE=True
4. **Clear Identification**: [INFO][MC] prefix makes MeshCore logs stand out
5. **Minimal Changes**: Only added logging, no logic changes
6. **Diagnostic Ready**: Can immediately identify where packet flow breaks

## Usage

### When Debugging MeshCore Issues

1. **Check if packets are received:**
   - Look for: `MC DEBUG: CALLING message_callback FROM meshcore_serial_interface`
   - If not present: Serial connection or MeshCore radio issue

2. **Check if packets are forwarded:**
   - Look for: `MC DEBUG: MESHCORE PACKET IN on_meshcore_message()`
   - If not present: Callback not set or dual_interface_manager issue

3. **Check if packets reach main bot:**
   - Look for: `MC DEBUG: MESHCORE PACKET RECEIVED IN on_message()`
   - If not present: Message callback chain broken

4. **Check if packets are processed:**
   - Look for: `MC DEBUG: MESHCORE PACKET IN add_packet()`
   - If not present: Packet filtering or validation issue

5. **Check if commands are routed:**
   - Look for: `MC DEBUG: TEXT_MESSAGE_APP FROM MESHCORE`
   - Look for: `MC DEBUG: CALLING process_text_message() FOR MESHCORE`
   - If not present: Message decoding or routing issue

### Log Filtering

To see only MeshCore logs:
```bash
journalctl -u meshbot -f | grep "\[MC\]"
```

To see complete packet flow for a specific message:
```bash
journalctl -u meshbot --since "1 minute ago" | grep -A 10 "MC DEBUG.*CALLING message_callback"
```

## Files Modified

1. `main_bot.py` - 6 MC DEBUG logging points added
2. `traffic_monitor.py` - 2 MC DEBUG logging points added
3. `dual_interface_manager.py` - 1 MC DEBUG logging point added
4. `meshcore_serial_interface.py` - 1 MC DEBUG logging point added
5. `test_mc_debug_logging.py` - New test file created

## Next Steps

1. Deploy updated code to production
2. Monitor logs for MC DEBUG lines when MeshCore packets arrive
3. Verify DMs are being processed and triggering commands
4. If packets arrive but commands don't execute, use MC DEBUG logs to identify the exact break point
5. Investigate command routing if packets reach process_text_message but don't trigger responses

## Troubleshooting

**If you don't see ANY MC DEBUG logs:**
- Check MESHCORE_ENABLED config setting
- Check DUAL_NETWORK_MODE config setting
- Verify MeshCore serial interface is connected
- Check serial port permissions

**If you see early MC DEBUG logs but not later ones:**
- Use the stage numbers to identify where flow breaks
- Check the last stage that logged successfully
- Investigate the next stage that should have logged

**If you see all MC DEBUG logs but no command response:**
- Check message_handler.py and message_router.py
- Verify command parsing logic
- Check throttling and authorization

## Related Documentation

- `MESHCORE_COMPANION.md` - MeshCore companion mode documentation
- `DUAL_INTERFACE_FAQ.md` - Dual interface architecture
- `utils.py` - Logging function implementations
