# /propag Deduplication - Visual Flow Diagram

## Data Flow: Before Fix

```
┌─────────────────────────────────────────────────────────────┐
│ TrafficPersistence.load_radio_links_with_positions()       │
│ Returns ALL packets with SNR/RSSI in time window            │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Packets from DB (24h):                                      │
│                                                              │
│ 1. A→B (SNR: -8.0, 10:55)  ─┐                              │
│ 2. A→B (SNR: -5.5, 10:54)  ├─ Same pair, different packets │
│ 3. A→B (SNR: -6.5, 10:42)  │                               │
│ 4. A→B (SNR: -7.2, 10:41)  ┘                               │
│ 5. C→D (SNR: None, 12:00)                                   │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Filter by GPS availability                                  │
│ Calculate distances                                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Sort by distance DESC                                       │
│ Take top 5                                                   │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: Top 5 (with duplicates!)                           │
│                                                              │
│ #1: C→D (17km)                                              │
│ #2: A→B (9.8km, SNR: -8.0)  ┐                              │
│ #3: A→B (9.8km, SNR: -5.5)  ├─ DUPLICATES!                │
│ #4: A→B (9.8km, SNR: -6.5)  │                              │
│ #5: A→B (9.8km, SNR: -7.2)  ┘                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow: After Fix

```
┌─────────────────────────────────────────────────────────────┐
│ TrafficPersistence.load_radio_links_with_positions()       │
│ Returns ALL packets with SNR/RSSI in time window            │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Packets from DB (24h):                                      │
│                                                              │
│ 1. A→B (SNR: -8.0, 10:55)  ─┐                              │
│ 2. A→B (SNR: -5.5, 10:54)  ├─ Same pair, different packets │
│ 3. A→B (SNR: -6.5, 10:42)  │                               │
│ 4. A→B (SNR: -7.2, 10:41)  ┘                               │
│ 5. C→D (SNR: None, 12:00)                                   │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Filter by GPS availability                                  │
│ Calculate distances                                          │
│ Add altitude information                                     │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ ✨ NEW: DEDUPLICATION BY PAIR ✨                            │
│                                                              │
│ For each packet:                                            │
│   pair_key = tuple(sorted([from_id, to_id]))               │
│   if pair not seen:                                         │
│     keep this packet                                        │
│   else:                                                     │
│     compare with existing:                                  │
│       - better SNR?     → replace                          │
│       - has SNR vs none? → replace                          │
│       - more recent?     → replace                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Deduplicated Links:                                         │
│                                                              │
│ 1. A→B (9.8km, SNR: -5.5) ← Best SNR kept                  │
│ 2. C→D (17km, SNR: None)                                    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Sort by distance DESC                                       │
│ Take top 5                                                   │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: Top 2 (unique pairs!)                              │
│                                                              │
│ #1: C→D (17km, Alt: 45m/39m)                               │
│ #2: A→B (9.8km, SNR: -5.5, Alt: 0m/39m) ← Best signal     │
└─────────────────────────────────────────────────────────────┘
```

## Deduplication Algorithm Detail

```
Input: links_with_distance = [link1, link2, link3, ...]

unique_links = {}  // Dictionary: pair_key → best_link

for each link in links_with_distance:
    
    ┌─────────────────────────────────────┐
    │ Create bidirectional pair key       │
    │ pair_key = (min_id, max_id)         │
    │                                      │
    │ Examples:                            │
    │   A→B: (A, B)                        │
    │   B→A: (A, B)  ← Same key!          │
    │   A→C: (A, C)                        │
    └──────────────┬──────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │ Is this pair new?                    │
    └──┬──────────────────────────────┬───┘
       │ YES                           │ NO
       ▼                               ▼
    ┌──────────────────┐    ┌─────────────────────────────┐
    │ Add to unique    │    │ Compare with existing:       │
    │ unique_links[    │    │                              │
    │   pair_key       │    │ if new.snr > existing.snr:   │
    │ ] = link         │    │   replace ✅                 │
    └──────────────────┘    │ elif new has snr, old none:  │
                            │   replace ✅                 │
                            │ elif new.timestamp > old:    │
                            │   replace ✅                 │
                            │ else:                        │
                            │   keep existing ⏭️           │
                            └─────────────────────────────┘

Output: unique_links.values() = [best_link_per_pair, ...]
```

## Selection Criteria Priority

```
┌────────────────────────────────────────────────────────┐
│ PRIORITY 1: SNR Quality (both have SNR)               │
│                                                         │
│ Link A: SNR -8.0 dB  ◀───────┐                        │
│ Link B: SNR -5.5 dB          │ Keep B (higher = better)│
│                              ✅                        │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ PRIORITY 2: SNR Presence (only one has SNR)           │
│                                                         │
│ Link A: SNR None     ◀───────┐                        │
│ Link B: SNR -10.0 dB         │ Keep B (has data)      │
│                              ✅                        │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ PRIORITY 3: Recency (neither/both have same SNR)      │
│                                                         │
│ Link A: timestamp 1000  ◀────┐                        │
│ Link B: timestamp 2000       │ Keep B (more recent)   │
│                              ✅                        │
└────────────────────────────────────────────────────────┘
```

## Bidirectional Deduplication Example

```
Input Packets:
┌─────────────────────┐
│ A → B               │
│ (from: 0xa6ea559e) │
│ (to:   0xa2e175ac) │
│ SNR: -8.0           │
└─────────────────────┘

┌─────────────────────┐
│ B → A               │  ← Different direction!
│ (from: 0xa2e175ac) │
│ (to:   0xa6ea559e) │
│ SNR: -5.5           │
└─────────────────────┘

Processing:
───────────

Step 1: A→B
  pair_key = sorted([0xa6ea559e, 0xa2e175ac])
           = (0xa2e175ac, 0xa6ea559e)
  ✅ New pair, add to unique_links

Step 2: B→A
  pair_key = sorted([0xa2e175ac, 0xa6ea559e])
           = (0xa2e175ac, 0xa6ea559e)  ← Same key!
  ⚡ Pair exists, compare:
     B→A SNR (-5.5) > A→B SNR (-8.0)
  ✅ Replace with B→A

Result:
───────
Only ONE link in output:
┌─────────────────────┐
│ B → A               │
│ Distance: 9.8km     │
│ SNR: -5.5 dB ✨     │  ← Best signal kept
│ Alt: 39m/0m         │
└─────────────────────┘
```

## Benefits Visualization

```
BEFORE FIX:
═══════════
Report shows: [═══════════════════════════] 5 entries
Unique pairs: [═══] 2 pairs
Usefulness:   ⭐⭐☆☆☆ (40% useful)

AFTER FIX:
══════════
Report shows: [═════] 2 entries
Unique pairs: [═════] 2 pairs
Usefulness:   ⭐⭐⭐⭐⭐ (100% useful!)
```
