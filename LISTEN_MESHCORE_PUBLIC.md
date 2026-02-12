# MeshCore Public Channel Listener - Diagnostic Tool

## Overview

`listen_meshcore_public.py` is a standalone diagnostic script that listens to MeshCore Public channel messages and logs all details to stdout. This tool helps understand the encryption and message format used by MeshCore, which is essential for implementing proper command handling.

## Purpose

This script was created to resolve the MeshCore encryption issue where `/echo` commands show as `[ENCRYPTED]` and are not processed by the bot.

**Goals:**
1. Understand MeshCore Public channel message format
2. Identify encryption method and requirements
3. Determine if PSK decryption is needed
4. Debug payload structure
5. Find the correct way to decrypt and process messages

## Requirements

- Python 3.8+
- `meshtastic` Python library
- Meshtastic node on /dev/ttyACM2 at 115200 baud

## Installation

```bash
pip install meshtastic
```

## Usage

### Basic Usage

```bash
cd /home/user/meshbot
python listen_meshcore_public.py
```

### What Happens

1. Script connects to /dev/ttyACM2 at 115200 baud
2. Displays node information
3. Starts listening for messages
4. Logs all received messages with full details

### Send Test Message

While the script is running:
1. Send `/echo test` on MeshCore Public channel
2. Watch the script output for detailed packet information

## Output Format

### Example Output

```
================================================================================
[2026-02-12 20:26:21.123] 📡 PACKET RECEIVED
================================================================================
From: 0x56a09311
To: 0xe151a2d3
Channel: 0

📋 DECODED DATA:
  Portnum: TEXT_MESSAGE_APP
  Payload (bytes): 39 bytes
  Payload (hex): 39 e7 15 00 11 93 a0 56 d3 a2 51 e1 a8 33 51 0d 2b 20 74 97 ac 02 3d 14 b4 7b a2 f0 47 d4 71 93 4c 32 a4 52 84 7a d2
  Payload (raw): b'9\xe7\x15\x00\x11\x93\xa0V\xd3\xa2Q\xe1\xa83Q\r+ t\x97\xac\x02=\x14\xb4{\xa2\xf0G\xd4q\x93L2\xa4R\x84z\xd2'

🔍 RAW PACKET DATA:
  fromId: 0x56a09311
  toId: 0xe151a2d3
  channel: 0
  rxRssi: -25
  rxSnr: 14.25

✅ This is a TEXT_MESSAGE_APP
⚠️  ENCRYPTED: Has payload but no text
   Payload may be encrypted data
```

## What to Look For

### 1. Encryption Status

**Encrypted Message:**
```
⚠️  ENCRYPTED: Has payload but no text
   Payload may be encrypted data
```
- Has `payload` with bytes
- No `text` field
- Cannot see command content

**Decrypted Message:**
```
✅ DECRYPTED: Text content available
   Message: '/echo test'
```
- Has `text` field with readable content
- Command is visible
- Can be processed

### 2. Payload Analysis

Look at the hex dump:
```
Payload (hex): 39 e7 15 00 11 93 a0 56 d3 a2 51 e1 ...
```

**Questions to answer:**
- Does the payload look like encrypted data (random bytes)?
- Are there patterns or structure?
- What is the encryption method?
- Is a PSK needed?

### 3. Channel Information

```
Channel: 0
```

- Channel 0 is typically the primary/public channel
- Check if channel matches your configuration
- Verify channel settings in Meshtastic

## Troubleshooting

### Connection Issues

**Error: Cannot connect to /dev/ttyACM2**

Solutions:
1. Check device exists: `ls -l /dev/ttyACM*`
2. Check permissions: `sudo chmod 666 /dev/ttyACM2`
3. Verify device is correct: Try /dev/ttyACM0 or /dev/ttyACM1
4. Check if another process is using the device

**Error: Permission denied**

```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

### No Messages Received

1. **Verify node is connected**: Check with `meshtastic --info`
2. **Send test message**: Use Meshtastic app or CLI
3. **Check channel**: Verify you're on the correct channel
4. **Check logs**: Look for connection messages in script output

### Module Not Found

```bash
pip install --upgrade meshtastic
```

## Understanding the Output

### Decryption Analysis

After running the script and observing messages:

**If messages are encrypted:**
- Payload contains random-looking bytes
- No text field present
- Need to determine:
  - Encryption method (AES? XSalsa20?)
  - PSK required
  - Nonce/IV handling

**If messages are decrypted:**
- Text field has readable content
- Commands are visible
- Meshtastic library handled decryption
- May indicate correct PSK is configured

## Next Steps

### After Collecting Data

1. **Analyze encryption pattern**
   - Look at hex dumps
   - Identify encryption type
   - Determine PSK requirements

2. **Test with different PSKs**
   - Try default Meshtastic PSK
   - Try custom channel PSK
   - Document which works

3. **Implement decryption**
   - Update bot code with findings
   - Add proper PSK configuration
   - Test /echo command

4. **Verify functionality**
   - Send /echo command
   - Check bot processes it
   - Verify response works

## Integration with Bot

Once you understand the encryption:

### Option 1: MeshCore Decrypts

Configure MeshCore to decrypt before forwarding to bot.

### Option 2: Bot Decrypts

1. Get the correct PSK from Meshtastic configuration
2. Add PSK to bot config
3. Implement decryption in bot
4. Use findings from this script

### Option 3: Library Handles It

If Meshtastic library decrypts automatically:
1. Ensure correct channel configuration
2. Set proper PSK in Meshtastic settings
3. Messages should arrive decrypted

## Related Documentation

- `MESHCORE_ENCRYPTION_ISSUE.md` - Full encryption analysis
- `PHASE18_REVERT.md` - Why Meshtastic methods don't work
- `README.md` - Main bot documentation

## Support

If the script doesn't work or you need help interpreting output:
1. Check the troubleshooting section
2. Review related documentation
3. Share script output for analysis

## Example Session

```bash
$ python listen_meshcore_public.py
================================================================================
🎯 MeshCore Public Channel Listener
================================================================================
Device: /dev/ttyACM2 @ 115200 baud
Started: 2026-02-12 20:45:00.000
Purpose: Listen to Public channel messages and log details

Press Ctrl+C to stop
================================================================================

[2026-02-12 20:45:01.234] 🔌 Connecting to /dev/ttyACM2...
[2026-02-12 20:45:02.567] ✅ Connected successfully
[2026-02-12 20:45:02.890] 📱 Node info:
   User: My Node
   ID: !12345678
   
[2026-02-12 20:45:03.000] 👂 Listening for messages...
[2026-02-12 20:45:03.001] 💡 Send a message on the Public channel to see it logged here

# Now send a message and watch the detailed output!
```

## Conclusion

This diagnostic tool provides the visibility needed to understand MeshCore Public channel encryption and implement proper command handling. Use the output to make informed decisions about encryption architecture and bot integration.
