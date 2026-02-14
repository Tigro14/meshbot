# MeshCore Encryption Detection Guide

## Quick Answer

**Q: "Now i got a crypted ? payload"**

**A: Yes, it's encrypted!** Specifically, you received an encrypted **ResponsePayload (type 1)**.

## Your Specific Case

### What You Saw

```
Payload Type: 1 (Response)
Route: Flood
Raw data: 20 bytes (hex string)
Hex: A393634C3F1DE763A4DA0C55AA1BBD0296417B3B
Decoded payload type: ResponsePayload
```

### Analysis

✅ **This is an encrypted ResponsePayload**
- Type 1 = Response packet
- 20 bytes of encrypted data
- No decoded text (because it's encrypted)

### What It Means

🔒 **Encryption Status:** Encrypted with channel PSK
- **To decrypt:** You need the channel's Pre-Shared Key (PSK)
- **Why encrypted:** ResponsePayloads are typically encrypted
- **Context:** This is a response to a previous request

---

## Understanding MeshCore Encryption

### Payload Types

**1. ResponsePayload (Type 1)**
- Usually encrypted
- Responses to requests (like /echo, /nodes, etc.)
- Requires channel PSK to decrypt
- Your case! ←

**2. TextMessage (Type 15)**
- May be encrypted or plaintext
- Depends on channel configuration
- If encrypted, needs appropriate PSK

**3. Other Types**
- Telemetry, position, etc.
- May or may not be encrypted
- Check payload type for context

### Encryption Indicators

**🔒 Encrypted:**
- Has raw data (hex bytes)
- No decoded text
- Shows "ENCRYPTED" indicator in diagnostic tool

**✅ Decrypted:**
- Has decoded text
- Shows actual message content
- Successfully decrypted with correct PSK

---

## PSK Requirements

### Channel Messages
- **Need:** Channel PSK
- **Where:** MeshCore channel configuration
- **Example:** Your ResponsePayload needs channel PSK

### Broadcast Messages
- **Need:** Default PSK (typically "AQ==")
- **Where:** Default configuration
- **When:** Messages to broadcast address

### Direct Messages (DMs)
- **Need:** Default PSK (Meshtastic 2.7.15+)
- **Where:** Default configuration
- **When:** DMs are encrypted by default in newer firmware

---

## How to Decrypt

### Step 1: Find Your Channel PSK

**Check MeshCore configuration:**
```bash
# Your MeshCore device should have channel configuration
# PSK is the Pre-Shared Key for the channel
```

### Step 2: Configure Bot

**In bot's config.py:**
```python
# Set the correct PSK for your channel
MESHCORE_CHANNEL_PSK = "your_channel_psk_here"
```

### Step 3: Test

**Run diagnostic script:**
```bash
python3 listen_meshcore_debug.py /dev/ttyACM1
```

**Send test message:**
```
/echo test
```

**Expected result:**
```
✅ DECRYPTED TEXT: "test"
→ Message successfully decrypted and decoded
```

---

## Diagnostic Tool Output

### Enhanced Detection

The diagnostic tool now shows:

**Encrypted ResponsePayload:**
```
📦 PAYLOAD:
  Type: dict
  Keys: ['raw', 'decoded']
  Decoded payload type: ResponsePayload

  🔒 ENCRYPTED ResponsePayload (type 1)
  Raw data: 20 bytes (hex string)
    Hex: A393634C3F1DE763A4DA0C55AA1BBD0296417B3B

  🔒 ENCRYPTED PAYLOAD
     ℹ️  This is an encrypted response packet (type 1)
     → ResponsePayloads are typically encrypted responses to requests
     → To decrypt, you need the channel PSK
```

**Decrypted Text:**
```
📦 PAYLOAD:
  ✅ DECRYPTED TEXT: "Hello World"
     → Message successfully decrypted and decoded
```

**Encrypted TextMessage:**
```
📦 PAYLOAD:
  Raw data: 39 bytes

  🔒 ENCRYPTED PAYLOAD
     ℹ️  This text message is encrypted
     → If broadcast: needs default PSK
     → If channel: needs channel PSK
     → If DM: needs default PSK (Meshtastic 2.7.15+)
```

---

## Troubleshooting

### Issue: All Messages Encrypted

**Symptom:** Never see decrypted text

**Solutions:**
1. Check PSK configuration
2. Verify channel settings match
3. Ensure PSK is base64 encoded correctly
4. Check Meshtastic firmware version

### Issue: Some Messages Decrypt, Others Don't

**Symptom:** Mix of encrypted and decrypted

**Explanation:**
- Different message types use different PSKs
- Channel messages vs broadcasts
- Check message destination (channel vs DM)

### Issue: ResponsePayload Always Encrypted

**Symptom:** Can't decrypt type 1 responses

**This is normal!**
- ResponsePayloads are typically encrypted
- Need channel PSK to decrypt
- Bot should handle this automatically

---

## Common Encryption Scenarios

### Scenario 1: Channel Message (/echo test)

**What happens:**
1. User sends `/echo test` on channel
2. Bot receives encrypted ResponsePayload
3. Bot decrypts with channel PSK
4. Bot processes and responds

**Your diagnostic tool shows:**
```
🔒 ENCRYPTED ResponsePayload (type 1)
→ To decrypt, you need the channel PSK
```

### Scenario 2: Broadcast Message

**What happens:**
1. Message sent to broadcast address
2. Encrypted with default PSK
3. All nodes can decrypt

**Diagnostic tool shows:**
```
🔒 ENCRYPTED TextMessage
→ If broadcast: needs default PSK
```

### Scenario 3: Direct Message (Meshtastic 2.7.15+)

**What happens:**
1. DM sent to specific node
2. Encrypted with default PSK
3. Only recipient can decrypt

**Diagnostic tool shows:**
```
🔒 ENCRYPTED TextMessage
→ If DM: needs default PSK (Meshtastic 2.7.15+)
```

---

## Summary

### Your Case: ResponsePayload

✅ **Yes, it's encrypted!**
- Type: ResponsePayload (type 1)
- Size: 20 bytes
- Encryption: Channel PSK
- Context: Response to a request

### Next Steps

1. ✅ **Identify:** You've identified it's encrypted (done!)
2. 🔧 **Configure:** Set correct PSK in bot config
3. ✅ **Test:** Run diagnostic tool to verify decryption
4. 🎉 **Use:** Bot processes decrypted messages

### Key Takeaways

1. 🔒 **ResponsePayloads** (type 1) are typically encrypted
2. 🔑 **Channel PSK** is needed to decrypt
3. ✅ **Diagnostic tool** clearly shows encryption status
4. 📚 **Documentation** helps understand what you see

---

## Additional Resources

**Related Documentation:**
- AUTO_MESSAGE_FETCHING_FIX.md - Message reception
- CALLBACK_SIGNATURE_FIX.md - Event handling
- RX_LOG_DATA_FIX.md - Event type selection

**Bot Configuration:**
- config.py - PSK configuration
- meshcore_cli_wrapper.py - MeshCore integration

**Meshtastic Documentation:**
- Encryption: https://meshtastic.org/docs/overview/encryption/
- Channels: https://meshtastic.org/docs/configuration/radio/channels/

---

**You now understand your encrypted payload and how to work with it!** 🎉
