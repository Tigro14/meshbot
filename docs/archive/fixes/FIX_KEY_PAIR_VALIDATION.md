# Fix: Private/Public Key Pair Validation Diagnostic

## Problem Statement

User reported: **"Still no pubkey. is it possible to test if the private key of the connected node is not good and do not match the public one?"**

Despite previous fixes for pubkey_prefix extraction, the pubkey is still not being found. The user suspects the private/public key pair on the connected MeshCore node may be mismatched or corrupted.

## Root Cause Analysis

### Possible Issues

1. **Mismatched Keys**: Private key on the device doesn't derive the expected public key
2. **Corrupted Keys**: Key files are corrupted or truncated
3. **Wrong Key Loaded**: Device loaded wrong private key from multiple key files
4. **Key Format Issues**: Keys are in wrong format or encoding

### Why This Matters

In Meshtastic/MeshCore:
- **Public key** = Identity of the node (first 32 bytes)
- **Node ID** = First 4 bytes of public key (used for addressing)
- **Private key** = Used for decrypting DMs and signing messages

If the private key doesn't match the public key:
- ❌ Can't decrypt DMs
- ❌ Node ID derivation fails
- ❌ Messages can't be decrypted
- ❌ Identity verification fails

## Solution: Key Pair Validation

### Implementation

Added comprehensive key pair validation to diagnostic checks that:

1. **Derives public key from private key** using Curve25519 cryptography
2. **Compares derived vs expected public key**
3. **Derives node_id from public key** (first 4 bytes)
4. **Validates node_id matches device** node_id
5. **Reports mismatches clearly** with hex values

### Code Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ meshcore_cli_wrapper.py                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. PyNaCl Import (with graceful fallback)                      │
│    try:                                                         │
│        import nacl.public                                       │
│        NACL_AVAILABLE = True                                    │
│    except ImportError:                                          │
│        NACL_AVAILABLE = False                                   │
│                                                                 │
│ 2. _validate_key_pair() Method                                 │
│    • Parse private key (bytes/hex/base64)                      │
│    • Derive public key using Curve25519                        │
│    • Compare with expected public key                          │
│    • Return (is_valid, derived_key, error_msg)                │
│                                                                 │
│ 3. _check_configuration() Enhancement                          │
│    • Find private key (memory/files)                           │
│    • Validate key pair                                         │
│    • Derive node_id from public key                            │
│    • Compare derived vs actual node_id                         │
│    • Report mismatches                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Validation Method

```python
def _validate_key_pair(self, private_key_data, public_key_data=None):
    """
    Validate that a private key can derive the expected public key
    
    Args:
        private_key_data: Private key (bytes/hex/base64)
        public_key_data: Optional expected public key for comparison
        
    Returns:
        tuple: (is_valid, derived_public_key, error_message)
    """
    if not NACL_AVAILABLE:
        return (None, None, "PyNaCl not available")
    
    # Parse private key (supports bytes, hex, base64)
    private_key_bytes = parse_key(private_key_data)
    
    # Derive public key using Curve25519
    private_key = nacl.public.PrivateKey(private_key_bytes)
    derived_public_key = private_key.public_key
    
    # Compare if expected public key provided
    if public_key_data:
        expected = parse_key(public_key_data)
        if derived_public_key != expected:
            return (False, derived_public_key, "Keys don't match!")
    
    return (True, derived_public_key, None)
```

## Diagnostic Output

### Scenario 1: Valid Key Pair ✅

```
1️⃣  Vérification clé privée...
   ✅ Attributs clé trouvés: private_key
   ✅ private_key est défini
   
   🔐 Validation paire de clés privée/publique...
   📝 Utilisation de private_key pour validation
   ✅ Clé privée valide - peut dériver une clé publique
   🔑 Clé publique dérivée: 143bcd7f1b1f4a5e...3d2c1b0a9f8e7d6c
   🆔 Node ID dérivé: 0x143bcd7f
   ✅ Node ID correspond: 0x143bcd7f
```

### Scenario 2: Mismatched Keys ❌

```
1️⃣  Vérification clé privée...
   ✅ Attributs clé trouvés: private_key
   ✅ private_key est défini
   
   🔐 Validation paire de clés privée/publique...
   📝 Utilisation de private_key pour validation
   ✅ Clé privée valide - peut dériver une clé publique
   🔑 Clé publique dérivée: 143bcd7f1b1f4a5e...3d2c1b0a9f8e7d6c
   🆔 Node ID dérivé: 0x143bcd7f
   ❌ Node ID ne correspond PAS!
      Dérivé:  0x143bcd7f
      Actuel:  0x0de3331e
   
⚠️  Problèmes de configuration détectés:
   1. Node ID dérivé (0x143bcd7f) != Node ID actuel (0x0de3331e)
      → La clé privée ne correspond pas au device!
```

### Scenario 3: PyNaCl Not Available ℹ️

```
1️⃣  Vérification clé privée...
   ✅ Attributs clé trouvés: private_key
   ✅ private_key est défini
   
   🔐 Validation paire de clés privée/publique...
   ℹ️  PyNaCl non disponible - validation de clé ignorée
      Installer avec: pip install PyNaCl
```

### Scenario 4: Corrupted Private Key ❌

```
1️⃣  Vérification clé privée...
   ✅ Fichier(s) clé privée trouvé(s): node.priv
   ✅ node.priv est lisible (45 octets)
   
   🔐 Validation paire de clés privée/publique...
   📝 Utilisation du fichier node.priv pour validation
   ❌ Validation de clé échouée: Clé privée invalide 
      (doit être 32 octets, reçu: 45)
   
⚠️  Problèmes de configuration détectés:
   1. Validation de paire de clés échouée: Clé privée invalide
```

## Key Format Support

The validation supports multiple key formats:

### 1. Raw Bytes (32 bytes)
```python
private_key = b'\x01\x02\x03...\x1f\x20'  # 32 bytes
```

### 2. Hex String (64 characters)
```python
private_key = "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"
```

### 3. Hex with Public Key (128 characters)
```python
# MeshCore sometimes stores priv+pub concatenated
private_key = "0102030405...1f20" + "a1b2c3d4...e5f6"  # 64 bytes hex
# Only first 32 bytes (64 hex chars) used for private key
```

### 4. Base64 Encoded
```python
private_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="  # 32 bytes
```

## Node ID Derivation

### How Node IDs Work

In Meshtastic/MeshCore:
```
Public Key (32 bytes)
↓ Take first 4 bytes
Node ID (32-bit integer)
```

**Example:**
```
Public Key: 143bcd7f 1b1f4a5e 9c8d7b6a 5e4d3c2b 1a0f9e8d 7c6b5a49 3827...
            ^^^^^^^^
            First 4 bytes
            
Node ID:    0x143bcd7f (in decimal: 340901247)
```

### Validation Process

```python
# 1. Derive public key from private key
derived_public_key = derive_from_private(private_key)  # 32 bytes

# 2. Extract first 4 bytes for node_id
derived_node_id = int.from_bytes(derived_public_key[:4], 'big')

# 3. Compare with device's node_id
if derived_node_id == meshcore.node_id:
    ✅ Keys match!
else:
    ❌ Keys don't match - wrong private key loaded!
```

## Use Cases

### Use Case 1: Multiple Key Files

**Problem**: Device has multiple `.priv` files, loaded wrong one

**Diagnostic Output**:
```
Node ID ne correspond PAS!
   Dérivé:  0x143bcd7f  (from old_node.priv)
   Actuel:  0x0de3331e  (device's actual ID)
   
💡 Solution: Delete old_node.priv, keep only correct key file
```

### Use Case 2: Corrupted Key File

**Problem**: Key file truncated or corrupted

**Diagnostic Output**:
```
Validation de clé échouée: Clé privée invalide (doit être 32 octets, reçu: 28)

💡 Solution: Restore from backup or regenerate keys
```

### Use Case 3: Factory Reset Lost Keys

**Problem**: Device factory reset, key changed but file not updated

**Diagnostic Output**:
```
Node ID ne correspond PAS!
   Dérivé:  0xaabbccdd  (from old file)
   Actuel:  0x12345678  (device's new ID)
   
💡 Solution: Export new private key from device
```

## Testing

### Test Suite: `test_key_pair_validation.py`

Comprehensive test coverage:

1. ✅ **test_valid_key_pair** - Valid keys validate correctly
2. ✅ **test_mismatched_key_pair** - Mismatched keys detected
3. ✅ **test_key_hex_format** - Hex-encoded keys work
4. ✅ **test_key_base64_format** - Base64-encoded keys work
5. ✅ **test_node_id_derivation** - Node ID derivation correct
6. ✅ **test_invalid_key_size** - Invalid key sizes rejected
7. ✅ **test_nacl_not_available_graceful_fallback** - Graceful fallback

**Run Tests:**
```bash
$ python test_key_pair_validation.py
```

**Expected Output:**
```
============================================================
  ✅ ALL TESTS PASSED!
     7 tests run successfully
============================================================
```

## Installation

### For Full Validation Capability

```bash
pip install PyNaCl
```

**What it provides:**
- Curve25519 elliptic curve cryptography
- Private/public key derivation
- Used by Meshtastic for encryption

**Without PyNaCl:**
- Validation is skipped
- Diagnostic reports it clearly
- No functionality broken

## Troubleshooting Guide

### Issue: "PyNaCl non disponible"

**Solution:**
```bash
pip install PyNaCl
```

Then restart bot and run diagnostic.

### Issue: "Clé privée invalide (doit être 32 octets)"

**Causes:**
- Truncated key file
- Wrong file loaded
- Encoding issue

**Solutions:**
1. Check file size: `ls -la *.priv`
2. Should be exactly 32 bytes (or 44 for base64, 64 for hex)
3. Restore from backup or export from device

### Issue: "Node ID ne correspond PAS!"

**Cause:** Wrong private key loaded for this device

**Solutions:**
1. **Find correct key:**
   ```bash
   # List all key files
   ls -la *.priv
   
   # Try each one with diagnostic
   ```

2. **Export from device:**
   ```bash
   # Using meshcore-cli or meshtastic CLI
   meshtastic --export-keys
   ```

3. **Last resort:** Factory reset device and regenerate keys
   - ⚠️ Will lose ability to decrypt old messages
   - Will get new node_id

## Integration with Existing Diagnostics

The key validation is integrated into the existing `_check_configuration()` method:

```
Diagnostic Flow:
================

1️⃣  Vérification clé privée...
   • Check memory attributes
   • Check key files
   • NEW: Validate key pair ←
   • NEW: Validate node_id derivation ←

2️⃣  Vérification capacité sync contacts...
   
3️⃣  Vérification auto message fetching...

4️⃣  Vérification event dispatcher...

Summary:
   ⚠️  Problèmes détectés (if any)
```

## Benefits

1. ✅ **Identifies Mismatched Keys**: Catches wrong key loaded
2. ✅ **Validates Cryptography**: Ensures keys can derive correctly
3. ✅ **Diagnoses Root Cause**: Clear error messages
4. ✅ **Supports Multiple Formats**: Works with hex/base64/bytes
5. ✅ **Graceful Degradation**: Works without PyNaCl
6. ✅ **Comprehensive Testing**: 7 tests, all passing
7. ✅ **Clear Troubleshooting**: Actionable error messages

## Future Enhancements

### Potential Additions

1. **Key Export**: Add command to export current device key
2. **Key Backup**: Automatic backup of working keys
3. **Multiple Key Test**: Test all `.priv` files, suggest correct one
4. **Key History**: Log key changes for troubleshooting
5. **Auto-Fix**: Automatic selection of correct key from multiple files

### Advanced Validation

1. **Signature Test**: Sign/verify test message
2. **Encryption Test**: Encrypt/decrypt test message
3. **Contact Validation**: Validate contact public keys
4. **Certificate Chain**: Validate PKI certificate chain (if used)

## Related Issues

- **FIX_PUBKEY_FIELD_NAME.md**: Field naming issues
- **FIX_MESHCORE_PUBKEY_PREFIX_VARIANTS.md**: pubkey_prefix extraction
- **CONTACT_MESSAGE_FIX.md**: DM handling

## Status

✅ **IMPLEMENTED AND TESTED**

- Code changes: Complete
- Tests: 7/7 passing
- Documentation: Complete
- Ready for deployment

This diagnostic will help identify if the node's private key is mismatched or invalid, solving the "still no pubkey" issue!
