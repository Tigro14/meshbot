# Implementation Summary: Battery Current in ESPHome Telemetry

**Date**: 2025-12-15
**Issue**: Add battery current (intensité) to telemetry metrics
**Status**: ✅ COMPLETE

## Problem Statement (Original French)

> Dans la commande /power, nous récupérons déjà l'intensité et la tension de la batterie du node mesh. On pourrait l'ajouter aux métriques température/hygrométrie/pression déjà envoyés

**Translation**: The `/power` command already retrieves battery current and voltage from the mesh node. We should add these to the temperature/humidity/pressure metrics already being sent.

## Solution

Enhanced the ESPHome telemetry broadcasting system to include battery current alongside voltage using Meshtastic's `PowerMetrics` protobuf message.

## Architecture

### Before (2 Packets)
```
1. Environment Metrics
   - Temperature (°C)
   - Barometric Pressure (hPa)
   - Relative Humidity (%)

2. Device Metrics
   - Battery Voltage (V)
   - Battery Level (%)
```

### After (3 Packets)
```
1. Environment Metrics
   - Temperature (°C)
   - Barometric Pressure (hPa)
   - Relative Humidity (%)

2. Device Metrics
   - Battery Voltage (V)
   - Battery Level (%)

3. Power Metrics (NEW)
   - Channel 1 Voltage (V) - Battery voltage
   - Channel 1 Current (A) - Battery current
```

## Technical Implementation

### 1. ESPHome Client (`esphome_client.py`)

**Changes**:
- Added `/sensor/battery_current` to endpoint mapping
- Added `battery_current` field to sensor values dictionary
- Updated docstring to document new field

**Code**:
```python
endpoints_map = {
    '/sensor/bme280_temperature': 'temperature',
    '/sensor/bme280_pressure': 'pressure',
    '/sensor/bme280_relative_humidity': 'humidity',
    '/sensor/bme280_humidity': 'humidity',  # Fallback
    '/sensor/battery_voltage': 'battery_voltage',
    '/sensor/battery_current': 'battery_current'  # NEW
}

result = {
    'temperature': None,
    'pressure': None,
    'humidity': None,
    'battery_voltage': None,
    'battery_current': None  # NEW
}
```

### 2. Main Bot (`main_bot.py`)

**Changes**:
- Added Packet 3: Power Metrics transmission
- Updated `send_esphome_telemetry()` method
- Added 0.5s delay between packets
- Updated docstrings

**Code**:
```python
# ===== PACKET 3: Power Metrics =====
has_power_data = False
power_telemetry = telemetry_pb2.Telemetry()
power_telemetry.time = current_time

if sensor_values.get('battery_voltage') is not None:
    power_telemetry.power_metrics.ch1_voltage = sensor_values['battery_voltage']
    has_power_data = True

if sensor_values.get('battery_current') is not None:
    power_telemetry.power_metrics.ch1_current = sensor_values['battery_current']
    has_power_data = True

if has_power_data:
    if self._send_telemetry_packet(power_telemetry, "power_metrics"):
        packets_sent += 1
```

### 3. Documentation (`ESPHOME_TELEMETRY.md`)

**Updates**:
- Added Power Metrics section to Supported Sensors
- Updated packet count (2 → 3)
- Added complete code example for Packet 3
- Updated "Why three packets?" explanation

### 4. Tests (`test_esphome_telemetry.py`)

**Updates**:
- Test 1: Added battery_current to sensor value checks
- Test 2: Updated to expect 3 packets, added power_metrics verification
- Test 3: Added battery_current to partial sensor tests
- Test 4: Updated partial broadcast tests (env only vs device+power)
- All tests pass ✓

## Protobuf Details

### PowerMetrics Message

Meshtastic's `PowerMetrics` supports up to 3 channels for voltage and current monitoring:

```protobuf
message PowerMetrics {
    float ch1_voltage = 1;  // Battery monitoring
    float ch1_current = 2;  // Battery monitoring
    float ch2_voltage = 3;  // Available for future use
    float ch2_current = 4;  // Available for future use
    float ch3_voltage = 5;  // Available for future use
    float ch3_current = 6;  // Available for future use
}
```

We use Channel 1 for battery monitoring:
- `ch1_voltage`: Battery voltage in Volts
- `ch1_current`: Battery current in Amperes

### Why Separate Packets?

Meshtastic's `Telemetry` protobuf uses a `oneof` field, meaning only ONE metric type can be sent per packet:
- `environment_metrics` OR
- `device_metrics` OR
- `power_metrics` OR
- `air_quality_metrics` OR
- etc.

Attempting to set multiple types results in only the last-set type being transmitted.

## Benefits

1. **Richer Power Monitoring**: Current draw visible alongside voltage
2. **Network-Wide Visibility**: All mesh nodes can see power consumption
3. **Better Battery Management**: Current data helps predict runtime
4. **Solar System Monitoring**: Track charging/discharging rates
5. **Backward Compatible**: Works with existing nodes, no config changes

## Configuration

**No configuration changes required!**

The bot automatically:
1. Polls `/sensor/battery_current` from ESPHome
2. Sends battery current in power_metrics packet
3. Falls back gracefully if sensor unavailable

## Verification

Run tests:
```bash
python3 test_esphome_telemetry.py
```

Expected output:
```
✅ Test 1 réussi: Valeurs correctes, pression convertie en Pa, et current récupéré
✅ Test 2 réussi: 3 paquets télémétrie envoyés séparément (conforme au standard)
✅ Test 3 réussi: Gestion capteurs manquants
✅ Test 4 réussi: Gère correctement les données partielles
✅ TOUS LES TESTS RÉUSSIS
```

## Log Output Examples

### Successful Broadcast (All Sensors Available)
```
📊 Télémétrie Env - Température: 22.3°C
📊 Télémétrie Env - Pression: 101325 Pa
📊 Télémétrie Env - Humidité: 58.2%
✅ Télémétrie environment_metrics envoyée

📊 Télémétrie Device - Batterie: 13.1V (75%)
✅ Télémétrie device_metrics envoyée

📊 Télémétrie Power - Batterie: 13.1V @ 1.250A
✅ Télémétrie power_metrics envoyée

✅ Télémétrie ESPHome complète: 3 paquet(s) envoyé(s)
```

### Partial Sensors (Current Unavailable)
```
📊 Télémétrie Env - Température: 22.3°C
📊 Télémétrie Env - Pression: 1013.25 hPa
📊 Télémétrie Env - Humidité: 58.2%
✅ Télémétrie environment_metrics envoyée

📊 Télémétrie Device - Batterie: 13.1V (75%)
✅ Télémétrie device_metrics envoyée

📊 Télémétrie Power - Batterie: 13.1V @ N/A
✅ Télémétrie power_metrics envoyée

✅ Télémétrie ESPHome complète: 3 paquet(s) envoyé(s)
```

## Viewing Data in Meshtastic Apps

On receiving nodes, the telemetry data appears in:

### iOS/Android/Web Apps
1. Open Meshtastic app
2. Navigate to node details for the bot
3. View "Telemetry" or "Environment" tab
4. See graphs for:
   - Temperature
   - Pressure
   - Humidity
   - Battery voltage
   - Battery current (NEW)

### Python API
```python
def on_telemetry(packet, interface):
    decoded = packet.get('decoded', {})
    if decoded.get('portnum') == 'TELEMETRY_APP':
        telemetry = decoded.get('telemetry', {})
        
        # Environment data
        if 'environmentMetrics' in telemetry:
            env = telemetry['environmentMetrics']
            print(f"Temp: {env.get('temperature')}°C")
            print(f"Pressure: {env.get('barometricPressure')} Pa")
            print(f"Humidity: {env.get('relativeHumidity')}%")
        
        # Device data
        if 'deviceMetrics' in telemetry:
            device = telemetry['deviceMetrics']
            print(f"Voltage: {device.get('voltage')}V")
            print(f"Battery: {device.get('batteryLevel')}%")
        
        # Power data (NEW)
        if 'powerMetrics' in telemetry:
            power = telemetry['powerMetrics']
            print(f"Ch1 Voltage: {power.get('ch1Voltage')}V")
            print(f"Ch1 Current: {power.get('ch1Current')}A")
```

## Files Modified

| File | Lines Changed | Description |
|------|---------------|-------------|
| `esphome_client.py` | +5 | Added battery_current retrieval |
| `main_bot.py` | +33 | Added power_metrics packet |
| `ESPHOME_TELEMETRY.md` | +20 | Updated documentation |
| `test_esphome_telemetry.py` | +53 | Updated tests for 3 packets |

**Total**: 4 files, ~111 lines changed

## Commit History

1. `e9cbe81` - Add battery current to ESPHome telemetry (PowerMetrics)
2. `df6782d` - Update tests for battery current in telemetry
3. `be32d5a` - Add Packet 3 code example to ESPHOME_TELEMETRY.md

## Future Enhancements

Potential improvements:
1. Add Channel 2/3 for additional power monitoring (solar panel, load)
2. Calculate power (W = V × A) and report in logs
3. Add power consumption tracking over time
4. Send alerts when current exceeds thresholds
5. Track battery charge/discharge efficiency

## References

- Meshtastic Protobufs: https://github.com/meshtastic/protobufs
- PowerMetrics Documentation: https://buf.build/meshtastic/protobufs
- Telemetry Module: https://meshtastic.org/docs/configuration/module/telemetry/

---

**Status**: ✅ Implementation complete and verified
**Tests**: ✅ All tests passing
**Documentation**: ✅ Complete with examples
**Backward Compatibility**: ✅ Maintained
