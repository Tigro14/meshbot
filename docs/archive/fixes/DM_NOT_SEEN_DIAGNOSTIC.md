# DM Not Seen/Responded To - Diagnostic Guide

## Problem
User reports DMs not being seen or responded to on Meshtastic side.

## Solution
Added ultra-verbose packet structure diagnostics.

## Expected Output

### Successful DM:
```
[PACKET-STRUCTURE] Packet exists
[PACKET-STRUCTURE] Keys: ['from', 'to', 'id', 'decoded']
[PACKET-STRUCTURE] Decoded exists
[PACKET-STRUCTURE] Decoded keys: ['portnum', 'payload']
portnum: TEXT_MESSAGE_APP
MESSAGE BRUT: '/help'
```

### Missing Decoded:
```
NO DECODED FIELD!
This is likely why packet not being processed
```

## Deployment
```bash
cd /home/dietpi/bot
git pull
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot -f | grep "PACKET-STRUCTURE"
```

Then send DM and share logs.
