# Dual Network Mode Warning Fix

## Problem Statement

When `DUAL_NETWORK_MODE=True` with both Meshtastic and MeshCore enabled, the startup logs incorrectly showed a warning that Meshtastic is prioritized and MeshCore will be ignored, even though dual mode was successfully initialized and both networks were actually being handled equally.

## Example of the Problem

**User's Log (Before Fix):**
```
Feb 01 19:46:56 DietPi meshtastic-bot[577301]: [INFO] ⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés
Feb 01 19:46:56 DietPi meshtastic-bot[577301]: [INFO]    → Priorité donnée à Meshtastic (capacités mesh complètes)
Feb 01 19:46:56 DietPi meshtastic-bot[577301]: [INFO]    → MeshCore sera ignoré. Pour utiliser MeshCore:
Feb 01 19:46:56 DietPi meshtastic-bot[577301]: [INFO]    →   Définir MESHTASTIC_ENABLED = False dans config.py
```

This was confusing because:
1. The bot WAS in dual network mode
2. Both networks WERE being handled equally
3. MeshCore was NOT being ignored
4. The warning suggested disabling Meshtastic, which was wrong

## Root Cause

In `main_bot.py` at line 1770, the conditional logic was:

```python
elif meshtastic_enabled and meshcore_enabled:
    # Both enabled - warn user and prioritize Meshtastic
    info_print("⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés")
    info_print("   → Priorité donnée à Meshtastic (capacités mesh complètes)")
    info_print("   → MeshCore sera ignoré. Pour utiliser MeshCore:")
    info_print("   →   Définir MESHTASTIC_ENABLED = False dans config.py")
```

This condition didn't check whether `DUAL_NETWORK_MODE` was enabled, so it showed the warning even when both networks were intentionally configured to work together.

## Solution

Updated the condition to check for `not dual_mode`:

```python
elif meshtastic_enabled and meshcore_enabled and not dual_mode:
    # Both enabled but dual mode NOT enabled - warn user and prioritize Meshtastic
    info_print("⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés")
    info_print("   → Priorité donnée à Meshtastic (capacités mesh complètes)")
    info_print("   → MeshCore sera ignoré. Pour utiliser MeshCore:")
    info_print("   →   Définir MESHTASTIC_ENABLED = False dans config.py")
    info_print("   → OU activer le mode dual: DUAL_NETWORK_MODE = True")
```

## Before and After

### Scenario 1: Dual Network Mode Enabled (The Fix)

**Configuration:**
```python
DUAL_NETWORK_MODE = True
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
```

**Before Fix:**
```
[INFO] 🔄 MODE DUAL: Connexion simultanée Meshtastic + MeshCore
[INFO]    → Deux réseaux mesh actifs en parallèle
[INFO]    → Statistiques agrégées des deux réseaux
[INFO]    → Réponses routées vers le réseau source
... (dual mode setup succeeds)
[INFO] ⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés
[INFO]    → Priorité donnée à Meshtastic (capacités mesh complètes)
[INFO]    → MeshCore sera ignoré. Pour utiliser MeshCore:
[INFO]    →   Définir MESHTASTIC_ENABLED = False dans config.py
❌ Problem: Confusing warning appears!
```

**After Fix:**
```
[INFO] 🔄 MODE DUAL: Connexion simultanée Meshtastic + MeshCore
[INFO]    → Deux réseaux mesh actifs en parallèle
[INFO]    → Statistiques agrégées des deux réseaux
[INFO]    → Réponses routées vers le réseau source
... (continues without warning)
✅ Fixed: No warning, both networks handled equally!
```

### Scenario 2: Both Networks Enabled WITHOUT Dual Mode

**Configuration:**
```python
DUAL_NETWORK_MODE = False  # or not set
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
```

**Behavior (Same Before and After):**
```
[INFO] ⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés
[INFO]    → Priorité donnée à Meshtastic (capacités mesh complètes)
[INFO]    → MeshCore sera ignoré. Pour utiliser MeshCore:
[INFO]    →   Définir MESHTASTIC_ENABLED = False dans config.py
[INFO]    → OU activer le mode dual: DUAL_NETWORK_MODE = True
✅ Helpful warning with suggestion to enable dual mode
```

### Scenario 3: Single Network Enabled

**Configuration:**
```python
DUAL_NETWORK_MODE = False
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
```

**Behavior (Same Before and After):**
```
... (continues with normal Meshtastic initialization)
✅ No warning needed
```

## Decision Flow

The new logic flow is:

```
1. If DUAL_NETWORK_MODE=True AND both networks enabled:
   → Initialize dual mode (handle both equally)
   → NO WARNING
   
2. If DUAL_NETWORK_MODE=False AND both networks enabled:
   → Initialize Meshtastic only (ignore MeshCore)
   → SHOW WARNING with dual mode suggestion
   
3. If only one network enabled:
   → Initialize that network
   → NO WARNING
   
4. If neither network enabled:
   → Initialize standalone mode
   → NO WARNING
```

## Testing

Created comprehensive test suite with 6 test cases covering all scenarios:

✅ Test 1: Dual mode enabled with both networks - No warning shown  
✅ Test 2: Dual mode disabled with both networks - Warning shown  
✅ Test 3: Dual mode enabled but only Meshtastic - No warning  
✅ Test 4: Both disabled (standalone) - No warning  
✅ Test 5: Only Meshtastic enabled - No warning  
✅ Test 6: Only MeshCore enabled - No warning  

**All tests passed!**

## Code Changes

### File: `main_bot.py`

**Line 1770 - Changed from:**
```python
elif meshtastic_enabled and meshcore_enabled:
```

**To:**
```python
elif meshtastic_enabled and meshcore_enabled and not dual_mode:
```

**Line 1776 - Added:**
```python
info_print("   → OU activer le mode dual: DUAL_NETWORK_MODE = True")
```

## Benefits

✅ **No False Warnings** - Dual mode works without confusing error messages  
✅ **Clear Guidance** - Warning now suggests enabling dual mode as an option  
✅ **Correct Behavior** - Warning only appears when it should  
✅ **User-Friendly** - Users understand how to properly configure dual network mode  
✅ **Fully Tested** - Comprehensive test coverage ensures reliability  

## Summary

This fix ensures that when `DUAL_NETWORK_MODE=True`, both Meshtastic and MeshCore networks are handled equally without any warning about prioritization. The warning now only appears when both networks are enabled WITHOUT dual mode, and it helpfully suggests enabling dual mode as a solution.

**Status: COMPLETE ✅**
