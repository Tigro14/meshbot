# Fix: No MeshCore Packets Logged Despite Traffic

## Problem

User reports:
1. ❌ No MeshCore packet logs `[DEBUG][MC]` despite claiming there is traffic
2. ❌ Bot not responding to MeshCore DM messages

## Root Cause

### The Basic Implementation Limitation

The bot has **two** MeshCore interface implementations:

#### 1. meshcore-cli Library (FULL SUPPORT) ✅
- Full binary protocol parsing
- Complete message handling
- DM encryption/decryption
- Contact management
- Auto message fetching (RX_LOG_DATA events)

#### 2. Basic Implementation (LIMITED) ⚠️
- **Only supports text format:** `DM:<id>:<msg>`
- **Does NOT parse binary protocol**
- **Result:** Binary data is received but ignored

### What Happens with Basic Implementation

When MeshCore radio sends binary data:

```
📥 [MESHCORE-DATA] 45 bytes waiting
📦 [MESHCORE-RAW] Read 45 bytes: 3e2d00010203...
📨 [MESHCORE-BINARY] Reçu: 45 octets (protocole binaire MeshCore)

❌ [MESHCORE-BINARY] PROTOCOLE BINAIRE NON SUPPORTÉ!
   PROBLÈME: Données binaires MeshCore reçues mais non décodées
   IMPACT: Pas de logs [DEBUG][MC], pas de réponse aux DM
```

**No packets are created**, **no callbacks are invoked**, **no [DEBUG][MC] logs appear**.

## Solution

### Option 1: Install meshcore-cli Library (RECOMMENDED)

This is the **proper** solution for production use.

#### Installation

```bash
# Install meshcore library
pip install meshcore

# Install packet decoder (optional but recommended)
pip install meshcoredecoder

# Restart bot
sudo systemctl restart meshtastic-bot
```

#### Verification

Check startup logs:

```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep "meshcore-cli\|basic implementation"
```

**Should see:**
```
✅ Using meshcore-cli library
✅ [MESHCORE] Library meshcore-decoder disponible (packet decoding)
```

**Should NOT see:**
```
⚠️ Using basic implementation (meshcore-cli not available)
⚠️ [MESHCORE] UTILISATION DE L'IMPLÉMENTATION BASIQUE
```

#### Expected Results

With meshcore-cli library:

```
✅ Using meshcore-cli library
✅ [MESHCORE-CLI] Auto message fetching démarré
🔄 [MESHCORE-CLI] Vérification messages...

[When DM arrives:]
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de Alice 12345678 [direct]
[DEBUG][MC] 🔗 MESHCORE TEXTMESSAGE from Alice (12345678)
[DEBUG][MC]   └─ Msg:"Hello bot" | Payload:9B | ID:123456
```

Bot will respond to DMs.

### Option 2: Use Text Mode (WORKAROUND)

If you can't install meshcore-cli library, configure MeshCore radio to send **text format** instead of binary.

**Text format expected:**
```
DM:<sender_id_hex>:<message_text>
```

**Example:**
```
DM:12345678:Hello bot
```

**Note:** This requires configuring the MeshCore radio's companion mode output format (if supported).

### Option 3: Implement Binary Protocol (FOR DEVELOPERS)

If you're developing/testing the protocol, you can implement full binary parsing in `meshcore_serial_interface.py`:

- Parse binary frames: `0x3E + length(2 bytes) + payload`
- Decode message packets
- Extract sender ID, message text, metadata
- Create packet dict
- Call `self.message_callback(packet, None)`

**Not recommended** for production use - use meshcore-cli library instead.

## Diagnostic Commands

### Check Which Implementation Is Loaded

```bash
journalctl -u meshtastic-bot --since "5 minutes ago" | grep -i "meshcore-cli\|basic implementation"
```

### Check for Binary Data Warnings

```bash
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "PROTOCOLE BINAIRE NON SUPPORTÉ"
```

If you see this error repeatedly, MeshCore IS sending data but it's binary and can't be parsed.

### Check for Any MeshCore Activity

```bash
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "MESHCORE"
```

Look for:
- `📥 [MESHCORE-DATA]` - Data is arriving ✅
- `📨 [MESHCORE-BINARY]` - But it's binary ⚠️
- `❌ [MESHCORE-BINARY] PROTOCOLE BINAIRE NON SUPPORTÉ!` - And can't be parsed ❌

### Check Serial Port Status

```bash
# List available ports
ls -la /dev/ttyUSB* /dev/ttyACM*

# Check if port is in use
sudo lsof /dev/ttyUSB0  # Or whatever port you configured

# Check permissions
groups  # Should include 'dialout' group
```

## Configuration Requirements

### config.py

```python
DUAL_NETWORK_MODE = True          # Enable dual mode
MESHTASTIC_ENABLED = True         # Primary network
MESHCORE_ENABLED = True           # Secondary network
SERIAL_PORT = "/dev/ttyACM0"      # Meshtastic radio
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore radio (MUST be different!)
```

### System Requirements

#### For meshcore-cli Library:

```bash
# Python dependencies
pip install meshcore
pip install meshcoredecoder
pip install pyserial

# User permissions
sudo usermod -a -G dialout $USER
# Then logout/login or reboot
```

## Troubleshooting

### Issue: Still No Packets After Installing meshcore-cli

**Check startup logs for import errors:**

```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep -E "meshcore|ImportError|ModuleNotFoundError"
```

**Possible causes:**
- Library installed in wrong Python environment
- Bot running as different user (root vs dietpi)
- Virtualenv not activated

**Fix:**
```bash
# Check which Python bot uses
sudo systemctl cat meshtastic-bot | grep ExecStart

# Install in correct environment
# If using virtualenv:
source /path/to/venv/bin/activate
pip install meshcore meshcoredecoder

# If system Python:
sudo pip install meshcore meshcoredecoder

# Restart
sudo systemctl restart meshtastic-bot
```

### Issue: meshcore-cli Library Available But Still Binary Warnings

This suggests the library is installed but not being used properly.

**Check:**
1. Is `meshcore` library actually importable?
   ```bash
   python3 -c "import meshcore; print('OK')"
   ```

2. Check bot logs for which implementation was chosen:
   ```bash
   journalctl -u meshtastic-bot --since "5 minutes ago" | head -100 | grep "Using"
   ```

### Issue: Radio Not Sending Data

If you see heartbeat but NO data:

```
🔄 [MESHCORE-HEARTBEAT] Read loop active: 600 iterations, 0 data packets received
```

**Possible causes:**
- Radio not in companion mode
- Wrong serial port
- Radio not powered
- Wrong baudrate

**Verification:**
```bash
# Test serial port directly
sudo cat /dev/ttyUSB0
# Should see data if radio is transmitting

# Or use screen
sudo screen /dev/ttyUSB0 115200
# Press Ctrl+A, K to exit
```

## Summary

| Symptom | Cause | Solution |
|---------|-------|----------|
| No [DEBUG][MC] logs | Basic impl + binary protocol | Install meshcore-cli |
| Binary data ignored warnings | Basic impl limitations | Install meshcore-cli |
| Heartbeat shows 0 packets | No serial data | Check hardware/config |
| Bot doesn't respond to DMs | No packets parsed | Install meshcore-cli |

## Prevention

Always use meshcore-cli library for production MeshCore integration.

The basic implementation is only for:
- Development/testing of the protocol
- Debugging when meshcore-cli is not available
- Text-only communication (if radio supports it)

---

**Status:** Root cause identified, solution documented

**User action:** Install `pip install meshcore meshcoredecoder` and restart bot
