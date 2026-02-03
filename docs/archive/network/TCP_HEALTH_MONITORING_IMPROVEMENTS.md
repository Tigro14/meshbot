# TCP Health Monitoring Improvements

## Problem Summary

After upgrading the Meshtastic node (tigrog2) to firmware **2.7.15**, the bot experiences packet reception issues where:

1. Connection appears healthy (socket is "connected")
2. Packets flow normally for ~2 minutes
3. Packet reception suddenly stops (silence)
4. After 120 seconds of silence, bot triggers reconnection
5. After reconnection, packets flow again for ~2 minutes
6. Cycle repeats continuously

**Expected behavior**: Local network should receive ~1 packet/second (60 packets/minute) given the network activity and node placement.

**Actual behavior**: Packets stop flowing after ~2 minutes despite socket appearing connected.

## Root Cause Hypothesis

The issue likely stems from one of these causes:

### 1. ESP32 Firmware 2.7.15 TCP Bug
- New firmware version may have TCP stack issues
- ESP32 stops forwarding packets over TCP after certain conditions
- Reconnection "resets" the issue temporarily

### 2. ESP32 Resource Exhaustion
- Memory or buffer overflow in ESP32
- High packet rate overwhelms the node
- Connection gets "stuck" until reset

### 3. Python Meshtastic Library Issue
- `__reader` thread in meshtastic library gets stuck
- Blocking recv() call stops responding
- Thread doesn't detect socket death

## Implemented Solution

This PR adds **configurable TCP health monitoring** and **packet reception diagnostics** to help:
1. **Detect issues faster** (configurable check interval)
2. **Diagnose root cause** (packet rate tracking)
3. **Provide actionable data** (session statistics)

### Changes Made

#### 1. Configurable Health Check Interval

**Before:** Hardcoded 30-second check interval in class constant
```python
TCP_HEALTH_CHECK_INTERVAL = 30  # Fixed in code
```

**After:** Configurable via config.py
```python
# config.py
TCP_HEALTH_CHECK_INTERVAL = 30  # User can adjust

# main_bot.py
self.TCP_HEALTH_CHECK_INTERVAL = getattr(cfg, 'TCP_HEALTH_CHECK_INTERVAL', 30)
```

**Benefits:**
- Users can adjust without modifying code
- Faster detection with lower intervals (e.g., 15s)
- Reduced overhead for constrained systems (e.g., 60s)

#### 2. Packet Reception Rate Tracking

**New functionality:**
- Track last 100 packet timestamps in circular buffer (deque)
- Calculate packets/minute over sliding 60-second window
- Display rate in health check logs

**Implementation:**
```python
# Track packets
self._packet_timestamps = deque(maxlen=100)
self._packets_this_session = 0
self._session_start_time = time.time()

# Calculate rate
def _get_packet_reception_rate(self, window_seconds=60):
    # Count packets in time window
    # Calculate rate in packets/minute
```

**Log Output:**
```
✅ Health TCP OK: dernier paquet il y a 15s (débit: 58.3 pkt/min)
```

#### 3. Session Statistics

**New functionality:**
- Track packets received per TCP session
- Calculate average rate for entire session
- Log stats when reconnection is triggered

**Log Output:**
```
⚠️ SILENCE TCP: 140s sans paquet (max: 120s)
📊 Session stats: 127 paquets en 135s (56.4 pkt/min)
```

#### 4. Enhanced Diagnostics

**What's tracked:**
- Total packets per session
- Session duration
- Average session rate
- Recent packet rate (60s window)
- Time since last packet

**Reset on reconnection:**
- All counters reset when new TCP session starts
- Provides clean metrics per connection

## Configuration Guide

### config.py Options

```python
# ========================================
# TCP HEALTH MONITORING
# ========================================

# Maximum time without packets before forcing reconnection
TCP_SILENT_TIMEOUT = 120  # seconds (2 minutes)

# Frequency of health checks
TCP_HEALTH_CHECK_INTERVAL = 30  # seconds
```

### Recommended Settings

| Network Type | TCP_SILENT_TIMEOUT | TCP_HEALTH_CHECK_INTERVAL | Why |
|--------------|-------------------|---------------------------|-----|
| **Active** (1+ pkt/sec) | 120s | 15s | Fast detection, frequent traffic |
| **Moderate** (1 pkt/min) | 180s | 30s | Balance between detection and overhead |
| **Sparse** (<1 pkt/5min) | 300s | 60s | Avoid false positives in quiet networks |
| **Debugging** | 120s | 10s | Maximum detection speed |

### For the Current Issue

Given the symptoms (should have 60 pkt/min but gets silence), try:

```python
TCP_SILENT_TIMEOUT = 90  # Reduce to 90s for faster recovery
TCP_HEALTH_CHECK_INTERVAL = 15  # Check every 15s for faster detection
```

This provides:
- Faster detection (15s instead of 30s checks)
- Faster recovery (90s timeout instead of 120s)
- More frequent rate measurements
- Better diagnostic data

## Interpreting Logs

### Normal Operation
```
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 15s (débit: 58.3 pkt/min)
```
- Receiving packets regularly
- Rate close to expected (~60 pkt/min for active network)
- All is well

### Gradual Slowdown
```
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 10s (débit: 45.2 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 25s (débit: 30.1 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 40s (débit: 18.5 pkt/min)
```
- Rate gradually decreasing
- Suggests ESP32 resource exhaustion or congestion
- Connection degrading before complete failure

### Sudden Stop
```
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 20s (débit: 62.1 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 50s (débit: 61.8 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 80s
```
- Rate normal, then packets stop completely
- Suggests TCP stack bug or thread hang
- No warning, sudden failure

### Reconnection Triggered
```
[INFO] ⚠️ SILENCE TCP: 140s sans paquet (max: 120s)
[INFO] 📊 Session stats: 127 paquets en 135s (56.4 pkt/min)
[INFO] 🔄 Forçage reconnexion TCP (silence détecté)...
```
- Shows how many packets were received before failure
- Session rate helps identify if it was always low or degraded
- Triggers automatic recovery

## Troubleshooting Guide

### Issue: Frequent Reconnections Every 2 Minutes

**Symptoms:**
- Reconnection every ~120 seconds
- Should have high packet rate but getting silence
- Pattern repeats consistently

**Diagnosis:**
1. Check session stats in logs - what was the rate before silence?
2. If rate was high (50+ pkt/min), then sudden stop → likely TCP bug
3. If rate was low or declining → likely resource exhaustion

**Actions:**
- **Short-term**: Reduce `TCP_HEALTH_CHECK_INTERVAL` to 15s for faster recovery
- **Medium-term**: Collect diagnostic data over 24h
- **Long-term**: Report to Meshtastic if firmware bug confirmed

### Issue: False Positives (Reconnects on Quiet Network)

**Symptoms:**
- Reconnections in sparse network
- Low packet rate is normal for network
- Unnecessary reconnection cycles

**Diagnosis:**
- Check if `TCP_SILENT_TIMEOUT` is too aggressive
- Look at session stats - is rate consistently low?

**Actions:**
- Increase `TCP_SILENT_TIMEOUT` to 180s or 300s
- Increase `TCP_HEALTH_CHECK_INTERVAL` to 60s to reduce overhead

### Issue: Slow Detection of Real Problems

**Symptoms:**
- Long time before reconnection triggered
- Missed packets during silence period

**Diagnosis:**
- Check interval is too long

**Actions:**
- Decrease `TCP_HEALTH_CHECK_INTERVAL` to 15s or 10s
- Keep `TCP_SILENT_TIMEOUT` at reasonable level (90-120s)

## Data Collection for Bug Reports

If you suspect a Meshtastic 2.7.15 firmware bug, collect this data:

```bash
# Enable debug logging
DEBUG_MODE = True  # in config.py

# Run for 24 hours and collect logs
sudo journalctl -u meshbot -f > tcp_diagnostics.log

# Look for patterns:
grep "Health TCP OK" tcp_diagnostics.log | tail -100
grep "Session stats" tcp_diagnostics.log
grep "SILENCE TCP" tcp_diagnostics.log
```

**Data to report:**
1. Firmware version (2.7.15)
2. Hardware model (e.g., Heltec V3)
3. Session stats before each failure
4. Pattern: gradual slowdown vs sudden stop
5. Frequency of reconnections
6. Network characteristics (active vs sparse)

## Testing

Run the test suite to verify functionality:

```bash
python3 test_tcp_health_improvements.py
```

Expected output:
```
============================================================
TCP Health Monitoring Improvements - Test Suite
============================================================

Testing packet rate calculation...
✅ Rate with 60 packets in 60s: 61.0 pkt/min (expected: ~60)
✅ Rate with 30 packets in 60s: 31.1 pkt/min (expected: ~30)
✅ Rate with 10 packets in 10s: 66.7 pkt/min (expected: ~60)

Testing session statistics...
✅ Session: 120 packets in 120s
✅ Session rate: 60.0 pkt/min (expected: ~60)
✅ Low traffic session: 50 packets in 300s
✅ Session rate: 10.0 pkt/min (expected: ~10)

Testing configuration loading...
✅ TCP_SILENT_TIMEOUT: 120s
✅ TCP_HEALTH_CHECK_INTERVAL: 30s
✅ Default fallback works: 999 (expected: 999)

============================================================
✅ All tests passed!
============================================================
```

## Future Improvements

### Potential Enhancements

1. **Proactive Health Checks**
   - Send periodic ping/heartbeat to ESP32
   - Detect stuck connection before full timeout
   - Faster recovery without waiting for silence period

2. **Adaptive Timeouts**
   - Automatically adjust timeouts based on network characteristics
   - Learn normal packet rate and detect anomalies
   - Self-tuning thresholds

3. **ESP32 Resource Monitoring**
   - Query ESP32 memory/buffer stats if API available
   - Detect resource exhaustion proactively
   - Log correlation with packet loss

4. **Historical Analysis**
   - Store session stats in database
   - Analyze patterns over days/weeks
   - Identify time-of-day or load-related patterns

5. **Meshtastic Library Improvements**
   - Add watchdog for __reader thread
   - Implement non-blocking recv with timeout
   - Better socket death detection

## Related Issues

- **Meshtastic Firmware**: May have TCP stack bug in 2.7.15
- **ESP32 Resources**: Limited memory/buffers for high traffic
- **Python Library**: Blocking recv() may miss socket death
- **TCP Keepalive**: Not sufficient for detecting stuck connections

## References

- TCP_ARCHITECTURE.md - Network stack design
- main_bot.py - Implementation details
- config.py.sample - Configuration options
- test_tcp_health_improvements.py - Test suite
