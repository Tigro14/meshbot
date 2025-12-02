# 🗺️ Système de Cartes Meshtastic

Visualisation géographique et topologique du réseau Meshtastic via cartes interactives web.

## 📋 Vue d'ensemble

Ce système génère automatiquement une carte interactive unifiée à partir des données du réseau Meshtastic :

**`map.html`** - Carte unifiée avec trois modes de visualisation :
- 🗺️ **Vue Nœuds** : Carte géographique (GPS) des nœuds avec filtres temporels
- 🔗 **Vue Liens** : Topologie réseau avec liens et qualité SNR
- 👁️ **Vue Les deux** : Superposition des deux vues précédentes

**`meshlink.html`** - Redirection automatique vers la vue Liens de la carte unifiée

Les données sont extraites du nœud Meshtastic `tigrog2`, formatées en JSON, puis synchronisées vers un serveur web externe pour visualisation publique.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Raspberry Pi (Bot)                   │
│                                                          │
│  ┌──────────────┐                                       │
│  │ infoup.sh    │  (exécuté par cron toutes les 5 min)  │
│  └──────┬───────┘                                       │
│         │                                                │
│         ├──► 1. export_neighbors.py ──► info_neighbors.json
│         │       (données de voisinage TCP)               │
│         │                                                │
│         ├──► 2. meshtastic --info ──► info_raw.json    │
│         │       (liste des nœuds)                       │
│         │                                                │
│         └──► 3. info_json_clean.py ──► info.json       │
│                 (nettoyage JSON)                         │
│                                                          │
│         ┌────────────────────────────┐                  │
│         │ Validation + Backup        │                  │
│         │ - Vérifie JSON valide      │                  │
│         │ - Taille > 100 bytes       │                  │
│         │ - Garde backup si échec    │                  │
│         └────────────┬───────────────┘                  │
│                      │                                   │
│                      ▼                                   │
│         ┌────────────────────────────┐                  │
│         │ Upload SCP vers serveur    │                  │
│         │ 100.120.148.60             │                  │
│         └────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
                       │
                       │ SCP
                       ▼
┌─────────────────────────────────────────────────────────┐
│           Serveur Web (100.120.148.60)                  │
│         /opt/WebSites/projectsend/                      │
│                                                          │
│  ┌──────────────┐         ┌────────────────────────┐       │
│  │ info.json    │◄────────│  map.html (Unifiée)    │       │
│  └──────────────┘         │  - Vue Nœuds (GPS)     │       │
│                           │  - Vue Liens (Topo)    │       │
│  ┌─────────────────────┐  │  - Vue Les deux        │       │
│  │ info_neighbors.json │  └────────────────────────┘       │
│  └─────────────────────┘                                    │
│                           ┌────────────────┐               │
│                           │ meshlink.html  │               │
│                           │ (Redirige vers │               │
│                           │  map.html)     │               │
│                           └────────────────┘               │
│                                                          │
│            Accessible via https://tigro.fr/             │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Fichiers

### Scripts

| Fichier | Description |
|---------|-------------|
| `infoup.sh` | Script original (simple, mais pas robuste en cron) |
| `infoup_improved.sh` | ✨ Script amélioré avec lock, validation, backup |
| `export_neighbors.py` | Extraction données de voisinage via TCP |
| `info_json_clean.py` | Nettoyage de la sortie `meshtastic --info` |

### Configuration

| Fichier | Description |
|---------|-------------|
| `map_config.sh.sample` | Template de configuration |
| `map_config.sh` | Configuration locale (gitignored) |

### Données générées

| Fichier | Description | Consommateur |
|---------|-------------|--------------|
| `info.json` | Liste des nœuds avec positions GPS | `map.html` |
| `info_neighbors.json` | Relations de voisinage | `meshlink.html` |
| `info.json.backup` | Backup du dernier `info.json` valide | Restauration auto |
| `info_neighbors.json.backup` | Backup du dernier fichier valide | Restauration auto |
| `infoup.log` | Logs d'exécution | Debug |

### Cartes HTML

| Fichier | Description | Source de données |
|---------|-------------|-------------------|
| `map.html` | ✨ **Carte unifiée** avec 3 modes de visualisation | `https://tigro.fr/info.json` |
|  | - Vue **Nœuds** : géographique avec filtres temporels (24h/48h/72h) | |
|  | - Vue **Liens** : topologie réseau avec qualité SNR | |
|  | - Vue **Les deux** : superposition des vues | |
| `meshlink.html` | Redirection automatique vers `map.html?view=links` | - |
| `mesh_map.html` | Carte alternative de topologie (legacy) | Générée par `generate_mesh_map.py` |

---

## ⚙️ Installation

### 1. Configuration

Créer le fichier de configuration :

```bash
cd /home/user/meshbot/map
cp map_config.sh.sample map_config.sh
nano map_config.sh
```

Adapter les valeurs :
- `MESH_HOST` : IP du nœud Meshtastic
- `REMOTE_HOST` : IP du serveur web distant
- `REMOTE_PATH` : Chemin sur le serveur web

### 2. Rendre le script exécutable

```bash
chmod +x infoup_improved.sh
chmod +x export_neighbors.py
```

### 3. Test manuel

```bash
cd /home/user/meshbot/map
./infoup_improved.sh
```

Vérifier les logs :
```bash
tail -f infoup.log
```

### 4. Configurer le cron

**⚠️ IMPORTANT** : Utiliser `infoup_improved.sh` au lieu de `infoup.sh` pour éviter les fichiers vides.

Éditer le crontab :
```bash
crontab -e
```

Ajouter :
```cron
# Mise à jour cartes Meshtastic toutes les 5 minutes
*/5 * * * * /home/user/meshbot/map/infoup_improved.sh >> /home/user/meshbot/map/cron.log 2>&1
```

Ou toutes les 10 minutes (si génération prend >5min) :
```cron
*/10 * * * * /home/user/meshbot/map/infoup_improved.sh >> /home/user/meshbot/map/cron.log 2>&1
```

---

## 🔧 Utilisation

### Génération manuelle

```bash
cd /home/user/meshbot/map
./infoup_improved.sh
```

### Vérifier le statut

```bash
# Logs en temps réel
tail -f infoup.log

# Dernières exécutions
tail -20 infoup.log

# Vérifier la taille des fichiers générés
ls -lh info*.json
```

### Valider les fichiers JSON

```bash
# Syntaxe JSON
python3 -m json.tool info.json > /dev/null && echo "✓ info.json valide"
python3 -m json.tool info_neighbors.json > /dev/null && echo "✓ info_neighbors.json valide"

# Nombre de nœuds
jq '.["Nodes in mesh"] | length' info.json
```

### Tester la connexion serveur

```bash
# Test SCP (sans upload réel)
scp -q /dev/null root@100.120.148.60:/tmp/test && echo "✓ SCP OK"

# Vérifier les fichiers sur le serveur
ssh root@100.120.148.60 "ls -lh /opt/WebSites/projectsend/info*.json"
```

---

## 🐛 Troubleshooting

### Problème : Fichier `info.json` vide en cron

**Cause** : Race condition (plusieurs instances simultanées) ou timeout Meshtastic.

**Solution** :
1. ✅ Utiliser `infoup_improved.sh` qui gère les locks
2. Augmenter l'intervalle cron (*/10 au lieu de */5)
3. Vérifier les logs : `tail -f infoup.log`

### Problème : `export_neighbors.py` timeout

**Cause** : Connexion TCP lente ou nœud indisponible.

**Solution** :
```bash
# Tester manuellement
cd /home/user/meshbot/map
./export_neighbors.py --debug

# Vérifier connexion TCP
nc -zv 192.168.1.38 4403
```

### Problème : Upload SCP échoue

**Cause** : Clés SSH manquantes ou serveur inaccessible.

**Solution** :
```bash
# Configurer clés SSH (si pas déjà fait)
ssh-keygen -t rsa
ssh-copy-id root@100.120.148.60

# Tester connexion
ssh root@100.120.148.60 "echo OK"
```

### Problème : JSON invalide après nettoyage

**Cause** : Format inattendu de `meshtastic --info`.

**Solution** :
```bash
# Voir la sortie brute
meshtastic --host 192.168.1.38 --info > debug_raw.txt
cat debug_raw.txt

# Vérifier le parsing
python3 info_json_clean.py debug_raw.txt debug_clean.json
```

### Problème : Lock expiré constamment

**Cause** : Script met plus de 5 minutes (LOCK_TIMEOUT).

**Solution** :
Augmenter `LOCK_TIMEOUT` dans `map_config.sh` :
```bash
LOCK_TIMEOUT=600  # 10 minutes
```

---

## 📊 Données générées

### Structure de `info.json`

```json
{
  "Nodes in mesh": {
    "!16fad3dc": {
      "num": 385503196,
      "user": {
        "id": "!16fad3dc",
        "longName": "tigro G2 PV",
        "shortName": "TG2",
        "hwModel": "HELTEC_V3"
      },
      "position": {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "altitude": 35
      },
      "snr": 9.75,
      "lastHeard": 1699999999
    }
  }
}
```

### Structure de `info_neighbors.json`

```json
{
  "export_time": "2024-11-16T12:00:00",
  "source_host": "192.168.1.38",
  "total_nodes": 42,
  "nodes": {
    "!16fad3dc": {
      "neighbors_extracted": [
        {
          "nodeId": 385503197,
          "snr": 8.5,
          "lastRxTime": 1699999999
        }
      ],
      "neighbor_count": 15
    }
  },
  "statistics": {
    "nodes_with_neighbors": 28,
    "total_neighbor_entries": 156,
    "average_neighbors": 3.7
  }
}
```

---

## 🌐 Déploiement serveur web

### Option 1 : Serveur distant (actuel)

Les fichiers sont uploadés automatiquement via SCP vers `100.120.148.60`.

Les cartes HTML doivent être présentes sur le serveur :
```bash
scp map.html root@100.120.148.60:/opt/WebSites/projectsend/
scp meshlink.html root@100.120.148.60:/opt/WebSites/projectsend/
```

Accès :
- https://tigro.fr/map.html
- https://tigro.fr/meshlink.html

### Option 2 : Serveur local (Raspberry Pi)

Installer un serveur web sur le Pi :
```bash
sudo apt install nginx
sudo mkdir -p /var/www/meshbot/map
sudo cp *.html *.json /var/www/meshbot/map/
```

Configuration Nginx (`/etc/nginx/sites-available/meshbot`) :
```nginx
server {
    listen 80;
    server_name meshbot.local;
    root /var/www/meshbot/map;
    index map.html;

    location ~ \.json$ {
        add_header Cache-Control "no-cache, must-revalidate";
    }
}
```

Accès local : http://192.168.1.X/map.html

### Option 3 : GitHub Pages (public)

```bash
# Dans un repo git
git add map.html meshlink.html info.json info_neighbors.json
git commit -m "Update maps"
git push

# Activer GitHub Pages dans Settings > Pages
```

Accès : https://username.github.io/meshbot/map.html

---

## 🔐 Sécurité

### Données sensibles dans les JSON

Les fichiers `info.json` contiennent :
- Positions GPS exactes des nœuds
- IDs des nœuds
- Noms des utilisateurs

**Recommandations** :
1. Héberger sur serveur privé (authentification)
2. Ou anonymiser les données avant upload
3. Ou servir seulement en réseau local

### Anonymisation (optionnel)

Créer `anonymize_json.py` :
```python
import json

with open('info.json', 'r') as f:
    data = json.load(f)

for node_id, node in data['Nodes in mesh'].items():
    if 'user' in node:
        node['user']['longName'] = f"Node {node_id[-4:]}"
    if 'position' in node:
        # Réduire précision GPS (±100m)
        node['position']['latitude'] = round(node['position']['latitude'], 3)
        node['position']['longitude'] = round(node['position']['longitude'], 3)

with open('info_anon.json', 'w') as f:
    json.dump(data, f, indent=2)
```

---

## 📈 Optimisations

### Réduire la fréquence cron

Si les données changent peu, passer de */5 à */15 ou */30 :
```cron
*/30 * * * * /home/user/meshbot/map/infoup_improved.sh
```

### Mise en cache côté serveur

Ajouter headers HTTP pour cache (1 minute) :
```nginx
location ~ \.json$ {
    add_header Cache-Control "public, max-age=60";
}
```

### Compression JSON

Activer gzip sur le serveur web :
```nginx
gzip on;
gzip_types application/json;
```

Réduction ~70% de la taille des JSON.

---

## 🔄 Améliorations futures

- [ ] API REST pour interroger les données en temps réel
- [ ] Historique des positions (track GPS)
- [ ] Alertes si nœud disparaît (>24h sans données)
- [ ] Carte de chaleur (heatmap) de couverture
- [ ] Export CSV pour analyse
- [ ] Dashboard Grafana avec métriques réseau
- [ ] Détection automatique de nouveaux nœuds
- [ ] Notifications Telegram si erreur génération

---

## 📞 Support

En cas de problème :

1. Consulter les logs : `tail -f infoup.log`
2. Tester manuellement : `./infoup_improved.sh`
3. Vérifier la doc : ce README
4. Vérifier les issues GitHub

---

## 📄 Licence

Partie du projet **meshbot** - Voir LICENSE à la racine du projet.

---

**Dernière mise à jour** : 2024-11-16
**Maintenu par** : Tigro14
