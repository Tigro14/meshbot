# Auto-Reboot sur Erreurs DB Persistantes

## Vue d'ensemble

Le bot surveille automatiquement les erreurs d'écriture en base de données SQLite et déclenche un reboot automatique de l'application lorsque les erreurs deviennent persistantes. Cela permet une récupération automatique en cas de corruption de base de données ou d'autres problèmes persistants.

## Problème résolu

### Scénario réel: Base de données corrompue ou système de fichiers en lecture seule

**Situation**: Le bot fonctionne mais la base de données SQLite rencontre des erreurs répétées:
- Fichier de base de données corrompu
- Système de fichiers passé en lecture seule
- Disque plein
- Permissions incorrectes
- Problèmes de verrouillage SQLite

**Conséquences sans auto-reboot**:
- Les paquets ne sont plus sauvegardés en base
- Les statistiques deviennent incorrectes
- Le bot continue de tourner mais perd des données
- Intervention manuelle nécessaire pour redémarrer

**Solution avec auto-reboot**:
- Détection automatique des erreurs persistantes
- Reboot automatique après 5 minutes d'échecs
- Récupération sans intervention humaine
- Logs détaillés pour diagnostic

## Architecture

### Composants

```
┌────────────────────────────────────────────┐
│         TrafficPersistence                 │
│  (save_packet, save_public_message)        │
└──────────────┬─────────────────────────────┘
               │ error_callback()
               ▼
┌────────────────────────────────────────────┐
│         DBErrorMonitor                     │
│  - Fenêtre glissante (5 min)               │
│  - Compteur d'erreurs                      │
│  - Seuil configurable (10 erreurs)         │
└──────────────┬─────────────────────────────┘
               │ reboot_callback()
               ▼
┌────────────────────────────────────────────┐
│         RebootSemaphore                    │
│  Signal via /dev/shm/meshbot_reboot.lock   │
└────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│      rebootpi-watcher.py                   │
│  Détecte signal → Reboot système           │
└────────────────────────────────────────────┘
```

### Flux de détection et reboot

```
1. TrafficMonitor.add_packet()
   └─> TrafficPersistence.save_packet()
       └─> [ERREUR SQLite] ❌
           └─> error_callback(error, 'save_packet')
               └─> DBErrorMonitor.record_error()
                   └─> errors.append((timestamp, error, operation))
                   └─> _check_threshold()
                       └─> [SI errors >= 10 dans 300s]
                           └─> _trigger_reboot()
                               └─> reboot_callback()
                                   └─> RebootSemaphore.signal_reboot()
                                       └─> Lock /dev/shm/meshbot_reboot.lock
                                           └─> rebootpi-watcher détecte
                                               └─> sudo reboot
```

## Configuration

### Options dans config.py

```python
# ========================================
# MONITORING ET AUTO-REBOOT
# ========================================

# Activer/désactiver le monitoring d'erreurs DB avec auto-reboot
DB_AUTO_REBOOT_ENABLED = True

# Taille de la fenêtre de temps pour compter les erreurs (en secondes)
# Valeur par défaut: 300 secondes (5 minutes)
DB_AUTO_REBOOT_WINDOW_SECONDS = 300

# Nombre d'erreurs nécessaires pour déclencher le reboot automatique
# Valeur par défaut: 10 erreurs dans la fenêtre de temps
DB_AUTO_REBOOT_ERROR_THRESHOLD = 10
```

### Paramètres recommandés

| Scénario | Window (s) | Threshold | Justification |
|----------|------------|-----------|---------------|
| **Production** (défaut) | 300 | 10 | Balance entre tolérance et rapidité |
| **Développement** | 600 | 20 | Plus tolérant pour tests |
| **Critique** | 180 | 5 | Réaction plus rapide |
| **Conservateur** | 900 | 30 | Maximum de tolérance |

### Désactivation

Pour désactiver complètement le monitoring:

```python
DB_AUTO_REBOOT_ENABLED = False
```

Le système continuera de logger les erreurs mais ne déclenchera jamais de reboot.

## Fonctionnement détaillé

### 1. Détection des erreurs

Toutes les erreurs levées lors de `save_packet()` et `save_public_message()` sont capturées:

```python
try:
    self.conn.commit()
except Exception as e:
    logger.error(f"❌ Erreur lors de la sauvegarde du paquet : {e}")
    
    # Notifier le moniteur d'erreurs
    if self.error_callback:
        self.error_callback(e, 'save_packet')
```

### 2. Fenêtre glissante

Le moniteur maintient une file d'erreurs avec timestamps:

```python
self.errors = deque(maxlen=100)  # Dernières 100 erreurs
self.errors.append((timestamp, exception, operation))
```

Seules les erreurs récentes (dans la fenêtre de temps) sont comptabilisées.

### 3. Vérification du seuil

À chaque erreur enregistrée, le seuil est vérifié:

```python
current_time = time.time()
window_start = current_time - self.window_seconds

errors_in_window = [
    err for err in self.errors
    if err[0] > window_start
]

if len(errors_in_window) >= self.error_threshold:
    self._trigger_reboot()
```

### 4. Déclenchement du reboot

Quand le seuil est atteint:

1. **Log détaillé** des erreurs et leur répartition
2. **Appel du callback** pour activer le sémaphore
3. **Protection** contre reboots multiples (flag `reboot_triggered`)
4. **Statistiques** mises à jour

```python
def _trigger_reboot(self, error_count, errors_in_window):
    error_print("🚨 SEUIL D'ERREURS DB ATTEINT - REBOOT AUTOMATIQUE")
    error_print(f"📊 Erreurs détectées: {error_count} en {self.window_seconds}s")
    
    # Log des types d'erreurs
    for error_type, count in error_types.items():
        error_print(f"   {error_type}: {count}")
    
    # Déclencher le reboot
    success = self.reboot_callback()
```

### 5. Sémaphore et reboot

Le reboot utilise le système existant `RebootSemaphore`:

```python
requester_info = {
    'name': 'DBErrorMonitor',
    'node_id': '0xDB_ERROR',
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
}
RebootSemaphore.signal_reboot(requester_info)
```

Le daemon `rebootpi-watcher.py` détecte le signal et exécute `sudo reboot`.

## Logs et monitoring

### Logs des erreurs DB

Chaque erreur est loggée:

```
[ERROR] 📝 Erreur DB enregistrée: save_packet - OperationalError: database is locked
```

### Logs de déclenchement

Quand le seuil est atteint:

```
[ERROR] ============================================================
[ERROR] 🚨 SEUIL D'ERREURS DB ATTEINT - REBOOT AUTOMATIQUE
[ERROR] ============================================================
[ERROR] 📊 Erreurs détectées: 10 en 300s
[ERROR] ⚠️ Seuil configuré: 10 erreurs
[ERROR] 📝 Répartition des erreurs:
[ERROR]    OperationalError: 7
[ERROR]    IntegrityError: 3
[INFO] 🔄 Déclenchement du reboot via callback...
[INFO] ✅ Sémaphore reboot activé: /dev/shm/meshbot_reboot.lock
[INFO] ✅ Signal de reboot envoyé avec succès
[ERROR] ============================================================
```

### Monitoring via commande (future)

On peut ajouter une commande `/dbstats` pour consulter l'état du moniteur:

```python
report = self.db_error_monitor.get_status_report(compact=True)
# Retourne:
# ✅ DB Monitor
# Erreurs: 3/10 (300s)
# Total: 15 err, 0 reboot
```

## Tests

### Exécution des tests

```bash
cd /home/user/meshbot
python3 test_db_auto_reboot.py
```

### Tests inclus

1. **test_error_tracking** - Vérifie le suivi des erreurs
2. **test_threshold_trigger** - Vérifie le déclenchement au seuil
3. **test_no_duplicate_reboot** - Vérifie pas de reboots multiples
4. **test_window_expiration** - Vérifie expiration fenêtre
5. **test_disabled_monitor** - Vérifie respect du flag désactivé
6. **test_status_report** - Vérifie génération des rapports
7. **test_reboot_semaphore_integration** - Vérifie intégration sémaphore

### Résultats attendus

```
✅ Tous les tests passent
Tests réussis: 7/7
```

## Exemples d'utilisation

### Exemple 1: Configuration production

```python
# config.py
DB_AUTO_REBOOT_ENABLED = True
DB_AUTO_REBOOT_WINDOW_SECONDS = 300  # 5 minutes
DB_AUTO_REBOOT_ERROR_THRESHOLD = 10  # 10 erreurs
```

**Comportement**: Tolère quelques erreurs temporaires mais réagit si les erreurs persistent.

### Exemple 2: Système très stable

```python
# config.py
DB_AUTO_REBOOT_ENABLED = True
DB_AUTO_REBOOT_WINDOW_SECONDS = 600  # 10 minutes
DB_AUTO_REBOOT_ERROR_THRESHOLD = 20  # 20 erreurs
```

**Comportement**: Plus tolérant, ne reboot que si vraiment problématique.

### Exemple 3: Système critique

```python
# config.py
DB_AUTO_REBOOT_ENABLED = True
DB_AUTO_REBOOT_WINDOW_SECONDS = 180  # 3 minutes
DB_AUTO_REBOOT_ERROR_THRESHOLD = 5   # 5 erreurs
```

**Comportement**: Réagit rapidement aux problèmes persistants.

### Exemple 4: Développement/debug

```python
# config.py
DB_AUTO_REBOOT_ENABLED = False  # Désactivé
```

**Comportement**: Erreurs loggées mais pas de reboot automatique.

## Diagnostic

### Vérifier l'état du moniteur

Ajouter temporairement dans `main_bot.py::periodic_cleanup()`:

```python
if self.db_error_monitor:
    stats = self.db_error_monitor.get_stats()
    if stats['errors_in_window'] > 0:
        debug_print(f"🔍 DB Monitor: {stats['errors_in_window']}/{stats['error_threshold']} erreurs")
```

### Consulter les logs

```bash
# Logs du bot
journalctl -u meshbot -f | grep "DB"

# Logs de reboot
cat /dev/shm/meshbot_reboot.info
```

### Vérifier le sémaphore

```bash
# Vérifier si sémaphore actif
ls -la /dev/shm/meshbot_reboot.*

# Voir les infos de reboot
cat /dev/shm/meshbot_reboot.info
```

## Troubleshooting

### Problème: Reboots trop fréquents

**Symptôme**: Le bot reboot constamment

**Causes possibles**:
- Problème de disque persistant (plein, corrompu)
- Seuil trop bas
- Permissions incorrectes sur fichier DB

**Solutions**:
1. Vérifier l'espace disque: `df -h`
2. Vérifier les permissions: `ls -la traffic_history.db`
3. Augmenter le seuil temporairement:
   ```python
   DB_AUTO_REBOOT_ERROR_THRESHOLD = 30
   ```
4. Vérifier l'intégrité de la DB:
   ```bash
   sqlite3 traffic_history.db "PRAGMA integrity_check"
   ```

### Problème: Pas de reboot malgré erreurs

**Symptôme**: Erreurs DB mais pas de reboot

**Causes possibles**:
- Moniteur désactivé
- Seuil non atteint
- rebootpi-watcher pas actif

**Solutions**:
1. Vérifier la configuration:
   ```python
   DB_AUTO_REBOOT_ENABLED = True  # Doit être True
   ```
2. Vérifier les logs pour voir le compteur d'erreurs
3. Vérifier que rebootpi-watcher tourne:
   ```bash
   sudo systemctl status rebootpi-watcher
   ```

### Problème: Erreurs temporaires déclenchent reboot

**Symptôme**: Reboot alors que les erreurs sont isolées

**Causes possibles**:
- Fenêtre de temps trop courte
- Seuil trop bas

**Solution**: Augmenter la fenêtre ou le seuil:
```python
DB_AUTO_REBOOT_WINDOW_SECONDS = 600  # 10 minutes
DB_AUTO_REBOOT_ERROR_THRESHOLD = 20  # 20 erreurs
```

## Intégration avec autres systèmes

### Alertes Telegram (future)

On peut ajouter une alerte Telegram avant le reboot:

```python
def reboot_callback():
    # Envoyer alerte Telegram
    if self.platform_manager:
        telegram = self.platform_manager.get_platform('telegram')
        if telegram:
            telegram.alert_manager.send_alert(
                "🚨 DB errors threshold reached - rebooting bot"
            )
    
    # Déclencher le reboot
    return RebootSemaphore.signal_reboot(requester_info)
```

### Métriques Prometheus (future)

Exporter les métriques du moniteur:

```python
db_errors_total = Counter('meshbot_db_errors_total', 'Total DB errors')
db_reboots_total = Counter('meshbot_db_reboots_total', 'Total DB-triggered reboots')

def record_error(self, error, operation):
    db_errors_total.inc()
    # ... reste du code
```

## Différences avec TCP Auto-Reboot

| Fonctionnalité | TCP Auto-Reboot | DB Auto-Reboot |
|----------------|-----------------|----------------|
| **Cible** | Nœud Meshtastic distant | Bot (application) |
| **Déclencheur** | Erreur connexion TCP | Erreurs DB persistantes |
| **Action** | `meshtastic --reboot` | `RebootSemaphore.signal_reboot()` |
| **Timing** | Immédiat (1 retry) | Après fenêtre de temps |
| **Seuil** | 1 échec (avec retry) | Configurable (défaut: 10) |
| **Use case** | Nœud distant bloqué | DB corrompue/filesystem RO |

Les deux systèmes sont complémentaires et peuvent être actifs simultanément.

## Meilleures pratiques

### 1. Configuration conservative

Commencer avec des valeurs conservatrices:

```python
DB_AUTO_REBOOT_ENABLED = True
DB_AUTO_REBOOT_WINDOW_SECONDS = 600
DB_AUTO_REBOOT_ERROR_THRESHOLD = 20
```

Puis ajuster selon l'expérience.

### 2. Monitoring des logs

Surveiller les logs régulièrement:

```bash
# Compter les erreurs DB récentes
journalctl -u meshbot --since "1 hour ago" | grep "Erreur DB" | wc -l

# Voir les types d'erreurs
journalctl -u meshbot --since "1 day ago" | grep "Erreur DB"
```

### 3. Tests périodiques

Tester manuellement le système:

```bash
# Simuler corruption DB
sqlite3 traffic_history.db "PRAGMA locking_mode=EXCLUSIVE; BEGIN EXCLUSIVE;"
# Dans un autre terminal, démarrer le bot
# Observer les erreurs et le reboot automatique
```

### 4. Backup de la DB

Faire des backups réguliers avant que la corruption ne se propage:

```bash
# Cron quotidien
0 3 * * * cp /home/user/meshbot/traffic_history.db /backup/traffic_$(date +\%Y\%m\%d).db
```

## Références

- **Code source**: `db_error_monitor.py`, `traffic_persistence.py`
- **Tests**: `test_db_auto_reboot.py`
- **Configuration**: `config.py.sample` (lignes 324-340)
- **Sémaphore**: `reboot_semaphore.py`, `REBOOT_SEMAPHORE.md`
- **Watcher**: `rebootpi-watcher.py`

## Changelog

### Version 1.0 (2024-12-14)
- Implémentation initiale du monitoring d'erreurs DB
- Support fenêtre de temps glissante
- Seuil d'erreurs configurable
- Intégration avec RebootSemaphore existant
- Tests unitaires complets (7 tests)
- Documentation complète
- Configuration dans config.py.sample

---

**Auteur:** GitHub Copilot  
**Date:** 2024-12-14  
**Issue:** Auto-reboot sur erreurs DB persistantes
