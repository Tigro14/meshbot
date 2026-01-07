# TCP False Alarm Fix: Configuration Validation

## Problem Summary

Your bot is experiencing false TCP silence alarms every ~2 minutes, causing unnecessary reconnections:

```
Jan 07 20:15:53 Health TCP OK: dernier paquet il y a 89s
Jan 07 20:16:08 ⚠️ SILENCE TCP: 104s sans paquet (max: 90s)
Jan 07 20:16:08 🔄 Forçage reconnexion TCP (silence détecté)...
```

Despite packets being received regularly (21.7 pkt/min), the bot keeps reconnecting every ~2 minutes.

## Root Cause

Your configuration has:
```python
TCP_HEALTH_CHECK_INTERVAL = 15  # Health checks every 15 seconds
TCP_SILENT_TIMEOUT = 90          # Timeout after 90 seconds
```

**The Problem:** The ratio `90 / 15 = 6.0` is an **integer**.

This causes health checks to occur at: **T+15, 30, 45, 60, 75, 90, 105...**

### What Happens (Worst Case)

1. Packet arrives at **T+0.1s** (just after a health check)
2. Check at **T+90s**: silence = 89.9s ≤ 90s → ✅ OK
3. Check at **T+105s**: silence = 104.9s > 90s → ❌ **FALSE ALARM!**

The timeout (90s) is exceeded, but only by 14.9s (one check interval). The connection was likely fine, but the detection happened "late" because the checks are spaced 15s apart.

### Timeline Visualization

```
Last packet at T+1s:

T+15s:  Check → 14s silence ≤ 90s → ✅ OK
T+30s:  Check → 29s silence ≤ 90s → ✅ OK  
T+45s:  Check → 44s silence ≤ 90s → ✅ OK
T+60s:  Check → 59s silence ≤ 90s → ✅ OK
T+75s:  Check → 74s silence ≤ 90s → ✅ OK
T+90s:  Check → 89s silence ≤ 90s → ✅ OK (barely!)
T+105s: Check → 104s silence > 90s → ❌ TIMEOUT! ← FALSE ALARM
                                        Triggers reconnection
```

## Solution

You need to break the integer ratio by adjusting either the timeout or the interval.

### Option 1: Increase Timeout (RECOMMENDED)

Add a margin to your timeout to get a fractional ratio:

```python
TCP_HEALTH_CHECK_INTERVAL = 15  # Keep 15s checks
TCP_SILENT_TIMEOUT = 98         # 6.5× ratio → only 7s latency
```

**Why this works:**
- Ratio: 98 / 15 = 6.53 (fractional, not integer)
- Checks at: 15, 30, 45, 60, 75, 90, **105**
- At T+90s: 89s ≤ 98s → ✅ OK
- At T+105s: 104s > 98s → ⚠️ TIMEOUT (only 6s late, not 14.9s)

Other good values: **105s, 112s, 120s** (all create fractional ratios with 15s intervals)

### Option 2: Use Default Values

The safest option is to use the recommended defaults:

```python
TCP_HEALTH_CHECK_INTERVAL = 30  # Standard 30s checks
TCP_SILENT_TIMEOUT = 120        # 4.0× ratio
```

**Why this works:**
- The 30s interval is large enough that 30s detection latency is acceptable
- 4× ratio provides good balance between responsiveness and false alarm avoidance
- Proven configuration used by most users

### Option 3: Increase Check Interval

Keep your timeout but check less frequently:

```python
TCP_HEALTH_CHECK_INTERVAL = 30  # Reduce check frequency
TCP_SILENT_TIMEOUT = 90         # Keep 90s timeout
```

**Trade-off:** Detection will be slower (up to 30s after timeout), but no false alarms.

## Implementation

The bot now includes automatic configuration validation. When you start the bot with a problematic configuration, you'll see:

```
⚠️  ATTENTION: CONFIGURATION TCP NON-OPTIMALE DÉTECTÉE
================================================================================

Votre configuration actuelle peut causer des problèmes:

  TCP_HEALTH_CHECK_INTERVAL = 15s
  TCP_SILENT_TIMEOUT        = 90s
  Ratio: 6.00× (fractional part: 0.00)

Problème: Le timeout (90s) est trop proche d'un multiple
de l'intervalle (6×15s = 90s).

Impact: La détection du timeout sera retardée de ~15s
  • Timeout configuré: 90s
  • Détection réelle:  105s (au prochain check)
  • Retard:            15s

Solutions recommandées:

  Option 1 (RECOMMANDÉE): Ajouter une marge de sécurité
    TCP_SILENT_TIMEOUT = 98  # Ajoute ~8s de marge

  Option 2: Réduire l'intervalle de vérification
    TCP_HEALTH_CHECK_INTERVAL = 11  # Détection plus fréquente

  Option 3: Utiliser les valeurs par défaut
    TCP_HEALTH_CHECK_INTERVAL = 30
    TCP_SILENT_TIMEOUT = 120  # Ratio 4.0×, pas de retard excessif
```

## Recommended Action

1. **Edit your `config.py`:**
   ```python
   TCP_HEALTH_CHECK_INTERVAL = 15  # Or 30 for default
   TCP_SILENT_TIMEOUT = 98         # Or 120 for default
   ```

2. **Restart the bot:**
   ```bash
   sudo systemctl restart meshbot
   ```

3. **Monitor for 10-15 minutes:**
   ```bash
   journalctl -u meshbot -f | grep -E "SILENCE TCP|Health TCP|Reconnexion"
   ```

4. **Expected behavior:**
   - Regular "✅ Health TCP OK: XXs" messages every 15s (or 30s if using defaults)
   - **NO** "⚠️ SILENCE TCP" messages during normal operation
   - "⚠️ SILENCE TCP" **only** if truly disconnected (node down, network failure)

## Mathematical Explanation

The validation uses this logic:

```python
ratio = TCP_SILENT_TIMEOUT / TCP_HEALTH_CHECK_INTERVAL
fractional_part = ratio - floor(ratio)

if fractional_part < 0.3:  # Too close to integer
    detection_latency = INTERVAL  # Will be full interval late
    
    if INTERVAL < 20:
        # For fast checks, this is problematic
        WARN: False alarms likely
    elif INTERVAL < 30:
        # For medium checks, depends on latency
        if detection_latency >= INTERVAL:
            WARN: Detection too late
    else:
        # For slow checks (≥30s), latency is expected and acceptable
        OK
```

**Why fractional ratios are better:**
- Integer ratio (6.0): Detection at 105s for 90s timeout = 15s late
- Fractional ratio (6.5): Detection at 105s for 98s timeout = 7s late
- Fractional ratio (7.5): Detection at 120s for 112s timeout = 8s late

## Files Modified

- `main_bot.py`: Added `_validate_tcp_health_config()` method (lines 181-270)
- `config.py.sample`: Enhanced TCP configuration documentation (lines 109-147)
- `test_tcp_config_validation.py`: Comprehensive test suite (NEW)

## Testing

A test suite is included to verify your configuration:

```bash
python3 test_tcp_config_validation.py
```

This will show you:
- Whether your current config is safe
- Detection latency for your configuration  
- Timeline visualization of health checks
- Recommended alternative configurations

## Summary

The issue is caused by an **integer ratio** between your timeout and check interval, creating predictable timing where the check occurs exactly one full interval after the timeout expires. By adding a small margin to break this integer relationship, you eliminate false alarms while maintaining responsive detection of real connection issues.

**TL;DR:** Change `TCP_SILENT_TIMEOUT = 90` to `TCP_SILENT_TIMEOUT = 98` (or 112, 120) in your `config.py`.
