# How to Send Messages on Public Default Channel

## Overview
The MeshBot supports sending messages on the **public default channel (channel 0)** via MeshCore. This guide explains how to do it and which interfaces support it.

## Quick Answer

To send a message on the public default channel:

```python
interface.sendText(
    "Your message here",
    destinationId=0xFFFFFFFF,  # Broadcast address
    channelIndex=0             # Public channel (default)
)
```

## Interface Support Matrix

| Interface | Broadcast Support | Channel Support | Notes |
|-----------|------------------|-----------------|-------|
| **MeshCoreSerialInterface** | ✅ Yes | ✅ Yes | Full binary protocol support |
| **MeshCoreCLIWrapper** | ❌ No | ❌ No | Only supports DM messages |
| **Meshtastic** | ✅ Yes | ✅ Yes | Standard Meshtastic behavior |

## Which Interface Am I Using?

The bot automatically selects the interface based on library availability:

```python
try:
    from meshcore import MeshCore
    # Uses MeshCoreCLIWrapper (NO broadcast support)
except ImportError:
    # Uses MeshCoreSerialInterface (HAS broadcast support)
```

Check your logs at startup:
- **MeshCoreCLIWrapper**: `✅ MESHCORE: Using meshcore-cli library (FULL SUPPORT)`
- **MeshCoreSerialInterface**: `⚠️ MESHCORE: Using BASIC implementation (LIMITED)`

**Important**: Despite the names, the "BASIC implementation" (`MeshCoreSerialInterface`) actually has BETTER broadcast support than the "FULL SUPPORT" version (`MeshCoreCLIWrapper`)!

## Solution 1: Use MeshCoreSerialInterface (Recommended)

### Current Status
If you DON'T have `meshcore-cli` library installed, you're already using `MeshCoreSerialInterface`, which supports broadcasts!

### How It Works

The `MeshCoreSerialInterface.sendText()` method:

```python
def sendText(self, message, destinationId=None, channelIndex=0):
    # Detect broadcast
    is_broadcast = (destinationId is None or destinationId == 0xFFFFFFFF)
    
    if is_broadcast:
        # Build binary packet using CMD_SEND_CHANNEL_TXT_MSG
        message_bytes = message.encode('utf-8')
        payload = bytes([CMD_SEND_CHANNEL_TXT_MSG, channelIndex]) + message_bytes
        length = len(payload)
        packet = bytes([0x3C]) + struct.pack('<H', length) + payload
        self.serial.write(packet)
    else:
        # Send as DM
        cmd = f"SEND_DM:{destinationId:08x}:{message}\n"
        self.serial.write(cmd.encode('utf-8'))
```

### Binary Packet Format

For channel broadcasts, the packet follows the MeshCore Companion Radio Protocol:

```
Byte 0:     0x3C ('<')                - Start marker (app -> radio)
Bytes 1-2:  Length (little-endian)    - Payload length
Byte 3:     0x03                      - CMD_SEND_CHANNEL_TXT_MSG
Byte 4:     Channel index (0 = public)
Bytes 5+:   UTF-8 encoded message
```

Example for "Hello mesh!" on public channel:
```
3c 0d 00 03 00 48 65 6c 6c 6f 20 6d 65 73 68 21
```

### Usage Examples

#### Example 1: Send to Public Channel (Broadcast)
```python
from meshcore_serial_interface import MeshCoreSerialInterface

interface = MeshCoreSerialInterface(port='/dev/ttyUSB0', baudrate=115200)
interface.connect()

# Send broadcast on public channel
interface.sendText(
    "Hello everyone on the mesh!",
    destinationId=0xFFFFFFFF,  # Broadcast
    channelIndex=0             # Public channel
)
```

#### Example 2: Send Direct Message
```python
# Send DM to specific node
interface.sendText(
    "Private message",
    destinationId=0x12345678,  # Specific node ID
    channelIndex=0             # Ignored for DMs
)
```

#### Example 3: Using Dual Interface Manager
```python
from dual_interface_manager import DualInterfaceManager, NetworkSource

dual_mgr = DualInterfaceManager()
dual_mgr.set_meshcore_interface(interface)

# Send via MeshCore to public channel
dual_mgr.send_message(
    text="Broadcast message",
    destination_id=0xFFFFFFFF,   # Broadcast
    network_source=NetworkSource.MESHCORE,
    channelIndex=0               # Public channel
)
```

## Solution 2: Uninstall MeshCore CLI Library (If Needed)

If you have `meshcore-cli` installed but want broadcast support:

```bash
# Uninstall meshcore-cli to use MeshCoreSerialInterface
pip uninstall meshcore meshcoredecoder

# Restart the bot
sudo systemctl restart meshtastic-bot
```

The bot will automatically fall back to `MeshCoreSerialInterface`.

## Solution 3: Add Broadcast Support to MeshCoreCLIWrapper

If you need both meshcore-cli features AND broadcast support, you would need to enhance `MeshCoreCLIWrapper`. However, this is complex because:

1. The `meshcore-cli` library's `send_msg()` API only supports direct messages
2. Channel broadcasts would need to be implemented via a different method
3. This requires understanding the MeshCore library's internal APIs

**Not recommended** - Use `MeshCoreSerialInterface` instead.

## Configuration

In `config.py`:

```python
# Enable MeshCore companion mode
MESHCORE_ENABLED = True

# Serial port for MeshCore device
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
MESHCORE_BAUDRATE = 115200

# For dual mode (both Meshtastic and MeshCore)
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
```

## Testing

### Test 1: Direct Interface Test
```python
# Test broadcast support
from meshcore_serial_interface import MeshCoreSerialInterface

interface = MeshCoreSerialInterface('/dev/ttyUSB0', 115200)
interface.connect()

result = interface.sendText(
    "Test broadcast", 
    destinationId=0xFFFFFFFF,
    channelIndex=0
)
print(f"Broadcast sent: {result}")
```

### Test 2: Via Echo Command
If the bot is running with MeshCoreSerialInterface:
```
Send from another node: /echo test message
```

You should see in logs:
```
📢 [MESHCORE] Envoi broadcast sur canal 0: test message
✅ [MESHCORE-CHANNEL] Broadcast envoyé sur canal 0 (12 octets)
```

## Troubleshooting

### Problem: "Broadcast messages not supported via meshcore-cli"

**Cause**: You're using `MeshCoreCLIWrapper` which doesn't support broadcasts.

**Solution**: Uninstall `meshcore-cli` library:
```bash
pip uninstall meshcore meshcoredecoder
sudo systemctl restart meshtastic-bot
```

### Problem: No messages appearing on mesh

**Causes**:
1. Wrong serial port
2. MeshCore device not connected
3. Wrong channel configuration

**Debug**:
```bash
# Check serial port
ls -la /dev/ttyUSB* /dev/ttyACM*

# Monitor MeshCore serial
python3 meshcore-serial-monitor.py /dev/ttyUSB0

# Check bot logs
journalctl -u meshtastic-bot -f
```

### Problem: Binary packet format errors

**Cause**: Incorrect implementation or protocol mismatch.

**Solution**: Verify packet format matches MeshCore Companion Radio Protocol specification.

## Related Documentation

- `FIX_ECHO_MESHCORE_CHANNEL.md` - Implementation details for echo command
- `FIX_MESHCORE_BROADCAST_REJECTION.md` - Why MeshCoreCLIWrapper doesn't support broadcasts
- `meshcore_serial_interface.py` - Full implementation
- `tests/test_echo_meshcore_channel.py` - Test suite

## Summary

**To send messages on the public default channel with MeshCore:**

1. ✅ **Use `MeshCoreSerialInterface`** (basic implementation) - it has full broadcast support
2. ❌ **Don't use `MeshCoreCLIWrapper`** - it only supports DM messages
3. 🔧 **Call**: `interface.sendText(text, destinationId=0xFFFFFFFF, channelIndex=0)`
4. 📡 **Protocol**: Binary packet with `CMD_SEND_CHANNEL_TXT_MSG` (0x03)

The functionality **already exists** in the codebase and works correctly when using the right interface!
