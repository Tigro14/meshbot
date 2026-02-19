# MeshCore Hop Count and Path Display

## Overview

This document describes the implementation of hop count and routing path display for MeshCore messages, making them consistent with Meshtastic message display.

## Problem Statement

**Request:** "We want to know the hops and if possible the full path in meshcore also"

### Issues Identified

1. **Incorrect Hop Count**: MeshCore messages always showed `Hops:0/0` even when packets traveled through multiple nodes
2. **Missing Path Information**: Routing path data was available in the decoder but not displayed in logs
3. **Inconsistent Display**: MeshCore lacked features that Meshtastic messages had

### Example of the Problem

```
🔗 MESHCORE TEXTMESSAGE from Node-889fa138 (9fa138) | Hops:0/0 | SNR:11.2dB(🟢)
  └─ Msg:"Hello World" | Payload:11B | ID:123456 | RX:16:38:35
```

Problems:
- ❌ Always shows `Hops:0/0` (incorrect)
- ❌ No routing path information
- ❌ Can't see which nodes relayed the message

## Solution

### Technical Analysis

The MeshCore decoder (`meshcoredecoder` library) already extracts:
1. **`path_length`**: Number of hops the packet has traveled
2. **`path`**: Array of node IDs showing the routing path

However, these were not properly passed through to the bot's packet structure and display logic.

### Root Cause

In `meshcore_cli_wrapper.py` lines 2246-2247:

```python
# BROKEN CODE
'hopLimit': decoded_packet.path_length if hasattr(decoded_packet, 'path_length') else 0,
'hopStart': decoded_packet.path_length if hasattr(decoded_packet, 'path_length') else 0,
```

When `hopLimit = hopStart = path_length`:
- Calculation: `hops = hopStart - hopLimit = 3 - 3 = 0`
- Result: Always showed 0 hops ❌

### Implementation

#### 1. Fix Hop Calculation

**File:** `meshcore_cli_wrapper.py`

```python
# FIXED CODE
'hopLimit': 0,  # Packet received with 0 hops remaining
'hopStart': decoded_packet.path_length if hasattr(decoded_packet, 'path_length') else 0,
```

Now:
- Calculation: `hops = hopStart - hopLimit = 3 - 0 = 3`
- Result: Shows correct hop count ✅

**Reasoning:**
- `hopLimit`: Represents remaining hops when packet is received (always 0 at destination)
- `hopStart`: Represents initial hop count when packet started
- Difference gives actual hops taken

#### 2. Add Path to Packet Structure

**File:** `meshcore_cli_wrapper.py`

```python
# Add routing path if available (for hop visualization)
if hasattr(decoded_packet, 'path') and decoded_packet.path:
    bot_packet['_meshcore_path'] = decoded_packet.path
    debug_print_mc(f"   📍 Path: {' → '.join([f'0x{n:08x}' if isinstance(n, int) else str(n) for n in decoded_packet.path])}")
```

This:
- Extracts the `path` array from decoded packet
- Stores it in `bot_packet['_meshcore_path']`
- Logs the path immediately for debugging

#### 3. Display Path in Traffic Monitor

**File:** `traffic_monitor.py`

```python
# Add routing path if available (MeshCore packets)
if '_meshcore_path' in packet and packet['_meshcore_path']:
    path = packet['_meshcore_path']
    path_str = ' → '.join([f"0x{n:08x}" if isinstance(n, int) else str(n) for n in path])
    line2_parts.append(f"Path:[{path_str}]")
```

This displays the path in line 2 of the packet log.

## Results

### After Fix

```
🔗 MESHCORE TEXTMESSAGE from Node-889fa138 (9fa138) | Hops:3/3 | SNR:11.2dB(🟢)
  └─ Msg:"Hello World" | Path:[0x12345678 → 0x9abcdef0 → 0xfedcba98] | Payload:11B | ID:123456
```

Now shows:
- ✅ Correct hop count: `Hops:3/3`
- ✅ Full routing path: `Path:[0x12345678 → 0x9abcdef0 → 0xfedcba98]`
- ✅ Consistent with Meshtastic display format

### Test Results

Comprehensive test suite created: `tests/test_meshcore_hop_path.py`

```bash
$ python3 tests/test_meshcore_hop_path.py

✅ ALL TESTS PASSED (3/3)
  ✅ Path added to bot_packet
  ✅ Traffic monitor path display
  ✅ Hop calculation
```

Test scenarios:
1. **Path in bot_packet**: Verifies `_meshcore_path` field is populated
2. **Traffic monitor display**: Confirms path appears in logs
3. **Hop calculation**: Tests various hop counts (0, 1, 3, 7 hops)

## Benefits

### 1. Accurate Hop Count
Shows the real number of hops a message took through the network.

**Use case:** Verify network topology, identify if messages are taking optimal routes.

### 2. Routing Path Visibility
See the exact sequence of nodes that forwarded the message.

**Example:**
```
Path:[0x12345678 → 0x9abcdef0 → 0xfedcba98]
```
This shows the message traveled: Node1 → Node2 → Node3 → Destination

### 3. Network Troubleshooting
Identify problematic relay nodes or routing issues.

**Example:** If messages always go through the same intermediate node with high hop count, that node might be poorly positioned.

### 4. Consistent User Experience
MeshCore and Meshtastic messages now show the same information format.

### 5. Better Network Analysis
Understand network topology and optimize node placement.

## Use Cases

### 1. Troubleshooting Message Delivery

**Scenario:** Messages not reaching their destination reliably.

**Solution:** Check the path to see:
- Which nodes are involved in forwarding
- If any node consistently appears in failed message paths
- If hop count is unexpectedly high

### 2. Network Topology Mapping

**Scenario:** Understanding how nodes are connected.

**Solution:** Collect paths from multiple messages to map:
- Which nodes act as relay/router nodes
- Network structure and connectivity
- Identify critical nodes

### 3. Range Testing

**Scenario:** Testing antenna configurations or node placement.

**Solution:** Monitor hop count to see:
- If direct communication is possible (0 hops)
- If relay nodes are needed
- Which relay nodes provide the best path

### 4. Mesh Network Optimization

**Scenario:** Reducing latency and improving reliability.

**Solution:** Analyze paths to:
- Add nodes in strategic locations to reduce hops
- Identify and eliminate unnecessary relay hops
- Balance load across multiple relay nodes

## Technical Details

### Packet Structure

MeshCore RX_LOG packets now include:

```python
bot_packet = {
    'from': sender_id,
    'to': receiver_id,
    'id': packet_id,
    'rxTime': timestamp,
    'rssi': rssi,
    'snr': snr,
    'hopLimit': 0,  # Fixed: Always 0 at destination
    'hopStart': path_length,  # Number of hops taken
    'channel': 0,
    'decoded': {...},
    '_meshcore_rx_log': True,
    '_meshcore_broadcast': is_broadcast,
    '_meshcore_path': [node1_id, node2_id, node3_id]  # NEW!
}
```

### Path Array Format

The `_meshcore_path` array contains node IDs in the order they forwarded the packet:

```python
[0x12345678, 0x9abcdef0, 0xfedcba98]
```

Where:
- `0x12345678`: First node that forwarded the packet
- `0x9abcdef0`: Second relay node
- `0xfedcba98`: Final relay node before reaching us

### Display Format

**Line 1 (Header):**
```
🔗 MESHCORE TEXTMESSAGE from Node-889fa138 (9fa138) | Hops:3/3 | SNR:11.2dB(🟢)
```

**Line 2 (Details):**
```
  └─ Msg:"Hello" | Path:[0x12345678 → 0x9abcdef0 → 0xfedcba98] | Payload:11B
```

## Files Modified

### Core Changes

1. **`meshcore_cli_wrapper.py`** (lines 2246-2254)
   - Fixed hop calculation
   - Added path extraction and storage

2. **`traffic_monitor.py`** (lines 1244-1249)
   - Added path display in line 2 of logs

### Test & Documentation

3. **`tests/test_meshcore_hop_path.py`** (NEW)
   - Comprehensive test suite
   - 3 test scenarios
   - All tests passing

4. **`demos/demo_meshcore_hop_path.py`** (NEW)
   - Interactive demonstration
   - Shows before/after comparison
   - Use case examples

5. **`docs/MESHCORE_HOP_PATH.md`** (THIS FILE)
   - Complete documentation
   - Technical details
   - Use cases

## Deployment

### No Configuration Changes Required

This is a pure enhancement with no breaking changes:
- ✅ No config.py changes needed
- ✅ Backward compatible
- ✅ Automatic for all MeshCore packets

### Verification

After deployment, check logs for MeshCore messages:

```bash
journalctl -u meshtastic-bot -f | grep "MESHCORE TEXTMESSAGE"

# Should see:
🔗 MESHCORE TEXTMESSAGE from Node-XXX | Hops:N/N | SNR:X.XdB
  └─ Msg:"..." | Path:[0xXXX → 0xYYY] | Payload:XB
```

## Comparison with Meshtastic

### Before (MeshCore only)

MeshCore lacked hop/path information that Meshtastic had:

| Feature | Meshtastic | MeshCore (Before) |
|---------|-----------|-------------------|
| Hop Count | ✅ Accurate | ❌ Always 0/0 |
| Routing Path | ✅ Via relay guess | ❌ Not shown |
| Display Format | ✅ Consistent | ❌ Incomplete |

### After (Both Networks)

Now both networks have full information:

| Feature | Meshtastic | MeshCore (After) |
|---------|-----------|------------------|
| Hop Count | ✅ Accurate | ✅ Accurate |
| Routing Path | ✅ Via relay guess | ✅ Full path array |
| Display Format | ✅ Consistent | ✅ Consistent |

**Note:** MeshCore actually has MORE detailed path information since it includes the full array of relay nodes, not just a guess.

## Future Enhancements

Potential improvements for future versions:

1. **Path Analysis Statistics**
   - Track most common relay nodes
   - Identify bottleneck nodes
   - Generate network topology graphs

2. **Path-based Routing Optimization**
   - Suggest better node placement
   - Identify redundant relay nodes
   - Recommend additional relay locations

3. **Historical Path Data**
   - Store path history in database
   - Analyze path changes over time
   - Detect network changes

4. **Visual Path Display**
   - Generate network map from paths
   - Show real-time message flow
   - Highlight active relay nodes

## References

### Related Files

- `meshcore_cli_wrapper.py`: MeshCore packet processing
- `traffic_monitor.py`: Packet logging and display
- `meshcoredecoder`: External library for decoding MeshCore packets

### Related Features

- **Traffic Monitor**: Packet logging system
- **MeshCore Integration**: MeshCore network support
- **Dual Mode**: Running both Meshtastic and MeshCore

### External Documentation

- [MeshCore Protocol](https://github.com/meshcore-dev/MeshCore/wiki)
- [MeshCore Decoder](https://github.com/meshcore-dev/meshcore-decoder)

## Summary

### Problem
MeshCore messages showed `Hops:0/0` and no routing path information.

### Solution
- Fix hop calculation: `hopLimit=0`, `hopStart=path_length`
- Extract path array from decoder
- Display path in logs

### Result
- ✅ Accurate hop count
- ✅ Full routing path visible
- ✅ Consistent with Meshtastic
- ✅ Better network troubleshooting

**Status: ✅ COMPLETE**
