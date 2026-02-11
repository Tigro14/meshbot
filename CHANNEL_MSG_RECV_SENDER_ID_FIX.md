# Fix: CHANNEL_MSG_RECV Missing Sender ID

## Problem

When `/echo` command sent on MeshCore public channel, the bot logs showed:

```
[INFO][MC] 📢 [MESHCORE-CHANNEL] Canal public message reçu!
[DEBUG][MC] 📦 [CHANNEL] Payload keys: ['type', 'SNR', 'channel_idx', 'path_len', 'txt_type', 'sender_timestamp', 'text']
[DEBUG][MC] 📋 [CHANNEL] Event attributes: {'channel_idx': 0, 'txt_type': 0}
[DEBUG][MC] ⚠️ [CHANNEL] Sender ID manquant après toutes les tentatives, ignoré
```

**Issue**: CHANNEL_MSG_RECV event doesn't contain sender_id in any accessible location.

## Root Cause

### Duplicate Event Processing

The bot was subscribed to TWO event types that both fire for channel messages:

1. **RX_LOG_DATA** (enabled by default)
   - Fires for ALL RF packets
   - Includes complete packet header info (sender, receiver)
   - Successfully forwards to bot ✅

2. **CHANNEL_MSG_RECV** (newly added)
   - Fires specifically for channel messages
   - Event structure lacks sender identification
   - Cannot process message ❌

**Both events fire for the same message!**

### Why CHANNEL_MSG_RECV Has No Sender ID

The meshcore-cli library's CHANNEL_MSG_RECV event structure:
- `event.__dict__.keys()`: `['type', 'payload', 'attributes']`
- `payload` dict keys: `['type', 'SNR', 'channel_idx', 'path_len', 'txt_type', 'sender_timestamp', 'text']`
- `event.attributes` dict: `{'channel_idx': 0, 'txt_type': 0}`

**None of these contain sender_id!**

Sender information is only available via:
- Packet header parsing (done by RX_LOG)
- CONTACT_MSG_RECV events (for DMs, which do include sender info)

## Solution

### Mutually Exclusive Subscriptions

Don't subscribe to CHANNEL_MSG_RECV when RX_LOG_DATA is enabled:

```python
# Before: Always subscribe to both (causes duplicates)
subscribe(EventType.CONTACT_MSG_RECV)   # DMs
subscribe(EventType.CHANNEL_MSG_RECV)   # Channel messages (no sender_id!)
subscribe(EventType.RX_LOG_DATA)        # All packets (has sender_id)

# After: Conditional subscription
subscribe(EventType.CONTACT_MSG_RECV)   # DMs

if RX_LOG_DATA enabled:
    subscribe(EventType.RX_LOG_DATA)    # Handles ALL packets including channel
else:
    subscribe(EventType.CHANNEL_MSG_RECV)  # Fallback for channel messages
```

### Logic Flow

```
if MESHCORE_RX_LOG_ENABLED (default: True):
    ✅ Subscribe to RX_LOG_DATA
       → Forwards ALL packets (DMs, channel, telemetry, etc.)
       → Has complete packet info (sender, receiver, text)
       → No need for CHANNEL_MSG_RECV
    
else:
    ✅ Subscribe to CHANNEL_MSG_RECV
       → Fallback for channel messages
       → Used when RX_LOG not available/disabled
```

## Implementation

### Changes Made

**File**: `meshcore_cli_wrapper.py`

**Lines 815-877**: Restructured subscription logic

```python
# MeshCore uses 'events' attribute for subscriptions
if hasattr(self.meshcore, 'events'):
    self.meshcore.events.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_message)
    
    # Check if RX_LOG is enabled
    rx_log_enabled = getattr(config, 'MESHCORE_RX_LOG_ENABLED', True)
    
    if rx_log_enabled and hasattr(EventType, 'RX_LOG_DATA'):
        # RX_LOG handles everything - don't need CHANNEL_MSG_RECV
        self.meshcore.events.subscribe(EventType.RX_LOG_DATA, self._on_rx_log_data)
        info_print("→ CHANNEL_MSG_RECV non nécessaire (RX_LOG traite déjà les messages de canal)")
    
    elif not rx_log_enabled:
        # Fallback to CHANNEL_MSG_RECV if RX_LOG disabled
        if hasattr(EventType, 'CHANNEL_MSG_RECV'):
            self.meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_message)
    
    # ... similar logic for dispatcher branch
```

## Benefits

### 1. No Duplicate Processing ✅

Before: Same message processed twice
- RX_LOG_DATA → forwards packet ✅
- CHANNEL_MSG_RECV → can't process (no sender) ❌

After: Single processing path
- RX_LOG_DATA → forwards packet ✅
- No CHANNEL_MSG_RECV subscription

### 2. Complete Packet Information ✅

RX_LOG_DATA provides:
- Sender ID (from packet header)
- Receiver ID (from packet header)
- Message text (from decoded payload)
- SNR, RSSI, hop count, etc.

CHANNEL_MSG_RECV only provides:
- Message text
- Channel index
- SNR (signal strength)
- **NO sender identification**

### 3. Cleaner Architecture ✅

Clear separation of concerns:
- **CONTACT_MSG_RECV**: DM messages (has sender info)
- **RX_LOG_DATA**: ALL packets when enabled (has complete info)
- **CHANNEL_MSG_RECV**: Fallback for channel messages when RX_LOG disabled

### 4. No Error Messages ✅

Before:
```
⚠️ [CHANNEL] Sender ID manquant après toutes les tentatives, ignoré
```

After:
```
✅ Souscription à RX_LOG_DATA (tous les paquets RF)
   → CHANNEL_MSG_RECV non nécessaire (RX_LOG traite déjà les messages de canal)
```

## Expected Behavior

### Scenario 1: RX_LOG Enabled (Default)

**Startup logs:**
```
✅ Souscription aux messages DM (events.subscribe)
✅ Souscription à RX_LOG_DATA (tous les paquets RF)
   → Monitoring actif: broadcasts, télémétrie, DMs, etc.
   → CHANNEL_MSG_RECV non nécessaire (RX_LOG traite déjà les messages de canal)
```

**When /echo sent on public channel:**
```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (56B) - From: 0x1ad711bf → To: 0xa8f69e51
[DEBUG][MC] ➡️  [RX_LOG] Forwarding TEXT_MESSAGE_APP packet to bot callback
[DEBUG][MC]    📦 From: 0x1ad711bf → To: 0xa8f69e51 | Broadcast: False
[DEBUG][MC] ✅ [RX_LOG] Packet forwarded successfully
```
✅ No CHANNEL_MSG_RECV event, no "Sender ID manquant" error

### Scenario 2: RX_LOG Disabled

**Startup logs:**
```
✅ Souscription aux messages DM (events.subscribe)
ℹ️  RX_LOG_DATA désactivé (MESHCORE_RX_LOG_ENABLED=False)
   → Le bot ne verra que les DM, pas les broadcasts
✅ Souscription aux messages de canal public (CHANNEL_MSG_RECV)
   → Le bot peut maintenant traiter les commandes du canal public (ex: /echo)
```

**When /echo sent on public channel:**
```
[INFO][MC] 📢 [MESHCORE-CHANNEL] Canal public message reçu!
[DEBUG][MC] ⚠️ [CHANNEL] Sender ID manquant après toutes les tentatives, ignoré
```
⚠️ Still fails because CHANNEL_MSG_RECV event structure lacks sender_id

**Recommendation**: Keep RX_LOG enabled (default) for proper channel message support.

## Configuration

### Default (Recommended)

```python
# config.py
MESHCORE_RX_LOG_ENABLED = True  # Default
```

Uses RX_LOG_DATA for all packets. Channel messages work correctly.

### Alternative (Limited Functionality)

```python
# config.py
MESHCORE_RX_LOG_ENABLED = False
```

Uses CHANNEL_MSG_RECV but **cannot process channel messages** due to missing sender_id.

## Testing

### Manual Test

1. **Enable RX_LOG (default)**:
   ```bash
   # In config.py: MESHCORE_RX_LOG_ENABLED = True
   sudo systemctl restart meshbot
   ```

2. **Check logs**:
   ```bash
   journalctl -u meshbot | grep "CHANNEL_MSG_RECV"
   # Should see: → CHANNEL_MSG_RECV non nécessaire
   ```

3. **Send /echo on public channel**:
   ```
   Send: /echo test from public channel
   ```

4. **Verify processing**:
   ```bash
   journalctl -u meshbot -f | grep "RX_LOG\|CHANNEL"
   # Should see RX_LOG forwarding, no CHANNEL_MSG_RECV event
   ```

5. **Confirm no errors**:
   ```bash
   journalctl -u meshbot | grep "Sender ID manquant"
   # Should return nothing
   ```

## Summary

**Problem**: CHANNEL_MSG_RECV event lacks sender_id, causing "Sender ID manquant" errors.

**Root Cause**: Duplicate subscription to RX_LOG_DATA + CHANNEL_MSG_RECV for same messages.

**Solution**: Only subscribe to CHANNEL_MSG_RECV when RX_LOG disabled.

**Result**: 
- ✅ No duplicate processing
- ✅ Complete packet information from RX_LOG
- ✅ No sender_id errors
- ✅ Cleaner architecture

**Recommendation**: Keep RX_LOG enabled (default) for full functionality.

---

**Status**: ✅ Fixed  
**Date**: 2026-02-11  
**PR**: copilot/add-echo-command-listener
