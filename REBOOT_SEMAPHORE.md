# Système de Sémaphore pour Redémarrage Pi

## Vue d'ensemble

Le bot utilise un système de sémaphore basé sur `/dev/shm` (mémoire partagée tmpfs) pour signaler 
les demandes de redémarrage. Cette approche résout le problème critique des systèmes de fichiers 
en lecture seule.

## Problème résolu

### Ancien système (fichier dans /tmp)
```
/rebootpi command → Write /tmp/reboot_requested → Watcher reads file → Reboot
                    ❌ FAIL if filesystem is read-only
```

**Problème**: Quand le Raspberry Pi a des problèmes de carte SD ou de corruption, le système de 
fichiers peut passer en mode lecture seule (read-only). Dans ce cas, impossible d'écrire le fichier 
signal, donc impossible de redémarrer à distance alors que c'est le moment où on en a le plus besoin!

### Nouveau système (sémaphore dans /dev/shm)
```
/rebootpi command → Lock /dev/shm/meshbot_reboot.lock → Watcher checks lock → Reboot
                    ✅ Works even if / or /tmp are read-only
```

**Solution**: `/dev/shm` est un filesystem tmpfs monté en RAM. Il reste accessible même si les 
filesystems sur disque sont en lecture seule.

## Architecture technique

### Composants

1. **`reboot_semaphore.py`** - Module Python de signalisation
   - `RebootSemaphore.signal_reboot(info)` - Signaler un reboot
   - `RebootSemaphore.check_reboot_signal()` - Vérifier si reboot demandé
   - `RebootSemaphore.clear_reboot_signal()` - Effacer le signal
   - `RebootSemaphore.get_reboot_info()` - Obtenir info sur la demande

2. **`system_commands.py`** - Commande `/rebootpi` mise à jour
   - Utilise `RebootSemaphore` au lieu d'écriture fichier
   - Maintient la sécurité (auth + password)

3. **`rebootpi-watcher.py`** - Daemon Python (recommandé)
   - Vérifie le sémaphore toutes les 5 secondes
   - Logs détaillés
   - Gestion d'erreurs robuste

4. **`rebootpi-watcher.sh`** - Alternative Bash (simple)
   - Version shell du watcher
   - Utilise `flock` pour vérifier le lock

### Mécanisme de locking

Le système utilise `fcntl.flock()` pour créer un lock exclusif:

```python
# Signal reboot (bot)
lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_WRONLY, 0o644)
fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
# Lock is held while bot is running

# Check signal (watcher)
try:
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Got lock → no reboot signaled
    return False
except IOError:
    # Lock is held → reboot is signaled
    return True
```

### Fichiers utilisés

- **`/dev/shm/meshbot_reboot.lock`** - Fichier de verrouillage (sémaphore)
- **`/dev/shm/meshbot_reboot.info`** - Informations sur la demande (optionnel)
- **`/var/log/bot-reboot.log`** - Log du watcher

## Avantages

1. ✅ **Survie aux filesystems read-only**: `/dev/shm` est en RAM
2. ✅ **IPC propre**: Utilise les primitives système (fcntl)
3. ✅ **Nettoyage automatique**: tmpfs est effacé au redémarrage
4. ✅ **Compatible multiprocess**: Bot et watcher communiquent sans dépendances
5. ✅ **Performance**: Pas d'I/O disque
6. ✅ **Simplicité**: Pas besoin de librairies externes (posix_ipc)

## Installation

### 1. Copier les fichiers

```bash
# Le module semaphore est déjà dans le repo
# Copier le watcher (version Python recommandée)
sudo cp rebootpi-watcher.py /usr/local/bin/
sudo chmod +x /usr/local/bin/rebootpi-watcher.py

# Ou version Bash (alternative)
sudo cp rebootpi-watcher.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/rebootpi-watcher.sh
```

### 2. Créer le service systemd

**Pour la version Python** (recommandée):

```bash
sudo tee /etc/systemd/system/rebootpi-watcher.service << 'EOF'
[Unit]
Description=Bot RebootPi Watcher (Python)
Documentation=https://github.com/Tigro14/meshbot
After=multi-user.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/rebootpi-watcher.py
Restart=always
RestartSec=10
User=root
StandardOutput=journal
StandardError=journal
WorkingDirectory=/home/user/meshbot

[Install]
WantedBy=multi-user.target
EOF
```

**Ajustez** `WorkingDirectory` pour pointer vers votre installation du bot.

### 3. Activer le service

```bash
# Créer le log
sudo touch /var/log/bot-reboot.log
sudo chmod 644 /var/log/bot-reboot.log

# Activer et démarrer
sudo systemctl daemon-reload
sudo systemctl enable rebootpi-watcher.service
sudo systemctl start rebootpi-watcher.service

# Vérifier
sudo systemctl status rebootpi-watcher.service
```

## Tests

### Test du module semaphore

```bash
cd /home/user/meshbot
python3 test_reboot_semaphore.py
```

Résultat attendu:
```
✅ Tous les tests passent
✅ Utilise /dev/shm (tmpfs en RAM)
✅ Survit même si /tmp ou / deviennent read-only
```

### Test manuel du signal (SANS reboot)

```bash
python3 << 'EOF'
from reboot_semaphore import RebootSemaphore
import time

# Signal reboot
info = {
    'name': 'TestManual',
    'node_id': '0xFFFFFFFF',
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
}

if RebootSemaphore.signal_reboot(info):
    print("✅ Signal créé")
    
    # Vérifier
    if RebootSemaphore.check_reboot_signal():
        print("✅ Signal détecté par check")
    
    # Nettoyer (pour éviter un reboot réel!)
    RebootSemaphore.clear_reboot_signal()
    print("✅ Signal nettoyé (reboot annulé)")
else:
    print("❌ Erreur création signal")
EOF
```

### Test complet (ATTENTION: redémarre le système!)

```bash
# Via Python
python3 << 'EOF'
from reboot_semaphore import RebootSemaphore
import time

info = {
    'name': 'TestComplet',
    'node_id': '0xDEADBEEF',
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
}

RebootSemaphore.signal_reboot(info)
print("🚨 Signal envoyé - système va redémarrer dans 5-10 secondes!")
EOF
```

### Vérifier les logs du watcher

```bash
# Logs systemd
sudo journalctl -u rebootpi-watcher.service -f

# Logs fichier
sudo tail -f /var/log/bot-reboot.log
```

## Dépannage

### Le signal ne fonctionne pas

```bash
# 1. Vérifier que /dev/shm est monté
mount | grep shm
# Devrait afficher: tmpfs on /dev/shm type tmpfs ...

# 2. Vérifier que le watcher tourne
sudo systemctl status rebootpi-watcher.service

# 3. Vérifier les permissions
ls -la /dev/shm/meshbot*

# 4. Tester manuellement
python3 test_reboot_semaphore.py
```

### Le watcher ne démarre pas

```bash
# Voir les erreurs
sudo journalctl -u rebootpi-watcher.service -n 50

# Vérifier WorkingDirectory
# Doit pointer vers le répertoire contenant reboot_semaphore.py
```

### /dev/shm non disponible

Sur certains systèmes minimalistes, `/dev/shm` peut ne pas être monté:

```bash
# Vérifier
df -h /dev/shm

# Si absent, monter temporairement
sudo mount -t tmpfs -o size=10M tmpfs /dev/shm

# Ou ajouter à /etc/fstab pour permanence
echo "tmpfs /dev/shm tmpfs defaults,size=10M 0 0" | sudo tee -a /etc/fstab
```

## Migration depuis l'ancien système

Si vous utilisiez l'ancien système avec `/tmp/reboot_requested`:

1. **Le nouveau code est rétrocompatible**: Le bot utilise maintenant le sémaphore automatiquement
2. **Mettre à jour le watcher**: Remplacer l'ancien script par la nouvelle version
3. **Tester**: Utiliser `test_reboot_semaphore.py`
4. **Redémarrer les services**:
   ```bash
   sudo systemctl restart meshbot.service
   sudo systemctl restart rebootpi-watcher.service
   ```

## Sécurité

Le système de sémaphore **ne change pas** le modèle de sécurité:

- ✅ Authentification par liste d'utilisateurs autorisés
- ✅ Vérification du mot de passe
- ✅ Logs de toutes les demandes
- ✅ Le watcher doit tourner en root (nécessaire pour reboot)

La seule différence est le **mécanisme de signalisation** (sémaphore au lieu de fichier).

## Références

- **Code**: `reboot_semaphore.py`, `system_commands.py`
- **Tests**: `test_reboot_semaphore.py`
- **Watcher Python**: `rebootpi-watcher.py`
- **Watcher Bash**: Voir `README.md` section "Commande de Redémarrage"
- **Documentation système**: `man 2 flock`, `man 7 tmpfs`
