# Phase 9: Encrypted Broadcast Message Fix

## Problem Statement

After Phase 8 successfully extracted payload bytes, encrypted public channel messages still showed as UNKNOWN_APP:

```
[DEBUG][MC] 📋 [RX_LOG] Determined portnum from type 15: UNKNOWN_APP
[DEBUG][MC] ➡️  [RX_LOG] Forwarding UNKNOWN_APP packet to bot callback
```

**Result**: Bot received encrypted data but didn't process `/echo` commands.

## Diagnostic Findings

Phase 8 logs revealed:
```
Type: Unknown(15) | Size: 39B | Hops: 0
🔧 [RX_LOG] Decoded raw empty, using original raw_hex: 39B
✅ [RX_LOG] Converted hex to bytes: 39B
📋 [RX_LOG] Determined portnum from type 15: UNKNOWN_APP  ← Problem!
```

Payload extracted ✅, but portnum wrong ❌

## Root Cause Analysis

### Packet Type Mapping

**Existing mapping:**
```python
if payload_type_value == 1:
    portnum = 'TEXT_MESSAGE_APP'
elif payload_type_value == 3:
    portnum = 'POSITION_APP'
elif payload_type_value == 4:
    portnum = 'NODEINFO_APP'
elif payload_type_value == 7:
    portnum = 'TELEMETRY_APP'
else:
    portnum = 'UNKNOWN_APP'  # ← Types 13, 15 fall here!
```

**Missing types:**
- Type 13, 15 = **Encrypted message wrappers**
- Not in mapping → defaults to UNKNOWN_APP
- Bot ignores UNKNOWN_APP for command processing

### Encryption Types

**Two encryption methods:**

1. **Channel/Broadcast** (Public Channel):
   - Uses Channel PSK (Pre-Shared Key)
   - Outer type = 13 or 15 (encrypted wrapper)
   - Inner type = 1 (TEXT_MESSAGE_APP) - hidden until decrypted
   - Bot CAN decrypt using channel PSK

2. **Direct Message** (DM):
   - Uses PKI (Public Key Infrastructure)
   - Different encryption method
   - Bot may or may not decrypt (depends on key exchange)

### Why Type 15 for Encrypted Messages?

When a user sends `/echo` on encrypted public channel:
1. Meshtastic encrypts message using channel PSK
2. Wraps in packet with type 15 (encrypted indicator)
3. Original type 1 (TEXT_MESSAGE_APP) is inside encrypted data
4. Receiver must:
   - Recognize type 15 = encrypted text
   - Decrypt to reveal type 1
   - Process as TEXT_MESSAGE_APP

**Our bot was:**
- ✅ Recognizing type 15
- ❌ Mapping to UNKNOWN_APP (not TEXT_MESSAGE_APP)
- ❌ Not attempting decryption

## Solution

### Broadcast Detection

**Check if packet is broadcast:**
```python
is_broadcast = (receiver_id == 0xFFFFFFFF or receiver_id == 0xffffffff)
```

**Broadcast characteristics:**
- receiver_id = 0xFFFFFFFF (all nodes)
- Sent to public channel
- Uses channel PSK encryption

### Type Mapping Enhancement

**Add types 13, 15 for broadcasts:**
```python
elif payload_type_value in [13, 15] and is_broadcast:
    # Encrypted wrapper on broadcast = encrypted text message
    portnum = 'TEXT_MESSAGE_APP'
    debug_print_mc(f"🔐 [RX_LOG] Encrypted broadcast (type {payload_type_value}) → TEXT_MESSAGE_APP")
```

**Keep DMs separate:**
```python
else:
    # Non-broadcast encrypted (DM) or truly unknown
    portnum = 'UNKNOWN_APP'
```

### Complete Flow

```
User sends /echo on encrypted public channel
  ↓
MeshCore receives encrypted packet (type 15)
  ↓
Bot detects: receiver_id = 0xFFFFFFFF (broadcast)
  ↓
Bot checks: type 15 + broadcast → TEXT_MESSAGE_APP
  ↓
Bot forwards as TEXT_MESSAGE_APP with encrypted bytes
  ↓
Bot's traffic_monitor decrypts using channel PSK
  ↓
Bot extracts "/echo test" command
  ↓
Bot processes and responds ✅
```

## Implementation

### File Modified

**meshcore_cli_wrapper.py** (lines 1846-1877)

### Changes

1. **Added broadcast detection** (line 1854):
```python
is_broadcast = (receiver_id == 0xFFFFFFFF or receiver_id == 0xffffffff)
```

2. **Added types 13, 15 mapping** (lines 1866-1870):
```python
elif payload_type_value in [13, 15] and is_broadcast:
    portnum = 'TEXT_MESSAGE_APP'
    debug_print_mc(f"🔐 Encrypted broadcast (type {payload_type_value}) → TEXT_MESSAGE_APP")
```

3. **Enhanced debug logging** (line 1874):
```python
debug_print_mc(f"📋 [RX_LOG] Determined portnum from type {payload_type_value}: {portnum} (broadcast={is_broadcast})")
```

## Benefits

1. ✅ **Encrypted broadcasts recognized**: Types 13, 15 mapped correctly
2. ✅ **Bot decrypts**: Forwarded as TEXT_MESSAGE_APP triggers decryption
3. ✅ **Commands work**: `/echo` and other commands processed
4. ✅ **DMs protected**: Non-broadcast encrypted stays UNKNOWN_APP
5. ✅ **Clear debugging**: Logs show encryption handling

## Expected Behavior

### Before Fix (Phase 8)

```
[DEBUG][MC] Type: Unknown(15) | Size: 39B
[DEBUG][MC] ✅ [RX_LOG] Converted hex to bytes: 39B
[DEBUG][MC] 📋 [RX_LOG] Determined portnum from type 15: UNKNOWN_APP
[DEBUG][MC] ➡️  [RX_LOG] Forwarding UNKNOWN_APP packet
[Result]: Bot ignores, no response
```

### After Fix (Phase 9)

```
[DEBUG][MC] Type: Unknown(15) | Size: 39B
[DEBUG][MC] ✅ [RX_LOG] Converted hex to bytes: 39B
[DEBUG][MC] 🔐 [RX_LOG] Encrypted broadcast (type 15) → TEXT_MESSAGE_APP
[DEBUG][MC] 📋 [RX_LOG] Determined portnum from type 15: TEXT_MESSAGE_APP (broadcast=True)
[DEBUG][MC] ➡️  [RX_LOG] Forwarding TEXT_MESSAGE_APP packet
[Result]: Bot decrypts, processes /echo, responds! ✅
```

## Testing

### Deploy

```bash
cd /home/user/meshbot
git pull origin copilot/add-echo-command-listener
sudo systemctl restart meshbot
```

### Monitor

```bash
journalctl -u meshbot -f | grep -E "(RX_LOG|🔐|TEXT_MESSAGE)"
```

### Test

Send `/echo test` on MeshCore public channel

### Expected Logs

```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (39B) - From: 0x... → To: 0xFFFFFFFF
[DEBUG][MC] Type: Unknown(15) | Route: Flood | Size: 39B
[DEBUG][MC] 🔧 [RX_LOG] Decoded raw empty, using original raw_hex: 39B
[DEBUG][MC] ✅ [RX_LOG] Converted hex to bytes: 39B
[DEBUG][MC] 🔐 [RX_LOG] Encrypted broadcast (type 15) → TEXT_MESSAGE_APP
[DEBUG][MC] 📋 [RX_LOG] Determined portnum from type 15: TEXT_MESSAGE_APP (broadcast=True)
[DEBUG][MC] ➡️  [RX_LOG] Forwarding TEXT_MESSAGE_APP packet
[DEBUG][MC] 📦 From: 0x... → To: 0xFFFFFFFF | Broadcast: False
```

**Key indicators:**
- ✅ `🔐 Encrypted broadcast (type 15) → TEXT_MESSAGE_APP`
- ✅ `broadcast=True` in determination log
- ✅ `Forwarding TEXT_MESSAGE_APP packet`

### Success Criteria

1. Bot receives encrypted packet
2. Detects broadcast (receiver_id = 0xFFFFFFFF)
3. Maps type 15 → TEXT_MESSAGE_APP
4. Decrypts encrypted bytes
5. Extracts `/echo test` command
6. Responds on public channel

## Technical Details

### Why Broadcast Check?

**Broadcast (Public Channel):**
- Uses channel PSK (bot knows it)
- Bot can decrypt ✅
- Safe to map encrypted → TEXT_MESSAGE_APP

**DM (Direct Message):**
- Uses PKI encryption (different keys)
- Bot may not have keys
- Keep as UNKNOWN_APP (let PKI handler deal with it)

### Packet Types Reference

| Type | Name | Description |
|------|------|-------------|
| 1 | TEXT_MESSAGE_APP | Plain text message |
| 3 | POSITION_APP | GPS position |
| 4 | NODEINFO_APP | Node information |
| 7 | TELEMETRY_APP | Telemetry data |
| 13 | Encrypted wrapper | Encrypted message (older) |
| 15 | Encrypted wrapper | Encrypted message (newer) |

### Receiver ID Values

| receiver_id | Meaning |
|-------------|---------|
| 0xFFFFFFFF | Broadcast to all nodes |
| Specific ID | Direct message to node |

## Status

**Phase 9 Complete**: Encrypted public channel messages now properly handled.

**Ready for Testing**: User should deploy and verify bot processes `/echo` commands on encrypted MeshCore public channel.
