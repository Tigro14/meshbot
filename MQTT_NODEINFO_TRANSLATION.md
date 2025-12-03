# MQTT Node Name Translation Fix - Visual Demonstration

## Problem Statement

When displaying mesh neighbors learned via MQTT, node IDs were shown as "Node-xxxxxxxx" instead of their actual longNames.

### Example Output (BEFORE Fix):

```
**Node-08b80708** (!08b80708)
  └─ 7 voisin(s):
     • Node-1163ccb5: SNR: 11.2
     • Node-41557097: SNR: 10.8
     • Node-3a697f21: SNR: 9.0
     • Node-da6576d8: SNR: -3.5
     • Node-5f88ed7d: SNR: -10.5
     • Node-ec4943b0: SNR: -11.5
     • Node-8b8551d8: SNR: -13.5
```

### Example Output (AFTER Fix):

```
**tigrog2-outdoor** (!08b80708)
  └─ 7 voisin(s):
     • tigrobot-maison: SNR: 11.2
     • NodePontarlier: SNR: 10.8
     • NodeBesancon: SNR: 9.0
     • NodeMontbeliard: SNR: -3.5
     • NodeDole: SNR: -10.5
     • NodeLonsLeSaunier: SNR: -11.5
     • NodeValorbe: SNR: -13.5
```

## Solution

### Architecture Flow

```
┌──────────────────────────────────────────────┐
│    Meshtastic MQTT Server                   │
│    (serveurperso.com:1883)                   │
└──────────────┬───────────────────────────────┘
               │
               │ Publishes protobuf packets:
               │ - NODEINFO_APP (port 4) ← NEW!
               │ - NEIGHBORINFO_APP (port 71)
               │
               ▼
┌──────────────────────────────────────────────┐
│    MQTTNeighborCollector                     │
│    (_on_mqtt_message)                        │
└──────┬───────────────────────┬───────────────┘
       │                       │
       │ NODEINFO_APP          │ NEIGHBORINFO_APP
       │                       │
       ▼                       ▼
┌──────────────────┐    ┌─────────────────────┐
│ _process_nodeinfo│    │ save_neighbor_info  │
│                  │    │ (existing)          │
│ Extracts:        │    └─────────────────────┘
│ - longName       │
│ - shortName      │
│                  │
│ Updates:         │
│ node_manager     │
│   .node_names    │
└──────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│    NodeManager                               │
│    node_names = {                            │
│      0x08b80708: "tigrog2-outdoor",          │
│      0x1163ccb5: "tigrobot-maison",          │
│      ...                                     │
│    }                                         │
└──────────────────────────────────────────────┘
       │
       │ Used by:
       ▼
┌──────────────────────────────────────────────┐
│    TrafficMonitor.get_neighbors_report()     │
│                                              │
│    node_name = node_manager.get_node_name()  │
│    ↓                                         │
│    Returns "tigrog2-outdoor"                 │
│    (not "Node-08b80708")                     │
└──────────────────────────────────────────────┘
```

## Implementation Details

### File Modified: `mqtt_neighbor_collector.py`

#### 1. Added NODEINFO_APP Processing

```python
# Before: Only processed NEIGHBORINFO_APP (port 71)
portnum = decoded.portnum
is_loggable = portnum in [
    portnums_pb2.PortNum.POSITION_APP,
    portnums_pb2.PortNum.TELEMETRY_APP,
    portnums_pb2.PortNum.NEIGHBORINFO_APP
]

# After: Also processes NODEINFO_APP (port 4)
portnum = decoded.portnum
is_loggable = portnum in [
    portnums_pb2.PortNum.POSITION_APP,
    portnums_pb2.PortNum.NODEINFO_APP,      # ← NEW!
    portnums_pb2.PortNum.TELEMETRY_APP,
    portnums_pb2.PortNum.NEIGHBORINFO_APP
]
```

#### 2. Added Route to NODEINFO Handler

```python
# Traiter les paquets NODEINFO pour mettre à jour les noms de nœuds
if decoded.portnum == portnums_pb2.PortNum.NODEINFO_APP:
    self._process_nodeinfo(packet, decoded, from_id)
    return
```

#### 3. New Method: `_process_nodeinfo()`

```python
def _process_nodeinfo(self, packet, decoded, from_id):
    """
    Traiter un paquet NODEINFO pour extraire et sauvegarder le nom du nœud
    """
    try:
        # Parser le payload User
        user = mesh_pb2.User()
        user.ParseFromString(decoded.payload)
        
        # Extraire les noms
        long_name = user.long_name.strip() if user.long_name else ""
        short_name = user.short_name.strip() if user.short_name else ""
        
        # Utiliser longName en priorité, sinon shortName
        name = long_name or short_name
        
        if name and self.node_manager:
            # Mettre à jour le node_manager avec ce nom
            if from_id not in self.node_manager.node_names:
                self.node_manager.node_names[from_id] = {
                    'name': name,
                    'lat': None,
                    'lon': None,
                    'alt': None,
                    'last_update': time.time()
                }
                debug_print(f"👥 [MQTT] Nouveau nœud: {name} (!{from_id:08x})")
            else:
                old_name = self.node_manager.node_names[from_id]['name']
                if old_name != name:
                    self.node_manager.node_names[from_id]['name'] = name
                    debug_print(f"👥 [MQTT] Nœud renommé: {old_name} → {name} (!{from_id:08x})")
            
            # Sauvegarder les noms de nœuds (différé pour éviter trop d'écritures)
            import threading
            threading.Timer(10.0, lambda: self.node_manager.save_node_names()).start()
            
    except Exception as e:
        debug_print(f"👥 Erreur traitement NODEINFO: {e}")
```

## Benefits

1. **Improved Readability**: Users can identify nodes by name instead of hex IDs
2. **Better UX**: Network topology is easier to understand
3. **Automatic**: No manual configuration needed - names are learned from MQTT
4. **Persistent**: Names are saved to `node_names.json` for future use
5. **Backward Compatible**: Nodes without NODEINFO still show as "Node-xxxxxxxx"

## Testing

Two comprehensive test suites were created:

1. **`test_mqtt_nodeinfo_translation.py`** - Unit tests
   - Validates NODEINFO processing logic
   - Verifies name translation in neighbor reports
   - Tests fallback to "Node-xxxxxxxx" for unknown nodes

2. **`test_mqtt_nodeinfo_integration.py`** - Integration test
   - Demonstrates complete flow from MQTT to display
   - Shows before/after comparison
   - Validates all components work together

Both test suites pass ✅

## Debug Logging

When running with `DEBUG_MODE=True`, you'll see:

```
👥 [MQTT] Paquet NODEINFO de 08b80708
👥 [MQTT] Nouveau nœud: tigrog2-outdoor (!08b80708)
👥 [MQTT] Paquet NEIGHBORINFO de 08b80708
👥 MQTT: 7 voisins pour !08b80708
```

## Configuration

No additional configuration needed. The feature works automatically if:
- `MQTT_NEIGHBOR_ENABLED = True`
- MQTT server is configured and accessible
- Nodes publish NODEINFO packets to MQTT

## Summary

✅ MQTT-learned nodes now display with their actual longName  
✅ Backward compatible with existing code  
✅ Fully tested with comprehensive test suites  
✅ Minimal code changes (54 lines added to 1 file)  
✅ No breaking changes  
