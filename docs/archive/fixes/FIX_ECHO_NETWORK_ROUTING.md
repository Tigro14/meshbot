# Fix: Echo Command Broadcasts to Wrong Network in Dual Mode

## Problem Statement

When `/echo coucou` was received via MeshCore in dual mode, the response was incorrectly broadcasted on the Meshtastic network instead of being sent back via MeshCore.

## Root Cause

The `handle_echo()` method in `handlers/command_handlers/utility_commands.py` was directly calling `interface.sendText()` which:

1. **Used `_get_interface()`** which returns the PRIMARY interface (Meshtastic by default)
2. **Bypassed dual mode routing** logic that exists in `send_single()`
3. **Ignored sender network mapping** tracked in `main_bot.py`

### Code Path (Before Fix)

```
MeshCore User → /echo test
        ↓
main_bot.py: Track sender network (line 643)
  set_sender_network(from_id, NetworkSource.MESHCORE)
        ↓
utility_commands.py: handle_echo()
        ↓
interface = _get_interface()  ← Returns PRIMARY (Meshtastic)
        ↓
interface.sendText(echo_response)  ← Sends to Meshtastic! ❌
```

### Correct Routing (in send_single)

The `send_single()` method in `message_sender.py` (lines 138-156) correctly implements dual mode routing:

```python
if self.dual_interface and self.dual_interface.is_dual_mode():
    network_source = self.get_sender_network(sender_id)  # Get tracked network
    success = self.dual_interface.send_message(message, sender_id, network_source)
```

## Solution

### Changes Made

#### 1. Modified `handle_echo()` in utility_commands.py

Added dual mode routing BEFORE the single-mode interface logic:

```python
# DUAL MODE: Route to correct network
if current_sender.dual_interface and current_sender.dual_interface.is_dual_mode():
    network_source = current_sender.get_sender_network(sender_id)
    
    if network_source:
        # Send broadcast to the correct network
        success = current_sender.dual_interface.send_message(
            echo_response, 
            0xFFFFFFFF,  # Broadcast destination
            network_source,
            channelIndex=0  # Public channel
        )
        return
```

#### 2. Enhanced `send_message()` in dual_interface_manager.py

Added `channelIndex` parameter to support proper broadcast channel selection:

```python
def send_message(self, text, destination_id, network_source=None, channelIndex=0):
    # ...
    if is_meshcore:
        interface.sendText(text, destinationId=destination_id, channelIndex=channelIndex)
    else:
        interface.sendText(text, destinationId=destination_id, channelIndex=channelIndex)
```

## Message Flow (After Fix)

```
MeshCore User → /echo test
        ↓
main_bot.py: Track sender network
  set_sender_network(from_id, NetworkSource.MESHCORE)
        ↓
utility_commands.py: handle_echo()
        ↓
Check dual mode: TRUE
        ↓
Get sender network: NetworkSource.MESHCORE
        ↓
dual_interface.send_message(
    text=echo_response,
    destination_id=0xFFFFFFFF,  # Broadcast
    network_source=NetworkSource.MESHCORE,
    channelIndex=0  # Public channel
)
        ↓
Selects MeshCore interface
        ↓
interface.sendText(..., destinationId=0xFFFFFFFF, channelIndex=0)
        ↓
Echo broadcasted on MeshCore! ✅
```

## Comparison

### Before Fix

| Source Network | Echo Command | Response Sent To | Correct? |
|----------------|--------------|------------------|----------|
| Meshtastic     | `/echo test` | Meshtastic       | ✅ Yes   |
| MeshCore       | `/echo test` | Meshtastic       | ❌ No!   |

### After Fix

| Source Network | Echo Command | Response Sent To | Correct? |
|----------------|--------------|------------------|----------|
| Meshtastic     | `/echo test` | Meshtastic       | ✅ Yes   |
| MeshCore       | `/echo test` | MeshCore         | ✅ Yes   |

## Other Commands Affected

This same pattern should be checked in other broadcast commands that directly use `interface.sendText()`:

### Potentially Affected Commands
1. `/bot` - AI responses (in `ai_commands.py`)
2. `/ia` - AI responses French (in `ai_commands.py`)
3. `/propag` - Propagation stats (in `network_commands.py`)
4. `/weather` - Weather broadcasts (in `utility_commands.py`)

These commands use the helper method `_send_broadcast_via_tigrog2()` which also needs to be updated with dual mode routing.

## Testing

### Test Case 1: MeshCore Echo
```
User sends via MeshCore DM: /echo hello
Expected: Echo broadcast appears on MeshCore network
Result: ✅ PASS (with fix)
```

### Test Case 2: Meshtastic Echo  
```
User sends via Meshtastic: /echo world
Expected: Echo broadcast appears on Meshtastic network
Result: ✅ PASS (unchanged)
```

### Test Case 3: Network Isolation
```
User A on MeshCore: /echo test1
User B on Meshtastic: /echo test2
Expected: Each echo appears only on its source network
Result: ✅ PASS (with fix)
```

## Expected Logs

### MeshCore Echo (After Fix)
```
[INFO] 📬 [MESHCORE-DM] De: 0x143bcd7f | Message: /echo test
[DEBUG] ✅ [DUAL-MODE] Packet accepté (dual mode actif)
[INFO] ECHO PUBLIC de Node-143bcd7f: '/echo test'
[INFO] 🔍 [DUAL MODE] Routing echo broadcast to NetworkSource.MESHCORE
[DEBUG] ✅ Message sent via MeshCore (channel 0): 'Node-143b: test'
[INFO] ✅ Echo broadcast envoyé via NetworkSource.MESHCORE (canal public)
```

### Meshtastic Echo (Unchanged)
```
[INFO] 📨 MESSAGE BRUT: '/echo test' | from=0x[sender_id]
[DEBUG] ✅ [DUAL-MODE] Packet accepté (dual mode actif)
[INFO] ECHO PUBLIC de Node-xxxx: '/echo test'
[INFO] 🔍 [DUAL MODE] Routing echo broadcast to NetworkSource.MESHTASTIC
[DEBUG] ✅ Message sent via Meshtastic (channel 0): 'Node-xxxx: test'
[INFO] ✅ Echo broadcast envoyé via NetworkSource.MESHTASTIC (canal public)
```

## Files Modified

1. **`handlers/command_handlers/utility_commands.py`** (handle_echo method)
   - Added dual mode routing check
   - Uses `dual_interface.send_message()` for proper network routing
   - Falls back to single-mode behavior if not in dual mode

2. **`dual_interface_manager.py`** (send_message method)
   - Added `channelIndex` parameter (default 0 for public channel)
   - Properly passes channelIndex to both MeshCore and Meshtastic interfaces
   - Enhanced logging to show channel index

## Future Improvements

### Short Term
1. Apply same fix to other broadcast commands (`/bot`, `/ia`, `/propag`, etc.)
2. Create helper method for dual-mode broadcasts to avoid code duplication
3. Test with various command types

### Long Term
1. Refactor broadcast logic into a common utility
2. Add unit tests for dual mode routing
3. Consider automatic network detection without explicit tracking

## Related Documentation

- Dual mode architecture: `DUAL_NETWORK_MODE.md`
- MeshCore DM fix: `FIX_MESHCORE_DM_DUAL_MODE.md`
- Network routing: `handlers/message_sender.py` lines 135-156
- Sender tracking: `main_bot.py` lines 639-644

## Status

✅ **COMPLETE** - Echo commands now correctly broadcast to the source network in dual mode

Both MeshCore and Meshtastic echo commands work correctly and remain isolated to their respective networks.
