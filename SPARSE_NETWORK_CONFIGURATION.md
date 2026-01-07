# Configuration for Sparse Mesh Networks

## Problem Description

Mesh networks with low traffic density (sparse networks) can trigger false TCP disconnect alarms when the normal gap between packets exceeds the timeout threshold.

**Example from production logs:**
```
18:22:32 Last packet received
18:25:01 SILENCE TCP: 149s sans paquet (max: 120s)
[Triggering unnecessary reconnection]
```

This is **not a bug** - it's the bot correctly detecting genuine TCP silence. However, for sparse networks, this silence is *normal* and doesn't indicate a problem.

## Root Cause

**Active networks** (typical):
- Packets every 30-60 seconds (telemetry, position updates, messages)
- 120-second timeout works well
- Quick detection of genuine disconnects

**Sparse networks**:
- Packets every 2-5 minutes (or longer)
- 120-second timeout too aggressive
- Normal traffic gaps trigger false alarms

## Solution: Adjust TCP_SILENT_TIMEOUT

### Configuration

Add to your `config.py`:

```python
# TCP silence timeout configuration
# Increase this value for sparse networks to avoid false disconnect alarms

# Default (active networks):
TCP_SILENT_TIMEOUT = 120  # 2 minutes

# Medium-sparse networks:
TCP_SILENT_TIMEOUT = 180  # 3 minutes

# Sparse networks:
TCP_SILENT_TIMEOUT = 300  # 5 minutes

# Very sparse networks:
TCP_SILENT_TIMEOUT = 600  # 10 minutes
```

### Recommendations by Network Type

| Network Type | Typical Packet Interval | Recommended Timeout | Detection Time |
|--------------|------------------------|---------------------|----------------|
| **Active** (default) | 30-60s | 120s (2 min) | ~2 minutes |
| **Medium-sparse** | 1-3 minutes | 180s (3 min) | ~3 minutes |
| **Sparse** | 3-5 minutes | 300s (5 min) | ~5 minutes |
| **Very sparse** | 5-10 minutes | 600s (10 min) | ~10 minutes |

### How to Identify Your Network Type

Monitor your logs for a few hours and look for the time between health checks showing packet activity:

```bash
journalctl -u meshbot --since "1 hour ago" | grep "Health TCP OK"
```

**Example output analysis:**
```
18:22:31 Health TCP OK: dernier paquet il y a 59s
18:23:01 Health TCP OK: dernier paquet il y a 29s  ← 30s gap (ACTIVE)
18:23:31 Health TCP OK: dernier paquet il y a 59s
```

vs

```
18:22:31 Health TCP OK: dernier paquet il y a 59s
18:23:01 Health TCP OK: dernier paquet il y a 29s
18:23:31 Health TCP OK: dernier paquet il y a 59s
18:24:01 Health TCP OK: dernier paquet il y a 89s
18:24:31 Health TCP OK: dernier paquet il y a 119s  ← 90s gap (SPARSE)
```

**Decision criteria:**
- Gaps typically < 90s → Keep 120s (default)
- Gaps typically 90-150s → Use 180s
- Gaps typically 150-240s → Use 300s
- Gaps > 240s → Use 600s or higher

## Trade-offs

### Shorter Timeout (e.g., 120s)
**Pros:**
- ✅ Faster detection of real connection issues
- ✅ Quicker recovery from genuine disconnects
- ✅ Better responsiveness

**Cons:**
- ❌ More false alarms on sparse networks
- ❌ Unnecessary reconnections
- ❌ Increased log noise

### Longer Timeout (e.g., 300s)
**Pros:**
- ✅ No false alarms on sparse networks
- ✅ Cleaner logs
- ✅ Fewer unnecessary operations

**Cons:**
- ❌ Slower detection of genuine disconnects
- ❌ Longer downtime before recovery

## Implementation

The bot now reads `TCP_SILENT_TIMEOUT` from `config.py` at startup:

```python
# In main_bot.py __init__:
import config as cfg
self.TCP_SILENT_TIMEOUT = getattr(cfg, 'TCP_SILENT_TIMEOUT', 120)
debug_print(f"🔧 TCP_SILENT_TIMEOUT configuré: {self.TCP_SILENT_TIMEOUT}s")
```

**Startup log:**
```
[DEBUG] 🔧 TCP_SILENT_TIMEOUT configuré: 300s
[INFO] 🔍 Moniteur santé TCP démarré (intervalle: 30s, silence max: 300s)
```

## Verification

After changing the configuration:

### 1. Restart the Bot
```bash
sudo systemctl restart meshbot
```

### 2. Verify Configuration Loaded
```bash
journalctl -u meshbot | grep "TCP_SILENT_TIMEOUT configuré"
# Should show: 🔧 TCP_SILENT_TIMEOUT configuré: 300s
```

### 3. Monitor Health Checks
```bash
journalctl -u meshbot -f | grep -E "Health TCP|SILENCE TCP"
```

**Expected behavior with correct timeout:**
- Regular "✅ Health TCP OK: XXs" messages
- **No** "⚠️ SILENCE TCP" messages during normal operation
- "⚠️ SILENCE TCP" **only** if truly disconnected (node down, network failure)

### 4. Long-term Monitoring
```bash
# Count reconnections in last 24 hours
journalctl -u meshbot --since "24 hours ago" | grep "Forçage reconnexion TCP" | wc -l

# Expected: 0-2 (only genuine issues)
# Too many: Timeout still too short for your network
```

## Tuning Process

1. **Start with default (120s)**: Works for most networks
2. **Monitor for 1-2 hours**: Check how often SILENCE alarms occur
3. **If false alarms**:
   - Count gaps in Health OK messages
   - Add 50% margin to longest observed gap
   - Set `TCP_SILENT_TIMEOUT` to that value
4. **Restart and monitor**: Verify no more false alarms
5. **Fine-tune if needed**: Adjust based on observed behavior

## Example Configuration

For the user experiencing 149-second gaps:

```python
# config.py

# Observed: 149s maximum gap
# Recommendation: 149s + 50% margin = 224s
# Round up to: 240s (4 minutes)
TCP_SILENT_TIMEOUT = 240

# Or be more conservative:
TCP_SILENT_TIMEOUT = 300  # 5 minutes
```

## Advanced: Dynamic Timeout (Future Enhancement)

For networks with variable traffic patterns, consider implementing dynamic timeout adjustment:

```python
# Pseudocode (not implemented yet)
def calculate_dynamic_timeout():
    recent_gaps = get_last_20_packet_gaps()
    avg_gap = statistics.mean(recent_gaps)
    p95_gap = statistics.quantile(recent_gaps, 0.95)
    
    # Set timeout to 95th percentile + 50% margin
    return int(p95_gap * 1.5)
```

This would automatically adapt to network traffic patterns.

## Summary

**The "bug" was actually correct behavior** - the bot detected genuine TCP silence.

**The solution** is configuration, not code changes:
1. Identify your network type (active vs sparse)
2. Set `TCP_SILENT_TIMEOUT` appropriately in `config.py`
3. Restart bot and verify no more false alarms

**Default 120s** works for 95% of networks. Only adjust if you're experiencing false disconnect alarms on a sparse network.
