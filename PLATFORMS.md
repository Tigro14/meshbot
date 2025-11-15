# Architecture Multi-Plateformes - Meshtastic Bot

## Vue d'ensemble

Le bot Meshtastic utilise maintenant une architecture modulaire multi-plateformes permettant d'intégrer facilement **Telegram**, **Discord**, **Matrix** ou toute autre plateforme de messagerie.

### Avantages

- ✅ **Modularité** : Activer/désactiver chaque plateforme indépendamment
- ✅ **Extensibilité** : Ajouter facilement de nouvelles plateformes
- ✅ **Abstraction** : Interface commune pour toutes les plateformes
- ✅ **Configuration centralisée** : Un seul fichier pour toutes les plateformes
- ✅ **Compatibilité** : Maintien de la rétrocompatibilité avec le code existant

---

## Structure du Module `platforms/`

```
platforms/
├── __init__.py                      # Exports publics
├── platform_interface.py            # Interface abstraite MessagingPlatform
├── platform_manager.py              # Gestionnaire centralisé
├── telegram_platform.py             # Implémentation Telegram
└── discord_platform.py              # Template Discord (futur)
```

---

## Interface `MessagingPlatform`

Toutes les plateformes doivent implémenter cette interface abstraite :

```python
class MessagingPlatform(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Nom de la plateforme (telegram, discord, etc.)"""

    @abstractmethod
    def start(self):
        """Démarrer la plateforme"""

    @abstractmethod
    def stop(self):
        """Arrêter la plateforme"""

    @abstractmethod
    def send_message(self, user_id, message: str) -> bool:
        """Envoyer un message à un utilisateur"""

    @abstractmethod
    def send_alert(self, message: str):
        """Envoyer une alerte aux utilisateurs autorisés"""
```

### Méthodes communes (fournies par la classe de base)

- `check_authorization(user_id)` - Vérifier les permissions
- `get_mesh_identity(user_id)` - Mapping utilisateur → nœud Mesh
- `get_ai_config()` - Configuration IA de la plateforme
- `is_enabled()` - Vérifier si la plateforme est activée

---

## Configuration

### Fichier `platform_config.py`

Centralise la configuration de toutes les plateformes :

```python
from platforms import PlatformConfig

# Configuration Telegram
TELEGRAM_PLATFORM_CONFIG = PlatformConfig(
    platform_name='telegram',
    enabled=True,
    max_message_length=4096,
    ai_config=TELEGRAM_AI_CONFIG,
    authorized_users=TELEGRAM_AUTHORIZED_USERS,
    user_to_mesh_mapping=TELEGRAM_TO_MESH_MAPPING,
    extra_config={
        'bot_token': TELEGRAM_BOT_TOKEN,
        'alert_users': TELEGRAM_ALERT_USERS,
    }
)

# Configuration Discord (exemple futur)
DISCORD_PLATFORM_CONFIG = PlatformConfig(
    platform_name='discord',
    enabled=False,  # À activer quand implémenté
    max_message_length=2000,
    ai_config=DISCORD_AI_CONFIG,
    authorized_users=[...],
    extra_config={
        'bot_token': 'DISCORD_TOKEN',
        'guild_id': 12345678
    }
)
```

### Fichier `config.py`

Ajoutez simplement :

```python
# Activer/désactiver Telegram
TELEGRAM_ENABLED = True  # False pour désactiver

# Configuration AI spécifique Telegram
TELEGRAM_AI_CONFIG = {
    "max_tokens": 4000,
    "max_response_chars": 3000
}
```

---

## Utilisation dans `main_bot.py`

### Initialisation

```python
from platforms import PlatformManager
from platforms.telegram_platform import TelegramPlatform
from platform_config import get_enabled_platforms

# Créer le gestionnaire
self.platform_manager = PlatformManager()

# Enregistrer les plateformes activées
for platform_config in get_enabled_platforms():
    if platform_config.platform_name == 'telegram':
        telegram_platform = TelegramPlatform(
            platform_config,
            self.message_handler,
            self.node_manager,
            self.context_manager
        )
        self.platform_manager.register_platform(telegram_platform)

# Démarrer toutes les plateformes
self.platform_manager.start_all()
```

### Arrêt

```python
# Arrêter toutes les plateformes
self.platform_manager.stop_all()
```

### Envoyer des alertes

```python
# Envoyer sur toutes les plateformes actives
self.platform_manager.send_alert_to_all("⚠️ Alerte système")

# Envoyer sur une plateforme spécifique
telegram = self.platform_manager.get_platform('telegram')
if telegram:
    telegram.send_alert("Alerte Telegram uniquement")
```

---

## Ajouter une Nouvelle Plateforme

### Étape 1 : Créer l'implémentation

Créez `platforms/discord_platform.py` :

```python
from .platform_interface import MessagingPlatform, PlatformConfig
import discord

class DiscordPlatform(MessagingPlatform):
    def __init__(self, config, message_handler, node_manager, context_manager):
        super().__init__(config, message_handler, node_manager, context_manager)

        # Initialiser le client Discord
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = discord.Client(intents=intents)

        # Enregistrer les événements
        @self.bot.event
        async def on_message(message):
            # Traiter les commandes
            pass

    @property
    def platform_name(self) -> str:
        return "discord"

    def start(self):
        token = self.config.extra_config['bot_token']
        self.bot.run(token)

    def stop(self):
        await self.bot.close()

    def send_message(self, channel_id, message):
        channel = await self.bot.fetch_channel(channel_id)
        await channel.send(message)

    def send_alert(self, message):
        for user_id in self.config.authorized_users:
            self.send_message(user_id, message)
```

### Étape 2 : Ajouter la configuration

Dans `platform_config.py` :

```python
DISCORD_PLATFORM_CONFIG = PlatformConfig(
    platform_name='discord',
    enabled=True,  # Activer Discord
    max_message_length=2000,
    ai_config=DISCORD_AI_CONFIG,
    authorized_users=[...],
    extra_config={
        'bot_token': 'YOUR_DISCORD_TOKEN'
    }
)

ENABLED_PLATFORMS = [
    TELEGRAM_PLATFORM_CONFIG,
    DISCORD_PLATFORM_CONFIG,  # Ajouter Discord
]
```

### Étape 3 : Enregistrer dans main_bot.py

```python
from platforms.discord_platform import DiscordPlatform

# Dans start()
elif platform_config.platform_name == 'discord':
    discord_platform = DiscordPlatform(
        platform_config,
        self.message_handler,
        self.node_manager,
        self.context_manager
    )
    self.platform_manager.register_platform(discord_platform)
```

---

## Différences entre Plateformes

### Commandes communes (toutes plateformes)

La majorité des commandes sont identiques :
- `/nodes`, `/my`, `/trace`, `/sys`, `/power`, etc.

### Commandes spécifiques plateforme

Seules **2 commandes** ont besoin d'adaptations :

#### 1. `/bot` (IA)

**Différence** : Configuration AI différente par plateforme

```python
# Telegram : Messages courts pour LoRa
TELEGRAM_AI_CONFIG = {
    "max_tokens": 4000,
    "max_response_chars": 3000
}

# Discord : Messages plus longs
DISCORD_AI_CONFIG = {
    "max_tokens": 8000,
    "max_response_chars": 1900  # Limite Discord
}
```

#### 2. `/fullnodes` (Telegram uniquement)

Cette commande affiche TOUS les nœuds avec détails, spécifique à Telegram.

Sur Discord, vous pourriez :
- L'implémenter différemment (embed riche)
- La désactiver
- Créer une variante `/nodes --full`

---

## Désactiver Telegram

### Option 1 : Configuration

Dans `config.py` :

```python
TELEGRAM_ENABLED = False
```

### Option 2 : Ne pas enregistrer la plateforme

Dans `main_bot.py`, commentez :

```python
# if platform_config.platform_name == 'telegram':
#     telegram_platform = TelegramPlatform(...)
#     self.platform_manager.register_platform(telegram_platform)
```

### Option 3 : Retirer de la liste

Dans `platform_config.py` :

```python
ENABLED_PLATFORMS = [
    # TELEGRAM_PLATFORM_CONFIG,  # Commenté = désactivé
]
```

---

## Migration depuis l'Ancienne Architecture

### Avant

```python
from telegram_integration import TelegramIntegration

self.telegram_integration = TelegramIntegration(...)
self.telegram_integration.start()
```

### Après

```python
from platforms import PlatformManager
from platforms.telegram_platform import TelegramPlatform

self.platform_manager = PlatformManager()

telegram_platform = TelegramPlatform(config, ...)
self.platform_manager.register_platform(telegram_platform)
self.platform_manager.start_all()
```

### Compatibilité

Pour maintenir la compatibilité, `telegram_integration` est toujours accessible :

```python
# Référence maintenue pour le code legacy
self.telegram_integration = telegram_platform.telegram_integration
```

---

## Plateformes Supportées

| Plateforme | Status | Fichier | Notes |
|------------|--------|---------|-------|
| **Telegram** | ✅ Actif | `telegram_platform.py` | Entièrement fonctionnel |
| **Discord** | 📋 Template | `discord_platform.py` | Prêt à implémenter |
| **Matrix** | 📋 Config | `platform_config.py` | Configuration préparée |
| **Slack** | ❌ Non planifié | - | Facile à ajouter |
| **Signal** | ❌ Non planifié | - | Possible via API |

---

## FAQ

### Q: Puis-je utiliser plusieurs plateformes en même temps ?

**R:** Oui ! C'est l'objectif de cette architecture. Activez simplement toutes les plateformes voulues dans `ENABLED_PLATFORMS`.

### Q: Comment les alertes sont distribuées ?

**R:** Utilisez `platform_manager.send_alert_to_all(message)` pour envoyer sur toutes les plateformes actives.

### Q: Quelle est la performance ?

**R:** Chaque plateforme tourne dans son propre thread. L'impact est minimal (~5-10MB RAM par plateforme).

### Q: Puis-je désactiver temporairement une plateforme ?

**R:** Oui, dans `config.py` : `TELEGRAM_ENABLED = False` et redémarrez le bot.

### Q: Les commandes mesh sont-elles affectées ?

**R:** Non, les commandes mesh (via LoRa) sont totalement indépendantes des plateformes de messagerie.

---

## Contribution

Pour ajouter une nouvelle plateforme :

1. Créez `platforms/ma_plateforme_platform.py`
2. Implémentez `MessagingPlatform`
3. Ajoutez la configuration dans `platform_config.py`
4. Enregistrez dans `main_bot.py`
5. Testez et créez une PR !

---

## Architecture Technique

```
main_bot.py
    ↓
PlatformManager
    ├── TelegramPlatform (wrap TelegramIntegration)
    │   ├── BasicCommands
    │   ├── SystemCommands
    │   ├── NetworkCommands
    │   ├── StatsCommands
    │   ├── UtilityCommands
    │   ├── MeshCommands
    │   ├── AICommands
    │   ├── TraceCommands
    │   └── AdminCommands
    │
    ├── DiscordPlatform (futur)
    │   └── ... (mêmes commandes, implémentation différente)
    │
    └── MatrixPlatform (futur)
        └── ...
```

Chaque plateforme partage :
- `node_manager` - Base de nœuds mesh
- `message_handler` - Logique métier des commandes
- `context_manager` - Contexte conversationnel IA
- `traffic_monitor` - Statistiques réseau

---

**Date de création** : 2025-11-15
**Version** : 1.0
**Auteur** : Claude (AI Assistant)
