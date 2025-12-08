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
  - **Short hex node IDs** (e.g., "f5k1", "40ad", "75ac") - NEW in v1.3
    - Matches against any part of the hex portion of the node ID
    - Works without the `!` prefix
    - Example: "f5k1" matches "!12f5k123"
- **Case Insensitive**: Searches work regardless of letter casing
- **Partial Match**: Searches find nodes that contain the search term

### 2. Search Button
- Click to execute search
- Alternatively, press Enter in the input field
- **Layout**: Positioned on same row as "Effacer" button (fixed in v1.1)

### 3. Clear Button
- Clears the search input
- Removes highlight from previously found node
- Closes any open popup
- Hides results listbox if visible
- Returns map to default view (owner node or Paris center)
- **Layout**: Shares row with "Chercher" button using equal flex sizing

### 4. Multiple Results Listbox (New in v1.1)
- **Appears when**: Multiple nodes match the search term
- **Features**:
  - Shows all matching nodes with long name and ID
  - Scrollable list (max height 150px)
  - Clickable items to zoom to specific node
  - Filtered nodes shown with red "(filtré)" tag and disabled
  - Auto-hides when result is selected or search is cleared
- **Visual Design**: White background with rounded borders, hover effects

### 5. Result Messages
- **Success** (Green): 
  - Single match: "✓ Trouvé: [Node Name]"
  - Multiple matches: "[N] nœuds trouvés"
- **Errors** (Red):
  - Empty input: "Veuillez entrer un nom de nœud"
  - Node not found: "Aucun nœud trouvé pour [search term]"
  - Node filtered: "Nœud [name] trouvé mais pas visible (filtre de temps)"
  - Data not loaded: "Données non chargées"

## User Workflow

### Basic Search - Single Result
1. Type node name or ID in the search field
2. Click "Chercher" or press Enter
3. If only one match: Map zooms to the node (zoom level 15)
4. Node pulses 3 times with highlight animation
5. Popup opens showing node details

### Basic Search - Multiple Results (New in v1.1)
1. Type partial node name or ID that matches multiple nodes
2. Click "Chercher" or press Enter
3. Results listbox appears showing all matches
4. Click on desired node in the list
5. Map zooms to selected node
6. Results listbox hides automatically

### Clear Search
1. Click "Effacer" button
2. Search input is cleared
3. Highlight is removed
4. Popup closes
5. Results listbox hides
6. Map returns to default view

## Technical Details

### Search Algorithm
```javascript
// Searches across three fields (case-insensitive)
// Returns ALL matching nodes (not just first match)
- node.user.shortName
- node.user.longName
- node ID

// Single match: zoom directly
// Multiple matches: show listbox
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

### New Classes Added (v1.0)
- `.search-container`: Container for entire search section
- `.search-label`: "🔍 Rechercher un nœud" label
- `.search-input-container`: Wrapper for input field only (v1.1)
- `.search-input`: Text input field
- `.search-buttons`: Flex container for both buttons (v1.1)
- `.search-btn`: Blue search button
- `.clear-btn`: Gray clear button
- `.search-result`: Message area
- `.search-result.success`: Green success message
- `.search-result.error`: Red error message
- `.highlighted-marker`: Pulse animation class

### New Classes Added (v1.1)
- `.search-results-list`: Scrollable results container (hidden by default)
- `.search-results-list.visible`: Shows listbox when active
- `.search-result-item`: Individual result item
- `.search-result-item .node-name`: Bold blue node name
- `.search-result-item .node-id`: Gray node ID text

### Animation
```css
@keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 0.8; }
    50% { transform: scale(1.3); opacity: 1; }
}
```

## JavaScript Functions

### Public Functions
- `searchNode()`: Executes search, finds all matching nodes
- `zoomToNode(nodeId, node, resultDiv)`: Helper to zoom to specific node (v1.1)
- `clearSearch()`: Resets search state and hides results list
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

### Example 3a: Find node by short hex ID (New in v1.3)
```
Input: "f5k1"
Result: Finds node with ID "!12f5k123" (matches hex portion)
```

### Example 3b: Find node by partial hex ID (New in v1.3)
```
Input: "40ad"
Result: Finds node with ID "!ab40ad45" (matches hex portion)
```

### Example 3c: Find node by last 4 hex chars (New in v1.3)
```
Input: "75ac"
Result: Finds node with ID "!a2e175ac" (matches last 4 chars)
```

### Example 4: Multiple nodes with partial match (New in v1.1)
```
Input: "tigro"
Result: Shows listbox with all nodes containing "tigro"
  - Tigro G2 PV (ID: a2e175ac)
  - Tigro Bot (ID: 16fad3dc)
  - Tigro Old Node (filtré) - not clickable
Action: Click on desired node to zoom
```

### Example 5: Node not visible due to filter
```
Input: "oldnode"
Time Filter: 24h
Result: "Nœud oldnode trouvé mais pas visible (filtre de temps)"
Action: Change time filter to "Tout" (All) and search again
```

## URL Parameters (New in v1.2)

The map now supports URL parameters for automatic search and zoom on page load.

### `node` Parameter

Automatically searches for and zooms to a specific node when the page loads.

**Syntax:**
```
map.html?node=<search-term>
```

**Examples:**
```
# Search by short name
map.html?node=tigro

# Search by long name
map.html?node=G2%20PV

# Search by node ID
map.html?node=a2e175ac

# Combine with view parameter
map.html?view=both&node=tigro

# URL-encoded search with spaces
map.html?node=Tigro%20G2%20PV
```

**Behavior:**
- Populates the search input field with the search term
- Automatically triggers a search 500ms after page load
- If single match: zooms directly to node
- If multiple matches: displays results listbox
- Respects active time filters (default is 24h)
- Shows error message if node not found or filtered out

**Use Cases:**
- Direct links to specific nodes in documentation
- Sharing node locations with team members
- Bookmarking favorite nodes for quick access
- Integration with external systems (e.g., dashboards, monitoring tools)

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
- [x] **Multi-node selection** (Implemented in v1.1)
- [x] **URL parameter support** (Implemented in v1.2)
- [ ] Autocomplete suggestions while typing
- [ ] Search history
- [ ] Regular expression support
- [ ] Search by hop count or SNR range
- [ ] Export search results
- [ ] Keyboard navigation in results listbox (arrow keys)

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
- `map/test_short_hex_search.html`: Short hex ID search test suite (NEW in v1.3)
- `map/test_map_search.html`: Automated tests (gitignored)
- `map/.gitignore`: Excludes test files from version control

## Version History

- **v1.3** (2024-12-08): Short hex node ID support
  - Enhanced search to match short hex node IDs (e.g., "f5k1", "40ad")
  - Strips `!` prefix from node IDs during comparison
  - Enables searching by any portion of the hex ID, not just the full ID
  - Examples: "75ac" matches "!a2e175ac", "f5k1" matches "!12f5k123"
  - Fully backward compatible with existing search patterns
  - Added comprehensive test suite (`test_short_hex_search.html`)

- **v1.2** (2024-12-04): URL parameter support
  - Added `node` URL parameter for automatic search on page load
  - Example: `map.html?node=tigro` will automatically search and zoom to "tigro"
  - Works with short names, long names, and node IDs
  - Compatible with existing `view` parameter (e.g., `?view=both&node=tigro`)
  - Respects time filters when searching from URL parameters
  
- **v1.1** (2024-12-04): Layout fixes and multiple results
  - Fixed button layout: "Chercher" and "Effacer" on same row
  - Added results listbox for multiple matches
  - Refactored search logic to find all matches (not just first)
  - Added `zoomToNode()` helper function
  - Visual feedback for filtered nodes in results
  - Improved button sizing with equal flex layout
  
- **v1.0** (2024-12-03): Initial implementation
  - Search by shortName, longName, and ID
  - Zoom and highlight functionality
  - Clear function
  - Time filter integration
  - Enter key support
  - Visual feedback with messages
