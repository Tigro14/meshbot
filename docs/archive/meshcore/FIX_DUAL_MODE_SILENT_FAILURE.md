# Fix: Dual Mode Silent Failure

## Problem

User reports NO MeshCore packets despite:
- ✅ Libraries installed (`meshcore`, `meshcoredecoder`)
- ✅ `DUAL_NETWORK_MODE = True` in config
- ✅ Runtime shows `dual_mode=True`
- ❌ But interface is `SerialInterface` (not dual)
- ❌ NO MeshCore packet logs

## Root Cause

Dual mode initialization can fail at multiple points, but falls back to Meshtastic-only mode **silently**:

1. **Meshtastic interface creation fails** (line 1806)
2. **MeshCore connection fails** (line 1841)
3. **MeshCore start_reading fails** (line 1850)

When failure occurs:
- Sets `_dual_mode_active = False`
- Falls back to `self.interface = meshtastic_interface`
- Logs error to stderr (might not be visible)
- **User doesn't realize dual mode failed**

## Solution

Added **prominent diagnostic banner** at startup that appears when config doesn't match reality:

```
================================================================================
⚠️  DUAL MODE INITIALIZATION FAILED!
================================================================================
   CONFIG: DUAL_NETWORK_MODE=True
   REALITY: Running in Meshtastic-only mode
   
   POSSIBLE CAUSES:
   1. Meshtastic port creation failed
   2. MeshCore port connection failed
   3. MeshCore start_reading failed
   
   CHECK LOGS ABOVE for error messages:
   - Look for '❌ Échec création interface Meshtastic'
   - Look for '❌ Échec connexion MeshCore'
   - Look for '❌ Échec démarrage lecture MeshCore'
   
   VERIFY:
   - SERIAL_PORT exists and accessible
   - MESHCORE_SERIAL_PORT exists and accessible
   - Both ports are different
   - meshcore/meshcoredecoder libraries installed
================================================================================
```

## Diagnostic Steps

### Step 1: Check for Failure Warning (30 seconds)

```bash
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot --since "1 minute ago" | grep "DUAL MODE INITIALIZATION FAILED" -A 25
```

If you see the warning, dual mode failed. Continue to Step 2.

### Step 2: Find Actual Error

```bash
journalctl -u meshtastic-bot --since "boot" | grep "❌ Échec"
```

This shows the exact failure point.

### Step 3: Verify Configuration

```bash
# Check ports exist
ls -la /dev/ttyACM* /dev/ttyUSB*

# Check config
grep -E "SERIAL_PORT|MESHCORE_SERIAL_PORT" config.py

# Check library
python3 -c "import meshcore; print('OK')"
```

## 5 Common Failure Scenarios

### Scenario 1: MeshCore Port Doesn't Exist

**Symptom:**
```
❌ Échec connexion MeshCore - Mode dual désactivé
```

**Check:**
```bash
ls -la /dev/ttyUSB*
```

**Possible causes:**
- MeshCore radio not connected
- Wrong port in config
- USB cable issue
- Radio powered off

**Fix:**
- Verify USB connection
- Check config: `MESHCORE_SERIAL_PORT`
- Try different USB port
- Power cycle radio

### Scenario 2: Port Permission Denied

**Symptom:**
```
❌ Échec connexion MeshCore - Mode dual désactivé
```

**Check:**
```bash
ls -la /dev/ttyUSB0
# Shows: crw-rw---- 1 root dialout ...
```

**Cause:**
User not in `dialout` group

**Fix:**
```bash
sudo usermod -a -G dialout dietpi
# Logout and login for group change to take effect
```

### Scenario 3: Same Port for Both

**Symptom:**
```
❌ Échec connexion MeshCore - Mode dual désactivé
```
OR
```
❌ Port Meshtastic verrouillé
```

**Check:**
```bash
grep SERIAL_PORT config.py
```

**Issue:**
```python
SERIAL_PORT = "/dev/ttyACM0"
MESHCORE_SERIAL_PORT = "/dev/ttyACM0"  # WRONG! Same port
```

**Fix:**
```python
SERIAL_PORT = "/dev/ttyACM0"           # Meshtastic
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore (DIFFERENT)
```

### Scenario 4: Port Already in Use

**Symptom:**
```
❌ Port Meshtastic verrouillé (tentative 1/3)
```

**Check:**
```bash
sudo lsof /dev/ttyACM0
```

**Cause:**
Another process using the port

**Fix:**
- Stop other process
- Or use different port
- Check for zombie processes

### Scenario 5: Library Not Imported

**Symptom:**
```
⚠️ Using basic implementation (meshcore-cli not available)
❌ Échec démarrage lecture MeshCore
```

**Check:**
```bash
python3 -c "import meshcore; print('OK')"
```

**Cause:**
Library not installed or import error

**Fix:**
```bash
pip install meshcore meshcoredecoder --break-system-packages
sudo systemctl restart meshtastic-bot
```

## Configuration Examples

### Correct Dual Mode Config

```python
# config.py
DUAL_NETWORK_MODE = True          # Enable dual mode
MESHTASTIC_ENABLED = True         # Primary network
MESHCORE_ENABLED = True           # Secondary network

# MUST be different ports!
SERIAL_PORT = "/dev/ttyACM0"      # Meshtastic radio
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore radio

# Libraries must be installed
# pip install meshcore meshcoredecoder
```

### Meshtastic-Only Config

```python
# config.py
DUAL_NETWORK_MODE = False         # Not using dual mode
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False

SERIAL_PORT = "/dev/ttyACM0"
```

### MeshCore-Only Config

```python
# config.py
DUAL_NETWORK_MODE = False
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True

MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

## Expected Results

### With Warning (Dual Mode Failed)

```
================================================================================
⚠️  DUAL MODE INITIALIZATION FAILED!
================================================================================
   CONFIG: DUAL_NETWORK_MODE=True
   REALITY: Running in Meshtastic-only mode
   ...
================================================================================
[INFO] interface=SerialInterface
[INFO] 🔔🔔🔔 on_message CALLED...
(Only Meshtastic packets, no MeshCore)
```

### Without Warning (Dual Mode Success)

```
🔄 MODE DUAL: Connexion simultanée Meshtastic + MeshCore
✅ Meshtastic Serial: /dev/ttyACM0
🔗 Configuration interface MeshCore: /dev/ttyUSB0...
🔧 [MESHCORE] DÉMARRAGE DIAGNOSTICS
✅ Mode dual initialisé avec succès

[INFO] dual_mode (active) = True
[INFO] 📡 ACTIVE NETWORKS:
       ✅ Meshtastic (via primary interface)
       ✅ MeshCore (via dual interface)
       → Will see [DEBUG][MT] AND [DEBUG][MC] packets
```

## Verification Commands

```bash
# Check dual mode status
journalctl -u meshtastic-bot --since "1m" | grep "dual_mode (active)"

# Check for failure warning
journalctl -u meshtastic-bot --since "1m" | grep "DUAL MODE INITIALIZATION FAILED"

# Check actual errors
journalctl -u meshtastic-bot --since "boot" | grep "❌ Échec"

# Port status
ls -la /dev/tty{ACM,USB}*
sudo lsof /dev/ttyACM0
sudo lsof /dev/ttyUSB0

# Library status
python3 -c "import meshcore; print('meshcore OK')"
python3 -c "import meshcoredecoder; print('decoder OK')"

# Config check
grep -E "DUAL_NETWORK_MODE|MESHTASTIC_ENABLED|MESHCORE_ENABLED|SERIAL_PORT|MESHCORE_SERIAL_PORT" config.py
```

## Impact

**Before:**
- Silent fallback to Meshtastic-only
- User doesn't know why no MeshCore
- Hours of debugging

**After:**
- PROMINENT warning at startup
- Clear explanation of failure
- Actionable verification steps
- 5-minute diagnosis

## Files Modified

- main_bot.py (+26 lines diagnostic banner)

## Testing

```bash
python3 -m py_compile main_bot.py
```

---

**Status:** Fixed and documented  
**User action:** Restart bot and check for warning, then verify config/ports
