# Fix Summary: Display Searched Nodes Regardless of Time Filter

## Problem Statement
When searching for a node in map.html, if the node was filtered out by the time filter (e.g., last heard 48 hours ago but filter set to 24h), the search would find the node but display an error message:
```
Nœud "91LIMOLM8ClP_F4IED/JN18ap" trouvé mais pas visible (filtre de temps)
```

Users had to manually adjust the time filter to see the searched node, which was inconvenient.

## Solution Implemented

### Key Changes

1. **Created `createSingleMarker()` function**
   - Extracted marker creation logic into a reusable function
   - Accepts `isSearchResult` parameter to apply special styling
   - Handles all marker creation including tooltips, labels, and MQTT hi-viz circles

2. **Modified `zoomToNode()` function**
   - Now creates markers on-demand for nodes filtered by time
   - Checks if node has valid GPS position before creating marker
   - Updates visible node count when adding searched nodes
   - No longer returns early with error for filtered nodes

3. **Visual Distinction for Searched Nodes**
   - Magenta border (`#FF00FF`) with 4px weight (vs normal 2px white)
   - Popup includes warning: `⚠ Affiché via recherche (hors filtre temps)`
   - Clear visual indicator that node is outside normal time filter

4. **Updated Search Results List**
   - Changed tag from `(filtré)` to `(filtré - sera affiché)`
   - Removed "not-allowed" cursor and opacity reduction
   - All found nodes are now clickable, even if filtered

## Visual Comparison

### Before (Broken)
- Search finds node but shows error
- Node cannot be viewed without changing time filter
- Filtered nodes marked as "not-allowed" in search results

### After (Fixed)
- Search finds node and displays it automatically
- Distinctive magenta border indicates it's a search result
- User can immediately zoom to and interact with the node
- Clear popup message explains the node is outside time filter

## Testing

See screenshot: https://github.com/user-attachments/assets/43cf600b-5229-4bf9-86df-55b932bb3890

### Test Steps
1. Open `map.html` in a browser
2. Set time filter to "24h" (default)
3. Search for a node last heard more than 24 hours ago
4. Verify the node appears with a magenta border
5. Click the node to see popup with warning message
6. Try searching with multiple results - verify all are clickable

### Expected Results
- ✅ Node is displayed with magenta border
- ✅ Popup shows: `⚠ Affiché via recherche (hors filtre temps)`
- ✅ Search results show: `(filtré - sera affiché)`
- ✅ All nodes in search results are clickable
- ✅ Visible node count increments when searched node is added

## Files Modified
- `map/map.html` - Search and marker creation logic

## Code Quality
- ✅ JavaScript syntax validated with Node.js
- ✅ No linting errors
- ✅ Follows existing code patterns
- ✅ Minimal changes (142 additions, 15 deletions)
- ✅ Backward compatible with existing functionality
