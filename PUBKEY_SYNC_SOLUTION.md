# Public Key Synchronization for DM Decryption

**Date**: 2025-12-25  
**Problem**: Need public keys from TCP node for DM decryption while respecting ESP32 single-connection limitation

## The Problem

In Meshtastic 2.5.0+, Direct Messages (DMs) are encrypted using PKI (Public Key Infrastructure):
- Each node has a unique public/private key pair
- Sender encrypts DM with recipient's public key  
- Only recipient can decrypt with their private key

The Meshtastic Python library automatically decrypts PKI DMs **IF** it has the sender's public key in `interface.nodes[sender_id]['user']['publicKey']`.

### The Challenge in TCP Mode

1. **Serial Mode**: Library loads node database from disk at startup → `interface.nodes` populated immediately with all keys
2. **TCP Mode**: `interface.nodes` starts **empty**, only populates as NODEINFO packets arrive (15-30 min per node)
3. **ESP32 Limitation**: Only **ONE TCP connection** allowed at a time
4. **Cannot Query**: Cannot create a 2nd TCP connection to fetch keys from remote node's database (would kill main bot connection)

## The Solution

Extract and persist public keys from NODEINFO packets, then inject them into `interface.nodes`:

```
┌─────────────────────────────────────────────────────────────────┐
│                  NODEINFO Packet Flow                           │
└─────────────────────────────────────────────────────────────────┘

    Mesh Network → NODEINFO_APP packet → Bot receives
                       │
                       ▼
            ┌──────────────────────┐
            │ node_manager.py      │
            │ update_node_from_    │
            │ packet()             │
            └──────────┬───────────┘
                       │
                       │ Extract publicKey from packet['decoded']['user']
                       ▼
            ┌──────────────────────┐
            │ node_names.json      │
            │ {                    │
            │   "node_id": {       │
            │     "name": "...",   │
            │     "publicKey": "..." ← Persisted!
            │   }                  │
            │ }                    │
            └──────────┬───────────┘
                       │
                       │ At startup + every 5 min
                       ▼
            ┌──────────────────────┐
            │ sync_pubkeys_to_     │
            │ interface()          │
            └──────────┬───────────┘
                       │
                       │ Inject keys into interface.nodes
                       ▼
            ┌──────────────────────┐
            │ interface.nodes      │
            │ {                    │
            │   node_id: {         │
            │     'user': {        │
            │       'publicKey': "..." ← Available for DM decryption!
            │     }                │
            │   }                  │
            │ }                    │
            └──────────────────────┘
                       │
                       │ Meshtastic library can now decrypt DMs
                       ▼
            ✅ DM Decryption Works!
```

## Implementation

### 1. Extract Public Keys from NODEINFO Packets

**File**: `node_manager.py`

```python
def update_node_from_packet(self, packet):
    """Extract and persist public keys from NODEINFO_APP packets"""
    if 'decoded' in packet and packet['decoded'].get('portnum') == 'NODEINFO_APP':
        node_id = packet.get('from')
        user_info = packet['decoded']['user']
        
        # Extract public key if present
        public_key = user_info.get('publicKey')
        
        # Store in persistent database
        self.node_names[node_id] = {
            'name': name,
            'publicKey': public_key,  # ← Persisted!
            # ... other fields
        }
```

### 2. Inject Keys into interface.nodes

**File**: `node_manager.py`

```python
def sync_pubkeys_to_interface(self, interface):
    """
    Synchronize public keys from node_names.json to interface.nodes
    
    This enables DM decryption in TCP mode without violating
    ESP32 single-connection limitation.
    """
    injected_count = 0
    nodes = getattr(interface, 'nodes', {})
    
    for node_id, node_data in self.node_names.items():
        public_key = node_data.get('publicKey')
        if not public_key:
            continue
        
        # Try to find node in interface.nodes
        if node_id in nodes:
            # Node exists → inject key
            nodes[node_id]['user']['publicKey'] = public_key
        else:
            # Node doesn't exist → create entry with key
            nodes[node_id] = {
                'num': node_id,
                'user': {
                    'id': f"!{node_id:08x}",
                    'longName': node_data['name'],
                    'publicKey': public_key  # ← Injected!
                }
            }
        injected_count += 1
    
    return injected_count
```

### 3. Call Sync at Startup and Periodically

**File**: `main_bot.py`

```python
def start(self):
    # ... interface creation ...
    
    # Synchronize public keys at startup
    self.node_manager.sync_pubkeys_to_interface(self.interface)
    # ✅ Now interface.nodes has all known keys

def cleanup_cache(self):
    # Synchronize every 5 minutes (in periodic cleanup)
    self.node_manager.sync_pubkeys_to_interface(self.interface)
    # ✅ New keys from NODEINFO packets are continuously injected
```

## Benefits

1. ✅ **Respects ESP32 Limitation**: No additional TCP connections created
2. ✅ **Persistent**: Keys survive bot restarts
3. ✅ **Automatic**: Extracts keys from NODEINFO packets passively
4. ✅ **Immediate**: Keys available at startup (not 15-30 min wait)
5. ✅ **Continuous**: New keys injected every 5 minutes
6. ✅ **DM Decryption**: Meshtastic library can now decrypt DMs

## Comparison: Before vs After

### Before (TCP Mode)

```
Bot starts → interface.nodes = {}  (empty!)
Wait 15-30 min → NODEINFO arrives → interface.nodes populated
DMs received before NODEINFO → appear as ENCRYPTED
```

**Result**: DM decryption fails for first 15-30 minutes

### After (TCP Mode)

```
Bot starts → Load node_names.json → inject keys → interface.nodes populated ✓
DMs received immediately → library has keys → decryption works ✓
NODEINFO arrives → keys updated → even better coverage ✓
```

**Result**: DM decryption works immediately

## Testing

Run test suite:
```bash
python3 test_pubkey_sync.py
```

Expected output:
```
✅ TEST 1: Public Key Extraction from NODEINFO Packets
✅ TEST 2: Public Key Update on Change
✅ TEST 3: Public Key Injection to Interface.nodes
✅ TEST 4: Public Key Update for Existing Interface Node
✅ TEST 6: ESP32 Single Connection Compliance
```

## Files Modified

1. **node_manager.py**
   - Extract `publicKey` from NODEINFO packets
   - Store in `node_names[node_id]['publicKey']`
   - Added `sync_pubkeys_to_interface()` method
   - Update keys when they change

2. **main_bot.py**
   - Call `sync_pubkeys_to_interface()` at startup
   - Call `sync_pubkeys_to_interface()` every 5 min in `cleanup_cache()`

3. **test_pubkey_sync.py** (NEW)
   - Comprehensive test suite
   - Validates all aspects of the solution

## Future Enhancements

1. **Key Expiration**: Optionally expire keys after N days
2. **Key Verification**: Validate key format before injection
3. **Statistics**: Track key injection/update counts
4. **Alert on Missing Keys**: Notify when encrypted DM received but no key available

## References

- **TCP_PKI_KEYS_LIMITATION.md** - Original problem documentation
- **DM_DECRYPTION_2715.md** - Meshtastic PKI encryption details
- **TCP_SINGLE_CONNECTION_REFACTOR.md** - ESP32 single-connection architecture

---

**Status**: ✅ Implemented and Tested  
**Version**: 1.0  
**Last Updated**: 2025-12-25
