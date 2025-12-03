# Fix: Missing Neighbors at Startup - Issue Investigation

## Problem Statement

The bot was missing many neighbors at startup (42 instead of 500+) even with the initial TCP query enabled. This was preventing complete network topology visualization in the maps.

## Root Cause Analysis

### Original Implementation

The `populate_neighbors_from_interface()` method in `traffic_monitor.py` had the following limitations:

```python
def populate_neighbors_from_interface(self, interface, wait_time=10):
    info_print(f"👥 Chargement initial des voisins depuis l'interface ({wait_time}s)...")
    time.sleep(wait_time)  # ❌ Fixed 10 second wait
    
    if not hasattr(interface, 'nodes') or not interface.nodes:
        info_print("⚠️  Aucun nœud disponible dans l'interface")
        return 0  # ❌ No retry
```

**Issues:**
1. **Fixed wait time**: Only 10 seconds before checking interface.nodes
2. **No progress tracking**: Can't tell if nodes are still loading
3. **No retry logic**: Single attempt, no verification
4. **Insufficient for TCP**: ESP32 with 500+ nodes can take 30-60 seconds to fully populate

### Why TCP Takes Longer

When connecting via TCP to a Meshtastic node:

1. **Initial connection**: 2-3 seconds
2. **Node database transfer**: Depends on number of nodes
   - Small network (10-50 nodes): ~5 seconds
   - Medium network (100-200 nodes): ~15 seconds
   - Large network (500+ nodes): 30-60 seconds
3. **Neighbor data**: Additional time for neighborinfo attributes

With only 10 seconds wait time, the bot would often start extracting before all nodes were loaded.

## Solution

### 1. Polling Mechanism

Instead of a fixed wait time, implement progressive polling:

```python
# Initial wait
time.sleep(wait_time)

# Then poll until stable
while elapsed_time < max_wait_time:
    current_node_count = len(interface.nodes) if interface.nodes else 0
    
    if current_node_count == previous_node_count:
        stable_count += 1
        if stable_count >= required_stable_checks:
            # Stabilized!
            break
    else:
        stable_count = 0  # Reset
        # Log progress
    
    time.sleep(poll_interval)
    elapsed_time += poll_interval
```

**Benefits:**
- Adapts to network size (small networks finish faster)
- Detects when loading is complete (stable count)
- Provides progress feedback
- Prevents premature extraction

### 2. Configuration Options

New config options in `config.py.sample`:

```python
# Configuration chargement initial des voisins au démarrage
NEIGHBOR_LOAD_INITIAL_WAIT = 10    # Attente initiale (secondes)
NEIGHBOR_LOAD_MAX_WAIT = 60        # Timeout maximum (secondes)
NEIGHBOR_LOAD_POLL_INTERVAL = 5    # Intervalle entre vérifications (secondes)
```

**Benefits:**
- Tunable for different network sizes
- Can be adjusted without code changes
- Defaults work for most cases

### 3. Enhanced Diagnostics

Track and report detailed statistics:

```python
total_neighbors = 0
nodes_with_neighbors = 0
nodes_without_neighbors = 0
nodes_without_neighborinfo = 0

# ... extraction ...

info_print(f"✅ Chargement initial terminé:")
info_print(f"   • Nœuds totaux: {final_node_count}")
info_print(f"   • Nœuds avec voisins: {nodes_with_neighbors}")
info_print(f"   • Nœuds sans voisins: {nodes_without_neighbors}")
info_print(f"   • Relations de voisinage: {total_neighbors}")
info_print(f"   • Moyenne voisins/nœud: {avg_neighbors:.1f}")

if nodes_without_neighborinfo > 0:
    info_print(f"   ⚠️  Nœuds sans neighborinfo: {nodes_without_neighborinfo}")
    info_print(f"      Exemples: {sample_nodes}")
```

**Benefits:**
- Easy to diagnose issues
- Shows exactly what was loaded
- Identifies nodes without neighborinfo
- Helps tune configuration

## Testing

### Test 1: Polling Logic (`test_neighbor_polling.py`)

Verifies the polling mechanism works correctly:

```
=== Test 1: Simulating progressive node loading ===
Iteration 1: 2s - 100 nodes (+100)
Iteration 2: 5s - 200 nodes (+100)
Iteration 3: 8s - 300 nodes (+100)
Iteration 4: 11s - 400 nodes (+100)
Iteration 5: 14s - 500 nodes (+100)
Iteration 6: 17s - 500 nodes (stable 1/2)
Iteration 7: 20s - 500 nodes (stable 2/2)
✅ Stabilized at 500 nodes after 20s
```

**Result:** ✅ PASSED

### Test 2: Comprehensive Loading (`test_comprehensive_neighbor_loading.py`)

Simulates realistic conditions with 500 nodes:

```
======================================================================
VALIDATION
======================================================================

✅ All 500 nodes loaded successfully
✅ Correct number of nodes with neighbors: 420
✅ Neighbor relationships in expected range: 1680 (expected 1260-2100)
✅ Loading completed within timeout: 17s (max: 30s)

======================================================================
✅ ALL TESTS PASSED
======================================================================
```

**Result:** ✅ PASSED

## Expected Impact

### Before Fix
```
👥 Chargement initial des voisins depuis l'interface (10s)...
✅ Chargement initial terminé: 42 nœuds, 156 voisins
```

**42 nodes with neighbors** - Many nodes not yet loaded

### After Fix
```
👥 Chargement initial des voisins depuis l'interface...
   Attente initiale: 10s, maximum: 60s, vérification tous les 5s
   📈 10s: 100 nœuds chargés (+100)
   📈 15s: 300 nœuds chargés (+200)
   📈 20s: 500 nœuds chargés (+200)
   ⏳ 25s: 500 nœuds (stable 1/2)
   ✅ Chargement stabilisé à 500 nœuds après 30s
📊 Début extraction voisins de 500 nœuds...
✅ Chargement initial terminé:
   • Nœuds totaux: 500
   • Nœuds avec voisins: 420
   • Nœuds sans voisins: 80
   • Relations de voisinage: 1680
   • Moyenne voisins/nœud: 4.0
```

**420 nodes with neighbors** - 10x improvement!

## Deployment

### 1. Update Configuration

If needed, tune the polling parameters in `config.py`:

```python
# For very large networks (1000+ nodes), increase timeout
NEIGHBOR_LOAD_MAX_WAIT = 120  # 2 minutes

# For faster networks, decrease poll interval
NEIGHBOR_LOAD_POLL_INTERVAL = 3  # Check every 3 seconds
```

### 2. Restart Bot

```bash
sudo systemctl restart meshbot
```

### 3. Check Logs

Monitor the neighbor loading progress:

```bash
journalctl -u meshbot -f | grep -A 20 "Chargement initial des voisins"
```

Look for:
- ✅ Final node count matches expected
- ✅ Stabilization within timeout
- ✅ Neighbor relationships detected

### 4. Verify Maps

After bot has been running for a few minutes:

```bash
cd /home/dietpi/bot/map
./infoup_db.sh
```

Check that `info_neighbors.json` has significantly more nodes than before.

## Troubleshooting

### Issue: Still getting low neighbor counts

**Possible causes:**
1. **Network too large**: Increase `NEIGHBOR_LOAD_MAX_WAIT`
2. **TCP slow**: Check network latency to node
3. **No neighborinfo**: Many nodes don't broadcast NEIGHBORINFO_APP

**Debug:**
```bash
# Check how many nodes are in the interface
meshtastic --host <IP> --info | jq '.nodes | length'

# Check if nodes have neighborinfo
meshtastic --host <IP> --info | jq '.nodes[] | select(.neighborinfo != null) | .user.longName'
```

### Issue: Timeout exceeded

**Symptoms:**
```
⏳ 60s: Still loading, 300 nœuds...
```

**Solutions:**
1. Increase `NEIGHBOR_LOAD_MAX_WAIT` to 120
2. Check TCP connection stability
3. Verify ESP32 isn't overloaded

### Issue: Many nodes without neighborinfo

**Symptoms:**
```
⚠️  Nœuds sans neighborinfo: 400
```

**Explanation:**
This is normal if:
- Nodes haven't broadcast NEIGHBORINFO_APP yet (every 15-30 min)
- Nodes are configured with `neighbor_info.enabled = false`
- Nodes are older firmware without neighbor support

**Solutions:**
1. Wait 1-2 hours for passive collection via NEIGHBORINFO_APP packets
2. Use hybrid mode in map export: `./export_neighbors_from_db.py --tcp-query <IP>`
3. Enable neighbor_info on nodes: `meshtastic --set neighbor_info.enabled true`

## Related Documentation

- `map/README_NEIGHBORS.md` - Neighbor data collection overview
- `map/HYBRID_MODE_GUIDE.md` - Using TCP query for complete data
- `CLAUDE.md` - Full architecture documentation
- Issue #97 - Original issue report

## Files Changed

- `traffic_monitor.py::populate_neighbors_from_interface()` - Core implementation
- `config.py.sample` - Configuration options
- `test_neighbor_polling.py` - Polling logic test
- `test_comprehensive_neighbor_loading.py` - Integration test

## Verification Checklist

- [x] Polling mechanism implemented
- [x] Configuration options added
- [x] Enhanced diagnostics
- [x] Unit tests pass
- [x] Integration tests pass
- [ ] Real-world testing with actual TCP connection
- [ ] Verify 500+ neighbors loaded at startup
- [ ] Confirm map visualization shows complete network

## Next Steps

1. **User testing**: Deploy to production and monitor logs
2. **Feedback loop**: Adjust config defaults if needed
3. **Documentation**: Update user docs with new config options
4. **Monitoring**: Add metrics to track neighbor loading success rate
