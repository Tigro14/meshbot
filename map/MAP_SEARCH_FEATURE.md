# Map Search Feature Documentation

## Overview

The map.html file now includes a powerful search feature that allows users to quickly locate and zoom to specific nodes on the Meshtastic network map.

## Location

The search form is located in the stats panel on the right side of the map, below the time filter buttons.

## Features

### 1. Search Input
- **Placeholder**: "Nom ou ID du nœud" (Node name or ID)
- **Search Types Supported**:
  - Short name (e.g., "tigro", "bob")
  - Long name (e.g., "Tigro G2 PV", "Bob's Node")
  - Node ID (e.g., "!a2e175ac", "a2e175ac")
- **Case Insensitive**: Searches work regardless of letter casing
- **Partial Match**: Searches find nodes that contain the search term

### 2. Search Button
- Click to execute search
- Alternatively, press Enter in the input field

### 3. Clear Button
- Clears the search input
- Removes highlight from previously found node
- Closes any open popup
- Returns map to default view (owner node or Paris center)

### 4. Result Messages
- **Success** (Green): "✓ Trouvé: [Node Name]"
- **Errors** (Red):
  - Empty input: "Veuillez entrer un nom de nœud"
  - Node not found: "Aucun nœud trouvé pour [search term]"
  - Node filtered: "Nœud [name] trouvé mais pas visible (filtre de temps)"
  - Data not loaded: "Données non chargées"

## User Workflow

### Basic Search
1. Type node name or ID in the search field
2. Click "Chercher" or press Enter
3. Map zooms to the node (zoom level 15)
4. Node pulses 3 times with highlight animation
5. Popup opens showing node details

### Clear Search
1. Click "Effacer" button
2. Search input is cleared
3. Highlight is removed
4. Popup closes
5. Map returns to default view

## Technical Details

### Search Algorithm
```javascript
// Searches across three fields (case-insensitive)
- node.user.shortName
- node.user.longName
- node ID
```

### Zoom Behavior
- **Target Zoom Level**: 15 (detailed view)
- **Animation**: Smooth 1-second transition
- **Centering**: Node positioned at map center

### Highlight Animation
- **Duration**: 1.5 seconds per pulse
- **Repetitions**: 3 pulses
- **Effect**: Scale from 1.0 to 1.3 with opacity change
- **Timing**: Starts 500ms after zoom begins

### Time Filter Integration
- Search respects active time filters (24h, 48h, 72h, All)
- If a node exists but is filtered out by time, user receives appropriate message
- Only visible nodes can be highlighted and zoomed to

## CSS Classes

### New Classes Added
- `.search-container`: Container for entire search section
- `.search-label`: "🔍 Rechercher un nœud" label
- `.search-box`: Flex container for input/buttons
- `.search-input`: Text input field
- `.search-btn`: Blue search button
- `.clear-btn`: Gray clear button
- `.search-result`: Message area
- `.search-result.success`: Green success message
- `.search-result.error`: Red error message
- `.highlighted-marker`: Pulse animation class

### Animation
```css
@keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 0.8; }
    50% { transform: scale(1.3); opacity: 1; }
}
```

## JavaScript Functions

### Public Functions
- `searchNode()`: Executes search based on input value
- `clearSearch()`: Resets search state
- `handleSearchKeyPress(event)`: Handles Enter key in input field

### Internal Variables
- `highlightedMarker`: Stores reference to currently highlighted marker

## Use Cases

### Example 1: Find node by short name
```
Input: "tigro"
Result: Finds and zooms to node with shortName containing "tigro"
```

### Example 2: Find node by long name
```
Input: "G2 PV"
Result: Finds node with longName containing "G2 PV"
```

### Example 3: Find node by ID
```
Input: "a2e175ac"
Result: Finds node with ID "!a2e175ac"
```

### Example 4: Node not visible due to filter
```
Input: "oldnode"
Time Filter: 24h
Result: "Nœud oldnode trouvé mais pas visible (filtre de temps)"
Action: Change time filter to "Tout" (All) and search again
```

## Browser Compatibility

The search feature uses standard web APIs:
- CSS animations
- JavaScript classList API
- Leaflet.js map methods

Compatible with:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Opera 76+

## Accessibility

- Input field is keyboard accessible
- Enter key support for quick searching
- Clear visual feedback with color-coded messages
- Focus states on interactive elements
- Semantic HTML structure

## Future Enhancements

Potential improvements for future versions:
- [ ] Autocomplete suggestions while typing
- [ ] Search history
- [ ] Multi-node selection
- [ ] Regular expression support
- [ ] Search by hop count or SNR range
- [ ] Export search results
- [ ] URL parameter support (e.g., ?search=tigro)

## Troubleshooting

### Issue: Search not working
**Solution**: Check that:
1. Map data has finished loading
2. JavaScript console shows no errors
3. Browser supports required features

### Issue: Node found but not zooming
**Solution**: 
1. Check if node has valid GPS coordinates
2. Verify node is within map bounds
3. Try adjusting time filter

### Issue: Highlight animation not showing
**Solution**:
1. Ensure CSS animations are enabled in browser
2. Check browser developer console for CSS errors
3. Verify marker element exists in DOM

## Related Files

- `map/map.html`: Main implementation
- `map/test_map_search.html`: Automated tests (gitignored)
- `map/.gitignore`: Excludes test files from version control

## Version History

- **v1.0** (2024-12-03): Initial implementation
  - Search by shortName, longName, and ID
  - Zoom and highlight functionality
  - Clear function
  - Time filter integration
  - Enter key support
  - Visual feedback with messages
