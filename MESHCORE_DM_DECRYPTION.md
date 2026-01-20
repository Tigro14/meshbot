# MeshCore DM Decryption

## Overview

The `meshcore-serial-monitor.py` tool now supports **Direct Message (DM) decryption** using PyNaCl. This allows you to decrypt encrypted DMs that the MeshCore library couldn't decrypt automatically due to missing keys or configuration issues.

## How It Works

### Encryption Method

MeshCore uses **NaCl/libsodium** for DM encryption:
- **Algorithm**: Curve25519 (ECDH) + XSalsa20-Poly1305 (AEAD)
- **Key Exchange**: Elliptic Curve Diffie-Hellman (ECDH)
- **Message Format**: Nonce (24 bytes) + Ciphertext + Authentication tag

### Decryption Process

```
┌────────────────────────────────────────┐
│  1. Encrypted DM Received              │
│     Via CONTACT_MSG_RECV event         │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  2. Check if Text is Encrypted         │
│     • Non-printable characters         │
│     • Base64-like pattern              │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  3. Get Sender's Public Key            │
│     From MeshCore contacts database    │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  4. Decrypt Using PyNaCl               │
│     • Our private key (provided)       │
│     • Sender's public key (contacts)   │
│     • NaCl Box (crypto_box)            │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  5. Display Decrypted Message          │
│     Show both encrypted and plaintext  │
└────────────────────────────────────────┘
```

## Installation

### Requirements

```bash
# Install PyNaCl for decryption
pip install PyNaCl

# Or with --break-system-packages on managed systems
pip install PyNaCl --break-system-packages
```

### Verify Installation

```bash
python3 -c "import nacl; print(f'PyNaCl version: {nacl.__version__}')"
```

Expected output:
```
PyNaCl version: 1.6.2
```

## Usage

### Basic Usage (No Decryption)

```bash
# Standard mode - relies on MeshCore library for decryption
python3 meshcore-serial-monitor.py /dev/ttyACM0
```

### With DM Decryption

#### Option 1: Private Key as Argument

```bash
# Base64 format (32 bytes - private key only)
python3 meshcore-serial-monitor.py /dev/ttyACM0 \
  --private-key "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU="

# Hex format (64 hex characters = 32 bytes)
python3 meshcore-serial-monitor.py /dev/ttyACM0 \
  --private-key "6162636465666768696a6b6c6d6e6f707172737475767778797a30313233343"

# MeshCore format (128 hex characters = 64 bytes: private key + public key)
python3 meshcore-serial-monitor.py /dev/ttyACM0 \
  --private-key "B8F7F7105F8929A641F6E6A75DE6E6ACDCC06A9A4661E3FDF0B3F9C402CC9043C6B9EF0F804E2FC854CC21EEFBBA6FCCA33D63C207CB3A6E928426E0AEC5F652"
```

**Note**: The tool automatically detects and handles both formats:
- **32 bytes**: Private key only
- **64 bytes**: Private key (first 32 bytes) + public key (last 32 bytes) - MeshCore format

#### Option 2: Private Key from File

```bash
# Create a key file
echo "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU=" > my_private_key.txt

# Use the key file
python3 meshcore-serial-monitor.py /dev/ttyACM0 \
  --private-key-file my_private_key.txt
```

#### With Debug Mode

```bash
# Show verbose decryption attempts
python3 meshcore-serial-monitor.py /dev/ttyACM0 \
  --private-key-file my_private_key.txt \
  --debug
```

## Output Examples

### Without Decryption

```
============================================================
[14:23:45] 📬 Message #1 received!
============================================================
Event type: ContactMessageEvent
  From: 0x12345678
  Text: �v�k�5?�ŝ�8�a�I�  <- Encrypted, unreadable
============================================================
```

### With Decryption

```
============================================================
[14:23:45] 📬 Message #1 received!
============================================================
Event type: ContactMessageEvent
  From: 0x12345678
  Text: �v�k�5?�ŝ�8�a�I�  <- Original encrypted

🔐 Text appears encrypted, attempting decryption...
  ✅ Found sender's public key (32 bytes)
  ✅ Decryption successful!
  📨 Decrypted text: /help
============================================================
```

### Statistics

```
📊 Statistics:
   DM messages received: 5
   RF packets received: 47
   Messages decrypted: 3    <- Shows decryption count
```

## Getting Your Private Key

### From MeshCore Device

1. **Connect to your MeshCore device**:
   ```bash
   # Via serial console or SSH
   ```

2. **Locate the private key**:
   ```bash
   # Common locations:
   cat /etc/meshcore/private_key.txt
   cat ~/.meshcore/key.priv
   ```

3. **Key format**: Should be 32 bytes in base64 or hex

### Generate Test Key (For Testing)

```python
import nacl.public
import base64

# Generate a test keypair
private_key = nacl.public.PrivateKey.generate()
public_key = private_key.public_key

# Display keys
print(f"Private key (base64): {base64.b64encode(bytes(private_key)).decode()}")
print(f"Public key (base64):  {base64.b64encode(bytes(public_key)).decode()}")
```

## Troubleshooting

### Issue 1: "PyNaCl not installed"

**Solution**:
```bash
pip install PyNaCl --break-system-packages
```

### Issue 2: "Failed to parse private key"

**Symptoms**:
```
⚠️  Failed to parse private key (expected 32 or 64 bytes, got X chars)
```

**Solution**:
- Verify key is 32 bytes (private key only) or 64 bytes (private + public key)
- Check format (base64 or hex)
- Remove any whitespace/newlines

**Valid formats**:
```bash
# Base64 - 32 bytes (44 characters with padding)
YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU=

# Hex - 32 bytes (64 hex characters)
6162636465666768696a6b6c6d6e6f707172737475767778797a30313233343

# MeshCore format - 64 bytes (128 hex characters: private key + public key)
B8F7F7105F8929A641F6E6A75DE6E6ACDCC06A9A4661E3FDF0B3F9C402CC9043C6B9EF0F804E2FC854CC21EEFBBA6FCCA33D63C207CB3A6E928426E0AEC5F652

# Hex with colons - 32 bytes (95 characters)
61:62:63:64:65:66:67:68:69:6a:6b:6c:6d:6e:6f:70:71:72:73:74:75:76:77:78:79:7a:30:31:32:33:34
```

**Note**: The MeshCore format concatenates the private key (first 32 bytes) and public key (last 32 bytes). The tool automatically uses only the first 32 bytes as the private key.

### Issue 3: "Sender's public key not found in contacts"

**Symptoms**:
```
❌ Sender's public key not found in contacts
   Contact ID: 0x12345678
```

**Solution**:
1. Ensure contacts are synced:
   ```
   ✅ Contacts synced successfully  <- Check startup logs
   ```

2. Verify sender is in contact list:
   - The sender must have broadcast their NODEINFO
   - Contact sync must have completed successfully

3. Check MeshCore library version:
   ```bash
   pip show meshcore
   ```

### Issue 4: "Decryption failed"

**Symptoms**:
```
✅ Found sender's public key (32 bytes)
❌ Decryption failed
```

**Possible causes**:
1. **Wrong private key** - Using a different device's key
2. **Corrupted encrypted data** - Network transmission error
3. **Wrong sender public key** - Contact database out of sync

**Solution**:
- Verify you're using the correct private key for your device
- Re-sync contacts
- Ask sender to send message again

### Issue 5: RF packets received but no DMs decoded

**Symptoms**:
```
[07:40:48] 📡 RX_LOG_DATA #1
  SNR: 11.75
  RSSI: -11
  Payload length: 39
  ℹ️  RF packet received but not decoded as DM by MeshCore library

[07:41:18] 💓 Monitor active | DM messages: 0 | RF packets: 47 ⚠️  (RF received but no DM decoded)
```

**Root Cause**: The MeshCore library is receiving RF packets but not successfully decoding them into CONTACT_MSG_RECV events. This typically means:
1. The MeshCore device doesn't have the private key configured properly
2. Contacts are not synced (missing sender's public key)
3. The encryption keys in the MeshCore device don't match the provided key file

**Solution**:

1. **Verify the private key matches your device**:
   - The key file should contain YOUR device's private key
   - Check if the key was exported from the correct device
   - MeshCore format: 64 bytes (private key + public key concatenated)

2. **Check MeshCore device configuration**:
   ```bash
   # Connect to device console and verify keys are loaded
   # The device must have the private key configured internally
   ```

3. **Verify contacts are synced**:
   - Look for "✅ Contacts synced successfully" in startup logs
   - Check the contact count: "ℹ️  X contacts available"
   - If 0 contacts, ensure other nodes have broadcasted their NODEINFO
   - In the Configuration Diagnostics section, verify:
     - Contact list shows the sender's node ID
     - Contact has "✅ Has pubkey" status
   - If contacts sync fails, the library can't decrypt DMs

4. **Check contact list details**:
   The monitor shows contact details during startup diagnostics:
   ```
   📋 Contact List:
      1. ID: 0x12345678 (SenderNode) - ✅ Has pubkey
      2. ID: 0x87654321 (OtherNode) - ⚠️  No pubkey
   ```
   Verify that the sender of the DM appears in this list with "✅ Has pubkey"

4. **Verify auto message fetching is running**:
   - Look for "✅ Auto message fetching started" in startup logs
   - Without this, CONTACT_MSG_RECV events won't be dispatched

5. **Check MeshCore library version**:
   ```bash
   pip show meshcore
   ```
   - Ensure you're using a compatible version that supports PKI encryption

**Important Note**: The monitor's DM decryption feature only works when the MeshCore library successfully dispatches CONTACT_MSG_RECV events. If the library itself can't decrypt (due to missing keys in the device), the monitor won't receive the event to decrypt manually.

**Workaround**: If MeshCore library consistently fails to decode DMs, you may need to:
- Reconfigure the MeshCore device with proper keys
- Or use a different decryption approach that works directly with raw RF payloads (not currently implemented)

### Issue 6: Not detecting encrypted messages

**Symptoms**:
- Messages appear garbled but decryption not attempted

**Solution**:
- Enable debug mode to see detection logic:
  ```bash
  python3 meshcore-serial-monitor.py /dev/ttyACM0 \
    --private-key-file key.txt \
    --debug
  ```

## Security Considerations

### Private Key Protection

⚠️ **IMPORTANT**: Your private key is highly sensitive!

**Best practices**:
1. **Never share** your private key
2. **Use file permissions**:
   ```bash
   chmod 600 my_private_key.txt
   ```
3. **Don't commit** keys to git
4. **Use environment variables** for automation:
   ```bash
   export MESHCORE_PRIVATE_KEY="..."
   ```

### What Can Be Decrypted

✅ **Can decrypt**:
- DMs sent to your device (using your private key)
- Messages from contacts with known public keys

❌ **Cannot decrypt**:
- DMs sent to other devices (not addressed to you)
- Messages from unknown contacts (no public key)
- Channel/broadcast messages (different encryption)

### Privacy

- ✅ Only your DMs are decrypted (addressed to your device)
- ✅ Respects end-to-end encryption (needs both keys)
- ✅ No man-in-the-middle decryption possible
- ✅ Each message requires both sender's public key and receiver's private key

## Testing

### Run Decryption Tests

```bash
# Run comprehensive test suite
python3 test_meshcore_dm_decryption.py
```

Expected output:
```
============================================================
MeshCore DM Decryption Test Suite
============================================================

✅ PyNaCl version: 1.6.2

Test 1: Basic Encryption/Decryption
✅ TEST PASSED: Decryption successful!

Test 2: Key Parsing
✅ TEST PASSED: All key formats parsed successfully!

Test 3: Monitor Decryption Logic
✅ TEST PASSED: Monitor decryption successful!

Test 4: Invalid Key/Data Handling
✅ TEST PASSED: Invalid inputs handled correctly!

Test Summary
  ✅ Passed: 4/4
  ❌ Failed: 0/4

🎉 All tests passed!
```

### Manual Testing

1. **Generate test keypair**:
   ```bash
   python3 -c "
   import nacl.public
   import base64
   k = nacl.public.PrivateKey.generate()
   print('Private:', base64.b64encode(bytes(k)).decode())
   print('Public:', base64.b64encode(bytes(k.public_key)).decode())
   "
   ```

2. **Run monitor with test key**:
   ```bash
   python3 meshcore-serial-monitor.py /dev/ttyACM0 \
     --private-key "<base64_key_from_step1>" \
     --debug
   ```

3. **Send encrypted DM** from another device

4. **Verify decryption** in monitor output

## Command Reference

### CLI Options

| Option | Description |
|--------|-------------|
| `port` | Serial port (default: /dev/ttyACM0) |
| `--debug` | Enable verbose meshcore library output |
| `--private-key <key>` | Private key in base64 or hex (32 bytes) |
| `--private-key-file <path>` | Path to file containing private key |

### Key Formats

| Format | Length | Example |
|--------|--------|---------|
| Base64 | 44 chars | `YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU=` |
| Hex | 64 chars | `616263...` |
| Hex+Colons | 95 chars | `61:62:63:...` |

## Implementation Details

### Encryption Algorithm

- **Key Exchange**: Curve25519 (ECDH)
- **Encryption**: XSalsa20 (stream cipher)
- **Authentication**: Poly1305 (MAC)
- **Combined**: NaCl crypto_box (authenticated encryption)

### Key Sizes

- **Private Key**: 32 bytes (Curve25519 scalar)
- **Public Key**: 32 bytes (Curve25519 point)
- **Nonce**: 24 bytes (XSalsa20 nonce)

### Message Format

```
[Nonce: 24 bytes][Ciphertext: N bytes][MAC: 16 bytes]
```

Total overhead: 40 bytes (nonce + MAC)

## References

- **PyNaCl Documentation**: https://pynacl.readthedocs.io/
- **NaCl/libsodium**: https://nacl.cr.yp.to/
- **Curve25519**: https://cr.yp.to/ecdh.html
- **MeshCore**: https://github.com/meshcore-dev

## Changelog

### 2025-01-20 - Initial Implementation

- ✅ Added PyNaCl dependency for DM decryption
- ✅ Implemented `--private-key` and `--private-key-file` CLI options
- ✅ Added encrypted message detection logic
- ✅ Implemented NaCl crypto_box decryption
- ✅ Created comprehensive test suite
- ✅ Added documentation

### Features

1. **Automatic Detection**: Detects encrypted messages by analyzing text
2. **Multiple Key Formats**: Supports base64, hex, and hex-with-colons
3. **Contact Integration**: Retrieves sender public keys from MeshCore contacts
4. **Statistics**: Tracks decryption success rate
5. **Error Handling**: Gracefully handles missing keys and decryption failures

---

**Status**: ✅ Implemented and Tested  
**Version**: 1.0  
**Last Updated**: 2025-01-20
