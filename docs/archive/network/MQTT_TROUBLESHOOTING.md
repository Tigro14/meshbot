# MQTT Neighbor Collector - Guide de Dépannage

## Problèmes Résolus (serveurperso.com)

### Problème 1: Aucun Message Reçu

**Symptôme:**
```
Messages totaux reçus: 0
Topics écoutés:
```

**Cause:** Topic manquait le wildcard `/#` pour capturer les IDs de gateway.

**Solution:**
Les messages sont publiés comme: `msh/EU_868/2/e/MediumFast/!b29fae64`

Utilisez le pattern avec `/#`:
```python
MQTT_NEIGHBOR_TOPIC_PATTERN = "msh/EU_868/2/e/MediumFast/#"
```

### Problème 2: Erreur de Parsing

**Symptôme:**
```
❌ Erreur parsing ServiceEnvelope: module 'meshtastic.protobuf.mesh_pb2' has no attribute 'ServiceEnvelope'
```

**Cause:** `ServiceEnvelope` est dans `mqtt_pb2`, pas `mesh_pb2`.

**Solution:** Déjà corrigé dans le code - le collecteur utilise maintenant:
```python
from meshtastic.protobuf import mqtt_pb2
envelope = mqtt_pb2.ServiceEnvelope()
```

## Configuration Complète (serveurperso.com)

```python
# config.py
MQTT_NEIGHBOR_ENABLED = True
MQTT_NEIGHBOR_SERVER = "serveurperso.com"
MQTT_NEIGHBOR_PORT = 1883
MQTT_NEIGHBOR_USER = "meshdev"
MQTT_NEIGHBOR_PASSWORD = "votre_mot_de_passe"
MQTT_NEIGHBOR_TOPIC_ROOT = "msh"
MQTT_NEIGHBOR_TOPIC_PATTERN = "msh/EU_868/2/e/MediumFast/#"  # ← /# est CRITIQUE
```

## Procédure de Test

### 1. Tester la Connexion MQTT

```bash
python3 test_mqtt_connection.py
# Entrez le mot de passe MQTT quand demandé
```

**Sortie attendue:**
```
✅ Connecté au serveur MQTT: serveurperso.com:1883
✅ Abonné à: msh/EU_868/2/e/MediumFast/#
✅ Abonnement confirmé par le serveur

📬 Premier message reçu!
   Topic: msh/EU_868/2/e/MediumFast/!b29fae64
   Taille payload: 163 octets

👥 NEIGHBORINFO de !a2e175ac: 8 voisins
   [1] !a2ed97fc - SNR: 8.5 dB
   [2] !7c5b0738 - SNR: 6.2 dB
   ...

🔒 Message chiffré de !435b9ae8
📊 10 messages reçus jusqu'à présent...
```

### 2. Démarrer le Bot

```bash
# Configurer config.py avec les paramètres ci-dessus
sudo systemctl restart meshbot
```

### 3. Vérifier les Logs

```bash
journalctl -u meshbot -f | grep MQTT
```

**Logs attendus:**
```
👥 Connecté au serveur MQTT Meshtastic
   Abonné à: msh/EU_868/2/e/MediumFast/# (topic spécifique)
[MQTT] 👥 NEIGHBORINFO de tigrog2 [12.5km]: 8 voisins
[MQTT] 👥 NEIGHBORINFO de relay-node [45.3km]: 5 voisins
```

**Note:** Les logs `[MQTT]` n'apparaissent que si `DEBUG_MODE=True` dans config.py.

### 4. Tester via Telegram

```
/rx
```

**Sortie attendue:**
```
👥 **MQTT Neighbor Collector**
Statut: Connecté 🟢
Serveur: serveurperso.com:1883

📊 **Statistiques**
• Messages reçus: 42
• Paquets neighbor: 15
• Nœuds découverts: 23
• Dernière MAJ: 15:30:45
```

## Problèmes Courants

### Messages Chiffrés

**Symptôme:**
```
🔒 Message chiffré de !b29fae64
Messages chiffrés (encrypted): 89
Messages NEIGHBORINFO_APP: 0
```

**Explication:** Les messages chiffrés ne peuvent pas être parsés. Le bot ne peut collecter les NEIGHBORINFO que depuis des paquets **non-chiffrés**.

**Solution:** C'est normal. Le collecteur filtre automatiquement les messages chiffrés. Seuls les paquets NEIGHBORINFO non-chiffrés sont utilisés.

### Pas de Logs [MQTT] dans journalctl

**Cause:** `DEBUG_MODE=False` dans config.py

**Solution:**
```python
DEBUG_MODE = True
```

Puis redémarrer le bot:
```bash
sudo systemctl restart meshbot
```

### Distance Filter

Les nœuds >100km ne sont **pas** loggés (filtre automatique).

**Vérification:**
```python
# Dans les logs, vous ne verrez que:
[MQTT] 👥 NEIGHBORINFO de node_proche [12.5km]: 8 voisins
# Pas de:
# [MQTT] 👥 NEIGHBORINFO de node_loin [150km]: ...
```

C'est **volontaire** - le filtre de distance est à 100km.

### Abonnement Confirmé mais Aucun Message

**Causes possibles:**
1. **Permissions ACL MQTT** - L'utilisateur n'a pas accès au topic
2. **Pas de trafic** - Attendez quelques minutes
3. **Topic incorrect** - Vérifiez avec MQTT Explorer

**Diagnostic:**
```bash
# Vérifier avec MQTT Explorer que vous voyez du trafic sur:
# msh/EU_868/2/e/MediumFast/!XXXXXXXX
```

## Structure des Topics MQTT

**Format Meshtastic:**
```
msh/<region>/<channel>/2/e/<gateway_id>
│   │        │           │  │  │
│   │        │           │  │  └─ Node ID du gateway (!b29fae64)
│   │        │           │  └──── "e" = ServiceEnvelope
│   │        │           └─────── "2" = version protobuf
│   │        └─────────────────── Nom du channel (MediumFast)
│   └──────────────────────────── Région (EU_868)
└──────────────────────────────── Racine MQTT
```

**Pattern de subscription:**
- Wildcard complet: `msh/+/+/2/e/+` (tous les régions/channels/gateways)
- Topic spécifique: `msh/EU_868/2/e/MediumFast/#` (tous les gateways de ce channel)

**Important:** Le `/#` final est **obligatoire** pour capturer tous les gateway IDs.

## Dépendances

```bash
pip install paho-mqtt meshtastic
```

**Version minimale:**
- paho-mqtt >= 2.1.0
- meshtastic >= 2.2.0 (avec mqtt_pb2)

## Vérifier l'Installation

```bash
python3 << 'EOF'
from meshtastic.protobuf import mqtt_pb2, mesh_pb2, portnums_pb2
print("✅ Tous les modules protobuf disponibles")
print("✅ mqtt_pb2.ServiceEnvelope:", hasattr(mqtt_pb2, 'ServiceEnvelope'))
print("✅ mesh_pb2.NeighborInfo:", hasattr(mesh_pb2, 'NeighborInfo'))
EOF
```

**Sortie attendue:**
```
✅ Tous les modules protobuf disponibles
✅ mqtt_pb2.ServiceEnvelope: True
✅ mesh_pb2.NeighborInfo: True
```

## Support

Si problème persistant:
1. Vérifier MQTT Explorer voit du trafic sur le topic
2. Tester avec `test_mqtt_connection.py`
3. Vérifier les logs avec `journalctl -u meshbot -f`
4. S'assurer que `DEBUG_MODE=True` pour voir tous les logs

## Résumé Checklist

- [ ] Config MQTT dans config.py
- [ ] Topic pattern avec `/#` à la fin
- [ ] DEBUG_MODE = True
- [ ] Test avec test_mqtt_connection.py
- [ ] Redémarrage du bot
- [ ] Vérification logs journalctl
- [ ] Test /rx sur Telegram
- [ ] Patience (messages peuvent prendre quelques minutes)
