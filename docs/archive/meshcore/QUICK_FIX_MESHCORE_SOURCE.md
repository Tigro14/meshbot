# Quick Diagnostic: MeshCore Packet Source Not Set

## Problem
MeshCore packets not logging with [DEBUG][MC] classification in DEBUG mode.

## Quick Check

```bash
# 1. Check what source is being assigned
journalctl -u meshbot -f | grep "Final source"

# 2. Check network_source parameter
journalctl -u meshbot -f | grep "network_source="

# 3. Check mode settings
journalctl -u meshbot -f | grep "_dual_mode_active\|MESHCORE_ENABLED"
```

## Common Issues

### Issue 1: Source is 'local' instead of 'meshcore'

**Symptom:**
```
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'local'
```

**Likely Causes:**
1. Dual mode not active: `_dual_mode_active=False`
2. network_source is None: `network_source=None`
3. MESHCORE_ENABLED is False

**Solution:**
```python
# In config.py
DUAL_NETWORK_MODE = True   # Enable dual mode
MESHCORE_ENABLED = True    # Enable MeshCore
DEBUG_MODE = True          # Enable debug logging
```

### Issue 2: network_source is None

**Symptom:**
```
[DEBUG]    network_source=None
```

**Cause:** MeshCore interface not passing NetworkSource.MESHCORE to callback

**Check:** Look for this in dual_interface_manager.py:
```python
self.message_callback(packet, interface, NetworkSource.MESHCORE)
```

### Issue 3: Packets arrive but no classification

**Symptom:** Packets logged but all show [DEBUG][MT] instead of [DEBUG][MC]

**Solution:** The source parameter is wrong. Check with:
```bash
journalctl -u meshbot -f | grep "PACKET-SOURCE"
```

## Fix It

**For Dual Mode:**
```python
# config.py
DUAL_NETWORK_MODE = True
MESHCORE_ENABLED = True
DEBUG_MODE = True
```

**For Single MeshCore Mode:**
```python
# config.py
MESHCORE_ENABLED = True
CONNECTION_MODE = 'serial'  # or wherever MeshCore is
DEBUG_MODE = True
```

Then restart:
```bash
sudo systemctl restart meshbot
```

## Verify Fix

After restart, you should see:
```
[DEBUG] 🔍 [SOURCE-DEBUG] Final source = 'meshcore'
[INFO][MC] 🔗 MC DEBUG: MESHCORE PACKET IN add_packet()
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de NodeName ...
```

If not, run:
```bash
journalctl -u meshbot -n 200 | grep -E "SOURCE-DEBUG|network_source|dual_mode"
```

And share the output for further diagnosis.
