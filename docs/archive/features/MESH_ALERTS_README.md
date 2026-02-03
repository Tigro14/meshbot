# Système d'Alertes Mesh via DM

Ce document décrit le système d'alertes automatiques par Direct Message (DM) Meshtastic pour les événements critiques (vigilance météo et éclairs).

## Vue d'ensemble

Le système d'alertes Mesh permet d'envoyer automatiquement des messages DM aux nœuds Meshtastic abonnés lorsque des conditions critiques sont détectées :
- **Vigilance météo** : Alertes Météo-France niveau Orange ou Rouge
- **Éclairs** : Détection d'orages à proximité (via Blitzortung.org)

### Avantages
- ✅ **Automatique** : Les alertes sont envoyées sans intervention manuelle
- ✅ **Format compact** : Messages optimisés pour LoRa (< 180 caractères)
- ✅ **Anti-spam** : Throttling intelligent pour éviter les envois répétés
- ✅ **Configurable** : Seuils et nœuds abonnés personnalisables
- ✅ **Fiable** : Réutilise MessageSender (gestion des erreurs, retry)

## Configuration

### 1. Activer les alertes Mesh

Dans `config.py`, ajouter :

```python
# ========================================
# CONFIGURATION ALERTES MESH (DM)
# ========================================

# Activer le système d'alertes Mesh
MESH_ALERTS_ENABLED = True

# Nœuds abonnés aux alertes (format int ou hex)
MESH_ALERT_SUBSCRIBED_NODES = [
    0x16fad3dc,  # Node tigro (hex)
    305419896,   # Node autre (decimal)
    0x12345678,  # Node exemple
]

# Seuil d'éclairs pour déclencher une alerte
BLITZ_MESH_ALERT_THRESHOLD = 5  # >= 5 éclairs dans la fenêtre

# Throttling (temps minimum entre 2 alertes identiques)
MESH_ALERT_THROTTLE_SECONDS = 1800  # 30 minutes
```

### 2. Activer la vigilance météo (si pas déjà fait)

```python
# Configuration vigilance Météo-France
VIGILANCE_ENABLED = True
VIGILANCE_DEPARTEMENT = '25'  # Votre département
VIGILANCE_CHECK_INTERVAL = 28800  # 8 heures
VIGILANCE_ALERT_LEVELS = ['Orange', 'Rouge']
```

### 3. Activer la surveillance des éclairs (si pas déjà fait)

```python
# Configuration Blitzortung
BLITZ_ENABLED = True
BLITZ_RADIUS_KM = 50  # Rayon de surveillance
BLITZ_CHECK_INTERVAL = 900  # 15 minutes
BLITZ_WINDOW_MINUTES = 15  # Fenêtre de temps
```

## Formats d'alertes

### Alerte Vigilance Météo

Format compact pour LoRa (≤ 180 chars) :

```
🟠 VIGILANCE ORANGE
Dept 25
Vent violent: Orange
```

ou

```
🔴 VIGILANCE ROUGE
Dept 25
- Vent violent: Rouge
- Pluie-inondation: Orange
```

### Alerte Éclairs

Format compact pour LoRa (≤ 180 chars) :

```
⚡ 8 éclairs (15min)
+ proche: 12.3km
il y a 2min
```

## Comportement

### Déclenchement automatique

Les alertes sont envoyées automatiquement lorsque :
1. **Vigilance** : Niveau Orange ou Rouge détecté (vérif toutes les 8h)
2. **Éclairs** : Nombre d'éclairs ≥ seuil (vérif toutes les 15min)

### Throttling

Pour éviter le spam, le système limite les envois :
- **Par type d'alerte** : Vigilance et Éclairs sont indépendants
- **Par nœud** : Chaque nœud a son propre throttle
- **Durée** : 30 minutes par défaut (configurable)

**Exemple** :
```
10:00 → Alerte vigilance envoyée à tigro
10:15 → Alerte éclairs envoyée à tigro (type différent = OK)
10:20 → Nouvelle vigilance (throttlée car < 30min depuis 10:00)
10:31 → Nouvelle vigilance (OK, 31min écoulées)
```

### Envoi aux nœuds

Les DM sont envoyés via `MessageSender` :
- ✅ Gestion automatique des erreurs
- ✅ Retry en cas d'échec
- ✅ Respect du throttling global du bot
- ✅ Logs complets pour debug

## Logs et Monitoring

### Logs d'initialisation

```
[INFO] 📢 MeshAlertManager initialisé
[INFO]    Nœuds abonnés: 3
[INFO]    IDs: 0x16fad3dc, 0x12345678, 0xabcdef01
[INFO]    Throttle: 1800s (30min)
```

### Logs d'envoi d'alertes

```
[INFO] 📢 Envoi alerte vigilance à 3 nœud(s)
[DEBUG]    Message: 🟠 VIGILANCE ORANGE...
[DEBUG]    → 0x16fad3dc: Envoi DM...
[INFO] ✅ Alerte envoyée à 0x16fad3dc
[INFO] 📊 Alerte vigilance: 3/3 envoyées
```

### Logs de throttling

```
[DEBUG]    Alerte vigilance throttlée pour 0x16fad3dc: 1200s restants
[DEBUG]    → 0x16fad3dc: Throttlé
```

## Statistiques

Le gestionnaire d'alertes collecte des statistiques :

```python
# Via Python
stats = mesh_alert_manager.get_stats()
# {'subscribed_nodes': 3,
#  'total_alerts_sent': 12,
#  'alerts_throttled': 5,
#  'active_history_entries': 6}

# Rapport de statut
report = mesh_alert_manager.get_status_report(compact=False)
print(report)
```

**Sortie** :
```
📢 STATUT ALERTES MESH
Nœuds abonnés: 3
Total alertes envoyées: 12
Alertes throttlées: 5
Historique actif: 6 entrées

Nœuds abonnés:
  - 0x16fad3dc
  - 0x12345678
  - 0xabcdef01
```

## Tests

### Exécuter les tests

```bash
# Tous les tests (9 test cases)
python test_mesh_alert_manager.py

# Résultat attendu:
# ✅ TOUS LES TESTS RÉUSSIS
```

### Tests couverts

1. ✅ Initialisation du gestionnaire
2. ✅ Envoi d'alerte basique
3. ✅ Throttling des alertes
4. ✅ Types d'alertes différents
5. ✅ Flag force pour ignorer throttling
6. ✅ Envoi à plusieurs nœuds
7. ✅ Liste de nœuds vide
8. ✅ Statistiques
9. ✅ Rapports de statut

## Démonstration

```bash
# Lancer la démonstration interactive
python demo_mesh_alerts.py
```

La démo montre :
- Configuration des alertes
- Envoi d'alerte vigilance
- Envoi d'alerte éclairs
- Comportement du throttling

## Architecture

### Composants

```
┌─────────────────────────────────────────────┐
│           periodic_cleanup()                │
│         (toutes les 5 minutes)              │
└───────────┬─────────────────────────────────┘
            │
    ┌───────▼─────────┐    ┌──────────────┐
    │ VigilanceMonitor │    │ BlitzMonitor │
    │                  │    │              │
    │ check_vigilance()│    │ check_and_   │
    │ should_alert()   │    │ report()     │
    └───────┬──────────┘    └──────┬───────┘
            │                      │
            │  Critical            │  Threshold
            │  detected            │  exceeded
            │                      │
    ┌───────▼──────────────────────▼───────┐
    │     send_mesh_alert()                │
    │                                       │
    │     MeshAlertManager                 │
    │   - Throttling per node/type         │
    │   - Statistics tracking              │
    │   - Multiple nodes support           │
    └───────┬───────────────────────────────┘
            │
            │ For each subscribed node
            │
    ┌───────▼─────────┐
    │  MessageSender  │
    │  send_single()  │
    │                 │
    │  - Error retry  │
    │  - DM routing   │
    └─────────────────┘
            │
            ▼
    Meshtastic Interface
```

### Flux de traitement

1. **Détection** : Monitors vérifient périodiquement les conditions
2. **Évaluation** : Détermination si alerte nécessaire (seuils, throttle)
3. **Génération** : Création du message compact (< 180 chars)
4. **Envoi** : Distribution aux nœuds via MeshAlertManager
5. **Tracking** : Enregistrement pour throttling et stats

## Dépannage

### Les alertes ne sont pas envoyées

**Vérifier** :
1. `MESH_ALERTS_ENABLED = True` dans config.py
2. `MESH_ALERT_SUBSCRIBED_NODES` contient des IDs valides
3. Les monitors sont activés (VIGILANCE_ENABLED, BLITZ_ENABLED)
4. Logs : chercher "MeshAlertManager initialisé"

### Alertes trop fréquentes

**Solution** : Augmenter `MESH_ALERT_THROTTLE_SECONDS`

```python
# Dans config.py
MESH_ALERT_THROTTLE_SECONDS = 3600  # 1 heure au lieu de 30min
```

### Alertes éclairs jamais envoyées

**Vérifier** :
1. Seuil : `BLITZ_MESH_ALERT_THRESHOLD`
2. Rayon : `BLITZ_RADIUS_KM` (trop petit ?)
3. Position GPS du node configurée
4. Logs : "⚡ Blitz check: X éclairs détectés"

### Un nœud ne reçoit pas les alertes

**Vérifier** :
1. ID du nœud correct dans `MESH_ALERT_SUBSCRIBED_NODES`
2. Nœud accessible (pas hors de portée)
3. Logs : chercher "→ 0xXXXXXXXX: Throttlé" ou erreurs d'envoi

## Limitations

### Format LoRa

- **180 caractères max** : Messages tronqués si plus longs
- **Pas de markdown** : Format texte simple uniquement
- **Emojis limités** : Certains emojis occupent plusieurs chars

### Throttling

- **Par type + nœud** : Pas de throttling global tous nœuds
- **Pas de priorité** : Toutes les alertes sont égales
- **Pas de queue** : Alertes throttlées sont perdues (pas mises en attente)

### Fiabilité

- **Best effort** : Pas de garantie de livraison (LoRa)
- **Pas d'accusé de réception** : Pas de confirmation lecture
- **Pas de retry automatique** : Si échec, alerte perdue

## Extensions futures possibles

### Fonctionnalités potentielles

- [ ] Priorités d'alertes (urgent vs normal)
- [ ] Queue d'attente pour alertes throttlées
- [ ] Confirmation de réception (ACK)
- [ ] Alertes personnalisées par nœud
- [ ] Alertes conditionnelles (ex: éclairs à moins de X km)
- [ ] Intégration avec d'autres monitors (température, CPU, etc.)

## Support

### Documentation supplémentaire

- `CLAUDE.md` : Guide pour développeurs AI
- `config.py.sample` : Exemple de configuration complète
- Source code :
  - `mesh_alert_manager.py` : Gestionnaire principal
  - `vigilance_monitor.py` : Monitor vigilance
  - `blitz_monitor.py` : Monitor éclairs
  - `main_bot.py` : Intégration

### Tests et exemples

- `test_mesh_alert_manager.py` : Suite de tests
- `demo_mesh_alerts.py` : Démonstration interactive

---

**Version** : 1.0
**Dernière mise à jour** : 2025-01-30
**Auteur** : GitHub Copilot
**Projet** : Tigro14/meshbot
