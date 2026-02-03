# Analyse MQTT - Confirmation de Lecture Exclusive

## Résumé Exécutif

✅ **CONFIRMATION**: Le code MQTT du projet MeshBot effectue **EXCLUSIVEMENT** de la lecture de messages. Aucune opération de publication (write) n'a été détectée dans le code.

## Modules MQTT Identifiés

Le projet contient deux modules principaux utilisant MQTT:

### 1. `mqtt_neighbor_collector.py` - Collecteur de Voisins Meshtastic

**Objectif**: Collecter les informations de topologie réseau depuis un serveur MQTT Meshtastic

**Opérations MQTT**:
- ✅ `subscribe()` - S'abonne aux topics NEIGHBORINFO_APP
- ✅ `on_message()` - Callback de réception de messages
- ✅ `on_connect()` - Callback de connexion
- ✅ `on_disconnect()` - Callback de déconnexion
- ❌ **Aucune opération `publish()` détectée**

**Topics MQTT**:
- Lecture seule: `msh/<region>/<channel>/2/e/<gateway>` (format protobuf)
- Pattern wildcard: `msh/+/+/2/e/+` pour capturer tous les messages

**Serveur par défaut**: `mqtt.meshtastic.liamcottle.net:1883`

### 2. `blitz_monitor.py` - Détection d'Éclairs Blitzortung

**Objectif**: Surveiller les éclairs en temps réel depuis le serveur public Blitzortung.org

**Opérations MQTT**:
- ✅ `subscribe()` - S'abonne aux topics geohash d'éclairs
- ✅ `on_message()` - Callback de réception de messages
- ✅ `on_connect()` - Callback de connexion
- ✅ `on_disconnect()` - Callback de déconnexion
- ❌ **Aucune opération `publish()` détectée**

**Topics MQTT**:
- Lecture seule: `blitzortung/1.1/<geohash>` (format JSON)
- Abonnement à 9 geohashes (centre + 8 voisins) pour couvrir un rayon de 50km

**Serveur**: `blitzortung.ha.sed.pl:1883` (serveur public)

## Vérification Technique

### Recherche d'Opérations Publish

```bash
# Recherche dans tout le code MQTT
grep -r "\.publish\|client\.publish" /home/runner/work/meshbot/meshbot --include="*.py" | grep -i mqtt
# Résultat: Aucune correspondance trouvée ✅
```

### Liste des Opérations MQTT Utilisées

#### mqtt_neighbor_collector.py (lignes identifiées)
```python
Ligne 164:  client.subscribe(topic_pattern)          # LECTURE
Ligne 717:  self.mqtt_client.on_connect = ...        # Configuration
Ligne 718:  self.mqtt_client.on_disconnect = ...     # Configuration  
Ligne 719:  self.mqtt_client.on_message = ...        # LECTURE (callback)
Ligne 722:  self.mqtt_client.reconnect_delay_set()   # Configuration
Ligne 729:  self.mqtt_client.connect_async()         # Connexion
Ligne 795:  self.mqtt_client.reconnect()             # Reconnexion
Ligne 803:  self.mqtt_client.disconnect()            # Déconnexion
```

#### blitz_monitor.py (lignes identifiées)
```python
Ligne 240:  client.subscribe(topic)                  # LECTURE
Ligne 323:  self.mqtt_client.on_connect = ...        # Configuration
Ligne 324:  self.mqtt_client.on_disconnect = ...     # Configuration
Ligne 325:  self.mqtt_client.on_message = ...        # LECTURE (callback)
Ligne 328:  self.mqtt_client.reconnect_delay_set()   # Configuration
Ligne 332:  self.mqtt_client.connect_async()         # Connexion
Ligne 397:  self.mqtt_client.reconnect()             # Reconnexion
Ligne 405:  self.mqtt_client.disconnect()            # Déconnexion
```

**Conclusion**: Seules des opérations de **lecture** (subscribe, on_message) et de **gestion de connexion** sont présentes.

## Architecture de Lecture

### Flux de Données MQTT

```
┌─────────────────────────────────────────────────────┐
│           Serveurs MQTT Externes                    │
├─────────────────────────────────────────────────────┤
│  1. mqtt.meshtastic.liamcottle.net                 │
│     └─> NEIGHBORINFO_APP (topologie réseau)        │
│                                                      │
│  2. blitzortung.ha.sed.pl                          │
│     └─> Lightning strikes (éclairs en temps réel)  │
└───────────────────┬─────────────────────────────────┘
                    │
                    │ MQTT Subscribe (lecture seule)
                    ▼
┌─────────────────────────────────────────────────────┐
│              MeshBot (Raspberry Pi 5)               │
├─────────────────────────────────────────────────────┤
│  • mqtt_neighbor_collector.py                      │
│    └─> on_message() → save_neighbor_info()         │
│                                                      │
│  • blitz_monitor.py                                │
│    └─> on_message() → process_lightning()          │
│                                                      │
│  ⚠️  AUCUNE PUBLICATION VERS MQTT                  │
└─────────────────────────────────────────────────────┘
                    │
                    │ Stockage local uniquement
                    ▼
┌─────────────────────────────────────────────────────┐
│         Base de données SQLite locale               │
│  • traffic_history.db (neighbors table)            │
│  • Historique éclairs (deque en mémoire)           │
└─────────────────────────────────────────────────────┘
```

### Callbacks de Réception

Les deux modules utilisent le pattern standard MQTT:

```python
def _on_mqtt_message(self, client, userdata, msg):
    """
    Callback appelé à la réception d'un message MQTT
    
    Opérations effectuées:
    1. Parsing du payload (JSON ou Protobuf)
    2. Filtrage des données pertinentes
    3. Stockage en base de données locale
    4. ❌ AUCUNE publication vers MQTT
    """
    # Traitement en lecture seule
    data = json.loads(msg.payload)
    self.process_received_data(data)  # Stockage local uniquement
```

## Configuration

### Variables d'Activation

```python
# config.py - Activation/désactivation des collecteurs MQTT

# Collecteur de voisins Meshtastic
MQTT_NEIGHBOR_ENABLED = True
MQTT_NEIGHBOR_SERVER = "mqtt.meshtastic.liamcottle.net"
MQTT_NEIGHBOR_USER = "uplink"
MQTT_NEIGHBOR_PASSWORD = "..." # Dans config_priv.py

# Détection d'éclairs Blitzortung
BLITZ_ENABLED = True
BLITZ_LATITUDE = 0.0  # Auto-détection depuis GPS
BLITZ_LONGITUDE = 0.0
BLITZ_RADIUS_KM = 50
```

### Politique de Sécurité

Les modules MQTT suivent une politique stricte de **lecture seule**:

1. ✅ **Pas de publication** de données vers les serveurs MQTT
2. ✅ **Pas de modification** de l'état des serveurs distants
3. ✅ **Stockage local uniquement** des données reçues
4. ✅ **Accès en lecture** aux flux publics uniquement

## Cas d'Usage

### 1. Collecteur de Voisins (MQTT Neighbor Collector)

**Problème résolu**: Obtenir une vue complète de la topologie du réseau Meshtastic au-delà de la portée radio directe.

**Méthode**:
- Écoute passive des messages NEIGHBORINFO_APP publiés par d'autres nœuds
- Aucune interaction avec le réseau (pas de questions/réponses)
- Agrégation des données localement

**Commandes utilisateur**:
- `/neighbors [node]` - Afficher les voisins d'un nœud
- `/mqtt [hours]` - Lister les nœuds entendus via MQTT
- `/rx` - Statistiques du collecteur MQTT

### 2. Détecteur d'Éclairs (Blitz Monitor)

**Problème résolu**: Alerter les utilisateurs du réseau Meshtastic en cas d'orage à proximité.

**Méthode**:
- Écoute passive du flux d'éclairs public Blitzortung.org
- Filtrage géographique local (rayon de 50km)
- Génération d'alertes sur le réseau Meshtastic (via interface série/TCP, **pas via MQTT**)

**Commandes utilisateur**:
- `/weather blitz` - Afficher les éclairs récents

**Note importante**: Les alertes générées sont envoyées sur le réseau Meshtastic via l'interface **série/TCP locale**, PAS via MQTT. Le module MQTT est utilisé uniquement pour **recevoir** les données d'éclairs.

## Avantages de l'Architecture Read-Only

### Sécurité
- ✅ Pas de risque de spam sur les serveurs MQTT publics
- ✅ Pas de risque d'injection de fausses données
- ✅ Conformité avec les politiques des serveurs publics

### Performance
- ✅ Bande passante minimale (réception uniquement)
- ✅ Pas de file d'attente d'envoi à gérer
- ✅ Architecture simplifiée (unidirectionnelle)

### Fiabilité
- ✅ Fonctionnement même si authentification limitée
- ✅ Pas de dépendance sur la capacité d'écriture
- ✅ Modes de failover plus simples

## Documentation Associée

Documents confirmant la nature lecture-seule:

1. **MQTT_COMMAND_SUMMARY.md** - Décrit le collecteur de voisins
   - Ligne 15: "Query the neighbors database" (lecture de la DB locale)
   - Aucune mention de publication MQTT

2. **MTMQTT_DEBUG_DOCUMENTATION.md** - Documentation du debug MQTT
   - Focus sur la réception et le parsing de messages
   - Aucune documentation d'opérations publish

3. **MQTT_PROTOBUF_MIGRATION.md** - Migration vers protobuf
   - Documentation du décodage de messages (lecture)
   - Aucune mention d'encodage pour publication

## Tests Effectués

### Recherches Exhaustives

```bash
# 1. Recherche de toute opération publish
grep -r "publish" /home/runner/work/meshbot/meshbot --include="*.py" | grep mqtt
# Résultat: 0 correspondance ✅

# 2. Recherche dans les fichiers MQTT spécifiques
grep "publish" mqtt_neighbor_collector.py
# Résultat: 0 correspondance ✅

grep "publish" blitz_monitor.py
# Résultat: 0 correspondance ✅

# 3. Vérification des imports paho.mqtt
grep -n "import.*mqtt" mqtt_neighbor_collector.py blitz_monitor.py
# Résultat: Import de client uniquement (pas de publisher) ✅
```

### Analyse du Code Source

Inspection manuelle complète de:
- ✅ `mqtt_neighbor_collector.py` (1088 lignes) - 100% lecture seule
- ✅ `blitz_monitor.py` (566 lignes) - 100% lecture seule

## Conclusion

### Confirmation Formelle

**Le code MQTT du projet MeshBot est 100% en lecture seule (read-only).**

Aucune des opérations suivantes n'a été trouvée dans le code:
- ❌ `client.publish()`
- ❌ `client.publish_single()`
- ❌ `client.publish_multiple()`
- ❌ Aucune méthode de publication MQTT

### Opérations MQTT Effectuées

| Opération | Type | Présent |
|-----------|------|---------|
| `subscribe()` | Lecture | ✅ |
| `on_message()` | Lecture | ✅ |
| `publish()` | **Écriture** | ❌ |
| `on_connect()` | Gestion | ✅ |
| `on_disconnect()` | Gestion | ✅ |

### Recommandations

Pour maintenir cette architecture read-only:

1. ✅ **Documenté**: Cette analyse confirme et documente le comportement actuel
2. ✅ **Intentionnel**: L'architecture est cohérente avec l'usage de serveurs publics
3. ✅ **Sûr**: Aucun risque de pollution des flux MQTT publics
4. ⚠️ **À maintenir**: Toute future évolution devrait préserver ce comportement

### Certification

```
┌─────────────────────────────────────────────────────┐
│            CERTIFICATION READ-ONLY                  │
├─────────────────────────────────────────────────────┤
│  Code MQTT analysé: mqtt_neighbor_collector.py     │
│                     blitz_monitor.py                │
│                                                      │
│  Opérations publish détectées: 0                   │
│  Opérations subscribe détectées: 2                 │
│                                                      │
│  Status: ✅ LECTURE EXCLUSIVE CONFIRMÉE            │
│                                                      │
│  Date: 2026-02-03                                  │
│  Analyseur: GitHub Copilot                         │
└─────────────────────────────────────────────────────┘
```

## Annexe: Exemples de Code

### Exemple 1: mqtt_neighbor_collector.py

```python
def _on_mqtt_message(self, client, userdata, msg):
    """
    Callback de réception de message MQTT
    
    ⚠️ LECTURE SEULE: Traite les messages reçus sans publier
    """
    try:
        # Parse le ServiceEnvelope protobuf
        service_envelope = mqtt_pb2.ServiceEnvelope()
        service_envelope.ParseFromString(msg.payload)
        
        # Traitement LOCAL uniquement
        if service_envelope.packet.decoded.portnum == portnums_pb2.NEIGHBORINFO_APP:
            self._process_neighborinfo(...)
            
        # ❌ AUCUN appel à client.publish()
        
    except Exception as e:
        error_print(f"👥 Erreur traitement message MQTT: {e}")
```

### Exemple 2: blitz_monitor.py

```python
def _on_mqtt_message(self, client, userdata, msg):
    """
    Callback de réception de message MQTT
    
    ⚠️ LECTURE SEULE: Enregistre les éclairs localement
    """
    try:
        # Parser le JSON
        data = json.loads(msg.payload.decode('utf-8'))
        
        # Calcul de distance et stockage LOCAL
        distance = self._haversine_distance(...)
        if distance <= self.radius_km:
            self.strikes.append(strike_info)
            
        # ❌ AUCUN appel à client.publish()
        
    except Exception as e:
        error_print(f"⚡ Erreur traitement message: {e}")
```

---

**Document généré le**: 2026-02-03  
**Version**: 1.0  
**Statut**: ✅ Validé
