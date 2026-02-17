# Public Key Logging Reduction - Visual Comparison

## Problem Statement

The bot was generating 6+ log lines for every public key operation, making logs difficult to read in production.

### Example Log Output (BEFORE)

```
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [DEBUG]    publicKey preview: JxdQ5cMb3gTCwdcTARFR
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [INFO] ✅ Public key UPDATED for Dalle
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [INFO]    Key type: str, length: 44
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [DEBUG]    🔑 Immediately synced key to interface.nodes for Dalle
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [INFO] ✓ Node Dalle now has publicKey in DB (len=44)
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [DEBUG] ✅ Nœud Meshtastic sauvegardé: Dalle (0x33690e68)
```

**Issues:**
- ❌ 6 lines per operation
- ❌ No source prefix (can't distinguish MeshCore vs Meshtastic)
- ❌ Repetitive information
- ❌ Mixed INFO and DEBUG levels without clear hierarchy

---

## Solution Implemented

### Log Output (AFTER)

#### Meshtastic Source
```
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [INFO][MT] ✅ Key updated: Dalle (len=44)
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [DEBUG][MT] 🔑 Key synced: Dalle → interface.nodes
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [DEBUG][MT] 💾 Node saved: Dalle (0x33690e68)
```

#### MeshCore Source
```
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [INFO][MC] ✅ Key updated: MeshCoreNode (len=44)
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [DEBUG][MC] 🔑 Key synced: MeshCoreNode → interface.nodes
Feb 17 23:37:44 DietPi meshtastic-bot[21999]: [DEBUG][MC] 💾 Node saved: MeshCoreNode (0x33690e68)
```

**Benefits:**
- ✅ 2-3 lines per operation (67% reduction)
- ✅ Clear [MC]/[MT] source prefixes
- ✅ Essential information preserved
- ✅ Clean separation: INFO for key changes, DEBUG for implementation details

---

## Technical Changes

### 1. Source Parameter Threading

**File: `node_manager.py`**

```python
# OLD
def update_node_from_packet(self, packet):
    ...

# NEW
def update_node_from_packet(self, packet, source='meshtastic'):
    """
    Args:
        packet: Packet reçu
        source: Source du packet ('meshtastic', 'meshcore', 'tcp', 'local')
    """
    ...
```

**File: `main_bot.py`**

```python
# OLD
self.node_manager.update_node_from_packet(packet)

# NEW
self.node_manager.update_node_from_packet(packet, source=source)
```

### 2. Helper Method for Logging

**File: `node_manager.py`**

```python
def _get_log_funcs(self, source):
    """Get appropriate logging functions based on source
    
    Returns:
        tuple: (debug_func, info_func)
    """
    if source == 'meshcore':
        return debug_print_mc, info_print_mc
    else:
        # Default to MT for meshtastic, tcp, local, etc.
        return debug_print_mt, info_print_mt
```

### 3. Consolidated Logging

**File: `node_manager.py`**

```python
# Get appropriate log functions
debug_func, info_func = self._get_log_funcs(source)

# OLD (6 lines)
debug_print(f"   publicKey preview: {pk_value[:20]}")
info_print(f"✅ Public key UPDATED for {name}")
info_print(f"   Key type: {type(public_key).__name__}, length: {len(public_key)}")
debug_print(f"   🔑 Immediately synced key to interface.nodes for {node_name}")
info_print(f"✓ Node {name} now has publicKey in DB (len={len(final_key)})")
debug_print(f"✅ Nœud Meshtastic sauvegardé: {name} (0x{node_id:08x})")

# NEW (2-3 lines)
info_func(f"✅ Key updated: {name} (len={len(public_key)})")
debug_func(f"🔑 Key synced: {node_name} → interface.nodes")
debug_func(f"💾 Node saved: {name} (0x{node_id:08x})")
```

### 4. Persistence Layer

**File: `traffic_persistence.py`**

```python
# OLD
def save_meshtastic_node(self, node_data):
    ...
    debug_print(f"✅ Nœud Meshtastic sauvegardé: {node_data.get('name')}")

# NEW
def save_meshtastic_node(self, node_data, source='meshtastic'):
    ...
    debug_func = debug_print_mc if source == 'meshcore' else debug_print_mt
    debug_func(f"💾 Node saved: {node_data.get('name')} (0x{node_data['node_id']:08x})")
```

---

## Comparison Table

| Aspect | Before | After | Improvement |
|--------|--------|-------|-------------|
| Lines per operation | 6+ | 2-3 | 67% reduction |
| Source identification | ❌ None | ✅ [MC]/[MT] | Clear |
| Information density | Low (repeated) | High (factorized) | Better |
| Debug mode impact | Always visible | DEBUG only | Cleaner |
| Maintainability | Scattered logs | Centralized | Easier |

---

## Files Modified

1. **node_manager.py** (60 lines changed)
   - Added `source` parameter to `update_node_from_packet()`
   - Added `_get_log_funcs()` helper method
   - Consolidated 6+ log statements into 2-3
   - Pass source to `_sync_single_pubkey_to_interface()`
   - Pass source to persistence layer

2. **traffic_persistence.py** (25 lines changed)
   - Added `source` parameter to `save_meshtastic_node()`
   - Use source-aware debug function
   - Simplified log message

3. **main_bot.py** (1 line changed)
   - Pass `source` parameter to `update_node_from_packet()`

---

## Testing

Run the demo:
```bash
python3 demos/demo_pubkey_logging_reduction.py
```

The demo shows:
- Expected log output for both Meshtastic and MeshCore sources
- Side-by-side comparison with old logs
- Benefits and summary of changes

---

## Migration Notes

**Backward Compatibility:**
- ✅ Source parameter has default value `'meshtastic'`
- ✅ Existing code works without changes
- ✅ No breaking changes to public APIs

**Deployment:**
- No configuration changes required
- Logs will be cleaner immediately after deployment
- DEBUG mode still shows all details

---

## Related Issues

- Original request: "Factorize and remove all the pubkey debug in far less lines"
- Also addresses: "Add correct [MC] or [MT] prefix according to source"
