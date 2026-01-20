# Contact Message (DM) Handling Fix

## Problem Statement

When users send direct messages (DMs) via MeshCore contact messages, the bot does not respond to commands like `/help`. The logs show:

```
Jan 20 16:06:42 DietPi meshtastic-bot[37041]: [DEBUG] 🔔 [MESHCORE-CLI] Event reçu: Event(type=<EventType.CONTACT_MSG_RECV: 'contact_message'>, payload={'type': 'PRIV', 'SNR': 12.5, 'pubkey_prefix': '143bcd7f1b1f', 'path_len': 1, 'txt_type': 0, 'sender_timestamp': 1768925194, 'text': 'Test'}, attributes={'pubkey_prefix': '143bcd7f1b1f', 'txt_type': 0})
Jan 20 16:06:42 DietPi meshtastic-bot[37041]: [DEBUG] 📦 [MESHCORE-CLI] Payload: {'type': 'PRIV', 'SNR': 12.5, 'pubkey_prefix': '143bcd7f1b1f', 'path_len': 1, 'txt_type': 0, 'sender_timestamp': 1768925194, 'text': 'Test'}
Jan 20 16:06:42 DietPi meshtastic-bot[37041]: [INFO] 📬 [MESHCORE-DM] De: 143bcd7f1b1f | Message: Test
Jan 20 16:06:42 DietPi meshtastic-bot[37041]: [DEBUG] 🔍 Interface était None, utilisation de self.interface
Jan 20 16:06:42 DietPi meshtastic-bot[37041]: [INFO] 📨 MESSAGE BRUT: 'Test' | from=0xffffffff | to=0xffffffff | broadcast=True
```

**Key Issue**: The message is logged as `from=0xffffffff | to=0xffffffff | broadcast=True`, which causes it to be filtered as a broadcast and never processed.

## Root Cause Analysis

### 1. Missing sender_id in MeshCore Events

The MeshCore contact message event only provides:
- `pubkey_prefix`: String prefix of the sender's public key (e.g., '143bcd7f1b1f')
- `text`: Message content
- **NO** `sender_id` or `contact_id` field

### 2. Fallback to Broadcast Address

In `meshcore_cli_wrapper.py::_on_contact_message()`:
```python
# Old code (lines 364-398)
sender_id = payload.get('contact_id') or payload.get('sender_id')
# ... more attempts to find sender_id ...

# If sender_id is None, fallback to broadcast
packet = {
    'from': sender_id if sender_id is not None else 0xFFFFFFFF,
    'to': self.localNode.nodeNum,
    ...
}
```

This creates a packet with `from=0xFFFFFFFF`, which is the broadcast address.

### 3. Broadcast Filtering in on_message()

In `main_bot.py::on_message()` (line 546):
```python
is_broadcast = (to_id in [0xFFFFFFFF, 0])

if is_broadcast:
    if self._is_recent_broadcast(message):
        # Skip processing
        return
```

Since `to_id=0xFFFFFFFF`, the message is treated as a broadcast and filtered, preventing command execution.

## Solution Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│  MeshCore Event                                             │
│  pubkey_prefix: '143bcd7f1b1f'                              │
│  text: '/help'                                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  meshcore_cli_wrapper._on_contact_message()                 │
│  1. Extract pubkey_prefix                                   │
│  2. Lookup node_id via NodeManager                          │
│  3. Create DM packet with:                                  │
│     - from: resolved_node_id (or 0xFFFFFFFF)                │
│     - to: local_node_id (NOT broadcast)                     │
│     - _meshcore_dm: True (flag for special handling)        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  main_bot.on_message()                                      │
│  1. Check _meshcore_dm flag                                 │
│  2. Override broadcast detection:                           │
│     is_broadcast = (to_id == 0xFFFFFFFF) and NOT dm_flag    │
│  3. Process command normally                                │
└─────────────────────────────────────────────────────────────┘
```

### Component Changes

#### 1. NodeManager.find_node_by_pubkey_prefix()

**File**: `node_manager.py`  
**Purpose**: Lookup node_id by matching public key prefix

```python
def find_node_by_pubkey_prefix(self, pubkey_prefix):
    """
    Find a node ID by matching the public key prefix
    
    Args:
        pubkey_prefix: Hex string prefix of the public key
        
    Returns:
        int: node_id if found, None otherwise
    """
    if not pubkey_prefix:
        return None
    
    pubkey_prefix = str(pubkey_prefix).lower().strip()
    
    for node_id, node_data in self.node_names.items():
        if 'publicKey' in node_data:
            public_key = node_data['publicKey']
            
            # Handle both string and bytes formats
            if isinstance(public_key, str):
                if public_key.lower().startswith(pubkey_prefix):
                    return node_id
            elif isinstance(public_key, bytes):
                public_key_hex = public_key.hex().lower()
                if public_key_hex.startswith(pubkey_prefix):
                    return node_id
    
    return None
```

**Features**:
- Case insensitive matching
- Supports both string and bytes publicKey formats
- Returns node_id or None if not found

#### 2. MeshCoreCLIWrapper._on_contact_message()

**File**: `meshcore_cli_wrapper.py`  
**Changes**: Enhanced to lookup sender by pubkey_prefix

```python
def _on_contact_message(self, event):
    # Extract sender_id from multiple sources
    sender_id = None
    pubkey_prefix = None
    
    if isinstance(payload, dict):
        sender_id = payload.get('contact_id') or payload.get('sender_id')
        pubkey_prefix = payload.get('pubkey_prefix')
    
    # NEW: If sender_id is None, try pubkey lookup
    if sender_id is None and pubkey_prefix and self.node_manager:
        sender_id = self.node_manager.find_node_by_pubkey_prefix(pubkey_prefix)
        if sender_id:
            info_print(f"✅ [MESHCORE-DM] Resolved {pubkey_prefix} → 0x{sender_id:08x}")
    
    # Create packet with proper DM structure
    if sender_id is None:
        sender_id = 0xFFFFFFFF
        to_id = self.localNode.nodeNum  # DM to us
    else:
        to_id = self.localNode.nodeNum  # DM to us
    
    packet = {
        'from': sender_id,
        'to': to_id,  # NOT broadcast (0xFFFFFFFF)
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': text.encode('utf-8')
        },
        '_meshcore_dm': True  # NEW: Mark as DM
    }
```

**Key Points**:
- Attempts to resolve sender_id by pubkey_prefix
- Sets `to` field to local node (not broadcast)
- Adds `_meshcore_dm` flag for special handling

#### 3. MeshCoreCLIWrapper.set_node_manager()

**File**: `meshcore_cli_wrapper.py`  
**Purpose**: Inject NodeManager for pubkey lookups

```python
def set_node_manager(self, node_manager):
    """
    Set the node manager for pubkey lookups
    
    Args:
        node_manager: NodeManager instance
    """
    self.node_manager = node_manager
```

Called from `main_bot.py` after interface creation:
```python
# Configure node_manager for pubkey lookups
if hasattr(self.interface, 'set_node_manager'):
    self.interface.set_node_manager(self.node_manager)
```

#### 4. MeshBot.on_message()

**File**: `main_bot.py`  
**Changes**: Updated broadcast detection

```python
# Check if this is a MeshCore DM (marked by wrapper)
is_meshcore_dm = packet.get('_meshcore_dm', False)

# Broadcast detection with DM override
# OLD: is_broadcast = (to_id in [0xFFFFFFFF, 0])
# NEW:
is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
```

**Effect**: DMs marked with `_meshcore_dm` flag are NOT treated as broadcasts, even if sender is 0xFFFFFFFF.

## Testing

### Test Suite: test_contact_message_fix.py

Comprehensive test suite covering:

1. **Pubkey Prefix Lookup**
   - Exact prefix match
   - Case insensitive matching
   - Shorter prefix matching
   - Non-existent prefix handling
   - Bytes format publicKey

2. **DM Packet Structure**
   - DM with resolved sender_id
   - DM with unresolved sender (fallback)

3. **Broadcast Detection**
   - Regular broadcasts
   - MeshCore DMs
   - Direct messages

4. **Event Parsing**
   - Extract pubkey_prefix
   - Extract text
   - Handle missing sender_id

**Run Tests**:
```bash
python3 test_contact_message_fix.py
```

**Expected Output**:
```
✅ ALL TESTS PASSED!
```

### Demo Script: demo_contact_message_fix.py

Educational demo showing:
- Problem before fix
- Solution after fix
- Edge cases (unknown sender)
- Implementation details

**Run Demo**:
```bash
python3 demo_contact_message_fix.py
```

## Edge Cases

### 1. Unknown Sender (Pubkey Not in Database)

If the pubkey_prefix is not found in the node database:
- sender_id remains 0xFFFFFFFF
- Packet is still marked with `_meshcore_dm=True`
- NOT treated as broadcast (flag overrides broadcast check)
- Command is processed normally

**Result**: Unknown senders can still send commands.

### 2. Node Database Not Synced

If NodeManager doesn't have the sender's publicKey:
- Lookup fails gracefully
- Falls back to 0xFFFFFFFF
- DM flag ensures processing continues
- User can still interact with bot

### 3. Backwards Compatibility

- Old packets without `_meshcore_dm` flag work as before
- Regular broadcasts are still filtered
- Direct messages to local node work as before
- Only MeshCore DMs get special handling

## Verification Checklist

- [x] Code changes implemented
- [x] Test suite passes
- [x] Demo script works
- [x] Edge cases handled
- [x] Documentation complete
- [ ] Real hardware testing (needs user with MeshCore device)

## Expected Behavior After Fix

### Before Fix
```
User sends: /help via DM
Bot logs:    from=0xffffffff, to=0xffffffff, broadcast=True
Bot action:  Filters as broadcast, no response
User sees:   Nothing
```

### After Fix
```
User sends: /help via DM
Bot logs:    [MESHCORE-DM] Resolved pubkey → 0x0de3331e
             from=0x0de3331e, to=0xaabbccdd, _meshcore_dm=True
             is_broadcast=False
Bot action:  Processes /help command
User sees:   Help text response
```

## Files Modified

1. `node_manager.py` - Added `find_node_by_pubkey_prefix()` method
2. `meshcore_cli_wrapper.py` - Enhanced `_on_contact_message()` with pubkey lookup
3. `main_bot.py` - Updated broadcast detection to handle DM flag

## New Files

1. `test_contact_message_fix.py` - Comprehensive test suite
2. `demo_contact_message_fix.py` - Educational demo script
3. `CONTACT_MESSAGE_FIX.md` - This documentation

## Performance Impact

- **Pubkey Lookup**: O(n) search through node database
  - Typically < 100 nodes, negligible impact
  - Only triggered for contact messages (rare)
  - Cached in node database

- **Memory**: One additional flag per DM packet (`_meshcore_dm`)
  - Boolean flag, minimal overhead

- **Processing**: No additional processing for non-DM messages

## Security Considerations

### Public Key Privacy

- Only pubkey_prefix (first ~12 chars) is logged
- Full public keys remain in node database
- No additional exposure beyond existing NODEINFO packets

### Unknown Sender Handling

- Unknown senders can send commands (by design)
- Rate limiting and throttling still apply
- Admin commands require authorization (unchanged)

### Broadcast Deduplication

- Regular broadcasts still deduplicated
- Only MeshCore DMs bypass broadcast filtering
- No risk of broadcast loops

## Future Enhancements

1. **Pubkey Cache**: Cache pubkey → node_id mappings for faster lookup
2. **Fuzzy Matching**: Handle pubkey variations or truncated prefixes
3. **Contact Sync**: Automatically sync contacts from MeshCore
4. **Sender Validation**: Verify sender's public key against known nodes

## References

- Issue: "Contact messages not processed"
- Related: MeshCore companion mode (meshcore-cli library)
- Related: DM decryption (Meshtastic 2.7.15+)

## Author

GitHub Copilot Workspace Agent  
Date: 2025-01-20  
Branch: copilot/add-contact-message-receive-again
