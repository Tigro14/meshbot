# ESPHome Telemetry Broadcasting

## Overview

The MeshBot can now automatically broadcast environmental sensor data from an ESPHome device to the Meshtastic network as TELEMETRY packets. This allows all nodes on the mesh to receive and display environmental conditions (temperature, pressure, humidity) and battery status from the bot's location.

**NEW:** When ESPHome telemetry broadcasting is enabled (`ESPHOME_TELEMETRY_ENABLED = True`), the bot automatically disables the Meshtastic device's embedded telemetry by setting `device_update_interval = 0`. This prevents duplicate telemetry packets on the mesh network and reduces mesh noise.

## Features

- **Automatic periodic broadcasts** of ESPHome sensor data
- **Configurable interval** (default: 3600 seconds / 1 hour)
- **Automatic disabling of embedded device telemetry** to avoid mesh noise
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

### Power Metrics
- **Channel 1 Voltage** (`battery_voltage`): Battery voltage in Volts
- **Channel 1 Current** (`battery_current`): Battery current in Amperes

## Embedded Device Telemetry

When ESPHome telemetry is enabled (`ESPHOME_TELEMETRY_ENABLED = True`), the bot automatically disables the Meshtastic device's built-in telemetry to avoid duplicate packets on the mesh network:

- **Automatic Configuration**: On bot startup, sets `device_update_interval = 0` in the telemetry module config
- **Reduces Mesh Noise**: Prevents redundant device telemetry broadcasts
- **Reversible**: If you later disable ESPHome telemetry, you can manually re-enable device telemetry with:
  ```bash
  meshtastic --set telemetry.device_update_interval 900  # Re-enable with 15-minute interval
  ```
- **Preserved When Disabled**: If `ESPHOME_TELEMETRY_ENABLED = False`, the device's embedded telemetry settings remain unchanged

**Logs during startup:**
```
📊 ESPHome télémétrie activée - désactivation télémétrie embarquée...
   Intervalle actuel: 900s
✅ Télémétrie embarquée désactivée (device_update_interval = 0)
```

## How It Works

1. **Periodic Check**: Every `ESPHOME_TELEMETRY_INTERVAL` seconds (runs in `periodic_update_thread`)
2. **Data Fetch**: Queries ESPHome device for sensor values via HTTP
3. **Data Preparation**: Creates Meshtastic telemetry protobuf messages (see note below)
4. **Broadcast**: Sends up to 3 TELEMETRY_APP packets to all mesh nodes (0xFFFFFFFF)

**IMPORTANT**: The Meshtastic telemetry protobuf uses a `oneof` field, which means **only ONE metric type can be sent per packet**. Therefore, the bot sends **THREE separate packets**:
- **Packet 1**: `environment_metrics` (temperature, pressure, humidity)
- **Packet 2**: `device_metrics` (battery voltage, battery level percentage)
- **Packet 3**: `power_metrics` (ch1_voltage, ch1_current for detailed power monitoring)

This ensures all telemetry data appears correctly in node details on receiving devices.

## Telemetry Packet Structure

The bot sends standard Meshtastic telemetry packets in **three separate broadcasts**:

```python
from meshtastic.protobuf import portnums_pb2, telemetry_pb2

# PACKET 1: Environment metrics only
env_telemetry = telemetry_pb2.Telemetry()
env_telemetry.time = int(time.time())
env_telemetry.environment_metrics.temperature = 21.5  # °C
env_telemetry.environment_metrics.barometric_pressure = 101325.0  # Pa
env_telemetry.environment_metrics.relative_humidity = 56.4  # %

interface.sendData(
    env_telemetry,
    destinationId=0xFFFFFFFF,  # Broadcast to all
    portNum=portnums_pb2.PortNum.TELEMETRY_APP,
    wantResponse=False
)

# Small delay between packets
time.sleep(0.5)

# PACKET 2: Device metrics only
device_telemetry = telemetry_pb2.Telemetry()
device_telemetry.time = int(time.time())
device_telemetry.device_metrics.voltage = 12.8  # V
device_telemetry.device_metrics.battery_level = 64  # %

interface.sendData(
    device_telemetry,
    destinationId=0xFFFFFFFF,  # Broadcast to all
    portNum=portnums_pb2.PortNum.TELEMETRY_APP,
    wantResponse=False
)
```

**Why three packets?** The Meshtastic `Telemetry` protobuf has a `oneof variant` field that restricts each packet to containing only one metric type (environment_metrics OR device_metrics OR power_metrics OR air_quality_metrics, etc). Attempting to set multiple types in one packet will result in only the last-set type being transmitted.

## Missing Sensors

The implementation handles missing or faulty sensors gracefully:

- **ESPHome Offline**: No telemetry broadcast, logs warning
- **Partial Sensors**: Broadcasts available data only (1 to 3 packets depending on what's available)
- **All Sensors Missing**: No telemetry broadcast
- **Bad Values**: Individual sensors that fail are skipped

Example with partial sensors:
```
Temperature: 21.5°C ✓
Pressure: N/A (sensor offline)
Humidity: N/A (sensor offline)  
Battery: 12.8V ✓

→ Broadcasts: 
  Packet 1: Temperature only (in environment_metrics)
  Packet 2: Battery voltage + level (in device_metrics)
  Packet 3: Battery voltage + current (in power_metrics)
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

🧪 Test 2: Broadcast télémétrie (2 paquets séparés)
✅ Test 2 réussi: 2 paquets télémétrie envoyés séparément (conforme au standard)

🧪 Test 3: Gestion capteurs manquants
✅ Test 3 réussi: Gère correctement les capteurs manquants

🧪 Test 4: Broadcast télémétrie partielle
✅ Test 4 réussi: Gère correctement les données partielles

============================================================
✅ TOUS LES TESTS RÉUSSIS
============================================================
```

## Logs

When telemetry is broadcast, you'll see logs like:

```
📊 Télémétrie Env - Température: 21.5°C
📊 Télémétrie Env - Pression: 101325 Pa
📊 Télémétrie Env - Humidité: 56.4%
📡 Envoi télémétrie ESPHome (environment_metrics)...
✅ Télémétrie environment_metrics envoyée
📊 Télémétrie Device - Batterie: 12.8V (64%)
📡 Envoi télémétrie ESPHome (device_metrics)...
✅ Télémétrie device_metrics envoyée
✅ Télémétrie ESPHome complète: 2 paquet(s) envoyé(s)
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
