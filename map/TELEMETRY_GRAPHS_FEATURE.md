# Telemetry History Graphs Feature

## Overview

This feature adds 7-day telemetry history sparkline graphs to node cards on `map.html`. Users can now see battery level and voltage trends over time, helping identify node health issues, solar charging efficiency, and power supply quality.

## Visual Example

![Telemetry Graphs Demo](https://github.com/user-attachments/assets/ed6bc91a-ef51-4a5f-8ced-01283c2b5e26)

**Before vs After:**
- **Before**: Only current telemetry values (battery: 92%, voltage: 4.18V)
- **After**: Sparkline graphs showing 7-day trends with min/max ranges

## Features

### 📊 Sparkline Graphs
- **Battery Level**: Green sparkline showing % over 7 days
- **Voltage**: Blue sparkline showing voltage (V) over 7 days
- **Compact Design**: 120x30px SVG graphs that fit in popups
- **Current/Min/Max**: Shows current value with range in parentheses

### 🎯 Key Benefits
1. **Trend Visualization** - See battery evolution over 7 days
2. **Node Health** - Identify nodes with rapid discharge
3. **Power Quality** - Monitor voltage variations
4. **Solar Panels** - Verify charging efficiency
5. **Performance** - Optimized with max 100 points per node

## Data Format

### info.json Structure

The `telemetryHistory` array is added to each node:

```json
{
  "!16fa4fdc": {
    "num": 385503196,
    "user": {
      "id": "!16fa4fdc",
      "longName": "Tigro G2 PV",
      "shortName": "TG2PV",
      "hwModel": "TBEAM"
    },
    "deviceMetrics": {
      "batteryLevel": 92,
      "voltage": 4.18
    },
    "telemetryHistory": [
      { "t": 1734259200, "b": 85, "v": 4.05 },
      { "t": 1734262800, "b": 87, "v": 4.08 },
      { "t": 1734266400, "b": 89, "v": 4.12 },
      ...
      { "t": 1734864000, "b": 92, "v": 4.18 }
    ]
  }
}
```

### Field Descriptions

| Field | Type | Description | Optional |
|-------|------|-------------|----------|
| `t` | int | Unix timestamp (seconds) | No |
| `b` | int | Battery level (%) | Yes |
| `v` | float | Voltage (V) | Yes |
| `c` | float | Channel utilization (%) | Yes |
| `a` | float | Air utilization (%) | Yes |

**Notes:**
- Array is automatically downsampled to max 100 points for performance
- Only fields with data are included (compact format)
- Sorted chronologically (oldest to newest)

## Implementation Details

### Backend: export_nodes_from_db.py

**Query telemetry from packets table:**
```python
# Extract 7-day telemetry history
history_cutoff = time.time() - (7 * 24 * 3600)

cursor.execute("""
    SELECT from_id, timestamp, telemetry
    FROM packets
    WHERE packet_type = 'TELEMETRY_APP' 
    AND timestamp > ? 
    AND telemetry IS NOT NULL
    ORDER BY from_id, timestamp ASC
""", (history_cutoff,))
```

**Extract and format data:**
```python
telemetry_obj = json.loads(telemetry_json)
battery = telemetry_obj.get('battery')
voltage = telemetry_obj.get('voltage')

data_point = {'t': int(timestamp)}
if battery is not None:
    data_point['b'] = battery
if voltage is not None:
    data_point['v'] = round(voltage, 2)

telemetry_history[node_id_str].append(data_point)
```

**Downsample for performance:**
```python
max_points = 100
if len(history) > max_points:
    step = len(history) // max_points
    telemetry_history[node_id_str] = [history[i] for i in range(0, len(history), step)][:max_points]
```

### Frontend: map.html

**Render sparkline graphs:**
```javascript
function renderTelemetryGraphs(telemetryHistory) {
    if (!telemetryHistory || telemetryHistory.length === 0) {
        return '';
    }
    
    // Extract battery and voltage data
    const batteryData = telemetryHistory.map(p => p.b !== undefined ? p.b : null);
    const voltageData = telemetryHistory.map(p => p.v !== undefined ? p.v : null);
    
    // Generate sparklines
    const batterySparkline = generateSparkline(batteryData, 120, 30, '#4CAF50', '%');
    const voltageSparkline = generateSparkline(voltageData, 120, 30, '#2196F3', 'V');
    
    return html;
}
```

**Generate SVG sparkline:**
```javascript
function generateSparkline(data, width, height, color, unit) {
    const validData = data.filter(v => v !== null);
    const min = Math.min(...validData);
    const max = Math.max(...validData);
    const range = max - min || 1;
    
    const points = data.map((value, index) => {
        const x = (index / (data.length - 1)) * width;
        const y = height - ((value - min) / range) * height;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).filter(p => p !== null).join(' ');
    
    return `<svg width="${width}" height="${height}">
        <polyline points="${points}" 
                  fill="none" 
                  stroke="${color}" 
                  stroke-width="1.5"/>
    </svg>`;
}
```

## Usage

### Automatic Data Collection

The bot automatically collects TELEMETRY_APP packets and stores them in SQLite:

1. **Bot receives telemetry** → Stored in `packets` table with `telemetry` JSON field
2. **Export script runs** → Queries last 7 days of telemetry data
3. **info.json generated** → Contains `telemetryHistory` arrays
4. **Map displays graphs** → Sparklines rendered in node popups

### Manual Regeneration

To regenerate the map with latest telemetry data:

```bash
cd map/
./infoup_db.sh
```

This will:
1. Export nodes from database (includes telemetry history)
2. Export neighbors from database
3. Update `info.json` with fresh 7-day data

## Performance Considerations

### Optimization Strategies

1. **Downsampling**: Max 100 points per node (from potentially 1000+ measurements)
2. **Compact Format**: Short field names (`t`, `b`, `v` instead of `timestamp`, `battery`, `voltage`)
3. **Optional Fields**: Only include fields with data
4. **SVG Rendering**: Lightweight vector graphics (no canvas overhead)
5. **Lazy Loading**: Graphs only rendered when popup is opened

### Expected Performance

| Metric | Value |
|--------|-------|
| Data points per node | 1-100 (downsampled) |
| Graph render time | <10ms per node |
| info.json size increase | ~1-2KB per node |
| Popup open latency | No noticeable impact |

## Troubleshooting

### No graphs displayed

**Possible causes:**
1. No telemetry data in database (node hasn't sent TELEMETRY_APP packets)
2. Data older than 7 days (increase retention if needed)
3. Telemetry data doesn't include battery or voltage

**Check:**
```bash
sqlite3 traffic_history.db "SELECT COUNT(*) FROM packets WHERE packet_type='TELEMETRY_APP'"
```

### Graphs look empty or flat

**Possible causes:**
1. Node battery/voltage is very stable (good thing!)
2. Only 1-2 data points (insufficient for trend)
3. All data points have same value

**Note**: Min/max labels will show the range. If min=max, the node has stable power.

### Performance issues

**If map loads slowly:**
1. Check number of nodes with telemetry (>100 nodes may slow down)
2. Verify downsampling is working (max 100 points per node)
3. Consider reducing retention period

## Future Enhancements

Possible improvements:
- Temperature/humidity graphs (if environmental sensors present)
- Channel utilization trends
- Click graph to zoom/expand full history
- Export graph data as CSV
- Compare multiple nodes side-by-side
- Alert thresholds (low battery warning)

## Related Files

| File | Purpose |
|------|---------|
| `export_nodes_from_db.py` | Extract telemetry history from SQLite |
| `map.html` | Render sparkline graphs in popups |
| `traffic_persistence.py` | Store telemetry packets in database |
| `traffic_monitor.py` | Collect TELEMETRY_APP packets |
| `demo_telemetry_graphs.html` | Visual demonstration of feature |

## Credits

- **Sparkline Concept**: Edward Tufte (data visualization pioneer)
- **Implementation**: GitHub Copilot + Tigro14
- **Data Source**: Meshtastic TELEMETRY_APP packets
