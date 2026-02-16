# Guide de Migration - Architecture Single-Node

Ce guide explique comment migrer votre bot Meshtastic depuis l'architecture multi-nodes vers la nouvelle architecture single-node simplifiée.

## Qu'est-ce qui change ?

### Ancienne architecture (Legacy - Toujours supportée)
- **Deux connexions simultanées** : Serial (tigrobot) + TCP optionnel (tigrog2)
- Les commandes sont traitées uniquement via Serial par défaut
- `PROCESS_TCP_COMMANDS` permet d'activer aussi TCP
- Configuration complexe avec deux nodes

### Nouvelle architecture (Recommandée)
- **Une seule connexion** : SOIT Serial SOIT TCP
- Configuration simplifiée avec `CONNECTION_MODE`
- Toutes les commandes passent par l'interface unique
- Plus facile à comprendre et maintenir

## Migration vers Single-Node

### Option 1 : Rester en mode Serial (recommandé pour la plupart)

Si vous utilisez actuellement un node connecté en USB/UART :

1. **Éditez `config.py`**
   ```python
   # Nouvelle section (ajouter en haut du fichier)
   CONNECTION_MODE = 'serial'
   SERIAL_PORT = "/dev/ttyACM0"  # Votre port actuel
   
   # Ancienne configuration (garder pour compatibilité)
   # PROCESS_TCP_COMMANDS = False  # Pas utilisé en mode single-node
   ```

2. **C'est tout !** Le bot continuera de fonctionner normalement.

### Option 2 : Migrer vers TCP

Si vous voulez utiliser votre node ROUTER en WiFi/Ethernet :

1. **Préparer le node**
   - Vérifier que le node est en mode ROUTER
   - Configurer WiFi/Ethernet
   - Noter l'adresse IP (ex: 192.168.1.38)

2. **Éditez `config.py`**
   ```python
   # Nouvelle section (ajouter en haut du fichier)
   CONNECTION_MODE = 'tcp'
   TCP_HOST = "192.168.1.38"  # IP de votre node
   TCP_PORT = 4403
   
   # Ancienne configuration (pas utilisée en mode TCP)
   # SERIAL_PORT = "/dev/ttyACM0"
   # PROCESS_TCP_COMMANDS = False
   ```

3. **Tester la connexion**
   ```bash
   # Vérifier que le port est accessible
   nc -zv 192.168.1.38 4403
   
   # Lancer le bot en mode debug
   python main_script.py --debug
   ```

### Option 3 : Conserver l'architecture Legacy

Si vous voulez garder le système actuel (2 nodes) :

1. **Ne changez rien** - L'architecture legacy reste supportée
2. Laissez `CONNECTION_MODE` non défini ou commenté
3. Continuez d'utiliser `PROCESS_TCP_COMMANDS`

## Tableau de comparaison

| Paramètre | Legacy (Multi-nodes) | Single-Node Serial | Single-Node TCP |
|-----------|---------------------|-------------------|-----------------|
| `CONNECTION_MODE` | Non défini | `'serial'` | `'tcp'` |
| `SERIAL_PORT` | Utilisé | Utilisé | Ignoré |
| `TCP_HOST` / `TCP_PORT` | Non utilisé* | Ignoré | Utilisé |
| `PROCESS_TCP_COMMANDS` | Contrôle TCP | Ignoré | Ignoré |
| Connexions actives | Serial + TCP optionnel | Serial uniquement | TCP uniquement |
| Commandes acceptées | Serial (+ TCP si flag) | Toutes (Serial) | Toutes (TCP) |

\* En mode legacy, TCP est utilisé uniquement pour les requêtes de nodes distants, pas pour les commandes

## Vérification de la configuration

Après migration, vérifiez les logs au démarrage :

### Mode Serial attendu :
```
🤖 Bot Meshtastic-Llama avec architecture modulaire
🔌 Mode Serial: Connexion série /dev/ttyACM0
✅ Interface série créée
✅ Connexion série stable
```

### Mode TCP attendu :
```
🤖 Bot Meshtastic-Llama avec architecture modulaire
🌐 Mode TCP: Connexion à 192.168.1.38:4403
✅ Interface TCP créée
✅ Connexion TCP stable
```

## Dépannage

### Mode Serial

**Erreur : "Permission denied on /dev/ttyACM0"**
```bash
# Ajouter l'utilisateur au groupe dialout
sudo usermod -a -G dialout $USER
# Se déconnecter et reconnecter
```

**Erreur : "Port not found"**
```bash
# Lister les ports disponibles
ls -l /dev/tty* | grep -E "ACM|USB"
```

### Mode TCP

**Erreur : "Connection refused"**
- Vérifier que le node est allumé et connecté au réseau
- Vérifier l'IP avec `ping 192.168.1.38`
- Vérifier le port avec `nc -zv 192.168.1.38 4403`

**Erreur : "Connection timeout"**
- Vérifier le firewall du Raspberry Pi
- Vérifier que le node a bien le WiFi activé
- Essayer de se connecter avec l'app Meshtastic pour valider l'IP

## Retour en arrière

Si vous voulez revenir à l'ancienne configuration :

1. Commenter ou supprimer la ligne `CONNECTION_MODE`
2. Restaurer votre ancienne configuration
3. Redémarrer le bot

## Support

Pour plus d'aide :
- Voir `config.serial.example` pour un exemple de configuration Serial
- Voir `config.tcp.example` pour un exemple de configuration TCP
- Consulter README.md pour la documentation complète
- Ouvrir une issue GitHub si problème
