# ESPHome Telemetry Broadcasting

## Overview

The MeshBot can now automatically broadcast environmental sensor data from an ESPHome device to the Meshtastic network as TELEMETRY packets. This allows all nodes on the mesh to receive and display environmental conditions (temperature, pressure, humidity) and battery status from the bot's location.

## Features

- **Automatic periodic broadcasts** of ESPHome sensor data
- **Configurable interval** (default: 3600 seconds / 1 hour)
- **Graceful handling** of missing or faulty sensors
- **Standard Meshtastic TELEMETRY_APP** format for compatibility
- **Battery monitoring** with voltage and calculated percentage

## Configuration

Add these options to your `config.py`:

```python
# ========================================
# CONFIGURATION ESPHOME
# ========================================
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

# Telemetry broadcast ESPHome
ESPHOME_TELEMETRY_ENABLED = True  # Enable/disable automatic telemetry broadcast
ESPHOME_TELEMETRY_INTERVAL = 3600  # Interval in seconds (3600s = 1 hour)
```

## Supported Sensors

The following ESPHome sensors are automatically broadcast when available:

### Environmental Metrics
- **Temperature** (`bme280_temperature`): Celsius
- **Barometric Pressure** (`bme280_pressure`): Automatically converted from hPa to Pascals
- **Relative Humidity** (`bme280_relative_humidity` or `bme280_humidity`): Percentage

### Device Metrics
- **Battery Voltage** (`battery_voltage`): Volts
- **Battery Level**: Automatically calculated percentage (11.0V = 0%, 13.8V = 100%)

## How It Works

1. **Periodic Check**: Every `ESPHOME_TELEMETRY_INTERVAL` seconds (runs in `periodic_update_thread`)
2. **Data Fetch**: Queries ESPHome device for sensor values via HTTP
3. **Data Preparation**: Creates Meshtastic telemetry protobuf message
4. **Broadcast**: Sends TELEMETRY_APP packet to all mesh nodes (0xFFFFFFFF)

## Telemetry Packet Structure

The bot sends standard Meshtastic telemetry packets using:

```python
from meshtastic.protobuf import portnums_pb2, telemetry_pb2

telemetry_data = telemetry_pb2.Telemetry()
telemetry_data.time = int(time.time())

# Environmental metrics
telemetry_data.environment_metrics.temperature = 21.5  # °C
telemetry_data.environment_metrics.barometric_pressure = 101325.0  # Pa
telemetry_data.environment_metrics.relative_humidity = 56.4  # %

# Device metrics
telemetry_data.device_metrics.voltage = 12.8  # V
telemetry_data.device_metrics.battery_level = 64  # %

interface.sendData(
    telemetry_data,
    destinationId=0xFFFFFFFF,  # Broadcast to all
    portNum=portnums_pb2.PortNum.TELEMETRY_APP,
    wantResponse=False
)
```

## Missing Sensors

The implementation handles missing or faulty sensors gracefully:

- **ESPHome Offline**: No telemetry broadcast, logs warning
- **Partial Sensors**: Broadcasts available data only
- **All Sensors Missing**: No telemetry broadcast
- **Bad Values**: Individual sensors that fail are skipped

Example with partial sensors:
```
Temperature: 21.5°C ✓
Pressure: N/A (sensor offline)
Humidity: N/A (sensor offline)  
Battery: 12.8V ✓

→ Broadcasts: Temperature + Battery only
```

## Viewing Telemetry Data

On receiving nodes, telemetry data will appear in:

1. **Meshtastic Apps** (iOS/Android/Web):
   - Navigate to node details
   - View "Telemetry" or "Environment" tab
   - See temperature, pressure, humidity graphs

2. **Python API**:
   ```python
   # Subscribe to telemetry packets
   def on_telemetry(packet, interface):
       decoded = packet.get('decoded', {})
       if decoded.get('portnum') == 'TELEMETRY_APP':
           telemetry = decoded.get('telemetry', {})
           env = telemetry.get('environmentMetrics', {})
           print(f"Temperature: {env.get('temperature')}°C")
           print(f"Pressure: {env.get('barometricPressure')} Pa")
   
   pub.subscribe(on_telemetry, "meshtastic.receive.telemetry")
   ```

3. **CLI**:
   ```bash
   meshtastic --info
   # Shows telemetry data for nodes that have broadcast it
   ```

## ESPHome Setup

Your ESPHome device should expose the following HTTP endpoints:

```yaml
# ESPHome configuration example
sensor:
  - platform: bme280
    temperature:
      name: "BME280 Temperature"
      id: bme280_temperature
    pressure:
      name: "BME280 Pressure"
      id: bme280_pressure
    humidity:
      name: "BME280 Humidity" 
      id: bme280_relative_humidity
    address: 0x76
    update_interval: 60s
  
  - platform: adc
    pin: GPIO34
    name: "Battery Voltage"
    id: battery_voltage
    attenuation: 11db
    filters:
      - multiply: 3.548  # Voltage divider calibration
    update_interval: 60s

web_server:
  port: 80
```

## Testing

Run the test suite to verify functionality:

```bash
python3 test_esphome_telemetry.py
```

**Expected output:**
```
============================================================
    TESTS TÉLÉMÉTRIE ESPHOME
============================================================

🧪 Test 1: Récupération valeurs capteurs ESPHome
✅ Test 1 réussi: Valeurs correctes et pression convertie en Pa

🧪 Test 2: Broadcast télémétrie
✅ Test 2 réussi: Broadcast télémétrie fonctionne

🧪 Test 3: Gestion capteurs manquants
✅ Test 3 réussi: Gère correctement les capteurs manquants

============================================================
✅ TOUS LES TESTS RÉUSSIS
============================================================
```

## Logs

When telemetry is broadcast, you'll see logs like:

```
📊 Télémétrie - Température: 21.5°C
📊 Télémétrie - Pression: 101325 Pa
📊 Télémétrie - Humidité: 56.4%
📊 Télémétrie - Batterie: 12.8V (64%)
📡 Envoi télémétrie ESPHome en broadcast...
✅ Télémétrie ESPHome envoyée avec succès
```

## Troubleshooting

### Telemetry not broadcasting

1. **Check configuration**: `ESPHOME_TELEMETRY_ENABLED = True`
2. **Check ESPHome connection**: Can you access `http://{ESPHOME_HOST}/`?
3. **Check sensor endpoints**: Visit `http://{ESPHOME_HOST}/sensor/bme280_temperature`
4. **Check logs**: Look for error messages in bot logs

### Partial data

This is normal! The bot only broadcasts sensors that are available. If some sensors are offline or not configured, they are simply omitted.

### Wrong values

1. **Pressure in wrong unit**: Should auto-convert hPa→Pa. Check `get_sensor_values()` logic
2. **Battery percentage wrong**: Adjust voltage range in `send_esphome_telemetry()`:
   ```python
   battery_level = min(100, max(0, 
       int((voltage - MIN_VOLTAGE) / (MAX_VOLTAGE - MIN_VOLTAGE) * 100)
   ))
   ```

## Performance Impact

- **Network**: One TELEMETRY packet per interval (default: 1 hour)
- **CPU**: Minimal (HTTP requests to ESPHome already done for `/power` command)
- **Memory**: ~1KB per telemetry packet, garbage collected immediately

## Related Commands

- `/power`: Displays ESPHome data in text format (on-demand)
- `/stats`: Shows network statistics including TELEMETRY packet counts

## Future Enhancements

Possible improvements:

- [ ] Add more sensor types (air quality, UV, wind)
- [ ] Support multiple ESPHome devices
- [ ] Configurable battery voltage range
- [ ] Telemetry history/trending
- [ ] Alert thresholds (e.g., temperature > 30°C)

## References

- [Meshtastic Telemetry Module](https://meshtastic.org/docs/configuration/module/telemetry/)
- [Meshtastic Python API](https://python.meshtastic.org/)
- [ESPHome Documentation](https://esphome.io/)
