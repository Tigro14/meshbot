# Summary: TCP Scheduled Reconnection Implementation

## What Was Done

In response to comment #3720477966 from @Tigro14, I implemented a **TCP scheduled reconnection feature** to address Meshtastic firmware 2.7.15 TCP stability issues on Station G2 nodes.

## Changes Implemented

### 1. Configuration Option (config.py.sample)
```python
TCP_FORCE_RECONNECT_INTERVAL = 0  # 0=disabled, 180=every 3min (recommended)
```

- **Default**: 0 (disabled) - maintains backward compatibility
- **Recommended**: 180s (3 minutes) for Station G2 with firmware 2.7.15
- **Alternative**: 300s (5 minutes) for more conservative approach

### 2. Implementation (main_bot.py)

**Changes:**
- Load `TCP_FORCE_RECONNECT_INTERVAL` from config (lines 72-77)
- Initialize `_last_forced_reconnect` tracking variable (line 150)
- Add scheduled reconnection logic in `tcp_health_monitor_thread()` (lines 1043-1058)
- Reset timer on successful reconnection (line 854)

**Logic:**
```python
if TCP_FORCE_RECONNECT_INTERVAL > 0:
    time_since_last = time.time() - self._last_forced_reconnect
    if time_since_last >= TCP_FORCE_RECONNECT_INTERVAL:
        # Log session stats
        # Trigger reconnection
        # Reset timer
```

### 3. Test Suite (test_tcp_scheduled_reconnect.py)

**New test file with 5 test cases:**
- ✅ Scheduled reconnection disabled when set to 0
- ✅ Scheduled reconnection triggers at correct interval
- ✅ Configuration loading with getattr pattern
- ✅ Interaction with silence detection (both work independently)
- ✅ Recommended settings coherence

**All tests passing.**

### 4. Documentation (TCP_SCHEDULED_RECONNECTION.md)

**Comprehensive 10KB documentation covering:**
- Problem statement and solution
- Configuration guide with recommended settings
- How it works (dual protection mechanism)
- Timeline examples comparing with/without feature
- Log output examples
- Multiple configuration scenarios
- Benefits and drawbacks
- Testing instructions
- Troubleshooting guide

## How It Works

### Dual Protection Mechanism

The bot now has **two independent reconnection triggers**:

1. **Scheduled Reconnection** (NEW): Proactively reconnects every `TCP_FORCE_RECONNECT_INTERVAL` seconds
2. **Silence Detection** (existing): Reconnects after `TCP_SILENT_TIMEOUT` seconds without packets

**Whichever triggers first will cause reconnection.**

### Example: Station G2 with Recommended Settings

```python
TCP_FORCE_RECONNECT_INTERVAL = 180  # 3 minutes
TCP_SILENT_TIMEOUT = 120            # 2 minutes (backup)
TCP_HEALTH_CHECK_INTERVAL = 30      # Check every 30s
```

**Normal Operation:**
- Scheduled reconnection triggers every 3 minutes proactively
- Prevents TCP degradation before it causes packet loss
- Silence detection acts as backup if degradation happens faster

**Timeline:**
```
0:00  Connection established
0:30  Health check: OK (60 pkt/min)
1:00  Health check: OK (58 pkt/min)
1:30  Health check: OK (61 pkt/min)
2:00  Health check: OK (59 pkt/min)
2:30  Health check: OK (57 pkt/min)
3:00  🔄 Scheduled reconnection triggered
3:01  Connection re-established
3:30  Health check: OK (62 pkt/min)
...repeats every 3 minutes
```

## Files Changed

| File | Lines Changed | Description |
|------|---------------|-------------|
| `config.py.sample` | +11 | New configuration option with documentation |
| `main_bot.py` | +31 | Implementation of scheduled reconnection |
| `test_tcp_scheduled_reconnect.py` | +195 | Comprehensive test suite (NEW) |
| `TCP_SCHEDULED_RECONNECTION.md` | +330 | Feature documentation (NEW) |

**Total**: 4 files, +567 lines

## Testing Results

### Automated Tests
```
============================================================
TCP Scheduled Reconnection - Test Suite
============================================================

Testing scheduled reconnection disabled (TCP_FORCE_RECONNECT_INTERVAL=0)...
✅ PASS: Scheduled reconnection properly disabled

Testing scheduled reconnection enabled (TCP_FORCE_RECONNECT_INTERVAL=180)...
✅ PASS: Scheduled reconnection works correctly

Testing configuration loading...
✅ PASS: Configuration loading works

Testing interaction with silence detection...
✅ PASS: Both mechanisms work independently

Testing recommended settings for Station G2...
✅ PASS: Recommended settings are coherent

============================================================
✅ All tests passed!
============================================================
```

### Manual Verification
- ✅ Configuration loads correctly with default (0)
- ✅ Configuration loads correctly with custom value (180)
- ✅ Logging shows when feature is enabled/disabled
- ✅ Dual protection mechanism logic is sound
- ✅ Timer resets on successful reconnection

## Benefits

1. **Proactive Prevention**: Reconnects before TCP degradation occurs
2. **Configurable**: Users adjust based on their hardware
3. **Backward Compatible**: Default 0 maintains existing behavior
4. **Dual Protection**: Silence detection acts as backup
5. **Independent**: Works alongside existing mechanisms
6. **Low Risk**: Optional feature, disabled by default
7. **Proven Solution**: Based on working implementation from @Tigro14
8. **Well Tested**: Comprehensive test suite
9. **Well Documented**: 10KB of documentation

## Risk Assessment

**Risk Level**: 🟢 **LOW**

**Why:**
- ✅ Optional feature (disabled by default)
- ✅ No changes to existing behavior when disabled
- ✅ Independent of other mechanisms
- ✅ Well-tested with comprehensive test suite
- ✅ Based on proven working solution
- ✅ Comprehensive documentation
- ✅ Easy to disable if issues occur

## Commits

1. **bab5a59** - Add TCP scheduled reconnection feature (TCP_FORCE_RECONNECT_INTERVAL)
2. **52a3fc9** - Add documentation for TCP scheduled reconnection feature

## Response to Comment

**Comment #3720477966** from @Tigro14:
- ✅ Implemented suggested scheduled reconnection
- ✅ Made it configurable (TCP_FORCE_RECONNECT_INTERVAL)
- ✅ Default: 0 (disabled)
- ✅ Recommended: 180s (3 minutes) for Station G2
- ✅ Replied to comment with implementation details

## Usage

### For Station G2 with Firmware 2.7.15

Add to `config.py`:
```python
# Enable scheduled reconnection for Station G2
TCP_FORCE_RECONNECT_INTERVAL = 180  # Reconnect every 3 minutes
```

Restart bot:
```bash
sudo systemctl restart meshbot
```

Monitor logs:
```bash
sudo journalctl -u meshbot -f | grep -E "(programmée|Session stats)"
```

Expected output every 3 minutes:
```
[INFO] 🔄 Reconnexion TCP programmée (intervalle: 180s)
[INFO] 📊 Session stats: 127 paquets en 179s (42.5 pkt/min)
```

### For Stable Networks

No changes needed - feature is disabled by default.

## Next Steps

### For Users
1. Review `TCP_SCHEDULED_RECONNECTION.md` for detailed documentation
2. If using Station G2 with 2.7.15, add configuration:
   ```python
   TCP_FORCE_RECONNECT_INTERVAL = 180
   ```
3. Monitor logs to verify stable operation
4. Adjust interval if needed based on observations

### For Developers
1. Monitor effectiveness in production
2. Consider adaptive interval based on observed stability
3. Consider keepalive pings as alternative approach
4. Track metrics to measure improvement

## Conclusion

Successfully implemented TCP scheduled reconnection feature as requested by @Tigro14. The feature:
- ✅ Addresses Meshtastic 2.7.15 TCP issues on Station G2
- ✅ Is configurable and backward compatible
- ✅ Is well-tested and documented
- ✅ Provides dual protection with silence detection
- ✅ Is based on proven working solution
- ✅ Ready for production use

**Status**: ✅ COMPLETE
**Commits**: bab5a59, 52a3fc9
**Tests**: All passing
**Documentation**: Complete
**Risk**: Low
**Ready**: For merge

---

_Implementation completed on 2026-01-07 in response to comment #3720477966_
