# Integration Telegram Bot avec Meshtastic Bot

## Vue d'ensemble

Cette intégration ajoute une interface Telegram à votre bot Meshtastic existant, permettant de contrôler le réseau mesh depuis Telegram.

## Architecture

```
Telegram User → Telegram Bot → File Queue → Meshtastic Bot → LoRa/Mesh → tigrog2
                     ↑                             ↓
                Response ← File Response ← Command Processing
```

## Installation

### 1. Préparer l'environnement

```bash
# Exécuter le script d'installation
chmod +x telegram_setup.sh
sudo ./telegram_setup.sh
```

### 2. Créer le bot Telegram

1. Ouvrir Telegram et chercher **@BotFather**
2. Envoyer : `/newbot`
3. Nom : `Meshtastic Bridge Bot`
4. Username : `votrenom_mesh_bot`
5. Copier le token reçu

### 3. Configuration

```bash
cd /opt/meshtastic-telegram
nano telegram_config.py
```

Modifier :
```python
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHijklMNOpqrsTUVwxyz"
AUTHORIZED_USERS = [123456789, 987654321]  # Vos IDs Telegram
```

### 4. Intégrer dans le bot Meshtastic

Ajouter dans votre `main_bot.py` :

```python
# En haut du fichier, avec les autres imports
try:
    from telegram_integration import TelegramIntegration
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

class DebugMeshBot:
    def __init__(self):
        # ... code existant ...
        self.telegram_integration = None
    
    def start(self):
        # ... code existant après l'initialisation du message_handler ...
        
        # Ajouter l'intégration Telegram
        if TELEGRAM_AVAILABLE:
            try:
                self.telegram_integration = TelegramIntegration(
                    self.message_handler,
                    self.node_manager,
                    self.context_manager
                )
                self.telegram_integration.start()
                info_print("✅ Interface Telegram intégrée")
            except Exception as e:
                error_print(f"Erreur intégration Telegram: {e}")
        else:
            debug_print("📱 Module Telegram non disponible")
    
    def stop(self):
        # ... code existant ...
        
        # Arrêter l'intégration Telegram
        if self.telegram_integration:
            self.telegram_integration.stop()
```

## Démarrage

### 1. Tester la configuration

```bash
cd /opt/meshtastic-telegram
./manage_telegram_bot.sh test
```

### 2. Démarrer les services

```bash
# Démarrer le bot Telegram
./manage_telegram_bot.sh start

# Redémarrer votre bot Meshtastic avec l'intégration
sudo systemctl restart meshtastic-bot  # ou votre méthode habituelle
```

### 3. Vérifier les logs

```bash
# Logs bot Telegram
./manage_telegram_bot.sh logs

# Logs bot Meshtastic
journalctl -u meshtastic-bot -f
```

## Utilisation

### Commandes Telegram disponibles

**Commandes directes:**
- `/start` - Démarrer le bot
- `/help` - Aide complète
- `/status` - État du système
- `/nodes` - Liste des nœuds
- `/stats` - Statistiques

**Commandes mesh (via `/mesh`):**
- `/mesh /bot <question>` - Chat IA
- `/mesh /power` - Info batterie
- `/mesh /rx [page]` - Nœuds tigrog2
- `/mesh /sys` - Info système

**Commandes spéciales:**
- `/echo <message>` - Diffuser via tigrog2
- `<message direct>` - Raccourci pour `/mesh /bot <message>`

### Exemples d'usage

```
Vous: Bonjour
Bot: 🤖 IA Mesh: Salut ! Comment puis-je t'aider ?

Vous: /echo Salut le réseau !
Bot: 📡 Echo diffusé: Salut le réseau !

Vous: /mesh /power
Bot: 📡 Réponse Mesh: 13.2V (1.45A) | Today:1250Wh | T:22.1C | P:1013 | HR:65%(12.4g/m³)

Vous: /status
Bot: 📊 État Meshtastic:
Pi5 Bot: ✅ Actif
Tigrog2: ✅ Connecté
Llama: ✅ Opérationnel
```

## Fichiers de communication

Le système utilise des fichiers JSON pour la communication :

- `/tmp/telegram_mesh_queue.json` - Requêtes Telegram → Mesh
- `/tmp/mesh_telegram_response.json` - Réponses Mesh → Telegram

## Sécurité

### Autorisation des utilisateurs

Modifier `AUTHORIZED_USERS` dans `telegram_config.py` :

```python
# Liste vide = tout le monde autorisé (dangereux)
AUTHORIZED_USERS = []

# Liste spécifique d'IDs Telegram autorisés
AUTHORIZED_USERS = [123456789, 987654321]
```

### Trouver votre ID Telegram

Envoyer `/start` au bot, votre ID apparaît dans le message de bienvenue.

## Maintenance

### Gestion du service

```bash
# Statut
./manage_telegram_bot.sh status

# Redémarrage
./manage_telegram_bot.sh restart

# Voir les logs
./manage_telegram_bot.sh logs

# Éditer la config
./manage_telegram_bot.sh config
```

### Logs et debugging

Les logs incluent :
- Requêtes traitées
- Erreurs de connexion
- Statistiques d'usage
- Debug des communications

### Nettoyage périodique

Les fichiers de communication se nettoient automatiquement, mais vous pouvez forcer :

```bash
# Nettoyer les files
rm /tmp/telegram_mesh_queue.json /tmp/mesh_telegram_response.json
```

## Dépannage

### Bot Telegram ne répond pas

1. Vérifier le token : `./manage_telegram_bot.sh test`
2. Vérifier les logs : `./manage_telegram_bot.sh logs`
3. Redémarrer : `./manage_telegram_bot.sh restart`

### Pas de réponse du bot Meshtastic

1. Vérifier que l'intégration est chargée dans main_bot.py
2. Vérifier les permissions sur `/tmp/telegram_mesh_*`
3. Vérifier les logs du bot Meshtastic

### Commandes timeout

Le timeout par défaut est 30s. Pour les commandes lentes (/bot avec IA), c'est normal.

### Echo ne fonctionne pas

1. Vérifier que tigrog2 est accessible
2. Vérifier la configuration REMOTE_NODE_HOST
3. Tester `/mesh /rx` pour valider la connexion tigrog2

## Limitations

- **Commande `/my`** : Non disponible depuis Telegram (réservée aux vrais nœuds mesh)
- **Timeout** : 30 secondes maximum par commande
- **Rate limiting** : 10 commandes par minute par utilisateur
- **Taille message** : Limitée par Telegram (4096 caractères)

## Configuration avancée

### Variables d'environnement

```bash
export TELEGRAM_BOT_TOKEN="votre_token"
export TELEGRAM_LOG_LEVEL="DEBUG"
export MESHTASTIC_API_URL="http://localhost:8000"
```

### Personnalisation

Vous pouvez modifier `telegram_bridge.py` pour :
- Ajouter des commandes spécifiques
- Modifier le formatage des réponses
- Ajouter des notifications automatiques
- Intégrer d'autres services

---

**Note**: Cette intégration est conçue pour fonctionner avec votre architecture existante sans modification majeure du code principal.
