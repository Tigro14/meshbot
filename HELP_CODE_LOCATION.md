# Quick Reference: /help Code Location

## Main File
**Path**: `handlers/command_handlers/utility_commands.py`

---

## 1. Compact Help (Mesh/LoRa)

**Method**: `_format_help()`  
**Line**: 575  
**Purpose**: Short help text for mesh (180 char limit)

```python
def _format_help(self):
    """Formater l'aide des commandes"""
    help_lines = [
        "/bot IA",
        "/ia IA", 
        "/power",
        "/sys",
        "/echo",
        "/nodes",
        "/nodesmc",
        "/nodemt",
        "/neighbors",
        "/propag",
        "/info",
        "/keys",
        "/mqtt",
        "/stats [cmd]",
        "/db [cmd]",
        "/trace",
        "/legend",
        "/weather",
        "/rain",
        "/vigi",
        "/help"
    ]
    return "\n".join(help_lines)
```

**To customize**: Edit the `help_lines` array

---

## 2. Detailed Help (Telegram)

**Method**: `_format_help_telegram()`  
**Line**: 602  
**Purpose**: Rich help text for Telegram (no size limit)

```python
def _format_help_telegram(self):
    """Format aide détaillée pour Telegram (sans contrainte de taille)"""
    import textwrap
    
    help_text = textwrap.dedent("""
    📖 AIDE COMPLÈTE - BOT MESHTASTIC
    
    🤖 CHAT IA
    • /bot <question> → Conversation avec l'IA
    • /ia <question> → Alias français de /bot
    
    ⚡ SYSTÈME & MONITORING
    • /power - Télémétrie complète
    • /weather [rain|astro|blitz|vigi] [ville] - Météo
    
    📡 RÉSEAU MESHTASTIC
    • /nodes - Liste nœuds
    • /nodesmc [page|full] - Liste contacts MeshCore
    
    # ... etc (full 200+ lines)
    """)
    
    return help_text
```

**To customize**: Edit the multi-line string with markdown formatting

---

## 3. Help Handler

**Method**: `handle_help()`  
**Line**: 536  
**Purpose**: Routes help request to appropriate format

```python
def handle_help(self, sender_id, sender_info):
    """Gérer la commande /help"""
    info_print(f"Help: {sender_info}")
    
    # Throttling check
    if not self.sender.check_throttling(sender_id, sender_info):
        return
    
    # Get help text
    help_text = self._format_help()
    
    # Send response
    self.sender.send_single(help_text, sender_id, sender_info)
    self.sender.log_conversation(sender_id, sender_info, "/help", help_text)
```

---

## 4. Companion Mode Commands

**File**: `handlers/message_router.py`  
**Line**: 34  
**Purpose**: Define commands available in MeshCore companion mode

```python
# Commandes supportées en mode companion (non-Meshtastic)
self.companion_commands = [
    '/bot',      # AI
    '/ia',       # AI (alias français)
    '/weather',  # Météo
    '/rain',     # Graphiques pluie
    '/power',    # ESPHome telemetry
    '/sys',      # Système (CPU, RAM, uptime)
    '/help',     # Aide
    '/blitz',    # Lightning (si activé)
    '/vigilance',# Vigilance météo (si activé)
    '/rebootpi', # Redémarrage Pi (authentifié)
    '/nodesmc'   # Contacts MeshCore (base SQLite, pas Meshtastic)
]
```

**To customize**: Add/remove commands from the list

---

## How to Customize Help for MeshCore

### Option 1: Detect Mode in Help Text

```python
def _format_help(self):
    """Formater l'aide des commandes"""
    
    # Check if MeshCore mode
    try:
        from config import MESHCORE_ENABLED
        is_meshcore = MESHCORE_ENABLED
    except:
        is_meshcore = False
    
    help_lines = [
        "=== AIDE BOT ===",
        "/bot - Chat IA",
        "/echo - Diffuser msg",
        "/sys - Info système",
    ]
    
    if is_meshcore:
        help_lines.append("Mode: MeshCore")
        help_lines.append("/nodesmc - Contacts")
    else:
        help_lines.append("Mode: Meshtastic")
        help_lines.append("/nodes - Nœuds")
    
    return "\n".join(help_lines)
```

### Option 2: Separate Methods

```python
def _format_help_meshcore(self):
    """Help text specific for MeshCore mode"""
    return "\n".join([
        "=== MESHCORE BOT ===",
        "/bot - Chat IA",
        "/nodesmc - Contacts",
        "/sys - Système",
        "/echo - Diffuser",
        "/help - Aide"
    ])

def _format_help(self):
    """Main help router"""
    try:
        from config import MESHCORE_ENABLED
        if MESHCORE_ENABLED:
            return self._format_help_meshcore()
    except:
        pass
    
    # Default Meshtastic help
    return self._format_help_meshtastic()
```

### Option 3: Dynamic Based on Interface

```python
def _format_help(self):
    """Format help based on available interface"""
    
    # Check interface type
    interface = self.sender._get_interface()
    is_meshcore = hasattr(interface, '__class__') and 'MeshCore' in interface.__class__.__name__
    
    if is_meshcore:
        help_lines = [
            "=== MESHCORE ===",
            "/bot, /ia - IA",
            "/nodesmc - Contacts",
            # MeshCore-specific commands
        ]
    else:
        help_lines = [
            "=== MESHTASTIC ===",
            "/bot, /ia - IA", 
            "/nodes - Nœuds",
            # Meshtastic-specific commands
        ]
    
    return "\n".join(help_lines)
```

---

## Quick Edit Workflow

1. Open file:
   ```bash
   nano handlers/command_handlers/utility_commands.py
   ```

2. Jump to line:
   - Mesh help: `:575` (in nano: Ctrl+_ then type 575)
   - Telegram help: `:602`
   - Handler: `:536`

3. Make changes

4. Test:
   ```bash
   # Via mesh
   /help
   
   # Via Telegram
   /help
   ```

5. Commit:
   ```bash
   git add handlers/command_handlers/utility_commands.py
   git commit -m "Update help text for MeshCore mode"
   git push
   ```

---

## Related Files

- **Command routing**: `handlers/message_router.py`
- **Message sending**: `handlers/message_sender.py`
- **Telegram commands**: `telegram_bot/commands/basic_commands.py`

All help text follows the same pattern:
1. Business logic in `utility_commands.py`
2. Called by router in `message_router.py`
3. Sent via `message_sender.py` with throttling
