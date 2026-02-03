# Pull Request: TCP Health Monitoring Improvements

## Summary

This PR addresses TCP stability issues where the bot reconnects every ~2 minutes due to packet silence, despite the network having high traffic. The changes add **configurable TCP health monitoring** and **comprehensive packet reception diagnostics** to help detect, diagnose, and recover from TCP connection issues faster.

## Problem Statement

After upgrading Meshtastic node (tigrog2) to firmware 2.7.15, the bot experiences:

- ✅ Socket appears "connected"
- ✅ Packets flow normally for ~2 minutes
- ❌ Packet reception suddenly stops (silence)
- ❌ After 120 seconds, bot triggers reconnection
- ✅ After reconnection, packets flow again
- 🔄 Cycle repeats continuously

**Expected**: ~60 packets/minute (1 packet/second)
**Actual**: Packets stop after ~2 minutes, requiring reconnection

## Root Cause (Hypothesis)

Three potential causes identified:

1. **ESP32 Firmware 2.7.15 TCP Bug** - New firmware may have TCP stack issues
2. **ESP32 Resource Exhaustion** - Memory/buffer overflow on high packet rate
3. **Python Library Issue** - Meshtastic `__reader` thread gets stuck

## Solution Implemented

### 1. Configurable TCP Health Check Interval ✅

**Before:**
```python
# Hardcoded in class
TCP_HEALTH_CHECK_INTERVAL = 30  # Can't change without modifying code
```

**After:**
```python
# In config.py
TCP_HEALTH_CHECK_INTERVAL = 30  # User can adjust

# In main_bot.py
self.TCP_HEALTH_CHECK_INTERVAL = getattr(cfg, 'TCP_HEALTH_CHECK_INTERVAL', 30)
```

**Benefits:**
- Users can adjust without code changes
- Faster detection: 15s for quick recovery
- Slower checks: 60s for resource-constrained systems
- Default: 30s (backward compatible)

### 2. Packet Reception Rate Tracking ✅

**New Functionality:**
```python
# Track last 100 packet timestamps
self._packet_timestamps = deque(maxlen=100)

# Calculate packets/minute over 60s window
def _get_packet_reception_rate(self, window_seconds=60):
    # Returns packets/minute
```

**Log Output:**
```
✅ Health TCP OK: dernier paquet il y a 15s (débit: 58.3 pkt/min)
```

**Benefits:**
- See actual packet rates in logs
- Identify gradual slowdown vs sudden stop
- Understand network behavior over time

### 3. Session Statistics ✅

**New Functionality:**
```python
# Per-session tracking
self._packets_this_session = 0
self._session_start_time = time.time()

def _get_session_stats(self):
    # Returns packets, duration, rate
```

**Log Output:**
```
⚠️ SILENCE TCP: 140s sans paquet (max: 120s)
📊 Session stats: 127 paquets en 135s (56.4 pkt/min)
```

**Benefits:**
- See how many packets before failure
- Calculate average session rate
- Reset counters on reconnection

### 4. Enhanced Diagnostic Logging ✅

**What's New:**
- Packet rate in every health check
- Session stats when reconnection triggered
- Clear differentiation of issue types
- Reset notification on new session

## Files Changed

| File | Changes | Description |
|------|---------|-------------|
| `config.py.sample` | +11 lines | Added `TCP_HEALTH_CHECK_INTERVAL` config option |
| `main_bot.py` | +81 lines, -6 lines | Added rate tracking, session stats, enhanced logging |
| `test_tcp_health_improvements.py` | +144 lines (new) | Test suite for new functionality |
| `TCP_HEALTH_MONITORING_IMPROVEMENTS.md` | +363 lines (new) | Comprehensive documentation |
| `CLAUDE.md` | +16 lines | Updated recent changes section |

**Total**: +615 lines added, -6 lines removed

## Testing

### Automated Tests ✅

```bash
$ python3 test_tcp_health_improvements.py
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

### Manual Testing Checklist

- [ ] Bot starts without errors with new config
- [ ] Health check logs show packet rate
- [ ] Session stats appear on reconnection
- [ ] Counters reset after reconnection
- [ ] Configuration loading works with defaults
- [ ] Configuration loading works with custom values

## Usage

### Basic Configuration

```python
# config.py
TCP_SILENT_TIMEOUT = 120  # Max silence before reconnect
TCP_HEALTH_CHECK_INTERVAL = 30  # Check frequency
```

### For Faster Detection (Current Issue)

```python
# config.py
TCP_SILENT_TIMEOUT = 90  # Faster recovery (90s instead of 120s)
TCP_HEALTH_CHECK_INTERVAL = 15  # More frequent checks
```

### For Sparse Networks

```python
# config.py
TCP_SILENT_TIMEOUT = 300  # Avoid false positives
TCP_HEALTH_CHECK_INTERVAL = 60  # Reduce overhead
```

## Log Examples

### Normal Operation
```
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 15s (débit: 58.3 pkt/min)
```

### Gradual Slowdown (Resource Exhaustion)
```
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 10s (débit: 45.2 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 25s (débit: 30.1 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 40s (débit: 18.5 pkt/min)
```

### Sudden Stop (TCP Bug)
```
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 20s (débit: 62.1 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 50s (débit: 61.8 pkt/min)
[DEBUG] ✅ Health TCP OK: dernier paquet il y a 80s
[INFO] ⚠️ SILENCE TCP: 140s sans paquet (max: 120s)
```

## Benefits

### For Users 👥
1. **Configurable Monitoring** - Adjust health check frequency without code changes
2. **Better Diagnostics** - See actual packet rates in logs
3. **Faster Recovery** - Reduce check interval for quicker detection
4. **Root Cause Analysis** - Differentiate between issue types
5. **Network Profiling** - Understand typical vs problematic patterns

### For Developers 🔧
6. **Data-Driven Debugging** - Packet rate metrics help identify patterns
7. **ESP32 Characterization** - Analyze if 2.7.15 has systematic issues
8. **Foundation for Future** - Base for adaptive health checks
9. **Upstream Bug Reports** - Collect data to report to Meshtastic
10. **Maintainability** - Clean, documented, tested code

## Breaking Changes

❌ **None** - All changes are backward compatible:
- Default values preserved (30s check, 120s timeout)
- New config options have fallback defaults
- Existing logs unchanged (new info added only)
- No API changes to existing methods

## Migration Guide

### Existing Users
1. Update `config.py.sample` to `config.py` (or add new options)
2. Optionally adjust `TCP_HEALTH_CHECK_INTERVAL` if needed
3. No code changes required - works out of box

### New Features (Optional)
```python
# Add to config.py for customization
TCP_HEALTH_CHECK_INTERVAL = 30  # Adjust as needed
```

## Documentation

### New Documents
- `TCP_HEALTH_MONITORING_IMPROVEMENTS.md` - Complete guide (10KB)
  - Problem summary
  - Root cause hypothesis
  - Solution details
  - Configuration guide
  - Log interpretation
  - Troubleshooting
  - Testing instructions

### Updated Documents
- `CLAUDE.md` - Added to "Recent Architectural Changes"

## Future Improvements

Ideas for follow-up work:

1. **Proactive Health Checks** - Send ping/heartbeat to ESP32
2. **Adaptive Timeouts** - Auto-adjust based on network characteristics
3. **ESP32 Resource Monitoring** - Query memory/buffer stats
4. **Historical Analysis** - Store session stats in database
5. **Meshtastic Library Improvements** - Watchdog for __reader thread

## Checklist

- [x] Code implemented and tested
- [x] Tests passing
- [x] Configuration added to sample config
- [x] Documentation written
- [x] CLAUDE.md updated
- [x] No breaking changes
- [x] Backward compatible
- [x] Ready for review

## Recommendations for Deployment

1. **Monitor logs** for 24-48 hours after deployment
2. **Collect packet rate data** to identify patterns
3. **Adjust timeouts** if needed based on observations
4. **Report to Meshtastic** if firmware bug confirmed

## Related Issues

- Meshtastic firmware 2.7.15 TCP behavior
- ESP32 resource constraints
- Python meshtastic library blocking recv()
- TCP keepalive limitations

## Questions for Reviewer

1. Should we make `TCP_SILENT_TIMEOUT` more aggressive by default (e.g., 90s)?
2. Should we log session stats even on successful connections (periodically)?
3. Should we implement proactive ping/heartbeat in this PR or separate PR?

---

**Ready for Review** ✅

This PR provides immediate improvements while maintaining full backward compatibility. It gives users the tools to diagnose and adapt to TCP stability issues, with a foundation for future enhancements.
