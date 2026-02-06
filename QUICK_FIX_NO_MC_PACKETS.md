# Quick Fix: Pas de Paquets MeshCore [DEBUG][MC]

## Problème
Voir `[DEBUG][MT]` mais PAS `[DEBUG][MC]` malgré traffic local.

## Cause
`MESHCORE_ENABLED=True` MAIS `DUAL_NETWORK_MODE=False`
→ Meshtastic prend priorité, MeshCore ignoré

## Solution Rapide

### Si vous avez 2 radios (Meshtastic + MeshCore):

```python
# config.py
DUAL_NETWORK_MODE = True  # ⭐ CHANGER False → True
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = True
SERIAL_PORT = "/dev/ttyACM0"  # Meshtastic
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore (DIFFÉRENT!)
```

### Si vous avez 1 radio MeshCore seulement:

```python
# config.py
DUAL_NETWORK_MODE = False
MESHTASTIC_ENABLED = False  # ⭐ DÉSACTIVER
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
MESHCORE_RX_LOG_ENABLED = True
```

### Si vous avez 1 radio Meshtastic seulement:

```python
# config.py
DUAL_NETWORK_MODE = False
MESHTASTIC_ENABLED = True
MESHCORE_ENABLED = False  # ⭐ DÉSACTIVER (pas nécessaire)
```

## Vérification

```bash
sudo systemctl restart meshtastic-bot
journalctl -u meshtastic-bot --since "1 minute ago" | grep "ACTIVE NETWORK"
```

**Attendu:**
```
   📡 ACTIVE NETWORKS:
      ✅ Meshtastic (via primary interface)
      ✅ MeshCore (via dual interface)
      → Will see [DEBUG][MT] AND [DEBUG][MC] packets
```

OU

```
   📡 ACTIVE NETWORK:
      ✅ MeshCore ONLY
      → Will see [DEBUG][MC] packets only
```

## Documentation Complète

Voir `NO_MESHCORE_PACKETS_GUIDE.md` pour:
- Explications détaillées
- 3 options de configuration
- FAQ
- Troubleshooting
