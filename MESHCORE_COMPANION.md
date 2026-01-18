# Mode MeshCore Companion - Guide de développement

## Vue d'ensemble

Le mode MeshCore Companion permet au bot de fonctionner sans connexion Meshtastic, en utilisant uniquement une connexion série avec un device MeshCore. Ce mode est conçu pour les utilisateurs qui veulent utiliser le bot avec MeshCore plutôt que Meshtastic.

## Architecture

### Composants clés

1. **`meshcore_serial_interface.py`**
   - `MeshCoreSerialInterface` : Interface série pour communication MeshCore
   - `MeshCoreStandaloneInterface` : Interface factice pour tests sans radio

2. **`main_bot.py`**
   - Support de mode optionnel Meshtastic via `MESHTASTIC_ENABLED`
   - Support de mode MeshCore via `MESHCORE_ENABLED`
   - Gestion des trois modes : Meshtastic, MeshCore, Standalone

3. **`message_router.py`**
   - Flag `companion_mode` pour filtrer les commandes
   - Liste `companion_commands` des commandes supportées
   - Message d'erreur explicite pour commandes désactivées

## Protocole MeshCore (implémentation actuelle)

L'implémentation actuelle supporte **deux formats** de communication MeshCore :

### 1. Format texte (simple)

Format texte pour compatibilité et tests rapides.

**Format de réception (DM entrant)** :
```
DM:<sender_id_hex>:<message_text>
```

**Exemple** :
```
DM:12345678:/bot hello
```

**Format d'envoi (DM sortant)** :
```
SEND_DM:<destination_id_hex>:<message_text>\n
```

### 2. Format binaire (protobuf)

Support automatique des données binaires protobuf. Lorsque des données binaires sont reçues :
- Détection automatique (échec décodage UTF-8)
- Logging différencié : `[MESHCORE-BINARY]` vs `[MESHCORE-TEXT]`
- Empêche l'affichage de "blob data" dans les logs
- Stub pour décodage protobuf (à implémenter selon spec MeshCore)

**Logs différenciés** :
```
📨 [MESHCORE-TEXT] Reçu: DM:12345678:/help
📨 [MESHCORE-BINARY] Reçu: 156 octets (protobuf)
📬 [MESHCORE-DM] De: 0x12345678 | Message: /help
📤 [MESHCORE-DM] Envoyé à 0x12345678: Voici l'aide...
```

### Protocole binaire MeshCore

Le protocole réel de MeshCore utilise un format binaire avec :
- **Framing** : Messages encapsulés avec longueur et CRC
- **Command codes** : Codes de commande pour différentes opérations
  - `CMD_SEND_TXT_MSG` : Envoyer un message texte
  - `CMD_RCV_TXT_MSG` : Recevoir un message texte
  - Autres codes pour configuration, statut, etc.

**TODO** : Adapter l'implémentation pour supporter le protocole binaire réel.

## Adaptation du protocole

Pour adapter l'implémentation au protocole binaire MeshCore :

### 1. Modifier `_read_loop()` dans `MeshCoreSerialInterface`

```python
def _read_loop(self):
    """Boucle de lecture des messages série (protocole binaire)"""
    buffer = bytearray()
    
    while self.running and self.serial and self.serial.is_open:
        try:
            # Lire les octets disponibles
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting)
                buffer.extend(data)
                
                # Parser le buffer pour extraire les frames complètes
                while True:
                    frame = self._parse_meshcore_frame(buffer)
                    if frame is None:
                        break  # Pas de frame complète
                    
                    # Traiter la frame
                    self._process_meshcore_frame(frame)
            
            time.sleep(0.01)
            
        except Exception as e:
            error_print(f"❌ Erreur lecture série MeshCore: {e}")
```

### 2. Implémenter le parser de frames

```python
def _parse_meshcore_frame(self, buffer):
    """
    Parse une frame MeshCore du buffer
    
    Format frame MeshCore (exemple) :
    - 2 bytes : Magic (0xAA55)
    - 1 byte  : Command code
    - 2 bytes : Length (little-endian)
    - N bytes : Payload
    - 2 bytes : CRC16
    
    Returns:
        dict: Frame parsée ou None si incomplète
    """
    if len(buffer) < 7:  # Taille minimale
        return None
    
    # Vérifier magic
    if buffer[0] != 0xAA or buffer[1] != 0x55:
        # Resynchroniser
        try:
            magic_pos = buffer.index(b'\xAA\x55', 1)
            del buffer[:magic_pos]
        except ValueError:
            buffer.clear()
        return None
    
    # Lire la longueur
    length = struct.unpack('<H', buffer[3:5])[0]
    frame_size = 7 + length  # Magic(2) + Cmd(1) + Len(2) + Payload(N) + CRC(2)
    
    if len(buffer) < frame_size:
        return None  # Frame incomplète
    
    # Extraire la frame
    frame_data = bytes(buffer[:frame_size])
    del buffer[:frame_size]
    
    # Vérifier CRC
    calculated_crc = self._calculate_crc16(frame_data[:-2])
    received_crc = struct.unpack('<H', frame_data[-2:])[0]
    
    if calculated_crc != received_crc:
        error_print(f"❌ CRC invalide (calculé: {calculated_crc:04x}, reçu: {received_crc:04x})")
        return None
    
    # Parser la frame
    command = frame_data[2]
    payload = frame_data[5:-2]
    
    return {
        'command': command,
        'payload': payload
    }
```

### 3. Traiter les frames MeshCore

```python
def _process_meshcore_frame(self, frame):
    """Traite une frame MeshCore reçue"""
    command = frame['command']
    payload = frame['payload']
    
    # CMD_RCV_TXT_MSG = 0x10 (exemple)
    if command == 0x10:
        # Parser le payload du message texte
        # Format (exemple) : 4 bytes sender_id + N bytes message
        sender_id = struct.unpack('<I', payload[:4])[0]
        message = payload[4:].decode('utf-8', errors='ignore')
        
        # Créer un pseudo-packet compatible
        packet = {
            'from': sender_id,
            'to': self.localNode.nodeNum,
            'decoded': {
                'portnum': 'TEXT_MESSAGE_APP',
                'payload': message.encode('utf-8')
            }
        }
        
        # Appeler le callback
        if self.message_callback:
            self.message_callback(packet, None)
```

### 4. Envoyer des messages via MeshCore

```python
def sendText(self, message, destinationId=None):
    """Envoie un message texte via MeshCore (protocole binaire)"""
    if destinationId is None:
        return False  # Pas de broadcast en mode companion
    
    try:
        # Construire le payload
        payload = struct.pack('<I', destinationId) + message.encode('utf-8')
        
        # Construire la frame
        frame = self._build_meshcore_frame(
            command=0x11,  # CMD_SEND_TXT_MSG (exemple)
            payload=payload
        )
        
        # Envoyer
        self.serial.write(frame)
        debug_print(f"📤 MeshCore envoyé: {len(frame)} octets")
        return True
        
    except Exception as e:
        error_print(f"❌ Erreur envoi message MeshCore: {e}")
        return False

def _build_meshcore_frame(self, command, payload):
    """Construit une frame MeshCore"""
    # Magic + Command + Length + Payload
    frame = bytearray([0xAA, 0x55, command])
    frame.extend(struct.pack('<H', len(payload)))
    frame.extend(payload)
    
    # Ajouter CRC
    crc = self._calculate_crc16(frame)
    frame.extend(struct.pack('<H', crc))
    
    return bytes(frame)
```

## Configuration

### Mode MeshCore uniquement

```python
# config.py
MESHTASTIC_ENABLED = False
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"
```

### Mode hybride (pour tests)

```python
# Possibilité de garder Meshtastic actif pour certaines fonctions
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'serial'
SERIAL_PORT = "/dev/ttyACM0"  # Meshtastic

# MeshCore en parallèle
MESHCORE_ENABLED = True
MESHCORE_SERIAL_PORT = "/dev/ttyUSB0"  # MeshCore
```

**Note** : Le mode hybride n'est pas encore implémenté et nécessiterait des modifications supplémentaires.

## Tests

### Exécuter les tests

```bash
cd /home/runner/work/meshbot/meshbot
python3 test_meshcore_companion.py
```

### Tests disponibles

1. `test_meshcore_interface_creation` - Création de l'interface
2. `test_standalone_interface_creation` - Interface standalone
3. `test_message_router_companion_mode` - Filtrage des commandes
4. `test_meshcore_message_parsing` - Parsing des messages
5. `test_companion_commands_filtering` - Vérification des erreurs
6. `test_config_meshcore_mode` - Configuration

## Commandes supportées

### ✅ Commandes disponibles en mode companion

| Commande | Description | Dépendances |
|----------|-------------|-------------|
| `/bot <question>` | Chat avec IA | Llama.cpp |
| `/weather [ville]` | Prévisions météo | wttr.in API |
| `/rain [ville] [jours]` | Graphiques pluie | wttr.in API |
| `/power` | Télémétrie ESPHome | ESPHome (optionnel) |
| `/sys` | Infos système | Aucune |
| `/help` | Aide | Aucune |
| `/blitz` | Éclairs détectés | BlitzMonitor (optionnel) |
| `/vigilance` | Vigilance météo | VigilanceMonitor (optionnel) |

### ❌ Commandes désactivées (Meshtastic requis)

| Commande | Raison |
|----------|--------|
| `/nodes` | Nécessite node database Meshtastic |
| `/my` | Nécessite interface Meshtastic pour signaux |
| `/trace` | Nécessite traceroute mesh |
| `/neighbors` | Nécessite NEIGHBORINFO_APP packets |
| `/info` | Nécessite node metadata Meshtastic |
| `/stats`, `/top`, `/histo` | Nécessite traffic monitor Meshtastic |
| `/keys`, `/propag`, `/hop` | Fonctionnalités réseau Meshtastic |
| `/db` | Base de données trafic Meshtastic |

## Dépannage

### Erreur "No module named 'serial'"

```bash
pip install pyserial
```

### Port série introuvable

```bash
# Lister les ports série disponibles
ls -la /dev/tty* | grep USB

# Vérifier les permissions
sudo usermod -a -G dialout $USER
# Déconnecter/reconnecter pour appliquer
```

### Messages non reçus

1. Vérifier le baudrate (défaut: 115200)
2. Vérifier le format de protocole (texte vs binaire)
3. Activer DEBUG_MODE pour logs détaillés
4. Vérifier les câbles et connexions

### Commande refusée en mode companion

C'est normal ! Seules les commandes listées dans `companion_commands` sont supportées.
Le bot affichera un message explicite avec la liste des commandes disponibles.

## Évolutions futures

1. **Support protocole binaire MeshCore complet**
   - Implémenter le framing et CRC
   - Support de tous les codes de commande
   - Gestion des acknowledgements

2. **Mode hybride Meshtastic + MeshCore**
   - Deux interfaces simultanées
   - Routage intelligent des commandes
   - Synchronisation des bases de données

3. **Bridge Meshtastic ↔ MeshCore**
   - Relay des messages entre les deux réseaux
   - Traduction des formats
   - Gestion des conflits d'ID

4. **Interface configuration web**
   - Configuration graphique du mode companion
   - Monitoring en temps réel
   - Logs et diagnostics

## Références

- [MeshCore Documentation](https://deepwiki.com/meshcore-dev/MeshCore/)
- [MeshCore Serial Interfaces](https://deepwiki.com/meshcore-dev/MeshCore/9.1-serial-interfaces)
- [Meshtastic Python API](https://meshtastic.org/docs/software/python/cli/)
- [PySerial Documentation](https://pythonhosted.org/pyserial/)
