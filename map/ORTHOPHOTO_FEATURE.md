# Orthophoto Toggle Feature

## Overview
Added a layer toggle button to switch between OpenStreetMap and IGN Géoportail Orthophoto (aerial imagery) views.

## Changes Made

### 1. No External Plugin Required
The implementation now uses Leaflet's native `L.tileLayer` with a properly formatted WMTS URL template, eliminating the need for the external WMTS plugin that was causing MIME type issues.

### 2. Modified Map Initialization
The `initMap()` function now creates two base layers:

**OpenStreetMap Layer (default):**
```javascript
const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
});
```

**IGN Géoportail Orthophoto Layer:**
```javascript
const orthoGeoportail = L.tileLayer(
    'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/jpeg',
    {
        attribution: '© IGN - Géoportail',
        maxZoom: 19
    }
);
```

### 3. Added Layer Control
```javascript
const baseLayers = {
    "OpenStreetMap": osmLayer,
    "Orthophoto": orthoGeoportail
};
L.control.layers(baseLayers, null, {position: 'topleft'}).addTo(map);
```

### 4. Error Handling
Added try-catch block around layer initialization to prevent map freeze if layer loading fails.

## User Interface

The layer control appears as a button in the **top-left corner** of the map:
- Click the layer control icon (📄) to open the layer selector
- Select either "OpenStreetMap" or "Orthophoto" to switch views
- The control automatically closes after selection

## Technical Details

### WMTS URL Template
Instead of using a plugin, the WMTS service is accessed via a standard URL template:
- **Service URL**: `https://data.geopf.fr/wmts`
- **Parameters**: 
  - `SERVICE=WMTS`
  - `REQUEST=GetTile`
  - `VERSION=1.0.0`
  - `LAYER=ORTHOIMAGERY.ORTHOPHOTOS` (current orthophoto imagery from IGN)
  - `STYLE=normal` (default styling)
  - `TILEMATRIXSET=PM` (Pseudo-Mercator, compatible with Web Mercator)
  - `TILEMATRIX={z}` (zoom level)
  - `TILEROW={y}` (tile row)
  - `TILECOL={x}` (tile column)
  - `FORMAT=image/jpeg` (compressed aerial imagery)

### Performance
- Both layers are loaded on demand (tiles only loaded when visible)
- No impact on initial page load time
- Layer switching is instant (no page reload required)
- No external dependencies to load

## Bug Fix

**Issue**: The previous implementation used an external WMTS plugin (`leaflet.tilelayer.wmts`) that was being blocked due to MIME type mismatch, causing the entire map to freeze/appear as plain grey.

**Solution**: Replaced the plugin with native Leaflet functionality using a properly formatted WMTS URL template. This eliminates the dependency and resolves the MIME type issue.

## Testing

To test the feature:
1. Open `map.html` in a web browser
2. Look for the layer control icon in the top-left corner
3. Click it and select "Orthophoto"
4. The map should switch from street map to aerial imagery
5. Switch back to "OpenStreetMap" to return to the original view

## Compatibility

- ✅ Works with all existing map features (markers, links, filters)
- ✅ Compatible with mobile devices
- ✅ No breaking changes to existing functionality
- ✅ Maintains all current map interactions
- ✅ No external dependencies required
- ✅ Resolves MIME type blocking issue
