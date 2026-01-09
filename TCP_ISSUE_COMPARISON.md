# TCP Issue Analysis - False Alarm vs Real Connection Failure

## Issue #1: False Alarm (FIXED by our PR)

### Symptoms
```
Jan 07 20:15:53 ✅ Health TCP OK: dernier paquet il y a 89s
Jan 07 20:16:08 ⚠️ SILENCE TCP: 104s sans paquet (max: 90s) ← FALSE ALARM
Jan 07 20:16:08 🔄 Forçage reconnexion TCP (silence détecté)...
```

### Root Cause
- Configuration: `TCP_HEALTH_CHECK_INTERVAL=15s`, `TCP_SILENT_TIMEOUT=90s`
- Integer ratio (6.0×) causing detection latency
- Packets arriving but detected 15s late due to timing mismatch

### Fix Applied
✅ Configuration validation warns users about integer ratios
✅ Recommends `TCP_SILENT_TIMEOUT=98s` or `120s` to avoid false alarms

---

## Issue #2: Real Connection Failure (CURRENT PROBLEM)

### Symptoms
```
Jan 07 21:39:50 ✅ Health TCP OK: dernier paquet il y a 177s
Jan 07 21:40:00 Unexpected OSError, terminating meshtastic reader... [Errno 104] Connection reset by peer
Jan 07 21:40:08 🔄 Reconnexion TCP programmée (intervalle: 300s)
```

### Root Cause
- **Real TCP socket error** from ESP32 node
- Connection drops after ~5 minutes (300-305s)
- Not a timing issue - the socket actually dies
- "Connection reset by peer" = ESP32 closed the connection

### Analysis
Based on your logs:
- Health check interval: **18 seconds** (not 15s)
- Silent timeout: **≥180 seconds** (silence went to 177s without triggering)
- TCP_FORCE_RECONNECT_INTERVAL: **300 seconds** (5 minutes)

**Problem:** Your ESP32 node closes connections after ~5 minutes. This is likely:
1. Firmware bug in Meshtastic 2.7.15 (known issue with Station G2)
2. TCP keepalive timeout on ESP32 side
3. Memory pressure causing connection drops

### Validation Check

Your current config (estimated):
```
TCP_HEALTH_CHECK_INTERVAL = 18s
TCP_SILENT_TIMEOUT = 180s  # Or 240s
```

This would be **flagged as RISKY** by our validation:
- Ratio: 180/18 = 10.0 (integer)
- Detection latency: 18s
- Reason: Fast interval (<20s) with integer ratio

However, the validation warning is **not the cause** of your connection failures. The OSError is a real hardware/firmware issue.

---

## Solutions for Issue #2

### Option 1: Work Around ESP32 Instability (Current)
```python
TCP_FORCE_RECONNECT_INTERVAL = 180  # Reconnect every 3 minutes
```
**Pro:** Reconnects before ESP32 crashes  
**Con:** Wastes bandwidth, doesn't fix root cause

### Option 2: Fix Configuration + Let Silence Detect Failures
```python
TCP_HEALTH_CHECK_INTERVAL = 30  # Standard interval
TCP_SILENT_TIMEOUT = 120        # Standard timeout
TCP_FORCE_RECONNECT_INTERVAL = 0  # Disable scheduled reconnection
```
**Pro:** Only reconnects on real failures  
**Con:** If ESP32 keeps crashing, you'll see reconnections every ~2-3 min

### Option 3: Fix Configuration + Tolerate ESP32 Instability
```python
TCP_HEALTH_CHECK_INTERVAL = 30  # Standard interval
TCP_SILENT_TIMEOUT = 240        # Higher tolerance
TCP_FORCE_RECONNECT_INTERVAL = 240  # Reconnect every 4 min
```
**Pro:** Balance between responsiveness and stability  
**Con:** Slower to detect real failures

### Option 4: Investigate ESP32 Root Cause
- Check ESP32 logs for memory issues
- Verify firmware version (upgrade if available)
- Monitor ESP32 uptime and resource usage
- Check if WiFi connection is stable
- Consider hardware reset/power cycle

---

## Summary

| Aspect | False Alarm (Fixed) | Connection Failure (Current) |
|--------|---------------------|------------------------------|
| **Error Type** | Logic/timing race condition | Real TCP socket error |
| **Log Message** | "SILENCE TCP: 104s" | "Connection reset by peer" |
| **Cause** | Integer ratio config | ESP32 firmware/hardware issue |
| **Fix** | Adjust timeout value | Fix ESP32 or work around |
| **Our PR** | ✅ Prevents this | ❌ Can't prevent this |

The validation code we added **would have prevented your original false alarm issue** (15s/90s config). The current issue is a **different problem** requiring ESP32-side investigation.

---

## Recommended Next Steps

1. **Check your `config.py`:**
   ```bash
   grep -E "TCP_HEALTH_CHECK_INTERVAL|TCP_SILENT_TIMEOUT|TCP_FORCE_RECONNECT_INTERVAL" config.py
   ```

2. **Choose a stable configuration:**
   - If keeping 18s interval: use `TCP_SILENT_TIMEOUT = 126s` (7.0× ratio with margin)
   - Or switch to defaults: `30s interval / 120s timeout`

3. **Monitor ESP32 health:**
   - Check ESP32 logs for crashes/reboots
   - Monitor WiFi signal strength
   - Check for firmware updates

4. **Test without scheduled reconnection:**
   - Set `TCP_FORCE_RECONNECT_INTERVAL = 0`
   - Let silence detection handle failures
   - See how often real failures occur

The validation code is working as designed - it will warn you about integer ratio configurations that cause false alarms. But it can't prevent real hardware/firmware failures.
