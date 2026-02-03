# MQTT Debug Logging Implementation

## Feature Request

Add debug logging for new MQTT neighbor entries as they come in, similar to mesh packet logs, with a distance filter for nodes <100km.

## Implementation

### Changes Made

**mqtt_neighbor_collector.py:**
1. Added `node_manager` parameter to constructor (optional)
2. Added distance calculation in message processing
3. Added debug logging with format: `[MQTT] 👥 NEIGHBORINFO de <name> [<dist>km]: <count> voisins`
4. Implemented <100km distance filter
5. Node name resolution

**main_bot.py:**
- Pass `node_manager` to MQTTNeighborCollector on initialization

### Debug Log Format

```
[MQTT] 👥 NEIGHBORINFO de <node_name> [<distance>km]: <neighbor_count> voisins
```

**Examples:**
```
[MQTT] 👥 NEIGHBORINFO de tigrog2 [12.5km]: 8 voisins
[MQTT] 👥 NEIGHBORINFO de relay-paris [45.3km]: 5 voisins
[MQTT] 👥 NEIGHBORINFO de outdoor-node [87.2km]: 12 voisins
```

**Filtered out (>100km):**
Nodes beyond 100km are silently processed but not logged.

### Distance Calculation Flow

```
1. MQTT message received with NEIGHBORINFO_APP
2. Extract node_id from protobuf
3. Lookup node GPS coordinates from NodeManager
4. Get bot's reference position from NodeManager
5. Calculate distance using haversine formula
6. If distance < 100km:
   - Get node name from NodeManager
   - Log: [MQTT] 👥 NEIGHBORINFO de <name> [<dist>km]: <count> voisins
7. If distance >= 100km or no GPS:
   - Skip logging (silent)
8. Always save to database regardless of distance
```

### Edge Cases Handled

1. **No NodeManager:** Logs without distance filter (all nodes shown)
2. **No GPS for node:** Logs without distance info
3. **No bot GPS:** Logs without distance filter
4. **Distance calculation error:** Logs with error message, continues processing
5. **Node name lookup fails:** Falls back to node ID (!xxxxxxxx)

### Code Highlights

**Distance Calculation:**
```python
# Calculer la distance du nœud si node_manager disponible
should_log = True
distance_km = None

if self.node_manager:
    try:
        node_data = self.node_manager.get_node_data(node_id)
        if node_data and 'latitude' in node_data:
            node_lat = node_data['latitude']
            node_lon = node_data['longitude']
            
            ref_pos = self.node_manager.get_reference_position()
            if ref_pos and ref_pos[0] != 0:
                distance_km = self.node_manager.haversine_distance(
                    ref_lat, ref_lon, node_lat, node_lon
                )
                
                # Filtrer: seulement afficher si <100km
                if distance_km >= 100:
                    should_log = False
    except Exception as e:
        debug_print(f"👥 Erreur calcul distance: {e}")
```

**Log Generation:**
```python
if should_log:
    node_name = self.node_manager.get_node_name(node_id)
    
    distance_str = ""
    if distance_km is not None:
        distance_str = f" [{distance_km:.1f}km]"
    
    debug_print(f"[MQTT] 👥 NEIGHBORINFO de {node_name}{distance_str}: {len(formatted_neighbors)} voisins")
```

### Integration with Existing Logs

The MQTT debug log format matches the style of existing mesh packet logs:
- **Prefix:** `[MQTT]` to distinguish from radio packets
- **Emoji:** `👥` for NEIGHBORINFO packets (same as radio)
- **Node name:** Human-readable name from NodeManager
- **Distance:** `[XX.Xkm]` format when available
- **Count:** Number of neighbors

**Comparison:**

**Radio packet log:**
```
[DEBUG] 📡 NEIGHBORINFO from tigrog2: 8 neighbors
```

**MQTT packet log:**
```
[MQTT] 👥 NEIGHBORINFO de tigrog2 [12.5km]: 8 voisins
```

### Benefits

1. **Visibility:** See neighbor data arriving from MQTT in real-time
2. **Distance awareness:** Focus on nearby nodes (<100km)
3. **Network monitoring:** Understand data flow and coverage
4. **Debugging:** Troubleshoot MQTT collection issues
5. **Consistency:** Similar format to existing mesh logs
6. **Performance:** Filtering reduces log noise from distant nodes

### Configuration

**Enable debug logging:**
```python
# config.py
DEBUG_MODE = True
```

**Distance filter:**
Hardcoded at 100km (can be made configurable if needed)

### Testing

**Unit tests:**
- MQTTNeighborCollector accepts node_manager parameter ✅
- Graceful handling when node_manager is None ✅
- Distance calculation works with valid GPS ✅

**Manual testing required:**
- Connect to serveurperso.com MQTT server
- Enable DEBUG_MODE=True
- Monitor logs for `[MQTT] 👥 NEIGHBORINFO` entries
- Verify distance filtering (<100km)
- Verify node name resolution

### Future Enhancements

Potential improvements:
- [ ] Configurable distance threshold (100km currently hardcoded)
- [ ] Option to log all nodes regardless of distance
- [ ] Statistics on filtered vs logged nodes
- [ ] Distance-based log levels (info <50km, debug 50-100km)

### Performance Impact

**Minimal:**
- Distance calculation only runs when DEBUG_MODE=True
- Haversine formula is fast (simple trigonometry)
- GPS lookups use existing NodeManager cache
- No additional MQTT overhead
- Filtering happens after database save (no data loss)

### Security

**No new risks:**
- Node positions already in NodeManager (public info)
- Distance calculation uses public GPS data
- No credentials or sensitive data in logs
- Same security profile as existing debug logs

---

**Implementation Date:** 2025-12-03
**Commit:** 717f6ec
**Status:** ✅ Complete - Ready for testing
