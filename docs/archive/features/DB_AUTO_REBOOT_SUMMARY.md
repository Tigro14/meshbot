# Résumé: Auto-Reboot sur Erreurs DB Persistantes

## Vue d'ensemble

Implémentation complète d'un système de reboot automatique qui surveille les erreurs de base de données et déclenche un redémarrage de l'application lorsque les erreurs deviennent persistantes.

## Problème résolu

**Situation**: Le bot continue de fonctionner mais la base de données SQLite rencontre des erreurs répétées (corruption, filesystem en lecture seule, disque plein).

**Conséquence**: Les données ne sont plus sauvegardées mais le bot ne redémarre pas automatiquement.

**Solution**: Monitoring automatique avec reboot après 5 minutes d'échecs répétés (10 erreurs).

## Architecture

```
TrafficPersistence (save_packet errors)
           ↓
    error_callback
           ↓
    DBErrorMonitor (sliding window)
           ↓
    reboot_callback (threshold reached)
           ↓
    RebootSemaphore (/dev/shm)
           ↓
    rebootpi-watcher.py
           ↓
    sudo reboot
```

## Fichiers créés

1. **db_error_monitor.py** (220 lignes)
   - Classe `DBErrorMonitor` avec fenêtre glissante
   - Comptage d'erreurs sur période configurable
   - Protection contre reboots multiples
   - Génération de rapports d'état

2. **test_db_auto_reboot.py** (350 lignes)
   - 7 tests unitaires complets
   - Couverture: tracking, seuil, expiration, désactivation
   - Tests d'intégration avec RebootSemaphore

3. **test_db_auto_reboot_integration.py** (390 lignes)
   - 4 tests d'intégration complets
   - Validation TrafficPersistence + DBErrorMonitor
   - Tests de fonctionnement normal et en erreur

4. **DB_AUTO_REBOOT.md** (540 lignes)
   - Documentation complète
   - Diagrammes et exemples
   - Configuration recommandée
   - Guide de troubleshooting

## Fichiers modifiés

1. **traffic_persistence.py**
   - Ajout paramètre `error_callback` au constructeur
   - Appel du callback en cas d'erreur dans `save_packet()`
   - Appel du callback en cas d'erreur dans `save_public_message()`
   - Type hints complets

2. **main_bot.py**
   - Import `DBErrorMonitor` et `RebootSemaphore`
   - Méthode `_init_db_error_monitor()`
   - Configuration du callback entre persistence et moniteur
   - Initialisation au démarrage

3. **config.py.sample**
   - Section "MONITORING ET AUTO-REBOOT"
   - 3 nouvelles options configurables
   - Documentation des valeurs recommandées

## Configuration

### Options disponibles

```python
# Activer/désactiver le monitoring
DB_AUTO_REBOOT_ENABLED = True

# Fenêtre de temps (secondes)
DB_AUTO_REBOOT_WINDOW_SECONDS = 300  # 5 minutes

# Seuil d'erreurs
DB_AUTO_REBOOT_ERROR_THRESHOLD = 10
```

### Scénarios recommandés

| Scénario | Window | Threshold | Comportement |
|----------|--------|-----------|--------------|
| Production | 300s | 10 | Balance tolérance/réactivité |
| Développement | 600s | 20 | Plus tolérant pour tests |
| Critique | 180s | 5 | Réaction rapide |
| Conservateur | 900s | 30 | Maximum tolérance |

## Tests

### Tests unitaires (7/7 passent)

```bash
python3 test_db_auto_reboot.py
```

1. ✅ Suivi des erreurs dans fenêtre glissante
2. ✅ Déclenchement au seuil configuré
3. ✅ Protection contre reboots multiples
4. ✅ Expiration de la fenêtre de temps
5. ✅ Respect du flag enable/disable
6. ✅ Génération de rapports d'état
7. ✅ Intégration avec RebootSemaphore

### Tests d'intégration (4/4 passent)

```bash
python3 test_db_auto_reboot_integration.py
```

1. ✅ Callback d'erreur dans TrafficPersistence
2. ✅ Intégration complète du système
3. ✅ Fonctionnement normal sans erreurs
4. ✅ Simulation filesystem lecture seule

## Fonctionnement

### 1. Détection

Toute erreur dans `save_packet()` ou `save_public_message()` est capturée:

```python
try:
    cursor.execute(...)
    self.conn.commit()
except Exception as e:
    logger.error(f"❌ Erreur: {e}")
    if self.error_callback:
        self.error_callback(e, 'save_packet')
```

### 2. Enregistrement

Le moniteur enregistre l'erreur avec timestamp:

```python
def record_error(self, error, operation):
    timestamp = time.time()
    self.errors.append((timestamp, error, operation))
    self._check_threshold()
```

### 3. Vérification

Seules les erreurs récentes (dans la fenêtre) sont comptées:

```python
window_start = time.time() - self.window_seconds
errors_in_window = [
    err for err in self.errors
    if err[0] > window_start
]
```

### 4. Déclenchement

Si le seuil est atteint, reboot via sémaphore:

```python
if len(errors_in_window) >= self.error_threshold:
    requester_info = {
        'name': 'DBErrorMonitor',
        'node_id': '0xDB_ERROR',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    RebootSemaphore.signal_reboot(requester_info)
```

## Logs

### Erreur normale

```
[ERROR] 📝 Erreur DB enregistrée: save_packet - OperationalError: database is locked
```

### Seuil atteint

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

## Avantages

1. ✅ **Récupération automatique** - Pas d'intervention manuelle nécessaire
2. ✅ **Tolérance aux erreurs temporaires** - Ne reboot pas pour quelques erreurs isolées
3. ✅ **Configurable** - Fenêtre et seuil ajustables selon besoins
4. ✅ **Logs détaillés** - Traçabilité complète des erreurs
5. ✅ **Protection anti-boucle** - Un seul reboot par session
6. ✅ **Intégration propre** - Utilise système RebootSemaphore existant
7. ✅ **Tests complets** - 11 tests unitaires + intégration
8. ✅ **Documentation** - Guide complet avec exemples

## Intégration avec systèmes existants

### RebootSemaphore

Utilise le système de sémaphore existant via `/dev/shm`:
- Fonctionne même si filesystem principal est en lecture seule
- Compatible avec `rebootpi-watcher.py` existant
- Pas de modification du système de reboot

### TrafficPersistence

Modification minimale et rétrocompatible:
- Ajout paramètre optionnel `error_callback`
- Comportement identique si callback non fourni
- Pas de changement breaking

### Main Bot

Initialisation simple dans `__init__()`:
```python
self._init_db_error_monitor()
# ...
self.traffic_monitor.persistence.error_callback = self.db_error_monitor.record_error
```

## Désactivation

Pour désactiver complètement:

```python
# config.py
DB_AUTO_REBOOT_ENABLED = False
```

Le monitoring continue de logger les erreurs mais ne déclenche jamais de reboot.

## Maintenance

### Vérifier l'état

Consulter les statistiques du moniteur:

```python
stats = self.db_error_monitor.get_stats()
# {
#   'enabled': True,
#   'total_errors': 15,
#   'errors_in_window': 3,
#   'reboot_triggered': False,
#   ...
# }
```

### Réinitialiser

Après maintenance manuelle:

```python
self.db_error_monitor.reset()
```

### Ajuster configuration

Modifier `config.py` et redémarrer:

```python
DB_AUTO_REBOOT_WINDOW_SECONDS = 600  # Augmenter tolérance
DB_AUTO_REBOOT_ERROR_THRESHOLD = 20
```

## Différences avec TCP Auto-Reboot

| Aspect | TCP Auto-Reboot | DB Auto-Reboot |
|--------|-----------------|----------------|
| **Cible** | Nœud Meshtastic | Application bot |
| **Déclencheur** | Erreur connexion | Erreurs DB persistantes |
| **Seuil** | 1 échec | 10 erreurs/5min |
| **Timing** | Immédiat | Fenêtre temporelle |
| **Action** | `meshtastic --reboot` | `RebootSemaphore` |

Les deux systèmes sont **complémentaires** et peuvent être actifs simultanément.

## Commits

1. **b6f3236** - Implement DB error monitoring with auto-reboot functionality
   - Nouveaux fichiers: db_error_monitor.py, test_db_auto_reboot.py
   - Modifications: traffic_persistence.py, main_bot.py, config.py.sample

2. **948e638** - Add documentation and integration tests for DB auto-reboot
   - Nouveaux fichiers: DB_AUTO_REBOOT.md, test_db_auto_reboot_integration.py

3. **b12d74f** - Add type hints and make error queue size configurable
   - Améliorations: type hints, paramètre max_errors_stored

## Références

- **Documentation principale**: `DB_AUTO_REBOOT.md`
- **Code source**: `db_error_monitor.py`, `traffic_persistence.py`, `main_bot.py`
- **Tests unitaires**: `test_db_auto_reboot.py`
- **Tests intégration**: `test_db_auto_reboot_integration.py`
- **Configuration**: `config.py.sample` (lignes 324-340)
- **Système reboot**: `REBOOT_SEMAPHORE.md`

---

**Auteur**: GitHub Copilot  
**Date**: 2024-12-14  
**Statut**: ✅ Implémentation complète et testée  
**Tests**: ✅ 11/11 passent  
**Documentation**: ✅ Complète
