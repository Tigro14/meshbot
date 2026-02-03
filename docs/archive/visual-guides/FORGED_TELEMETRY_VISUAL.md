# Forged Telemetry Storage - Visual Guide

## Problem Overview

### Before Implementation ❌

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEMETRY FLOW (BROKEN)                 │
└─────────────────────────────────────────────────────────────┘

┌──────────┐
│ ESPHome  │ Battery: 12.5V
│ Sensors  │ Temp: 22.5°C
└────┬─────┘ Humidity: 65%
     │
     ▼
┌──────────────────┐
│ send_esphome_    │
│ telemetry()      │
└────┬─────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────┐
│  Broadcast to Mesh Network                             │
│  ✅ 3 packets sent (env, device, power)               │
└────┬───────────────────────────────────────────────────┘
     │
     ├─────────────────┐
     ▼                 ▼
┌─────────┐      ┌──────────────┐
│ Other   │      │ Bot's Own    │
│ Nodes   │      │ Database     │
│ ✅ See  │      │ ❌ MISSING   │
│ Data    │      │              │
└─────────┘      └──────────────┘
                       │
                       ▼
                 ┌──────────────┐
                 │ JSON Export  │
                 │ ❌ NO DATA   │
                 └──────────────┘
                       │
                       ▼
                 ┌──────────────┐
                 │ Map Display  │
                 │ ❌ INVISIBLE │
                 └──────────────┘
```

### Issue Identified

In `traffic_monitor.py`, line 444:
```python
# Filters out self-generated telemetry to avoid duplicate counting
if packet_type == 'TELEMETRY_APP' and my_node_id and from_id == my_node_id:
    return  # ❌ Skip self-generated telemetry
```

**Result:** Bot's telemetry never makes it to the database!

---

## Solution Implementation ✅

### After Implementation

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEMETRY FLOW (FIXED)                   │
└─────────────────────────────────────────────────────────────┘

┌──────────┐
│ ESPHome  │ Battery: 12.5V
│ Sensors  │ Temp: 22.5°C
└────┬─────┘ Humidity: 65%
     │
     ▼
┌──────────────────┐
│ send_esphome_    │
│ telemetry()      │
└────┬─────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────┐
│  Broadcast to Mesh Network                             │
│  ✅ 3 packets sent (env, device, power)               │
└────┬───────────────────────────────────────────────────┘
     │
     ├─────────────────┐
     ▼                 ▼
┌─────────┐      ┌──────────────────────────┐
│ Other   │      │ ✨ NEW: Store in DB     │
│ Nodes   │      │ _store_sent_telemetry()  │
│ ✅ See  │      └──────────┬───────────────┘
│ Data    │                 │
└─────────┘                 ▼
                 ┌──────────────────────────┐
                 │ TrafficPersistence       │
                 │ save_node_stats()        │
                 │                          │
                 │ node_stats table:        │
                 │ • last_battery: 85%      │
                 │ • last_voltage: 12.5V    │
                 │ • last_temperature: 22.5°│
                 │ • last_humidity: 65%     │
                 │ • last_pressure: 1013hPa │
                 │ ✅ STORED                │
                 └──────────┬───────────────┘
                            │
                            ▼
                 ┌──────────────────────────┐
                 │ export_nodes_from_db.py  │
                 │                          │
                 │ Query:                   │
                 │ SELECT last_battery_*,   │
                 │        last_temperature, │
                 │        last_humidity...  │
                 │ ✅ DATA INCLUDED         │
                 └──────────┬───────────────┘
                            │
                            ▼
                 ┌──────────────────────────┐
                 │ info.json                │
                 │                          │
                 │ {                        │
                 │   "!16fa4fdc": {         │
                 │     "deviceMetrics": {   │
                 │       "batteryLevel": 85 │
                 │       "voltage": 12.5    │
                 │     },                   │
                 │     "environmentMetrics" │
                 │       "temperature": 22.5│
                 │     }                    │
                 │   }                      │
                 │ }                        │
                 │ ✅ JSON READY            │
                 └──────────┬───────────────┘
                            │
                            ▼
                 ┌──────────────────────────┐
                 │ map.html                 │
                 │                          │
                 │ Node Popup:              │
                 │ ┌────────────────────┐   │
                 │ │ 🤖 MeshBot         │   │
                 │ │                    │   │
                 │ │ 🔋 85% (12.5V)     │   │
                 │ │ 🌡️ 22.5°C         │   │
                 │ │ 💧 65% RH          │   │
                 │ │ 📊 1013 hPa        │   │
                 │ └────────────────────┘   │
                 │ ✅ VISIBLE!              │
                 └──────────────────────────┘
```

---

## Code Flow Detail

### 1. Send Telemetry
```python
def send_esphome_telemetry(self):
    """Send ESPHome data as telemetry broadcast."""
    
    # Get sensor values
    sensor_values = self.esphome_client.get_sensor_values()
    # {
    #   'battery_voltage': 12.5,
    #   'temperature': 22.5,
    #   'humidity': 65.0,
    #   'pressure': 1013.25
    # }
    
    # Calculate battery percentage
    battery_level = min(100, max(0, 
        int((sensor_values['battery_voltage'] - 11.0) / (13.8 - 11.0) * 100)
    ))  # 85%
    
    # Send 3 packets to mesh
    packets_sent = 0
    
    # Packet 1: Environment metrics
    if has_env_data:
        self._send_telemetry_packet(env_telemetry, "environment_metrics")
        packets_sent += 1
    
    # Packet 2: Device metrics (battery)
    if has_device_data:
        self._send_telemetry_packet(device_telemetry, "device_metrics")
        packets_sent += 1
    
    # Packet 3: Power metrics
    if has_power_data:
        self._send_telemetry_packet(power_telemetry, "power_metrics")
        packets_sent += 1
    
    if packets_sent > 0:
        info_print(f"✅ Télémétrie ESPHome: {packets_sent} paquet(s)")
        
        # ✨ NEW: Store in database
        self._store_sent_telemetry(sensor_values, battery_level)
```

### 2. Store in Database
```python
def _store_sent_telemetry(self, sensor_values, battery_level):
    """Store telemetry in local database."""
    
    # Get bot's node ID
    my_node_id = self.interface.localNode.nodeNum  # 385503196
    node_id_hex = f"!{my_node_id:08x}"  # "!16fa4fdc"
    
    # Get/create node stats entry
    if node_id_hex not in self.traffic_monitor.node_packet_stats:
        self.traffic_monitor.node_packet_stats[node_id_hex] = {
            'telemetry_stats': {'count': 0},
            # ... other fields ...
        }
    
    # Update telemetry stats
    tel_stats = self.traffic_monitor.node_packet_stats[node_id_hex]['telemetry_stats']
    
    tel_stats['last_battery'] = battery_level           # 85
    tel_stats['last_voltage'] = sensor_values['battery_voltage']  # 12.5
    tel_stats['last_temperature'] = sensor_values['temperature']  # 22.5
    tel_stats['last_humidity'] = sensor_values['humidity']        # 65.0
    tel_stats['last_pressure'] = sensor_values['pressure']        # 1013.25
    
    # Save to SQLite
    self.traffic_monitor.persistence.save_node_stats({
        node_id_hex: self.traffic_monitor.node_packet_stats[node_id_hex]
    })
    
    debug_print(f"💾 Télémétrie stockée pour {node_id_hex}")
```

### 3. Export to JSON
```python
# In map/export_nodes_from_db.py

# Query telemetry from database
cursor.execute("""
    SELECT node_id, 
           last_battery_level, last_battery_voltage,
           last_temperature, last_humidity, last_pressure
    FROM node_stats
    WHERE last_battery_level IS NOT NULL
       OR last_temperature IS NOT NULL
""")

for row in cursor.fetchall():
    node_id = row[0]  # "!16fa4fdc"
    
    telemetry_data[node_id] = {
        'battery_level': row[1],   # 85
        'battery_voltage': row[2],  # 12.5
        'temperature': row[3],      # 22.5
        'humidity': row[4],         # 65.0
        'pressure': row[5]          # 1013.25
    }

# Build node entry
node_entry = {
    "num": 385503196,
    "user": {"longName": "MeshBot"},
    "deviceMetrics": {
        "batteryLevel": 85,
        "voltage": 12.5
    },
    "environmentMetrics": {
        "temperature": 22.5,
        "relativeHumidity": 65.0,
        "barometricPressure": 1013.25
    }
}
```

### 4. Display on Map
```javascript
// In map.html (already implemented)

// Parse info.json
fetch('info.json')
  .then(response => response.json())
  .then(data => {
    const botNode = data['!16fa4fdc'];
    
    // Create popup with telemetry
    const popup = `
      <h3>${botNode.user.longName}</h3>
      <div class="telemetry">
        <strong>🔋 Battery:</strong> 
        ${botNode.deviceMetrics.batteryLevel}% 
        (${botNode.deviceMetrics.voltage}V)
        <br>
        <strong>🌡️ Temperature:</strong> 
        ${botNode.environmentMetrics.temperature}°C
        <br>
        <strong>💧 Humidity:</strong> 
        ${botNode.environmentMetrics.relativeHumidity}%
        <br>
        <strong>📊 Pressure:</strong> 
        ${botNode.environmentMetrics.barometricPressure / 100} hPa
      </div>
    `;
  });
```

---

## Database Schema

```sql
CREATE TABLE node_stats (
    node_id TEXT PRIMARY KEY,              -- "!16fa4fdc"
    total_packets INTEGER,                 -- Total packets seen
    total_bytes INTEGER,                   -- Total bytes
    
    -- ✨ TELEMETRY FIELDS
    last_battery_level INTEGER,            -- 0-100%
    last_battery_voltage REAL,             -- Volts
    last_telemetry_update REAL,            -- Unix timestamp
    last_temperature REAL,                 -- Celsius
    last_humidity REAL,                    -- 0-100%
    last_pressure REAL,                    -- hPa
    last_air_quality REAL,                 -- IAQ index
    
    last_updated REAL                      -- Last update time
);
```

Example row:
```
node_id               = "!16fa4fdc"
last_battery_level    = 85
last_battery_voltage  = 12.5
last_temperature      = 22.5
last_humidity         = 65.0
last_pressure         = 1013.25
last_telemetry_update = 1702743245.123
```

---

## Key Design Decisions

### ✅ Store AFTER Send
- Only store if telemetry was successfully broadcast
- Ensures consistency between mesh and database

### ✅ No Traffic Stats Impact
- Doesn't increment `total_packets`
- Doesn't affect traffic statistics
- Only updates telemetry fields

### ✅ Use Existing Infrastructure
- Leverages `TrafficPersistence.save_node_stats()`
- Uses existing `node_stats` table
- No schema changes needed

### ✅ Compatible with Export
- Export script already queries telemetry columns
- JSON format matches Meshtastic standard
- No changes needed to map display

---

## Testing

### Unit Test Flow
```
1. Create TrafficMonitor + TrafficPersistence
2. Simulate sensor data
3. Call storage logic
4. Verify database contents
   ✅ Battery: 85% (12.5V)
   ✅ Temperature: 22.5°C
   ✅ Humidity: 65%
   ✅ Pressure: 1013.25 hPa
```

### Integration Test Flow
```
1. Store telemetry (simulate bot)
2. Query database (simulate export)
3. Build JSON (simulate export format)
4. Verify JSON structure
   ✅ deviceMetrics present
   ✅ environmentMetrics present
   ✅ Values match input
```

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| Bot telemetry in DB | ❌ Missing | ✅ Stored |
| JSON export | ❌ No data | ✅ Included |
| Map display | ❌ Invisible | ✅ Visible |
| Traffic stats | ✅ Correct | ✅ Still correct |
| Code complexity | Low | Still low (+70 lines) |
| Testing | Manual | ✅ Automated |
| Documentation | None | ✅ Complete |

---

## Production Deployment

### Verification Checklist

After deploying:

- [ ] Bot sends ESPHome telemetry (check logs for "✅ Télémétrie ESPHome complète")
- [ ] Database contains bot's telemetry (query `node_stats` table)
- [ ] Export includes bot's data (check `info.json`)
- [ ] Map displays bot's sensors (open `map.html`, click bot marker)
- [ ] No errors in logs (check for "❌ Erreur stockage télémétrie")

### Commands

```bash
# 1. Check bot logs
journalctl -u meshbot -f | grep -E "Télémétrie|stockée"

# 2. Verify database
sqlite3 traffic_history.db "
SELECT node_id, last_battery_level, last_battery_voltage, 
       last_temperature, last_humidity 
FROM node_stats 
WHERE node_id LIKE '!%' AND last_battery_level IS NOT NULL;
"

# 3. Export to JSON
cd map/
./export_nodes_from_db.py > info.json

# 4. Check JSON
cat info.json | jq '.["!YOUR_NODE_ID"]'

# 5. Open map in browser
firefox map.html  # or your browser
```

---

## Troubleshooting

### Problem: Telemetry not in database

**Check 1:** Is telemetry being sent?
```bash
journalctl -u meshbot | grep "Télémétrie ESPHome"
# Should see: "✅ Télémétrie ESPHome complète: 3 paquet(s)"
```

**Check 2:** Is storage being called?
```bash
journalctl -u meshbot | grep "stockée"
# Should see: "💾 Télémétrie stockée en DB pour !xxxxxxxx"
```

**Check 3:** Any errors?
```bash
journalctl -u meshbot | grep "Erreur stockage"
```

### Problem: JSON doesn't include telemetry

**Check 1:** Database has data?
```bash
sqlite3 traffic_history.db "
SELECT * FROM node_stats WHERE last_battery_level IS NOT NULL;
"
```

**Check 2:** Node ID format correct?
```bash
# Should be: !16fa4fdc (with exclamation mark)
```

**Check 3:** Re-export with logging
```bash
cd map/
./export_nodes_from_db.py 2>&1 | tee export.log
grep -i telemetry export.log
```

---

## Implementation Complete ✅

All components working:
1. ✅ Bot sends telemetry to mesh
2. ✅ Bot stores telemetry in database
3. ✅ Export script includes telemetry
4. ✅ Map displays telemetry
5. ✅ No impact on statistics
6. ✅ Fully tested
7. ✅ Well documented

**Ready for production deployment!**
