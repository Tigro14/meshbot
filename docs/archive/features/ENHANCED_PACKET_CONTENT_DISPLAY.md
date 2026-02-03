# Enhanced Packet Content Display

## Overview

Enhanced the MeshCore RX_LOG display to show detailed packet type/family/content information for public messages, advertising packets, and routing packets.

## Problem Statement

> "I want the packet type to be displayed, the packet type/family/content when public, advertising/routing packets, ..."

The existing display showed basic packet type and route but lacked context about:
- Whether messages are public/broadcast vs direct/unicast
- Device information in advertisements (role, location)
- Group message context
- Routing packet purposes

## Solution Implemented

Enhanced `meshcore_cli_wrapper.py::_on_rx_log_data()` to display:

### 1. Message Type Context

**Text Messages** now show if they're public or direct:
- 📢 Public Message (Flood route)
- 📨 Direct Message (Direct route)

**Before:**
```
[DEBUG] 📝 [RX_LOG] Message: "Hello from the mesh"
```

**After:**
```
[DEBUG] 📝 [RX_LOG] 📢 Public Message: "Hello from the mesh"
```

### 2. Advertisement Details

**Advertisements** now show:
- Device name
- Device role (ChatNode, Repeater, RoomServer, Sensor)
- GPS coordinates when available

**Before:**
```
[DEBUG] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar
```

**After:**
```
[DEBUG] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar | Role: Repeater | GPS: (47.5440, -122.1086)
```

### 3. Group Messages

**Group messages** show context:
```
[DEBUG] 👥 [RX_LOG] Group Text (public broadcast)
```

### 4. Routing Packets

**Routing packets** show their purpose:
- 🔍 Trace packet (routing diagnostic)
- 🛣️  Path packet (routing info)

## Implementation Details

### Code Changes

**File:** `meshcore_cli_wrapper.py`

Enhanced the payload display section (lines ~1440-1490) to:

1. **Detect public/broadcast routes**
   ```python
   from meshcoredecoder.types import RouteType as RT
   is_public = packet.route_type in [RT.Flood, RT.TransportFlood]
   ```

2. **Text messages with context**
   ```python
   if hasattr(decoded_payload, 'text'):
       msg_type = "📢 Public" if is_public else "📨 Direct"
       debug_print(f"📝 [RX_LOG] {msg_type} Message: \"{text}\"")
   ```

3. **Enhanced advertisement display**
   ```python
   advert_parts = [f"from: {name}"]
   
   # Add device role
   if 'device_role' in app_data:
       role = app_data['device_role']
       role_name = str(role).split('.')[-1]
       advert_parts.append(f"Role: {role_name}")
   
   # Add GPS location
   if app_data.get('has_location'):
       location = app_data.get('location', {})
       lat = location.get('latitude', 0)
       lon = location.get('longitude', 0)
       advert_parts.append(f"GPS: ({lat:.4f}, {lon:.4f})")
   ```

4. **Group message indicators**
   ```python
   elif packet.payload_type.name in ['GroupText', 'GroupData']:
       content_type = "Group Text" if packet.payload_type.name == 'GroupText' else "Group Data"
       debug_print(f"👥 [RX_LOG] {content_type} (public broadcast)")
   ```

5. **Routing packet labels**
   ```python
   elif packet.payload_type.name == 'Trace':
       debug_print(f"🔍 [RX_LOG] Trace packet (routing diagnostic)")
   elif packet.payload_type.name == 'Path':
       debug_print(f"🛣️  [RX_LOG] Path packet (routing info)")
   ```

## Example Output

### Advertisement with Full Context

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (134B) - SNR:11.5dB RSSI:-58dBm Hex:11007E7662676F7F0850A8A355BAAFBFC1EB7B41...
[DEBUG] 📦 [RX_LOG] Type: Advert | Route: Flood | Size: 134B | Hash: F9C060FE | Status: ✅
[DEBUG] 📢 [RX_LOG] Advert from: WW7STR/PugetMesh Cougar | Role: Repeater | GPS: (47.5440, -122.1086)
```

### Public Text Message

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (65B) - SNR:12.0dB RSSI:-55dBm Hex:21007E7662676F7F0850...
[DEBUG] 📦 [RX_LOG] Type: TextMessage | Route: Flood | Size: 65B | Hash: A1B2C3D4 | Status: ✅
[DEBUG] 📝 [RX_LOG] 📢 Public Message: "Hello mesh network!"
```

### Direct Message

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (45B) - SNR:14.5dB RSSI:-45dBm Hex:22007E7662676F7F0850...
[DEBUG] 📦 [RX_LOG] Type: TextMessage | Route: Direct | Size: 45B | Hash: E5F6G7H8 | Status: ✅
[DEBUG] 📝 [RX_LOG] 📨 Direct Message: "Private message"
```

### Group Message

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (55B) - SNR:11.0dB RSSI:-60dBm Hex:51007E7662676F7F0850...
[DEBUG] 📦 [RX_LOG] Type: GroupText | Route: Flood | Size: 55B | Status: ✅
[DEBUG] 👥 [RX_LOG] Group Text (public broadcast)
```

### Routing Packets

```
[DEBUG] 📡 [RX_LOG] Paquet RF reçu (30B) - SNR:10.5dB RSSI:-65dBm Hex:81007E7662676F7F0850...
[DEBUG] 📦 [RX_LOG] Type: Path | Route: Flood | Size: 30B | Status: ✅
[DEBUG] 🛣️  [RX_LOG] Path packet (routing info)
```

## Benefits

### 1. Better Network Understanding
- **Public vs Direct**: Immediately see message visibility
- **Device Roles**: Understand node functions (Repeater, Sensor, etc.)
- **Location Awareness**: Track nodes with GPS capability

### 2. Improved Debugging
- **Message Flow**: Distinguish broadcast from unicast traffic
- **Device Context**: Know what role each device plays
- **Routing Analysis**: Identify trace and path packets

### 3. Network Monitoring
- **Traffic Patterns**: See ratio of public vs direct messages
- **Device Discovery**: Track advertisers and their roles
- **Topology Insights**: Monitor routing packets

## Device Roles

The system recognizes these MeshCore device roles:

| Role | Value | Description |
|------|-------|-------------|
| **ChatNode** | 1 | Standard messaging node |
| **Repeater** | 2 | Network range extender |
| **RoomServer** | 3 | Message hub/server |
| **Sensor** | 4 | Data collection device |

## Route Types

Packets are classified by route type:

| Type | Classification | Icon |
|------|----------------|------|
| **Flood** | Public/Broadcast | 📢 |
| **TransportFlood** | Public/Transport | 📢 |
| **Direct** | Private/Unicast | 📨 |
| **TransportDirect** | Private/Transport | 📨 |

## Packet Families

Enhanced display covers these packet families:

1. **Text Messages** - Personal and public communications
2. **Advertisements** - Device announcements with metadata
3. **Group Messages** - Multi-recipient broadcasts
4. **Routing Packets** - Network topology and diagnostics
5. **Custom Types** - Application-specific packets

## Testing

### Demo Script

Run the demonstration:
```bash
python3 demo_enhanced_packet_content.py
```

The demo shows:
- Advertisement with device role and GPS
- Unknown type packets on public routes
- Error handling for malformed packets
- All enhanced display features

### Manual Testing

1. Start bot with MeshCore in debug mode
2. Observe RX_LOG_DATA events
3. Verify new fields appear:
   - Public/Direct indicators on text messages
   - Device role and GPS on adverts
   - Group message indicators
   - Routing packet labels

## Backward Compatibility

✅ **100% backward compatible**
- No breaking changes
- Existing displays still work
- New info only shows when available
- Graceful handling of missing fields

## Performance

✅ **Zero overhead**
- Display-only enhancements
- No additional computation
- Same number of log lines (just more informative)
- Conditional checks only when payload decoded

## Dependencies

- Uses existing `meshcoredecoder` library
- No new dependencies added
- Compatible with meshcoredecoder >= 0.2.0

## Future Enhancements

Possible future additions:
- Request/Response correlation
- Multi-part message tracking
- Encrypted message indicators
- Signature validation status
- Timestamp display for adverts
- Distance calculation from GPS coordinates

## Related Documentation

- `MESHCORE_RX_LOG_IMPROVEMENTS.md` - Previous RX_LOG enhancements
- `MESHCORE_DECODER_INTEGRATION.md` - Initial decoder integration
- `demo_enhanced_packet_content.py` - Interactive demonstration
