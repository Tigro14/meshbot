# Dual Network Architecture - Visual Guide

This document provides visual diagrams to help understand how the dual network mode works.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Raspberry Pi 5 (Bot Host)                    │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                     MeshBot Core                          │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │           DualInterfaceManager                     │  │ │
│  │  │                                                    │  │ │
│  │  │  ┌─────────────────┐    ┌─────────────────┐      │  │ │
│  │  │  │ Meshtastic      │    │ MeshCore        │      │  │ │
│  │  │  │ Interface       │    │ Interface       │      │  │ │
│  │  │  │                 │    │                 │      │  │ │
│  │  │  │ /dev/ttyACM0    │    │ /dev/ttyUSB0    │      │  │ │
│  │  │  └────────┬────────┘    └────────┬────────┘      │  │ │
│  │  │           │                      │               │  │ │
│  │  │           └──────────┬───────────┘               │  │ │
│  │  │                      │                           │  │ │
│  │  │           ┌──────────▼──────────┐                │  │ │
│  │  │           │  Message Router     │                │  │ │
│  │  │           │  - Tracks source    │                │  │ │
│  │  │           │  - Routes replies   │                │  │ │
│  │  │           └─────────────────────┘                │  │ │
│  │  └────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
└───────────────────┬──────────────────────┬──────────────────┘
                    │                      │
            ┌───────▼────────┐     ┌──────▼───────────┐
            │ Meshtastic     │     │ MeshCore         │
            │ Radio          │     │ Radio            │
            │                │     │                  │
            │ Frequency: A   │     │ Frequency: B     │
            └───────┬────────┘     └──────┬───────────┘
                    │                     │
            ┌───────▼────────┐     ┌──────▼───────────┐
            │ Meshtastic     │     │ MeshCore         │
            │ Network        │     │ Network          │
            │ (Community A)  │     │ (Community B)    │
            └────────────────┘     └──────────────────┘
```

## Message Flow: Incoming

### Scenario 1: Message from Meshtastic Network

```
User on Meshtastic Network
         │
         │ "Hey bot, /weather"
         │
         ▼
  ┌──────────────┐
  │ Meshtastic   │
  │ Radio        │
  └──────┬───────┘
         │ /dev/ttyACM0
         │
         ▼
  ┌──────────────────────────┐
  │ DualInterfaceManager     │
  │                          │
  │ on_meshtastic_message()  │
  │   → tag: MESHTASTIC      │
  └──────┬───────────────────┘
         │
         │ packet + network_source
         │
         ▼
  ┌─────────────────┐
  │ on_message()    │
  │                 │
  │ 1. Track sender │ ← stores: {sender_id: MESHTASTIC}
  │ 2. Process cmd  │
  └─────────────────┘
```

### Scenario 2: Message from MeshCore Network

```
User on MeshCore Network
         │
         │ "Hey bot, /weather"
         │
         ▼
  ┌──────────────┐
  │ MeshCore     │
  │ Radio        │
  └──────┬───────┘
         │ /dev/ttyUSB0
         │
         ▼
  ┌──────────────────────────┐
  │ DualInterfaceManager     │
  │                          │
  │ on_meshcore_message()    │
  │   → tag: MESHCORE        │
  └──────┬───────────────────┘
         │
         │ packet + network_source
         │
         ▼
  ┌─────────────────┐
  │ on_message()    │
  │                 │
  │ 1. Track sender │ ← stores: {sender_id: MESHCORE}
  │ 2. Process cmd  │
  └─────────────────┘
```

## Message Flow: Outgoing (Reply Routing)

### Automatic Reply Routing

```
User sends "/weather" from Meshtastic
         │
         ▼
    [Incoming flow - tracked as MESHTASTIC]
         │
         ▼
  ┌─────────────────┐
  │ Command Handler │
  │                 │
  │ generate_reply()│
  └─────┬───────────┘
        │ "Paris: 15°C, Sunny"
        │
        ▼
  ┌──────────────────┐
  │ MessageSender    │
  │                  │
  │ send_single()    │
  │   1. Look up sender_network_map
  │   2. Find: MESHTASTIC
  └─────┬────────────┘
        │
        ▼
  ┌──────────────────────────┐
  │ DualInterfaceManager     │
  │                          │
  │ send_message(            │
  │   text=reply,            │
  │   dest=sender_id,        │
  │   network=MESHTASTIC     │ ← Routed to correct network!
  │ )                        │
  └─────┬────────────────────┘
        │
        ▼
  ┌──────────────┐
  │ Meshtastic   │
  │ Radio        │ ← Reply goes back to Meshtastic
  └──────────────┘
```

## Network Source Tracking

### Sender Network Map

```
┌───────────────────────────────────────────┐
│     MessageSender._sender_network_map     │
├─────────────────┬─────────────────────────┤
│   Sender ID     │   Network Source        │
├─────────────────┼─────────────────────────┤
│   0x12345678    │   MESHTASTIC            │
│   0x87654321    │   MESHCORE              │
│   0xABCDEF00    │   MESHTASTIC            │
│   0x11111111    │   MESHCORE              │
└─────────────────┴─────────────────────────┘

This map is used to route replies:
- When reply needed → Look up sender ID
- Get network source → Route to that network
- If not found → Use primary (Meshtastic)
```

## Statistics Aggregation

### Packet Counters

```
┌─────────────────────────────────────────────────┐
│         DualInterfaceManager Statistics         │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌────────────────────┐  ┌────────────────────┐│
│  │ Meshtastic Network │  │ MeshCore Network   ││
│  │                    │  │                    ││
│  │ Packets: 1,234     │  │ Packets: 567       ││
│  │ Last: 2s ago       │  │ Last: 5s ago       ││
│  └────────────────────┘  └────────────────────┘│
│                                                 │
│  ┌────────────────────────────────────────────┐│
│  │          Aggregate Statistics              ││
│  │                                            ││
│  │  Total Packets: 1,801                      ││
│  │  Dual Mode: Active                         ││
│  │  Primary: Meshtastic                       ││
│  └────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

## Command Availability Matrix

```
┌────────────────────┬────────────────┬────────────────┐
│     Command        │  Meshtastic    │   MeshCore     │
├────────────────────┼────────────────┼────────────────┤
│ /bot <question>    │       ✅       │       ✅       │
│ /help              │       ✅       │       ✅       │
│ /weather           │       ✅       │       ✅       │
│ /power             │       ✅       │       ✅       │
│ /sys               │       ✅       │       ✅       │
├────────────────────┼────────────────┼────────────────┤
│ /nodes             │       ✅       │       ❌       │
│ /neighbors         │       ✅       │       ❌       │
│ /my                │       ✅       │       ❌       │
│ /trace             │       ✅       │       ❌       │
│ /stats             │       ✅       │       ❌       │
│ /echo              │       ✅       │       ❌       │
└────────────────────┴────────────────┴────────────────┘

Legend:
✅ = Fully supported
❌ = Not available (requires full mesh network)
```

## Configuration Flow

### Single Mode vs Dual Mode

```
┌─────────────────────────────────────────────────┐
│              Configuration File                 │
└──────────────┬──────────────────────────────────┘
               │
        ┌──────▼──────┐
        │ DUAL_MODE?  │
        └──────┬──────┘
               │
       ┌───────┴──────┐
       │              │
     False          True
       │              │
       ▼              ▼
┌────────────┐  ┌────────────────┐
│ SINGLE     │  │ DUAL           │
│ MODE       │  │ MODE           │
│            │  │                │
│ Meshtastic │  │ Meshtastic +   │
│    OR      │  │ MeshCore       │
│ MeshCore   │  │                │
└────────────┘  └────────────────┘
       │              │
       └──────┬───────┘
              │
              ▼
    ┌─────────────────┐
    │ Bot Initialized │
    └─────────────────┘
```

## Troubleshooting Flow

### Connection Debugging

```
Start Bot
    │
    ▼
┌────────────────┐
│ Check Dual     │     No      ┌──────────────────┐
│ Mode Config?   ├────────────►│ Use Single Mode  │
└────────┬───────┘             └──────────────────┘
         │ Yes
         ▼
┌────────────────┐
│ Both Radios    │     No      ┌──────────────────┐
│ Connected?     ├────────────►│ Fallback to      │
└────────┬───────┘             │ Single Mode      │
         │ Yes                 └──────────────────┘
         ▼
┌────────────────┐
│ Meshtastic     │     Fail    ┌──────────────────┐
│ Init OK?       ├────────────►│ Error: Cannot    │
└────────┬───────┘             │ Start            │
         │ OK                  └──────────────────┘
         ▼
┌────────────────┐
│ MeshCore       │     Fail    ┌──────────────────┐
│ Init OK?       ├────────────►│ Fallback to      │
└────────┬───────┘             │ Meshtastic Only  │
         │ OK                  └──────────────────┘
         ▼
┌────────────────┐
│ ✅ Dual Mode   │
│    Active      │
└────────────────┘
```

## Network Isolation

### Security Boundaries

```
┌────────────────────────────────────────────────┐
│                                                │
│  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Meshtastic       │  │ MeshCore         │  │
│  │ Network          │  │ Network          │  │
│  │                  │  │                  │  │
│  │ PSK: ********    │  │ Contacts: XYZ    │  │
│  │ Channel: 0       │  │ Keys: Private    │  │
│  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │             │
│           └──────────┬──────────┘             │
│                      │                        │
│                ┌─────▼─────┐                  │
│                │    Bot    │                  │
│                │           │                  │
│                │ No Bridge │ ← Networks isolated
│                │ No Forward│
│                └───────────┘                  │
│                                                │
│  Messages received from each network          │
│  but NOT automatically forwarded              │
└────────────────────────────────────────────────┘
```

## Hardware Setup Example

### Raspberry Pi 5 Connections

```
                 Raspberry Pi 5
         ┌──────────────────────────┐
         │                          │
         │  ┌────────────────┐      │
         │  │  USB Port 1    │      │
         │  └────────┬───────┘      │
         │           │ /dev/ttyACM0 │
         │           ▼              │
         │     ┌──────────┐         │
         │     │Meshtastic│         │
         │     │  T-Beam  │         │
         │     └──────────┘         │
         │                          │
         │  ┌────────────────┐      │
         │  │  USB Port 2    │      │
         │  └────────┬───────┘      │
         │           │ /dev/ttyUSB0 │
         │           ▼              │
         │     ┌──────────┐         │
         │     │ MeshCore │         │
         │     │  Device  │         │
         │     └──────────┘         │
         │                          │
         └──────────────────────────┘

Antenna Placement:
- Separate antennas by at least 30cm
- Use different frequencies (e.g., 868MHz vs 915MHz)
- Consider directional antennas for isolation
```

## Performance Monitoring

### System Resources

```
┌─────────────────────────────────────────────┐
│         System Resource Usage               │
├─────────────────────────────────────────────┤
│                                             │
│  Single Mode:                               │
│  ┌────────────────────────────────────────┐│
│  │ CPU: ░░░░░░░░░░ 20%                    ││
│  │ RAM: ░░░░░░░░░░░░ 150MB                ││
│  └────────────────────────────────────────┘│
│                                             │
│  Dual Mode:                                 │
│  ┌────────────────────────────────────────┐│
│  │ CPU: ░░░░░░░░░░░░░ 35%                 ││
│  │ RAM: ░░░░░░░░░░░░░░░░ 220MB            ││
│  └────────────────────────────────────────┘│
│                                             │
│  Additional overhead: ~15% CPU, ~70MB RAM   │
└─────────────────────────────────────────────┘
```

## Summary Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Dual Network Bot                     │
│                                                         │
│  Features:                                              │
│  • Two separate mesh networks                           │
│  • Automatic reply routing                              │
│  • Aggregated statistics                                │
│  • Network isolation                                    │
│  • Backward compatible                                  │
│                                                         │
│  Requirements:                                          │
│  • 2 physical radios                                    │
│  • Different frequencies                                │
│  • Raspberry Pi 4/5                                     │
│  • meshcore-cli library                                 │
│                                                         │
│  Configuration:                                         │
│  • DUAL_NETWORK_MODE = True                             │
│  • MESHTASTIC_ENABLED = True                            │
│  • MESHCORE_ENABLED = True                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```
