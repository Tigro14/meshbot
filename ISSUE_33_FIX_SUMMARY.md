# Issue #33 Fix: Vigilance Monitor Error Handling Improvements

## Summary

Fixed error handling in `vigilance_monitor.py` to handle external API failures more gracefully.

## Problems Fixed

### 1. ❌ No Timeout on API Calls
**Before:** API calls could hang indefinitely
**After:** 10-second socket timeout prevents hanging

### 2. ❌ Too Aggressive Error Logging
**Before:** Every retry attempt logged as `[ERROR]`
**After:** Intermediate retries use `[INFO]`, only final failure is `[ERROR]`

### 3. ❌ Fixed Backoff Delays
**Before:** Fixed delays (2s, 4s, 8s) - can cause thundering herd
**After:** Exponential backoff with jitter (2.0-3.0s, 4.0-5.0s) - spreads retries

### 4. ❌ Generic Exception Handling
**Before:** Caught all exceptions the same way
**After:** Specific handling for `RemoteDisconnected`, `socket.timeout`, `ConnectionResetError`, etc.

## Code Changes

### Import Additions
```python
import random
import socket
import http.client
```

### Timeout Implementation
```python
# Set timeout before API call
old_timeout = socket.getdefaulttimeout()
try:
    socket.setdefaulttimeout(10)  # 10-second timeout
    zone = vigilancemeteo.DepartmentWeatherAlert(self.departement)
finally:
    socket.setdefaulttimeout(old_timeout)  # Restore
```

### Improved Error Handling
```python
except (http.client.RemoteDisconnected, 
        socket.timeout,
        ConnectionResetError,
        ConnectionRefusedError,
        OSError) as e:
    # Network errors - specific handling
    
    if attempt < max_retries - 1:
        # Intermediate retry - INFO level
        info_print(f"⚠️ Erreur réseau vigilance ({error_type}), tentative {attempt + 1}/{max_retries}")
        debug_print(f"   Message: {error_msg}")
    else:
        # Final failure - ERROR level
        error_print(f"❌ Erreur vérification vigilance après {max_retries} tentatives:")
```

### Exponential Backoff with Jitter
```python
# Old: Fixed delay
retry_delay *= 2  # 2s → 4s → 8s (predictable)

# New: Jitter added
jitter = random.uniform(0, 1)
sleep_time = (base_retry_delay * (2 ** attempt)) + jitter
# Example: 2.9s → 4.7s → ... (unpredictable, prevents thundering herd)
```

## Test Results

### Before Fix (Problematic Logs)
```
[ERROR] ⚠️ Erreur vigilance (ConnectionResetError): Remote end closed connection
[ERROR]    Tentative 1/3 échouée, nouvelle tentative dans 2s...
[ERROR] ⚠️ Erreur vigilance (ConnectionResetError): Remote end closed connection
[ERROR]    Tentative 2/3 échouée, nouvelle tentative dans 4s...
[ERROR] ⚠️ Erreur vigilance (ConnectionResetError): Remote end closed connection
[ERROR]    Tentative 3/3 échouée
[ERROR] ❌ Erreur vérification vigilance après 3 tentatives:
[ERROR]    Type: ConnectionResetError
[ERROR]    Message: Remote end closed connection
Traceback (most recent call last):
  ...
```
**Problems:**
- Too many ERROR messages (alarming)
- Traceback shown even when not in debug mode
- Fixed delays (2s, 4s) - thundering herd risk

### After Fix (Improved Logs)
```
[INFO] ⚠️ Erreur réseau vigilance (ConnectionResetError), tentative 1/3
[DEBUG]    Message: Remote end closed connection
[DEBUG]    Nouvelle tentative dans 2.9s...
[INFO] ⚠️ Erreur réseau vigilance (ConnectionResetError), tentative 2/3
[DEBUG]    Message: Remote end closed connection
[DEBUG]    Nouvelle tentative dans 4.7s...
[ERROR] ❌ Erreur vérification vigilance après 3 tentatives:
[ERROR]    Type: ConnectionResetError
[ERROR]    Message: Remote end closed connection
[DEBUG] Traceback complet:
[DEBUG] Traceback (most recent call last):
  ...
```
**Improvements:**
- Intermediate retries: INFO level (less alarming)
- Error details: DEBUG only
- Jittered delays (2.9s, 4.7s) - prevents thundering herd
- Only final failure: ERROR level
- Traceback: DEBUG mode only

## Test Coverage

### test_network_resilience.py (Existing)
✅ Retry logic works correctly
✅ Returns None after all retries exhausted

### test_vigilance_improvements.py (New)
✅ Socket timeout is set and restored correctly
✅ RemoteDisconnected exception caught specifically
✅ Exponential backoff includes jitter (not fixed)
✅ Logging levels correct (INFO for retries, ERROR for final)

All tests pass: **7/7** ✅

## Benefits

1. **Prevents Indefinite Hangs**: 10-second timeout on all API calls
2. **Less Noise in Logs**: Intermediate retries don't trigger ERROR alerts
3. **Prevents Thundering Herd**: Jitter spreads retry attempts over time
4. **Better Debugging**: Clear error categorization (network vs unexpected)
5. **Debug-Only Traceback**: Production logs stay clean

## Configuration

No configuration changes needed. The improvements are transparent to existing deployments.

Default values:
- Timeout: 10 seconds
- Max retries: 3
- Base retry delay: 2 seconds
- Jitter range: 0-1 second
