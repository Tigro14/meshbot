# TCP Auto-Reboot Feature Documentation

## Overview

The TCP auto-reboot feature automatically attempts to reboot a remote Meshtastic node when the bot fails to establish an initial TCP connection. This prevents manual intervention when the remote node becomes unreachable due to network issues or being stuck.

## Problem Statement

When running the bot in TCP mode (`CONNECTION_MODE='tcp'`), if the remote Meshtastic node is unreachable at startup, the bot would crash with errors like:

```
OSError: [Errno 113] No route to host
```

Without the TCP connection, the bot cannot start, and there was no automated recovery mechanism. Manual intervention was required to:
1. SSH into the remote node's host
2. Manually reboot the node
3. Restart the bot

## Solution

The bot now automatically attempts to reboot the remote node using the Meshtastic CLI:

```bash
meshtastic --host <IP> --reboot
```

This allows the bot to recover from transient network issues or stuck node states without manual intervention.

## Configuration

Add these options to your `config.py`:

```python
# Auto-reboot du nœud distant en cas d'échec de connexion TCP initial
# Si True, le bot tentera automatiquement de rebooter le nœud distant
# via 'meshtastic --host <IP> --reboot' en cas d'erreur de connexion
# (ex: "No route to host", timeout, connexion refusée)
TCP_AUTO_REBOOT_ON_FAILURE = True

# Délai d'attente après reboot avant de retenter la connexion (secondes)
# Le nœud a besoin de temps pour redémarrer complètement
TCP_REBOOT_WAIT_TIME = 45
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `TCP_AUTO_REBOOT_ON_FAILURE` | bool | `True` | Enable/disable automatic reboot on connection failure |
| `TCP_REBOOT_WAIT_TIME` | int | `45` | Seconds to wait after reboot before retrying connection |

## How It Works

### Connection Flow

```
┌──────────────────────────────────────────────────────────────┐
│ Bot Startup - TCP Mode                                       │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │ Attempt TCP Connection       │
            │ to tcp_host:tcp_port         │
            └──────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
             ✅ Success      ❌ OSError
                    │             │
                    │             ▼
                    │   ┌─────────────────────┐
                    │   │ Check errno         │
                    │   │ - 113: No route     │
                    │   │ - 110: Timeout      │
                    │   │ - 111: Refused      │
                    │   │ - 101: Unreachable  │
                    │   └─────────────────────┘
                    │             │
                    │      ┌──────┴───────┐
                    │      │              │
                    │  Network      Non-network
                    │   Error          Error
                    │      │              │
                    │      ▼              ▼
                    │   ┌──────────┐   Return
                    │   │ Auto-    │   False
                    │   │ Reboot?  │
                    │   └──────────┘
                    │      │
                    │   ┌──┴───┐
                    │   │      │
                    │  Yes    No
                    │   │      │
                    │   ▼      ▼
                    │ ┌──────┐ Return
                    │ │Reboot│ False
                    │ │Node  │
                    │ └──────┘
                    │   │
                    │   ▼
                    │ Wait 45s
                    │   │
                    │   ▼
                    │ ┌──────────────┐
                    │ │ Retry        │
                    │ │ Connection   │
                    │ └──────────────┘
                    │   │
                    ├───┘
                    │
                    ▼
         ┌──────────────────────┐
         │ Bot Running          │
         │ Interface Connected  │
         └──────────────────────┘
```

### Error Detection

The auto-reboot feature triggers on these network errors:

| errno | Error Name | Description |
|-------|------------|-------------|
| 113 | `EHOSTUNREACH` | No route to host |
| 110 | `ETIMEDOUT` | Connection timed out |
| 111 | `ECONNREFUSED` | Connection refused |
| 101 | `ENETUNREACH` | Network is unreachable |

Other errors (e.g., invalid hostname, permission denied) do NOT trigger auto-reboot.

### Retry Logic

1. **First Connection Attempt**
   - Try to connect to TCP node
   - If network error detected AND auto-reboot enabled:
     - Execute `meshtastic --host <IP> --reboot`
     - Wait `TCP_REBOOT_WAIT_TIME` seconds (default: 45)
     - Proceed to retry

2. **Second Connection Attempt** (after reboot)
   - Try to connect again
   - If success: Bot continues normally
   - If failure: Bot stops with error (prevents infinite loops)

3. **Maximum Attempts**
   - Only **1 reboot** per bot startup
   - Prevents infinite reboot loops
   - Ensures the bot doesn't hammer the node

## Implementation Details

### `_reboot_remote_node()` Method

Located in `main_bot.py`:

```python
def _reboot_remote_node(self, tcp_host):
    """
    Redémarre le nœud Meshtastic distant via la commande CLI
    
    Args:
        tcp_host: Adresse IP du nœud à redémarrer
    
    Returns:
        bool: True si le reboot a été envoyé avec succès, False sinon
    """
```

**Features:**
- Uses `subprocess.run()` with 30-second timeout
- Executes `python3 -m meshtastic --host <IP> --reboot`
- Captures stdout/stderr for debugging
- Returns True/False for success/failure
- Handles exceptions gracefully

### TCP Connection Initialization

The TCP connection code in `start()` method has been enhanced:

```python
# Before (would crash on error)
self.interface = OptimizedTCPInterface(
    hostname=tcp_host,
    portNumber=tcp_port
)

# After (with auto-reboot)
max_connection_attempts = 2
for attempt in range(max_connection_attempts):
    try:
        self.interface = OptimizedTCPInterface(...)
        break  # Success
    except OSError as e:
        if attempt == 0 and auto_reboot and e.errno in network_errors:
            # Trigger reboot and retry
            self._reboot_remote_node(tcp_host)
            time.sleep(reboot_wait_time)
        else:
            break  # Give up
```

## Usage Examples

### Example 1: Successful Auto-Reboot

```
[INFO] 🌐 Mode TCP: Connexion à 192.168.1.38:4403
[INFO] 🔧 Initialisation OptimizedTCPInterface pour 192.168.1.38:4403
[ERROR] ❌ Erreur connexion TCP (tentative 1/2): [Errno 113] No route to host
[INFO] 🔄 Erreur réseau détectée (errno 113)
[INFO]    → Tentative de redémarrage automatique du nœud...
[INFO] 🔄 Tentative de redémarrage du nœud distant 192.168.1.38...
[INFO]    Commande: python3 -m meshtastic --host 192.168.1.38 --reboot
[INFO] ✅ Commande de redémarrage envoyée au nœud 192.168.1.38
[INFO] ⏳ Attente de 45s pour le redémarrage du nœud...
[INFO] 🔄 Nouvelle tentative de connexion après reboot...
[INFO] 🔧 Initialisation OptimizedTCPInterface pour 192.168.1.38:4403
[INFO] ✅ Interface TCP créée
[INFO] ✅ Connexion TCP stable
```

### Example 2: Auto-Reboot Disabled

```
TCP_AUTO_REBOOT_ON_FAILURE = False
```

```
[INFO] 🌐 Mode TCP: Connexion à 192.168.1.38:4403
[INFO] 🔧 Initialisation OptimizedTCPInterface pour 192.168.1.38:4403
[ERROR] ❌ Erreur connexion TCP (tentative 1/2): [Errno 113] No route to host
[ERROR]    Auto-reboot désactivé (TCP_AUTO_REBOOT_ON_FAILURE=False)
[ERROR] ❌ Impossible de se connecter au nœud TCP
[ERROR]    Le bot ne peut pas démarrer sans connexion Meshtastic
```

### Example 3: Non-Network Error

```
[INFO] 🌐 Mode TCP: Connexion à invalid-hostname:4403
[INFO] 🔧 Initialisation OptimizedTCPInterface pour invalid-hostname:4403
[ERROR] ❌ Erreur inattendue lors de la connexion TCP: [Errno -2] Name or service not known
[ERROR] ❌ Impossible de se connecter au nœud TCP
```

## Requirements

### Python Modules
- `meshtastic>=2.2.0` - Provides the CLI and Python API

### System Dependencies
- None additional (uses Python's built-in `subprocess` module)

### Meshtastic CLI
The `meshtastic` CLI is automatically available when the `meshtastic` Python package is installed:

```bash
# Check availability
python3 -m meshtastic --help

# Manual reboot (what the bot executes)
python3 -m meshtastic --host 192.168.1.38 --reboot
```

## Testing

### Unit Tests

Run `test_auto_reboot.py`:

```bash
python3 test_auto_reboot.py
```

Tests:
- ✅ Meshtastic CLI command construction
- ✅ Network error detection (errno values)
- ✅ Configuration options
- ✅ Retry logic scenarios

### Integration Tests

Run `test_auto_reboot_integration.py`:

```bash
python3 test_auto_reboot_integration.py
```

Tests:
- ✅ Auto-reboot on connection failure
- ✅ Respect disabled flag
- ✅ Handle non-network errors

## Troubleshooting

### Issue: Reboot command fails

**Symptom:**
```
[ERROR] ❌ Module meshtastic non trouvé - impossible de rebooter
```

**Solution:**
Install meshtastic package:
```bash
pip install meshtastic --break-system-packages
```

### Issue: Reboot times out

**Symptom:**
```
[ERROR] ⏱️ Timeout lors du reboot du nœud 192.168.1.38
```

**Causes:**
- Node is completely offline (not just stuck)
- Network connectivity issues
- Firewall blocking connection

**Solution:**
Check network connectivity to the node:
```bash
ping 192.168.1.38
```

### Issue: Bot still fails after reboot

**Symptom:**
```
[ERROR] ❌ Erreur connexion TCP (tentative 2/2): [Errno 113] No route to host
[ERROR] ❌ Impossible de se connecter au nœud TCP
```

**Causes:**
- Node needs more time to boot (>45 seconds)
- Node has a persistent hardware/software issue
- Network routing problem

**Solution:**
1. Increase wait time:
   ```python
   TCP_REBOOT_WAIT_TIME = 90  # 90 seconds
   ```

2. Check node logs for boot issues

3. Verify node is actually accessible:
   ```bash
   meshtastic --host 192.168.1.38 --info
   ```

### Issue: Infinite reboot loops

This **cannot happen** by design. The code explicitly limits to 1 reboot per startup:

```python
max_connection_attempts = 2  # Initial + 1 retry after reboot
```

If you see repeated reboots, it's from systemd restarting the bot service, not the auto-reboot feature.

## Security Considerations

### Network Access

The reboot command requires network access to the Meshtastic node. Ensure:
- Bot has network connectivity to TCP_HOST
- Node's TCP interface is enabled (port 4403)
- No firewall blocking the connection

### Authorization

The `meshtastic --reboot` command does NOT require authentication when using the TCP interface. Anyone with network access to the node can reboot it.

**Mitigation:**
- Use a private network for Meshtastic nodes
- Implement firewall rules to restrict access
- Only enable TCP interface on trusted networks

### Resource Impact

Each reboot attempt:
- Takes ~30 seconds to execute (timeout)
- Waits 45 seconds for node to restart
- Total: ~75 seconds added to bot startup on first failure

This is acceptable for automated recovery but should be considered for monitoring/alerting systems.

## Best Practices

### 1. Enable for Production

```python
TCP_AUTO_REBOOT_ON_FAILURE = True  # Recommended for production
```

This allows the bot to recover from transient issues automatically.

### 2. Adjust Wait Time for Your Node

Different nodes take different times to boot:

```python
# Fast node (ESP32-S3)
TCP_REBOOT_WAIT_TIME = 30

# Standard node (ESP32)
TCP_REBOOT_WAIT_TIME = 45  # Default

# Slow node or with many modules
TCP_REBOOT_WAIT_TIME = 60
```

### 3. Monitor Reboot Attempts

Check logs for auto-reboot events:

```bash
journalctl -u meshbot | grep "redémarrage automatique"
```

Frequent reboots indicate an underlying issue that needs investigation.

### 4. Disable for Development

When developing/debugging, you may want immediate failures:

```python
TCP_AUTO_REBOOT_ON_FAILURE = False  # Faster feedback during dev
```

### 5. Combine with Systemd Restart

For maximum reliability, combine auto-reboot with systemd auto-restart:

```ini
[Service]
Restart=on-failure
RestartSec=30
```

This provides two levels of recovery:
1. Auto-reboot (fixes node issues)
2. Service restart (fixes bot issues)

## Future Enhancements

Potential improvements for future versions:

1. **Configurable Max Attempts**
   ```python
   TCP_AUTO_REBOOT_MAX_ATTEMPTS = 1  # Allow more retries
   ```

2. **Exponential Backoff**
   - First retry: 45s
   - Second retry: 90s
   - Third retry: 180s

3. **Health Check Before Reboot**
   - Try ping first
   - Only reboot if ping succeeds but TCP fails

4. **Alert on Reboot**
   - Send Telegram notification when auto-reboot triggered
   - Track reboot statistics

5. **Alternative Recovery Methods**
   - Try serial connection as fallback
   - Use ESPHome API to reboot node

## Related Documentation

- [TCP Architecture](TCP_ARCHITECTURE.md) - Understanding TCP connections
- [Network Resilience](NETWORK_RESILIENCE.md) - Connection recovery strategies
- [Configuration Guide](README.md) - General bot configuration

## Changelog

### Version 1.0 (2024-12-04)
- Initial implementation of auto-reboot feature
- Support for errno 113, 110, 111, 101
- Configurable enable/disable flag
- Configurable wait time
- Comprehensive test suite
- Documentation

---

**Author:** GitHub Copilot  
**Date:** 2024-12-04  
**Issue:** Automatic reboot on TCP connection failure (#issue_number)
