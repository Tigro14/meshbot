# MeshCore Encryption Architecture Issue

## Problem Statement

**User's `/echo` command on MeshCore Public channel is not decoded nor responded to.**

The bot receives MeshCore packets, detects they are encrypted, but cannot decrypt them to process commands.

## Current Behavior

```
📦 TEXT_MESSAGE_APP from Node-56a09311 (39B)
└─ Msg:"[ENCRYPTED]" | Payload:39B
```

Commands like `/echo hello` show as `[ENCRYPTED]` and are never processed.

## Root Cause Analysis

### The Architecture Conflict

**MeshCore Wrapper** (meshcore_cli_wrapper.py lines 1862-1864):
```python
# Map to TEXT_MESSAGE_APP and let bot's decryption handle it
# Bot has PSK for channels → will decrypt channel messages
# Bot lacks PKI for DMs → will ignore what it can't decrypt
```

**The wrapper expects the bot to decrypt channel messages.**

**Bot Behavior** (traffic_monitor.py lines 727-748):
```python
if source == 'meshcore':
    # Skip ALL Meshtastic decryption
    message_text = "[ENCRYPTED]"
```

**The bot skips all decryption for MeshCore packets** (per user request).

### The Conflict

1. MeshCore forwards **encrypted bytes** (39-40B payload)
2. MeshCore **expects bot to decrypt** (per code comments)
3. Bot **skips decryption** for MeshCore (per user request)
4. Result: Messages stay `[ENCRYPTED]`, commands never processed

## Why Meshtastic PSK Doesn't Work

When we tried using Meshtastic PSK decryption (Phase 18):
```
❌ [Meshtastic 2.7.15+] Failed: Error parsing message with type 'meshtastic.protobuf.Data'
❌ [Meshtastic 2.6.x] Failed: Error parsing...
❌ [Big-endian] Failed: Error parsing...
❌ [Reversed] Failed: Error parsing...
```

**All 4 Meshtastic methods failed** because:
- MeshCore uses **different encryption** than Meshtastic, OR
- MeshCore uses **different PSK** than default Meshtastic PSK, OR
- MeshCore uses **different nonce calculation** than Meshtastic

## Possible Solutions

### Option 1: MeshCore Decrypts Internally (RECOMMENDED)

**Have MeshCore library decrypt BEFORE forwarding to bot.**

**Advantages:**
- ✅ Clean separation of concerns
- ✅ Bot receives plain text
- ✅ No encryption mixing
- ✅ Simple architecture

**Implementation:**
1. Configure MeshCore with its channel PSK
2. Modify meshcore_cli_wrapper.py to decrypt before creating packet
3. Forward decrypted text in packet dict
4. Bot processes plain text commands

**Disadvantage:**
- Requires access to MeshCore library decryption capabilities
- May need MeshCore library modifications

### Option 2: Bot Uses MeshCore PSK (POSSIBLE)

**Provide bot with MeshCore's actual channel PSK.**

**Advantages:**
- ✅ No MeshCore library changes needed
- ✅ Bot can decrypt MeshCore channels

**Implementation:**
1. Get MeshCore's channel PSK (not default Meshtastic PSK)
2. Add MESHCORE_CHANNEL_PSK to config.py
3. Modify traffic_monitor.py to use correct PSK for MeshCore
4. Decrypt with MeshCore's method (may differ from Meshtastic)

**Disadvantages:**
- ❌ Mixed encryption systems in bot
- ❌ Need to know MeshCore's encryption method
- ❌ Maintenance complexity

### Option 3: Accept [ENCRYPTED] Status (CURRENT)

**Leave messages encrypted, don't process commands.**

**Advantages:**
- ✅ Simple, no changes needed
- ✅ Statistics still work

**Disadvantages:**
- ❌ No command processing on MeshCore
- ❌ `/echo` and other commands don't work
- ❌ Limited functionality

## Technical Details

### MeshCore Encryption Types

Based on code analysis:

1. **Public Channels**: Use PSK encryption (exact method unknown)
2. **DMs**: Use PyNaCl (Curve25519 + XSalsa20-Poly1305)

### Packet Flow

```
User sends /echo hello on MeshCore Public channel
  ↓
MeshCore receives encrypted RF packet (39B)
  ↓
MeshCore wrapper maps type 15 → TEXT_MESSAGE_APP
  ↓
MeshCore forwards encrypted bytes to bot
  ↓
Bot receives: {'portnum': 'TEXT_MESSAGE_APP', 'payload': b'\x39\xe7...'}
  ↓
Bot detects is_encrypted: True
  ↓
Bot detects source=meshcore
  ↓
Bot skips decryption (user request)
  ↓
Message shows as [ENCRYPTED]
  ↓
Bot never processes /echo command ❌
```

### What We Need to Know

To implement Option 1 or 2, we need:

1. **Can MeshCore decrypt internally?**
   - Does MeshCore library have decryption methods?
   - Can we configure channel PSK in MeshCore?

2. **What is MeshCore's encryption method?**
   - Same as Meshtastic (AES-CTR)?
   - Different algorithm?
   - Different nonce calculation?

3. **What is MeshCore's channel PSK?**
   - Default PSK?
   - Custom PSK?
   - How to obtain it?

## Recommendation

**Preferred architecture: Option 1 (MeshCore decrypts internally)**

This is the cleanest design:
- MeshCore handles its own encryption/decryption
- Bot only processes plain text
- No encryption mixing
- Clear responsibilities

**Alternative: Option 2 (Bot with correct PSK)**

If MeshCore cannot decrypt internally:
- Provide MeshCore's channel PSK to bot
- Implement MeshCore-specific decryption
- Accept the complexity

**Current state: Option 3 (Accept [ENCRYPTED])**

Without the above information:
- Messages remain encrypted
- Commands don't work
- Limited functionality

## User Action Required

Please provide:
1. MeshCore library decryption capabilities, OR
2. MeshCore's channel PSK and encryption method, OR
3. Accept that commands won't work on MeshCore

Cannot proceed with `/echo` functionality until this is resolved.

## Status

- **Current**: `/echo` commands show as `[ENCRYPTED]`, not processed
- **Blocker**: Encryption architecture decision needed
- **Next**: Waiting for user input on preferred solution
