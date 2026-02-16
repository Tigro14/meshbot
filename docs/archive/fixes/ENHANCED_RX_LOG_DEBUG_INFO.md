# Enhanced MeshCore RX_LOG Packet Debug Information

## Overview

This document describes the enhancements made to the MeshCore RX_LOG packet display to provide more comprehensive debugging information for mesh network analysis.

## Problem Statement

The original RX_LOG display showed basic packet information but lacked key details needed for effective network debugging:

```
Feb 03 12:18:40 DietPi meshtastic-bot[663039]: [DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (132B) - SNR:12.25dB RSSI:-49dBm Hex:31cf11024abfe1f098b837d0b3d11d59988d5590...
Feb 03 12:18:40 DietPi meshtastic-bot[663039]: [DEBUG][MC] 📦 [RX_LOG] Type: Unknown(12) | Route: Flood | Size: 132B | Status: ℹ️
```

**Missing Information:**
- Hop count visibility (only shown when > 0)
- Routing path (which nodes the packet traversed)
- Node identification in adverts
- Consistent routing information display

## Solution

Enhanced the `_on_rx_log_data()` method in `meshcore_cli_wrapper.py` to extract and display additional packet information available from the meshcore-decoder library.

## Enhancements Implemented

### 1. Always Display Hop Count

**Before:** Hops only shown when `path_length > 0`
```python
if packet.path_length > 0:
    info_parts.append(f"Hops: {packet.path_length}")
```

**After:** Hops always displayed
```python
# Always show hops, even if 0, for routing visibility
info_parts.append(f"Hops: {packet.path_length}")
```

**Benefit:** Provides consistent routing information, making it easier to distinguish direct packets (Hops: 0) from multi-hop packets.

**Example Output:**
```
[DEBUG][MC] 📦 [RX_LOG] Type: Unknown(12) | Route: Flood | Size: 132B | Hops: 0 | Status: ℹ️
                                                                        ^^^^^^^^ Always shown
```

### 2. Display Routing Path

**New Feature:** Shows the actual path a packet took through the mesh network.

```python
# Add actual routing path if available
if hasattr(packet, 'path') and packet.path:
    # Path is a list of node IDs the packet traveled through
    path_str = ' → '.join([f"0x{node:08x}" if isinstance(node, int) else str(node) for node in packet.path])
    info_parts.append(f"Path: {path_str}")
```

**Benefit:** Visualizes the packet's journey through intermediate nodes, helping diagnose routing issues and understand network topology.

**Example Output:**
```
[DEBUG][MC] 📦 [RX_LOG] Type: TextMessage | Route: Flood | Size: 85B | Hash: A1B2C3D4 | Hops: 2 | Path: 0x12345678 → 0xabcdef01 | Status: ✅
                                                                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                                                          Shows which nodes forwarded this packet
```

**Note:** Path information is only displayed when available in the packet. Most packets may not include this data.

### 3. Node ID in Advertisements

**New Feature:** Derives node ID from public key in advertisement packets.

```python
# Add public key prefix for node identification
if hasattr(decoded_payload, 'public_key') and decoded_payload.public_key:
    pubkey_prefix = decoded_payload.public_key[:12]  # First 6 bytes (12 hex chars)
    # Derive node ID from public key (first 4 bytes)
    node_id_hex = decoded_payload.public_key[:8]  # First 4 bytes (8 hex chars)
    try:
        node_id = int(node_id_hex, 16)
        advert_parts.append(f"Node: 0x{node_id:08x}")
    except:
        advert_parts.append(f"PubKey: {pubkey_prefix}...")
```

**Benefit:** Provides clear node identification in advertisement packets, making it easier to track which nodes are active on the network.

**Example Output:**
```
[DEBUG][MC] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar | Node: 0x7e766267 | Role: Repeater | GPS: (47.5440, -122.1086)
                                                               ^^^^^^^^^^^^^^^^
                                                               Derived from public key
```

### 4. Existing Features Retained

The following features were already implemented and continue to work:

- **Node Name:** Displayed from `app_data.name` in adverts
- **GPS Position:** Shown from `app_data.location` when available
- **Device Role:** Extracted from `app_data.device_role`
- **Message Hash:** Packet identifier for tracking
- **Transport Codes:** Routing transport information when available

## Complete Example Outputs

### Advertisement Packet (Full Information)
```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662676F7F0850A8A355BAAFBFC1EB7B41...
[DEBUG][MC] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hash: F9C060FE | Hops: 0 | Status: ✅
[DEBUG][MC] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar | Node: 0x7e766267 | Role: Repeater | GPS: (47.5440, -122.1086)
```

**Information Shown:**
- Packet size: 134B
- Signal quality: SNR 11.5dB, RSSI -58dBm
- Message hash: F9C060FE
- Hop count: 0 (direct)
- Node name: WW7STR/PugetMesh Cougar
- Node ID: 0x7e766267 (derived from public key)
- Device role: Repeater
- GPS coordinates: (47.5440, -122.1086)

### Unknown Packet Type
```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (132B) - SNR:12.25dB RSSI:-49dBm Hex:31cf11024abfe1f098b837d0b3d11d59988d5590...
[DEBUG][MC] 📦 [RX_LOG] Type: Unknown(12) | Route: Flood | Size: 132B | Hops: 0 | Status: ℹ️
```

**Information Shown:**
- Packet size: 132B
- Signal quality: SNR 12.25dB, RSSI -49dBm
- Unknown type with numeric ID: 12
- Hop count: 0 (always shown now)
- Status: Info (not an error for unknown types)

### Multi-hop Packet with Path (When Available)
```
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (85B) - SNR:8.5dB RSSI:-78dBm Hex:...
[DEBUG][MC] 📦 [RX_LOG] Type: TextMessage | Route: Flood | Size: 85B | Hash: A1B2C3D4 | Hops: 2 | Path: 0x12345678 → 0xabcdef01 | Status: ✅
```

**Information Shown:**
- Hop count: 2 (packet forwarded twice)
- Routing path: Shows the two intermediate nodes
- Helps visualize network topology

## Use Cases

### 1. Network Topology Analysis
The hop count and path information help understand:
- Which nodes are acting as repeaters
- How packets flow through the network
- Potential routing bottlenecks

### 2. Coverage Analysis
GPS coordinates and node IDs help:
- Map node locations
- Identify coverage gaps
- Plan node placement

### 3. Routing Diagnostics
Path and transport information help:
- Debug routing issues
- Understand why packets take certain paths
- Optimize network configuration

### 4. Node Identification
Node IDs derived from public keys help:
- Track individual nodes
- Correlate advertisements with other packet types
- Build node databases

## Technical Details

### Modified Files
- `meshcore_cli_wrapper.py` - Enhanced `_on_rx_log_data()` method
  - Lines ~1393-1406: Always show hops, add path display
  - Lines ~1455-1478: Add node ID extraction from public key

### Dependencies
- `meshcoredecoder>=0.1.0` - Packet decoding library
- `meshcoredecoder.types` - Type definitions

### Backward Compatibility
All enhancements are backward compatible:
- Missing data is gracefully handled
- Only available information is displayed
- No breaking changes to existing functionality

## Testing

### Test Suite
Created comprehensive test suite in `test_rx_log_enhancements.py`:
- Tests various packet types
- Verifies all enhancements are displayed correctly
- Validates graceful handling of missing data

Run tests:
```bash
python3 test_rx_log_enhancements.py
```

### Visual Demo
Created visual comparison demo in `demo_rx_log_enhancements.py`:
- Shows before/after comparisons
- Demonstrates all enhancements
- Provides usage examples

Run demo:
```bash
python3 demo_rx_log_enhancements.py
```

## Future Enhancements

Potential future improvements:
1. **From/To Node IDs:** If available in RX_LOG event payload
2. **Signal Quality Trend:** Track signal quality over time
3. **Path Latency:** Measure propagation delay through hops
4. **Node Distance:** Calculate distance based on GPS coordinates
5. **Network Graph:** Visualize routing paths graphically

## References

- MeshCore Documentation: See `MESHCORE_RX_LOG_IMPLEMENTATION.md`
- Decoder Integration: See `MESHCORE_DECODER_INTEGRATION.md`
- Packet Types: See `MESHCORE_DECODER_QUICK_REFERENCE.md`

## Summary

These enhancements provide significantly more visibility into mesh network operations without any breaking changes. The additional information helps with:
- Network troubleshooting
- Performance optimization
- Coverage planning
- Node management

All improvements maintain the existing log format structure while adding valuable new data points where available.
