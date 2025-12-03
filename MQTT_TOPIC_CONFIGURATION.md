# MQTT Topic Configuration Guide

## Problem: Wildcard Subscriptions Not Working

Some MQTT servers (like serveurperso.com) don't support wildcard subscriptions (`msh/+/+/2/e/+`), causing the MQTT neighbor collector to receive no messages.

## Solution: Specific Topic Configuration

The bot now supports configuring a specific MQTT topic pattern instead of using wildcards.

## Configuration

### Option 1: Specific Topic (for serveurperso.com)

Edit `config.py` and add:

```python
MQTT_NEIGHBOR_TOPIC_PATTERN = "msh/EU_868/2/e/MediumFast"
```

### Option 2: Wildcard Pattern (standard MQTT servers)

This is the default if not configured:

```python
# No need to add this - it's the default
MQTT_NEIGHBOR_TOPIC_PATTERN = "msh/+/+/2/e/+"
```

### Option 3: Omit Configuration (uses wildcard default)

If you don't add `MQTT_NEIGHBOR_TOPIC_PATTERN` to your config, the collector will automatically use the wildcard pattern `msh/+/+/2/e/+`.

## Finding Your Topic

### Using MQTT Explorer

1. Connect to your MQTT server with MQTT Explorer
2. Navigate the topic tree: `msh` → `EU_868` → `2` → `e` → `MediumFast` (or similar)
3. Look for topics with binary payloads (ServiceEnvelope protobuf)
4. Copy the full topic path (e.g., `msh/EU_868/2/e/MediumFast`)

### Using test_mqtt_connection.py

The test script is pre-configured with the serveurperso.com topic:

```bash
python3 test_mqtt_connection.py
# Enter MQTT password when prompted
```

If you see messages arriving, the topic is correct!

## Topic Format Explanation

### ServiceEnvelope Topic Structure

```
msh/<region>/<channel>/2/e/<gateway>
```

**Components:**
- `msh` - Root topic (configurable via MQTT_NEIGHBOR_TOPIC_ROOT)
- `<region>` - Frequency region (e.g., EU_868, US_915)
- `<channel>` - Channel name (e.g., MediumFast, LongFast, VeryLongSlow)
- `2` - Envelope version
- `e` - Envelope type (ServiceEnvelope)
- `<gateway>` - Gateway node ID

### Examples

**European region:**
```
msh/EU_868/2/e/MediumFast
```

**US region:**
```
msh/US_915/2/e/LongFast
```

**Multiple gateways (wildcard):**
```
msh/EU_868/2/e/+
```

## Testing Your Configuration

### 1. Test MQTT Connection

```bash
cd /home/dietpi/bot
python3 test_mqtt_connection.py
```

**Expected output if working:**
```
✅ Connecté au serveur MQTT: serveurperso.com:1883
✅ Abonné à: msh/EU_868/2/e/MediumFast
   (Topic spécifique - le serveur ne supporte pas les wildcards)
✅ Abonnement confirmé par le serveur (QoS: [0])

📬 Premier message reçu!
   Topic: msh/EU_868/MediumFast/2/e/!b29fae64
   Taille payload: 156 octets
```

### 2. Check Bot Logs

After configuring and restarting the bot:

```bash
journalctl -u meshbot -f | grep MQTT
```

**Look for:**
```
👥 Connecté au serveur MQTT Meshtastic
   Abonné à: msh/EU_868/2/e/MediumFast (topic spécifique)
```

### 3. Verify Data Collection

Use the `/rx` Telegram command:

```
/rx
```

**Should show:**
```
👥 MQTT Neighbor Collector
Statut: Connecté 🟢
Serveur: serveurperso.com:1883

📊 Statistiques
• Messages reçus: 42
• Paquets neighbor: 38
• Nœuds découverts: 15
```

## Troubleshooting

### No Messages Received

**Symptom:**
```
Messages totaux reçus: 0
```

**Possible causes:**
1. **Wrong topic pattern** - Check MQTT Explorer for the exact topic
2. **MQTT credentials** - Verify username/password in config.py
3. **Server ACL** - The meshdev user might not have read access to the topic
4. **Network firewall** - Port 1883 blocked

**Fix:**
- Verify topic in MQTT Explorer matches your config exactly
- Test with `test_mqtt_connection.py` first
- Check MQTT server logs for permission errors

### Messages Received But No Debug Logs

**Symptom:**
- Test script shows messages
- Bot logs show connection
- But no `[MQTT] 👥 NEIGHBORINFO` debug logs

**Possible causes:**
1. **DEBUG_MODE disabled** - Set `DEBUG_MODE = True` in config.py
2. **No NEIGHBORINFO packets** - Messages are other types (TEXT_MESSAGE_APP, etc.)
3. **All nodes encrypted** - Encrypted NEIGHBORINFO can't be parsed
4. **Distance filter** - All nodes >100km from bot position

**Fix:**
- Enable `DEBUG_MODE = True`
- Run test script to see which message types are arriving
- Check if nodes have GPS coordinates

### Encrypted Messages

**Symptom:**
```
🔒 Message chiffré de !b29fae64
```

**Explanation:**
Encrypted messages cannot be parsed for NEIGHBORINFO data. The bot can only collect neighbor information from **unencrypted** packets.

**Fix:**
- If most messages are encrypted, the MQTT collector won't be very useful
- Consider using direct radio collection instead (`/neighbors` command)
- Contact network admin about public channel settings

## Advanced: Multiple Topics

Future support for multiple topics (comma-separated):

```python
MQTT_NEIGHBOR_TOPIC_PATTERN = "msh/EU_868/2/e/MediumFast,msh/EU_868/2/e/LongFast"
```

Currently not implemented - use single topic only.

## Summary

**For serveurperso.com:**
```python
# config.py
MQTT_NEIGHBOR_ENABLED = True
MQTT_NEIGHBOR_SERVER = "serveurperso.com"
MQTT_NEIGHBOR_PORT = 1883
MQTT_NEIGHBOR_USER = "meshdev"
MQTT_NEIGHBOR_PASSWORD = "your_password_here"
MQTT_NEIGHBOR_TOPIC_ROOT = "msh"
MQTT_NEIGHBOR_TOPIC_PATTERN = "msh/EU_868/2/e/MediumFast"  # ← ADD THIS
```

**Test:**
```bash
python3 test_mqtt_connection.py
# Should now receive messages!
```

**Restart bot:**
```bash
sudo systemctl restart meshbot
```

**Verify:**
```bash
journalctl -u meshbot -f | grep MQTT
```
