# Phase 10: Map All Encrypted Types to TEXT_MESSAGE_APP

## Problem

After Phase 9, encrypted public channel messages still showing as UNKNOWN_APP:

```
From: 0x3431d211 → To: 0x7afed221
Type: Unknown(12)
Determined portnum from type 15: UNKNOWN_APP (broadcast=False)
```

Bot receives encrypted packets but doesn't process `/echo` commands.

## Root Cause Discovery

### The Channel Hash Issue

**Phase 9 assumption**: Broadcasts use receiver_id = 0xFFFFFFFF

**Reality**: Public channels use **channel hash** as receiver_id!

**Meshtastic addressing:**
- **True broadcast**: receiver_id = 0xFFFFFFFF (all nodes, rare)
- **Public channel**: receiver_id = **channel hash** (e.g., 0x7afed221) ← User's case!
- **Direct message**: receiver_id = specific node ID

**Phase 9 code:**
```python
is_broadcast = (receiver_id == 0xFFFFFFFF)
if type in [13, 15] and is_broadcast:
    portnum = 'TEXT_MESSAGE_APP'
```

**Result**: `broadcast=False` → `UNKNOWN_APP` ❌

### Why Channel Hashes?

Public channels in Meshtastic:
1. Have encryption enabled (PSK)
2. Use a **hash of channel settings** as receiver_id
3. This allows nodes to filter packets efficiently
4. Hash value is deterministic from channel config

Example channel hashes from logs:
- 0x7afed221
- 0xfed22134

These are NOT node IDs, they're channel identifiers!

## Solution

### The Insight

We cannot reliably detect "broadcast" from receiver_id alone because:
- Channel hash looks like regular address
- No way to distinguish from node ID
- Would need to know all channel hashes

**Better approach**: Trust the encryption!

### Implementation

**Map ALL encrypted types to TEXT_MESSAGE_APP:**

```python
# Phase 10: Remove broadcast check
elif payload_type_value in [12, 13, 15]:
    # Types 12, 13, 15 are encrypted message wrappers
    # Map to TEXT_MESSAGE_APP and let bot's decryption handle it
    portnum = 'TEXT_MESSAGE_APP'
    debug_print_mc(f"🔐 [RX_LOG] Encrypted packet (type {payload_type_value}) → TEXT_MESSAGE_APP")
```

**Why this works:**
1. Types 12/13/15 = encrypted wrappers
2. Bot has PSK for channels it's subscribed to
3. Bot will **successfully decrypt** channel messages ✅
4. Bot will **fail to decrypt** DMs (uses PKI, not PSK)
5. Bot safely ignores what it can't decrypt ℹ️

### Changes Made

**File**: `meshcore_cli_wrapper.py` (lines 1856-1873)

**Before (Phase 9):**
```python
# Check if broadcast
is_broadcast = (receiver_id == 0xFFFFFFFF or receiver_id == 0xffffffff)

if payload_type_value == 1:
    portnum = 'TEXT_MESSAGE_APP'
# ... other types ...
elif payload_type_value in [13, 15] and is_broadcast:  # ❌ Requires broadcast
    portnum = 'TEXT_MESSAGE_APP'
else:
    portnum = 'UNKNOWN_APP'
debug_print_mc(f"📋 [RX_LOG] Determined portnum: {portnum} (broadcast={is_broadcast})")
```

**After (Phase 10):**
```python
# No broadcast check needed!
if payload_type_value == 1:
    portnum = 'TEXT_MESSAGE_APP'
# ... other types ...
elif payload_type_value in [12, 13, 15]:  # ✅ All encrypted types
    portnum = 'TEXT_MESSAGE_APP'
    debug_print_mc(f"🔐 [RX_LOG] Encrypted packet (type {payload_type_value}) → TEXT_MESSAGE_APP")
else:
    portnum = 'UNKNOWN_APP'
debug_print_mc(f"📋 [RX_LOG] Determined portnum from type {payload_type_value}: {portnum}")
```

**Key differences:**
1. ✅ Removed `is_broadcast` check
2. ✅ Added type 12 (was missing!)
3. ✅ Simpler logic
4. ✅ More robust

## Benefits

1. **Handles channel hashes**: Works with any channel hash value
2. **Includes type 12**: Was missing in Phase 9
3. **Simpler code**: No broadcast detection needed
4. **Secure**: Bot only decrypts with correct PSK
5. **Fail-safe**: Ignores undecryptable messages

## Expected Behavior

### Before (Phase 9)

```
[DEBUG][MC] Type: Unknown(12)
[DEBUG][MC] 🔍 [RX_LOG] Payload value: {'raw': '', 'decoded': None}
[DEBUG][MC] 🔧 [RX_LOG] Decoded raw empty, using original raw_hex: 39B
[DEBUG][MC] ✅ [RX_LOG] Converted hex to bytes: 39B
[DEBUG][MC] 📋 [RX_LOG] Determined portnum from type 15: UNKNOWN_APP (broadcast=False)
[DEBUG][MC] ➡️  [RX_LOG] Forwarding UNKNOWN_APP packet
[Result: Bot ignores packet] ❌
```

### After (Phase 10)

```
[DEBUG][MC] Type: Unknown(12)
[DEBUG][MC] 🔍 [RX_LOG] Payload value: {'raw': '', 'decoded': None}
[DEBUG][MC] 🔧 [RX_LOG] Decoded raw empty, using original raw_hex: 39B
[DEBUG][MC] ✅ [RX_LOG] Converted hex to bytes: 39B
[DEBUG][MC] 🔐 [RX_LOG] Encrypted packet (type 12) → TEXT_MESSAGE_APP
[DEBUG][MC] 📋 [RX_LOG] Determined portnum from type 15: TEXT_MESSAGE_APP
[DEBUG][MC] ➡️  [RX_LOG] Forwarding TEXT_MESSAGE_APP packet
[Result: Bot decrypts with channel PSK]
[Result: Bot extracts /echo command]
[Result: Bot processes and responds] ✅
```

## Testing

### Deploy and Monitor

```bash
cd /home/user/meshbot
git pull origin copilot/add-echo-command-listener
sudo systemctl restart meshbot
journalctl -u meshbot -f | grep -E "(RX_LOG|🔐)"
```

### Send Test Command

Send `/echo test` on MeshCore public channel

### Expected Logs

```
🔐 [RX_LOG] Encrypted packet (type 12) → TEXT_MESSAGE_APP
📋 [RX_LOG] Determined portnum from type 12: TEXT_MESSAGE_APP
➡️  [RX_LOG] Forwarding TEXT_MESSAGE_APP packet
```

### Verification

Bot should:
1. ✅ Receive encrypted packet
2. ✅ Map to TEXT_MESSAGE_APP
3. ✅ Decrypt with channel PSK
4. ✅ Extract `/echo test` command
5. ✅ Process command
6. ✅ Respond on public channel

## Technical Details

### Meshtastic Packet Types

| Type | Name | Description |
|------|------|-------------|
| 1 | TEXT_MESSAGE_APP | Plain text message |
| 3 | POSITION_APP | GPS position |
| 4 | NODEINFO_APP | Node information |
| 7 | TELEMETRY_APP | Telemetry data |
| **12** | **ENCRYPTED** | **Encrypted wrapper** |
| **13** | **ENCRYPTED** | **Encrypted wrapper** |
| **15** | **ENCRYPTED** | **Encrypted wrapper** |

### Encryption Types

**Channel encryption (PSK):**
- Used for public channels
- All nodes share same key
- Bot has PSK → can decrypt ✅

**DM encryption (PKI):**
- Used for direct messages
- Asymmetric encryption
- Bot lacks private key → cannot decrypt ℹ️

### Why This Approach Works

1. **Channel messages**: Bot has PSK → decrypts successfully
2. **DM messages**: Bot lacks PKI → decryption fails → ignores
3. **No false positives**: Only processes what it can decrypt
4. **Simple logic**: No complex address detection

## Status

✅ Phase 10 complete
✅ All documentation updated
✅ Ready for user testing

Bot should now process `/echo` commands on encrypted MeshCore public channels!
