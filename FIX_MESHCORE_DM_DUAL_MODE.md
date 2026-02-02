# Fix: MeshCore DM Commands Not Processed in Dual Mode

## Problem Statement

MeshCore DM commands (e.g., `/echo coucou`) were received and saved to database but NOT processed by command handlers.

### Logs Showing the Issue

```
Feb 02 14:20:37 [INFO] 📬 [MESHCORE-DM] De: 0x143bcd7f | Message: /echo coucou
Feb 02 14:20:37 [INFO] 📞 [MESHCORE-CLI] Calling message_callback for message from 0x143bcd7f
Feb 02 14:20:37 [INFO] 🔔 on_message CALLED | packet=True | interface=True
Feb 02 14:20:37 [INFO] 📨 MESSAGE BRUT: '/echo coucou' | from=0x143bcd7f | to=0xfffffffe | broadcast=False
Feb 02 14:20:37 [DEBUG] 🔍 Source détectée: MeshCore (dual mode)
Feb 02 14:20:37 [INFO] ✅ [SAVE-MESHCORE] Paquet sauvegardé avec succès dans meshcore_packets
```

**What's Missing:**
- No "ECHO PUBLIC de..." log (command handler not called)
- No "MESSAGE REÇU de..." log (message router not reached)
- No command execution or response

## Root Cause

The filtering logic in `main_bot.py` (lines 577-581) was incorrectly filtering out MeshCore packets in dual mode:

```python
if connection_mode in ['serial', 'tcp']:
    # MODE SINGLE-NODE: Traiter tous les messages de notre interface unique
    if not is_from_our_interface:
        debug_print(f"📊 Paquet externe ignoré en mode single-node")
        return  # ❌ EARLY RETURN - Message never reaches command handlers!
```

### Why This Happened

In dual mode (`DUAL_NETWORK_MODE=True`):
- Both Meshtastic AND MeshCore interfaces are active
- `CONNECTION_MODE='serial'` (from config) applies to Meshtastic connection
- The filtering logic thought it was in "single-node mode"
- MeshCore packets had `is_from_our_interface` checked against Meshtastic interface
- If the check failed, packets were dropped BEFORE reaching command handlers

### The Bug

The comment says "MODE SINGLE-NODE" but the code was being executed in DUAL mode!

The condition `if connection_mode in ['serial', 'tcp']` is TRUE for dual mode because `CONNECTION_MODE='serial'` is set for the Meshtastic connection. But this filtering is inappropriate for dual mode where BOTH interfaces should be treated as "ours".

## Solution

Added a check for dual mode BEFORE the single-node filtering:

```python
# FIX: En mode dual, ne PAS filtrer par interface car les deux interfaces sont "les nôtres"
if self._dual_mode_active:
    # MODE DUAL: Tous les paquets des deux interfaces sont traités
    debug_print(f"✅ [DUAL-MODE] Packet accepté (dual mode actif)")
    # Continuer le traitement normalement
elif connection_mode in ['serial', 'tcp']:
    # MODE SINGLE-NODE: Traiter tous les messages de notre interface unique
    if not is_from_our_interface:
        debug_print(f"📊 Paquet externe ignoré en mode single-node")
        return
```

## Changes Made

### File: `main_bot.py`

**Line ~577**: Added dual mode check before single-node filtering

**Before:**
```python
if connection_mode in ['serial', 'tcp']:
    # MODE SINGLE-NODE: Traiter tous les messages de notre interface unique
    if not is_from_our_interface:
        debug_print(f"📊 Paquet externe ignoré en mode single-node")
        return
```

**After:**
```python
if self._dual_mode_active:
    # MODE DUAL: Tous les paquets des deux interfaces sont traités
    debug_print(f"✅ [DUAL-MODE] Packet accepté (dual mode actif)")
elif connection_mode in ['serial', 'tcp']:
    # MODE SINGLE-NODE: Traiter tous les messages de notre interface unique
    if not is_from_our_interface:
        debug_print(f"📊 Paquet externe ignoré en mode single-node")
        return
```

## Expected Behavior After Fix

With this fix, in dual mode:

```
[INFO] 📬 [MESHCORE-DM] De: 0x143bcd7f | Message: /echo coucou
[INFO] 📞 [MESHCORE-CLI] Calling message_callback for message from 0x143bcd7f
[INFO] 🔔 on_message CALLED | packet=True | interface=True
[INFO] 📨 MESSAGE BRUT: '/echo coucou' | from=0x143bcd7f | to=0xfffffffe | broadcast=False
[DEBUG] 🔍 Source détectée: MeshCore (dual mode)
[DEBUG] ✅ [DUAL-MODE] Packet accepté (dual mode actif)  ← NEW LOG
[INFO] 📞 [DEBUG] Appel process_text_message | message='/echo coucou' | _meshcore_dm=True
[DEBUG] 🔍 [ROUTER-DEBUG] _meshcore_dm=True | is_for_me=True | is_broadcast=False | to=0xfffffffe
[INFO] ECHO PUBLIC de Node-143bcd7f: '/echo coucou'  ← COMMAND EXECUTED!
[INFO] ✅ Message envoyé via MeshCore (broadcast, canal public)
```

## Impact

### Commands Now Working in Dual Mode
- `/echo` - Echo messages
- `/bot` - AI queries
- `/ia` - AI queries (French)
- All other broadcast-friendly commands
- All DM commands to either Meshtastic or MeshCore

### Modes Affected
- ✅ **Dual Mode** (`DUAL_NETWORK_MODE=True`) - FIXED
- ✅ **Single-Node Mode** (`CONNECTION_MODE='serial'` or `'tcp'`) - Unchanged
- ✅ **Legacy Mode** - Unchanged

## Testing

### Test Case 1: MeshCore DM Command
```
User sends: /echo test via MeshCore DM
Expected: Echo response sent back via MeshCore
```

### Test Case 2: Meshtastic Broadcast Command
```
User sends: /echo test via Meshtastic broadcast
Expected: Echo response sent back via Meshtastic
```

### Test Case 3: MeshCore Broadcast Command (future)
```
User sends: /echo test via MeshCore (if broadcast supported)
Expected: Echo response sent back via MeshCore
```

## Debug Logging

The fix includes comprehensive debug logging:

1. **Dual mode detection**: `✅ [DUAL-MODE] Packet accepté (dual mode actif)`
2. **Filter decision**: `🔍 [FILTER] connection_mode=... | dual_mode=True`
3. **MeshCore DM flag**: `🔍 [DEBUG] _meshcore_dm flag présent dans packet`
4. **Router decision**: `🔍 [ROUTER-DEBUG] _meshcore_dm=... | is_for_me=...`

## Future Improvements

### Clean Up Debug Logging
Once verified in production, the debug logging can be removed or reduced:
- Lines with `[DEBUG]` prefix
- Lines with `[DUAL-MODE]` prefix  
- Lines with `[FILTER]` prefix
- Lines with `[ROUTER-DEBUG]` prefix

### Configuration Clarification
Document that in dual mode:
- `CONNECTION_MODE` applies to Meshtastic connection only
- MeshCore connection is always serial (via `MESHCORE_SERIAL_PORT`)
- Both interfaces are treated as "ours" for command processing

## Related Files

- `main_bot.py` - Main fix (Phase 2 filtering logic)
- `handlers/message_router.py` - Debug logging for routing decisions
- `dual_interface_manager.py` - Dual mode interface manager
- `meshcore_cli_wrapper.py` - MeshCore DM packet creation with `_meshcore_dm` flag

## Verification

To verify the fix works:
1. Deploy bot with fix
2. Send `/echo test` command via MeshCore DM
3. Check logs for `✅ [DUAL-MODE] Packet accepté`
4. Verify `ECHO PUBLIC de...` log appears
5. Confirm echo response is sent back
