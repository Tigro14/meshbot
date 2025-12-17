# DM Decryption Fix Summary

## Issue Report
User reported that DMs from Meshtastic 2.7.11 sender to 2.6.11 receiver were not being decoded correctly:

```
Dec 16 23:30:59 DietPi meshtastic-bot[114533]: [DEBUG] 🔐 Attempting to decrypt DM from 0xa76f40da to us
Dec 16 23:30:59 DietPi meshtastic-bot[114533]: [DEBUG] 🔍 [Meshtastic 2.7.15+] Decrypted 23 bytes from 0xa76f40da
Dec 16 23:30:59 DietPi meshtastic-bot[114533]: [DEBUG] 🔍 [Meshtastic 2.7.15+] First bytes (hex): 64 69 78 cd bf 56 ac 6a a6 4b 5f 42 95 fa 47 70
```

The text sent was `/help` but decrypted to garbage: `64 69 78` = "dix..."

## Root Cause

**The implementation in PR #179 was fundamentally incorrect.**

### What Was Wrong

1. **Wrong Encryption Method**: PR #179 assumed DMs use channel PSK encryption (AES-CTR with shared key)
2. **Reality**: Meshtastic 2.5.0+ (including 2.6.11 and 2.7.11) use **PKI encryption** for DMs
3. **Result**: Attempting to decrypt PKI-encrypted data with PSK produces random garbage

### The Correct Understanding

| Message Type | Encryption | Key Used |
|-------------|-----------|----------|
| **Channel/Broadcast Messages** | AES256-CTR | Channel PSK (Pre-Shared Key) |
| **Direct Messages (DMs)** | **PKI (Public Key Cryptography)** | Recipient's Public Key + Sender Signature |
| **Admin Messages** | PKC (DH) + AES-CTR | Session Secret |

**Key Points:**
- DMs are **NOT** encrypted with channel PSK
- Each node has a unique public/private key pair
- Sender encrypts DM with recipient's **public key** (asymmetric encryption)
- Only recipient can decrypt with their **private key**
- Message is signed with sender's private key for authentication

## How PKI Decryption Works

**The Meshtastic Python library handles PKI decryption automatically:**

```
┌─────────────────────────────────────────┐
│ DM Sent (2.7.11 node)                   │
│ - Encrypted with receiver's public key  │
│ - Signed with sender's private key      │
└──────────────┬──────────────────────────┘
               │ (over LoRa/WiFi)
               ▼
┌─────────────────────────────────────────┐
│ Meshtastic Python Library (2.6.11 bot)  │
│ - Checks if keys available              │
│ - Decrypts with bot's private key       │
│ - Verifies sender's signature           │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴─────────┐
       │ Keys Available? │
       └───────┬─────────┘
               │
      ┌────────┴────────┐
      │ YES             │ NO
      ▼                 ▼
┌──────────────┐  ┌─────────────────┐
│ Auto-decrypt │  │ Keep 'encrypted'│
│ → 'decoded'  │  │ field (no keys) │
│ → Bot sees   │  │ → Bot sees      │
│   plaintext  │  │   encrypted     │
└──────────────┘  └─────────────────┘
```

**If keys are available**: Library auto-decrypts, bot receives `decoded` field ✅
**If keys are missing**: Library can't decrypt, bot receives `encrypted` field ⚠️

## The Fix

### Changes Made

1. **Removed PSK decryption for DMs** from `traffic_monitor.py`
   - Bot no longer attempts to decrypt DMs with channel PSK
   - Encrypted DMs remain encrypted (as they should)
   - Helpful log messages guide user to fix key exchange

2. **Updated DM_DECRYPTION_2715.md**
   - Corrected all incorrect information about PSK-based DM encryption
   - Added comprehensive troubleshooting for key exchange issues
   - Clear distinction between channel PSK and DM PKI encryption
   - Version 2.0 with major correction notice

3. **Marked test/demo files as deprecated**
   - Added warnings that these test PSK decryption (incorrect for DMs)
   - Point users to correct documentation

### New Behavior

When an encrypted DM is received:

```python
# OLD (incorrect):
debug_print(f"🔐 Attempting to decrypt DM from 0x{from_id:08x} to us")
decrypted = self._decrypt_packet(...)  # ❌ Wrong method!
# Result: Garbage data

# NEW (correct):
debug_print(f"🔐 Encrypted DM from 0x{from_id:08x} to us - likely PKI encrypted")
debug_print(f"💡 If this is a DM, ensure both nodes have exchanged public keys")
debug_print(f"   Run 'meshtastic --info' to check node database and keys")
# Keep packet as ENCRYPTED, wait for user to fix key exchange
```

## Solution for User

### Why DMs Appear as ENCRYPTED

**The issue is NOT in the bot - it's at the node level.**

When you see:
```
[DEBUG] 🔐 Encrypted DM from 0xa76f40da to us - likely PKI encrypted
```

It means:
1. ✅ Meshtastic Python library received the packet
2. ❌ Library couldn't auto-decrypt (missing sender's public key)
3. ⚠️ **Public key exchange incomplete**

### How to Fix

**Step 1: Check if you have sender's public key**
```bash
meshtastic --nodes | grep a76f40da
```

Look for `publicKey` field. If missing or empty, you don't have their key.

**Step 2: Request sender's node info**
```bash
meshtastic --request-telemetry --dest a76f40da
```

This triggers the sender to broadcast their NODEINFO (includes public key).

**Step 3: Wait for automatic exchange**
- Nodes broadcast NODEINFO every 15-30 minutes automatically
- Key will be exchanged passively over time
- Check logs for "Received NODEINFO from..." messages

**Step 4: Verify key exchange worked**
```bash
meshtastic --nodes | grep -A 5 a76f40da
```

Should now show `publicKey: <hex_string>`.

**Step 5: Test DM again**
```bash
# Ask sender to send another DM
# This time it should decrypt automatically
```

### Verify Both Directions

**Important**: Key exchange must work in BOTH directions:
- ✅ Your node must have sender's public key (to receive DMs)
- ✅ Sender must have your public key (to send DMs to you)

Check sender also has your key:
```bash
# On sender's node:
meshtastic --nodes | grep <your_node_id>
```

## Technical Details

### Why PSK Decryption Produced Garbage

When you try to decrypt PKI-encrypted data with a PSK:

1. **PKI encryption**: Uses sender's private key + recipient's public key
2. **PSK decryption**: Uses shared channel key
3. **Nonce mismatch**: Even if nonce construction matches, key is wrong
4. **Result**: XOR with wrong key stream → random bytes
5. **Hex output**: `64 69 78...` looks like data but is garbage
6. **Protobuf parsing**: May "succeed" but produces invalid fields

**Example from your log:**
- Expected: `/help` → hex `2f 68 65 6c 70`
- Got: garbage → hex `64 69 78 cd bf...` ("dix" + random bytes)

### Why the Library Can't Decrypt

The Meshtastic Python library decrypts PKI DMs automatically **if**:
- ✅ It has the sender's public key in node database
- ✅ The packet is properly signed
- ✅ The recipient's private key is available (always true for local node)

If any of these fail, packet remains with `encrypted` field.

## References

- **Meshtastic Encryption**: https://meshtastic.org/docs/overview/encryption/
- **PKI Implementation**: https://meshtastic.org/docs/development/reference/encryption-technical/
- **Python Library Docs**: https://meshtastic.org/docs/development/python/library/

## Changelog

- **2025-12-17**: Fixed incorrect PSK-based DM decryption from PR #179
- **2025-12-16**: Initial (incorrect) implementation in PR #179

---

**Status**: ✅ Fixed
**Version**: 2.0 (Major Correction)
**Issue**: Corrected fundamental misunderstanding of Meshtastic encryption
