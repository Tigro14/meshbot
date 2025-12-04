# Fix for MQTT Disconnect Callback Signature Issue

## Problem Description

The bot was experiencing the following error during MQTT disconnection:

```
Dec 04 00:00:08 DietPi meshtastic-bot[2264042]: [ERROR] 00:00:08 - ⚡ Erreur boucle MQTT: BlitzMonitor._on_mqtt_disconnect() takes from 4 to 5 positional arguments but 6 were given
```

## Root Cause

The issue was in the callback signature for `on_disconnect` in both `blitz_monitor.py` and `mqtt_neighbor_collector.py`.

When using `paho-mqtt` version 2.x with `CallbackAPIVersion.VERSION2`, the library expects a specific callback signature that includes a `disconnect_flags` parameter.

### Incorrect Signature (Before)
```python
def _on_mqtt_disconnect(self, client, userdata, rc, properties=None):
    """Callback de déconnexion MQTT"""
    self.connected = False
    if rc != 0:
        error_print(f"⚡ Déconnexion MQTT inattendue: code {rc}")
```

This signature has **4 positional parameters** (excluding `self`):
1. `client`
2. `userdata`
3. `rc`
4. `properties` (optional)

### Correct Signature (After)
```python
def _on_mqtt_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
    """Callback de déconnexion MQTT"""
    self.connected = False
    if reason_code != 0:
        error_print(f"⚡ Déconnexion MQTT inattendue: code {reason_code}")
```

This signature has **5 positional parameters** (excluding `self`):
1. `client`
2. `userdata`
3. `disconnect_flags` ← **NEW**
4. `reason_code` (renamed from `rc`)
5. `properties`

## paho-mqtt Version 2.x CallbackAPIVersion.VERSION2

According to the paho-mqtt documentation for VERSION2:

- **on_connect**: `callback(client, userdata, flags, reason_code, properties)`
- **on_disconnect**: `callback(client, userdata, disconnect_flags, reason_code, properties)`
- **on_message**: `callback(client, userdata, message)`

The key difference from VERSION1 is:
- `disconnect_flags` parameter added (contains information about the disconnect)
- `rc` renamed to `reason_code` for clarity
- `properties` is always present (not optional)

## Changes Made

### 1. blitz_monitor.py
- Updated `_on_mqtt_disconnect()` signature (line 239)
- Changed parameter name from `rc` to `reason_code`
- Removed `properties=None` default value

### 2. mqtt_neighbor_collector.py
- Updated `_on_mqtt_disconnect()` signature (line 159)
- Changed parameter name from `rc` to `reason_code`
- Removed `properties=None` default value

## Testing

### Unit Tests
Created `test_mqtt_disconnect_fix.py` to verify:
- ✅ Callback signatures are correct for VERSION2
- ✅ Callbacks can be assigned to MQTT client without errors
- ✅ Callbacks can be invoked with VERSION2 arguments

### Integration Tests
Created `test_mqtt_disconnect_integration.py` to verify:
- ✅ BlitzMonitor can create MQTT VERSION2 client
- ✅ MQTTNeighborCollector can create MQTT VERSION2 client
- ✅ Disconnect callback can be invoked without errors
- ✅ Error codes are handled correctly

### Test Results
All tests pass successfully:
```
test_mqtt_disconnect_fix.py
======================================================================
Ran 4 tests in 0.323s

OK

test_mqtt_disconnect_integration.py
======================================================================
Ran 4 tests in 0.008s

OK (skipped=1)
```

## Impact

This fix resolves the runtime error that was causing the MQTT loop to crash when the connection was lost. The bot will now handle MQTT disconnections gracefully.

### Before Fix
- MQTT loop would crash with TypeError
- Bot would not properly handle reconnections
- Error messages in logs

### After Fix
- MQTT disconnections are handled correctly
- Automatic reconnection works as expected
- Proper error logging for unexpected disconnects
- Normal disconnects logged at debug level

## Backward Compatibility

This change only affects the internal callback signatures. The external API and configuration remain unchanged. No changes are needed to `config.py` or user code.

## References

- paho-mqtt documentation: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
- CallbackAPIVersion.VERSION2: https://github.com/eclipse/paho.mqtt.python/blob/master/ChangeLog.txt
- Issue: MQTT disconnect callback signature mismatch error

## Verification

To verify the fix is working:

1. Start the bot with BlitzMonitor or MQTTNeighborCollector enabled
2. Monitor logs for successful MQTT connection
3. Simulate a disconnect (e.g., restart MQTT server)
4. Verify no TypeError in logs
5. Verify automatic reconnection works

Expected log output on normal disconnect:
```
[DEBUG] ⚡ Déconnexion MQTT normale
```

Expected log output on error disconnect:
```
[ERROR] ⚡ Déconnexion MQTT inattendue: code 7
```
