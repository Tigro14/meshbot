# Navigateur interactif pour traffic_history.db

Interface TUI (Text User Interface) interactive style `lnav` pour parcourir la base de données de trafic avec les touches fléchées.

## Installation

Aucune dépendance externe requise (utilise `curses` de la stdlib Python).

```bash
chmod +x browse_traffic_db.py
```

## Lancement

```bash
./browse_traffic_db.py
# ou
python3 browse_traffic_db.py

# Avec une DB à un autre emplacement
./browse_traffic_db.py --db /chemin/vers/traffic_history.db
```

## Navigation

### Navigation de base

- **↑ / ↓** ou **j / k** : Monter/descendre dans la liste
- **PgUp / PgDn** : Page précédente/suivante
- **Home / End** : Aller au début/fin de la liste
- **ENTER** : Voir les détails de l'item sélectionné
- **ESC** ou **q** : Quitter (depuis la vue liste)

### Actions

- **/** : Rechercher dans les messages
  - Tape votre terme de recherche
  - ENTER pour valider
  - La vue se rafraîchit avec les résultats

- **f** : Filtrer par type de paquet (vue packets seulement)
  - Affiche la liste des types disponibles
  - Tape le numéro correspondant
  - 0 pour enlever le filtre

- **v** : Changer de vue
  - Cycle entre : packets → messages → nodes → packets
  - Réinitialise les filtres et recherche

- **r** : Rafraîchir les données depuis la DB
  - Utile si le bot est en cours d'exécution

- **?** : Afficher l'aide

### Mode détail

Quand vous appuyez sur ENTER sur un item :

- **↑ / ↓** : Scroller le texte des détails
- **PgUp / PgDn** : Scroller par page
- **ENTER** ou **ESC** : Retourner à la liste

## Vues disponibles

### Vue PACKETS (par défaut)

Affiche tous les paquets reçus avec :
- Timestamp
- Source (local/tigrog2)
- Nom de l'expéditeur
- Type de paquet
- Début du message (si présent)

**Détails :** Timestamp, IDs, type, signal (RSSI/SNR), hops, message complet, télémétrie

### Vue MESSAGES

Affiche uniquement les messages publics broadcast avec :
- Timestamp
- Source
- Nom de l'expéditeur
- Texte du message

**Détails :** Infos complètes du message, signal, longueur

### Vue NODES

Affiche les statistiques par nœud :
- ID du nœud
- Nombre total de paquets
- Taille totale des données

**Détails :** Stats complètes par type de paquet, activité horaire, stats de messages, télémétrie

## Interface

```
┌─────────────────────────────────────────────────────────────────┐
│      Traffic DB Browser - PACKETS [Filter: TEXT_MESSAGE_APP]    │
│ 156 items | Row 5/156                                           │
├─────────────────────────────────────────────────────────────────┤
│11-14 22:15 local    tigrog2         TEXT_MESSAGE_APP  Bonjour  │
│11-14 22:16 tigrog2  alice           POSITION_APP               │
│11-14 22:17 local    bob             TEXT_MESSAGE_APP  Salut    │
│11-14 22:18 tigrog2  charlie         TELEMETRY_APP              │
│> 11-14 22:19 local  tigrog2         TEXT_MESSAGE_APP  Test     │  ← Sélection
│11-14 22:20 tigrog2  dave            NODEINFO_APP               │
│...                                                              │
├─────────────────────────────────────────────────────────────────┤
│↑/↓:Nav ENTER:Details /:Search f:Filter v:View r:Refresh q:Quit │
└─────────────────────────────────────────────────────────────────┘
```

## Exemples d'utilisation

### Parcourir les derniers paquets
```bash
./browse_traffic_db.py
# Utilise ↑/↓ pour naviguer
# ENTER pour voir les détails
```

### Chercher un message
```bash
./browse_traffic_db.py
# Appuie sur /
# Tape "météo"
# ENTER
# Navigue dans les résultats
```

### Filtrer par type de paquet
```bash
./browse_traffic_db.py
# Appuie sur f
# Sélectionne le numéro correspondant à TEXT_MESSAGE_APP
# Navigue dans les messages filtrés
```

### Voir les stats des nœuds
```bash
./browse_traffic_db.py
# Appuie sur v pour passer en vue NODES
# Navigue dans la liste des nœuds
# ENTER pour voir les détails d'un nœud
```

### Surveiller en temps réel
```bash
./browse_traffic_db.py
# Pendant que le bot tourne
# Appuie sur r périodiquement pour rafraîchir
```

## Astuces

1. **Navigation rapide** : Utilisez PgUp/PgDn pour naviguer rapidement dans de grandes listes

2. **Filtres multiples** : Combinez recherche (/) et filtre (f) pour affiner les résultats

3. **Détails longs** : Dans le mode détail, utilisez ↑/↓ pour scroller si le contenu dépasse l'écran

4. **Changement de vue** : Appuyez plusieurs fois sur 'v' pour cycler rapidement entre les vues

5. **Réinitialiser** : Appuyez sur 'v' pour changer de vue, ça réinitialise les filtres

## Limitations

- Charge max 1000 items par vue (pour les performances)
- La recherche ne fonctionne que sur les messages texte
- Le filtre par type n'est disponible que dans la vue packets
- Nécessite un terminal avec support des couleurs et curses

## Comparaison avec view_traffic_db.py

| Fonctionnalité | view_traffic_db.py | browse_traffic_db.py |
|----------------|-------------------|---------------------|
| Type | CLI statique | TUI interactive |
| Navigation | Aucune | Flèches, vim-style |
| Recherche | Via argument | Interactive (/) |
| Filtre | N/A | Interactive (f) |
| Détails | Tout affiché | À la demande (ENTER) |
| Rafraîchir | Relancer script | Touche (r) |
| Use case | Rapports rapides | Exploration approfondie |

## Codes de retour

- 0 : Sortie normale
- 1 : Erreur de connexion à la DB

## Troubleshooting

**"Error: Cannot open database"**
- Vérifiez que traffic_history.db existe
- Utilisez --db pour spécifier le chemin correct

**Interface cassée / caractères bizarres**
- Votre terminal ne supporte peut-être pas curses
- Essayez un terminal différent (xterm, gnome-terminal, etc.)

**Trop lent**
- La DB contient beaucoup de données
- Utilisez les filtres (f) pour réduire le nombre d'items

**ESC ne fonctionne pas**
- Certains terminaux ont un délai sur ESC
- Utilisez 'q' à la place
