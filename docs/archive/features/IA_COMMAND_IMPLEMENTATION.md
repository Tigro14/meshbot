# Commande /ia - Guide d'implémentation

## Vue d'ensemble

La commande `/ia` est un **alias français** de la commande `/bot` pour les interactions avec l'intelligence artificielle. Elle fonctionne de manière identique à `/bot` et est disponible dans tous les modes, y compris le **mode companion** (MeshCore sans Meshtastic).

## Fonctionnalité

### Utilisation

```bash
# Via Meshtastic (mesh)
/ia Quelle est la météo ?
/ia Raconte-moi une blague
/ia Bonjour, comment vas-tu ?

# Via Telegram
/ia Explique-moi le réseau mesh
/ia Quelle heure est-il ?

# Mode broadcast (public)
/ia @tous Bonjour le réseau !
```

### Équivalence avec /bot

Les deux commandes sont **strictement équivalentes** :

| Commande | Alias | Description |
|----------|-------|-------------|
| `/bot <question>` | Anglais | Conversation avec l'IA |
| `/ia <question>` | Français | Conversation avec l'IA |

## Architecture

### 1. Message Router (`handlers/message_router.py`)

#### Mode companion
```python
self.companion_commands = [
    '/bot',      # AI
    '/ia',       # AI (alias français)
    '/weather',
    # ...
]
```

#### Mode broadcast
```python
broadcast_commands = ['/echo', '/my', '/weather', '/rain', '/bot', '/ia', '/info', '/propag', '/hop']

if message.startswith('/ia'):
    info_print(f"IA PUBLIC de {sender_info}: '{message}'")
    self.ai_handler.handle_bot(message, sender_id, sender_info, is_broadcast=True)
```

#### Mode direct
```python
elif message.startswith('/ia'):
    self.ai_handler.handle_bot(message, sender_id, sender_info)
```

### 2. AI Handler (`handlers/command_handlers/ai_commands.py`)

```python
def handle_bot(self, message, sender_id, sender_info, is_broadcast=False):
    """
    Gérer la commande /bot ou /ia (alias français)
    """
    # Détecter la commande utilisée (/bot ou /ia)
    if message.startswith('/ia'):
        prompt = message[3:].strip()  # Longueur de "/ia"
        command_name = "/ia"
    else:  # /bot
        prompt = message[4:].strip()  # Longueur de "/bot"
        command_name = "/bot"
    
    # Traitement identique pour les deux commandes
    response = self.llama_client.query_llama_mesh(prompt, sender_id)
    # ...
```

### 3. Telegram Integration

#### telegram_integration.py
```python
self.application.add_handler(CommandHandler("ia", self.ai_commands.ia_command))
```

#### telegram_bot/commands/ai_commands.py
```python
async def ia_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /ia <question> - Alias français de /bot"""
    question = ' '.join(context.args)
    response = await asyncio.to_thread(query_ai)
    await update.effective_message.reply_text(response)
```

## Exemples d'utilisation

### 1. Mode companion (MeshCore)

```python
# Configuration
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True

# Message reçu via MeshCore
DM:12345678:/ia Bonjour

# Bot répond
📬 [MESHCORE-DM] De: 0x12345678 | Message: /ia Bonjour
📤 [MESHCORE-DM] Envoyé à 0x12345678: Bonjour ! Comment puis-je vous aider ?
```

### 2. Mode Meshtastic broadcast

```python
# Message broadcast sur le mesh
/ia @tous Quelle heure est-il ?

# Bot répond en broadcast
📡 Broadcast /ia via interface partagée...
Il est actuellement 14h30.
```

### 3. Mode Telegram

```python
# Utilisateur envoie
/ia Explique le protocole LoRa

# Bot répond (réponse détaillée, pas de limite 180 chars)
LoRa (Long Range) est un protocole de communication sans fil...
[réponse longue jusqu'à 3000 caractères]
```

## Tests

### Suite de tests complète (`test_ia_command.py`)

```bash
$ python3 test_ia_command.py -v

test_ia_command_in_broadcast_commands ... ok
test_ia_command_in_companion_commands ... ok
test_ia_command_prompt_extraction ... ok
test_ia_vs_bot_same_behavior ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.010s
OK
```

### Test 1: /ia dans companion_commands
```python
def test_ia_command_in_companion_commands(self):
    router = MessageRouter(..., companion_mode=True)
    self.assertIn('/ia', router.companion_commands)
```

### Test 2: /ia déclenche broadcast
```python
def test_ia_command_in_broadcast_commands(self):
    packet = {'from': 0x87654321, 'to': 0xFFFFFFFF}
    message = "/ia Bonjour"
    router.process_text_message(packet, decoded, message)
    # Vérifie que handle_bot est appelé avec is_broadcast=True
```

### Test 3: Extraction du prompt
```python
def test_ia_command_prompt_extraction(self):
    message = "/ia Quelle est la météo?"
    ai_handler.handle_bot(message, 0x12345678, "TestNode")
    # Vérifie que le prompt est "Quelle est la météo?"
```

### Test 4: Équivalence /ia et /bot
```python
def test_ia_vs_bot_same_behavior(self):
    message_ia = "/ia Test question"
    message_bot = "/bot Test question"
    # Vérifie que les deux produisent le même prompt
    self.assertEqual(ia_prompt, bot_prompt)
```

## Différences avec /bot

**Aucune différence fonctionnelle !** Les deux commandes :
- Utilisent le même handler `handle_bot()`
- Appellent `query_llama_mesh()` ou `query_llama_telegram()`
- Maintiennent le même contexte conversationnel
- Respectent les mêmes limites (180 chars mesh, 3000 chars Telegram)
- Sont disponibles en mode companion
- Supportent le mode broadcast

**Seule différence** : Le nom de la commande (3 caractères vs 4 caractères)

## Aide utilisateur

### Aide compacte (mesh)
```
/bot IA
/ia IA
/help
```

### Aide détaillée (Telegram)
```
🤖 CHAT IA
• /bot <question> → Conversation avec l'IA
• /ia <question> → Alias français de /bot
• Contexte conversationnel maintenu 30min
• Réponses plus détaillées possibles sur Telegram vs mesh
```

## Configuration

Aucune configuration supplémentaire nécessaire ! `/ia` fonctionne automatiquement dès que l'IA est activée :

```python
# config.py
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080

MESH_AI_CONFIG = {
    "system_prompt": "...",
    "max_tokens": 1500,
    "max_response_chars": 320
}

TELEGRAM_AI_CONFIG = {
    "max_tokens": 4000,
    "max_response_chars": 3000
}
```

## Logs

### Exemple de logs avec /ia

```
[INFO] IA PUBLIC de tigro: '/ia Quelle heure est-il ?'
[INFO] Bot: tigro: 'Quelle heure est-il ?' (broadcast=True, command=/ia)
[INFO] 📡 Broadcast /ia via interface partagée...
[INFO] ✅ Broadcast /ia envoyé avec succès
```

### Comparaison /ia vs /bot

```bash
# /ia
[INFO] Bot: tigro: 'Hello' (broadcast=False, command=/ia)

# /bot
[INFO] Bot: tigro: 'Hello' (broadcast=False, command=/bot)

# Logs identiques sauf le nom de la commande
```

## Bénéfices

1. **Accessibilité** : Commande en français plus naturelle pour les utilisateurs francophones
2. **Compatibilité** : Fonctionne dans tous les modes (Meshtastic, companion, Telegram)
3. **Simplicité** : Pas de configuration supplémentaire
4. **Maintenance** : Code partagé avec `/bot`, pas de duplication
5. **Tests** : Suite de tests complète garantit la fiabilité

## Cas d'usage

### Utilisateur francophone sur mesh
```
Tigro > /ia Bonjour, comment vas-tu ?
Bot   > Bonjour ! Je vais bien, merci. Comment puis-je vous aider ?
```

### Groupe Telegram français
```
User1: /ia Quelle est la température du raspberry ?
Bot  : La température actuelle du CPU est de 45.2°C.
       La température ambiante (BME280) est de 22.3°C.
```

### Mode companion sans Meshtastic
```
MeshCore > DM:12345678:/ia Explique le mode companion
Bot      > Le mode companion permet d'utiliser le bot avec MeshCore...
```

## Résolution de problèmes

### /ia ne fonctionne pas

1. Vérifier que l'IA est activée :
   ```bash
   curl http://localhost:8080/health
   ```

2. Vérifier les logs :
   ```bash
   journalctl -u meshbot -f | grep "IA PUBLIC"
   ```

3. Tester avec /bot :
   ```bash
   /bot Test
   # Si /bot fonctionne, /ia devrait fonctionner aussi
   ```

### Prompt mal extrait

Si le prompt semble tronqué, vérifier dans les logs :
```
[INFO] Bot: user: 'prompt_extrait' (broadcast=False, command=/ia)
```

Le prompt devrait être la question sans `/ia ` au début.

## Références

- Issue originale : "Commande /ia désactivée en mode companion"
- PR : #[à compléter]
- Tests : `test_ia_command.py`
- Documentation companion : `MESHCORE_COMPANION.md`
