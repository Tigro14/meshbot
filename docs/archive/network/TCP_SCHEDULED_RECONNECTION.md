# TCP Scheduled Reconnection Feature

## Overview

This feature adds **proactive/scheduled TCP reconnection** to work around firmware bugs where the TCP connection degrades over time without being detected as disconnected.

## Problem

Meshtastic firmware 2.7.15 on ESP32-based nodes (particularly Station G2) exhibits TCP stack issues where:
- Connection appears stable (socket is "connected")
- Packet reception degrades or stops after 2-3 minutes
- Silence detection eventually triggers reconnection
- Issue repeats in a cycle

## Solution

**Scheduled Reconnection**: Proactively reconnect at regular intervals (e.g., every 3 minutes) before degradation occurs.

## Configuration

### config.py

```python
# Configuration reconnexion TCP programmée (préventive)
# Force une reconnexion TCP périodique même si la connexion semble stable
# Utile pour contourner les bugs de firmware (ex: Meshtastic 2.7.15 Station G2)
TCP_FORCE_RECONNECT_INTERVAL = 0  # 0 = désactivé, 180 = tous les 3 min
```

### Recommended Settings

| Hardware | Firmware | TCP_FORCE_RECONNECT_INTERVAL | Why |
|----------|----------|------------------------------|-----|
| **Station G2** | 2.7.15 | **180** (3 min) | Known TCP bug - reconnect before degradation |
| Other ESP32 | 2.7.15 | 180 or 300 | May have similar issues |
| Stable nodes | Any | **0** (disabled) | No need for scheduled reconnection |
| Testing | Any | 120 (2 min) | Aggressive for troubleshooting |

## How It Works

### Dual Protection Mechanism

The bot now has **two independent reconnection triggers**:

```
┌─────────────────────────────────────────────────────┐
│  TCP Health Monitor Thread                          │
│                                                      │
│  Every TCP_HEALTH_CHECK_INTERVAL (30s):            │
│                                                      │
│  1. Scheduled Reconnection Check:                   │
│     if (TCP_FORCE_RECONNECT_INTERVAL > 0 AND        │
│         time_since_last >= interval)                │
│         → RECONNECT                                 │
│                                                      │
│  2. Silence Detection Check:                        │
│     if (silence_duration > TCP_SILENT_TIMEOUT)      │
│         → RECONNECT                                 │
│                                                      │
│  Whichever triggers FIRST causes reconnection       │
└─────────────────────────────────────────────────────┘
```

### Example Timeline (Station G2 with TCP_FORCE_RECONNECT_INTERVAL=180)

```
Time    Event                           Trigger
──────  ──────────────────────────────  ───────────────────
0:00    Connection established          -
0:30    Health check: OK (30 pkt/min)   -
1:00    Health check: OK (58 pkt/min)   -
1:30    Health check: OK (61 pkt/min)   -
2:00    Health check: OK (59 pkt/min)   -
2:30    Health check: OK (57 pkt/min)   -
3:00    Scheduled reconnection          ← TCP_FORCE_RECONNECT_INTERVAL
3:01    Connection re-established       -
3:30    Health check: OK (62 pkt/min)   -
...
```

### Example Timeline (without scheduled reconnection, relying on silence detection)

```
Time    Event                           Trigger
──────  ──────────────────────────────  ───────────────────
0:00    Connection established          -
0:30    Health check: OK (30 pkt/min)   -
1:00    Health check: OK (58 pkt/min)   -
1:30    Health check: OK (61 pkt/min)   -
2:00    Packets stop (bug triggers)     -
2:30    Health check: SILENCE 30s       -
3:00    Health check: SILENCE 60s       -
3:30    Health check: SILENCE 90s       -
4:00    Health check: SILENCE 120s      ← TCP_SILENT_TIMEOUT
4:01    Silence-triggered reconnection  -
4:02    Connection re-established       -
```

**Result:** Scheduled reconnection prevents the 2-minute gap where no packets are received.

## Log Output

### Normal Health Check
```
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 15s (débit: 58.3 pkt/min)
```

### Scheduled Reconnection
```
[INFO] 🔄 Reconnexion TCP programmée (intervalle: 180s)
[INFO] 📊 Session stats: 127 paquets en 179s (42.5 pkt/min)
[INFO] 🔄 Reconnexion TCP #1 à 192.168.1.38:4403...
[INFO] ✅ Reconnexion TCP réussie (background)
```

### Silence-Triggered Reconnection (backup)
```
[INFO] ⚠️ SILENCE TCP: 125s sans paquet (max: 120s)
[INFO] 📊 Session stats: 89 paquets en 125s (42.7 pkt/min)
[INFO] 🔄 Forçage reconnexion TCP (silence détecté)...
```

## Configuration Examples

### Example 1: Station G2 with 2.7.15 (Recommended)

```python
# Proactive reconnection every 3 minutes
TCP_FORCE_RECONNECT_INTERVAL = 180

# Silence detection as backup
TCP_SILENT_TIMEOUT = 120

# Check every 30 seconds
TCP_HEALTH_CHECK_INTERVAL = 30
```

**Behavior:**
- Reconnects every 3 minutes proactively
- If degradation happens faster, silence detection catches it at 2 minutes
- Dual protection ensures maximum reliability

### Example 2: Stable Network (Default)

```python
# No scheduled reconnection
TCP_FORCE_RECONNECT_INTERVAL = 0

# Rely on silence detection only
TCP_SILENT_TIMEOUT = 120
TCP_HEALTH_CHECK_INTERVAL = 30
```

**Behavior:**
- Only reconnects when silence is detected
- Suitable for stable hardware/firmware

### Example 3: Very Problematic Connection

```python
# Aggressive reconnection every 2 minutes
TCP_FORCE_RECONNECT_INTERVAL = 120

# Faster silence detection
TCP_SILENT_TIMEOUT = 90

# More frequent checks
TCP_HEALTH_CHECK_INTERVAL = 15
```

**Behavior:**
- Maximum protection for problematic hardware
- More CPU overhead due to frequent checks
- Use temporarily for debugging

## Benefits

1. **Proactive Prevention**: Reconnect before issues occur
2. **Configurable**: Adjust based on hardware characteristics
3. **Backward Compatible**: Default 0 maintains existing behavior
4. **Dual Protection**: Silence detection acts as backup
5. **Independent**: Works alongside existing mechanisms
6. **Low Risk**: Optional feature, disabled by default
7. **Proven Solution**: Based on successful implementation by @Tigro14

## Drawbacks

1. **Temporary Packet Loss**: Brief interruption during reconnection (~3 seconds)
2. **Unnecessary Reconnections**: If connection is stable, reconnection is redundant
3. **Resource Usage**: Slight increase in CPU/network activity

**Recommendation:** Only enable for known problematic hardware.

## Testing

### Test Suite

Run `test_tcp_scheduled_reconnect.py` to verify:

```bash
python3 test_tcp_scheduled_reconnect.py
```

Tests:
- ✅ Scheduled reconnection disabled when set to 0
- ✅ Scheduled reconnection triggers at correct interval
- ✅ Configuration loading with getattr pattern
- ✅ Interaction with silence detection (both work independently)
- ✅ Recommended settings coherence

### Manual Testing

1. Enable scheduled reconnection:
   ```python
   TCP_FORCE_RECONNECT_INTERVAL = 120  # 2 min for faster testing
   ```

2. Start bot and monitor logs:
   ```bash
   sudo journalctl -u meshbot -f | grep -E "(programmée|Session stats)"
   ```

3. Observe scheduled reconnections every 2 minutes

4. Verify packet reception continues after reconnection

## Troubleshooting

### Issue: Too Many Reconnections

**Symptoms:**
- Reconnections every few minutes
- Packet loss during reconnections

**Diagnosis:**
- Check if scheduled interval is too aggressive

**Solution:**
```python
# Increase interval or disable
TCP_FORCE_RECONNECT_INTERVAL = 300  # 5 minutes
# or
TCP_FORCE_RECONNECT_INTERVAL = 0  # Disable
```

### Issue: Still Getting Packet Loss

**Symptoms:**
- Scheduled reconnection enabled
- Still seeing packet silence before reconnection

**Diagnosis:**
- Interval may be too long
- Check silence detection timeout

**Solution:**
```python
# Reduce scheduled interval
TCP_FORCE_RECONNECT_INTERVAL = 120  # 2 minutes

# or adjust silence timeout
TCP_SILENT_TIMEOUT = 90  # 1.5 minutes
```

### Issue: Feature Not Working

**Symptoms:**
- Configuration set but no scheduled reconnections

**Diagnosis:**
- Check configuration loading
- Verify TCP mode is active

**Solution:**
1. Check logs for config loading:
   ```
   🔧 TCP_FORCE_RECONNECT_INTERVAL configuré: 180s (reconnexion programmée activée)
   ```

2. If not present, verify `config.py` has the setting

3. Restart bot to reload configuration

## Original Working Solution (Reference)

From @Tigro14's comment #3720477966:

```python
# Works perfectly - reconnects every 3 minutes
for i in range(18):  # 18 * 10s = 3 minutes
    time.sleep(10)
    if i % 3 == 0 and i > 0:
        try:
            iface.getMyNodeInfo()  # Keepalive ping
        except: 
            break  # Reconnect if ping fails

# Force scheduled reconnect after 3 minutes
print("Scheduled reconnect...")
```

This manual implementation has been integrated into the bot as a configurable feature.

## Related Features

- **TCP_SILENT_TIMEOUT**: Maximum silence before reconnection (backup mechanism)
- **TCP_HEALTH_CHECK_INTERVAL**: How often health checks run
- Packet reception rate tracking (see `TCP_HEALTH_MONITORING_IMPROVEMENTS.md`)

## Future Enhancements

Potential improvements:
1. **Adaptive Interval**: Adjust based on observed stability
2. **Keepalive Pings**: Send periodic traffic to keep connection alive
3. **Firmware Detection**: Auto-enable for known problematic versions
4. **Telemetry**: Track effectiveness of scheduled reconnections

## References

- Original PR: #[PR_NUMBER] - TCP Health Monitoring Improvements
- Comment: #3720477966 (@Tigro14)
- Test suite: `test_tcp_scheduled_reconnect.py`
- Main implementation: `main_bot.py::tcp_health_monitor_thread()`
- Configuration: `config.py.sample`

---

**Status**: ✅ Implemented and tested
**Version**: Added in commit bab5a59
**Backward Compatible**: Yes (default disabled)
