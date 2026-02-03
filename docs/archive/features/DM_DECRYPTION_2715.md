# Meshtastic DM Encryption - Important Update

## ⚠️ IMPORTANT: This Document Contains Outdated Information

**The original implementation was based on incorrect assumptions about Meshtastic encryption.**

## Correct Information About Meshtastic Encryption

### Encryption Methods by Message Type

Starting with **Meshtastic firmware 2.5.0** (not 2.7.15), encryption works as follows:

| Message Type | Encryption Method | Key Used |
|-------------|------------------|----------|
| **Channel/Broadcast Messages** | AES256-CTR | Channel PSK (Pre-Shared Key) |
| **Direct Messages (DMs)** | **PKI (Public Key Cryptography)** | Recipient's Public Key + Sender's Private Key |
| **Admin Messages** | PKC (DH) + AES-CTR | Session Secret |

### The Real Problem

#### Before Meshtastic 2.5.0
- DM messages MAY have been sent with channel PSK encryption
- Less secure (anyone with channel key could read DMs)

#### With Meshtastic 2.5.0+ (including 2.6.x and 2.7.x)
- **DMs use PKI encryption**, NOT channel PSK
- Each node has a unique public/private key pair
- Sender encrypts DM with recipient's public key
- Only recipient can decrypt with their private key
- Message is signed with sender's private key for authentication
- **Meshtastic Python library automatically decrypts PKI DMs** if keys are available

### Why Encrypted DMs Appear in Logs

If you see encrypted DMs in logs:
```
[DEBUG] 📦 ENCRYPTED de tigro t1000E f40da [direct] (SNR:12.0dB)
[DEBUG] 🔐 Encrypted DM from 0xa76f40da to us - likely PKI encrypted
[DEBUG] 💡 If this is a DM, ensure both nodes have exchanged public keys
```

**This means:**
1. ✅ The Meshtastic Python library received the packet
2. ❌ The library could NOT automatically decrypt it with PKI
3. ⚠️ **Public key exchange is missing or incomplete**

## The Correct Solution

### How PKI Encryption Works

**Meshtastic Python library handles PKI decryption automatically:**
- When a DM is received, the library checks if it's encrypted with PKI
- If the receiving node has the sender's public key, decryption happens automatically
- The bot receives the packet with a `decoded` field (plaintext)
- **No manual decryption needed by the bot**

### Why Manual PSK Decryption is Wrong

**The previous implementation (PR #179) was incorrect:**
- ❌ Tried to decrypt PKI-encrypted DMs with channel PSK
- ❌ Produced garbage data (e.g., "dix" instead of "/help")
- ❌ Even if "decryption" appeared successful, result was invalid protobuf
- ❌ This is fundamentally the wrong encryption method

**Channel PSK decryption should only be used for:**
- ✅ Channel/broadcast messages (to `0xFFFFFFFF`)
- ❌ NOT for Direct Messages (DMs have unique recipient)

### Fixing Encrypted DM Issues

If DMs appear as ENCRYPTED, the issue is at the **node level**, not the bot:

1. **Check Public Key Exchange:**
   ```bash
   meshtastic --info
   # Look for "nodes" section - each node should have a "user" field with "publicKey"
   ```

2. **Verify Node Database:**
   - The receiving node must have the sender's public key in its node database
   - The sender must have the receiver's public key
   - Keys are exchanged via NODEINFO_APP packets

3. **Force Node Database Refresh:**
   ```bash
   # Request nodeinfo from sender
   meshtastic --request-telemetry --dest <sender_node_id>
   ```

4. **Check for Duplicate/Conflicted Keys:**
   - Some vendors shipped devices with duplicate keys (security issue)
   - Regenerate keys if needed
   - See Meshtastic security advisories

### Detection Logic (Updated)

The bot now correctly handles encrypted packets:
1. ✅ Packet has `encrypted` field (not `decoded`)
2. ✅ Check if it's a DM to our node (`to_id == my_node_id`)
3. ⚠️ **Do NOT attempt PSK decryption** (will produce garbage)
4. ✅ Log helpful message about key exchange
5. ✅ Keep packet as ENCRYPTED in statistics

### Processing Flow (Correct)

```
┌─────────────────────────────────────────────┐
│  Packet Received                            │
│  from Meshtastic Python Library             │
└────────────────┬────────────────────────────┘
                 │
                 ▼
         ┌───────────────────┐
         │ Has 'decoded'     │
         │ field?            │
         └─────────┬─────────┘
                   │
        ┌──────────┴──────────┐
        │ Yes                 │ No ('encrypted' present)
        ▼                     ▼
┌──────────────────┐  ┌──────────────────────────┐
│ Library already  │  │ Library couldn't decrypt │
│ decrypted PKI    │  │ (missing public key)     │
│ → Process!       │  │ → Keep as ENCRYPTED      │
└──────────────────┘  └──────────┬───────────────┘
                                 │
                                 ▼
                        ┌────────────────────┐
                        │ Is DM to us?       │
                        └────────┬───────────┘
                                 │
                        ┌────────┴─────────┐
                        │ Yes              │ No
                        ▼                  ▼
                ┌──────────────────┐  ┌──────────────┐
                │ Log: Check key   │  │ Log: Not     │
                │ exchange status  │  │ for us       │
                └──────────────────┘  └──────────────┘
```

## Privacy & Security

### What is Decrypted
- ✅ **DMs with PKI**: Automatically decrypted by Meshtastic library if keys available
- ✅ **Channel messages**: Decrypted by library if correct channel PSK configured
- ❌ **DMs without keys**: Remain encrypted (node database issue)
- ❌ **DMs to other nodes**: NOT decrypted by us (respects privacy)

### Security Considerations
1. **PKI Security**: Each node has unique public/private key pair
2. **End-to-End Encryption**: Only sender and recipient can read DMs
3. **Message Authentication**: Sender's signature verifies message integrity
4. **Key Management**: Public keys exchanged via NODEINFO_APP packets
5. **No PSK for DMs**: Channel PSK only for broadcast, NOT for DMs

## Configuration

### Requirements
- **Meshtastic**: `meshtastic>=2.2.0` with PKI support
- **Firmware**: Meshtastic 2.5.0+ (all versions with PKI encryption)
- **No special configuration needed**: PKI handled by Meshtastic library

### Key Management

**Public/Private keys are managed at the node level, not in bot config:**

1. **Check Node Keys:**
   ```bash
   meshtastic --info
   ```
   Look for:
   - `user.id`: Your node ID
   - `user.publicKey`: Your public key (hex string)
   - In `nodes` section: Other nodes' public keys

2. **Verify Key Exchange:**
   ```bash
   meshtastic --nodes
   ```
   Each node should show `publicKey` field

3. **Regenerate Keys (if needed):**
   ```bash
   # WARNING: This will change your node identity
   # Other nodes will need to re-learn your public key
   meshtastic --set security.private_key ""
   meshtastic --reboot
   ```

### Channel PSK Configuration (For Broadcasts Only)

Channel PSK is for broadcast messages, NOT DMs. To configure:

```bash
# View current channel config
meshtastic --ch-index 0 --ch-get

# Set custom PSK for channel 0
meshtastic --ch-set psk base64:YOUR_PSK_HERE --ch-index 0
```

**Note**: Changing channel PSK does NOT affect DM encryption (uses PKI).

## Troubleshooting

### DMs Still Show as ENCRYPTED

**Log Example**:
```
[DEBUG] 📦 ENCRYPTED de tigro t1000E f40da [direct] (SNR:12.0dB)
[DEBUG] 🔐 Encrypted DM from 0xa76f40da to us - likely PKI encrypted
[DEBUG] 💡 If this is a DM, ensure both nodes have exchanged public keys
```

**Root Cause**: Missing public key exchange between nodes

**Solutions**:

1. **Check if sender's public key is in your node database:**
   ```bash
   meshtastic --nodes | grep -A 5 "a76f40da"
   ```
   Should show `publicKey` field. If missing, node hasn't received sender's NODEINFO.

2. **Request sender's node info:**
   ```bash
   # Request NODEINFO from sender (triggers key broadcast)
   meshtastic --request-telemetry --dest a76f40da
   ```

3. **Wait for automatic key exchange:**
   - Nodes broadcast NODEINFO periodically (every 15-30 minutes)
   - Key will be exchanged automatically over time
   - Check logs for "Received NODEINFO from..." messages

4. **Check for duplicate keys (security issue):**
   ```bash
   meshtastic --info | grep "publicKey"
   ```
   If your key matches known compromised keys, regenerate it.

5. **Verify sender can send DMs:**
   - Sender must also have YOUR public key
   - Ask sender to check their node database
   - Both directions need key exchange

### Testing Key Exchange

**Send test DM from sender's device:**
```bash
# From sender (e.g., 2.7.11 node)
meshtastic --sendtext "test" --dest YOUR_NODE_ID
```

**Expected outcomes:**
- ✅ **If keys exchanged**: DM appears with `decoded` field, bot processes it
- ❌ **If keys missing**: DM appears as ENCRYPTED in logs

**Note**: The first DM after key exchange may fail. Subsequent DMs should work.

## Performance Impact

### No Bot-Side Decryption Overhead
- PKI decryption handled by Meshtastic library (C++ code)
- Bot receives pre-decrypted packets (if keys available)
- Zero additional CPU/memory overhead in Python
- No impact on broadcast or relay performance

### Memory Usage
- No additional memory needed for decryption
- Library handles key management internally
- Bot only processes final decoded packets

## Future Enhancements

### Potential Improvements
1. **Key Exchange Monitoring**: Alert when new nodes lack public keys
2. **Statistics**: Track encrypted vs decrypted DM ratio
3. **Auto-diagnostics**: Detect and report key exchange issues
4. **Key Validation**: Check for duplicate/compromised keys

## References

- **Meshtastic Encryption (Official)**: https://meshtastic.org/docs/overview/encryption/
- **PKI Implementation Details**: https://meshtastic.org/docs/development/reference/encryption-technical/
- **Meshtastic Python Library**: https://meshtastic.org/docs/development/python/library/
- **Public Key Cryptography**: https://en.wikipedia.org/wiki/Public-key_cryptography
- **Firmware Releases**: https://github.com/meshtastic/firmware/releases

## Changelog

### 2025-12-17 - Major Correction
- ⚠️ **CORRECTED**: Removed incorrect PSK-based DM decryption
- ✅ **UPDATED**: Documentation reflects correct PKI encryption for DMs
- ✅ **FIXED**: Bot no longer attempts to decrypt PKI DMs with PSK
- ✅ **ADDED**: Proper guidance for key exchange troubleshooting
- ✅ **CLARIFIED**: Distinction between channel PSK and DM PKI encryption

### 2025-12-16 - Initial Implementation (INCORRECT)
- ❌ Added PSK-based DM decryption (wrong approach)
- ❌ Implemented `_decrypt_packet()` method (not needed for DMs)
- ❌ Documentation incorrectly stated DMs use channel PSK

---

**Status**: ✅ Corrected and Updated  
**Version**: 2.0 (Major Revision)  
**Last Updated**: 2025-12-17

**IMPORTANT**: If you implemented the previous version (1.0), please update to this corrected version immediately. The old implementation will produce garbage data when attempting to decrypt PKI-encrypted DMs with channel PSK.
