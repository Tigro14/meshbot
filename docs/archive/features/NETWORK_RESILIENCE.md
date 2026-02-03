# Network Resilience Improvements

This document describes the network error handling and retry logic implemented across the MeshBot codebase to handle unreliable external services gracefully.

## Problem Statement

The bot integrates with several external services over HTTP and MQTT:
- **Météo-France Vigilance API** (via `vigilancemeteo` Python package)
- **wttr.in Weather API** (via curl subprocess)
- **Blitzortung.org MQTT** (via paho-mqtt)
- **ESPHome HTTP API** (via requests)
- **Remote Meshtastic nodes** (via TCP)

These services can fail due to:
- Network timeouts
- Connection refused
- Remote server disconnections
- Temporary service outages

Without proper error handling, these failures would:
- Crash the periodic monitoring loop
- Generate excessive error logs
- Prevent the bot from functioning properly

## Solution Overview

We implemented a **3-layer approach** to network resilience:

1. **Retry Logic with Exponential Backoff** - Temporary failures are retried automatically
2. **Graceful Degradation** - Services continue to work with cached/fallback data
3. **Error Isolation** - One service failure doesn't crash the entire bot

## Implementation Details

### 1. Vigilance Monitor (`vigilance_monitor.py`)

**Retry Configuration:**
- Max retries: 3
- Initial delay: 2 seconds
- Backoff strategy: Exponential (2s → 4s → 8s)

**Error Handling:**
```python
for attempt in range(max_retries):
    try:
        zone = vigilancemeteo.DepartmentWeatherAlert(self.departement)
        # ... success ...
        return result
    except ImportError:
        # Module not available - fail immediately
        return None
    except Exception as e:
        # Network error - retry with backoff
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
            retry_delay *= 2
        else:
            # All retries exhausted
            return None
```

**Features:**
- Distinguishes between permanent (ImportError) and temporary (network) errors
- Full traceback only in debug mode
- Updates `last_check_time` even on failure to prevent spam

### 2. Blitz Monitor (`blitz_monitor.py`)

**Retry Configuration:**
- Connection retries: 3
- Initial delay: 5 seconds
- Backoff strategy: Exponential (5s → 10s → 20s)

**Auto-Reconnect:**
```python
# Configure automatic reconnection
self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)

# Run in persistent loop with reconnect
def _mqtt_loop_with_reconnect(self):
    while True:
        try:
            self.mqtt_client.loop_forever()  # Auto-reconnects
        except Exception as e:
            time.sleep(30)
            self.mqtt_client.reconnect()
```

**Features:**
- Initial connection retry with exponential backoff
- Automatic reconnection if connection drops
- Separate error handling for OSError (network) vs general exceptions
- Background thread continues running even after connection failures

### 3. ESPHome Client (`esphome_client.py`)

**Retry Configuration:**
- Max retries: 2
- Initial delay: 2 seconds
- Backoff strategy: Exponential (2s → 4s)
- Connectivity timeout: 3 seconds
- Sensor timeout: 2 seconds

**Error Handling:**
```python
for attempt in range(max_retries):
    try:
        response = requests.get(url, timeout=3)
        # ... process ...
        return result
    except requests.exceptions.Timeout:
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
            retry_delay *= 2
        else:
            return "ESPHome timeout"
    except requests.exceptions.ConnectionError:
        # ... similar retry logic ...
```

**Features:**
- Specific handling for Timeout vs ConnectionError
- Two separate methods with retry: `parse_esphome_data()` and `get_sensor_values()`
- Graceful fallback messages ("ESPHome timeout", "ESPHome inaccessible")

### 4. Remote Nodes Client (`remote_nodes_client.py`)

**Retry Configuration:**
- Max retries: 2
- Initial delay: 3 seconds
- Backoff strategy: Exponential (3s → 6s)

**Error Handling:**
```python
for attempt in range(max_retries):
    try:
        remote_interface = SafeTCPConnection(host, port).__enter__()
        # ... process nodes ...
        return node_list
    except OSError as e:
        # Network error - retry
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
            retry_delay *= 2
        else:
            return []
```

**Features:**
- Leverages existing `SafeTCPConnection` context manager
- Cache still works during network failures (60-second TTL)
- Returns empty list on complete failure instead of crashing

### 5. Weather Utilities (`utils_weather.py`)

**Already Implemented** (before this PR):
- `_curl_with_retry()` function with 3 retries
- Exponential backoff (2s → 4s → 8s)
- Stale cache fallback (up to 24 hours)

**Features:**
- Retry logic for all curl-based weather requests
- Multi-level cache strategy (fresh → stale → error)
- Detailed error messages with attempt counts

### 6. Main Bot Periodic Loop (`main_bot.py`)

**Error Isolation:**
```python
# Vérification vigilance météo (si activée)
if self.vigilance_monitor:
    try:
        self.vigilance_monitor.check_vigilance()
    except Exception as e:
        error_print(f"⚠️ Erreur check vigilance (non-bloquante): {e}")
        # Continue with other tasks

# Vérification éclairs (si activée)
if self.blitz_monitor and self.blitz_monitor.enabled:
    try:
        self.blitz_monitor.check_and_report()
    except Exception as e:
        error_print(f"⚠️ Erreur check blitz (non-bloquante): {e}")
        # Continue with other tasks
```

**Features:**
- Each monitor check is wrapped in try-except
- Errors are logged but don't crash the periodic thread
- Thread continues running even if one service fails

## Retry Strategy Comparison

| Service | Max Retries | Initial Delay | Timeout | Auto-Reconnect |
|---------|-------------|---------------|---------|----------------|
| Vigilance Monitor | 3 | 2s | N/A | No |
| Blitz MQTT | 3 | 5s | N/A | Yes |
| ESPHome HTTP | 2 | 2s | 3s | No |
| Remote TCP | 2 | 3s | 10s (SafeTCP) | No |
| Weather Curl | 3 | 2s | 25s | No |

## Error Message Examples

### Before (No Retry)
```
[ERROR] 06:01:30 - ❌ Erreur vérification vigilance: Remote end closed connection without response
Traceback (most recent call last):
  ...
http.client.RemoteDisconnected: Remote end closed connection without response
```

### After (With Retry)
```
[ERROR] 06:01:30 - ⚠️ Erreur vigilance (RemoteDisconnected): Remote end closed connection without response
[ERROR]    Tentative 1/3 échouée, nouvelle tentative dans 2s...
[ERROR] 06:01:32 - ⚠️ Erreur vigilance (RemoteDisconnected): Remote end closed connection without response
[ERROR]    Tentative 2/3 échouée, nouvelle tentative dans 4s...
[INFO] 06:01:36 - ✅ Vigilance récupérée après 3 tentative(s)
```

Or if all retries fail:
```
[ERROR] 06:01:38 - ❌ Erreur vérification vigilance après 3 tentatives:
[ERROR]    Type: RemoteDisconnected
[ERROR]    Message: Remote end closed connection without response
```

## Testing

### Manual Testing

1. **Simulate Network Failure:**
   ```bash
   # Block Météo-France API temporarily
   sudo iptables -A OUTPUT -d vigilance.meteofrance.fr -j DROP
   
   # Check logs - should see retry attempts
   journalctl -u meshbot -f | grep vigilance
   
   # Unblock
   sudo iptables -D OUTPUT -d vigilance.meteofrance.fr -j DROP
   ```

2. **Simulate Timeout:**
   ```bash
   # Add network delay
   sudo tc qdisc add dev eth0 root netem delay 5000ms
   
   # Should see timeout errors with retries
   
   # Remove delay
   sudo tc qdisc del dev eth0 root
   ```

3. **Verify MQTT Reconnection:**
   ```bash
   # Restart Blitzortung MQTT broker (if local)
   # Or temporarily block MQTT port
   sudo iptables -A OUTPUT -p tcp --dport 1883 -j DROP
   
   # Check logs - should see reconnection attempts
   
   # Unblock
   sudo iptables -D OUTPUT -p tcp --dport 1883 -j DROP
   ```

### Expected Behavior

After implementing these changes:
- ✅ Temporary network issues are retried automatically
- ✅ Errors are logged with clear retry status
- ✅ Bot continues functioning despite external service failures
- ✅ Periodic monitoring loop never crashes
- ✅ Cache mechanisms provide fallback data

## Configuration

All retry parameters are hardcoded but can be made configurable in `config.py` if needed:

```python
# Potential config.py additions
VIGILANCE_MAX_RETRIES = 3
VIGILANCE_RETRY_DELAY = 2
BLITZ_MAX_RETRIES = 3
BLITZ_RETRY_DELAY = 5
ESPHOME_MAX_RETRIES = 2
ESPHOME_RETRY_DELAY = 2
```

## Monitoring

### Log Indicators

**Healthy Operation:**
```
[INFO] ✅ Vigilance check département 25: Vert
[INFO] ⚡ Blitz check: 0 éclairs détectés (15min)
[DEBUG] ESPHome: 13.2V (1.5A) | Today:450Wh | T:22.5C | P:1013 | HR:65%
```

**Temporary Issues (Recovering):**
```
[ERROR] ⚠️ Erreur vigilance (Timeout): Connection timeout
[ERROR]    Tentative 1/3 échouée, nouvelle tentative dans 2s...
[INFO] ✅ Vigilance récupérée après 2 tentative(s)
```

**Persistent Issues (Failing):**
```
[ERROR] ❌ Erreur vérification vigilance après 3 tentatives:
[ERROR]    Type: ConnectionError
[ERROR]    Message: Connection refused
[ERROR] ⚠️ Erreur check vigilance (non-bloquante): [Errno 111] Connection refused
```

## Future Improvements

1. **Circuit Breaker Pattern**: Skip retries if service is known to be down
2. **Exponential Backoff with Jitter**: Add randomness to avoid thundering herd
3. **Configurable Retry Parameters**: Move hardcoded values to `config.py`
4. **Health Checks**: Periodic health check endpoint for monitoring
5. **Metrics Collection**: Track retry counts and success rates
6. **Alert on Persistent Failures**: Send Telegram alert if service down > 1 hour

## References

- [Exponential Backoff Algorithm](https://en.wikipedia.org/wiki/Exponential_backoff)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Python Requests Retry Strategy](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.Retry)
- [Paho MQTT Reconnect](https://www.eclipse.org/paho/index.php?page=clients/python/docs/index.php#reconnect)

---

**Last Updated**: 2024-11-20  
**Author**: GitHub Copilot  
**Version**: 1.0
