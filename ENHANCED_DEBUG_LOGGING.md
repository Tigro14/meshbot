# Enhanced Debug Logging for Public Key Extraction

## Issue

With firmware 2.7.15 confirmed on all nodes, but still 0 public keys detected after 24h, we need comprehensive logging to diagnose why keys aren't being extracted.

## Enhanced Logging Added

### 1. NODEINFO Packet Reception (ALWAYS LOGGED)

Every time a NODEINFO packet is received, the bot now logs:

```
📋 NODEINFO received from NodeName (0x12345678):
   Fields in packet: ['id', 'longName', 'shortName', 'hwModel', 'public_key']
   Has 'public_key' field: True
   Has 'publicKey' field: False
   public_key value type: bytes, length: 32
   public_key preview: b'\x01\x02\x03\x04...'
   Extracted public_key: YES
```

**What to look for:**
- Does the packet have `public_key` field? (Should be True for firmware 2.7.15)
- What is the value type? (Should be `bytes`)
- What is the length? (Should be 32 bytes for valid key)
- Is it being extracted? (Should show YES)

### 2. Key Storage (ALWAYS LOGGED)

When a key is extracted and stored:

```
📱 New node added: NodeName (0x12345678)
✅ Public key EXTRACTED and STORED for NodeName
   Key type: bytes, length: 32
```

Or if key is missing:

```
📱 New node added: NodeName (0x12345678)
❌ NO public key for NodeName - DM decryption will NOT work
```

For existing nodes being updated:

```
✅ Public key UPDATED for NodeName
   Key type: bytes, length: 32
```

Or if still no key:

```
⚠️ Still NO public key for NodeName after NODEINFO update
```

### 3. Key Synchronization to interface.nodes (ALWAYS LOGGED)

When `sync_pubkeys_to_interface()` is called (at startup and every 5 min):

```
🔄 Starting public key synchronization to interface.nodes...
   Current interface.nodes count: 15
   Keys to sync from node_names: 10
   Processing NodeName (0x12345678): has key in DB
      Found in interface.nodes with key: 305419896
      ✅ Injected key into existing node
   Processing NodeName2 (0x87654321): has key in DB
      Not in interface.nodes yet - creating entry
      ✅ Created node in interface.nodes with key
✅ SYNC COMPLETE: 10 public keys synchronized to interface.nodes
```

**What to look for:**
- How many keys are in `node_names.json`?
- How many nodes are in `interface.nodes`?
- Are keys being found and injected?
- Are new nodes being created with keys?

## Diagnosis Scenarios

### Scenario 1: Keys in Packets but Not Extracted

**Logs show:**
```
📋 NODEINFO received from NodeName (0x12345678):
   Has 'public_key' field: True
   public_key value type: bytes, length: 32
   Extracted public_key: NO
```

**Problem:** Extraction logic is failing despite field being present
**Action:** Check if both field values are empty/None

### Scenario 2: Keys Extracted but Not Stored

**Logs show:**
```
📋 NODEINFO received from NodeName (0x12345678):
   Extracted public_key: YES
📱 New node added: NodeName (0x12345678)
❌ NO public key for NodeName
```

**Problem:** Key is lost between extraction and storage
**Action:** Check the storage logic in node_names assignment

### Scenario 3: Keys Stored but Not Synced

**Logs show:**
```
✅ Public key EXTRACTED and STORED for NodeName
...later...
🔄 Starting public key synchronization to interface.nodes...
   Keys to sync from node_names: 0
```

**Problem:** Keys not persisting to `node_names.json` or not loading
**Action:** Check file save/load operations

### Scenario 4: Keys Empty Despite Field Present

**Logs show:**
```
📋 NODEINFO received from NodeName (0x12345678):
   Has 'public_key' field: True
   public_key value type: NoneType, length: 0
   Extracted public_key: NO
```

**Problem:** Field exists but is empty - PKI might be disabled
**Action:** Check node settings for PKI enabled

### Scenario 5: Wrong Field Name

**Logs show:**
```
📋 NODEINFO received from NodeName (0x12345678):
   Fields in packet: ['id', 'longName', 'shortName', 'publicKey']
   Has 'public_key' field: False
   Has 'publicKey' field: True
```

**Problem:** Using camelCase instead of snake_case
**Action:** Code already handles both, but confirms field naming

## Expected Behavior (Success)

With firmware 2.7.15, you should see:

```
📋 NODEINFO received from Node1 (0x12345678):
   Fields in packet: ['id', 'longName', 'shortName', 'hwModel', 'public_key']
   Has 'public_key' field: True
   public_key value type: bytes, length: 32
   public_key preview: b'\x04\x89\x3a\x2f...'
   Extracted public_key: YES

📱 New node added: Node1 (0x12345678)
✅ Public key EXTRACTED and STORED for Node1
   Key type: bytes, length: 32

... (more nodes) ...

🔄 Starting public key synchronization to interface.nodes...
   Current interface.nodes count: 147
   Keys to sync from node_names: 145
   Processing Node1 (0x12345678): has key in DB
      Found in interface.nodes with key: 305419896
      ✅ Injected key into existing node
   ... (more nodes) ...
✅ SYNC COMPLETE: 145 public keys synchronized to interface.nodes
```

## How to Use These Logs

1. **Restart the bot** to get fresh logs
2. **Wait for NODEINFO packets** (or request them manually)
3. **Search logs** for:
   - "📋 NODEINFO received" - Shows packet structure
   - "✅ Public key EXTRACTED" - Confirms extraction
   - "🔄 Starting public key synchronization" - Shows sync process
4. **Count successes vs failures**:
   - How many show "Extracted public_key: YES"?
   - How many show "✅ Public key EXTRACTED and STORED"?
   - How many keys synced to interface.nodes?

## Common Issues to Identify

| Log Pattern | Issue | Solution |
|-------------|-------|----------|
| No "NODEINFO received" logs | No packets arriving | Check mesh connectivity |
| "Has 'public_key' field: False" | Old firmware | Upgrade to 2.5.0+ |
| "public_key value type: NoneType" | PKI disabled | Enable PKI in settings |
| "Extracted: YES" but "NO public key stored" | Storage bug | Report with logs |
| "Keys to sync: 0" after extraction | Save/load bug | Check node_names.json |
| Sync starts but "0 nodes processed" | Key format issue | Check node_id formats |

## Next Steps

After enabling these logs:
1. Collect 30 minutes of logs
2. Count how many NODEINFO packets received
3. Count how many keys extracted
4. Count how many keys stored
5. Count how many keys synced
6. Report any discrepancies

---

**All logging uses `info_print()` so it's ALWAYS visible, not just in DEBUG_MODE.**
