# hop_limit et hop_start - Documentation

## Vue d'ensemble

Les champs `hop_limit` et `hop_start` ont été ajoutés à la base de données des paquets Meshtastic pour permettre une analyse plus fine du routage mesh.

## Qu'est-ce que TTL (Time To Live) ?

Dans le réseau Meshtastic, chaque paquet a un compteur TTL qui détermine combien de "sauts" (relais) il peut effectuer avant d'être abandonné :

- **hop_start** : Valeur TTL initiale configurée sur le nœud émetteur (typiquement 3 ou 7)
- **hop_limit** : TTL restant après avoir traversé le réseau (décrémenté à chaque relai)
- **hops** : Nombre de sauts effectués = hop_start - hop_limit

### Exemple de Routage

```
Node A (hop_start=3) → Node B (hop_limit=2) → Node C (hop_limit=1) → Bot (hop_limit=0)

Le paquet a fait 3 sauts (hops=3)
```

## Changements Techniques

### 1. Base de Données

**Nouvelles colonnes ajoutées à la table `packets` :**

```sql
ALTER TABLE packets ADD COLUMN hop_limit INTEGER;
ALTER TABLE packets ADD COLUMN hop_start INTEGER;
```

**Migration automatique** :
- Lors du démarrage du bot, les colonnes sont ajoutées automatiquement aux bases existantes
- Les anciens paquets ont `hop_limit` et `hop_start` = NULL
- Les nouveaux paquets incluent ces valeurs

### 2. Fichiers Modifiés

#### traffic_persistence.py
- Ajout de la migration pour les nouvelles colonnes (lignes 96-112)
- Mise à jour de `save_packet()` pour sauvegarder hop_limit et hop_start (ligne 305-327)

#### traffic_monitor.py
- Mise à jour de `packet_entry` pour inclure hop_limit et hop_start (ligne 469-486)

## Cas d'Usage

### 1. Analyse de la Couverture Réseau

Identifier les nœuds en limite de portée :

```sql
SELECT from_id, sender_name, COUNT(*) as exhausted_packets
FROM packets
WHERE hop_limit = 0
GROUP BY from_id
ORDER BY exhausted_packets DESC;
```

**Interprétation** : Si un nœud a beaucoup de paquets avec `hop_limit=0`, il est probablement à la limite de la portée du réseau.

### 2. Détection de Zones Mal Couvertes

Trouver les nœuds nécessitant le plus de relais :

```sql
SELECT 
    from_id, 
    sender_name, 
    AVG(hops) as avg_hops,
    MAX(hops) as max_hops
FROM packets
WHERE hop_start IS NOT NULL
GROUP BY from_id
HAVING AVG(hops) > 2
ORDER BY avg_hops DESC;
```

**Interprétation** : Si un nœud a `avg_hops > 2`, il est probablement très éloigné ou dans une zone mal couverte.

### 3. Audit de Configuration TTL

Vérifier les différentes configurations TTL dans le réseau :

```sql
SELECT 
    hop_start,
    COUNT(DISTINCT from_id) as node_count,
    COUNT(*) as packet_count
FROM packets
WHERE hop_start IS NOT NULL
GROUP BY hop_start
ORDER BY hop_start;
```

**Interprétation** : Permet de voir si tous les nœuds utilisent la même configuration TTL (par défaut 3).

### 4. Analyse de Performance Routage

Mesurer l'efficacité du routage :

```sql
SELECT 
    hops,
    COUNT(*) as packet_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM packets
WHERE hop_start IS NOT NULL
GROUP BY hops
ORDER BY hops;
```

**Interprétation** : Distribution des sauts pour voir combien de paquets sont directs (hops=0) vs relayés.

## Script de Démonstration

Le script `demo_hop_analysis.py` fournit une analyse complète :

```bash
python demo_hop_analysis.py [chemin/vers/traffic_history.db]
```

**Rapport généré** :
1. Statistiques générales (min/max/moyenne hops)
2. Distribution des configurations TTL
3. Paquets en limite de portée (hop_limit=0)
4. Top nœuds par hops moyens
5. Exemples de paquets récents
6. Guide d'interprétation

## Tests

Suite de tests complète : `test_hop_limit_hop_start.py`

**5 tests couvrent** :
1. ✅ Existence des colonnes dans la base
2. ✅ Migration sur base existante
3. ✅ Sauvegarde et chargement des données
4. ✅ Intégration TrafficMonitor
5. ✅ Gestion des valeurs NULL

Exécuter les tests :

```bash
python test_hop_limit_hop_start.py
```

## Compatibilité

- ✅ **Rétrocompatible** : Les anciennes bases sont migrées automatiquement
- ✅ **Pas de perte de données** : Les paquets existants conservent leurs valeurs `hops` calculées
- ✅ **Transparent** : Aucune modification de configuration requise
- ✅ **Pas d'impact performance** : Colonnes indexées, requêtes optimisées

## Limitations

1. **Anciens paquets** : Les paquets enregistrés avant cette mise à jour ont `hop_limit` et `hop_start` = NULL
2. **Paquets chiffrés** : Les valeurs hop peuvent ne pas être disponibles pour certains paquets chiffrés
3. **Calcul hops** : Le champ `hops` reste calculé (hop_start - hop_limit) pour compatibilité

## Bénéfices

- 🔍 **Diagnostic réseau** : Identifier les zones mal couvertes
- 📊 **Optimisation** : Placer les nœuds de manière optimale
- 🛠️ **Dépannage** : Comprendre pourquoi certains nœuds ne communiquent pas
- 📈 **Métriques** : Mesurer la santé du réseau mesh
- 🎯 **Planification** : Prévoir l'ajout de répéteurs

## Références

- **Meshtastic Routing** : https://meshtastic.org/docs/overview/mesh-algorithm/
- **TTL (Time To Live)** : https://en.wikipedia.org/wiki/Time_to_live
- **Issue GitHub** : "add hop_limit and hop_start to DB, seems missing and would be useful"

## Auteurs

- **Implémentation** : GitHub Copilot
- **Tests** : Automatisés et validés
- **Documentation** : Complète avec exemples

---

**Date** : 2025-12-10  
**Version Bot** : main + PR copilot/add-hop-limit-and-hop-start
