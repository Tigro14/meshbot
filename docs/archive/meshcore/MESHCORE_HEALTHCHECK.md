# MeshCore Connection Healthcheck Monitoring

## Overview

Automatic health monitoring system for meshcore-cli connections that detects and alerts when the connection to the Meshtastic node is lost.

## Problem Solved

### Original Issue
Users reported "0 DM in the debug log" - no Direct Messages were being received at all.

### Root Cause Discovery
Investigation revealed the issue was **not in the code**, but a connection failure:

```
root@DietPi:/home/dietpi/bot# meshcore-cli -s /dev/ttyACM0 -b 115200 chat
INFO:meshcore:Serial Connection started
ERROR:meshcore:Error while querying device: Event(type=<EventType.ERROR: 'command_error'>, 
                                                    payload={'reason': 'no_event_received'}, 
                                                    attributes={})
```

When meshcore-cli loses connection to the node, **no messages can be received** regardless of code quality. Users had no visibility into this connection failure.

## Solution: Automatic Healthcheck

Added comprehensive connection health monitoring to `meshcore_cli_wrapper.py`.

### Features

#### 1. Activity Tracking
```python
# In _on_contact_message callback
self.last_message_time = time.time()
self.connection_healthy = True
```

Every time a message is received, the bot updates:
- Timestamp of last activity
- Connection health status

#### 2. Background Health Monitoring

Runs in dedicated daemon thread:
```python
self.healthcheck_thread = threading.Thread(
    target=self._healthcheck_monitor,
    name="MeshCore-Healthcheck",
    daemon=True
)
```

Checks every 60 seconds if messages have been received recently.

#### 3. Intelligent Alerting

**First Alert (Connection Lost)**:
```
⚠️ [MESHCORE-HEALTHCHECK] ALERTE: Aucun message reçu depuis 302s
   → La connexion au nœud semble perdue
   → Vérifiez: 1) Le nœud est allumé
   →          2) Le câble série est connecté (/dev/ttyACM0)
   →          3) meshcore-cli peut se connecter: meshcore-cli -s /dev/ttyACM0 -b 115200 chat
```

**Recovery Alert (Connection Restored)**:
```
✅ [MESHCORE-HEALTHCHECK] Connexion rétablie (message reçu il y a 15s)
```

**Debug Mode (Periodic OK)**:
```
🏥 [MESHCORE-HEALTHCHECK] OK - dernier message: 45s
```

#### 4. Diagnostic Information

When connection fails, the alert provides:
- How long since last message
- Port and baudrate being used
- Exact command to test connection manually
- Troubleshooting steps

### Configuration

```python
# In __init__
self.healthcheck_interval = 60      # Check every 60 seconds
self.message_timeout = 300          # Alert after 5 minutes of silence
```

Can be adjusted based on network characteristics:
- **High-traffic network**: Keep default (5 minutes)
- **Low-traffic network**: Increase timeout to avoid false alarms
- **Critical monitoring**: Decrease interval for faster detection

## Implementation Details

### Architecture

```
┌─────────────────────────────────────────────┐
│         MeshCoreCLIWrapper                  │
├─────────────────────────────────────────────┤
│                                             │
│  Main Thread                                │
│  ├── connect()                              │
│  └── start_reading()                        │
│      ├── Subscribe to CONTACT_MSG_RECV      │
│      ├── Start _async_event_loop thread     │
│      └── Start _healthcheck_monitor thread  │
│                                             │
│  Event Thread (_async_event_loop)           │
│  └── meshcore dispatcher                    │
│      └── _on_contact_message callback       │
│          └── Update last_message_time ✓     │
│                                             │
│  Healthcheck Thread (_healthcheck_monitor)  │
│  └── Every 60s:                             │
│      ├── Check time since last message      │
│      ├── Alert if > 300s                    │
│      └── Log recovery when restored         │
│                                             │
└─────────────────────────────────────────────┘
```

### State Machine

```
Initial State:
  connection_healthy = False
  last_message_time = None

After start_reading():
  last_message_time = now()
  (30 second grace period)

Healthy State:
  - Messages being received
  - connection_healthy = True
  - last_message_time updated on each message
  - Debug logs every 60s (if DEBUG_MODE)

Unhealthy Detection:
  - time_since_last_message > 300s
  - connection_healthy changed: True → False
  - ERROR alert logged with diagnostics
  - Continue monitoring

Recovery Detection:
  - Message received
  - connection_healthy changed: False → True
  - INFO alert logged
  - Return to Healthy State
```

### Thread Safety

- `last_message_time`: Written by event thread, read by healthcheck thread
- `connection_healthy`: Written by both threads (with state change detection)
- No locks needed: timestamp read is atomic, boolean updates are safe

### Grace Period

30-second initial delay before first healthcheck:
```python
# In _healthcheck_monitor
time.sleep(30)  # Wait for initial connection to stabilize
```

This prevents false alarms during:
- Bot startup
- Connection establishment
- Contact synchronization

## Usage

### Automatic Activation

Healthcheck starts automatically when `start_reading()` is called:

```python
# In main_bot.py or similar
interface = MeshCoreCLIWrapper(port="/dev/ttyACM0", baudrate=115200)
interface.connect()
interface.start_reading()  # ← Healthcheck starts here
```

No configuration or manual activation needed.

### Monitoring Logs

**Successful startup:**
```
✅ [MESHCORE-CLI] Thread événements démarré
✅ [MESHCORE-CLI] Healthcheck monitoring démarré
🏥 [MESHCORE-HEALTHCHECK] Healthcheck monitoring started
📡 [MESHCORE-CLI] Début écoute événements...
```

**Connection failure detected:**
```
⚠️ [MESHCORE-HEALTHCHECK] ALERTE: Aucun message reçu depuis 302s
   → La connexion au nœud semble perdue
   → Vérifiez: 1) Le nœud est allumé
   →          2) Le câble série est connecté (/dev/ttyACM0)
   →          3) meshcore-cli peut se connecter: meshcore-cli -s /dev/ttyACM0 -b 115200 chat
```

**Connection restored:**
```
✅ [MESHCORE-HEALTHCHECK] Connexion rétablie (message reçu il y a 15s)
```

### Manual Testing

To test the connection manually (as suggested by the alert):

```bash
meshcore-cli -s /dev/ttyACM0 -b 115200 chat
```

Expected output if healthy:
```
INFO:meshcore:Serial Connection started
[messages appear here]
```

Expected output if broken:
```
INFO:meshcore:Serial Connection started
ERROR:meshcore:Error while querying device: Event(type=<EventType.ERROR: 'command_error'>, 
                                                    payload={'reason': 'no_event_received'})
```

## Troubleshooting

### False Alarms (Low-Traffic Networks)

**Symptom**: Alerts even though connection is working

**Cause**: Network has very few messages (< 1 per 5 minutes)

**Solution**: Increase timeout
```python
self.message_timeout = 600  # 10 minutes instead of 5
```

### No Alerts (Connection Actually Down)

**Symptom**: Connection is broken but no alert

**Possible Causes**:
1. Bot not using meshcore-cli mode
2. Healthcheck thread crashed
3. `last_message_time` not being updated

**Check**:
```bash
# Look for healthcheck startup message in logs
grep "HEALTHCHECK" /var/log/syslog
```

### Rapid Alert/Recovery Cycling

**Symptom**: Alternating between alert and recovery every minute

**Cause**: Intermittent connection (cable issue, power problem)

**Action**: Physical inspection of:
- USB cable connection
- Node power supply
- Serial port assignment (`ls -la /dev/ttyACM*`)

## Benefits

1. **Immediate Awareness**: Know within 6 minutes if connection is lost
2. **Diagnostic Guidance**: Clear steps to verify and fix
3. **Auto-Recovery Tracking**: Confirmation when issue resolves itself
4. **Zero Configuration**: Works out of the box
5. **Minimal Overhead**: 1 check per minute, negligible CPU/memory

## Future Enhancements

Possible improvements:

1. **Telegram Alerts**: Send alert to Telegram when connection lost
2. **Auto-Reconnect**: Attempt reconnection when failure detected
3. **Metric Tracking**: Log connection uptime statistics
4. **Configurable Thresholds**: Allow timeout adjustment via config.py
5. **Health API**: Expose connection status via /health endpoint

## Related Issues

This healthcheck addresses:
- "0 DM in the debug log" - Now alerts when connection is the issue
- "meshcore-cli: no_event_received" - Provides visibility into this error
- Silent connection failures - No longer silent

## Code Reference

**File**: `meshcore_cli_wrapper.py`

**Key Methods**:
- `__init__`: Initialize healthcheck variables
- `start_reading`: Start healthcheck thread
- `_healthcheck_monitor`: Main monitoring loop
- `_on_contact_message`: Update activity timestamp
- `close`: Stop healthcheck thread

**Lines Added**: ~70 lines
**Tests**: Manual testing recommended (simulate connection loss)

---

**Status**: ✅ Implemented and ready for deployment
**Next Step**: User should monitor logs for healthcheck alerts
