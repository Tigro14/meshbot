# MeshCore No Packets - Complete Diagnostic Guide

## Problem Statement
"Still not a single Meshcore packet or DM displayed in the log nor responded to"

## Configuration Check

User has proper dual mode configuration:
```python
DUAL_NETWORK_MODE=True
MESHTASTIC_ENABLED=True
MESHCORE_ENABLED=True
DEBUG_MODE=True
```

## Diagnostic Procedure

### Step 1: Check Startup Logs

```bash
journalctl -u meshtastic-bot -n 300 | grep -A 20 "MESHCORE DUAL MODE INITIALIZATION"
```

**Look for:**

#### ✅ Success Pattern:
```
================================================================================
🔗 MESHCORE DUAL MODE INITIALIZATION
================================================================================
📍 MeshCore port: /dev/ttyUSB0
🔧 Interface class: MeshCoreCLIWrapper
🔍 Creating MeshCore interface...
✅ Interface object created: MeshCoreCLIWrapper
🔍 Attempting connection...
✅ MeshCore connection successful
✅ Node manager configured for pubkey lookups
🔍 Starting MeshCore serial reading thread...
✅ MeshCore reading thread started
🔍 Configuring dual interface manager...
✅ MeshCore interface set in dual manager
🔍 Setting up message callbacks...
✅ Message callbacks configured
✅ Primary interface: SerialInterface
================================================================================
✅ MESHCORE DUAL MODE INITIALIZATION COMPLETE
================================================================================
```

**If you see this:** MeshCore initialized successfully. Continue to Step 2.

#### ❌ Connection Failure Pattern:
```
================================================================================
❌ MESHCORE CONNECTION FAILED - Dual mode désactivé
================================================================================
   Port: /dev/ttyUSB0
   → Check serial port exists and is accessible
```

**Fix:**
```bash
# Check port exists
ls -la /dev/ttyUSB0

# Check permissions
groups $(whoami) | grep dialout

# Check if port is in use
sudo lsof /dev/ttyUSB0

# Check all USB serial ports
ls -la /dev/ttyUSB* /dev/ttyACM*
```

---

### Step 2: Verify Active Networks

```bash
journalctl -u meshtastic-bot -n 300 | grep -A 10 "SUBSCRIPTION SETUP"
```

**Expected output:**
```
================================================================================
🔔 SUBSCRIPTION SETUP - CRITICAL FOR PACKET RECEPTION
================================================================================
   meshtastic_enabled = True
   meshcore_enabled = True
   dual_mode (config) = True
   dual_mode (active) = True  ← MUST BE TRUE!
   connection_mode = serial
   📡 ACTIVE NETWORKS:
      ✅ Meshtastic (via primary interface)
      ✅ MeshCore (via dual interface)
      → Will see [DEBUG][MT] AND [DEBUG][MC] packets
```

**If `dual_mode (active) = False`:** Initialization failed, check Step 1 errors.

---

### Step 3: Monitor for Packet Reception

```bash
# Watch for MeshCore packets in real-time
journalctl -u meshtastic-bot -f | grep "\[MC\]"
```

**What to look for when MeshCore packet arrives:**
```
[INFO][MC] 📥 [RX_LOG] Paquet RF reçu (42B) - SNR:12.0dB RSSI:-50dBm
[DEBUG][MC] 📨 [RX_LOG] Text message detected, forwarding to bot
[DEBUG][MC] ➡️  [RX_LOG] Forwarding packet to bot callback
[DEBUG][MC] ✅ [RX_LOG] Packet forwarded successfully
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'meshcore'
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de NodeName...
```

**If you DON'T see these logs:** MeshCore radio may not be receiving packets.

---

## Quick Diagnostic Command

Run this all-in-one diagnostic:

```bash
echo "=== MeshCore Diagnostic ==="
echo ""
echo "1. Configuration:"
grep -E "DUAL_NETWORK_MODE|MESHTASTIC_ENABLED|MESHCORE_ENABLED" config.py
echo ""
echo "2. Serial Ports:"
ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No USB serial devices found"
echo ""
echo "3. Startup Status:"
journalctl -u meshtastic-bot -n 500 | grep -E "MESHCORE.*INITIALIZATION|dual_mode.*active" | tail -5
echo ""
echo "4. Recent MeshCore Activity:"
journalctl -u meshtastic-bot -n 100 | grep "\[MC\]" | tail -10
```

---

## Expected Full Startup Sequence

When everything is working correctly:

```
[INFO][MC] ✅ MESHCORE: Using meshcore-cli library (FULL SUPPORT)
[INFO] 🔄 MODE DUAL: Connexion simultanée Meshtastic + MeshCore
================================================================================
🔗 MESHCORE DUAL MODE INITIALIZATION
================================================================================
✅ MeshCore connection successful
✅ MeshCore reading thread started
================================================================================
✅ MESHCORE DUAL MODE INITIALIZATION COMPLETE
================================================================================
   dual_mode (active) = True
   📡 ACTIVE NETWORKS:
      ✅ Meshtastic (via primary interface)
      ✅ MeshCore (via dual interface)
```

**Then when MeshCore message arrives:**

```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (42B) - SNR:12.0dB
[DEBUG][MC] 📨 [RX_LOG] Text message detected, forwarding to bot
[DEBUG][MC] ✅ [RX_LOG] Packet forwarded successfully
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'meshcore'
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de NodeName 12345
```

---

## Next Steps

1. **Run Step 1** - Check if MeshCore initialized successfully
2. **If initialization failed** - Fix the error shown
3. **If initialization succeeded** - Run Steps 2-3 to check packet flow
4. **Share logs** showing complete startup sequence

---

**Date:** 2026-02-08  
**Version:** Enhanced diagnostics with ultra-visible logging
