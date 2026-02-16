# Plan de Consolidation des Commandes de Statistiques

## 🎯 Objectif

Consolider les multiples commandes de statistiques dispersées et les rendre accessibles sur **Mesh ET Telegram/Internet**.

## 📊 État Actuel (Problèmes)

### Commandes Existantes

| Commande | Mesh | Telegram | Business Logic | Problème |
|----------|------|----------|----------------|----------|
| `/stats` | ❌ | ✅ | ❌ | Seulement Telegram |
| `/top` | ✅ | ✅ | ✅ | Doublons, params différents |
| `/packets` | ✅ | ✅ | ✅ | Doublons |
| `/histo` | ✅ | ✅ | ✅ | Doublons |
| `/channel_stats` | ❌ | ❌ | ✅ | Pas accessible directement |
| `/trafic` | ❌ | ✅ | ❌ | Seulement Telegram |

### Problèmes Identifiés

1. **Duplication** : Certaines commandes existent en double (Mesh + Telegram)
2. **Incohérence** : Paramètres et comportements différents entre Mesh et Telegram
3. **Manque d'accessibilité** : Certaines stats (channel, global) pas facilement accessibles
4. **Confusion** : Trop de commandes différentes pour des stats similaires
5. **Business Logic** : Pas toujours réutilisée (duplication de code)

## 🔧 Solution Proposée

### Architecture Unifiée

```
┌─────────────────────────────────────────┐
│     Commande /stats Unifiée             │
│                                         │
│  /stats [sous-commande] [paramètres]   │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
   ┌───▼────┐     ┌────▼─────┐
   │  Mesh  │     │ Telegram │
   └────────┘     └──────────┘
       │                │
       └───────┬────────┘
               │
        ┌──────▼──────┐
        │   Business  │
        │    Logic    │
        │ StatsCommands│
        └─────────────┘
```

### Nouvelle Commande `/stats` Unifiée

```bash
# Statistiques globales (vue d'ensemble)
/stats                    # Équivalent à /stats global

# Sous-commandes spécifiques
/stats global            # Statistiques réseau globales
/stats top [hours] [n]   # Top talkers
/stats packets [hours]   # Distribution types de paquets
/stats channel [hours]   # Utilisation du canal (channel_stats)
/stats histo [type] [h]  # Histogramme par type
/stats traffic [hours]   # Historique messages publics
```

### Compatibilité Ascendante (Aliases)

Les anciennes commandes restent fonctionnelles comme **aliases** :

```bash
/top [hours]        → /stats top [hours]
/packets [hours]    → /stats packets [hours]
/histo [type] [h]   → /stats histo [type] [h]
/trafic [hours]     → /stats traffic [hours] (Telegram)
```

## 📋 Détails des Sous-Commandes

### 1. `/stats global` (par défaut)

**Affiche** : Vue d'ensemble du réseau
- Nombre de messages (1h, 24h, total)
- Nœuds actifs (1h, 24h, total)
- Heures de pointe/creuse
- Top 3 récents
- Uptime du monitoring

**Disponible** : ✅ Mesh + ✅ Telegram

**Exemple** :
```
📊 STATS RÉSEAU (24h)
Messages: 156
Nœuds actifs: 12
🏆 Top 3:
  1. tigrog2: 45
  2. meshbot: 23
  3. alice: 18
```

### 2. `/stats top [hours] [nombre]`

**Affiche** : Top talkers avec tous les types de paquets
- Classement par volume total
- Répartition par type de paquet
- Pourcentages

**Paramètres** :
- `hours` : Période (défaut: 24h Telegram, 3h Mesh)
- `nombre` : Nombre de nodes (défaut: 10)

**Disponible** : ✅ Mesh + ✅ Telegram

**Exemple** :
```
🏆 TOP TALKERS (24h)
1. tigrog2: 156 paquets
   📍45 🔔30 💬25 📊20
2. meshbot: 89 paquets
   📍30 💬25 📊15
```

### 3. `/stats packets [hours]`

**Affiche** : Distribution des types de paquets
- Comptage par type
- Pourcentages
- Histogramme ASCII

**Paramètres** :
- `hours` : Période (défaut: 1h Mesh, 24h Telegram)

**Disponible** : ✅ Mesh + ✅ Telegram

**Exemple** :
```
📦 TYPES DE PAQUETS (24h)
POSITION_APP: 450 (45%)
NODEINFO_APP: 300 (30%)
TEXT_MESSAGE: 150 (15%)
TELEMETRY_APP: 100 (10%)
```

### 4. `/stats channel [hours]`

**Affiche** : Utilisation du canal par nœud
- % utilisation canal (Channel Utilization)
- % utilisation air TX (Air Utilization TX)
- Alertes si >15%

**Paramètres** :
- `hours` : Période (défaut: 24h)

**Disponible** : ✅ Mesh + ✅ Telegram

**Exemple** :
```
📡 UTILISATION CANAL (24h)
1. 🔴 tigrog2: 22.5%
   ⚠️ Critique! Réduire fréquence
2. 🟢 meshbot: 8.2%
3. 🟢 alice: 5.1%

Moyenne réseau: 11.9%
```

### 5. `/stats histo [type] [hours]`

**Affiche** : Histogramme temporel des paquets
- Répartition heure par heure
- Visualisation ASCII
- Par type de paquet optionnel

**Paramètres** :
- `type` : Type de paquet (pos, text, node, tele) - optionnel
- `hours` : Période (défaut: 12h)

**Disponible** : ✅ Mesh + ✅ Telegram

**Exemple** :
```
📊 HISTOGRAMME POSITION (12h)
10h: ████████ 32
11h: ██████ 24
12h: ██████████ 40
13h: ████ 16
```

### 6. `/stats traffic [hours]`

**Affiche** : Historique des messages publics
- Liste chronologique
- Contenu des messages
- Émetteur + timestamp

**Paramètres** :
- `hours` : Période (défaut: 8h)

**Disponible** : ❌ Mesh (trop long) + ✅ Telegram

**Exemple** :
```
💬 MESSAGES PUBLICS (8h)
13:45 alice: Bonjour le réseau
13:50 bob: Salut! Signal?
14:00 charlie: -85dBm SNR 8
```

## 🏗️ Implémentation

### 1. Refactoring de la Business Logic

Créer une classe `UnifiedStatsCommands` qui centralise toute la logique :

```python
# handlers/command_handlers/unified_stats.py
class UnifiedStatsCommands:
    def __init__(self, traffic_monitor, node_manager):
        self.traffic_monitor = traffic_monitor
        self.node_manager = node_manager

    def get_stats(self, subcommand='global', **kwargs):
        """Point d'entrée unifié pour toutes les stats"""
        if subcommand == 'global':
            return self.get_global_stats(**kwargs)
        elif subcommand == 'top':
            return self.get_top_talkers(**kwargs)
        elif subcommand == 'packets':
            return self.get_packet_summary(**kwargs)
        elif subcommand == 'channel':
            return self.get_channel_stats(**kwargs)
        elif subcommand == 'histo':
            return self.get_histogram(**kwargs)
        elif subcommand == 'traffic':
            return self.get_traffic_history(**kwargs)
        else:
            return self.get_help()
```

### 2. Handlers Mesh

```python
# handlers/command_handlers/stats_commands.py (refactorisé)
def handle_stats(self, sender_id, sender_info, args):
    """
    Gérer /stats [subcommand] [params]
    """
    # Parser les arguments
    parts = args.split() if args else []
    subcommand = parts[0] if parts else 'global'
    params = parts[1:] if len(parts) > 1 else []

    # Appeler la business logic unifiée
    result = self.unified_stats.get_stats(
        subcommand=subcommand,
        params=params,
        channel='mesh'  # Adaptation automatique pour LoRa
    )

    self.sender.send_chunks(result, sender_id, sender_info)
```

### 3. Handlers Telegram

```python
# telegram_bot/commands/stats_commands.py (refactorisé)
async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gérer /stats [subcommand] [params]
    """
    # Parser les arguments
    args = context.args or []
    subcommand = args[0] if args else 'global'
    params = args[1:] if len(args) > 1 else []

    # Appeler la business logic unifiée
    response = await asyncio.to_thread(
        self.unified_stats.get_stats,
        subcommand=subcommand,
        params=params,
        channel='telegram'  # Adaptation pour Telegram (plus long)
    )

    await update.message.reply_text(response, parse_mode='Markdown')
```

### 4. Adaptation Automatique

La business logic s'adapte automatiquement au canal :

```python
def get_stats(self, subcommand, params, channel):
    # Limites adaptées au canal
    if channel == 'mesh':
        max_length = 180  # LoRa constraint
        default_hours = 3  # Court pour Mesh
        top_n = 5  # Top 5
    else:  # telegram
        max_length = 3000
        default_hours = 24
        top_n = 10

    # Générer le rapport adapté
    ...
```

## 📅 Plan de Migration

### Phase 1 : Préparation (1-2h)
1. ✅ Analyser les commandes existantes
2. ✅ Créer le plan de consolidation
3. ⬜ Créer `UnifiedStatsCommands` avec toute la business logic
4. ⬜ Tests unitaires de la business logic

### Phase 2 : Implémentation Mesh (1h)
1. ⬜ Refactoriser `stats_commands.py` (handlers)
2. ⬜ Ajouter `/stats` avec sous-commandes
3. ⬜ Maintenir aliases (`/top`, `/packets`, `/histo`)
4. ⬜ Tests manuels sur Mesh

### Phase 3 : Implémentation Telegram (1h)
1. ⬜ Refactoriser `stats_commands.py` (telegram_bot)
2. ⬜ Unifier avec la même business logic
3. ⬜ Tester toutes les sous-commandes
4. ⬜ Vérifier les alias

### Phase 4 : Documentation & Tests (30min)
1. ⬜ Mettre à jour `/help` avec nouvelle syntaxe
2. ⬜ Documenter dans CLAUDE.md
3. ⬜ Tests complets Mesh + Telegram
4. ⬜ Commit et push

## 🎨 Exemple d'Utilisation

### Sur Mesh (LoRa)

```bash
# Vue rapide
/stats
→ "📊 STATS(24h) 45msg 8nodes 🏆tigrog2:12"

# Top détaillé
/stats top 3
→ "🏆TOP(3h) 1.tigrog2:23 📍15💬8"

# Canal
/stats channel
→ "📡CANAL: tigrog2🔴22% alice🟢8%"
```

### Sur Telegram

```bash
# Vue complète
/stats
→ Rapport détaillé multi-lignes avec markdown

# Top avec graphique
/stats top 24 20
→ Top 20 sur 24h avec émojis et pourcentages

# Historique messages
/stats traffic 12
→ Liste des 50 derniers messages sur 12h
```

## ✅ Avantages

1. **Simplicité** : Une seule commande `/stats` au lieu de 5-6
2. **Cohérence** : Même syntaxe sur Mesh et Telegram
3. **Maintenabilité** : Business logic centralisée
4. **Extensibilité** : Facile d'ajouter de nouvelles sous-commandes
5. **Compatibilité** : Les anciennes commandes fonctionnent toujours (aliases)
6. **Adaptation** : Réponses automatiquement adaptées au canal (court pour LoRa, long pour Telegram)

## 🚀 Commencer

Validation du plan :
- ✅ Approuvé
- ⬜ À modifier (commentaires)

Une fois validé, je procède à l'implémentation !

---

**Auteur** : Claude (AI Assistant)
**Date** : 2025-11-15
**Version** : 1.0
