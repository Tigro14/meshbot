# ESPHome Telemetry Fix Summary

## Issue
ESPHome telemetry data was not appearing in the node details for tigrog2 (192.168.1.38) and other mesh nodes.

## Root Cause
The Meshtastic `Telemetry` protobuf message uses a **`oneof variant` field**, which allows **only ONE metric type per packet**. The original implementation tried to set both `environment_metrics` AND `device_metrics` in a single packet, but due to the `oneof` constraint, only the last-set field (`device_metrics`) was transmitted. The `environment_metrics` were silently discarded.

## Technical Details

### Protobuf Structure
```
message Telemetry {
  uint32 time = 1;
  
  oneof variant {
    DeviceMetrics device_metrics = 2;
    EnvironmentMetrics environment_metrics = 3;
    AirQualityMetrics air_quality_metrics = 4;
    PowerMetrics power_metrics = 5;
    // ... other metric types
  }
}
```

The `oneof variant` means you can set **ONLY ONE** of:
- `device_metrics`
- `environment_metrics`
- `air_quality_metrics`
- `power_metrics`
- `local_stats`
- `health_metrics`
- `host_metrics`

### Broken Implementation (Before)
```python
# This code appears to set both, but only device_metrics is sent
telemetry_data = telemetry_pb2.Telemetry()
telemetry_data.time = int(time.time())

# Set environment metrics
telemetry_data.environment_metrics.temperature = 21.5       # LOST!
telemetry_data.environment_metrics.barometric_pressure = 101325.0  # LOST!
telemetry_data.environment_metrics.relative_humidity = 56.4  # LOST!

# Set device metrics - this OVERWRITES the environment_metrics
telemetry_data.device_metrics.voltage = 12.8                # Sent ✓
telemetry_data.device_metrics.battery_level = 64            # Sent ✓

# Only device_metrics appear in the serialized packet!
interface.sendData(telemetry_data, ...)
```

### Fixed Implementation (After)
```python
# PACKET 1: Environment metrics only
env_telemetry = telemetry_pb2.Telemetry()
env_telemetry.time = int(time.time())
env_telemetry.environment_metrics.temperature = 21.5       # Sent ✓
env_telemetry.environment_metrics.barometric_pressure = 101325.0  # Sent ✓
env_telemetry.environment_metrics.relative_humidity = 56.4  # Sent ✓

interface.sendData(
    env_telemetry,
    destinationId=0xFFFFFFFF,
    portNum=portnums_pb2.PortNum.TELEMETRY_APP,
    wantResponse=False
)

# Small delay to avoid mesh congestion
time.sleep(0.5)

# PACKET 2: Device metrics only
device_telemetry = telemetry_pb2.Telemetry()
device_telemetry.time = int(time.time())
device_telemetry.device_metrics.voltage = 12.8             # Sent ✓
device_telemetry.device_metrics.battery_level = 64          # Sent ✓

interface.sendData(
    device_telemetry,
    destinationId=0xFFFFFFFF,
    portNum=portnums_pb2.PortNum.TELEMETRY_APP,
    wantResponse=False
)
```

## Changes Made

### Code Changes
1. **`main_bot.py::send_esphome_telemetry()`**
   - Split into two separate packet transmissions
   - Packet 1: `environment_metrics` (temperature, pressure, humidity)
   - Packet 2: `device_metrics` (battery voltage, battery level)
   - Added 0.5s delay between packets to avoid mesh congestion
   - Improved logging to show which packet is being sent

### Test Updates
2. **`test_esphome_telemetry.py`**
   - Updated Test 2 to verify **2 separate sendData() calls**
   - Added Test 4 to verify partial data scenarios (env-only or device-only)
   - All 4 tests passing ✅

### Documentation Updates
3. **`ESPHOME_TELEMETRY.md`**
   - Added explanation of `oneof` constraint
   - Updated packet structure example to show two separate packets
   - Updated example logs to reflect new behavior

4. **`TELEMETRY_FLOW.txt`**
   - Updated flow diagram to show two separate packet broadcasts
   - Updated performance metrics (2 packets instead of 1)
   - Updated error handling scenarios

5. **`demo_telemetry_fix.py`** (NEW)
   - Demonstration script showing broken vs fixed implementation
   - Visual proof of the `oneof` constraint behavior

## Test Results

All tests pass successfully:
```
✅ Test 1: Récupération valeurs capteurs ESPHome
✅ Test 2: Broadcast télémétrie (2 paquets séparés)
✅ Test 3: Gestion capteurs manquants
✅ Test 4: Broadcast télémétrie partielle
```

## Impact

### Positive
- **All telemetry data now visible** in node details on receiving nodes
- **Standards compliant** with Meshtastic TELEMETRY protobuf specification
- **Graceful handling** of partial sensor data (sends only available metrics)

### Performance
- **Network**: 2 packets per broadcast cycle instead of 1
  - Each packet: ~50-100 bytes
  - Total: ~100-200 bytes (same as before, but now both types are sent)
  - 0.5s delay between packets prevents mesh congestion
- **CPU**: Negligible impact (<1ms extra for second packet)
- **Memory**: No change (packets are immediately garbage collected)

## Verification Steps

1. **Run tests**: `python3 test_esphome_telemetry.py`
2. **Run demo**: `python3 demo_telemetry_fix.py`
3. **Deploy to production** and wait for next telemetry broadcast (default: 1 hour)
4. **Check node details** on tigrog2 and other nodes:
   - Temperature, pressure, humidity should now appear
   - Battery voltage and level should still appear
   - All metrics should be visible in the Meshtastic app

## Files Modified
- `main_bot.py` - Fixed telemetry broadcast logic
- `test_esphome_telemetry.py` - Updated and expanded tests
- `ESPHOME_TELEMETRY.md` - Updated documentation
- `TELEMETRY_FLOW.txt` - Updated flow diagram
- `demo_telemetry_fix.py` - NEW demonstration script

## References
- [Meshtastic Telemetry Module Documentation](https://meshtastic.org/docs/configuration/module/telemetry/)
- [Meshtastic Python API](https://python.meshtastic.org/)
- [Protocol Buffers (protobuf) oneof](https://protobuf.dev/programming-guides/proto3/#oneof)
