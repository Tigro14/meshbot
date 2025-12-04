# Visual Demonstration: MQTT Active Nodes on Map

## Problem Statement
> "still do not see 🌐 MQTT actif nodes on map.html for now"

## What You Should See After This Fix

### 1. Regular Node (No MQTT)
```
┌─────────────────────────────────────┐
│                                     │
│         ●  Blue/Green Circle        │
│                                     │
│   (No yellow border)                │
└─────────────────────────────────────┘

Popup shows:
  Node Name: Test Node
  Distance: 1.2 km
  SNR: 8.5 dB
  Dernier contact: 14:23:45
```

### 2. MQTT-Active Node (Has NEIGHBORINFO)
```
┌─────────────────────────────────────┐
│                                     │
│      🟡──────────────🟡             │
│     🟡              🟡              │
│    🟡       ●       🟡              │
│     🟡              🟡              │
│      🟡──────────────🟡             │
│                                     │
│   Yellow Circle + Colored Marker    │
└─────────────────────────────────────┘

Popup shows:
  Node Name: tigro G2 PV
  Distance: 1.2 km
  SNR: 8.5 dB
  🌐 MQTT: Actif  ← NEW!
  Voisins directs: 2  ← NEW!
  Dernier contact: 14:23:45
```

### 3. Map Legend
```
┌─────────────────────────────────┐
│ Distance (hops)                 │
├─────────────────────────────────┤
│ ● Votre nœud                    │
│ ● Direct (0 hop)                │
│ ● Hop 1                         │
│ ● Hop 2                         │
│ ● Hop 3                         │
│ ● Hop 4                         │
│ ● Hop 5+                        │
├─────────────────────────────────┤
│ 🟡 🌐 MQTT actif  ← This works! │
└─────────────────────────────────┘
```

## Technical Details

### info.json Structure

**Before Fix (Broken):**
```json
{
  "Nodes in mesh": {
    "!16fa4fdc": {
      "num": 385503196,
      "user": {
        "id": "!16fa4fdc",
        "longName": "tigro G2 PV"
      },
      "position": {
        "latitude": 47.2496,
        "longitude": 6.0248
      },
      "neighbors": [
        {"nodeId": "!123456789", "snr": 8.5}
      ]
      // ❌ Missing: "mqttActive": true
    }
  }
}
```

**After Fix (Working):**
```json
{
  "Nodes in mesh": {
    "!16fa4fdc": {
      "num": 385503196,
      "user": {
        "id": "!16fa4fdc",
        "longName": "tigro G2 PV"
      },
      "position": {
        "latitude": 47.2496,
        "longitude": 6.0248
      },
      "neighbors": [
        {"nodeId": "!123456789", "snr": 8.5}
      ],
      "mqttActive": true,  // ✅ Now present!
      "mqttLastHeard": 1733175600
    }
  }
}
```

### Map Rendering Code

The yellow circle is rendered by this code in map.html (lines 898-914):

```javascript
if (node.mqttActive) {
    const hivizCircle = L.circleMarker([lat, lon], {
        radius: 20,
        fillColor: 'transparent',
        color: '#FFD700',  // Bright yellow/gold
        weight: 5,
        opacity: 1,
        fillOpacity: 0,
        className: 'mqtt-active-hiviz',
        interactive: false
    });
    hivizCircle.addTo(map);
}
```

## How to Verify in Production

### Step 1: Regenerate Map Data
```bash
cd /home/user/meshbot/map
./infoup_db.sh
```

Expected output:
```
🗄️  Export depuis fichiers locaux du bot
✅ 42 nœuds trouvés dans node_names.json
📊 Enrichissement avec données SQLite...
   • MQTT active nodes: 15 nœuds  ← Look for this!
✅ Export réussi!
```

### Step 2: Check info.json
```bash
grep -A 3 "mqttActive" /tmp/info.json | head -20
```

Expected output:
```json
      "mqttActive": true,
      "mqttLastHeard": 1733175600,
      "neighbors": [
--
      "mqttActive": true,
      "mqttLastHeard": 1733175550,
      "neighbors": [
```

### Step 3: Open map.html
```bash
firefox map.html
# or
chromium map.html
# or
open map.html  # macOS
```

### Step 4: Visual Verification
Look for:
1. ✅ Yellow circles around some nodes
2. ✅ Legend shows "🌐 MQTT actif"
3. ✅ Click on yellow-circled node
4. ✅ Popup shows "🌐 MQTT: Actif"
5. ✅ Popup shows "Voisins directs: N"

## What This Means

### For Network Operators
- **Visibility**: See which nodes are actively reporting topology
- **Monitoring**: Identify nodes connected to MQTT broker
- **Planning**: Understand network coverage and redundancy
- **Health**: Quickly spot inactive nodes

### For the Network
- **Transparency**: Everyone can see network health
- **Community**: Encourage more nodes to enable MQTT
- **Growth**: Visual feedback for network expansion
- **Reliability**: Identify robust vs fragile areas

## Example Scenarios

### Scenario 1: Healthy Network
```
Map shows:
  - 15 nodes total
  - 12 with yellow circles (80% MQTT-active)
  - Good coverage across the area

Action: None needed, network is healthy
```

### Scenario 2: Coverage Gap
```
Map shows:
  - 20 nodes total
  - 5 with yellow circles in city center
  - 15 without in suburbs (not MQTT-connected)

Action: 
  - Contact suburban node operators
  - Help them enable MQTT
  - Improve network monitoring
```

### Scenario 3: Node Offline
```
Map shows:
  - Node "TigroG2" had yellow circle yesterday
  - Now appears as regular node (no MQTT)
  - Still on map but no neighbor data

Action:
  - Check if MQTT broker is down
  - Verify node's MQTT configuration
  - Contact node operator
```

## Troubleshooting

### Yellow circles not appearing?

1. **Check database has neighbor data:**
   ```bash
   sqlite3 /home/user/meshbot/traffic_history.db \
     "SELECT COUNT(*) FROM neighbors;"
   ```
   Should return > 0

2. **Check export includes mqttActive:**
   ```bash
   grep "mqttActive" /tmp/info.json
   ```
   Should find matches

3. **Check map.html is latest version:**
   ```bash
   grep "mqtt-active-hiviz" map/map.html
   ```
   Should find the yellow circle code

4. **Clear browser cache:**
   - Hard refresh: Ctrl+Shift+R (Linux/Windows)
   - Hard refresh: Cmd+Shift+R (macOS)

### Still not working?

Check the logs:
```bash
cd /home/user/meshbot/map
./infoup_db.sh 2>&1 | grep -i mqtt
```

If you see errors, the fix may not have been applied. 
Run the test suite:
```bash
cd /home/user/meshbot/map
./test_complete_workflow.sh
```

## Success Criteria

✅ All of these should be true:

1. `test_mqtt_active.sh` passes
2. `test_complete_workflow.sh` passes
3. `grep "mqttActive" /tmp/info.json` finds matches
4. Yellow circles visible on map.html
5. Clicking yellow-circled node shows "🌐 MQTT: Actif"

If all checks pass, the fix is working correctly!
