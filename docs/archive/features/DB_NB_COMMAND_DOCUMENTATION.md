# /db nb - Neighbors Statistics Sub-command

## Overview

The `/db nb` sub-command provides statistical information about the mesh network neighbors data stored in the SQLite database.

## Usage

### Mesh Channel (LoRa)
```
/db nb
```

### Telegram Channel
```
/db nb
/db neighbors
```

## Features

### Mesh Format (Compact - ≤180 chars)
- Total nodes with neighbors
- Total unique neighbor relationships  
- Total database entries
- Average neighbors per node

Example output:
```
👥 Voisinage:
6nœuds 16liens
16entrées
Moy:2.7v/nœud
```

### Telegram Format (Detailed)
- Total database entries
- Number of unique nodes with neighbors
- Number of unique relationships
- Average neighbors per node
- Time range (oldest/newest data)
- **Top 5 nodes** with most neighbors

Example output:
```
👥 **STATISTIQUES DE VOISINAGE**
==================================================

📊 **Données globales:**
• Total entrées: 16
• Nœuds avec voisins: 6
• Relations uniques: 16
• Moyenne voisins/nœud: 2.67

⏰ **Plage temporelle:**
• Plus ancien: 04/12 14:16
• Plus récent: 04/12 15:01
• Durée: 0.7 heures

🏆 **Top 5 nœuds (plus de voisins):**
• !16fad3dc: 5 voisins
• !12345678: 4 voisins
• !87654321: 3 voisins
• !abcdef12: 2 voisins
• !22222222: 1 voisins
```

## Edge Cases

### Empty Database
**Mesh:**
```
👥 Aucune donnée voisinage
```

**Telegram:**
```
👥 **AUCUNE DONNÉE DE VOISINAGE**

La table neighbors est vide. Les données de voisinage sont collectées:
• Depuis les paquets NEIGHBORINFO_APP reçus
• Depuis le serveur MQTT (si activé)

Vérifiez que:
• Les nœuds mesh ont neighborinfo activé
• Le bot reçoit bien les paquets
• Le collecteur MQTT fonctionne (si configuré)
```

### Missing Table
If the neighbors table doesn't exist in the database:

**Mesh:**
```
❌ Table neighbors inexistante
```

**Telegram:**
```
❌ **Table neighbors inexistante**

La table de voisinage n'est pas disponible dans cette base de données.
```

## Implementation Details

### Database Schema
The command queries the `neighbors` table with the following structure:
```sql
CREATE TABLE neighbors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    node_id TEXT NOT NULL,
    neighbor_id TEXT NOT NULL,
    snr REAL,
    last_rx_time INTEGER,
    node_broadcast_interval INTEGER
)
```

### SQL Queries Used

1. **Total entries:**
   ```sql
   SELECT COUNT(*) FROM neighbors
   ```

2. **Unique nodes:**
   ```sql
   SELECT COUNT(DISTINCT node_id) FROM neighbors
   ```

3. **Unique relationships:**
   ```sql
   SELECT COUNT(DISTINCT node_id || '-' || neighbor_id) FROM neighbors
   ```

4. **Time range:**
   ```sql
   SELECT MIN(timestamp), MAX(timestamp) FROM neighbors
   ```

5. **Top 5 nodes (Telegram only):**
   ```sql
   SELECT node_id, COUNT(DISTINCT neighbor_id) as neighbor_count
   FROM neighbors
   GROUP BY node_id
   ORDER BY neighbor_count DESC
   LIMIT 5
   ```

## Help Integration

The new sub-command is documented in both help formats:

### Mesh Help
```
🗄️ /db [cmd]
s=stats i=info
nb=neighbors
clean=nettoyage
v=vacuum pw=weather
```

### Telegram Help
```
🗄️ BASE DE DONNÉES - OPTIONS

Sous-commandes:
• stats - Statistiques DB
• info - Informations détaillées
• nb - Stats voisinage (neighbors)
• clean [hours] - Nettoyer données anciennes
• vacuum - Optimiser DB (VACUUM)

Exemples:
• /db stats - Stats DB
• /db nb - Stats voisinage
• /db clean 72 - Nettoyer > 72h
• /db vacuum - Optimiser

Raccourcis: s, i, v, nb
```

## Files Modified

1. **handlers/command_handlers/db_commands.py**
   - Added `_get_neighbors_stats(channel='mesh')` method
   - Updated `handle_db()` routing to support 'nb' and 'neighbors'
   - Updated `_get_help()` to document the new sub-command

2. **telegram_bot/commands/db_commands.py**
   - Updated `get_db_response()` to handle 'nb' and 'neighbors' sub-commands
   - Added logging for the new operation

## Testing

Run the test suite:
```bash
python3 test_db_neighbors_stats.py
```

Run the demonstration:
```bash
python3 demo_db_neighbors.py
```

## Use Cases

1. **Network Health Monitoring**: Quickly see how many nodes are connected and average connectivity
2. **Topology Analysis**: Identify hub nodes (nodes with many neighbors)
3. **Data Quality Check**: Verify that neighbor data is being collected properly
4. **Troubleshooting**: Check if neighbors table has recent data
5. **Network Planning**: Understand mesh density and coverage

## Related Commands

- `/neighbors [node]` - View detailed neighbor list for specific nodes
- `/db stats` - General database statistics
- `/db info` - Detailed database schema information
- `/nodes` - List all nodes in the network

## Notes

- The command respects the 180-character limit for mesh/LoRa output
- Telegram format provides much more detail including the Top 5 hub nodes
- Statistics are based on **all** data in the neighbors table (not time-filtered)
- Node names are resolved for the Top 5 display in Telegram format
- The command is throttled like all other `/db` sub-commands
