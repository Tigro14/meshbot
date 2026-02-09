# Quick Fix: No Logs for MeshCore DM

## Problem
"I get absolutely NO log line when transmitting DM to Meshcore side"

## Cause
Basic MeshCore interface does NOT support binary protocol.
DM packets arrive in binary format and are rejected.

## Solution

### Install meshcore-cli

```bash
pip install meshcore meshcoredecoder --break-system-packages
sudo systemctl restart meshtastic-bot
```

### Verify Fix

Check startup logs:
```bash
journalctl -u meshtastic-bot -n 100 | grep "MESHCORE:"
```

**Should see:**
```
✅ MESHCORE: Using meshcore-cli library (FULL SUPPORT)
```

**If you see this instead (problem not fixed):**
```
⚠️  MESHCORE: Using BASIC implementation (LIMITED)
❌ DM messages will NOT be logged or processed
```

## What Changes

**Before (basic interface):**
- ❌ No logs when DM arrives
- ❌ Binary packets rejected
- ❌ Commands don't work
- ❌ Error message shown for each packet

**After (meshcore-cli):**
- ✅ DM logged with [DEBUG][MC]
- ✅ Binary protocol supported
- ✅ Commands work
- ✅ Complete MeshCore API

## Diagnostic Commands

**Check if libraries installed:**
```bash
python3 -c "import meshcore; print('✅ OK')" 2>&1
python3 -c "import meshcoredecoder; print('✅ OK')" 2>&1
```

**Check for rejected packets:**
```bash
journalctl -u meshtastic-bot -n 1000 | grep "PROTOCOLE BINAIRE NON SUPPORTÉ"
# Each occurrence = 1 DM that wasn't processed
```

## Summary

**Root cause:** Basic interface doesn't support binary protocol  
**Solution:** Install meshcore-cli library  
**Time:** < 2 minutes to fix  
**Impact:** DM will work and be logged immediately
