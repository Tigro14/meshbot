# Fix: Meshtastic Packets Incorrectly Detected as MeshCore

**Date**: 2026-02-01  
**Issue**: Meshtastic packets were being labeled as "meshcore" source when both `MESHTASTIC_ENABLED=True` and `MESHCORE_ENABLED=True`

## Problem Description

When the bot was configured with both Meshtastic and MeshCore enabled:
```python
MESHTASTIC_ENABLED = True   # Active Meshtastic connection
MESHCORE_ENABLED = True     # MeshCore companion mode
```

ALL packets were being incorrectly labeled as "meshcore" source, including packets from Meshtastic-only remote nodes.

### Log Evidence

```
Feb 01 19:48:31 DietPi meshtastic-bot[577301]: [DEBUG] 🔍 Source détectée: MeshCore (MESHCORE_ENABLED=True, single mode)
Feb 01 19:48:31 DietPi meshtastic-bot[577301]: [INFO] 🔵 add_packet ENTRY | source=meshcore | from=0x2f9fb748 | interface=SerialInterface
Feb 01 19:48:31 DietPi meshtastic-bot[577301]: [INFO] 💾 [SAVE-MESHCORE] Tentative sauvegarde: POSITION_APP de 14FRS711QRA (0x2f9fb748)
```

**Note**: `14FRS711QRA` is a Meshtastic-only remote node, not a MeshCore node!

## Root Cause Analysis

### Initialization Logic (CORRECT ✅)

In `main_bot.py` lines 1670-1677, when both are enabled, Meshtastic has priority:

```python
elif meshtastic_enabled and meshcore_enabled:
    # Both enabled - warn user and prioritize Meshtastic
    info_print("⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED sont tous deux activés")
    info_print("   → Priorité donnée à Meshtastic (capacités mesh complètes)")
    info_print("   → MeshCore sera ignoré. Pour utiliser MeshCore:")
    info_print("   →   Définir MESHTASTIC_ENABLED = False dans config.py")
    # Continue to Meshtastic connection (next if blocks)
```

**Result**: A Meshtastic interface is created (either SerialInterface or TCPInterface).

### Source Detection Logic (INCORRECT ❌ - BEFORE FIX)

In `main_bot.py` line 496, source detection checked the **config variable**:

```python
# BEFORE FIX (INCORRECT)
if globals().get('MESHCORE_ENABLED', False):
    source = 'meshcore'  # ❌ BUG: Always 'meshcore' when config is True
    debug_print("🔍 Source détectée: MeshCore (MESHCORE_ENABLED=True)")
```

**Problem**: This checks the CONFIG, not the actual interface type!

## The Fix

### Change Made

Modified `main_bot.py` line 497 to check the **actual interface type** instead of the config:

```python
# AFTER FIX (CORRECT)
if isinstance(self.interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface)):
    source = 'meshcore'  # ✅ Only 'meshcore' when interface IS MeshCore
    debug_print("🔍 Source détectée: MeshCore (interface active)")
```

### Why This Works

1. **When both enabled**: `self.interface` is a Meshtastic interface (SerialInterface or OptimizedTCPInterface)
   - `isinstance()` returns `False`
   - Source correctly set to `'local'` or `'tcp'`

2. **When only MeshCore enabled**: `self.interface` is a MeshCore interface
   - `isinstance()` returns `True`
   - Source correctly set to `'meshcore'`

3. **When only Meshtastic enabled**: `self.interface` is a Meshtastic interface
   - `isinstance()` returns `False`
   - Source correctly set to `'local'` or `'tcp'`

## Test Results

### Before Fix (INCORRECT ❌)

```
AVANT LE FIX: Vérification via MESHCORE_ENABLED (config)
❌ BUG: source='meshcore' (alors que l'interface est Meshtastic!)
   Config MESHCORE_ENABLED=True
   Interface réelle: MockMeshtasticSerial
   → Résultat: TOUS les paquets marqués 'meshcore' (INCORRECT)
```

### After Fix (CORRECT ✅)

```
APRÈS LE FIX: Vérification via isinstance(interface, MeshCore*)
✅ CORRECT: source='local' (interface Meshtastic détectée)
   Config MESHCORE_ENABLED=True (ignorée)
   Interface réelle: MockMeshtasticSerial
   isinstance check: False
   → Résultat: Paquets Meshtastic marqués 'local' (CORRECT)
```

### MeshCore Still Works (CORRECT ✅)

```
TEST BONUS: MeshCore reste détecté quand c'est vraiment MeshCore
✅ CORRECT: source='meshcore' (interface MeshCore détectée)
   Interface réelle: MeshCoreSerialInterface
   isinstance check: True
   → MeshCore fonctionne toujours correctement!
```

## Impact

### Fixed Behavior

- ✅ Meshtastic packets correctly labeled as `'local'` or `'tcp'`
- ✅ MeshCore packets correctly labeled as `'meshcore'`
- ✅ Traffic statistics accurate (no false MeshCore packet counts)
- ✅ Database persistence correct (packets saved to correct tables)
- ✅ Log messages accurate and helpful for debugging

### No Breaking Changes

- ✅ MeshCore-only mode still works correctly
- ✅ Meshtastic-only mode still works correctly
- ✅ Hybrid config (both enabled) now works correctly
- ✅ All existing functionality preserved

## Configuration Guidance

### Recommended Configuration

**Option A**: Meshtastic Only (Most Common)
```python
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False
CONNECTION_MODE = 'serial'  # or 'tcp'
```

**Option B**: MeshCore Only (If no Meshtastic radio)
```python
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True
```

**Option C**: Both Enabled (Now Fixed ✅)
```python
MESHTASTIC_ENABLED = True   # Active Meshtastic connection
MESHCORE_ENABLED = True     # Ignored (Meshtastic has priority)
CONNECTION_MODE = 'serial'  # or 'tcp'
```

With the fix, Option C now works correctly - Meshtastic has priority and packets are correctly labeled.

## Files Modified

- `main_bot.py` - Lines 495-500: Source detection logic
- `demo_source_detection_fix.py` - Test demonstrating the fix
- `test_meshtastic_source_detection.py` - Unit tests for source detection

## Related Documentation

- `MESHCORE_COMPANION.md` - MeshCore companion mode documentation
- `DUAL_INTERFACE_FAQ.md` - FAQ about using multiple interfaces
- `config.py.sample` - Configuration template with explanations

## Verification

To verify the fix is working:

1. Check logs for source detection:
   ```bash
   journalctl -u meshbot -f | grep "Source détectée"
   ```

2. Verify packet source labels:
   ```bash
   journalctl -u meshbot -f | grep "add_packet ENTRY"
   ```

3. Expected output when both enabled:
   ```
   [DEBUG] 🔍 Source détectée: MeshCore (interface active)  # Only if MeshCore interface
   [DEBUG] 🔍 Source détectée: local/tcp                    # For Meshtastic packets
   ```

## Summary

**Before**: Config check → Always 'meshcore' when `MESHCORE_ENABLED=True`  
**After**: Type check → Only 'meshcore' when interface IS MeshCore  

**Result**: ✅ Accurate source detection respecting actual active interface
