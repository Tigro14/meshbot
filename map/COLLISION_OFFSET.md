# Collision Offset Algorithm for Overlapping Nodes

## Problem

When multiple Meshtastic nodes share the exact same GPS coordinates (e.g., multiple radios in the same building, nodes at a meetup location, or nodes sharing a single antenna), they appear as overlapping markers on the map. This creates several issues:

1. **Visibility**: Only the topmost marker is visible
2. **Clickability**: Lower markers are not accessible
3. **Information Loss**: Users cannot see or interact with hidden nodes
4. **Confusion**: Users may not realize multiple nodes exist at the same location

## Solution

We've implemented a **spiral offset algorithm** that automatically detects position collisions and applies minimal offsets to make all nodes visible and clickable.

### Algorithm Overview

The algorithm uses a **two-pass approach**:

#### Pass 1: Collision Detection
```javascript
// Group nodes by exact position
const positionMap = new Map();
Object.entries(nodes).forEach(([id, node]) => {
    const posKey = `${node.position.latitude},${node.position.longitude}`;
    if (!positionMap.has(posKey)) {
        positionMap.set(posKey, []);
    }
    positionMap.get(posKey).push(id);
});
```

#### Pass 2: Offset Calculation
```javascript
// Apply spiral offsets for colliding nodes
if (nodesAtPosition.length > 1) {
    const index = nodesAtPosition.indexOf(id);
    const angle = index * (2 * Math.PI / 5);  // 72° increments
    const radius = 0.00005 * (1 + Math.floor(index / 5));  // Growing circles
    offsetLat = radius * Math.cos(angle);
    offsetLon = radius * Math.sin(angle);
}
```

### Offset Pattern

**Pentagon Spiral**:
- **5 positions per circle** (72° apart)
- **Base radius**: 0.00005° (~5 meters at mid-latitudes)
- **Growing circles**: Each additional 5 nodes creates a new concentric circle with 2x radius

```
Example with 5 nodes:

    Node 1 (0°)
         •
         
Node 5   ⊗   Node 2
(288°)  Center (72°)

Node 4       Node 3
(216°)       (144°)
```

### Technical Details

**Distance Calculation**:
- 1 degree latitude ≈ 111 km (constant)
- 1 degree longitude ≈ 111 km * cos(latitude)
- At mid-latitudes (45°): 0.00005° ≈ 5.5 meters

**Scaling**:
- Nodes 1-5: Circle 1 (radius = 0.00005°, ~5.5m)
- Nodes 6-10: Circle 2 (radius = 0.00010°, ~11m)
- Nodes 11-15: Circle 3 (radius = 0.00015°, ~16.5m)
- And so on...

**Performance**:
- Time Complexity: O(n) - two linear passes
- Space Complexity: O(n) - position map and valid nodes array

### Implementation

Modified `map.html` in the `createMarkers()` function:

1. **Before rendering**: Group all nodes by exact position
2. **During rendering**: Calculate and apply offsets
3. **Apply to all markers**: circleMarker, labelMarker, and hivizCircle

### Testing

**Unit Tests**: `test_offset_algorithm.js`
- Test 1: Single node (no offset)
- Test 2: Two nodes (72° apart)
- Test 3: Five nodes (pentagon)
- Test 4: Six nodes (second circle)
- Test 5: Mixed positions

**Visual Demo**: `demo_collision_offset.html`
- Interactive canvas visualization
- Shows pentagon pattern
- Displays offset calculations
- Includes distance scale

**Integration Test**: `test_collision_offset.html`
- Full Leaflet map integration
- 5 test nodes at Paris coordinates
- Console logging of offsets

### Benefits

✅ **All nodes visible** - No hidden markers  
✅ **Minimal impact** - 5-10m offset imperceptible at typical zoom levels  
✅ **Individually clickable** - Each node fully accessible  
✅ **Regular pattern** - Pentagon layout aids visual identification  
✅ **Infinitely scalable** - Supports unlimited nodes via concentric circles  
✅ **Efficient** - O(n) algorithm with minimal overhead  
✅ **Automatic** - No manual configuration required  
✅ **Non-destructive** - Original GPS coordinates preserved in popup  

### Configuration

No configuration required! The algorithm automatically detects and handles position collisions.

**Constants** (can be adjusted if needed):
```javascript
const POSITIONS_PER_CIRCLE = 5;  // Pentagon pattern
const BASE_RADIUS = 0.00005;      // ~5 meters at mid-latitudes
```

### Debugging

Enable console logging to see offset details:
```javascript
console.log(`Node ${id} at collision position ${posKey}: offset by ${offsetLat.toFixed(6)}, ${offsetLon.toFixed(6)}`);
```

This logs:
- Which nodes are at collision positions
- Exact offset applied (in degrees)
- Distance from original position (in meters)

### Future Enhancements

Potential improvements for future versions:

1. **Adaptive radius**: Scale offset based on zoom level
2. **Clustering**: At low zoom, cluster nodes instead of offsetting
3. **Custom patterns**: Allow different patterns (grid, hexagon, etc.)
4. **User preference**: Toggle offset on/off via UI
5. **Animation**: Smooth transition when zooming in/out

### Related Files

- `map/map.html` - Production map with collision detection
- `map/demo_collision_offset.html` - Visual demonstration
- `map/test_collision_offset.html` - Leaflet integration test
- `map/test_offset_algorithm.js` - Unit tests
- `map/COLLISION_OFFSET.md` - This documentation

### References

- GitHub Issue: "Better display for two node sharing the exact same position"
- Implementation: Two-pass spiral offset algorithm
- Pattern: Pentagon (5 nodes per circle, 72° intervals)
- Radius: 0.00005° (~5 meters)

---

**Author**: GitHub Copilot  
**Date**: 2025-12-04  
**Version**: 1.0
