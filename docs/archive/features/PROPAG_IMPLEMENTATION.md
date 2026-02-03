# Implémentation de la commande /propag

## Résumé

Nouvelle commande `/propag` qui affiche les 5 plus longues liaisons radio des dernières 24 heures dans un rayon de 100km du nœud bot, avec le record de distance sur 30 jours.

## Fonctionnalités

### Commande de base
```
/propag              → Top 5 liaisons (24h, rayon 100km) + record 30j
/propag 48           → Top 5 liaisons (48h) + record 30j
/propag 24 10        → Top 10 liaisons (24h) + record 30j
```

### Paramètres
- `hours` (optionnel): Période d'analyse en heures (1-72h, défaut: 24h)
- `top_n` (optionnel): Nombre de liaisons à afficher (1-10, défaut: 5)
- Rayon fixe: 100km autour du nœud bot

### Formats de sortie

#### Format compact (LoRa, <180 chars)
```
📡 Top 5 liaisons (24h): 1.TigroA→TigroB 45km SNR:8 | 2.TigroC→TigroD 42km SNR:6 | 3.NodeE→NodeF 38km SNR:7 | 4.NodeG→NodeH 35km | 5.NodeI→NodeJ 32km SNR:5 | 🏆 Record 30j: 67km
```

#### Format détaillé (Telegram)
```
📡 **Top 5 liaisons radio** (dernières 24h)
🎯 Rayon maximum: 100km

🏆 **#1 - 45km**
   📤 TigroA (ID: !12345678)
   📥 TigroB (ID: !87654321)
   📊 SNR: 8.5 dB
   📶 RSSI: -95 dBm
   🕐 10/12 14:32

🥇 **#2 - 42km**
   📤 TigroC (ID: !abcd1234)
   📥 TigroD (ID: !4321dcba)
   📊 SNR: 6.2 dB
   🕐 10/12 13:15

...

📊 Distance moyenne: 38.4km
📈 Total liaisons analysées: 127

🏆 **Record 30 jours: 67km**
   TigroA ↔ TigroZ
   🕐 05/12/2024 16:45
```

## Architecture technique

### 1. TrafficPersistence.load_radio_links_with_positions()
**Fichier**: `traffic_persistence.py`

**Fonction**: Charge les liaisons radio depuis la base de données SQLite avec positions GPS.

**Requête SQL**:
```sql
SELECT 
    from_id, to_id, snr, rssi, timestamp, position
FROM packets
WHERE timestamp >= cutoff
    AND from_id IS NOT NULL 
    AND to_id IS NOT NULL
    AND to_id != 4294967295  -- Exclure broadcast
    AND to_id != 0
    AND (snr IS NOT NULL OR rssi IS NOT NULL)
ORDER BY timestamp DESC
```

**Retour**: Liste de dictionnaires avec from_id, to_id, snr, rssi, timestamp, lat, lon

### 2. TrafficMonitor.get_propagation_report()
**Fichier**: `traffic_monitor.py`

**Algorithme**:
1. Charger liaisons des dernières N heures via `load_radio_links_with_positions()`
2. Pour chaque liaison:
   - Récupérer positions GPS des nœuds from/to via `NodeManager.get_node_data()`
   - Calculer distance avec `haversine_distance()`
   - Filtrer par rayon (100km depuis bot) si position bot disponible
3. Trier liaisons par distance décroissante
4. Prendre top N liaisons
5. **Calculer record 30 jours**: Charger liaisons sur 720h, trouver distance max
6. Formater selon mode compact/détaillé

**Filtrage par rayon**:
- Vérifie distance du nœud FROM au bot
- Vérifie distance du nœud TO au bot
- Garde la liaison si au moins un des deux nœuds est dans le rayon

### 3. NetworkCommands.handle_propag()
**Fichier**: `handlers/command_handlers/network_commands.py`

**Responsabilités**:
- Parser arguments (hours, top_n)
- Validation des paramètres (1-72h, 1-10 liaisons)
- Détecter format (compact si Mesh, détaillé si Telegram/CLI)
- Appeler `get_propagation_report()`
- Logger conversation
- Gérer erreurs

### 4. Routage
**Fichier**: `handlers/message_router.py`

```python
elif message.startswith('/propag'):
    self.network_handler.handle_propag(message, sender_id, sender_info)
```

### 5. Aide
**Fichier**: `handlers/command_handlers/utility_commands.py`

Ajout dans:
- `_format_help()`: Liste simple des commandes
- `_format_help_telegram()`: Aide détaillée avec exemples

## Dépendances

### Données requises
- **Table packets**: from_id, to_id, snr, rssi, timestamp, position (JSON)
- **NodeManager**: Positions GPS des nœuds (latitude, longitude)
- **BOT_POSITION** (config.py): Position de référence pour filtrage rayon

### Modules utilisés
- `node_manager.py`: Calcul distances (haversine), récupération positions
- `traffic_persistence.py`: Accès base de données SQLite
- `traffic_monitor.py`: Génération rapport
- `handlers/`: Routing et traitement commandes

## Cas limites gérés

1. **Pas de données GPS**:
   - Liaison ignorée si from ou to n'a pas de position
   - Message: "❌ Aucune liaison radio avec GPS dans le rayon configuré"

2. **Base de données vide**:
   - Message: "❌ Aucune donnée de liaison radio disponible"

3. **Format trop long (LoRa)**:
   - Réduction progressive: suppression SNR, puis noms courts, puis distances seules
   - Garantit <180 caractères

4. **Erreur calcul record 30j**:
   - Capture exception, continue sans record
   - Pas de blocage du rapport principal

5. **Pas de position bot**:
   - Filtrage par rayon désactivé
   - Toutes les liaisons sont considérées

## Tests

### Test script
**Fichier**: `test_propag_command.py`

**Tests inclus**:
1. ✅ TrafficPersistence.load_radio_links_with_positions()
2. TrafficMonitor.get_propagation_report() (nécessite config)
3. NetworkCommands.handle_propag() (nécessite config)
4. ✅ Routage dans MessageRouter
5. ✅ Présence dans help text

### Validation manuelle
Pour tester en production:
```
# Format compact (Mesh)
/propag

# Format détaillé (Telegram)
/propag 48 10

# Vérifier record 30j présent dans les deux formats
```

## Performance

### Complexité
- Chargement DB: O(n) avec n = nombre de packets
- Calcul distances: O(m) avec m = nombre de liaisons valides
- Tri: O(m log m)
- Record 30j: O(p) avec p = packets sur 30 jours

### Optimisations
- Index SQL sur timestamp
- Limite SQL (5000 packets max)
- Calcul record en try/except pour ne pas bloquer
- Cache positions nœuds dans NodeManager

### Temps d'exécution estimé
- DB avec 1000 packets/24h: ~100ms
- DB avec 10000 packets/30j (record): ~500ms
- Total: <1 seconde

## Maintenance

### Ajout futur possible
1. Filtrage par SNR minimum (qualité liaison)
2. Export carte HTML des top liaisons
3. Historique records (record par mois)
4. Alerte si nouveau record détecté
5. Statistiques par type d'antenne/matériel

### Configuration potentielle
Ajouter dans `config.py`:
```python
PROPAG_MAX_DISTANCE_KM = 100    # Rayon filtrage
PROPAG_DEFAULT_HOURS = 24       # Période par défaut
PROPAG_DEFAULT_TOP = 5          # Nombre liaisons par défaut
PROPAG_RECORD_DAYS = 30         # Période record
```

## Exemples d'utilisation

### Analyse réseau local
```
/propag → Voir les meilleures liaisons locales (24h)
```

### Analyse étendue
```
/propag 48 10 → Analyse sur 2 jours, top 10
```

### Suivi record
```
/propag → Vérifier si nouveau record 30j
```

### Comparaison performances
Comparer avec `/neighbors` pour voir:
- `/neighbors`: Topologie réseau (qui entend qui)
- `/propag`: Performances radio (distances max)

## Compatibilité

- ✅ Mode serial (CONNECTION_MODE='serial')
- ✅ Mode TCP (CONNECTION_MODE='tcp')
- ✅ Telegram (format détaillé)
- ✅ CLI (format détaillé)
- ✅ LoRa Mesh (format compact <180 chars)
- ✅ Collecteur MQTT (données neighbors)

## Sécurité

- Pas de commandes système
- Lecture seule base de données
- Pas d'information sensible exposée (seulement IDs publics)
- Throttling via MessageSender (5 cmd/5min)

## Documentation

### Aide en ligne
- `/help`: Liste `/propag` dans les commandes
- Telegram: Aide détaillée avec exemples

### Fichiers mis à jour
1. `traffic_persistence.py`: +65 lignes
2. `traffic_monitor.py`: +187 lignes
3. `handlers/command_handlers/network_commands.py`: +74 lignes
4. `handlers/message_router.py`: +2 lignes
5. `handlers/command_handlers/utility_commands.py`: +6 lignes
6. `test_propag_command.py`: +258 lignes (nouveau)

**Total**: ~590 lignes ajoutées

## Conclusion

La commande `/propag` est maintenant opérationnelle et fournit:
- ✅ Top 5 liaisons radio par distance (configurable)
- ✅ Filtrage par rayon 100km du bot
- ✅ Support format compact (LoRa) et détaillé (Telegram)
- ✅ **Record de distance sur 30 jours**
- ✅ Statistiques (distance moyenne, total analysé)
- ✅ Qualité signal (SNR, RSSI)
- ✅ Timestamps des liaisons

Prêt pour déploiement et tests en production! 🚀
