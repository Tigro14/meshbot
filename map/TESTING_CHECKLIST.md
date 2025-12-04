# Testing Checklist: Search Node Filter Fix

## Pre-Testing Setup
- [ ] Open `map.html` in a web browser
- [ ] Ensure the page loads correctly and displays the map
- [ ] Verify the time filter buttons are visible (Tout, 2h, 24h, 48h, 72h)
- [ ] Confirm the search box is present with "🔍 Rechercher un nœud" label

## Test Case 1: Search for Visible Node (Within Time Filter)
**Expected**: Normal behavior - node already visible with white border

1. Set time filter to "24h" (default)
2. Search for a node that was last heard within 24 hours
3. **Expected Result**:
   - ✅ Node zooms into view
   - ✅ Node has normal white border (2px)
   - ✅ Popup opens automatically
   - ✅ No warning message in popup
   - ✅ Success message: "✓ Trouvé: [node name]"

## Test Case 2: Search for Filtered Node (Outside Time Filter) ⭐
**Expected**: NEW behavior - node created with magenta border

1. Set time filter to "24h"
2. Search for a node that was last heard MORE than 24 hours ago (e.g., "91LIMOLM8ClP_F4IED/JN18ap")
3. **Expected Result**:
   - ✅ Node appears on map (created dynamically)
   - ✅ Node has **magenta border (#FF00FF, 4px thick)**
   - ✅ Node zooms into view
   - ✅ Popup opens automatically
   - ✅ Popup shows warning: **"⚠ Affiché via recherche (hors filtre temps)"**
   - ✅ Success message: "✓ Trouvé: [node name]"
   - ✅ Visible node count increments by 1

## Test Case 3: Multiple Search Results with Mixed Visibility
**Expected**: All results clickable, filtered ones show "(filtré - sera affiché)"

1. Set time filter to "24h"
2. Search for a partial name that matches multiple nodes (some within 24h, some outside)
3. **Expected Result**:
   - ✅ Search results list appears with all matching nodes
   - ✅ Nodes within time filter: normal display
   - ✅ Nodes outside time filter: show **(filtré - sera affiché)** tag in red
   - ✅ ALL nodes are clickable (no "not-allowed" cursor)
   - ✅ Clicking any node zooms to it
   - ✅ Filtered nodes get magenta border when clicked

## Test Case 4: Search for Node Without Valid GPS
**Expected**: Error message about missing GPS

1. Search for a node that exists but has no GPS coordinates (lat/lon = 0 or null)
2. **Expected Result**:
   - ❌ Error message: "Nœud '[name]' trouvé mais sans position GPS valide"
   - ❌ No marker created
   - ❌ Map doesn't zoom

## Test Case 5: Clear Search
**Expected**: Search results cleared, view resets

1. Perform a search (any node)
2. Click "Effacer" button
3. **Expected Result**:
   - ✅ Search input cleared
   - ✅ Search results list hidden
   - ✅ Success/error message cleared
   - ✅ Map view resets to default (your node or Paris center)
   - ✅ Highlight animation removed from marker

## Test Case 6: Change Time Filter After Searching Filtered Node
**Expected**: Searched node behavior changes based on new filter

1. Set time filter to "24h"
2. Search for node last heard 48h ago (gets magenta border)
3. Change time filter to "72h"
4. **Expected Result**:
   - ✅ Node now within filter (no magenta border anymore)
   - ✅ Node displayed with normal white border
   - ✅ Popup no longer shows warning message

## Visual Verification Checklist

### Normal Node (Within Time Filter)
- ⚪ White border (2px)
- 🟢 Green fill (for direct nodes)
- 📝 Standard popup (no warning)

### Searched Node (Outside Time Filter) ⭐
- 🟣 **Magenta border (#FF00FF, 4px)** ← KEY DIFFERENCE
- 🟢 Green fill (color by hops)
- ⚠️ **Warning in popup: "Affiché via recherche (hors filtre temps)"**

## Edge Cases to Test

- [ ] Search with exact node ID (e.g., "!a2e175ac")
- [ ] Search with partial ID (e.g., "a2e175")
- [ ] Search with node name (case-insensitive)
- [ ] Search with non-existent node name
- [ ] Search while map is zoomed in/out
- [ ] Multiple rapid searches in succession
- [ ] Search then change view mode (nodes/links/both)

## Performance Checks

- [ ] No console errors when creating searched markers
- [ ] Page doesn't freeze or lag when searching
- [ ] Memory doesn't spike abnormally
- [ ] Markers cleanup properly when filter changes

## Regression Tests (Ensure Not Broken)

- [ ] Time filter buttons still work correctly
- [ ] View buttons (Nœuds/Liens/Les deux) still work
- [ ] Map zoom/pan works normally
- [ ] Existing markers display correctly
- [ ] MQTT hi-viz circles still appear
- [ ] Links between nodes still draw correctly
- [ ] Legend displays properly

## Success Criteria

✅ **PASS if all of the following are true:**
1. Searched nodes always display, regardless of time filter
2. Magenta border clearly distinguishes searched filtered nodes
3. Popup warning appears for filtered searched nodes
4. All search results are clickable
5. No JavaScript errors in console
6. Existing functionality unchanged

❌ **FAIL if any of the following occur:**
1. Searched filtered nodes still show error message
2. Searched nodes don't appear on map
3. Magenta border missing or wrong color
4. Console errors when searching
5. Existing features broken

## Test Results

Date: __________
Tester: __________

| Test Case | Pass/Fail | Notes |
|-----------|-----------|-------|
| TC1: Visible node | ⬜ | |
| TC2: Filtered node ⭐ | ⬜ | |
| TC3: Multiple results | ⬜ | |
| TC4: No GPS | ⬜ | |
| TC5: Clear search | ⬜ | |
| TC6: Filter change | ⬜ | |

Overall Result: ⬜ PASS / ⬜ FAIL

Comments:
_____________________________________________
_____________________________________________
_____________________________________________
