# Visualiseur de la base de données Traffic History

Script CLI pour explorer et visualiser le contenu de `traffic_history.db`.

## Installation

Le script utilise uniquement des bibliothèques Python standard, aucune dépendance externe requise.

```bash
chmod +x view_traffic_db.py
```

## Utilisation

### Commandes disponibles

#### 1. Résumé global (par défaut)
```bash
./view_traffic_db.py summary
# ou simplement
./view_traffic_db.py
```
Affiche :
- Statistiques générales (nombre de paquets, messages, nœuds)
- Période couverte
- Taille de la base de données
- Répartition par type de paquet
- Top 10 nœuds les plus actifs

#### 2. Derniers paquets
```bash
./view_traffic_db.py packets
./view_traffic_db.py packets --limit 50
```
Affiche les derniers paquets reçus avec :
- Horodatage
- Expéditeur (nom + ID)
- Type de paquet
- Signal (RSSI, SNR, hops)
- Message (si présent)

#### 3. Derniers messages publics
```bash
./view_traffic_db.py messages
./view_traffic_db.py messages --limit 30
```
Affiche uniquement les messages texte publics broadcast.

#### 4. Statistiques par nœud
```bash
# Tous les nœuds
./view_traffic_db.py nodes

# Nœud spécifique
./view_traffic_db.py node 0x123abc
./view_traffic_db.py node !123abc
```
Affiche pour chaque nœud :
- Total de paquets et octets
- Types de paquets envoyés
- Activité horaire
- Stats de messages (nombre, longueur moyenne)
- Stats de télémétrie (batterie, tension, utilisation canal)

#### 5. Statistiques globales
```bash
./view_traffic_db.py global
```
Affiche :
- Statistiques globales du réseau
- Répartition des types de paquets
- Statistiques réseau (hops, RSSI/SNR moyens)

#### 6. Recherche de texte
```bash
./view_traffic_db.py search "bonjour"
./view_traffic_db.py search "test123"
```
Recherche un terme dans tous les messages.

### Options générales

```bash
--db chemin/vers/base.db    # Spécifier une autre base de données
--limit N                    # Limiter le nombre de résultats (défaut: 20)
```

## Exemples d'utilisation

### Vérifier que la persistance fonctionne
```bash
# Afficher un résumé
./view_traffic_db.py summary

# Vérifier les derniers messages reçus
./view_traffic_db.py messages --limit 10
```

### Analyser l'activité d'un nœud
```bash
# Trouver l'ID du nœud dans le résumé
./view_traffic_db.py summary

# Voir les détails du nœud
./view_traffic_db.py node 0x862ad3dc
```

### Chercher un message spécifique
```bash
./view_traffic_db.py search "météo"
./view_traffic_db.py search "test"
```

### Voir l'historique complet
```bash
# 100 derniers paquets
./view_traffic_db.py packets --limit 100

# 50 derniers messages
./view_traffic_db.py messages --limit 50
```

## Sortie colorée

Le script utilise des couleurs ANSI pour une meilleure lisibilité :
- 🔵 Bleu : Titres et sections
- 🟢 Vert : Valeurs numériques et compteurs
- 🟡 Jaune : Timestamps et informations importantes
- 🔴 Rouge : Erreurs
- ⚪ Blanc gras : En-têtes

## Emplacement de la base de données

Par défaut, le script cherche `traffic_history.db` dans le répertoire courant.

Si votre base est ailleurs :
```bash
./view_traffic_db.py summary --db /chemin/vers/traffic_history.db
```

## Aide

```bash
./view_traffic_db.py --help
```
