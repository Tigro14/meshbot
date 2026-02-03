# Fix: Telegram /echo TCP Connection Conflict

## Problème

Lorsque le bot est en mode TCP (`CONNECTION_MODE='tcp'`), l'utilisation de la commande `/echo` depuis Telegram provoquait une **déconnexion de l'interface TCP principale** du bot, suivie d'une reconnexion automatique avec un délai de ~18 secondes.

### Logs observés (AVANT le fix)

```
Dec 09 21:59:10 DietPi meshtastic-bot[951]: [INFO] 📱 Telegram /echo: Clickyluke -> 'La carte https://tigro.fr/map.html'
Dec 09 21:59:10 DietPi meshtastic-bot[951]: [DEBUG] 🔌 Connexion TCP à 192.168.1.38:4403
Dec 09 21:59:10 DietPi meshtastic-bot[951]: [INFO] 🔧 Initialisation OptimizedTCPInterface pour 192.168.1.38:4403
Dec 09 21:59:11 DietPi meshtastic-bot[951]: [INFO] 🔌 Socket TCP mort: détecté par moniteur
Dec 09 21:59:11 DietPi meshtastic-bot[951]: [DEBUG] 🔄 Déclenchement reconnexion via callback...
Dec 09 21:59:11 DietPi meshtastic-bot[951]: [INFO] 🔄 Reconnexion TCP #1 à 192.168.1.38:4403...
Dec 09 21:59:11 DietPi meshtastic-bot[951]: [DEBUG] ⏳ Attente nettoyage (15s) - tentative 1/3...
Dec 09 21:59:26 DietPi meshtastic-bot[951]: [DEBUG] 🔧 Création nouvelle interface TCP...
Dec 09 21:59:27 DietPi meshtastic-bot[951]: [DEBUG] ⏳ Stabilisation nouvelle interface (3s)...
```

**Impact:**
- ❌ Déconnexion inattendue de l'interface principale
- ❌ Délai de reconnexion: ~18 secondes (15s cleanup + 3s stabilisation)
- ❌ Perte de messages pendant la période de reconnexion
- ❌ Instabilité générale du bot

## Cause racine

### Architecture ESP32 - Limite de connexions TCP

L'ESP32 utilisé dans les nœuds Meshtastic a une **limite stricte d'une seule connexion TCP par client**. Ceci est une contrainte matérielle de l'ESP32.

### Séquence problématique (AVANT le fix)

1. **État initial**: Bot connecté en mode TCP permanent à `192.168.1.38:4403`
2. **Utilisateur Telegram**: Envoie `/echo Bonjour`
3. **Code /echo**: Appelle `send_text_to_remote(REMOTE_NODE_HOST, message)`
4. **SafeTCPConnection**: Crée une **SECONDE** connexion TCP vers `192.168.1.38:4403`
5. **ESP32**: Rejette la nouvelle connexion car limite = 1 connexion par client
6. **Effet secondaire**: La connexion principale du bot est **DÉCONNECTÉE**
7. **Auto-recovery**: Le bot détecte la déconnexion et lance la reconnexion
8. **Délai**: 15s de nettoyage + 3s de stabilisation = **18+ secondes**

### Diagramme du problème

```
                           AVANT LE FIX
                           ============

    Raspberry Pi                           ESP32 Node
    ============                           ==========
    
    MeshBot (main)                         192.168.1.38:4403
    └─ TCP Interface ──────────────────────┐
       (connexion permanente)              │
                                           │ [Connexion 1: OK]
                                           │
    TelegramIntegration                    │
    └─ /echo command                       │
       └─ send_text_to_remote()            │
          └─ SafeTCPConnection() ──────────┼──> [REJET!]
             (connexion temporaire)        │    ESP32 limite = 1
                                           │
                                           ▼
                                    [Connexion 1: MORTE]
                                           │
                                           │
    MeshBot détecte déconnexion            │
    └─ _reconnect_tcp_interface()          │
       ├─ Attente 15s cleanup              │
       ├─ Nouvelle interface TCP ──────────┘
       └─ Attente 3s stabilisation
```

## Solution

### Principe

**Détecter le mode de connexion** et adapter le comportement:
- **Mode TCP**: Utiliser l'interface existante du bot (pas de seconde connexion)
- **Mode serial**: Créer une connexion TCP temporaire (comportement legacy inchangé)

### Changements implémentés

#### 1. `telegram_bot/command_base.py`

Ajout de l'accès à l'interface Meshtastic dans la classe de base:

```python
class TelegramCommandBase:
    def __init__(self, telegram_integration):
        self.telegram = telegram_integration
        self.message_handler = telegram_integration.message_handler
        self.node_manager = telegram_integration.node_manager
        self.context_manager = telegram_integration.context_manager
        self.traffic_monitor = telegram_integration.message_handler.traffic_monitor
        # NEW: Provide access to the bot's interface for commands that need to send messages
        self.interface = telegram_integration.message_handler.interface
```

**Bénéfice**: Toutes les commandes Telegram ont maintenant accès direct à l'interface du bot.

#### 2. `telegram_bot/commands/mesh_commands.py`

Détection du mode et utilisation de l'interface appropriée:

```python
from config import REMOTE_NODE_HOST, CONNECTION_MODE

def send_echo():
    # ... préparation du message ...
    
    # MODE DETECTION: Avoid TCP conflicts
    connection_mode = CONNECTION_MODE.lower() if CONNECTION_MODE else 'serial'
    
    if connection_mode == 'tcp':
        # TCP MODE: Use existing bot interface (no second connection)
        debug_print(f"🔌 Mode TCP: utilisation de l'interface existante du bot")
        
        if not self.interface:
            return "❌ Interface bot non disponible"
        
        try:
            debug_print(f"📤 Envoi via interface bot: '{message}'")
            self.interface.sendText(message)
            time.sleep(2)  # Wait for message to be queued
            info_print(f"✅ Message envoyé via interface TCP principale")
            return f"✅ Echo diffusé: {message}"
        except Exception as e:
            error_print(f"❌ Erreur sendText via interface: {e}")
            return f"❌ Échec envoi: {str(e)[:50]}"
            
    else:
        # SERIAL MODE: Create temporary TCP connection (legacy behavior)
        debug_print(f"📡 Mode serial: création connexion TCP temporaire")
        
        if not REMOTE_NODE_HOST:
            return "❌ REMOTE_NODE_HOST non configuré dans config.py"
        
        success, result_msg = send_text_to_remote(
            REMOTE_NODE_HOST,
            message,
            wait_time=10
        )
        
        if success:
            return f"✅ Echo diffusé: {message}"
        else:
            return f"❌ Échec: {result_msg}"
```

#### 3. `config.py.sample`

Documentation améliorée avec warnings explicites:

```python
# Configuration monitoring nœud distant (tigrog2)
# ⚠️ IMPORTANT: Si activé, le bot crée des connexions TCP vers REMOTE_NODE_HOST
#    pour surveiller l'état du nœud distant.
#
# ⚠️ CONFLIT TCP EN MODE CONNECTION_MODE='tcp':
#    Si CONNECTION_MODE='tcp', le bot maintient déjà une connexion TCP permanente.
#    Activer TIGROG2_MONITORING_ENABLED créerait une SECONDE connexion TCP vers
#    le même nœud, violant la limite ESP32 d'une connexion TCP par client.
#
#    RECOMMANDATION:
#    - Si CONNECTION_MODE='tcp'    → TIGROG2_MONITORING_ENABLED = False (OBLIGATOIRE)
#    - Si CONNECTION_MODE='serial' → TIGROG2_MONITORING_ENABLED peut être True
#
TIGROG2_MONITORING_ENABLED = False
```

### Nouvelle architecture (APRÈS le fix)

```
                           APRÈS LE FIX
                           ============

    Raspberry Pi                           ESP32 Node
    ============                           ==========
    
    MeshBot (main)                         192.168.1.38:4403
    └─ TCP Interface ──────────────────────┐
       (connexion permanente)              │ [Connexion 1: OK]
       │                                   │
       │                                   │
    TelegramIntegration                    │
    └─ /echo command                       │
       ├─ Détecte CONNECTION_MODE='tcp'    │
       └─ Utilise self.interface ──────────┘
          (RÉUTILISE connexion existante)
          
          ✅ Pas de seconde connexion
          ✅ Pas de déconnexion
          ✅ Message envoyé immédiatement
```

## Logs attendus (APRÈS le fix)

```
Dec 09 22:00:10 DietPi meshtastic-bot[951]: [INFO] 📱 Telegram /echo: Clickyluke -> 'La carte https://tigro.fr/map.html'
Dec 09 22:00:10 DietPi meshtastic-bot[951]: [DEBUG] 🔌 Mode TCP: utilisation de l'interface existante du bot
Dec 09 22:00:10 DietPi meshtastic-bot[951]: [DEBUG] 📤 Envoi via interface bot: 'tigro: La carte https://tigro.fr/map.html'
Dec 09 22:00:10 DietPi meshtastic-bot[951]: [INFO] ✅ Message envoyé via interface TCP principale
```

**Résultat:**
- ✅ Aucune déconnexion
- ✅ Envoi instantané (< 2 secondes)
- ✅ Aucune perte de messages
- ✅ Stabilité maintenue

## Tests

### Test suite: `test_echo_tcp_fix.py`

```bash
$ python3 test_echo_tcp_fix.py

======================================================================
TEST: Fix /echo TCP Connection Conflict
======================================================================

test_echo_uses_existing_interface_in_tcp_mode ... ✅ Test 1: Interface accessible via command base
ok
test_echo_tcp_mode_does_not_call_send_text_to_remote ... ✅ Test 2: Mode TCP utilise interface.sendText()
ok
test_echo_serial_mode_logic ... ✅ Test 3: Mode serial détecté correctement
ok

----------------------------------------------------------------------
Ran 3 tests in 0.007s

OK - ✅ TOUS LES TESTS PASSÉS
```

### Tests couverts

1. **Interface accessible**: Vérifie que `self.interface` est disponible dans les commandes
2. **Mode TCP**: Vérifie que l'interface existante est utilisée en mode TCP
3. **Mode serial**: Vérifie que le mode serial est correctement détecté

## Compatibilité

### Mode SERIAL (historique)

```python
# config.py
CONNECTION_MODE = 'serial'
REMOTE_NODE_HOST = '192.168.1.38'
```

**Comportement**: `/echo` crée une connexion TCP temporaire (INCHANGÉ)
- ✅ Pas de régression
- ✅ Comportement identique à avant le fix

### Mode TCP (avec le fix)

```python
# config.py
CONNECTION_MODE = 'tcp'
TCP_HOST = '192.168.1.38'
TCP_PORT = 4403
```

**Comportement**: `/echo` utilise l'interface existante (NOUVEAU)
- ✅ Plus de conflit TCP
- ✅ Plus de déconnexions
- ✅ Stabilité accrue

## Démonstration

```bash
$ python3 demo_echo_tcp_fix.py
```

Script de démonstration interactif montrant:
- Comportement AVANT le fix (conflit TCP)
- Comportement APRÈS le fix (interface partagée)
- Changements de code détaillés
- Comparaison des logs
- Résultats des tests

## Bénéfices

| Aspect | Avant | Après |
|--------|-------|-------|
| Déconnexions TCP | ❌ Systématiques | ✅ Aucune |
| Délai /echo | ❌ 18+ secondes | ✅ < 2 secondes |
| Perte de messages | ❌ Oui (18s) | ✅ Non |
| Stabilité | ❌ Instable | ✅ Stable |
| Compatibilité serial | ✅ OK | ✅ OK (inchangé) |

## Fichiers modifiés

1. `telegram_bot/command_base.py` - Ajout interface dans base class
2. `telegram_bot/commands/mesh_commands.py` - Détection mode et utilisation interface
3. `config.py.sample` - Documentation TCP conflicts
4. `test_echo_tcp_fix.py` - Tests unitaires (nouveau)
5. `demo_echo_tcp_fix.py` - Démonstration interactive (nouveau)

## Notes importantes

### ESP32 TCP Limits

L'ESP32 a une limite stricte:
- **1 connexion TCP par client** (contrainte matérielle)
- Tentative de seconde connexion → rejet + déconnexion de la première
- Pas de workaround possible côté ESP32

### Autres sources de conflits potentiels

**TIGROG2_MONITORING_ENABLED**: Si activé en mode TCP, créerait aussi des conflits
- Solution: Ajouter warning dans config.py.sample
- Recommandation: `TIGROG2_MONITORING_ENABLED = False` en mode TCP

### Future improvements

Si d'autres commandes Telegram nécessitent l'envoi de messages sur le mesh:
1. Utiliser `self.interface` (déjà disponible via command base)
2. Ne PAS créer de `SafeTCPConnection` en mode TCP
3. Vérifier `CONNECTION_MODE` si nécessaire

## Références

- Issue: Telegram /echo provoque déconnexion TCP
- PR: copilot/fix-telegram-echo-disconnect
- Commit: Fix: /echo command TCP connection conflict in TCP mode
- Tests: test_echo_tcp_fix.py (3/3 passed)
- Demo: demo_echo_tcp_fix.py
