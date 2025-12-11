# Fix: Duplicate Radio Links in /propag Command

## Problem

The `/propag` command was showing duplicate entries for the same node pairs because each packet between two nodes created a separate "link" entry.

### Before Fix (Example Output)
```
📡 **Top 5 liaisons radio** (dernières 24h)
🎯 Rayon maximum: 100km

🥈 **#1 - 17km**
   📤 poulaga dhouilles 🐔☀️ (ID: !d45aa8d4)
   📥 tigro G2 PV (ID: !a2e175ac)
   📶 RSSI: -89 dBm
   🕐 10/12 12:00

🥉 **#2 - 9.8km**  ← DUPLICATE
   📤 Tonio boitier T114 559e (ID: !a6ea559e)
   📥 tigro G2 PV (ID: !a2e175ac)
   📊 SNR: -8.0 dB
   📶 RSSI: -100 dBm
   🕐 10/12 22:55

🥉 **#3 - 9.8km**  ← DUPLICATE (same pair, different packet)
   📤 Tonio boitier T114 559e (ID: !a6ea559e)
   📥 tigro G2 PV (ID: !a2e175ac)
   📊 SNR: -5.5 dB
   📶 RSSI: -99 dBm
   🕐 10/12 22:54

🥉 **#4 - 9.8km**  ← DUPLICATE (same pair, different packet)
   📤 Tonio boitier T114 559e (ID: !a6ea559e)
   📥 tigro G2 PV (ID: !a2e175ac)
   📊 SNR: -6.5 dB
   📶 RSSI: -101 dBm
   🕐 10/12 22:42

🥉 **#5 - 9.8km**  ← DUPLICATE (same pair, different packet)
   📤 Tonio boitier T114 559e (ID: !a6ea559e)
   📥 tigro G2 PV (ID: !a2e175ac)
   📊 SNR: -7.2 dB
   📶 RSSI: -100 dBm
   🕐 10/12 22:41
```

**Issue**: Entries #2-5 are all packets between the same two nodes, making the report less useful.

## Solution

### Deduplication Algorithm

1. **Group by node pair**: Create bidirectional pair key `(min(from_id, to_id), max(from_id, to_id))`
2. **Select best link per pair** using criteria (in order):
   - **SNR quality**: If both have SNR, keep higher (better signal)
   - **SNR presence**: If only one has SNR, keep it
   - **Recency**: Otherwise, keep most recent (higher timestamp)

### Code Implementation

```python
# Déduplication par paire (from_id, to_id)
unique_links = {}
for link in links_with_distance:
    # Créer une clé unique pour la paire de nœuds (bidirectionnelle)
    # Trier les IDs pour que A→B et B→A soient considérés comme la même liaison
    pair_key = tuple(sorted([link['from_id'], link['to_id']]))
    
    if pair_key not in unique_links:
        unique_links[pair_key] = link
    else:
        # Comparer et garder le meilleur lien
        existing = unique_links[pair_key]
        
        replace = False
        if link['snr'] is not None and existing['snr'] is not None:
            if link['snr'] > existing['snr']:
                replace = True
        elif link['snr'] is not None and existing['snr'] is None:
            replace = True
        elif link['timestamp'] > existing['timestamp']:
            replace = True
        
        if replace:
            unique_links[pair_key] = link

# Convertir le dictionnaire en liste
links_with_distance = list(unique_links.values())
```

### After Fix (Example Output)
```
📡 **Top 2 liaisons radio** (dernières 24h)
🎯 Rayon maximum: 100km

🥈 **#1 - 17km**
   📤 poulaga dhouilles 🐔☀️ (ID: !d45aa8d4) - Alt: 45m
   📥 tigro G2 PV (ID: !a2e175ac) - Alt: 39m
   📶 RSSI: -89 dBm
   🕐 10/12 12:00

🥉 **#2 - 9.8km**  ← BEST SNR kept (-5.5 dB)
   📤 Tonio boitier T114 559e (ID: !a6ea559e) - Alt: 0m
   📥 tigro G2 PV (ID: !a2e175ac) - Alt: 39m
   📊 SNR: -5.5 dB
   📶 RSSI: -99 dBm
   🕐 10/12 22:54
```

**Improvement**: Only unique node pairs shown, with best signal quality for each.

## Additional Enhancement: Altitude Display

Added altitude information for each node in the link display:
- Format: `Alt: 45m`
- Fetched from database (30-day retention) or node_manager (memory)
- Defaults to 0m if not available

## Test Coverage

Created `test_propag_deduplication.py` to verify the deduplication logic:

```python
# Simulate 4 packets between same nodes
links = [
    {'from_id': 0xa6ea559e, 'to_id': 0xa2e175ac, 'snr': -8.0, 'timestamp': 1000},
    {'from_id': 0xa6ea559e, 'to_id': 0xa2e175ac, 'snr': -5.5, 'timestamp': 2000},  # BEST SNR
    {'from_id': 0xa6ea559e, 'to_id': 0xa2e175ac, 'snr': -6.5, 'timestamp': 3000},
    {'from_id': 0xa6ea559e, 'to_id': 0xa2e175ac, 'snr': -7.2, 'timestamp': 4000},
]

# After deduplication: 1 link with SNR -5.5 (best)
```

Test output:
```
✅ Test de déduplication réussi!
   - 4 liens réduits à 1 lien unique
   - Meilleur SNR conservé (-5.5)
```

## Files Modified

- **`traffic_monitor.py`**
  - `get_propagation_report()` method
  - Added altitude fetching from database/node_manager
  - Added deduplication logic after GPS validation
  - Updated display format to include altitude

## Backward Compatibility

- ✅ Compact format (LoRa, 180 chars): Still works
- ✅ Detailed format (Telegram): Enhanced with altitude
- ✅ No breaking changes to command interface
- ✅ Graceful handling of missing altitude data (defaults to 0m)

## Benefits

1. **Clearer reports**: No duplicate node pairs cluttering the list
2. **Better signal info**: Shows best SNR for each link
3. **More useful**: Top N shows N unique links, not N packets
4. **Altitude context**: Helps understand signal propagation
5. **Accurate statistics**: `Total liaisons analysées` shows unique pairs count
