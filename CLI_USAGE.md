# CLI Locale - Guide d'utilisation

## Vue d'ensemble

La plateforme CLI locale permet d'interagir directement avec le bot Meshtastic via ligne de commande, en parallèle de Telegram. C'est particulièrement utile pour :

- 🧪 **Développement et debug** : Tester rapidement sans dépendre de Telegram
- ⚡ **Tests locaux** : Pas de latence réseau, réponses instantanées
- 🔧 **Accès SSH** : Utiliser le bot en SSH sur le Raspberry Pi
- 💬 **Conversations AI** : Interagir avec Llama directement en local

## Activation

### 1. Configurer `config.py`

```python
# Dans config.py (ou config.py.sample)
CLI_ENABLED = True  # Activer la CLI locale

# Configuration AI pour CLI
CLI_AI_CONFIG = {
    "system_prompt": "Tu es un assistant intelligent accessible via CLI locale...",
    "max_tokens": 4000,
    "temperature": 0.8,
    "timeout": 120,
    "max_response_chars": 3000
}

# ID utilisateur CLI
CLI_USER_ID = 0xC11A0001  # ID fictif pour la CLI
```

### 2. Mapper vers une identité Mesh (optionnel)

Si vous voulez que vos messages CLI apparaissent comme venant d'un nœud Mesh spécifique :

```python
CLI_TO_MESH_MAPPING = {
    0xC11A0001: {
        "mesh_id": 0x12345678,  # Votre node ID mesh
        "mesh_name": "DevUser"   # Votre nom mesh
    }
}
```

### 3. Démarrer le bot

```bash
python main_script.py
```

La CLI démarre automatiquement si `CLI_ENABLED = True`.

## Utilisation

### Interface

Quand la CLI est active, vous verrez :

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️  CLI LOCALE ACTIVÉE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tapez vos commandes directement (ex: /help, /bot bonjour)
Tapez 'quit' ou Ctrl+C pour sortir
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

#### Commandes spéciales CLI

- `quit` ou `exit` : Quitter la CLI (le bot continue de tourner)
- `clear` : Nettoyer l'écran
- `Ctrl+C` : Interrompre la CLI
- `Ctrl+D` : EOF, quitter proprement

### Exemple de session

```bash
> /help
────────────────────────────────────────────────────────────
🤖 Bot:
📖 Commandes disponibles:
/bot <question> - Discuter avec l'IA
/nodes [page] - Liste des nœuds
/my - Vos stats
/stats - Statistiques réseau
/db - Opérations base de données
/help - Cette aide
────────────────────────────────────────────────────────────

> /bot Bonjour !
────────────────────────────────────────────────────────────
🤖 Bot:
Bonjour ! Comment puis-je t'aider aujourd'hui ? Je suis là
pour répondre à tes questions sur le réseau Meshtastic ou
tout autre sujet.
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
────────────────────────────────────────────────────────────

> quit
Sortie de la CLI (bot continue de tourner)
```

## Architecture

La CLI s'intègre dans l'architecture multi-plateforme :

```
MeshBot
  ├── PlatformManager
  │   ├── TelegramPlatform    (Messages riches via Telegram)
  │   ├── CLIPlatform         (Messages locaux via stdin/stdout)
  │   └── DiscordPlatform     (Futur)
  │
  └── MessageRouter
      └── Command Handlers
```

### Fonctionnement

1. **Thread d'input** : Lit vos commandes depuis `stdin` en boucle
2. **Simulation packet** : Crée un pseudo-packet Meshtastic
3. **Routing** : Passe par le `MessageRouter` comme tout message
4. **Réponse** : Affichée sur `stdout` avec formatage

### Avantages

- ✅ **Pas de code dupliqué** : Utilise les mêmes handlers que Mesh/Telegram
- ✅ **Test complet** : Teste toute la chaîne de traitement
- ✅ **Throttling** : Même système de limitation que les autres plateformes
- ✅ **Contexte AI** : Conversations avec historique comme Telegram
- ✅ **Logs identiques** : Même format de logs que production

## Différences avec Telegram

| Aspect | CLI | Telegram |
|--------|-----|----------|
| **Activation** | `CLI_ENABLED = True` | `TELEGRAM_ENABLED = True` |
| **Latence** | Instantané (local) | ~100-500ms (réseau) |
| **Formatage** | Texte brut | Markdown + emojis |
| **Limite** | 10000 chars | 4096 chars |
| **Auth** | Locale (Pi) | Token + user IDs |
| **Persistance** | Session uniquement | Historique Telegram |

## Debug et logs

Les interactions CLI sont loggées comme les autres plateformes :

```
[INFO] CLI→ /bot hello
[DEBUG] AI query from CLI User (0xc11a0001)
[INFO] AI response: 123 chars
```

Pour activer le debug verbeux :

```python
# config.py
DEBUG_MODE = True
```

## Limitations

- ❌ **Pas de formatage riche** : Texte brut uniquement (pas de Markdown)
- ❌ **Pas de notifications** : Pas d'alertes push
- ❌ **Session unique** : Une seule CLI active à la fois
- ❌ **Pas d'historique** : Pas de sauvegarde des conversations

## Cas d'usage

### Développement

```bash
# Tester rapidement une nouvelle commande
> /newcmd param1 param2

# Vérifier les stats en direct
> /stats global
> /db stats

# Debugger l'AI
> /bot test prompt engineering
```

### Production (SSH)

```bash
# Se connecter au Pi
ssh pi@192.168.1.100

# Interagir avec le bot
> /nodes
> /my
> /stats top 24 20
```

### Monitoring

```bash
# Script de monitoring
while true; do
    echo "/stats global" | timeout 5 nc localhost 9999
    sleep 300
done
```

## FAQ

**Q: La CLI bloque-t-elle le bot ?**
R: Non, la CLI tourne dans un thread séparé. Le bot continue de traiter les messages Mesh et Telegram normalement.

**Q: Peut-on avoir plusieurs CLI simultanées ?**
R: Non, une seule CLI à la fois. Mais vous pouvez utiliser CLI + Telegram + autres plateformes en parallèle.

**Q: Les messages CLI sont-ils envoyés sur le mesh ?**
R: Non, les commandes CLI sont traitées localement uniquement. Pour envoyer sur le mesh, utilisez `/echo` ou `/annonce`.

**Q: Comment quitter sans arrêter le bot ?**
R: Tapez `quit`, `exit`, ou `Ctrl+C`. Le bot continue de tourner en arrière-plan.

**Q: La CLI supporte-t-elle les couleurs ?**
R: Pas pour le moment, mais c'est facile à ajouter avec `colorama` ou codes ANSI.

## Roadmap

Améliorations possibles :

- [ ] Support des couleurs ANSI
- [ ] Historique des commandes (flèches ↑/↓)
- [ ] Auto-complétion (Tab)
- [ ] Envoi direct sur mesh avec `@mesh message`
- [ ] Mode interactif AI (conversation sans `/bot`)
- [ ] Formatage Markdown → ANSI
- [ ] Support readline pour édition avancée

## Voir aussi

- `CLAUDE.md` - Documentation complète du projet
- `PLATFORMS.md` - Architecture multi-plateforme
- `platform_config.py` - Configuration des plateformes
- `platforms/cli_platform.py` - Code source CLI
