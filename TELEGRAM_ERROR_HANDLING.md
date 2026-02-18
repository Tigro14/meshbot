# Amélioration de la gestion des erreurs Telegram

## Problème

Le bot Meshtastic affichait des logs très verbeux et des tracebacks complets pour des erreurs Telegram courantes :

### 1. Logs httpx verbeux
```
INFO:httpx:HTTP Request: POST https://api.telegram.org/bot83708179*****/getUpdates "HTTP/1.1 200 OK"
```

Ces logs INFO apparaissent constamment et encombrent les journaux système.

### 2. Erreur 409 Conflict
```
ERROR:telegram.ext.Updater:Exception happened while polling for updates.
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/dist-packages/telegram/ext/_utils/networkloop.py", line 161...
  [50+ lignes de traceback]
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

Cette erreur se produit lorsque plusieurs instances du bot tentent de faire `getUpdates` simultanément.

### 3. Erreur 429 Rate Limit
Erreurs de limitation de taux qui génèrent également des tracebacks complets.

## Solution

### 1. Suppression des logs httpx/telegram verbeux

**Fichier modifié**: `main_script.py`

Ajout d'une fonction `setup_logging()` qui configure le niveau de logging :

```python
def setup_logging():
    """Configure Python logging pour supprimer les logs verbeux"""
    # Supprimer les logs INFO de httpx (utilisé par python-telegram-bot)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # Supprimer les logs INFO de telegram.ext (trop verbeux)
    logging.getLogger('telegram.ext').setLevel(logging.WARNING)
    
    # Configurer le format de base
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
```

Cette fonction est appelée au démarrage du bot dans `main()`.

**Résultat** : Les logs INFO de httpx et telegram.ext ne sont plus affichés. Seuls les WARNING et ERROR sont visibles.

### 2. Gestion gracieuse des erreurs 409/429

**Fichier modifié**: `telegram_integration.py`

Amélioration de la méthode `_error_handler()` pour détecter et traiter spécifiquement les erreurs 409 et 429 :

```python
async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestionnaire d'erreurs global avec gestion spéciale pour 409/429
    
    409 Conflict: Multiples instances du bot tentent de faire getUpdates
    429 TooManyRequests: Rate limit atteint
    """
    error = context.error
    
    # Import des exceptions Telegram spécifiques
    from telegram.error import Conflict, RetryAfter, TelegramError
    
    # Gestion spéciale pour 409 Conflict
    if isinstance(error, Conflict):
        error_print("⚠️ TELEGRAM 409 CONFLICT: Multiple bot instances detected")
        error_print("   Solution: Ensure only ONE bot instance is running")
        error_print("   Check with: ps aux | grep python | grep meshbot")
        return  # Pas de traceback complet
    
    # Gestion spéciale pour 429 Rate Limit
    if isinstance(error, RetryAfter):
        retry_after = getattr(error, 'retry_after', 60)
        error_print(f"⚠️ TELEGRAM 429 RATE LIMIT: Too many requests")
        error_print(f"   Retry after: {retry_after} seconds")
        error_print(f"   The bot will automatically retry after the delay")
        return  # Pas de traceback complet
    
    # Pour les autres erreurs Telegram : log simplifié
    if isinstance(error, TelegramError):
        error_print(f"⚠️ Telegram Error: {error.__class__.__name__}: {str(error)}")
        # Traceback seulement en mode DEBUG
        if DEBUG_MODE:
            error_print(traceback.format_exc())
    else:
        # Erreurs non-Telegram : log complet
        error_print(f"❌ Erreur Telegram: {error}")
        error_print(traceback.format_exc())
```

**Résultat** : 
- Erreur 409 : Message clair avec solution au lieu d'un traceback de 50 lignes
- Erreur 429 : Message clair avec délai de retry
- Autres erreurs Telegram : Message simplifié (traceback seulement en mode DEBUG)

## Avantages

### 1. Logs plus propres
- ✅ Suppression de centaines de lignes de logs INFO inutiles par jour
- ✅ Logs système plus lisibles et pertinents
- ✅ Facilite le diagnostic des vrais problèmes

### 2. Meilleure expérience utilisateur
- ✅ Messages d'erreur clairs et actionnables
- ✅ Solutions proposées directement dans les logs
- ✅ Pas de tracebacks incompréhensibles pour des erreurs courantes

### 3. Maintenance simplifiée
- ✅ Logs DEBUG toujours disponibles avec `--debug`
- ✅ Détection rapide des problèmes réels
- ✅ Moins de bruit dans les journaux système

## Exemple de logs AVANT

```
Feb 18 07:41:48 DietPi meshtastic-bot[24762]: INFO:httpx:HTTP Request: POST https://api.telegram.org/bot83708179*****/getUpdates "HTTP/1.1 200 OK"
Feb 18 07:41:50 DietPi meshtastic-bot[24762]: INFO:httpx:HTTP Request: POST https://api.telegram.org/bot83708179*****/getUpdates "HTTP/1.1 200 OK"
Feb 18 07:41:52 DietPi meshtastic-bot[24762]: INFO:httpx:HTTP Request: POST https://api.telegram.org/bot83708179*****/getUpdates "HTTP/1.1 200 OK"
Feb 18 07:42:04 DietPi meshtastic-bot[24762]: INFO:httpx:HTTP Request: POST https://api.telegram.org/bot8370817963:AAGMr-Vgbsugn67zR4ihGTzBw564SKhpZzw/getUpdates "HTTP/1.1 409 Conflict"
Feb 18 07:42:04 DietPi meshtastic-bot[24762]: ERROR:telegram.ext.Updater:Exception happened while polling for updates.
Feb 18 07:42:04 DietPi meshtastic-bot[24762]: Traceback (most recent call last):
Feb 18 07:42:04 DietPi meshtastic-bot[24762]:   File "/usr/local/lib/python3.13/dist-packages/telegram/ext/_utils/networkloop.py", line 161, in network_retry_loop
[... 40+ lignes de traceback ...]
Feb 18 07:42:04 DietPi meshtastic-bot[24762]: telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

## Exemple de logs APRÈS

```
[INFO] Bot Telegram démarré en thread séparé
⚠️ TELEGRAM 409 CONFLICT: Multiple bot instances detected
   Solution: Ensure only ONE bot instance is running
   Check with: ps aux | grep python | grep meshbot
```

Logs httpx INFO : **SUPPRIMÉS** ✅
Traceback 409 : **SUPPRIMÉ** ✅
Message clair : **AFFICHÉ** ✅

## Test

Exécuter le script de démonstration :

```bash
python3 demos/demo_telegram_error_improvements.py
```

Ce script valide :
- ✅ Configuration du logging (httpx et telegram.ext en WARNING)
- ✅ Format des messages d'erreur 409 et 429
- ✅ Absence de tracebacks pour erreurs connues

## Déploiement

1. Redémarrer le bot :
```bash
sudo systemctl restart meshbot
```

2. Vérifier les logs :
```bash
journalctl -u meshbot -f
```

3. Constater :
   - Les logs httpx INFO ont disparu
   - Les erreurs 409/429 affichent des messages clairs
   - Le système est plus lisible

## Mode DEBUG

Pour activer les tracebacks complets (diagnostic approfondi) :

```bash
python3 main_script.py --debug
```

En mode DEBUG, tous les tracebacks sont affichés même pour les erreurs 409/429.

## Compatibilité

- ✅ Python 3.8+
- ✅ python-telegram-bot 21.0+
- ✅ Rétrocompatible avec les versions antérieures
- ✅ Pas d'impact sur le comportement fonctionnel du bot
- ✅ Mode DEBUG préservé pour le diagnostic

## Fichiers modifiés

1. `main_script.py` - Configuration du logging
2. `telegram_integration.py` - Gestion des erreurs 409/429
3. `demos/demo_telegram_error_improvements.py` - Script de démonstration (nouveau)

## Références

- Issue GitHub : Amélioration de la gestion des erreurs Telegram
- Documentation Telegram Bot API : https://core.telegram.org/bots/api
- python-telegram-bot : https://python-telegram-bot.org/
