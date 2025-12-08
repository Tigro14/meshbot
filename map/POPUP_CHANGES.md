# Node Popup Changes - Visual Comparison

## What Changed

This PR adds two new features to the node popup that appears when you click on a node in the map:

1. **Hardware Model (hwModel)** - Shows the device type
2. **Interactive Neighbor List** - Click on neighbors to navigate the network

---

## Visual Comparison

### BEFORE (Original Popup)
```
┌─────────────────────────────────────┐
│ tigrog2 🐯                          │
├─────────────────────────────────────┤
│ ID: TIG2                            │
│ Hops: 0                             │
│ SNR: 9.5 dB                         │
│ Voisins directs: 3                  │ ← Just a count
│ 🌐 MQTT: Actif                      │
│ Dernier contact: 08/12/2025 22:30  │
│ Il y a 5 minutes                    │
└─────────────────────────────────────┘
```

### AFTER (Enhanced Popup)
```
┌─────────────────────────────────────┐
│ tigrog2 🐯                          │
├─────────────────────────────────────┤
│ ID: TIG2                            │
│ Modèle: HELTEC_V3               ← NEW │
│ Hops: 0                             │
│ SNR: 9.5 dB                         │
│ Voisins directs: 3                  │
│   ParisNode1 (8.2 dB)           ← NEW │ ← Clickable
│   Relay Balcon (7.5 dB)         ← NEW │ ← Clickable
│   Station Toit (6.1 dB)         ← NEW │ ← Clickable
│ 🌐 MQTT: Actif                      │
│ Dernier contact: 08/12/2025 22:30  │
│ Il y a 5 minutes                    │
└─────────────────────────────────────┘
```

---

## New Interaction Flow

### Scenario: Exploring the Network

**Step 1:** Click on a node (e.g., tigrog2 🐯)
- Popup appears showing node information
- **NEW:** See hardware model: HELTEC_V3
- **NEW:** See list of 3 neighbors with their names and signal strength

**Step 2:** Click on a neighbor name (e.g., "ParisNode1")
- Map reloads with URL: `map.html?node=ParisNode1`
- Automatically searches for ParisNode1
- Automatically zooms to that node's location
- Opens ParisNode1's popup

**Step 3:** Explore ParisNode1's neighbors
- See ParisNode1's hardware model
- See ParisNode1's neighbors
- Click on another neighbor to continue exploring

**Result:** Interactive network topology exploration! 🎉

---

## Technical Details

### URL Format

When you click on a neighbor link, the URL becomes:
```
map.html?node=<neighborLongName>
```

Examples:
- `map.html?node=ParisNode1`
- `map.html?node=Relay%20Balcon` (spaces are URL-encoded)
- `map.html?node=tigrog2%20%F0%9F%90%AF` (emoji-friendly)

### Data Source

- **hwModel**: Comes from Meshtastic node database
  - Exported via `export_nodes_from_db.py`
  - Examples: HELTEC_V3, TBEAM, LORA32_V2_1
  
- **Neighbors**: Comes from NEIGHBORINFO_APP packets
  - Stored in SQLite `neighbors` table
  - Includes SNR (signal quality) for each connection

### Backward Compatibility

The implementation handles all edge cases:

| Scenario | Behavior |
|----------|----------|
| Node has hwModel | Displayed in popup |
| Node missing hwModel | Field not shown (no error) |
| Node has neighbors | Displayed as clickable list |
| Node has no neighbors | Section not shown |
| Neighbor not in database | Falls back to neighbor ID |

---

## Code Changes

### CSS (Lines 369-376)
```css
.popup-info a {
    color: #1a73e8;
    text-decoration: none;
}

.popup-info a:hover {
    text-decoration: underline;
}
```

### JavaScript (Lines 1393-1436)
```javascript
// Add hwModel if available
if (node.user?.hwModel) {
    popupContent += `<strong>Modèle:</strong> ${node.user.hwModel}<br>`;
}

// Add neighbor list with clickable links
if (node.neighbors || node.neighbours) {
    const neighbors = node.neighbors || node.neighbours;
    const neighborCount = neighbors.length;
    popupContent += `<strong>Voisins directs:</strong> ${neighborCount}<br>`;
    
    if (neighborCount > 0) {
        popupContent += `<div style="margin-left: 10px; margin-top: 5px;">`;
        neighbors.forEach((neighbor, index) => {
            const neighborId = neighbor.nodeId || neighbor.node_id || neighbor.id;
            const neighborNode = meshData.nodes[neighborId];
            const neighborName = neighborNode?.user?.longName || neighborId;
            const snrText = neighbor.snr !== undefined && neighbor.snr !== null ? 
                ` (${neighbor.snr.toFixed(1)} dB)` : '';
            
            // Create clickable link
            popupContent += `<a href="map.html?node=${encodeURIComponent(neighborName)}">${neighborName}</a>${snrText}`;
            
            if (index < neighborCount - 1) {
                popupContent += `<br>`;
            }
        });
        popupContent += `</div>`;
    }
}
```

---

## Benefits

✅ **Better Device Context**: Know what hardware each node is running
✅ **Interactive Exploration**: Navigate the mesh network by clicking neighbors
✅ **Signal Quality Insight**: See SNR values for each neighbor connection
✅ **Zero Learning Curve**: Familiar link behavior (click to navigate)
✅ **Mobile Friendly**: Touch-friendly clickable links
✅ **No Breaking Changes**: Works with all existing data

---

## Screenshots

See the full demo with examples: `map/test_popup_demo.html`

Or view the screenshot:
![Demo](https://github.com/user-attachments/assets/19c9afb9-a23f-4f9d-97c3-109b60bcd987)
