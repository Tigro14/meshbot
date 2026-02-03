# MeshCore DM Command Processing Debug

## Issue Description

MeshCore DM commands (like `/echo coucou`) are received and saved to database but NOT processed by command handlers.

## Logs Analysis

```
Feb 02 14:20:37 [INFO] 📬 [MESHCORE-DM] De: 0x143bcd7f | Message: /echo coucou
Feb 02 14:20:37 [INFO] 📞 [MESHCORE-CLI] Calling message_callback for message from 0x143bcd7f
Feb 02 14:20:37 [DEBUG] 📡 [MESHCORE] Packet #1 received
Feb 02 14:20:37 [INFO] 🔔 on_message CALLED | packet=True | interface=True
Feb 02 14:20:37 [INFO] 📨 MESSAGE BRUT: '/echo coucou' | from=0x143bcd7f | to=0xfffffffe | broadcast=False
Feb 02 14:20:37 [DEBUG] 🔍 Source détectée: MeshCore (dual mode)
Feb 02 14:20:37 [INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x143bcd7f | interface=SerialInterface
Feb 02 14:20:37 [INFO] 💿 [ROUTE-SAVE] Routage paquet: source=meshcore, type=TEXT_MESSAGE_APP, from=Node-143bcd7f
Feb 02 14:20:37 [INFO] 💾 [SAVE-MESHCORE] Tentative sauvegarde: TEXT_MESSAGE_APP de Node-143bcd7f (0x143bcd7f)
Feb 02 14:20:37 [INFO] ✅ [SAVE-MESHCORE] Paquet sauvegardé avec succès dans meshcore_packets
```

**MISSING LOGS**:
- No "ECHO PUBLIC de..." log (should appear in message_router.py line 95)
- No "MESSAGE REÇU de..." log (should appear in message_router.py line 125)
- No command execution

## Root Cause Analysis

### Packet Flow

1. **MeshCore Wrapper** (`meshcore_cli_wrapper.py` line 1296)
   ```python
   packet = {
       'from': sender_id,
       'to': to_id,  # 0xfffffffe for MeshCore local node
       'decoded': {...},
       '_meshcore_dm': True  # ✅ Flag is set
   }
   ```

2. **Dual Interface Manager** (`dual_interface_manager.py` line 174)
   ```python
   # Forward to main callback with network source tag
   self.message_callback(packet, interface, NetworkSource.MESHCORE)
   ```

3. **Main Bot** (`main_bot.py` line 704)
   ```python
   # Packet passes through, should reach message_handler
   self.message_handler.process_text_message(packet, decoded, message)
   ```

4. **Message Router** (`message_router.py` lines 83-93)
   ```python
   is_meshcore_dm = packet.get('_meshcore_dm', False)
   is_for_me = is_meshcore_dm or ((to_id == my_id) if my_id else False)
   is_broadcast = to_id in [0xFFFFFFFF, 0]
   
   # For /echo command
   if is_broadcast_command and (is_broadcast or is_for_me) and not is_from_me:
       # Should execute here if is_for_me is True
   ```

### Expected vs Actual

**For MeshCore DM with `/echo`:**
- `to_id = 0xfffffffe` (MeshCore local node)
- `_meshcore_dm = True` (set by wrapper)
- `is_meshcore_dm = True` (extracted in router)
- `is_for_me = True` (because is_meshcore_dm is True)
- `is_broadcast = False` (0xfffffffe not in [0xFFFFFFFF, 0])
- `is_broadcast_command = True` ("/echo" in list)
- Condition: `is_broadcast_command and (is_broadcast or is_for_me) and not is_from_me`
  - `True and (False or True) and True` → **should be TRUE**

**BUT**: No log "ECHO PUBLIC de..." appears, which means the condition is FALSE.

### Hypothesis

The `_meshcore_dm` flag might be:
1. ❓ Not present in packet (removed somewhere)
2. ❓ Present but not being checked correctly
3. ❓ Present but `is_for_me` calculation has a bug

## Debug Strategy

Added debug logging to trace the flag:

1. **main_bot.py** - Log when flag is present
2. **main_bot.py** - Log before calling process_text_message
3. **message_router.py** - Log routing decision with all variables

## Expected Debug Output

With the new logging, we should see:
```
[INFO] 🔍 [DEBUG] _meshcore_dm flag présent dans packet | from=0x143bcd7f | to=0xfffffffe
[INFO] 📞 [DEBUG] Appel process_text_message | message='/echo coucou' | _meshcore_dm=True
[DEBUG] 🔍 [ROUTER-DEBUG] _meshcore_dm=True | is_for_me=True | is_broadcast=False | to=0xfffffffe
```

If the flag is missing, we'll see:
```
[INFO] 📞 [DEBUG] Appel process_text_message | message='/echo coucou' | _meshcore_dm=False
[DEBUG] 🔍 [ROUTER-DEBUG] _meshcore_dm=False | is_for_me=False | is_broadcast=False | to=0xfffffffe
```

## Next Steps

1. ✅ Add debug logging
2. ⏳ Test with real MeshCore DM
3. ⏳ Identify where flag is lost (if it is)
4. ⏳ Fix the issue
5. ⏳ Remove debug logging
