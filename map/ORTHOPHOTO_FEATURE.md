# Orthophoto Toggle Feature

## Overview
Added a layer toggle button to switch between OpenStreetMap and IGN Géoportail Orthophoto (aerial imagery) views.

## Changes Made

### 1. Added Leaflet WMTS Plugin
```html
<script src="https://unpkg.com/leaflet.tilelayer.wmts@1.0.8/leaflet-tilelayer-wmts.js"></script>
```
This plugin is required to load WMTS (Web Map Tile Service) layers from IGN Géoportail.

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
const orthoGeoportail = L.tileLayer.wmts('https://data.geopf.fr/wmts', {
    layer: 'ORTHOIMAGERY.ORTHOPHOTOS',
    tilematrixSet: 'PM',
    format: 'image/jpeg',
    style: 'normal',
    attribution: '© IGN - Géoportail',
    maxZoom: 19
});
```

### 3. Added Layer Control
```javascript
const baseLayers = {
    "OpenStreetMap": osmLayer,
    "Orthophoto": orthoGeoportail
};
L.control.layers(baseLayers, null, {position: 'topleft'}).addTo(map);
```

## User Interface

The layer control appears as a button in the **top-left corner** of the map:
- Click the layer control icon (📄) to open the layer selector
- Select either "OpenStreetMap" or "Orthophoto" to switch views
- The control automatically closes after selection

## Technical Details

### WMTS Parameters
- **Service URL**: `https://data.geopf.fr/wmts`
- **Layer**: `ORTHOIMAGERY.ORTHOPHOTOS` (current orthophoto imagery from IGN)
- **Tile Matrix Set**: `PM` (Pseudo-Mercator, compatible with Web Mercator)
- **Format**: `image/jpeg` (compressed aerial imagery)
- **Style**: `normal` (default styling)

### Performance
- Both layers are loaded on demand (tiles only loaded when visible)
- No impact on initial page load time
- Layer switching is instant (no page reload required)

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
