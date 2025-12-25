# Quick Start: Public Key Sync for DM Decryption

## What This Fixes

**Problem**: In TCP mode, the bot couldn't decrypt Direct Messages (DMs) until 15-30 minutes after startup.

**Solution**: Bot now extracts and stores public keys from NODEINFO packets, enabling immediate DM decryption.

## How It Works (Simple Version)

1. **Node broadcasts NODEINFO** → Contains its public key
2. **Bot extracts key** → Stores in `node_names.json`
3. **Bot injects key** → Into `interface.nodes` (used by Meshtastic library)
4. **DM arrives** → Library can decrypt it immediately! ✓

## No Configuration Needed

This feature works automatically. No config changes required!

## What You'll See in Logs

### At Startup

```
[INFO] 🔑 Synchronisation des clés publiques vers interface.nodes...
[INFO] ✅ 5 clés publiques synchronisées vers interface.nodes
[INFO] ✅ 5 clés publiques restaurées pour déchiffrement DM
```

**Meaning**: Bot loaded 5 public keys from `node_names.json` and injected them into the interface. DMs from these 5 nodes can be decrypted immediately.

### During Operation (Every 5 Minutes)

```
[DEBUG] 🔑 Synchronisation périodique: 2 clés publiques mises à jour
```

**Meaning**: Bot found 2 new keys extracted from recent NODEINFO packets and injected them.

### When NODEINFO Arrives

```
[DEBUG] 📱 Nouveau: NodeName (12345678)
[DEBUG] 🔑 Clé publique extraite pour NodeName
```

**Meaning**: New node discovered with public key extracted and stored.

## Verifying It Works

### Test DM Decryption

1. **Start bot** (wait for "✅ clés publiques restaurées")
2. **Send DM to bot** from another node
3. **Check logs** - Should see decrypted text, not "ENCRYPTED"

**Before this fix**:
```
[DEBUG] 📦 ENCRYPTED de NodeName 12345678 [direct]
```

**After this fix**:
```
[DEBUG] 📦 TEXT_MESSAGE_APP de NodeName 12345678 [direct]
[DEBUG] Message: /help
```

### Check Key Count

Use the `/keys` command (if available) to see how many nodes have public keys.

## Troubleshooting

### "0 clés publiques synchronisées" at startup

**Cause**: No keys in `node_names.json` yet (first run or file deleted)

**Fix**: Wait for NODEINFO packets to arrive (15-30 min), then keys will be collected and persist across restarts.

### Still seeing ENCRYPTED messages

**Possible causes**:
1. Sender's NODEINFO not received yet → Wait for next NODEINFO broadcast
2. Sender using old firmware (< 2.5.0) → DM encryption may not be enabled
3. Network issue → Check mesh connectivity

**Quick fix**: Request NODEINFO manually:
```bash
meshtastic --request-telemetry --dest <node_id>
```

## File Locations

- **Key database**: `node_names.json` (in bot directory)
- **Backup**: Automatically saved every 60 seconds
- **Format**: Standard JSON, safe to inspect

## ESP32 Compliance

✅ This solution respects the ESP32 hardware limitation (single TCP connection)  
✅ No additional connections created  
✅ Uses passive collection only  

## Performance Impact

- **Network**: Zero additional overhead (passive collection)
- **CPU**: Minimal (JSON read/write every 5 min)
- **Memory**: ~1KB per 100 nodes (public keys)
- **Disk**: Keys stored in `node_names.json` (typically <100KB)

## Backward Compatibility

✅ Works with existing `node_names.json` files  
✅ Serial mode unchanged  
✅ TCP mode works with or without keys  
✅ No config changes needed  

## When To Use

**Automatic** - This feature is always active in both Serial and TCP modes. It just works!

## Support

If DM decryption still doesn't work after 30 minutes:

1. Check logs for "🔑 clés publiques" messages
2. Verify NODEINFO packets are being received
3. Check `node_names.json` for `publicKey` fields
4. See full documentation in `PUBKEY_SYNC_SOLUTION.md`

---

**Quick Summary**: 
- ✅ DM decryption works immediately at startup (TCP mode)
- ✅ No configuration needed
- ✅ No manual intervention required
- ✅ Just works!
