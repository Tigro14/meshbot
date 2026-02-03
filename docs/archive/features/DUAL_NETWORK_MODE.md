# Dual Network Mode: Meshtastic + MeshCore

## Overview

**NEW FEATURE**: The bot can now connect to **TWO SEPARATE mesh networks** simultaneously - a Meshtastic network AND a MeshCore network operating on different frequencies.

This allows you to be present on both networks at the same time, receiving messages from both and routing replies back to the correct network.

## Use Cases

### When to Use Dual Network Mode

- **Primary + Secondary Networks**: Connect to your main Meshtastic community network and a secondary MeshCore experimental network
- **Bridging Networks**: Act as a bridge between two separate mesh communities
- **Testing & Development**: Test MeshCore integration while maintaining your Meshtastic connection
- **Network Diversity**: Participate in both ecosystems simultaneously

### When NOT to Use Dual Network Mode

- **Single Network**: If you only have one mesh network, use single mode (simpler)
- **Limited Hardware**: Requires two physical radios - not possible with single radio
- **Frequency Conflicts**: Both networks must use different frequencies to avoid interference

## Requirements

### Hardware Requirements

1. **Two Physical Radios**:
   - One Meshtastic-compatible radio (e.g., `/dev/ttyACM0`)
   - One MeshCore-compatible radio (e.g., `/dev/ttyUSB0`)

2. **Different Frequencies**:
   - Each network must operate on a different frequency
   - Prevents RF interference between the two radios

### Software Requirements

- `MESHTASTIC_ENABLED = True` in `config.py`
- `MESHCORE_ENABLED = True` in `config.py`
- `DUAL_NETWORK_MODE = True` in `config.py`
- MeshCore library installed: `pip install meshcore-cli`

## Configuration

### Basic Configuration

```python
# config.py

# ========================================
# DUAL NETWORK MODE
# ========================================
DUAL_NETWORK_MODE = True  # Enable dual network support

# ========================================
# MESHTASTIC CONFIGURATION
# ========================================
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'serial'  # or 'tcp'
SERIAL_PORT = "/dev/ttyACM0"  # Meshtastic radio

# ========================================
# MESHCORE CONFIGURATION
# ========================================
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore radio
```

### Advanced Configuration

```python
# config.py

# Meshtastic via TCP (for remote node)
DUAL_NETWORK_MODE = True
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'tcp'
TCP_HOST = "192.168.1.38"
TCP_PORT = 4403

# MeshCore via Serial (local radio)
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────┐
│        Bot (Raspberry Pi)               │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │   DualInterfaceManager            │ │
│  │                                   │ │
│  │   ┌─────────────┐ ┌─────────────┐│ │
│  │   │ Meshtastic  │ │  MeshCore   ││ │
│  │   │ Interface   │ │  Interface  ││ │
│  │   └──────┬──────┘ └──────┬──────┘│ │
│  └──────────┼─────────────────┼──────┘ │
│             │                 │        │
└─────────────┼─────────────────┼────────┘
              │                 │
      ┌───────▼───────┐ ┌──────▼──────┐
      │ Meshtastic    │ │  MeshCore   │
      │ Network       │ │  Network    │
      │ (Freq A)      │ │  (Freq B)   │
      └───────────────┘ └─────────────┘
```

### Message Flow

1. **Incoming Messages**:
   - Messages from Meshtastic arrive via first interface
   - Messages from MeshCore arrive via second interface
   - Each message is tagged with its network source
   - Both are processed by the same bot logic

2. **Network Tracking**:
   - The bot tracks which network each sender came from
   - Mapping stored: `{sender_id: network_source}`
   - Used for routing replies back to correct network

3. **Outgoing Messages**:
   - Replies are automatically routed to the sender's network
   - If network source unknown, uses primary interface (Meshtastic)
   - Broadcasts go to primary network only

### Statistics Aggregation

The bot aggregates statistics from both networks:

- **Total Packets**: Combined count from both networks
- **Per-Network Stats**: Separate counters for each
- **Activity Tracking**: Last packet time per network

## Commands

### Available Commands

All standard bot commands work in dual mode:

**Full Feature Set** (Meshtastic network):
- `/nodes` - Show all mesh nodes
- `/neighbors` - Show network topology
- `/my` - Show your signal
- `/trace <node>` - Traceroute
- `/stats` - Network statistics
- `/bot <question>` - AI chat
- `/echo <message>` - Broadcast
- All other commands

**Limited Feature Set** (MeshCore network):
- `/bot <question>` - AI chat (via DM)
- `/weather` - Weather info
- `/power` - System telemetry
- `/sys` - System info
- `/help` - Help text

### Status Commands

**Check Dual Mode Status**:
```
/sys
```
Shows which networks are active and their statistics.

## Testing

### Step-by-Step Testing

1. **Verify Configuration**:
   ```bash
   grep -E "DUAL_NETWORK_MODE|MESHTASTIC_ENABLED|MESHCORE_ENABLED" config.py
   ```

2. **Check Hardware**:
   ```bash
   ls -la /dev/ttyACM* /dev/ttyUSB*
   ```
   You should see both serial devices.

3. **Start the Bot**:
   ```bash
   python main_script.py
   ```

4. **Check Startup Logs**:
   Look for these messages:
   ```
   🔄 MODE DUAL: Connexion simultanée Meshtastic + MeshCore
   ✅ Meshtastic interface set: ...
   ✅ MeshCore interface set: ...
   ✅ Mode dual initialisé avec succès
   ```

5. **Test Message Reception**:
   - Send a message via Meshtastic → Should receive and reply
   - Send a message via MeshCore → Should receive and reply
   - Verify replies go to the correct network

6. **Test Commands**:
   - Try `/help` from both networks
   - Try `/bot question` from both networks
   - Try `/nodes` from Meshtastic (should work)
   - Try `/nodes` from MeshCore (should indicate not available)

## Troubleshooting

### Bot Only Connects to Meshtastic

**Problem**: MeshCore interface fails to initialize

**Solutions**:
- Check `/dev/ttyUSB0` exists: `ls -la /dev/ttyUSB*`
- Check permissions: `sudo chmod 666 /dev/ttyUSB0`
- Verify MeshCore library: `pip list | grep meshcore`
- Check logs for error messages during MeshCore connection

### Replies Go to Wrong Network

**Problem**: Bot sends replies to wrong network

**Solutions**:
- Ensure `DUAL_NETWORK_MODE = True`
- Check logs for "Network route" messages
- Verify `set_sender_network()` is being called
- Test with debug mode: `DEBUG_MODE = True`

### Performance Issues

**Problem**: Bot is slow or unresponsive

**Solutions**:
- Check CPU usage: `top`
- Monitor packet rates from both networks
- Consider disabling one network temporarily
- Increase hardware resources (RAM, CPU)

### Frequency Interference

**Problem**: Both radios interfere with each other

**Solutions**:
- Ensure networks use different frequencies
- Increase physical separation between radios
- Use external antennas with better isolation
- Configure appropriate power levels

## Comparison: Single vs Dual Mode

| Feature | Single Mode | Dual Mode |
|---------|------------|-----------|
| Networks Connected | 1 | 2 |
| Physical Radios Required | 1 | 2 |
| Configuration Complexity | Simple | Moderate |
| Network Coverage | One network | Two networks |
| Reply Routing | Automatic | Network-aware |
| Statistics | Single source | Aggregated |
| CPU Usage | Lower | Higher |
| Use Case | Standard setup | Advanced bridging |

## Migration Guide

### From Single to Dual Mode

1. **Backup Configuration**:
   ```bash
   cp config.py config.py.backup
   ```

2. **Add Second Radio**:
   - Connect MeshCore radio
   - Note the device path (e.g., `/dev/ttyUSB0`)

3. **Update Configuration**:
   ```python
   DUAL_NETWORK_MODE = True
   MESHCORE_ENABLED = True
   MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
   ```

4. **Restart Bot**:
   ```bash
   sudo systemctl restart meshbot
   ```

5. **Verify Operation**:
   ```bash
   journalctl -u meshbot -f
   ```

### From Dual to Single Mode

1. **Update Configuration**:
   ```python
   DUAL_NETWORK_MODE = False
   # Keep only one network enabled
   ```

2. **Restart Bot**:
   ```bash
   sudo systemctl restart meshbot
   ```

## Performance Considerations

### Resource Usage

**Expected Overhead**:
- CPU: +10-20% compared to single mode
- Memory: +50-100MB for second interface
- Network: Proportional to packet rates on both networks

**Optimization Tips**:
- Use efficient hardware (Raspberry Pi 4/5 recommended)
- Monitor packet rates: `journalctl -u meshbot | grep "Packet #"`
- Adjust logging levels for production

### Scaling

**Network Load**:
- Each network adds to total packet processing
- Bot handles ~100 packets/minute comfortably
- Higher loads may require optimization

**Best Practices**:
- Monitor CPU and memory usage
- Set appropriate rate limits
- Use throttling to prevent overload

## Security Considerations

### Encryption

- Meshtastic: Uses channel PSK encryption
- MeshCore: Uses contact-based encryption
- Both are independent and secure

### Authentication

- Messages are authenticated per network
- No cross-network authentication needed
- Each network has its own user whitelist

### Isolation

- Networks are logically isolated
- No automatic bridging of messages
- Bot acts as separate participant on each

## FAQ

### Can I use Meshtastic TCP + MeshCore Serial?

**Yes!** You can mix connection types:
```python
DUAL_NETWORK_MODE = True
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'tcp'  # Remote Meshtastic node
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # Local MeshCore radio
```

### Can I bridge messages between networks?

**Not automatically.** The bot receives from both but doesn't forward messages between them. This is by design for privacy and network isolation.

To manually bridge, you could:
- Monitor messages from one network
- Manually forward via `/echo` to the other
- Implement custom bridging logic

### What happens if one network fails?

The bot continues operating on the remaining network:
- Meshtastic fails → MeshCore continues
- MeshCore fails → Meshtastic continues
- Automatic fallback to single-network mode

### Can I use three or more networks?

**Not currently.** The implementation supports exactly two networks (Meshtastic + MeshCore). Supporting more would require additional development.

### Which network gets priority?

**Meshtastic** is the primary interface:
- Full feature set
- Preferred for broadcasts
- Used when network source unknown

**MeshCore** is secondary:
- Companion mode features only
- Receives DMs
- Replies routed correctly

## References

- **Single Mode Documentation**: `DUAL_INTERFACE_FAQ.md`
- **MeshCore Integration**: `MESHCORE_COMPANION.md`
- **Configuration Guide**: `config.py.sample`
- **Architecture Details**: `dual_interface_manager.py`

## Support

For issues or questions:
1. Check logs: `journalctl -u meshbot -f`
2. Review configuration: `config.py`
3. Test in debug mode: `DEBUG_MODE = True`
4. Open GitHub issue with logs and config (sanitized)
