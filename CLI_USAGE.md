# CLI Client - Guide d'utilisation

## Vue d'ensemble

Le MeshBot inclut maintenant un **serveur CLI TCP** qui permet de se connecter au bot via un client en ligne de commande, **sans concurrence sur les ressources série**. C'est parfait pour :

- 🧪 **Développement et debug** : Tester rapidement sans dépendre de Telegram
- ⚡ **Tests locaux** : Latence minimale, réponses rapides
- 🔧 **Accès SSH** : Utiliser le bot en SSH sur le Raspberry Pi
- 💬 **Conversations AI** : Interagir avec Llama directement
- 🔒 **Sécurité** : Connexions locales uniquement (127.0.0.1)

## Architecture

```
┌────────────────────────────────────┐
│  MeshBot (daemon)                  │
│  - Interface série /dev/ttyACM0    │
│  - Telegram                        │
│  - Serveur CLI :9999               │◄────┐
└────────────────────────────────────┘     │
                                           │ TCP Socket
┌────────────────────────────────────┐     │
│  CLI Client (séparé)               │     │
│  python cli_client.py              │─────┘
│  > /bot hello                      │
│  > /stats global                   │
└────────────────────────────────────┘
```

**Avantages** :
- ✅ Aucune concurrence sur les ressources série
- ✅ Le bot continue de tourner normalement
- ✅ Plusieurs clients peuvent se connecter (si implémenté)
- ✅ Connexion/déconnexion à volonté

## Installation

### 1. Activer le serveur CLI dans le bot

Éditer `config.py` :

```python
# ========================================
# CONFIGURATION CLI SERVEUR
# ========================================

CLI_ENABLED = True  # Activer le serveur CLI
CLI_SERVER_HOST = '127.0.0.1'  # Local only (sécurité)
CLI_SERVER_PORT = 9999  # Port d'écoute

# Configuration AI pour CLI
CLI_AI_CONFIG = {
    "system_prompt": "Tu es un assistant intelligent accessible via CLI...",
    "max_tokens": 4000,
    "temperature": 0.8,
    "timeout": 120,
    "max_response_chars": 3000
}

# ID utilisateur CLI
CLI_USER_ID = 0xC11A0001  # ID fictif pour la CLI
```

### 2. Démarrer le bot

```bash
# Démarrer le bot normalement
python main_script.py

# Ou via systemd
sudo systemctl start meshbot
```

Le serveur CLI démarre automatiquement si `CLI_ENABLED = True`.

### 3. Se connecter avec le client

```bash
# Connexion par défaut (localhost:9999)
python cli_client.py

# Connexion personnalisée
python cli_client.py --host 127.0.0.1 --port 9999
```

## Utilisation

### Interface client

Quand vous lancez `cli_client.py`, vous verrez :

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️  MeshBot CLI Client
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Connected to bot. Type commands or 'quit' to exit.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Connected to MeshBot CLI
Type /help for commands, "quit" to exit
────────────────────────────────────────────────────────────

> _
```

### Commandes disponibles

Toutes les commandes du bot sont disponibles :

#### Commandes AI
```bash
> /bot Bonjour, comment vas-tu ?
> /bot Explique-moi le réseau Meshtastic
> /bot Quelle est la météo à Paris ?
```

#### Statistiques
```bash
> /stats
> /stats global
> /stats top 24 10
> /stats channel 12
> /stats histo TEXT 24
> /stats traffic
> /stats packets
```

#### Base de données
```bash
> /db
> /db stats
> /db info
> /db clean 48
> /db vacuum
```

#### Réseau
```bash
> /nodes
> /nodes 2
> /my
> /trace NodeName
```

#### Système
```bash
> /sys
> /power
> /weather
> /help
> /legend
```

#### Commandes client spéciales

- `quit` ou `exit` : Déconnecter le client (bot continue)
- `clear` : Nettoyer l'écran
- `Ctrl+C` : Interrompre le client
- `Ctrl+D` : Quitter proprement

### Exemple de session

```bash
$ python cli_client.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️  MeshBot CLI Client
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Connected to bot. Type commands or 'quit' to exit.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Connected to MeshBot CLI
Type /help for commands, "quit" to exit
────────────────────────────────────────────────────────────

> /help

────────────────────────────────────────────────────────────
🤖 Bot:
📖 Commandes disponibles:
/bot <question> - Discuter avec l'IA
/nodes [page] - Liste des nœuds
/my - Vos statistiques
/stats [sub] - Statistiques réseau
/db [cmd] - Opérations base de données
/trace <node> - Traceroute mesh
/help - Cette aide
────────────────────────────────────────────────────────────

> /bot Salut !

────────────────────────────────────────────────────────────
🤖 Bot:
Salut ! Comment puis-je t'aider aujourd'hui ? Je suis là
pour répondre à tes questions sur le réseau Meshtastic ou
tout autre sujet qui t'intéresse.
────────────────────────────────────────────────────────────

> /stats global

────────────────────────────────────────────────────────────
🤖 Bot:
📊 Stats Réseau (24h)

Total: 1234 paquets
Nœuds: 23 actifs
Types:
  TELE: 456 (37%)
  NODE: 234 (19%)
  POS: 189 (15%)
  TEXT: 123 (10%)

Nœud le plus actif: TigroG2 (234p)
────────────────────────────────────────────────────────────

> /db stats

────────────────────────────────────────────────────────────
🤖 Bot:
🗄️ DB: 2.3MB
1234pkt 123msg
2024-11-14-2024-11-15
(24h)
────────────────────────────────────────────────────────────

> quit
👋 Disconnecting...
$
```

## Protocole de communication

Le serveur et le client communiquent en JSON sur TCP :

### Messages envoyés par le client

```
/bot hello world\n
/stats global\n
```

(Texte brut, une ligne par commande)

### Messages reçus du serveur

```json
{"type": "welcome", "message": "Connected to MeshBot CLI..."}
{"type": "response", "message": "Réponse du bot..."}
```

## Sécurité

### Connexions locales uniquement

Par défaut, le serveur écoute sur `127.0.0.1` (localhost) uniquement :

```python
CLI_SERVER_HOST = '127.0.0.1'  # PAS 0.0.0.0 !
```

**Important** : Ne JAMAIS mettre `0.0.0.0` car cela exposerait le bot sur le réseau.

### Accès SSH

Pour utiliser la CLI en SSH :

```bash
# Se connecter au Pi
ssh pi@192.168.1.100

# Lancer le client CLI
cd /home/dietpi/bot
python cli_client.py
```

### Authentification

Actuellement, pas d'authentification (connexion locale uniquement).

Pour ajouter de l'authentification, modifier `cli_server_platform.py` :

```python
def _handle_client(self, client_socket, address):
    # Demander un mot de passe
    client_socket.sendall(b"Password: ")
    password = client_socket.recv(1024).decode().strip()

    if password != EXPECTED_PASSWORD:
        client_socket.close()
        return

    # Suite du code...
```

## Diagnostic et debug

### Le serveur ne démarre pas

```bash
# Vérifier que le port est libre
netstat -tulpn | grep 9999

# Vérifier les logs du bot
journalctl -u meshbot -f | grep CLI
```

### Le client ne peut pas se connecter

```bash
# Vérifier que le bot tourne
ps aux | grep main_script

# Vérifier que le serveur est actif
netstat -tulpn | grep 9999

# Tester avec telnet
telnet 127.0.0.1 9999
```

### Debug du protocole

Activer le debug dans `config.py` :

```python
DEBUG_MODE = True
```

Vous verrez alors :

```
[DEBUG] CLI← /bot hello
[DEBUG] CLI→ Sent 123 chars to 0xc11a0001
```

## Différences avec Telegram

| Aspect | CLI | Telegram |
|--------|-----|----------|
| **Connexion** | Socket TCP local | HTTPS + polling |
| **Latence** | ~1ms (local) | ~100-500ms (réseau) |
| **Formatage** | Texte brut | Markdown + emojis |
| **Limite** | 10000 chars | 4096 chars |
| **Auth** | Locale (Pi) | Token + user IDs |
| **Persistance** | Session uniquement | Historique Telegram |
| **Multi-user** | 1 à la fois | Illimité |

## Limitations actuelles

- ❌ **Un seul client** : Une seule connexion CLI active à la fois
- ❌ **Pas de formatage** : Texte brut uniquement
- ❌ **Pas d'authentification** : Connexion locale sans password
- ❌ **Pas d'historique** : Pas de sauvegarde des conversations
- ❌ **Pas de couleurs** : Terminal noir et blanc

## Améliorations possibles

- [ ] Support multi-clients (plusieurs CLI simultanées)
- [ ] Authentification par mot de passe
- [ ] Support des couleurs ANSI
- [ ] Historique des commandes (flèches ↑/↓)
- [ ] Auto-complétion (Tab)
- [ ] Formatage Markdown → ANSI
- [ ] Support readline pour édition
- [ ] Mode TLS pour connexions distantes sécurisées

## Cas d'usage

### Développement

```bash
# Terminal 1: Bot
python main_script.py

# Terminal 2: CLI pour tests
python cli_client.py
> /bot test prompt
> /stats global
```

### Monitoring en production

```bash
# Script de monitoring
while true; do
    echo "/stats global" | nc 127.0.0.1 9999
    sleep 300
done
```

### Debug d'un problème

```bash
# SSH au Pi
ssh pi@192.168.1.100

# Connecter au bot
cd /home/dietpi/bot
python cli_client.py

# Requêtes de debug
> /db info
> /nodes
> /my
> /trace ProblematicNode
```

## FAQ

**Q: Le bot doit-il tourner pour utiliser la CLI ?**
R: Oui, la CLI est un client qui se connecte au serveur intégré au bot.

**Q: Puis-je utiliser CLI et Telegram en même temps ?**
R: Oui ! Les deux sont totalement indépendants.

**Q: Le bot ralentit-il avec la CLI ?**
R: Non, la CLI utilise un thread séparé et n'impacte pas le bot.

**Q: Puis-je me connecter depuis une autre machine ?**
R: Non par défaut (127.0.0.1). Pour permettre ça, changez `CLI_SERVER_HOST` à `0.0.0.0` et ajoutez de l'authentification.

**Q: Comment arrêter le serveur CLI ?**
R: Désactivez `CLI_ENABLED = False` et redémarrez le bot.

**Q: Où sont les logs ?**
R: Les commandes CLI sont loggées comme les autres : `journalctl -u meshbot`

## Voir aussi

- `CLAUDE.md` - Documentation complète du projet
- `PLATFORMS.md` - Architecture multi-plateforme
- `platform_config.py` - Configuration des plateformes
- `platforms/cli_server_platform.py` - Code serveur
- `cli_client.py` - Code client
