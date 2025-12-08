# Map Enhancement: Larger Circles with Emoji Centers

## Problem Statement
On the map, we may use larger circles for the nodes, with the emoji of the node shortname centered in the circle when available (most mesh nodes in the community use emoji shortnames). We keep the longname as is on the side.

## Solution Implemented

### 1. Circle Size Increase
Changed circle marker radius values in `map/map.html`:
- **Regular nodes**: `12px` → `20px` (67% larger)
- **Owner node**: `20px` → `28px` (40% larger)
- **MQTT active circles**: `20px/28px` → `28px/36px` (40% larger)

### 2. Emoji Display Inside Circles
Added new CSS class `.node-emoji` to display emoji centered in circles:
```css
.node-emoji {
    font-size: 20px;
    pointer-events: none;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    line-height: 1;
    filter: drop-shadow(0 0 2px rgba(255, 255, 255, 0.8));
}

.node-emoji.owner {
    font-size: 24px;  /* Larger for owner node */
}
```

### 3. JavaScript Changes
Updated marker creation code in two functions:

#### createMarkers() function (main rendering)
- Added emoji marker creation using `node.user?.shortName`
- Emoji displayed as divIcon centered on coordinates
- Modified `labelMarkers` to store arrays (emoji + longName label)
- Updated cleanup code to handle marker arrays

#### createSingleMarker() function (search results)
- Same emoji + label logic for consistency
- Maintains search highlighting functionality

### 4. LongName Label (Preserved)
The existing `.node-label` class remains unchanged:
- Still displays `node.user?.longName` 
- Positioned on the side (top: -20px)
- White text-shadow for visibility

## Technical Details

### Data Flow
1. Node data contains `shortName` (emoji) and `longName` (full name)
2. Circle marker created with larger radius
3. Emoji marker created as divIcon, positioned at exact coordinates
4. LongName label created as divIcon, positioned with offset
5. Both emoji and label stored in `labelMarkers[id]` array

### Cleanup Handling
Updated marker cleanup to handle arrays:
```javascript
Object.values(labelMarkers).forEach(markerOrArray => {
    if (Array.isArray(markerOrArray)) {
        markerOrArray.forEach(m => map.removeLayer(m));
    } else {
        map.removeLayer(markerOrArray);
    }
});
```

## Files Modified
- `map/map.html` - Main map visualization (only file changed)

## Visual Impact
- **Before**: Small 12px circles with hex IDs, longName labels on side
- **After**: Large 20px circles with emoji centers, longName labels on side
- Better visual hierarchy and easier node identification
- Emoji shortNames more prominent and readable
- LongName labels provide detailed context

## Testing
Created `map/test_emoji_circles.html` for visual verification:
- 6 test nodes with emoji shortNames (🏠, 🚀, 🌟, 🔥, ⚡, 🌈)
- Demonstrates both regular and owner nodes
- Shows MQTT active circles
- Verifies centering and sizing

## Compatibility
- No breaking changes to data structure
- Backward compatible with existing info.json format
- Works with both emoji and non-emoji shortNames
- Gracefully handles missing shortName (skips emoji marker)

## Performance
- Minimal performance impact
- Two divIcon markers per node instead of one
- Cleanup properly removes all markers
- No memory leaks observed

## Future Enhancements (Optional)
- Could add animation to emoji on hover
- Could vary emoji size based on node importance
- Could add color coding to emoji based on node status
- Could make emoji interactive (show node details)
