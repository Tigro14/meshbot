# PR Summary - Migration vers Single-Node TCP/Serial

## 🎯 Objectif

Migration du bot Meshtastic vers une configuration simplifiée à un seul node, avec support complet pour les connexions TCP et Serial, tout en préservant la compatibilité avec l'architecture legacy multi-nodes.

## 📋 Issue associée

- Issue #23: https://github.com/Tigro14/meshbot/issues/23

## ✅ Changements implémentés

### 1. Configuration simplifiée (config.py.sample)

**Nouveau paramètre `CONNECTION_MODE`** pour choisir le mode de connexion :
- `'serial'` : Connexion via port série USB/UART (défaut)
- `'tcp'` : Connexion réseau à un node ROUTER distant

**Nouveaux paramètres TCP** :
- `TCP_HOST` : Adresse IP du node Meshtastic
- `TCP_PORT` : Port TCP (défaut: 4403)

**Architecture legacy préservée** :
- `PROCESS_TCP_COMMANDS` : Toujours supporté pour compatibilité
- `REMOTE_NODE_HOST` / `REMOTE_NODE_NAME` : Conservés pour requêtes distantes

### 2. Modifications du code (main_bot.py)

**Imports ajoutés** :
- `meshtastic.tcp_interface`
- `OptimizedTCPInterface` (pour économie CPU)
- `SafeTCPConnection`

**Méthode `start()` améliorée** :
- Détection automatique du mode via `CONNECTION_MODE`
- Création de l'interface Serial OU TCP selon configuration
- Stabilisation adaptée (3s Serial, 5s TCP)

**Méthode `on_message()` améliorée** :
- Support single-node : tous les paquets de l'interface unique sont traités
- Mode legacy : filtrage historique préservé via `PROCESS_TCP_COMMANDS`
- Source correcte pour statistiques ('local', 'tcp', 'tigrog2')

### 3. Documentation

**README.md** :
- Diagrammes Mermaid pour les deux architectures
- Section "Choix du mode de connexion" avec avantages/inconvénients
- Instructions de configuration détaillées

**MIGRATION_GUIDE.md** :
- Guide complet de migration depuis architecture legacy
- Options de migration (Serial, TCP, ou conserver legacy)
- Tableau de comparaison des paramètres
- Section dépannage

**Fichiers d'exemple** :
- `config.serial.example` : Configuration prête pour mode Serial
- `config.tcp.example` : Configuration prête pour mode TCP avec notes

### 4. Tests

**test_single_node_config.py** (5 tests) :
- ✅ Configuration mode Serial
- ✅ Configuration mode TCP
- ✅ Configuration legacy (sans CONNECTION_MODE)
- ✅ Syntaxe fichiers d'exemple
- ✅ Imports main_bot.py

**test_single_node_logic.py** (4 tests) :
- ✅ Logique démarrage mode Serial
- ✅ Logique démarrage mode TCP
- ✅ Mode par défaut (Serial)
- ✅ Filtrage messages selon mode

**Résultat** : 9/9 tests passent ✅

## 🔧 Architecture

### Mode Single-Node Serial (nouveau)
```
Raspberry Pi 5 → /dev/ttyACM0 → Meshtastic Node → LoRa Network
```
- Connexion directe via USB/UART
- Toutes les commandes passent par Serial
- Configuration simple et stable

### Mode Single-Node TCP (nouveau)
```
Raspberry Pi 5 → WiFi/Ethernet (192.168.x.x:4403) → Meshtastic ROUTER → LoRa Network
```
- Connexion réseau au node ROUTER
- Toutes les commandes passent par TCP
- Node peut être placé à distance (meilleure position pour antenne)

### Mode Legacy Multi-Nodes (préservé)
```
Raspberry Pi 5 → /dev/ttyACM0 → Meshtastic BOT (Serial)
              ↘ WiFi/Ethernet → Meshtastic ROUTER (TCP, stats only)
```
- Deux connexions simultanées
- Commandes via Serial (+ TCP si PROCESS_TCP_COMMANDS=True)
- Compatibilité totale avec installations existantes

## 📊 Matrice de compatibilité

| Configuration | CONNECTION_MODE | Connexions actives | Commandes acceptées | Compatible |
|--------------|-----------------|-------------------|-------------------|-----------|
| **Nouveau Serial** | `'serial'` | Serial uniquement | Toutes (Serial) | ✅ |
| **Nouveau TCP** | `'tcp'` | TCP uniquement | Toutes (TCP) | ✅ |
| **Legacy défaut** | Non défini | Serial + TCP stats | Serial uniquement | ✅ |
| **Legacy hybride** | Non défini + PROCESS_TCP_COMMANDS=True | Serial + TCP | Serial + TCP | ✅ |

## 🚀 Migration pour utilisateurs

### Pour rester en Serial (recommandé pour la plupart)

Ajouter simplement en haut de `config.py` :
```python
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"  # Votre port actuel
```

### Pour migrer vers TCP

1. Configurer le node en mode ROUTER avec WiFi/Ethernet
2. Ajouter en haut de `config.py` :
```python
CONNECTION_MODE = 'tcp'
TCP_HOST = "192.168.1.38"  # IP de votre node
TCP_PORT = 4403
```

### Pour conserver l'architecture legacy

Ne rien changer ! L'ancienne configuration continue de fonctionner.

## 🔍 Points d'attention

### Robustesse TCP
- ✅ Utilise `OptimizedTCPInterface` pour économie CPU
- ✅ Stabilisation 5s pour connexions TCP
- ✅ Gestion des déconnexions via pubsub
- ⚠️ Dépend de la stabilité du réseau local

### API Compatibility
- ✅ Aucun changement breaking pour les installations existantes
- ✅ `PROCESS_TCP_COMMANDS` toujours fonctionnel
- ✅ Tous les handlers de commandes inchangés
- ✅ Interface Meshtastic standard (serial/tcp)

### Documentation
- ✅ README.md mis à jour avec diagrammes
- ✅ MIGRATION_GUIDE.md pour utilisateurs existants
- ✅ Exemples de configuration (serial/tcp)
- ✅ Paramètres documentés dans config.py.sample

## 📝 Fichiers modifiés

- `config.py.sample` : Ajout CONNECTION_MODE, TCP_HOST, TCP_PORT
- `main_bot.py` : Support TCP dans start() et on_message()
- `README.md` : Diagrammes, documentation des modes

## 📄 Fichiers ajoutés

- `config.serial.example` : Exemple configuration Serial
- `config.tcp.example` : Exemple configuration TCP
- `MIGRATION_GUIDE.md` : Guide de migration
- `test_single_node_config.py` : Tests configuration
- `test_single_node_logic.py` : Tests logique
- `PR_SUMMARY.md` : Ce document

## ✅ Checklist finale

- [x] Code implémenté et testé
- [x] Tests unitaires créés (9/9 passent)
- [x] Documentation mise à jour
- [x] Guide de migration créé
- [x] Exemples de configuration fournis
- [x] Compatibilité legacy préservée
- [x] Syntaxe Python validée
- [x] Aucun changement breaking

## 🎉 Prêt pour review et merge!
