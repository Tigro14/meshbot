# Map.html Visual Improvements - Implementation Summary

## Date
2025-12-04

## Issue
Update map.html with the following requirements:
1. Mark green links less thick
2. Display longnames instead of 4 bytes nodes shortnames over the node dots
3. Add MQTT Hi-Viz Circle on map.html (verify implementation)
4. Add a new 2h button near the 24h button
5. Display both nodes & links by default on the map

## Changes Made

### 1. Green Links Thickness Reduction ✅
**File**: `map/map.html` line 465
**Change**: Reduced link weight from 7px to 4px for SNR > 5 (green/excellent links)
```javascript
// Before
if (snr > 5) return 7;

// After
if (snr > 5) return 4;  // Reduced from 7 to 4 for green links
```
**Impact**: Less visual clutter on the map, better overall visibility

### 2. Node Labels Display LongName ✅
**File**: `map/map.html` line 850
**Change**: Display human-readable longName instead of 4-digit hex ID
```javascript
// Before
const hexLabel = id.startsWith('!') ? id.substring(id.length - 4) : id.substring(0, 4);

// After
const labelText = node.user?.longName || (id.startsWith('!') ? id.substring(id.length - 4) : id.substring(0, 4));
```
**Impact**: Much better readability - users see "tigro G2 PV" instead of "d3dc"

### 3. MQTT Hi-Viz Circle ✅
**Status**: Already implemented and verified
**Implementation**: Lines 897-914 in map.html
- Yellow/gold circle (#FFD700) with 5px border
- Appears around nodes with `mqttActive: true` flag
- Legend entry included
- Popup indicator shows MQTT status
**No changes needed** - feature working as specified

### 4. Time Filter: 2h Button ✅
**File**: `map/map.html` line 385
**Change**: Added new 2h filter button
```html
<button class="filter-btn" onclick="setTimeFilter('2')">2h</button>
```
**Location**: Between "Tout" and "24h" buttons
**Impact**: Allows monitoring of very recent network activity

### 5. Default View: Both Nodes & Links ✅
**Files**: `map/map.html` multiple locations
**Changes**:
- Line 416: `let currentView = 'both';` (was 'nodes')
- Line 361: "Les deux" button has 'active' class (moved from "Nœuds")
- Line 372: Links row visibility `display: flex` (was 'display: none')

**Impact**: Map now shows complete network topology by default

## Files Modified
- `map/map.html` - All visual improvements (10 lines changed)
- `map/.gitignore` - Added test_changes.html to ignore list

## Testing
- Created visual test page (`test_changes.html`) to document all changes
- Verified all changes in the actual code
- Confirmed backward compatibility maintained
- All existing functionality preserved

## Screenshot
![Map Changes Summary](https://github.com/user-attachments/assets/9d9e3824-aa7b-4dc7-a4d0-835df2c5c479)

## Verification Checklist
- [x] Green links reduced from 7px to 4px
- [x] Node labels show longName instead of hex IDs
- [x] MQTT Hi-Viz Circle verified as implemented
- [x] 2h button added to time filters
- [x] Default view changed to 'both' (nodes + links)
- [x] All changes committed and pushed
- [x] PR description created with screenshots
- [x] Backward compatibility maintained
- [x] No breaking changes introduced

## Notes
- All changes are minimal and surgical
- Existing code patterns followed
- No new dependencies added
- No performance impact expected
- Changes improve usability without altering functionality
