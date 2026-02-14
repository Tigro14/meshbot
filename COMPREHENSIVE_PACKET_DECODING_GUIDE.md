# Comprehensive MeshCore Packet Decoding Guide

## Overview

This guide explains how the diagnostic script decodes MeshCore packets received on the Public channel.

## User Request

> "Would you please decode the meshcore packets received in the Public channel ?"

**Answer:** Yes! The diagnostic script now provides comprehensive packet decoding.

## Packet Structure

### Header Information

Every decoded packet shows:

```
🔍 DECODED PACKET:
  From: 0x56a09311           # Sender node ID
  To: Broadcast (0xFFFFFFFF) # Receiver (or broadcast)
  Payload Type: 15 (TextMessage)
  Route: Flood               # Routing method
  Hops: 2                    # Number of hops traversed
  Path: 0x12345678 → 0x87654321  # Routing path
  Message Hash: a1b2c3d4...  # Unique message identifier
  Packet Size: 45 bytes
  Status: ✅ Valid
```

### Routing Information

**Hops:** Number of times the packet was retransmitted
- `Hops: 0` - Direct from sender
- `Hops: 1` - Relayed once
- `Hops: 2+` - Multiple relays

**Path:** Actual route the packet took through the mesh
- Shows node IDs in order
- Helps identify mesh topology
- Useful for debugging routing issues

**Message Hash:** Unique identifier
- Used for deduplication
- Tracks packet across network
- Prevents loops

## Payload Types

### 1. TextMessage (Type 15)

**Public Broadcast:**
```
📦 PAYLOAD:
  Type: dict
  Keys: ['raw', 'decoded']
  Decoded Type: TextMessagePayload

  ✅ DECRYPTED TEXT (📢 Public):
     "Hello everyone on the mesh!"
     → Message successfully decrypted and decoded
```

**Direct Message:**
```
📦 PAYLOAD:
  ✅ DECRYPTED TEXT (📨 Direct):
     "Hi, this is a private message"
     → Message successfully decrypted and decoded
```

**Encrypted Text:**
```
📦 PAYLOAD:
  Raw data: 39 bytes

  🔒 ENCRYPTED PAYLOAD
     ℹ️  This text message is encrypted
     → If broadcast: needs default PSK
     → If channel: needs channel PSK
     → If DM: needs default PSK (Meshtastic 2.7.15+)
```

### 2. Advert (Device Advertisement)

Shows device information and node details:

```
📦 PAYLOAD:
  Type: dict
  Decoded Type: AdvertPayload

  📣 ADVERT (Device Advertisement):
     Device: MyMeshtasticNode
     Role: Router
     Hardware: TBEAM
     Node ID: 0x56a09311
```

**What It Shows:**
- Device name
- Hardware model (T-Beam, T-Echo, etc.)
- Node role (Router, Client, Repeater)
- Node ID derived from public key
- Network participation info

### 3. NodeInfo

Complete node configuration and identity:

```
📦 PAYLOAD:
  📋 NODE INFO:
     Long Name: My Meshtastic Node
     Short Name: MYND
     Hardware: TBEAM
     Role: Router
```

**Information Included:**
- Long name (full device name)
- Short name (4-letter identifier)
- Hardware model
- Node role
- Configuration details

### 4. Position

GPS location data:

```
📦 PAYLOAD:
  📍 POSITION:
     Latitude: 47.1234
     Longitude: 6.5678
     Altitude: 450m
```

**Location Data:**
- GPS coordinates (latitude/longitude)
- Altitude above sea level
- Precision depends on GPS quality
- Used for mapping and distance calculations

### 5. Telemetry

Sensor and system status:

```
📦 PAYLOAD:
  📊 TELEMETRY:
     Battery: 85%
     Voltage: 4.2V
     Temperature: 22.5°C
     Humidity: 45%
```

**Metrics Available:**
- Battery level (percentage)
- Battery voltage
- Temperature (from device sensor)
- Humidity (if sensor available)
- Other environmental data

### 6. ResponsePayload (Type 1)

Usually encrypted responses to requests:

```
📦 PAYLOAD:
  🔒 ENCRYPTED ResponsePayload (type 1)
  Raw data: 20 bytes
  Hex: A393634C3F1DE763A4DA0C55AA1BBD0296417B3B

  🔒 ENCRYPTED PAYLOAD
     ℹ️  This is an encrypted response packet (type 1)
     → ResponsePayloads are typically encrypted responses to requests
     → To decrypt, you need the channel PSK
```

**Characteristics:**
- Usually encrypted
- Response to a request (ping, traceroute, etc.)
- Requires channel PSK for decryption
- Contains reply data

## Route Types

**Flood:** Broadcast to all nodes
- Public messages
- Network-wide announcements
- Anyone can receive

**TransportFlood:** Similar to Flood with transport layer
- Used for mesh routing
- Public broadcast with guaranteed delivery

**Direct:** Point-to-point
- Direct messages (DMs)
- Specific node targeting
- Private communication

**Reliable:** Guaranteed delivery
- Acknowledgment required
- Retransmission on failure
- Important messages

## Message Context

### Public Messages (📢)

**Indicators:**
- `To: Broadcast (0xFFFFFFFF)`
- `Route: Flood`
- Shows `📢 Public` label

**Characteristics:**
- Visible to all nodes
- No specific recipient
- Anyone can decrypt (with channel PSK)

### Direct Messages (📨)

**Indicators:**
- `To: 0x12345678` (specific node ID)
- `Route: Direct`
- Shows `📨 Direct` label

**Characteristics:**
- Intended for specific node
- May be encrypted with DM PSK
- Private communication

## Encryption Status

### Decrypted (✅)

```
✅ DECRYPTED TEXT (📢 Public):
   "Message content here"
   → Message successfully decrypted and decoded
```

**Means:**
- Correct PSK configured
- Payload decoded successfully
- Content readable

### Encrypted (🔒)

```
🔒 ENCRYPTED PAYLOAD
   ℹ️  This text message is encrypted
   → If channel: needs channel PSK
```

**Means:**
- Wrong or missing PSK
- Cannot decrypt payload
- Shows raw hex data only
- Need to configure correct key

## Practical Examples

### Example 1: Public Text Message

```
================================================================================
[2026-02-13 08:30:15.123] 📡 MESHCORE EVENT RECEIVED
================================================================================
Event Type: EventType.RX_LOG_DATA
✅ This is RX_LOG_DATA (ALL RF packets)

📋 RAW DATA:
  Keys: ['raw_hex', 'snr', 'rssi', 'payload', 'payload_length']
  raw_packet: 45 bytes
    Hex: 2d0f001150ea9affffffff166b386df250...

🔍 DECODED PACKET:
  From: 0x56a09311
  To: Broadcast (0xFFFFFFFF)
  Payload Type: 15 (TextMessage)
  Route: Flood
  Hops: 0
  Message Hash: 166b386df250...
  Packet Size: 45 bytes
  Status: ✅ Valid

📦 PAYLOAD:
  Type: dict
  Keys: ['raw', 'decoded']
  Decoded Type: TextMessagePayload

  ✅ DECRYPTED TEXT (📢 Public):
     "Hello mesh network!"
     → Message successfully decrypted and decoded
```

**Interpretation:**
- Public broadcast message
- Sent by node 0x56a09311
- Successfully decrypted
- No relays (Hops: 0)
- Text content: "Hello mesh network!"

### Example 2: Device Advertisement

```
🔍 DECODED PACKET:
  From: 0x4f9daba9
  To: Broadcast (0xFFFFFFFF)
  Payload Type: 3 (Advert)
  Route: Flood
  Hops: 1
  Packet Size: 85 bytes
  Status: ✅ Valid

📦 PAYLOAD:
  📣 ADVERT (Device Advertisement):
     Device: RouterNode01
     Role: Router
     Hardware: TBEAM
     Node ID: 0x4f9daba9
```

**Interpretation:**
- Device announcing presence
- Router role node
- T-Beam hardware
- Relayed once (Hops: 1)

### Example 3: Position Update

```
🔍 DECODED PACKET:
  From: 0x12345678
  To: Broadcast (0xFFFFFFFF)
  Payload Type: 7 (Position)
  Route: Flood
  Hops: 0
  Status: ✅ Valid

📦 PAYLOAD:
  📍 POSITION:
     Latitude: 47.1234
     Longitude: 6.5678
     Altitude: 450m
```

**Interpretation:**
- GPS location broadcast
- Coordinates: 47.1234, 6.5678
- Altitude: 450 meters
- Direct from sender (no relays)

### Example 4: Telemetry Data

```
🔍 DECODED PACKET:
  From: 0x87654321
  To: Broadcast (0xFFFFFFFF)
  Payload Type: 11 (Telemetry)
  Route: Flood
  Status: ✅ Valid

📦 PAYLOAD:
  📊 TELEMETRY:
     Battery: 78%
     Voltage: 4.1V
     Temperature: 21.3°C
```

**Interpretation:**
- System status update
- Battery at 78%
- Temperature sensor reading
- All systems normal

## Troubleshooting

### Problem: All Messages Show Encrypted

**Solution:**
1. Check channel PSK configuration
2. Verify you're using correct channel
3. Ensure PSK matches network

### Problem: No Decoded Text

**Solution:**
1. Message may be encrypted
2. Different payload type (not TextMessage)
3. Check for `🔒 ENCRYPTED` indicator

### Problem: Only Seeing Raw Hex

**Solution:**
1. Install meshcoredecoder: `pip install meshcoredecoder`
2. Restart diagnostic script
3. Should see `✅ meshcoredecoder library available`

### Problem: Invalid Packets

**Solution:**
1. Check for `⚠️ Errors` section
2. May indicate truncated packet
3. Could be incompatible firmware version
4. Radio interference possible

## Using the Diagnostic Tool

### Run the Script

```bash
cd /home/dietpi/bot
python3 listen_meshcore_debug.py /dev/ttyACM1
```

### What You'll See

1. **Connection:**
   - `✅ Connected to MeshCore`
   - `✅ Auto message fetching started`

2. **Every Message:**
   - Full packet structure
   - Decoded payload
   - Routing information
   - Encryption status

3. **Useful for:**
   - Debugging encryption
   - Understanding mesh traffic
   - Monitoring node activity
   - Analyzing network topology
   - Testing configuration

## Summary

The diagnostic script now provides:

- ✅ **Complete packet structure** (sender, receiver, type, route)
- ✅ **Routing information** (hops, path, hash)
- ✅ **Decoded text messages** (public and direct)
- ✅ **Device information** (adverts, node info)
- ✅ **Location data** (GPS coordinates)
- ✅ **Telemetry** (battery, temperature, sensors)
- ✅ **Encryption status** (decrypted vs encrypted)
- ✅ **Visual context** (📢 public, 📨 direct, 📣 advert, etc.)

**User request fulfilled: Full MeshCore packet decoding for Public channel!** 🎉
