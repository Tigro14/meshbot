# Bug Fix: /trafficmc Not Showing MeshCore Messages

## Issue
The `/trafficmc` command was always showing:
```
📭 Aucun message public MeshCore dans les 8h
```

Even when MeshCore messages were being sent and received on the network.

## Root Cause Analysis

### The Problem
In `main_bot.py`, the `add_public_message()` method was being called with a hardcoded `source='local'` parameter:

**Line 983 (Before Fix):**
```python
self.traffic_monitor.add_public_message(packet, message, source='local')
```

**Line 1013 (Before Fix):**
```python
self.traffic_monitor.add_public_message(packet, message, source='local')
```

### Why This Was Wrong
The `source` variable is correctly determined earlier in the `on_message()` method (lines 810-833):

```python
if self._dual_mode_active and network_source:
    # Mode dual: utiliser le network_source fourni
    if network_source == NetworkSource.MESHTASTIC:
        source = 'meshtastic'
    elif network_source == NetworkSource.MESHCORE:
        source = 'meshcore'  # ← This is set correctly!
    else:
        source = 'unknown'
elif globals().get('MESHCORE_ENABLED', False) and not self._dual_mode_active:
    # Mode MeshCore companion (sans dual mode)
    source = 'meshcore'  # ← This too!
elif self._is_tcp_mode():
    source = 'tcp'
elif globals().get('CONNECTION_MODE', 'serial').lower() == 'serial':
    source = 'local'
else:
    source = 'local' if is_from_our_interface else 'tigrog2'
```

**However**, the hardcoded `source='local'` in the `add_public_message()` calls **overwrote** this correctly determined value!

### The Impact
1. **All messages were tagged as `source='local'`** regardless of their actual origin
2. **MeshCore messages were invisible to `/trafficmc`** because the filter looks for `source='meshcore'`
3. **The `/trafic` command still worked** because it shows all messages regardless of source

## The Fix

### Changes Made
Simply use the computed `source` variable instead of hardcoding it:

**Line 983 (After Fix):**
```python
self.traffic_monitor.add_public_message(packet, message, source=source)
```

**Line 1013 (After Fix):**
```python
self.traffic_monitor.add_public_message(packet, message, source=source)
```

### Why This Works
Now the messages are tagged with their **actual** source:
- MeshCore messages: `source='meshcore'` ✅
- Meshtastic messages: `source='local'` or `source='meshtastic'` ✅
- TCP messages: `source='tcp'` ✅

The `/trafficmc` filter can now correctly identify MeshCore messages:
```python
# In traffic_monitor.py::get_traffic_report_mc()
recent_messages = [
    msg for msg in self.public_messages
    if msg['timestamp'] >= cutoff_time and msg.get('source') == 'meshcore'
]
```

## Testing

### Validation Test
Created `tests/test_source_parameter_fix.py` to ensure:
1. ✅ No hardcoded `source='local'` remains in `add_public_message()` calls
2. ✅ All calls use the computed `source` variable
3. ✅ The `source` variable is in scope when needed

### Existing Tests
All existing tests continue to pass:
- ✅ `test_trafficmc_command.py` - Filtering works correctly
- ✅ `test_trafficmc_integration.py` - Method signatures correct
- ✅ `demo_trafficmc_filtering.py` - Demo shows 5 MeshCore messages

## Before & After

### Before Fix
```
User: /trafficmc
Bot:  📭 Aucun message public MeshCore dans les 8h
```
Even when MeshCore traffic exists! 😞

### After Fix
```
User: /trafficmc
Bot:  🔗 **MESSAGES PUBLICS MESHCORE (8h)**
      ========================================
      Total: 5 messages
      
      [10:44:18] [CoreNode1] MeshCore node online
      [10:45:23] [CoreNode2] Testing connectivity
      [10:46:45] [CoreNode3] All systems operational
      [11:23:12] [CoreNode1] Battery level: 85%
      [11:45:38] [CoreNode4] All systems operational
```
MeshCore messages now appear! 😊

## Related Code Flow

### Message Processing Pipeline
1. **Packet arrives** → `on_message(packet, interface, network_source)`
2. **Source determined** (lines 810-833)
   - Checks dual mode, MeshCore mode, TCP mode, serial mode
   - Sets `source` variable to correct value
3. **Packet added to statistics** (line 852)
   - `traffic_monitor.add_packet(packet, source=source, ...)`
4. **Text message extracted** (lines 955-964)
5. **Public message recorded** (lines 983 or 1013)
   - **NOW FIXED**: `add_public_message(packet, message, source=source)`
   - **PREVIOUSLY**: `add_public_message(packet, message, source='local')` ❌

### How /trafficmc Works
1. User sends `/trafficmc [hours]` on Telegram
2. Telegram handler calls `business_stats.get_traffic_report_mc(hours)`
3. Business stats calls `traffic_monitor.get_traffic_report_mc(hours)`
4. Traffic monitor filters `public_messages` deque:
   ```python
   recent_messages = [
       msg for msg in self.public_messages
       if msg['timestamp'] >= cutoff_time and msg.get('source') == 'meshcore'
   ]
   ```
5. Filtered messages are formatted and returned
6. **NOW WORKS**: MeshCore messages have `source='meshcore'` so they appear! ✅

## Lessons Learned

### Code Smell: Hardcoded Values
The bug was introduced because someone hardcoded `source='local'` instead of using the computed variable. This is a common anti-pattern.

**Bad:**
```python
source = determine_source()  # Compute it
do_something(source='local')  # Ignore it and hardcode! ❌
```

**Good:**
```python
source = determine_source()  # Compute it
do_something(source=source)  # Use it! ✅
```

### Testing Blind Spots
The original tests created messages directly with `source='meshcore'`, so they didn't catch that the real code path was overriding it. The new validation test specifically checks the code paths in `main_bot.py`.

### Documentation Importance
This bug existed because the original implementation documentation didn't explicitly warn about this. Now it's documented!

## Future Prevention

### Code Review Checklist
- [ ] Check for hardcoded `source=` values in message recording
- [ ] Verify computed variables are actually used
- [ ] Test the **actual** code path, not just mocked versions
- [ ] Look for parameter shadowing (computed but not used)

### Static Analysis
Could add a linter rule to warn about:
```python
source = ...  # Computed
... source='local'  # But hardcoded later - suspicious!
```

## References
- Original `/trafficmc` implementation: commits 562b958, b68e913, 963c2b7
- Bug fix: commit 3a207fc
- Test validation: `tests/test_source_parameter_fix.py`
- Demo validation: `demos/demo_trafficmc_filtering.py`
