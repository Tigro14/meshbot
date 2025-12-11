# Documentation: Commande /stats hop

## Vue d'ensemble

La commande `/stats hop` permet d'analyser la portée maximale de chaque nœud du réseau Meshtastic en affichant les 20 premiers nœuds triés par leur valeur `hop_start` (décroissante).

## Utilisation

### Syntaxe

```
/stats hop [hours]
```

### Paramètres

- **hours** (optionnel) : Nombre d'heures d'historique à analyser
  - Par défaut : 24 heures
  - Min : 1 heure
  - Max : 168 heures (7 jours)

### Exemples

```bash
/stats hop          # Analyse sur 24h (défaut)
/stats hop 48       # Analyse sur 48h
/stats hop 1        # Analyse sur la dernière heure
/stats hop 168      # Analyse sur 7 jours
```

## Fonctionnement

### Collecte des données

1. La commande charge tous les paquets de la période spécifiée depuis la base SQLite
2. Pour chaque nœud, elle extrait la valeur `hop_start` de ses paquets
3. Elle calcule le **maximum** de `hop_start` observé pour chaque nœud
4. Les nœuds sont triés par ordre décroissant de leur `hop_start` maximum

### Signification du hop_start

Le champ `hop_start` indique le nombre maximal de sauts (hops) qu'un paquet peut effectuer avant d'être écarté. Un `hop_start` élevé signifie :

- **7** : Portée maximale - Nœud configuré pour une grande diffusion (routeurs, relais principaux)
- **5-6** : Bonne portée - Nœuds mobiles ou relais secondaires
- **3-4** : Portée moyenne - Nœuds standards
- **1-2** : Faible portée - Nœuds intérieurs ou portables

## Formats de sortie

### Format Mesh (LoRa)

Version ultra-compacte (< 180 caractères) pour le réseau LoRa :

```
🔄 Hop(24h) Top10
Node-16f:7
Node-123:7
Node-e5f:6
Node-a1b:6
Node-556:5
Node-112:5
Node-99a:4
Node-111:3
Node-dde:3
Node-555:2
```

**Caractéristiques:**
- Limite à 10 nœuds pour rester compact
- Format `NomCourt:hop_start`
- Noms tronqués à 8 caractères

### Format Telegram

Version détaillée avec métadonnées complètes :

```
🔄 **TOP 20 NŒUDS PAR HOP_START (24h)**
==================================================

12 nœuds actifs, top 20 affichés

1. 🔴 **Node-12345678**
   Hop start max: **7** (5 paquets)

2. 🔴 **Node-16fad3dc**
   Hop start max: **7** (5 paquets)

3. 🟡 **Node-e5f6a7b8**
   Hop start max: **6** (5 paquets)

[...]

**Résumé:**
• Moyenne hop_start (top 20): 4.2
• Max hop_start observé: 7
```

**Caractéristiques:**
- Affiche jusqu'à 20 nœuds
- Icônes indicateurs de portée :
  - 🔴 : hop_start ≥ 7 (très grande portée)
  - 🟡 : hop_start ≥ 5 (grande portée)
  - 🟢 : hop_start ≥ 3 (portée moyenne)
  - ⚪ : hop_start < 3 (faible portée)
- Nombre de paquets analysés par nœud
- Statistiques résumées en fin de rapport

## Cas d'usage

### 1. Identifier les meilleurs relais

Les nœuds avec `hop_start` élevé (7) sont idéaux comme relais car ils propagent les messages sur de grandes distances.

### 2. Optimiser le placement des nœuds

En analysant les valeurs de `hop_start`, vous pouvez :
- Identifier les zones avec faible couverture
- Décider où placer de nouveaux nœuds
- Ajuster la configuration des nœuds existants

### 3. Analyser la topologie du réseau

Comprendre la distribution des valeurs `hop_start` aide à :
- Évaluer la redondance du réseau
- Identifier les points de défaillance uniques
- Optimiser la consommation d'énergie

### 4. Débogage réseau

Comparer le `hop_start` configuré avec la portée réelle observée peut révéler :
- Des problèmes de configuration
- Des obstacles physiques
- Des interférences radio

## Implémentation technique

### Fichiers modifiés

- **`handlers/command_handlers/unified_stats.py`**
  - Ajout de la méthode `get_hop_stats()`
  - Intégration dans le router `get_stats()`
  - Mise à jour de l'aide

### Structure de la base de données

La commande utilise la table `packets` de SQLite qui contient déjà :
- `hop_limit` : Nombre de sauts restants
- `hop_start` : Nombre de sauts initial configuré
- Migration automatique si les colonnes n'existent pas

### Agrégation des données

```python
# Pour chaque nœud :
node_hop_data[node_id] = {
    'max_hop_start': max(all_hop_starts_for_node),
    'count': number_of_packets,
    'name': node_name
}
```

## Tests

### Suite de tests complète

Le fichier `test_stats_hop.py` contient 4 tests :

1. **test_hop_stats_basic()** : Vérification fonctionnelle de base
2. **test_hop_stats_sorting()** : Validation du tri décroissant
3. **test_hop_stats_max_hop_start()** : Calcul correct du maximum
4. **test_hop_stats_limit_20()** : Respect de la limite de 20 nœuds

### Démonstration interactive

Le fichier `demo_stats_hop.py` fournit une démonstration réaliste avec :
- Données de test représentatives
- Affichage des deux formats (Mesh et Telegram)
- Exemples d'utilisation avec filtres temporels

## Aide intégrée

### Mesh

```
📊 /stats [cmd] [h]
g=global t=top p=pkt
ch=canal h=histo hop=hops
Types histo: pos,text,node,tele
Ex: /stats hop 48
```

### Telegram

```
📊 **STATS - OPTIONS DISPONIBLES**

**Sous-commandes:**
• `top [h] [n]` - Top talkers avec Canal% et Air TX
• `histo [type] [h]` - Historique (sparkline)
• `packets [h]` - Types de paquets
• `global` - Vue d'ensemble
• `traffic [h]` - Messages publics
• `hop [h]` - Top 20 nœuds par hop_start (portée max)

**Exemples:**
• `/stats hop 48` - Top 20 nœuds par portée sur 48h

**Raccourcis:** hop, hops
```

## Raccourcis

La commande accepte plusieurs alias :
- `/stats hop` (recommandé)
- `/stats hops`

## Limitations

1. **Limite de 20 nœuds** : Seuls les 20 premiers nœuds sont affichés (tri décroissant)
2. **Dépendance aux données** : Nécessite que les paquets incluent `hop_start`
3. **Historique limité** : Maximum 7 jours (168 heures)
4. **Format Mesh réduit** : Seulement 10 nœuds affichés pour respecter la limite LoRa

## Compatibilité

- ✅ Compatible avec tous les canaux (Mesh LoRa, Telegram)
- ✅ Utilise la base SQLite existante
- ✅ Migration automatique des anciennes bases
- ✅ Pas d'impact sur les autres commandes `/stats`

## Notes pour les développeurs

### Extension future possible

1. **Filtrage par type de nœud** : Router, Mobile, Portable
2. **Graphique temporel** : Évolution du hop_start dans le temps
3. **Comparaison hop_start vs. portée réelle** : Calculer l'efficacité
4. **Statistiques géographiques** : Corréler avec les positions GPS
5. **Alertes** : Notification si un nœud change drastiquement son hop_start

### Code quality

- ✅ Tests unitaires complets (4 tests)
- ✅ Documentation intégrée (docstrings)
- ✅ Gestion d'erreurs robuste
- ✅ Logging approprié
- ✅ Respect des conventions du projet

## Références

- **Issue GitHub** : #[à compléter]
- **Fichiers de test** : `test_stats_hop.py`, `demo_stats_hop.py`
- **Documentation Meshtastic** : https://meshtastic.org/docs/overview/mesh-algo/
