# Fix: MC Debug Logging Too Silent - Missing Subscription Messages

## Problem

When filtering MeshCore logs with `journalctl -u meshtastic-bot | grep MC`, the RX_LOG subscription messages were not visible because they used `info_print()` without the MC prefix.

### Before (Missing Logs)

```
Feb 03 14:25:29 DietPi meshtastic-bot[702]: [DEBUG][MC] ✅  PyNaCl disponible (validation clés)
Feb 03 14:25:29 DietPi meshtastic-bot[702]: [INFO][MC] ✅ Using meshcore-cli library
...
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [INFO][MC] ✅  Device connecté sur /dev/ttyACM0
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [DEBUG][MC] ✅  NodeManager configuré
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [INFO][MC] ✅  message_callback set successfully
```

**Missing:** No subscription message visible! User has no confirmation that RX_LOG monitoring is active.

## Solution

Changed all RX_LOG subscription messages to use `info_print_mc()` instead of `info_print()`, ensuring they appear with the `[INFO][MC]` prefix.

### After (Complete Logs)

```
Feb 03 14:25:29 DietPi meshtastic-bot[702]: [DEBUG][MC] ✅  PyNaCl disponible (validation clés)
Feb 03 14:25:29 DietPi meshtastic-bot[702]: [INFO][MC] ✅ Using meshcore-cli library
...
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [INFO][MC] ✅  Device connecté sur /dev/ttyACM0
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [DEBUG][MC] ✅  NodeManager configuré
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [INFO][MC] ✅  message_callback set successfully
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [INFO][MC] ✅ Souscription aux messages DM (events.subscribe)
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [INFO][MC] ✅ Souscription à RX_LOG_DATA (tous les paquets RF)
Feb 03 14:28:09 DietPi meshtastic-bot[977]: [INFO][MC]    → Monitoring actif: broadcasts, télémétrie, DMs, etc.
Feb 03 14:28:15 DietPi meshtastic-bot[977]: [DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662...
Feb 03 14:28:15 DietPi meshtastic-bot[977]: [DEBUG][MC] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hops: 0 | Status: ✅
```

**Now visible:** 
- ✅ Subscription confirmation messages
- ✅ Status message confirming monitoring is active
- ✅ RX_LOG packet activity (when DEBUG_MODE=True)

## Changes Made

### File: `meshcore_cli_wrapper.py`

#### Change 1: events.subscribe path (lines ~810-831)

**Before:**
```python
info_print("✅ [MESHCORE-CLI] Souscription à RX_LOG_DATA (tous les paquets RF)")
info_print("   → Le bot peut maintenant voir TOUS les paquets mesh (broadcasts, télémétrie, etc.)")
```

**After:**
```python
info_print_mc("✅ Souscription à RX_LOG_DATA (tous les paquets RF)")
info_print_mc("   → Monitoring actif: broadcasts, télémétrie, DMs, etc.")
```

#### Change 2: dispatcher.subscribe path (lines ~833-850)

**Before:**
```python
info_print("✅ [MESHCORE-CLI] Souscription à RX_LOG_DATA (tous les paquets RF)")
info_print("   → Le bot peut maintenant voir TOUS les paquets mesh")
```

**After:**
```python
info_print_mc("✅ Souscription à RX_LOG_DATA (tous les paquets RF)")
info_print_mc("   → Monitoring actif: broadcasts, télémétrie, DMs, etc.")
```

#### Change 3: DM subscription messages (lines ~812, ~835)

**Before:**
```python
info_print("✅ [MESHCORE-CLI] Souscription aux messages DM (events.subscribe)")
```

**After:**
```python
info_print_mc("✅ Souscription aux messages DM (events.subscribe)")
```

#### Change 4: Disabled messages (lines ~828-829, ~850)

**Before:**
```python
info_print("ℹ️  [MESHCORE-CLI] RX_LOG_DATA désactivé (MESHCORE_RX_LOG_ENABLED=False)")
```

**After:**
```python
info_print_mc("ℹ️  RX_LOG_DATA désactivé (MESHCORE_RX_LOG_ENABLED=False)")
```

## Benefits

1. **Consistent Logging:** All MeshCore messages now use the `[MC]` prefix
2. **Visibility:** Subscription messages visible when filtering for `[MC]`
3. **User Confirmation:** Users can confirm RX_LOG monitoring is active
4. **Troubleshooting:** Easier to diagnose if subscription fails
5. **Cleaner Format:** Removed redundant `[MESHCORE-CLI]` prefix (already have `[MC]`)

## Testing

Run the test script to verify:
```bash
python3 test_mc_logging_visibility.py
```

Expected output shows all messages with `[INFO][MC]` or `[DEBUG][MC]` prefix.

## Verification in Production

After deploying, check logs:
```bash
journalctl -u meshtastic-bot --no-pager -fn 1000 | grep MC
```

You should now see:
1. Initialization messages (`[INFO][MC]`)
2. **Subscription confirmation** (`[INFO][MC] ✅ Souscription...`)
3. **Monitoring status** (`[INFO][MC]    → Monitoring actif...`)
4. RX_LOG activity (`[DEBUG][MC] 📡 [RX_LOG]...`) when DEBUG_MODE=True

## Related Files

- `meshcore_cli_wrapper.py` - Main changes
- `utils.py` - Logging functions (unchanged, already correct)
- `test_mc_logging_visibility.py` - Test script
- `config.py` - DEBUG_MODE setting

## Impact

**Low risk:** Only changes logging output format, no functional changes to behavior.

**High value:** Makes MeshCore activity visible and debuggable.
