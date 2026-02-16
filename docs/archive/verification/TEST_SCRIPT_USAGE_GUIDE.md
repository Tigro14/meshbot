# MeshCore Broadcast Test Script - Usage Guide

## Purpose

This diagnostic script tests various MeshCore text protocol commands to identify the correct format for broadcasting messages on the public channel.

## Background

The echo command processes successfully but messages don't reach the public channel. We need to validate which MeshCore command actually broadcasts.

## Installation

The script is already in the repository:
```bash
cd /home/dietpi/bot
# Script is: test_meshcore_broadcast.py
```

## Usage

### Automated Testing (Recommended)

Run all tests automatically:
```bash
python test_meshcore_broadcast.py /dev/ttyACM1
```

This tests 5 different command formats and shows which ones work.

### Interactive Mode

For manual testing:
```bash
python test_meshcore_broadcast.py /dev/ttyACM1 --interactive
```

Enter commands manually and see immediate responses.

## Expected Output

### Automated Mode Example

```
============================================================
Testing MeshCore broadcast commands on /dev/ttyACM1
============================================================

✅ Serial port opened: /dev/ttyACM1 @ 115200

Test 1: SEND_DM with broadcast address
  Command: 'SEND_DM:ffffffff:TEST1'
  ✅ Sent: 28 bytes
  ⏳ Waiting for response...
  📨 Response: 3e02000102 (5 bytes)
  ❌ ERROR response from device

Test 2: BROADCAST command
  Command: 'BROADCAST:TEST2'
  ✅ Sent: 16 bytes
  ⏳ Waiting for response...
  📨 Response: 3e02000100 (5 bytes)
  ✅ SUCCESS response from device

Test 3: SEND_BROADCAST command
  Command: 'SEND_BROADCAST:TEST3'
  ✅ Sent: 23 bytes
  ⏳ Waiting for response...
  ℹ️  No response from device

Test 4: SEND_PUBLIC command
  Command: 'SEND_PUBLIC:TEST4'
  ✅ Sent: 19 bytes
  ⏳ Waiting for response...
  📨 Response: 3e02000102 (5 bytes)
  ❌ ERROR response from device

Test 5: SEND_CHANNEL with channel 0
  Command: 'SEND_CHANNEL:0:TEST5'
  ✅ Sent: 22 bytes
  ⏳ Waiting for response...
  ℹ️  No response from device

============================================================
Testing complete!
============================================================
```

## Interpreting Results

### Response Types

**✅ SUCCESS (0x3e02000100):**
- Device accepted command
- Message should broadcast
- This is the correct command!

**❌ ERROR (0x3e02000102):**
- Device rejected command
- Message NOT sent
- Wrong command format

**ℹ️ No Response:**
- Device didn't understand
- Command ignored
- Not the right format

### What Each Test Means

| Test | Command | If SUCCESS |
|------|---------|------------|
| 1 | SEND_DM:ffffffff:msg | Broadcast via DM address works |
| 2 | BROADCAST:msg | Simple BROADCAST command works |
| 3 | SEND_BROADCAST:msg | Explicit broadcast command works |
| 4 | SEND_PUBLIC:msg | Public channel command works |
| 5 | SEND_CHANNEL:0:msg | Channel-specific command works |

## What to Share

After running the test, share:

1. **Complete output** from the script
2. **Which test(s) showed SUCCESS** (✅)
3. **Which test(s) showed ERROR** (❌)
4. **Which test(s) had no response** (ℹ️)

Example:
```
Test results:
- Test 1: ERROR ❌
- Test 2: SUCCESS ✅ ← THIS ONE WORKS!
- Test 3: No response
- Test 4: ERROR ❌
- Test 5: No response
```

## Next Steps Based on Results

### If Test 1 (SEND_DM:ffffffff) Shows SUCCESS
✅ Current code is correct, issue is elsewhere
- Check device logs
- Verify other mesh nodes receive
- May be network issue, not code issue

### If Test 2 (BROADCAST) Shows SUCCESS
📝 Update code to use `BROADCAST:message`
```python
# In meshcore_serial_interface.py, change:
cmd = f"BROADCAST:{message}\n"
```

### If Test 3 (SEND_BROADCAST) Shows SUCCESS
📝 Update code to use `SEND_BROADCAST:message`
```python
cmd = f"SEND_BROADCAST:{message}\n"
```

### If Test 4 (SEND_PUBLIC) Shows SUCCESS
📝 Update code to use `SEND_PUBLIC:message`
```python
cmd = f"SEND_PUBLIC:{message}\n"
```

### If Test 5 (SEND_CHANNEL:0) Shows SUCCESS
📝 Update code to use `SEND_CHANNEL:0:message`
```python
cmd = f"SEND_CHANNEL:{channelIndex}:{message}\n"
```

### If ALL Tests Fail
🔍 Need to investigate:
- MeshCore firmware version
- Device mode/configuration
- Alternative text protocol commands
- Binary protocol as alternative

## Troubleshooting

### Permission Denied
```bash
sudo python test_meshcore_broadcast.py /dev/ttyACM1
```

### Port Not Found
Check available ports:
```bash
ls -la /dev/ttyACM*
```

### Script Not Executable
```bash
chmod +x test_meshcore_broadcast.py
```

## Interactive Mode Examples

```bash
python test_meshcore_broadcast.py /dev/ttyACM1 --interactive

Command> BROADCAST:Hello World
  ✅ Sent: 20 bytes
  📨 Response: 3e02000100 (5 bytes)

Command> SEND_DM:ffffffff:Test Message
  ✅ Sent: 32 bytes
  📨 Response: 3e02000102 (5 bytes)

Command> quit
✅ Serial port closed
```

## Summary

This test script:
- ✅ Tests all possible broadcast command formats
- ✅ Shows which commands device accepts
- ✅ Provides data for permanent fix
- ✅ Simple to run and share results

**Run it and share the output!** This will solve the echo broadcast issue permanently.
