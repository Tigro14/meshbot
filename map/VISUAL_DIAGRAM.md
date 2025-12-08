# Visual Diagram: Map Enhancement

## Circle Size Comparison

### Before (Original)
```
Regular Node (12px radius):
      Name
       ●
      
Owner Node (20px radius):
    OwnerName
       ⬤
      
MQTT Active (20px/28px radius):
      Name
      ╭─╮
      │●│  ← Yellow hiviz circle
      ╰─╯
```

### After (Enhanced)
```
Regular Node (20px radius):
      Name
       🚀   ← Emoji centered in circle
       ⬤
      
Owner Node (28px radius):
    OwnerName
       🏠   ← Larger emoji
       ⬤⬤
      
MQTT Active (28px/36px radius):
      Name
     ╭───╮
     │🌟│  ← Yellow hiviz circle + emoji
     ╰───╯
```

## CSS Structure

```css
/* New emoji display styles */
.node-emoji {
    font-size: 20px;           /* Emoji size for regular nodes */
    position: absolute;         /* Positioned over circle */
    top: 50%;                   /* Vertical center */
    left: 50%;                  /* Horizontal center */
    transform: translate(-50%, -50%); /* Perfect centering */
    filter: drop-shadow(...);   /* White glow for visibility */
}

.node-emoji.owner {
    font-size: 24px;           /* Larger emoji for owner */
}

/* Existing label style (unchanged) */
.node-label {
    font-size: 10px;
    position: relative;
    top: -20px;                /* Positioned above circle */
}
```

## JavaScript Implementation

```javascript
// Create circle marker (LARGER)
const marker = L.circleMarker([lat, lon], {
    radius: id === myNodeId ? 28 : 20,  // Was: 20 : 12
    fillColor: color,
    // ... other options
});

// NEW: Create emoji marker (centered)
const shortName = node.user?.shortName || '';
if (shortName) {
    const emojiIcon = L.divIcon({
        html: `<div class="node-emoji">${shortName}</div>`
    });
    const emojiMarker = L.marker([lat, lon], {
        icon: emojiIcon,
        interactive: false
    });
    emojiMarker.addTo(map);
}

// EXISTING: Create longName label (on side)
const labelIcon = L.divIcon({
    html: `<div class="node-label">${longName}</div>`
});
const labelMarker = L.marker([lat, lon], {
    icon: labelIcon,
    interactive: false
});
labelMarker.addTo(map);

// Store both markers for cleanup
labelMarkers[id] = [emojiMarker, labelMarker];
```

## Marker Layering (Z-index order)

```
Top Layer:    LongName Label (above circle)
              ↑
Middle Layer: Emoji (centered in circle)
              ↑
Base Layer:   Circle Marker (colored by hops)
              ↑
Bottom Layer: MQTT Hiviz Circle (if active)
```

## Data Flow

```
Node Data
    ↓
├─ user.shortName → Emoji Marker (centered)
│                   Font: 20px (24px for owner)
│                   Position: absolute center
│
└─ user.longName → Label Marker (side)
                   Font: 10px
                   Position: top -20px

Both markers stored in labelMarkers[id] array
```

## Size Comparison Table

| Element | Before | After | Change |
|---------|--------|-------|--------|
| Regular circle | 12px | 20px | +67% |
| Owner circle | 20px | 28px | +40% |
| MQTT hiviz (regular) | 20px | 28px | +40% |
| MQTT hiviz (owner) | 28px | 36px | +29% |
| Emoji size (regular) | N/A | 20px | NEW |
| Emoji size (owner) | N/A | 24px | NEW |
| LongName label | 10px | 10px | Same |

## Example Nodes

```
🏠 Owner Node (tigro G2 PV)
   Circle: 28px, red (#e74c3c)
   Emoji: 24px, centered
   Hiviz: 36px (if MQTT)

🚀 Direct Node (Hop 0)
   Circle: 20px, green (#27ae60)
   Emoji: 20px, centered
   Hiviz: 28px (if MQTT)

🌟 Hop 1 Node
   Circle: 20px, blue (#3498db)
   Emoji: 20px, centered
   Hiviz: 28px (if MQTT)

🔥 Hop 2 Node
   Circle: 20px, yellow (#f39c12)
   Emoji: 20px, centered
   Hiviz: 28px (if MQTT)
```

## Backward Compatibility

```
If shortName exists:
    Display emoji + longName
    
If shortName missing:
    Display only longName (same as before)
    
If both missing:
    Display hex ID (same as before)
```
