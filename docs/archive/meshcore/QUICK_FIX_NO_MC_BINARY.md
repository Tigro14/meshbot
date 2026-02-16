# Quick Fix: No MeshCore Packets (Binary Protocol Issue)

## Problem
- ❌ No [DEBUG][MC] logs despite traffic
- ❌ Bot doesn't respond to MeshCore DMs

## Root Cause
Basic implementation doesn't support binary protocol.

## Solution (2 minutes)

### 1. Install meshcore-cli Library

```bash
pip install meshcore meshcoredecoder
sudo systemctl restart meshtastic-bot
```

### 2. Verify

```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep "meshcore-cli"
```

**Should see:**
```
✅ Using meshcore-cli library
```

**Should NOT see:**
```
⚠️ Using basic implementation
⚠️ [MESHCORE] UTILISATION DE L'IMPLÉMENTATION BASIQUE
```

### 3. Test

Send DM to bot and check:

```bash
journalctl -u meshtastic-bot -f | grep "\[MC\]"
```

Should see:
```
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de Alice...
```

## Diagnostic

**Check for binary protocol errors:**

```bash
journalctl -u meshtastic-bot --since "10 minutes ago" | grep "PROTOCOLE BINAIRE NON SUPPORTÉ"
```

If you see this repeatedly → Binary data arriving but can't be parsed → Install meshcore-cli

## Common Issues

### Issue: Still using basic implementation after install

**Fix:**
```bash
# Check if meshcore is importable
python3 -c "import meshcore; print('OK')"

# If error, library not in correct environment
# Check which Python bot uses:
sudo systemctl cat meshtastic-bot | grep ExecStart

# Install in correct environment
sudo pip3 install meshcore meshcoredecoder

# Restart
sudo systemctl restart meshtastic-bot
```

### Issue: Library installed but still errors

**Check for import errors:**
```bash
journalctl -u meshtastic-bot --since "1 minute ago" | grep -E "ImportError|ModuleNotFoundError"
```

## Expected Results

**With meshcore-cli:**
```
✅ Using meshcore-cli library
✅ [MESHCORE-CLI] Auto message fetching démarré
[DEBUG][MC] 📦 TEXT_MESSAGE_APP de User...
[DEBUG][MC] 🔗 MESHCORE TEXTMESSAGE from User...
```

Bot responds to DMs.

---

**Time to fix:** 2 minutes

**Commands:**
1. `pip install meshcore meshcoredecoder`
2. `sudo systemctl restart meshtastic-bot`
3. `journalctl -u meshtastic-bot --since "1 minute ago" | grep meshcore-cli`
