# Visual Guide: Telemetry Display in Map

## What You'll See After the Fix

### Map Popup - Before Fix ❌
When clicking on a node in map.html, you would see:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TestNode1 (TST1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Position: 48.8566, 2.3522
📏 Distance: 12.3 km
📊 Hops: 2
📶 SNR: 8.5 dB

[No telemetry data displayed]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Map Popup - After Fix ✅
Now you'll see complete telemetry information:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TestNode1 (TST1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Position: 48.8566, 2.3522
📏 Distance: 12.3 km
📊 Hops: 2
📶 SNR: 8.5 dB

📡 Télémétrie:
  🔋 Batterie: 85%
  ⚡ Voltage: 4.15V
  🌡️ Température: 22.5°C
  💧 Humidité: 65%
  🌫️ Pression: 1013.25 hPa
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## How to Verify the Fix

### Step 1: Check Database Has Telemetry
```bash
cd /home/dietpi/bot
sqlite3 traffic_history.db "
SELECT 
    node_id,
    last_battery_level,
    last_battery_voltage,
    last_temperature,
    last_humidity,
    last_pressure
FROM node_stats 
WHERE last_battery_level IS NOT NULL 
   OR last_temperature IS NOT NULL
LIMIT 5;
"
```

**Expected Output:**
```
385503196|85|4.15|22.5|65.0|1013.25
305419896|92|4.18|21.0|70.0|1012.50
...
```

If you see data here, the database has telemetry! ✅

### Step 2: Regenerate Map Data
```bash
cd /home/dietpi/bot/map
./infoup_db.sh
```

**Expected Log Output:**
```
🗄️  Mode DATABASE UNIQUEMENT (sûr, pas de conflits TCP)
📊 Export des voisins...
📡 Récupération des infos nœuds depuis la base de données...
✅ 1 nœuds trouvés dans node_names.json
📊 Enrichissement avec données SQLite...
   • SNR disponible pour X nœuds
   • Last heard pour X nœuds
   • Hops disponible pour X nœuds
   • Neighbors disponible pour X nœuds
   • Telemetry disponible pour X nœuds    ← Should be > 0
   • Node stats disponible pour X nœuds
🔀 Fusion des données de voisinage dans info.json...
📤 Envoi vers le serveur web...
✅ Mise à jour terminée!
```

### Step 3: Check JSON Output
```bash
cd /home/dietpi/bot/map

# Check if telemetry is in the JSON
jq '.["Nodes in mesh"] | to_entries[] | select(.value.deviceMetrics) | {
  node: .key, 
  battery: .value.deviceMetrics.batteryLevel,
  voltage: .value.deviceMetrics.voltage
}' info.json
```

**Expected Output:**
```json
{
  "node": "!16fa4fdc",
  "battery": 85,
  "voltage": 4.15
}
{
  "node": "!12345678",
  "battery": 92,
  "voltage": 4.18
}
```

If you see this, telemetry is correctly exported! ✅

### Step 4: Visual Check in Browser
1. Open `map.html` in your browser
2. Click on any node marker on the map
3. Look for the "📡 Télémétrie:" section in the popup

**What to Look For:**
- 🔋 Battery percentage (if node reports battery)
- ⚡ Voltage in volts (if node reports voltage)
- 🌡️ Temperature in °C (if node has temperature sensor)
- 💧 Humidity in % (if node has humidity sensor)
- 🌫️ Pressure in hPa (if node has pressure sensor)

## Example JSON Structure

### Node WITHOUT Telemetry
```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": {
      "id": "!16fa4fdc",
      "longName": "TestNode1",
      "shortName": "TST1",
      "hwModel": "RAK4631"
    },
    "position": {
      "latitude": 48.8566,
      "longitude": 2.3522
    },
    "hopsAway": 2,
    "snr": 8.5
  }
}
```

### Node WITH Telemetry (After Fix)
```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": {
      "id": "!16fa4fdc",
      "longName": "TestNode1",
      "shortName": "TST1",
      "hwModel": "RAK4631"
    },
    "position": {
      "latitude": 48.8566,
      "longitude": 2.3522
    },
    "hopsAway": 2,
    "snr": 8.5,
    "deviceMetrics": {
      "batteryLevel": 85,
      "voltage": 4.15
    },
    "environmentMetrics": {
      "temperature": 22.5,
      "relativeHumidity": 65.0,
      "barometricPressure": 1013.25
    }
  }
}
```

## Troubleshooting

### "Telemetry disponible pour 0 nœuds"
**Cause:** No nodes in database have telemetry data yet
**Solution:** Wait for nodes to send TELEMETRY_APP packets. This happens automatically but may take 5-15 minutes.

### Telemetry in database but not in JSON
**Cause:** This was the original bug - now fixed!
**Solution:** Update to this version and re-run `./infoup_db.sh`

### Some nodes show telemetry, others don't
**Cause:** Normal - not all nodes send telemetry
**Explanation:** 
- Only nodes with batteries report battery level/voltage
- Only nodes with BME280/BME680 sensors report temperature/humidity/pressure
- Router nodes (mains powered) typically don't report battery

### Empty environmentMetrics section
**Cause:** Node doesn't have environment sensors
**Solution:** This is normal. Only nodes with BME280/BME680/similar sensors will show environment data.

## Network Insights From Telemetry

### Battery Monitoring
Watch battery levels to identify:
- Nodes that need solar panel adjustments
- Nodes with failing batteries
- Power consumption patterns

### Temperature Monitoring
Track temperature to:
- Identify overheating nodes
- Monitor weather conditions
- Detect nodes in sheltered vs exposed locations

### Network Health Dashboard
Use telemetry in map.html to:
- Quickly identify low-battery nodes
- Plan maintenance visits
- Monitor environmental conditions across the network
