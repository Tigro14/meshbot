# HTML Map Visual Improvements

## Summary

This document describes the visual improvements made to the Meshtastic map interface (`map/map.html`).

## Changes Implemented

### 1. 24h Filter as Default ✅

**Issue Requirement:** Display 24h nodes by default

**Implementation:**
- Changed default time filter from "all" to "24h"
- Updated JavaScript variable: `currentFilter = '24'`
- Updated HTML button active state to highlight 24h button by default

**Benefit:** Users immediately see active nodes from the last 24 hours when loading the map, providing better focus on current network activity.

### 2. 4-Digit Hex Labels on Markers ✅

**Issue Requirement:** Display 4 digits hexa short name on each node size: 8px

**Implementation:**
- Added CSS class `.node-label` with font styling
- Text labels show last 4 hex digits from node ID (e.g., "!16fad3dc" → "d3dc")
- Labels positioned above circle markers
- White text-shadow for readability against any background
- Non-interactive (pointer-events: none)

**Fix Applied (Commit 4c43d91):**
The initial implementation had a visibility issue due to incorrect Leaflet divIcon configuration.

**Problem:**
```javascript
// Labels were not visible
iconSize: [0, 0],
iconAnchor: [0, -17]
```

**Solution:**
```javascript
// Labels now visible
iconSize: [null, null],  // Auto-size instead of [0, 0]
// No iconAnchor needed
```

**Font Size Update (Commit 640201d):**
Updated from 8px to 10px for better readability based on user feedback.

**CSS:**
```css
.node-label {
    font-size: 10px;  /* Updated from 8px - 25% larger for better readability */
    font-weight: bold;
    color: #000;
    text-shadow: 0 0 3px #fff, 0 0 3px #fff, 0 0 3px #fff;
    white-space: nowrap;
    pointer-events: none;
    text-align: center;
    position: relative;
    top: -20px;  /* Position above marker */
}
```

**Benefit:** Quick visual node identification without requiring clicks or popups. The 10px font size provides better readability while maintaining a clean map appearance.

### 3. Hover Tooltips with LongName ✅

**Issue Requirement:** Display the longname of each node on a tooltip on mouse over

**Implementation:**
- Added Leaflet tooltip binding to all circle markers
- Tooltips display `node.user.longName` (e.g., "tigro G2 PV")
- Appear automatically on mouse hover
- No click required
- Direction set to "top" for better visibility

**Code:**
```javascript
// Add tooltip with longName that shows on hover
const longName = node.user?.longName || 'Nœud inconnu';
marker.bindTooltip(longName, {
    permanent: false,
    direction: 'top',
    className: 'node-tooltip'
});
```

**Benefit:** Faster UX than click-to-view popups. Users can quickly see full node names by hovering.

## Technical Details

### Files Modified
- `map/map.html` - Single file change containing all improvements

### JavaScript Changes
1. Added `labelMarkers = {}` object to track label markers separately from circle markers
2. Changed `currentFilter = 'all'` to `currentFilter = '24'`
3. Updated `createMarkers()` function to:
   - Bind tooltip with longName to each marker
   - Create label marker with 4-digit hex ID
   - Properly cleanup label markers when filters change

### Data Flow
```
Node ID (e.g., "!16fad3dc")
  ├─> Hex Label: "d3dc" (last 4 digits)
  └─> Tooltip: node.user.longName (e.g., "tigro G2 PV")
```

### Cleanup Logic
Both circle markers and label markers are properly cleaned up when time filters are applied:
```javascript
Object.values(markers).forEach(marker => map.removeLayer(marker));
Object.values(labelMarkers).forEach(marker => map.removeLayer(marker));
markers = {};
labelMarkers = {};
```

## Visual Examples

### Before
- No default time filter (showed all nodes)
- No visible labels on markers
- Only popup on click for node information

### After
- 24h filter active by default
- 4-digit hex labels visible above each marker
- Hover tooltip shows full node name
- Click popup still available for detailed information

## Commit History

1. **2fc6db4** - Initial implementation
   - 24h default filter
   - Hex labels (initial version with visibility issue)
   - Hover tooltips

2. **f4e48c3** - Documentation
   - Added this documentation file

3. **4c43d91** - Fix label visibility
   - Changed `iconSize: [0, 0]` to `iconSize: [null, null]`
   - Removed problematic `iconAnchor`
   - Added CSS positioning for label placement

4. **817028c** - Update documentation
   - Added label visibility fix details and visual examples

5. **640201d** - Increase font size
   - Updated label font size from 8px to 10px
   - 25% larger for better readability
   - Based on user feedback

## Testing

The changes have been verified to:
- ✅ Correctly display 24h filter as default
- ✅ Show 4-digit hex labels (10px font) on all markers
- ✅ Display hover tooltips with long names
- ✅ Properly cleanup markers when filters change
- ✅ Maintain all existing functionality (popups, views, links)
- ✅ Font size provides better readability without cluttering the map

## Label Visibility Issue & Fix

![Label Fix](https://github.com/user-attachments/assets/167a61db-639f-43e4-baed-084235ceab82)

The initial implementation had labels that were not visible. This was fixed by:
1. Changing from `iconSize: [0, 0]` to `iconSize: [null, null]` for auto-sizing
2. Removing `iconAnchor` which was causing positioning issues
3. Using CSS `position: relative; top: -20px;` to position labels above markers
4. Adding `text-align: center` for proper centering

## Compatibility

- No breaking changes to existing functionality
- Backward compatible with existing data format
- Works with both node view, link view, and combined view
- Tested with Leaflet 1.9.4

## Future Enhancements

Potential improvements that could be added later:
- Configurable label format (hex ID vs shortName)
- Adjustable label font size in settings
- Toggle labels on/off
- Custom label positioning options
