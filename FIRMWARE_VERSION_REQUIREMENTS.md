# Firmware Version Requirements for PKI Public Keys

## Critical Issue: No Public Keys Detected

If `/keys` shows **0 keys after 24+ hours**, the most likely cause is **firmware version incompatibility**.

## Root Cause

Public keys in NODEINFO packets are **only available in Meshtastic firmware 2.5.0+**

### Protobuf Field Availability

```protobuf
message User {
  string id = 1;
  string long_name = 2;
  string short_name = 3;
  bytes macaddr = 4;
  HardwareModel hw_model = 5;
  Role role = 6;
  bytes public_key = 7;  // ← Added in firmware 2.5.0
}
```

### Firmware Version Timeline

| Version | PKI Support | Public Keys in NODEINFO |
|---------|-------------|------------------------|
| < 2.5.0 | ❌ No | ❌ Field doesn't exist |
| 2.5.0+ | ✅ Yes | ✅ Field present |
| 2.7.15+ | ✅ Yes | ✅ DM encryption mandatory |

## Diagnosis

### Step 1: Check Bot's Firmware

```bash
# If connected via TCP
meshtastic --host 192.168.1.38 --info | grep firmware

# If connected via serial
meshtastic --info | grep firmware
```

Expected output:
```
Firmware version: 2.5.2.abc1234 (or higher)
```

### Step 2: Check Network Nodes' Firmware

```bash
# Via TCP node
meshtastic --host 192.168.1.38 --nodes | grep -A5 "firmware"

# Via serial
meshtastic --nodes | grep -A5 "firmware"
```

Look for firmware versions. If most nodes show < 2.5.0, they won't have public keys.

### Step 3: Enable Debug Mode

In `config.py`:
```python
DEBUG_MODE = True
```

Restart bot and check logs for:
```
⚠️ NodeName: NODEINFO sans champ public_key (firmware < 2.5.0?)
```

If you see this message frequently → nodes are running old firmware.

### Step 4: Check NODEINFO Packet Structure

With DEBUG_MODE enabled, look for:
```
🔍 NODEINFO from NodeName (0x12345678):
   Available fields: ['id', 'longName', 'shortName', 'hwModel']
   Has 'public_key': False
   Has 'publicKey': False
```

**If `public_key` is False** → firmware < 2.5.0 or PKI disabled

## Solutions

### Option 1: Upgrade Firmware (Recommended)

All nodes should upgrade to **Meshtastic 2.5.0 or higher**:

1. **Via Web Flasher**: https://flasher.meshtastic.org
2. **Via CLI**:
   ```bash
   meshtastic --flash-firmware
   ```
3. **Via OTA**: Use network flashing if available

**After upgrade**:
- Nodes will automatically exchange public keys
- NODEINFO packets will include `public_key` field
- DM decryption will work

### Option 2: Wait for Network Upgrade

If you can't control all nodes:
- Monitor logs for nodes with keys
- DM decryption will work **only with nodes running 2.5.0+**
- Older nodes' DMs will remain encrypted

### Option 3: Disable PKI (Not Recommended)

Some firmwares allow disabling PKI:
```
Settings → Security → PKI → Off
```

**⚠️ Warning**: This reduces security. Not recommended.

## Verification After Upgrade

1. **Wait 30 minutes** for NODEINFO broadcasts
2. **Check logs** for key extraction:
   ```
   🔑 Clé publique extraite pour NodeName
   ```
3. **Run `/keys`** - should show nodes with keys
4. **Test DM** - send DM to bot, check logs

## Expected Behavior

### With Firmware 2.5.0+

```
[DEBUG] 🔍 NODEINFO from NodeA (0x12345678):
   Available fields: ['id', 'longName', 'shortName', 'hwModel', 'public_key']
   Has 'public_key': True
[DEBUG] 🔑 Clé publique extraite pour NodeA

/keys
🔑 État des clés publiques PKI
   (Nœuds vus dans les 48h)

Nœuds actifs: 147
✅ Avec clé publique: 145
❌ Sans clé publique: 2
```

### With Firmware < 2.5.0

```
[DEBUG] 🔍 NODEINFO from NodeA (0x12345678):
   Available fields: ['id', 'longName', 'shortName', 'hwModel']
   Has 'public_key': False
[DEBUG] ⚠️ NodeA: NODEINFO sans champ public_key (firmware < 2.5.0?)

/keys
🔑 État des clés publiques PKI
   (Nœuds vus dans les 48h)

Nœuds actifs: 147
✅ Avec clé publique: 0
❌ Sans clé publique: 147

⚠️ AUCUNE CLÉ PUBLIQUE DÉTECTÉE

Causes possibles:
   1. 🔴 Firmware < 2.5.0 (pas de PKI)
```

## Impact on DM Decryption

| Sender Firmware | Bot Has Key? | DM Decryption |
|----------------|--------------|---------------|
| < 2.5.0 | ❌ No | ❌ Shows as ENCRYPTED |
| 2.5.0+ | ✅ Yes | ✅ Decrypts successfully |
| 2.5.0+ | ❌ No | ❌ Shows as ENCRYPTED |

**Bottom line**: Both sender AND receiver must be on firmware 2.5.0+ for DM decryption to work.

## Troubleshooting

### "Still no keys after firmware upgrade"

1. **Restart nodes** after upgrade
2. **Wait 30 minutes** for NODEINFO broadcasts
3. **Force NODEINFO request**:
   ```bash
   meshtastic --request-telemetry --dest <node_id>
   ```
4. **Check bot logs** for extraction messages

### "Some nodes have keys, others don't"

This is **normal** if:
- Mixed firmware versions in network
- Some nodes haven't broadcast NODEINFO yet
- Some nodes just joined network

**Solution**: Focus on nodes you need to communicate with. Request their NODEINFO manually.

### "Debug logs show public_key: True but /keys shows 0"

This would indicate a bug. Check:
1. Is `node_names.json` being saved? Check file exists and has `publicKey` fields
2. Is `sync_pubkeys_to_interface()` being called? Check startup logs
3. Are keys being injected correctly? Check `interface.nodes[node_id]['user']`

## References

- **Meshtastic PKI Documentation**: https://meshtastic.org/docs/overview/encryption/
- **Firmware Releases**: https://github.com/meshtastic/firmware/releases
- **Web Flasher**: https://flasher.meshtastic.org

---

**TL;DR**: If no keys detected after 24h, **nodes are likely running firmware < 2.5.0**. Upgrade to 2.5.0+ to enable PKI and public key exchange.
