# Public Key Sync - Visual Flow Diagram

## Problem: ESP32 Single TCP Connection Limitation

```
┌─────────────────────────────────────────────────────────────┐
│                   ❌ OLD APPROACH (Doesn't Work)            │
└─────────────────────────────────────────────────────────────┘

    Bot (Connection 1)                Remote Node Database
    TCP: 192.168.1.38:4403           (Has all public keys)
         │                                    │
         │                                    │
         ├──── Main connection (traffic) ────┤
         │                                    │
         │                                    │
         └──── Query keys? (Connection 2) ───┤
                        ❌                    │
                   REJECTED!                 │
               ESP32 allows only             │
               1 connection at a time!       │
                                              │
    Result: ❌ Can't get keys              │
            ❌ DM decryption fails          │


┌─────────────────────────────────────────────────────────────┐
│              ✅ NEW APPROACH (Works!)                        │
└─────────────────────────────────────────────────────────────┘

    Bot (Single Connection)          Mesh Network
    TCP: 192.168.1.38:4403
         │
         │ ┌────────────────────────────────────┐
         ├─┤ 1. Passive collection             │
         │ │    NODEINFO packets arrive        │
         │ │    containing publicKey           │
         │ └────────────────────────────────────┘
         │          │
         │          ▼
         │    ┌──────────────────────────────┐
         │    │ 2. Extract publicKey from    │
         │    │    packet['decoded']['user'] │
         │    └──────────────────────────────┘
         │          │
         │          ▼
         │    ┌──────────────────────────────┐
         │    │ 3. Store in node_names.json  │
         │    │    {                         │
         │    │      "node_id": {            │
         │    │        "name": "Node1",      │
         │    │        "publicKey": "..."    │
         │    │      }                        │
         │    │    }                         │
         │    └──────────────────────────────┘
         │          │
         │          ▼
         │    ┌──────────────────────────────┐
         │    │ 4. Inject into interface.nodes│
         │    │    at startup + every 5 min  │
         │    └──────────────────────────────┘
         │          │
         │          ▼
         │    ┌──────────────────────────────┐
         │    │ interface.nodes[node_id] =   │
         │    │   {'user': {                 │
         │    │     'publicKey': '...'  ✓   │
         │    │   }}                         │
         │    └──────────────────────────────┘
         │          │
         │          ▼
         │    ┌──────────────────────────────┐
         │    │ 5. Meshtastic library        │
         │    │    decrypts DMs with key! ✓ │
         │    └──────────────────────────────┘
         │
    Result: ✅ Keys available
            ✅ DM decryption works
            ✅ Single connection only
```

## Timeline Comparison

### Without Public Key Sync (TCP Mode)

```
Time    0min          15min         30min         45min
        │              │             │             │
        ▼              ▼             ▼             ▼
   Bot starts    NODEINFO     NODEINFO      NODEINFO
interface.nodes  arrives      arrives       arrives
= {} (EMPTY)    Node1 key    Node2 key     Node3 key
   │             added        added         added
   ▼             │            │             │
❌ DM from Node1  ▼            ▼             ▼
   ENCRYPTED!   ✅ DM from   ✅ DM from    ✅ DM from
                Node1 works  Node2 works   Node3 works

❌ 15-30 min delay before DM decryption works
```

### With Public Key Sync (TCP Mode)

```
Time    0min         5min        10min       15min
        │             │           │           │
        ▼             ▼           ▼           ▼
   Bot starts   Periodic    Periodic    NODEINFO
Load node_names  sync        sync       arrives
→ inject keys   (update)    (update)   (new key)
   │             │           │          │
   ▼             ▼           ▼          ▼
✅ DM from      ✅ DM from  ✅ DM from  ✅ All DMs
   Node1 works     any node    any node   work!

✅ Immediate DM decryption from startup
```

## Data Flow: NODEINFO → Storage → Injection

```
┌──────────────────────────────────────────────────────────────┐
│  Step 1: NODEINFO Packet Received                           │
└──────────────────────────────────────────────────────────────┘

    Mesh Network
         │
         │ NODEINFO_APP packet
         │ {
         │   'from': 0x16fad3dc,
         │   'decoded': {
         │     'portnum': 'NODEINFO_APP',
         │     'user': {
         │       'longName': 'tigro',
         │       'publicKey': 'ABC123XYZ789...' ← Extract this!
         │     }
         │   }
         │ }
         ▼
    node_manager.py
    update_node_from_packet()


┌──────────────────────────────────────────────────────────────┐
│  Step 2: Extract and Store in JSON                          │
└──────────────────────────────────────────────────────────────┘

    node_manager.py
         │
         │ Extract publicKey
         │ Store in self.node_names
         ▼
    node_names.json
    {
      "383787996": {              ← node_id (0x16fad3dc in decimal)
        "name": "tigro",
        "shortName": "tigro",
        "hwModel": "T1000E",
        "publicKey": "ABC123XYZ789...",  ← Persisted!
        "lat": 47.123,
        "lon": 6.456
      }
    }


┌──────────────────────────────────────────────────────────────┐
│  Step 3: Inject into interface.nodes                        │
└──────────────────────────────────────────────────────────────┘

    main_bot.py
    sync_pubkeys_to_interface()
         │
         │ Read node_names.json
         │ Inject keys into interface.nodes
         ▼
    interface.nodes
    {
      383787996: {
        'num': 383787996,
        'user': {
          'id': '!16fad3dc',
          'longName': 'tigro',
          'publicKey': 'ABC123XYZ789...'  ← Available for DM decryption!
        }
      }
    }


┌──────────────────────────────────────────────────────────────┐
│  Step 4: Meshtastic Library Decrypts DMs                    │
└──────────────────────────────────────────────────────────────┘

    Encrypted DM arrives
         │
         │ from: 0x16fad3dc (tigro)
         │ to: our_node_id
         │ encrypted: true
         ▼
    Meshtastic library checks:
    interface.nodes[0x16fad3dc]['user']['publicKey']
         │
         ✓ Key found!
         │
         ▼
    Decrypt with PKI
         │
         ▼
    packet['decoded']['text'] = "/help"  ✓
         │
         ▼
    Bot processes command!  ✓
```

## Key Points

1. **No new TCP connections**: Uses single shared interface only
2. **Passive collection**: Keys extracted from NODEINFO packets as they arrive
3. **Persistent storage**: Keys saved in `node_names.json`
4. **Automatic injection**: Keys loaded at startup + updated every 5 min
5. **Immediate availability**: Keys available from first boot (if previously collected)

---

**Visual Summary**: Extract → Store → Inject → Decrypt ✓
