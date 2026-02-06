# Guide: Pas de Paquets MeshCore Malgré Configuration

## Problème Reporté

**Symptômes:**
- Voir traffic Meshtastic: `[DEBUG][MT]` ✅
- PAS de paquets MeshCore: `[DEBUG][MC]` ❌
- Logs montrent `dual_mode = True` mais `interface type = SerialInterface`

## Diagnostic Rapide

Vérifier les logs de démarrage pour cette section:
```
================================================================================
🔔 SUBSCRIPTION SETUP - CRITICAL FOR PACKET RECEPTION
================================================================================
   meshtastic_enabled = True
   meshcore_enabled = True
   dual_mode (config) = ?????
   dual_mode (active) = ?????
   interface type = SerialInterface
   📡 ACTIVE NETWORK:
      ✅ Meshtastic ONLY (MeshCore ignored)
      ⚠️  Both enabled but DUAL_NETWORK_MODE=False
      → Will see [DEBUG][MT] packets only
      → To enable MeshCore: Set DUAL_NETWORK_MODE=True
================================================================================
```

## Cause Racine

Quand `MESHTASTIC_ENABLED=True` ET `MESHCORE_ENABLED=True` mais `DUAL_NETWORK_MODE=False`:
- Le bot **priorise Meshtastic** (capacités complètes)
- MeshCore est **ignoré silencieusement**
- Seuls les paquets `[DEBUG][MT]` apparaissent

**Code source** (`main_bot.py` lignes 1875-1878):
```python
elif meshtastic_enabled and meshcore_enabled and not dual_mode:
    # Both enabled but dual mode NOT enabled - warn user and prioritize Meshtastic
    info_print("⚠️ AVERTISSEMENT: MESHTASTIC_ENABLED et MESHCORE_ENABLED tous deux activés")
    # Continue to Meshtastic connection (next if blocks)
```

## Solutions

### Option A: Mode Dual (2 Radios) ⭐ RECOMMANDÉ SI MATÉRIEL DISPONIBLE

**Quand utiliser:**
- Vous avez DEUX radios physiques
- Une radio Meshtastic (/dev/ttyACM0)
- Une radio MeshCore (/dev/ttyUSB0)
- Vous voulez voir les DEUX réseaux simultanément

**Configuration:**
```python
# config.py
DUAL_NETWORK_MODE = True  # ⭐ ACTIVER DUAL MODE

MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"  # Radio Meshtastic

MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # Radio MeshCore (DIFFÉRENT!)
MESHCORE_RX_LOG_ENABLED = True  # Pour voir les paquets RF
```

**Résultat:**
- ✅ Paquets Meshtastic: `[DEBUG][MT]`
- ✅ Paquets MeshCore: `[DEBUG][MC]`
- ✅ Statistiques agrégées
- ✅ Commandes complètes sur les deux réseaux

**Vérification:**
```bash
ls -la /dev/ttyACM* /dev/ttyUSB*
# Doit afficher au moins 2 ports série
```

---

### Option B: MeshCore Uniquement

**Quand utiliser:**
- Vous avez UNE radio MeshCore seulement
- Pas de radio Meshtastic disponible
- Besoin DM uniquement (pas de broadcasts)

**Configuration:**
```python
# config.py
DUAL_NETWORK_MODE = False

MESHTASTIC_ENABLED = False  # ⭐ DÉSACTIVER Meshtastic
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
MESHCORE_RX_LOG_ENABLED = True  # ⭐ IMPORTANT pour voir les paquets
```

**Résultat:**
- ❌ Pas de paquets Meshtastic
- ✅ Paquets MeshCore: `[DEBUG][MC]`
- ⚠️ Fonctionnalités limitées (DM uniquement, pas de topology)

---

### Option C: Meshtastic Uniquement (Configuration Actuelle)

**Quand utiliser:**
- Vous avez UNE radio Meshtastic seulement
- Pas besoin de MeshCore
- Configuration recommandée pour la plupart des utilisateurs

**Configuration:**
```python
# config.py
DUAL_NETWORK_MODE = False

MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'serial'  # ou 'tcp'
SERIAL_PORT = "/dev/ttyACM0"

MESHCORE_ENABLED = False  # ⭐ DÉSACTIVER MeshCore
```

**Résultat:**
- ✅ Paquets Meshtastic: `[DEBUG][MT]`
- ❌ Pas de paquets MeshCore (pas nécessaire)
- ✅ Fonctionnalités complètes Meshtastic

---

## Vérification Configuration Actuelle

```bash
cd /home/dietpi/bot
grep -E "DUAL_NETWORK_MODE|MESHTASTIC_ENABLED|MESHCORE_ENABLED" config.py
```

**Attendu:**
```
DUAL_NETWORK_MODE = False  # ou True
MESHTASTIC_ENABLED = True  # ou False
MESHCORE_ENABLED = True    # ou False
```

## Après Modification Configuration

```bash
# Redémarrer le bot
sudo systemctl restart meshtastic-bot

# Vérifier les logs de démarrage (CRITIQUE!)
journalctl -u meshtastic-bot --since "1 minute ago" | grep -A 15 "SUBSCRIPTION SETUP"
```

**Ce que vous devriez voir:**

**Si dual_mode activé:**
```
   dual_mode (active) = True
   📡 ACTIVE NETWORKS:
      ✅ Meshtastic (via primary interface)
      ✅ MeshCore (via dual interface)
      → Will see [DEBUG][MT] AND [DEBUG][MC] packets
```

**Si MeshCore uniquement:**
```
   dual_mode (active) = False
   📡 ACTIVE NETWORK:
      ✅ MeshCore ONLY
      → Will see [DEBUG][MC] packets only
```

**Si Meshtastic uniquement:**
```
   dual_mode (active) = False
   📡 ACTIVE NETWORK:
      ✅ Meshtastic ONLY
      → Will see [DEBUG][MT] packets only
```

## Comprendre les Logs

### Logs avec Dual Mode Actif
```
[DEBUG][MT] 📦 POSITION_APP de Node1...     ← Paquet Meshtastic
[DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu...   ← Paquet MeshCore
[DEBUG][MT] 🌐 LOCAL TELEMETRY...           ← Paquet Meshtastic
[DEBUG][MC] 📦 [RX_LOG] DM | From:...       ← Paquet MeshCore
```

### Logs avec Meshtastic Uniquement (Actuel)
```
[DEBUG][MT] 📦 POSITION_APP de Node1...     ← Paquet Meshtastic
[DEBUG][MT] 🌐 LOCAL TELEMETRY...           ← Paquet Meshtastic
(Pas de [DEBUG][MC] - Normal si MESHCORE désactivé)
```

## Questions Fréquentes

### Q: Pourquoi dual_mode=True dans les logs mais pas de [MC]?

**R:** Le log montre `dual_mode (config)` du fichier config.py, PAS l'état réel.
L'état réel est `dual_mode (active)`. S'il est False, MeshCore n'est pas actif.

### Q: J'ai une seule radio, quel mode choisir?

**R:** Si c'est une radio Meshtastic → Option C (Meshtastic uniquement)
Si c'est une radio MeshCore → Option B (MeshCore uniquement)

### Q: Comment avoir les deux simultanément?

**R:** Besoin de **deux radios physiques** et `DUAL_NETWORK_MODE=True`

### Q: MeshCore est-il meilleur que Meshtastic?

**R:** Non! Meshtastic fait **tout** ce que MeshCore fait, et beaucoup plus:
- ✅ Broadcasts + DMs (vs MeshCore: DMs uniquement)
- ✅ Topology complète (vs MeshCore: limitée)
- ✅ Plus de types de messages
- ✅ Meilleure intégration

**Recommandation:** Si vous avez une radio Meshtastic, utilisez-la!

## Résumé

| Matériel | Configuration Recommandée | Résultat |
|----------|---------------------------|----------|
| 1 radio Meshtastic | Option C (Meshtastic only) | `[DEBUG][MT]` |
| 1 radio MeshCore | Option B (MeshCore only) | `[DEBUG][MC]` |
| 2 radios (Meshtastic + MeshCore) | Option A (Dual mode) | `[DEBUG][MT]` + `[DEBUG][MC]` |

## Déploiement

Après avoir modifié `config.py`:

```bash
cd /home/dietpi/bot
git checkout copilot/update-sqlite-data-cleanup
git pull
sudo systemctl restart meshtastic-bot

# VÉRIFIER les logs de démarrage (CRITIQUE!)
journalctl -u meshtastic-bot --since "1 minute ago" | grep -A 20 "SUBSCRIPTION SETUP"
```

Les nouveaux logs montreront clairement:
- `dual_mode (config)` vs `dual_mode (active)` - État réel
- `📡 ACTIVE NETWORKS:` - Quels réseaux sont actifs
- `→ Will see [DEBUG][MT] AND/OR [DEBUG][MC]` - Ce à quoi s'attendre

---

**Besoin d'aide?** Copiez la section "SUBSCRIPTION SETUP" des logs et partagez-la.
