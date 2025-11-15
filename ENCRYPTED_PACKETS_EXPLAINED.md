# Comprendre les Paquets Encryptés dans Meshtastic

## ⚠️ Confusion Fréquente : DM ≠ Encrypté

### Messages Privés (DM - Direct Messages)
- **Définition** : Message envoyé à un nœud spécifique (pas broadcast)
- **Indicateur** : `to_id != 0xFFFFFFFF` (pas "tous")
- **Canal** : Utilise le même canal que les broadcasts (Primary par défaut)
- **Chiffrement** : **NON** - même clé PSK que le canal Primary
- **Visibilité** : Tous les nœuds du canal peuvent décoder le contenu

### Messages Encryptés (Encrypted Packets)
- **Définition** : Paquet utilisant un canal avec une clé PSK différente
- **Indicateur** : Champ `encrypted` présent dans le paquet Meshtastic
- **Canal** : Canal secondaire avec sa propre clé PSK
- **Chiffrement** : **OUI** - clé PSK différente du canal Primary
- **Visibilité** : Seuls les nœuds ayant la clé PSK peuvent décoder

## 📊 Exemples

### Scénario 1 : Message Broadcast sur Primary
```
Type    : BROADCAST
Canal   : Primary (PSK: "AQ==")
To      : 0xFFFFFFFF (tous)
Encrypté: NON
Dans DB : packet_type = 'TEXT_MESSAGE_APP', is_encrypted = 0
```

### Scénario 2 : Message DM sur Primary
```
Type    : DIRECT MESSAGE (DM)
Canal   : Primary (PSK: "AQ==")
To      : 0x12345678 (nœud spécifique)
Encrypté: NON (même clé que Primary)
Dans DB : packet_type = 'TEXT_MESSAGE_APP', is_encrypted = 0
```

### Scénario 3 : Message sur Canal Secondaire
```
Type    : BROADCAST ou DM
Canal   : Secondary (PSK: "xyz123abc==")
To      : 0xFFFFFFFF ou nœud spécifique
Encrypté: OUI (clé PSK différente)
Dans DB : packet_type = 'ENCRYPTED', is_encrypted = 1
```

## 🔍 Comment le Bot Détecte les Paquets Encryptés

### Code de Détection (`traffic_monitor.py` lignes 238-244)

```python
if 'decoded' in packet:
    # Paquet décodable (clé PSK connue)
    decoded = packet['decoded']
    packet_type = decoded.get('portnum', 'UNKNOWN')
    # → TEXT_MESSAGE_APP, POSITION_APP, etc.

elif 'encrypted' in packet:
    # Paquet encrypté (clé PSK inconnue)
    is_encrypted = True
    packet_type = 'ENCRYPTED'
    # → Impossible de lire le contenu
```

### Résultat dans la Base de Données

| Situation | `packet_type` | `is_encrypted` | `message` |
|-----------|---------------|----------------|-----------|
| Broadcast Primary | TEXT_MESSAGE_APP | 0 | "Hello world" |
| DM Primary | TEXT_MESSAGE_APP | 0 | "Private msg" |
| Broadcast Secondary (clé connue) | TEXT_MESSAGE_APP | 0 | "Secondary" |
| Broadcast Secondary (clé inconnue) | ENCRYPTED | 1 | NULL |

## 🚀 Comment Voir des Paquets Encryptés

### Option 1 : Configurer un Canal Secondaire avec Clé Différente

1. **Sur votre nœud source** (celui qui envoie) :
   ```
   # Ajouter un canal secondaire
   Channel Index: 1
   Name: "Private"
   PSK: [générer une nouvelle clé]
   Role: SECONDARY
   ```

2. **Sur le nœud bot** (celui qui écoute) :
   - Ne PAS configurer ce canal
   - Le bot verra les paquets comme `ENCRYPTED`

3. **Envoyer un message sur le canal secondaire**
   - Le bot recevra un paquet avec `is_encrypted = 1`

### Option 2 : Écouter un Réseau avec Canaux Multiples

Si votre réseau mesh a des nœuds utilisant différents canaux :
- Les paquets des canaux que le bot ne connaît pas apparaîtront comme `ENCRYPTED`

## 🔧 Diagnostic

### Vérifier ce que le Bot Collecte

```bash
# Voir l'état de la base de données
python3 check_encrypted_packets.py

# Naviguer dans les paquets
python3 browse_traffic_db.py
# Touche 'e' pour filtrer les paquets encryptés
```

### Comprendre Pourquoi Vous Ne Voyez Pas de Paquets Encryptés

1. **Tous vos nœuds utilisent le même canal Primary**
   - → Tous les paquets sont décodables
   - → Aucun n'apparaît comme `ENCRYPTED`

2. **Les DM ne sont pas encryptés**
   - → Même s'ils sont privés, ils utilisent la clé Primary
   - → Le bot peut les lire

3. **Le bot n'est pas en cours d'exécution**
   - → Aucun paquet n'est collecté
   - → La base reste vide

## 📝 Logs de Debug

### Activer les Logs Détaillés

```python
# Dans config.py
DEBUG_MODE = True
```

### Vérifier les Logs du Bot

```bash
# Si systemd
journalctl -u meshbot -f

# Ou dans le terminal
python3 main_script.py --debug
```

### Ce que Vous Devriez Voir

```
# Paquet décodable (non-encrypté)
📦 Paquet reçu: TEXT_MESSAGE_APP from !12345678
   Message: "Hello world"

# Paquet encrypté (clé inconnue)
🔐 Paquet encrypté reçu from !abcdef12
   Type: ENCRYPTED (cannot decode)
```

## ⚙️ Configuration Exemple

### Nœud 1 (Bot) - Écoute sur Primary Seulement

```yaml
channels:
  - index: 0
    name: "Primary"
    psk: "AQ=="  # Clé par défaut
    role: PRIMARY
```

### Nœud 2 - Envoie sur Secondary

```yaml
channels:
  - index: 0
    name: "Primary"
    psk: "AQ=="
    role: PRIMARY

  - index: 1
    name: "Private"
    psk: "xyz123abc=="  # Clé différente
    role: SECONDARY
```

Résultat : Le bot verra les messages du Nœud 2 sur le canal Secondary comme **ENCRYPTED** ✅

## 🎯 Conclusion

**Pour voir des paquets encryptés dans votre base de données :**

1. ✅ **Démarrer le bot** pour qu'il collecte des paquets
2. ✅ **Configurer des canaux secondaires** avec des clés PSK différentes
3. ✅ **Envoyer des messages** sur ces canaux secondaires
4. ❌ **Ne PAS** s'attendre à ce que les DM soient encryptés (ils ne le sont pas)

**Les DM sont privés mais pas encryptés - c'est une différence importante !**

---

**Dernière mise à jour** : 2025-11-15
