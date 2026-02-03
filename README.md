# Bot Meshtastic-Llama

Bot pour réseau Meshtastic (+ Telegram, optionnel) avec intégration Llama et fonctionnalités avancées.

## Architectures supportées

Le bot supporte plusieurs modes de fonctionnement :

### Mode Meshtastic Serial (recommandé)
Connexion directe via USB/UART - Configuration simple et stable

```mermaid
graph TD
    %% Styles
    classDef node fill:#f9f,color:#000
    classDef rpi fill:#bbf,color:#000
    classDef connection stroke:#333,color:#000

    %% Nodes
    RPi5["Raspberry Pi 5<br/>(Bot + Llama.cpp)"]:::rpi
    MeshNode["Meshtastic Node<br/>(Serial USB/UART)"]:::node
    MeshNetwork["Réseau Mesh<br/>LoRa"]:::node

    %% Connections
    RPi5 -- "/dev/ttyACM0<br/>(USB)" --> MeshNode
    MeshNode -- "LoRa" --> MeshNetwork
```

**Avantages** : Simple, stable, latence minimale  
**Inconvénient** : Node doit être proche du Raspberry Pi

### Mode Meshtastic TCP (placement optimal)
Connexion réseau - Le node peut être placé à distance (extérieur, meilleure antenne)

```mermaid
graph TD
    %% Styles
    classDef node fill:#f9f,color:#000
    classDef rpi fill:#bbf,color:#000
    classDef connection stroke:#333,color:#000

    %% Nodes
    RPi5["Raspberry Pi 5<br/>(Bot + Llama.cpp)"]:::rpi
    MeshRouter["Meshtastic ROUTER<br/>(TCP/IP)"]:::node
    MeshNetwork["Réseau Mesh<br/>LoRa"]:::node

    %% Connections
    RPi5 -- "192.168.x.x:4403<br/>(WiFi/Ethernet)" --> MeshRouter
    MeshRouter -- "LoRa" --> MeshNetwork
```

**Avantages** : Node peut être à distance, meilleur placement d'antenne  
**Inconvénients** : Configuration réseau requise, dépend de la stabilité WiFi/Ethernet

### Mode MeshCore Companion (NOUVEAU) 
Connexion série MeshCore uniquement - Bot fonctionnant sans Meshtastic

**⭐ Utilise la library officielle [meshcore-cli](https://github.com/fdlamotte/meshcore-cli) si disponible**

```mermaid
graph TD
    %% Styles
    classDef node fill:#9f9,color:#000
    classDef rpi fill:#bbf,color:#000
    classDef connection stroke:#333,color:#000

    %% Nodes
    RPi5["Raspberry Pi 5<br/>(Bot + Llama.cpp)"]:::rpi
    MeshCoreNode["MeshCore Device<br/>(Serial USB/UART)"]:::node
    MeshCoreNetwork["Réseau MeshCore<br/>LoRa"]:::node

    %% Connections
    RPi5 -- "/dev/ttyUSB0<br/>(USB Serial)" --> MeshCoreNode
    MeshCoreNode -- "LoRa" --> MeshCoreNetwork
```

**Mode companion** : Le bot reçoit uniquement des DM (Direct Messages) via MeshCore
- ✅ Fonctionnalités disponibles : `/bot`, `/weather`, `/rain`, `/power`, `/sys`, `/help`, `/blitz`, `/vigilance`
- ❌ Fonctionnalités désactivées : `/nodes`, `/my`, `/trace`, `/neighbors`, `/stats` (requièrent Meshtastic)

**Installation** : 
```bash
pip install meshcore  # Library officielle (recommandé)
```

**Avantages** : Utilisation avec MeshCore, pas besoin de matériel Meshtastic, support protocole officiel  
**Inconvénients** : Fonctionnalités réseau Meshtastic non disponibles

**Configuration** : Voir `config.meshcore.example` pour un exemple complet

```markdown
## Fonctionnalités

- **Chat IA** : Intégration Llama via `/bot <question>`
- **Monitoring système** : `/sys` pour température CPU, RAM, uptime
- **Analyse réseau** : `/nodes` pour les nœuds directx entendus, `/my` pour signaux personnels, `/neighbors` pour topologie mesh
- **Stats réseau** : `/histo` pour la répartition en histogramme des paquets entendus, `/stats` ou `/packets` ou `/top` pour d'autres stats
- **Données ESPHome** : `/power` pour télémétrie solaire/batterie
- **Administration** : Commandes cachées pour gestion à distance
- **Collecte MQTT** : Collection automatique de topologie réseau via MQTT (au-delà de la portée radio)
- **Auto-récupération TCP** : Redémarrage automatique du node distant en cas d'échec de connexion (voir [TCP_AUTO_REBOOT.md](TCP_AUTO_REBOOT.md))

- genère une carte HMTL/JS des nodes, et une pour les links neighbours (dossier /map, autonome du bot)

- Pour compiler/installer llama.cpp sur le Raspberry Pi 5,
  voir le fichier https://github.com/Tigro14/meshbot/blob/main/llama.cpp-integration/READMELLAMA.md

## Installation

### Prérequis

**Système :**
- Python 3.8+ (testé sur Python 3.11-3.13)
- Raspberry Pi 5 recommandé (fonctionne sur autres Linux)
- Llama.cpp en cours d'exécution (voir [READMELLAMA.md](llama.cpp-integration/READMELLAMA.md))
- ESPHome (optionnel pour télémétrie solaire/batterie)

**Dépendances système (apt) :**
```bash
# Headers Python (requis pour pygeohash)
sudo apt-get install python3-dev

# Optionnel : outils de développement
sudo apt-get install git python3-pip python3-venv
```

### Installation des dépendances Python

**Méthode 1 : Depuis requirements.txt (recommandé)**
```bash
# Cloner le repository
git clone https://github.com/Tigro14/meshbot.git
cd meshbot

# Installer les dépendances
pip install -r requirements.txt --break-system-packages

# Note: --break-system-packages nécessaire sur Raspberry Pi OS
# et autres systèmes avec pip géré par le système
```

**Méthode 2 : Installation manuelle**
```bash
pip install meshtastic pypubsub requests python-telegram-bot \
    beautifulsoup4 lxml paho-mqtt pygeohash --break-system-packages
```

### Configuration

**⚠️ NOUVEAU : Configuration séparée en deux fichiers**

La configuration est maintenant divisée en deux fichiers pour une meilleure sécurité :
- **config.py** : Paramètres publics (ports, fonctionnalités, limites)
- **config_priv.py** : Paramètres sensibles (tokens, mots de passe, IDs utilisateurs) - **gitignored**

1. **Copier les templates de configuration**
   ```bash
   cp config.py.sample config.py
   cp config.priv.py.sample config_priv.py
   ```
   
   **OU** utiliser un exemple prêt à l'emploi :
   ```bash
   # Pour mode Serial (connexion USB)
   cp config.serial.example config.py
   cp config.priv.py.sample config_priv.py
   
   # Pour mode TCP (connexion réseau)
   cp config.tcp.example config.py
   cp config.priv.py.sample config_priv.py
   ```

2. **Éditer `config_priv.py` avec vos paramètres SENSIBLES**

   ```python
   # Token Telegram (obtenir via @BotFather)
   TELEGRAM_BOT_TOKEN = "1234567890:ABCdef..."
   
   # Utilisateurs autorisés (IDs Telegram)
   TELEGRAM_AUTHORIZED_USERS = [123456789]
   
   # Mot de passe pour commande /rebootpi
   REBOOT_PASSWORD = "your_secret_password"
   
   # Utilisateurs autorisés à rebooter
   REBOOT_AUTHORIZED_USERS = [123456789, 0x16fad3dc]
   
   # Mot de passe MQTT
   MQTT_NEIGHBOR_PASSWORD = "your_mqtt_password"
   ```

3. **Éditer `config.py` avec vos paramètres PUBLICS**

   **Mode de connexion (CONNECTION_MODE)**
   
   Le bot supporte maintenant deux modes de connexion au réseau Meshtastic :
   
   - **Mode Serial (défaut)** : Connexion via port série USB/UART
     ```python
     CONNECTION_MODE = 'serial'
     SERIAL_PORT = "/dev/ttyACM0"  # Adapter selon votre port
     ```
   
   - **Mode TCP** : Connexion réseau à un node ROUTER accessible en WiFi/Ethernet
     ```python
     CONNECTION_MODE = 'tcp'
     TCP_HOST = "192.168.1.38"  # IP du node Meshtastic
     TCP_PORT = 4403            # Port TCP (défaut: 4403)
     
     # Auto-reboot en cas d'échec de connexion (recommandé)
     TCP_AUTO_REBOOT_ON_FAILURE = True  # Redémarre le node si inaccessible
     TCP_REBOOT_WAIT_TIME = 45          # Attente après reboot (secondes)
     ```
     
     **Note:** Le mode TCP inclut désormais un système de récupération automatique. Si le node distant est inaccessible au démarrage (erreur "No route to host"), le bot tente automatiquement de le redémarrer via `meshtastic --reboot`. Voir [TCP_AUTO_REBOOT.md](TCP_AUTO_REBOOT.md) pour plus de détails.
   
   **Autres paramètres importants :**
   - Token Telegram (`TELEGRAM_BOT_TOKEN`) si intégration Telegram
   - Département pour vigilance météo (`VIGILANCE_DEPARTEMENT`)
   - Configuration AI Llama (host, port, prompts)
   - Autres paramètres selon besoins

3. **Lancer le bot**
   ```bash
   python main_script.py
   ```

   Ou en mode debug :
   ```bash
   python main_script.py --debug
   ```

### Choix du mode de connexion

**Mode Serial (recommandé pour débutants)**
- ✅ Connexion directe et stable
- ✅ Pas de configuration réseau nécessaire
- ✅ Latence minimale
- ❌ Nécessite un câble USB
- ❌ Node doit être proche du Raspberry Pi

**Mode TCP (pour déploiements avancés)**
- ✅ Node peut être placé à distance (meilleure position pour antenne)
- ✅ Pas de câble USB nécessaire
- ✅ Permet l'utilisation d'un node ROUTER existant
- ❌ Nécessite configuration WiFi/Ethernet du node
- ❌ Dépend de la stabilité du réseau local
- ❌ Latence légèrement supérieure

**Exemple de cas d'usage TCP :**
```
Raspberry Pi 5 (intérieur, serveur)
        ↓ WiFi/Ethernet
Node Meshtastic ROUTER (extérieur, antenne optimale)
        ↓ LoRa
Réseau mesh Meshtastic
```

**Note pour utilisateurs avancés :**
L'architecture legacy multi-nodes (connexions Serial + TCP simultanées) reste supportée pour compatibilité. 
Consultez [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) pour plus de détails.

### Installation en tant que service systemd

Voir le fichier `meshbot.service` pour un exemple de service systemd.

```bash
# Copier le service
sudo cp meshbot.service /etc/systemd/system/

# Éditer les chemins si nécessaire
sudo nano /etc/systemd/system/meshbot.service

# Activer et démarrer
sudo systemctl daemon-reload
sudo systemctl enable meshbot
sudo systemctl start meshbot

# Vérifier les logs
journalctl -u meshbot -f
```

## Configuration du redémarrage à distance

Le bot dispose d'une commande cachée `/rebootpi` qui permet de redémarrer le Pi5 à distance.
Pour des raisons de sécurité, cette fonctionnalité utilise un système de sémaphore en mémoire partagée.

**Note importante**: Le système utilise `/dev/shm` (mémoire partagée tmpfs) au lieu de `/tmp`.
Cela garantit que le signal de redémarrage fonctionne **même si le système de fichiers principal
devient read-only** (un problème courant sur Raspberry Pi avec des cartes SD défaillantes).

### 1. Script de surveillance

Créer le script `/usr/local/bin/rebootpi-watcher.sh` :

```bash
#!/bin/bash
# Script de surveillance pour redémarrage Pi via bot Meshtastic
# Utilise /dev/shm (tmpfs RAM) pour survivre aux filesystems read-only

LOCK_FILE="/dev/shm/meshbot_reboot.lock"
INFO_FILE="/dev/shm/meshbot_reboot.info"
LOG_FILE="/var/log/bot-reboot.log"

while true; do
    # Vérifier si le sémaphore de reboot est actif
    # On teste si le fichier lock existe et si on peut acquérir le lock
    if [ -f "$LOCK_FILE" ]; then
        # Tenter d'acquérir un lock exclusif (non-blocking)
        if ! flock -n -x "$LOCK_FILE" -c 'true' 2>/dev/null; then
            # Le lock est tenu = signal de reboot actif
            echo "$(date): Redémarrage Pi demandé via sémaphore (/dev/shm)" >> "$LOG_FILE"
            
            # Lire et logger les informations si disponibles
            if [ -f "$INFO_FILE" ]; then
                cat "$INFO_FILE" >> "$LOG_FILE"
            fi
            
            # Nettoyer les fichiers de signal
            rm -f "$LOCK_FILE" "$INFO_FILE" 2>/dev/null || true
            
            echo "$(date): Exécution du redémarrage Pi..." >> "$LOG_FILE"

            # Méthodes de redémarrage pour RPi5 (par ordre de préférence)
            # 1. systemctl (recommandé pour systemd)
            systemctl reboot || \
            # 2. shutdown avec délai court
            shutdown -r +1 "Redémarrage via bot" || \
            # 3. reboot direct
            /sbin/reboot || \
            # 4. sync + reboot forcé
            { sync; echo 1 > /proc/sys/kernel/sysrq; echo b > /proc/sysrq-trigger; }
        fi
    fi
    sleep 5
done
```

#### Alternative Python (recommandée)

Le bot inclut aussi une version Python plus robuste: `rebootpi-watcher.py`

Avantages de la version Python:
- ✅ Gestion d'erreurs plus complète
- ✅ Logs détaillés
- ✅ Shutdown gracieux (SIGTERM)
- ✅ Plus facile à maintenir et débugger

Pour utiliser la version Python, copiez le script:
```bash
sudo cp rebootpi-watcher.py /usr/local/bin/
sudo chmod +x /usr/local/bin/rebootpi-watcher.py
```

### 2. Service systemd pour permettre le reboot du Pi à distance

Créer le fichier `/etc/systemd/system/rebootpi-watcher.service` :

**Version Bash (simple):**
```ini
[Unit]
Description=Bot RebootPi Watcher (Bash)
Documentation=https://github.com/Tigro14/meshbot
After=multi-user.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/usr/local/bin/rebootpi-watcher.sh
Restart=always
RestartSec=10
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Version Python (recommandée):**
```ini
[Unit]
Description=Bot RebootPi Watcher (Python)
Documentation=https://github.com/Tigro14/meshbot
After=multi-user.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/rebootpi-watcher.py
Restart=always
RestartSec=10
User=root
StandardOutput=journal
StandardError=journal
WorkingDirectory=/home/votre-user/meshbot

[Install]
WantedBy=multi-user.target
```

**Note**: Ajustez `WorkingDirectory` pour pointer vers le répertoire du bot (nécessaire pour
importer `reboot_semaphore.py`).

### 3. Activation du service

```bash
# Rendre le script exécutable
sudo chmod +x /usr/local/bin/rebootpi-watcher.sh

# Créer le fichier de log
sudo touch /var/log/bot-reboot.log
sudo chmod 644 /var/log/bot-reboot.log

# Recharger systemd
sudo systemctl daemon-reload

# Activer et démarrer le service
sudo systemctl enable rebootpi-watcher.service
sudo systemctl start rebootpi-watcher.service

# Vérifier le statut
sudo systemctl status rebootpi-watcher.service
```

### 4. Vérification

```bash
# Vérifier que le service est actif
sudo systemctl is-active rebootpi-watcher.service

# Consulter les logs du service
sudo journalctl -u rebootpi-watcher.service -f

# Consulter le log fichier
sudo tail -f /var/log/bot-reboot.log

# Tester le mécanisme avec le module Python (SANS redémarrage réel)
python3 test_reboot_semaphore.py

# Test complet du signal (ATTENTION: redémarre le système!)
# Version Python:
python3 << 'EOF'
from reboot_semaphore import RebootSemaphore
import time

info = {
    'name': 'TestManual',
    'node_id': '0xFFFFFFFF',
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
}
RebootSemaphore.signal_reboot(info)
print("Signal envoyé - Le système va redémarrer dans 5-10 secondes!")
EOF

# Ou version shell (si vous utilisez la version bash du watcher):
# sudo python3 -c "from reboot_semaphore import RebootSemaphore; RebootSemaphore.signal_reboot({'name': 'Test', 'node_id': '0xFF', 'timestamp': '2024-01-01 00:00:00'})"
```

**Note sur /dev/shm**: Le système utilise maintenant `/dev/shm/meshbot_reboot.lock` au lieu de 
`/tmp/reboot_requested`. Cela permet au signal de reboot de fonctionner **même si le système de
fichiers principal est en read-only** (problème fréquent sur RPi avec SD corrompue).

Proceder de même avec :

- https://github.com/Tigro14/meshbot/blob/main/meshbot.service pour le bot Mesh+Telegram
- https://github.com/Tigro14/meshbot/blob/main/llama.cpp-integration/llamacpp.service pour llama.cpp

### Sécurité

- La commande `/rebootpi` n'apparaît pas dans l'aide publique
- Tous les redémarrages sont tracés dans `/var/log/bot-reboot.log`
- Le fichier signal contient l'identité du demandeur
- Le service de surveillance fonctionne avec des privilèges root

### Logs de traçabilité

Le fichier `/var/log/bot-reboot.log` contient :
- Horodatage de la demande
- Identité du nœud Meshtastic demandeur
- ID hexadécimal du nœud pour traçabilité complète

## Serveur CLI (Interface en ligne de commande)

Le bot intègre un serveur TCP local permettant de se connecter via une interface CLI pour envoyer des commandes sans passer par le réseau Meshtastic. Utile pour le développement et le debug.

### Configuration

Dans `config.py` :

```python
# Activer le serveur CLI
CLI_ENABLED = True
CLI_SERVER_HOST = '127.0.0.1'  # Écoute locale uniquement (sécurité)
CLI_SERVER_PORT = 9999
```

### Utilisation

Le client CLI se connecte au bot via TCP sur localhost:9999 :

```bash
# Lancer le client CLI
python cli_client.py

# Ou avec des paramètres personnalisés
python cli_client.py --host 127.0.0.1 --port 9999
```

Une fois connecté, vous pouvez envoyer toutes les commandes du bot :

```
> /help
🤖 Bot:
[Affiche l'aide complète]

> /stats top 24 5
🤖 Bot:
📊 Top 5 talkers (24h)
...

> /trace F547F
🤖 Bot:
🔍 Node F547F
📶 Signal info...

> quit
👋 Disconnecting...
```

### Fonctionnalités

- **Pas de limite LoRa** : Pas de contrainte de 180 caractères
- **Pas de throttling** : Pas de limite de commandes/minute
- **Accès complet** : Toutes les commandes du bot disponibles
- **Pas de compétition série** : Le CLI ne touche pas au port `/dev/ttyACM0`
- **Historique des commandes** : Navigation avec ↑/↓ (comme bash), persistant entre sessions
- **Multi-client** : Plusieurs clients CLI peuvent se connecter simultanément (futur)

### Architecture

Le serveur CLI fonctionne en parallèle du bot principal :
- **Bot principal** : Écoute sur l'interface configurée (Serial ou TCP)
- **Serveur CLI** : Écoute sur `127.0.0.1:9999` (TCP local)
- **Aucune interférence** : Les deux systèmes sont indépendants

### Sécurité

- Écoute **uniquement** en local (`127.0.0.1`)
- Pas d'accès distant possible
- Idéal pour développement et debug local

## Commandes disponibles

### Commandes MESH
- `/bot <question>` - Chat avec l'IA
- `/power` - Données ESPHome (batterie, solaire, météo)
- `/weather [rain|astro] [ville] [days]` - Météo (par https://wttr.in)
  - `/weather` - Météo locale (géolocalisée)
  - `/weather Paris` - Météo d'une ville spécifique
  - `/weather rain` - Graphe précipitations aujourd'hui (sparklines haute résolution)
  - `/weather rain 3` - Graphe précipitations 3 jours
  - `/weather rain Paris` - Précipitations Paris (aujourd'hui)
  - `/weather rain Paris 3` - Précipitations Paris (3 jours)
  - `/weather astro` - Infos astronomiques (sunrise, sunset, moon 🌑🌕)
  - `/weather astro Paris` - Infos astronomiques Paris
  - `/weather help` - Afficher l'aide
- `/nodes [page]` - Liste des nœuds directs vus par votre node (paginé, trié par SNR)
- `/my` - Vos signaux vus par votre node (lookinglass)
- `/trace` - Traceroute de votre message vers le bot (hops, RSSI, SNR)
- `/trace <node>` - Afficher les infos signal d'un nœud spécifique (nom ou ID partiel)
- `/sys` - Informations système (CPU, RAM, uptime bot et OS)
- `/stats [sub]` - Statistiques unifiées avec sous-commandes :
  - `/stats` ou `/stats global` - Aperçu global du réseau
  - `/stats top [heures] [n]` - Top talkers (défaut: 24h, top 10)
  - `/stats packets [heures]` - Distribution des types de paquets
  - `/stats channel [heures]` - Utilisation du canal
  - `/stats histo [type] [heures]` - Histogramme par type
  - `/stats traffic [heures]` - Historique des messages publics (Telegram uniquement)
- `/top [heures]` - Alias pour `/stats top` (legacy)
- `/histo [type]` - Alias pour `/stats histo` (legacy)
- `/packets` - Alias pour `/stats packets` (legacy)
- `/trafic` - Trafic du mesh local sur les dernières heures
- `/echo <message>` - Diffuser un message sur le réseau mesh
- `/legend` - Légende des indicateurs de signal
- `/help` - Aide des commandes

### Commandes administration
- `/rebootpi <passwd>` - Redémarrage du Pi5 (nécessite configuration et autorisation)

### Les commandes specifiques Telegram
- le bot IA a plus de token et de contexte ca les restrictions sont moindre qu'en Mesh
- `/fullnodes` renvoie une liste complete de tous les nodes et signal en mémoire du node répéteur
- voir /help pour pour d'info

## Configuration

Le fichier `config.py` contient tous les paramètres configurables :
- Ports série et réseau
- Token telegram
- Limites de throttling
- Configuration des nœuds distants
- Paramètres d'affichage


## Limitations

- Throttling : 5 commandes par 5 minutes par utilisateur
- Messages limités à 180 caractères (contrainte LoRa)
- Nécessite llama.cpp en fonctionnement pour `/bot`

---

## Documentation

### Quick Start
- **This file (README.md)**: Setup and user guide
- **[DOCS_INDEX.md](DOCS_INDEX.md)**: Complete documentation index
- **[CLAUDE.md](CLAUDE.md)**: Comprehensive developer guide (for AI assistants and contributors)

### User Guides
- **[CLI_USAGE.md](CLI_USAGE.md)**: Command-line interface usage
- **[ENCRYPTED_PACKETS_EXPLAINED.md](ENCRYPTED_PACKETS_EXPLAINED.md)**: Understanding DM encryption

### Developer Guides
- **[CLAUDE.md](CLAUDE.md)**: Primary development resource (2,968+ lines)
- **[PLATFORMS.md](PLATFORMS.md)**: Multi-platform architecture
- **[TCP_ARCHITECTURE.md](TCP_ARCHITECTURE.md)**: Network stack architecture
- **[STATS_CONSOLIDATION_PLAN.md](STATS_CONSOLIDATION_PLAN.md)**: Statistics system design

### Configuration & Migration
- **[CONFIG_MIGRATION.md](CONFIG_MIGRATION.md)**: Configuration updates
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)**: General migration guide
- **[MESHCORE_COMPANION.md](MESHCORE_COMPANION.md)**: MeshCore mode documentation
- **[REBOOT_SEMAPHORE.md](REBOOT_SEMAPHORE.md)**: Remote reboot mechanism

### Database Tools
- **[BROWSE_TRAFFIC_DB.md](BROWSE_TRAFFIC_DB.md)**: Web UI for traffic database
- **[TRAFFIC_DB_VIEWER.md](TRAFFIC_DB_VIEWER.md)**: CLI database viewer

### Historical Documentation
Over **412 archived documentation files** are available in `docs/archive/` for historical reference. See **[docs/archive/README.md](docs/archive/README.md)** for details.

---

## Crédits

Bot créé par Tigro14. Intégration Llama, Telegram, ESPHome, statistiques avancées, et bien plus.

