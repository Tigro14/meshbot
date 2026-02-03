# Meshtastic 2.7.15 DM Encryption - Troubleshooting Guide

## 📖 Overview

Starting with **Meshtastic firmware 2.7.15**, all Direct Messages (DMs) are **mandatorily encrypted using PKI (Public Key Infrastructure)**. This is a security enhancement that provides end-to-end encryption for private messages.

However, this change requires proper **public key exchange** between nodes to work correctly. If keys are not exchanged, DMs will appear as `ENCRYPTED` and cannot be processed by the bot.

## 🔍 Symptoms

If you see these log messages:
```
[DEBUG] 🔐 Encrypted DM from 0xa76f40da to us - likely PKI encrypted
[DEBUG] ❌ Missing public key for sender 0xa76f40da
[DEBUG] 💡 Solution: The sender's node needs to broadcast NODEINFO
```

This means:
- ✅ The bot received the DM packet
- ❌ The Meshtastic Python library couldn't decrypt it
- ⚠️ **Public key exchange is missing**

## 🎯 Root Cause

### Why Meshtastic 2.7.15 Changed DM Encryption

**Before 2.7.15:**
- DMs could use PSK (Pre-Shared Key) encryption
- Less secure - anyone with the channel password could read DMs
- Legacy behavior for backward compatibility

**With 2.7.15+:**
- **DMs MUST use PKI encryption**
- Each node has a unique public/private key pair
- Only the recipient (with private key) can decrypt DMs
- Sender signs messages with their private key
- Much more secure - true end-to-end encryption

### How PKI Encryption Works

```
┌─────────────────────────────────────────┐
│ Node A (Sender)                         │
│ - Has Node B's public key              │
│ - Encrypts DM with B's public key      │
│ - Signs with A's private key            │
└──────────────┬──────────────────────────┘
               │
               ▼ (Encrypted DM over LoRa/WiFi)
               │
┌──────────────▼──────────────────────────┐
│ Node B (Receiver - Bot)                 │
│ - Meshtastic library checks for keys   │
│ - Decrypts with B's private key        │
│ - Verifies A's signature                │
└─────────────────────────────────────────┘
```

**If Node B doesn't have Node A's public key:**
- Library can't verify signature → keeps packet encrypted
- Bot sees `encrypted` field instead of `decoded`
- Message cannot be processed

## 🛠️ Solution

### Step 1: Check Key Exchange Status

Use the new `/keys` command:

```bash
# Check all nodes
/keys

# Check specific node
/keys tigro
/keys F547F
/keys 0xa76f40da
```

**Expected output (compact format on mesh):**
```
✅ tigro: Clé OK (a1b2c3d4...)
❌ Node-a76f40da: Pas de clé publique
```

**Expected output (detailed format on Telegram/CLI):**
```
🔑 État des clés pour: tigro t1000E
   Node ID: 0xa76f40da

❌ Clé publique: MANQUANTE

⚠️ Vous NE POUVEZ PAS:
   • Recevoir des DM de ce nœud
   • Les DM apparaîtront comme ENCRYPTED

💡 Solution:
   1. Attendre l'échange automatique de clés
   2. Demander un NODEINFO au nœud:
      meshtastic --request-telemetry --dest a76f40da
   3. Vérifier que le nœud est en 2.5.0+
```

### Step 2: Request NODEINFO from Sender

From the **bot's host machine** (where bot is running):

```bash
# Request NODEINFO from the sender node
meshtastic --request-telemetry --dest a76f40da

# Or if you have the full node number (!hex notation)
meshtastic --request-telemetry --dest !a76f40da
```

This triggers the sender to broadcast their NODEINFO packet, which includes their public key.

### Step 3: Verify Key Exchange

After a few moments, check again:

```bash
# On the bot (via mesh or Telegram)
/keys tigro

# Or on bot's host machine
meshtastic --nodes | grep a76f40da
```

Look for `publicKey` field. Should show something like:
```
user:
  id: "!a76f40da"
  longName: "tigro t1000E"
  publicKey: "a1b2c3d4e5f6g7h8..."
```

### Step 4: Test DM Again

Once the key is exchanged:
1. Ask the sender to send another DM: `/help`
2. Bot should now be able to decrypt and process it
3. Check logs for success message:
```
[DEBUG] 📦 TEXT_MESSAGE_APP de tigro t1000E f40da [direct] (SNR:12.0dB)
```

## 🔄 Automatic Key Exchange

Meshtastic nodes automatically broadcast NODEINFO packets periodically (every 15-30 minutes by default). This includes their public key.

**If you're patient:**
- Just wait 15-30 minutes
- Keys will be exchanged automatically
- DMs will start working

**If you're impatient:**
- Use `meshtastic --request-telemetry --dest <node_id>` to trigger immediate exchange
- Or ask the sender to trigger it from their side

## ⚠️ Common Issues

### Issue 1: "But I have the key and it's still encrypted!"

If logs show:
```
[DEBUG] ✅ Sender's public key is present in node database
[DEBUG] ⚠️ Yet Meshtastic library couldn't decrypt - this is unexpected!
```

**Possible causes:**
1. **Outdated key**: Sender regenerated their keys but bot has old key
   - Solution: Request fresh NODEINFO
2. **Firmware incompatibility**: Sender on firmware < 2.5.0 (no PKI support)
   - Solution: Upgrade sender's firmware
3. **Corrupted key database**: Local node database corrupted
   - Solution: Restart Meshtastic interface, check `meshtastic --info`

### Issue 2: "Both nodes are on 2.7.15, still doesn't work!"

**Checklist:**
- ✅ Both nodes running 2.7.15 or 2.5.0+
- ✅ Public keys exchanged (check with `/keys`)
- ✅ Nodes can communicate (packets are received)
- ❌ **Missing**: Sender might not have **bot's** public key!

**Solution:** Key exchange must work in **both directions**:
- Bot needs sender's public key (to decrypt incoming DMs)
- Sender needs bot's public key (to encrypt outgoing DMs)

**Fix:**
```bash
# On sender's machine, request bot's NODEINFO
meshtastic --request-telemetry --dest <bot_node_id>

# Then check if sender has bot's key
meshtastic --nodes | grep <bot_node_id>
```

### Issue 3: "Keys keep disappearing"

If keys are exchanged but disappear later:
- Node database might be reset on reboot
- Check if node is configured to persist database
- Verify storage is working correctly

### Issue 4: "Can't request NODEINFO - command not working"

Make sure you're using the correct command syntax:
```bash
# Correct (lowercase, dash)
meshtastic --request-telemetry --dest a76f40da

# Wrong
meshtastic --requestTelemetry --dest a76f40da  # CamelCase doesn't work
meshtastic --request-nodeinfo --dest a76f40da  # Wrong flag name
```

## 📊 Diagnostic Commands

### Bot Commands (via mesh or Telegram)

| Command | Description |
|---------|-------------|
| `/keys` | Show key status for all nodes |
| `/keys tigro` | Check if specific node has key |
| `/keys 0xa76f40da` | Check by node ID |
| `/info tigro` | Full node info (includes key status in future) |
| `/nodes` | List known nodes |

### Host Machine Commands (CLI)

| Command | Description |
|---------|-------------|
| `meshtastic --info` | Show local node info + key |
| `meshtastic --nodes` | List all known nodes + keys |
| `meshtastic --request-telemetry --dest <id>` | Request NODEINFO |
| `journalctl -u meshbot -f` | Watch bot logs |
| `python3 cli_client.py` | Interactive CLI (if enabled) |

## 🔐 Security Notes

### What is Encrypted

- ✅ **DMs to specific nodes**: Encrypted with recipient's public key (PKI)
- ✅ **Channel messages**: Encrypted with channel PSK (shared password)
- ✅ **Admin messages**: Encrypted with session key

### What is NOT Encrypted

- ❌ **Broadcast announcements** (to 0xFFFFFFFF): If channel PSK is default/known
- ❌ **NODEINFO packets**: Public keys are sent in plaintext (by design)

### Privacy Considerations

**Good:**
- Only recipient can read DMs (end-to-end encryption)
- Even someone with channel PSK can't read DMs
- Each node has unique keys

**Important:**
- Public keys are **public** (broadcasted to network)
- Node IDs and names are visible
- Routing information (hops, relay nodes) is visible

## 📚 Technical Details

### Key Types

| Key Type | Size | Purpose |
|----------|------|---------|
| Public Key | 32 bytes (Curve25519) | Shared with network, used to encrypt DMs to this node |
| Private Key | 32 bytes (Curve25519) | Secret, never shared, used to decrypt DMs |

### Encryption Algorithm

- **DMs**: NaCl/libsodium `crypto_box` (Curve25519 + XSalsa20 + Poly1305)
- **Channels**: AES-256-CTR with shared PSK

### Firmware Versions

| Version | DM Encryption | Notes |
|---------|---------------|-------|
| < 2.5.0 | PSK (optional) | Legacy, insecure DMs |
| 2.5.0 - 2.7.14 | PKI (recommended) | PKI available but not mandatory |
| 2.7.15+ | PKI (mandatory) | **All DMs must use PKI** |

## 📖 References

- **Meshtastic Encryption**: https://meshtastic.org/docs/overview/encryption/
- **PKI Technical Details**: https://meshtastic.org/docs/development/reference/encryption-technical/
- **Firmware Changelog**: https://github.com/meshtastic/firmware/releases
- **Python Library**: https://meshtastic.org/docs/development/python/library/

## 🆘 Getting Help

If you're still stuck after following this guide:

1. **Check bot logs** with DEBUG_MODE enabled:
   ```python
   # In config.py
   DEBUG_MODE = True
   ```

2. **Use `/keys` command** to verify key status

3. **Check both directions**: Bot→Sender AND Sender→Bot

4. **Verify firmware versions**: Both nodes must be 2.5.0+

5. **Report issue** with:
   - Firmware versions (both nodes)
   - Output of `/keys <sender>`
   - Relevant log excerpts
   - Whether manual NODEINFO request worked

## ✅ Summary

**The Issue:**
- Meshtastic 2.7.15+ requires PKI key exchange for DMs
- Missing keys → DMs appear encrypted

**The Solution:**
1. Use `/keys` to check key status
2. Request NODEINFO from sender: `meshtastic --request-telemetry --dest <node_id>`
3. Verify key exchange worked: `/keys <node>`
4. Test DM again

**Prevention:**
- Keep firmware updated (2.7.15+ on all nodes)
- Wait 30min for automatic key exchange after adding new nodes
- Use `/keys` periodically to audit key status

---

**Last Updated**: 2025-12-24
**Applies to**: Meshtastic firmware 2.7.15+
**Bot Version**: meshbot (latest)
