# /db nb Command - Usage Examples

## Quick Reference

```bash
# Mesh (LoRa)
/db nb

# Telegram (can also use full word)
/db nb
/db neighbors
```

## Example Outputs

### 1. Mesh Channel (Compact Format)

**Command:** `/db nb`

**Output:**
```
👥 Voisinage:
6nœuds 16liens
16entrées
Moy:2.7v/nœud
```

**Character count:** 51 characters (well under 180 limit)

### 2. Telegram Channel (Detailed Format)

**Command:** `/db nb` or `/db neighbors`

**Output:**
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

### 3. Empty Database

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

## Help Text

### Mesh Help
```
/db

Output:
🗄️ /db [cmd]
s=stats i=info
nb=neighbors
clean=nettoyage
v=vacuum pw=weather
```

### Telegram Help
```
/db

Output:
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

## Comparison with /neighbors Command

| Feature | `/db nb` | `/neighbors` |
|---------|----------|-------------|
| **Purpose** | Database statistics | Node-specific neighbor list |
| **Shows** | Overall counts, averages, top 5 | Detailed neighbor info per node |
| **Filter** | No filtering | Can filter by node name/ID |
| **Format** | Statistics summary | List of neighbors with SNR |
| **Use Case** | Health check, overview | Troubleshooting specific node |

### Example Workflow

1. **Check overall health:** `/db nb`
   - See how many nodes have neighbors
   - Check average connectivity

2. **Investigate hub node:** `/neighbors tigrog2`
   - See detailed neighbor list for tigrog2
   - Check signal strengths (SNR)

3. **Verify data collection:** `/db nb`
   - Confirm new neighbor data is being collected
   - Check time range of data

## Technical Details

### What is Counted

- **Total entries:** Every row in the neighbors table
- **Unique nodes:** Distinct node_id values (nodes that have neighbors)
- **Unique relationships:** Distinct node_id + neighbor_id pairs
- **Average:** Unique relationships ÷ Unique nodes

### Time Range

The time range shows:
- **Plus ancien:** Oldest timestamp in neighbors table
- **Plus récent:** Newest timestamp in neighbors table
- **Durée:** Time span between oldest and newest (in hours)

### Top 5 Calculation

For Telegram format only:
1. Group by node_id
2. Count distinct neighbor_id per node
3. Sort descending by count
4. Take top 5
5. Resolve node IDs to names using NodeManager

## Performance Notes

- Query execution is fast even with thousands of entries
- Uses indexed columns (node_id, timestamp)
- No time filtering - shows ALL data in table
- Node name resolution only for Top 5 (minimal overhead)

## Troubleshooting

### "Aucune donnée voisinage"

**Possible causes:**
1. Neighbor info not enabled on mesh nodes
2. Bot not receiving NEIGHBORINFO_APP packets
3. MQTT collector not running (if configured)
4. Database was recently cleaned

**Solutions:**
- Enable neighbor info: `meshtastic --set neighbor_info.enabled true`
- Check bot logs for incoming packets
- Verify MQTT configuration
- Wait for new neighbor data to be collected

### "Table neighbors inexistante"

**Cause:** Database created before neighbors feature was added

**Solution:** 
- Restart bot to trigger database migration
- Or manually create table (see DB_NB_COMMAND_DOCUMENTATION.md)

## Related Documentation

- Full documentation: `DB_NB_COMMAND_DOCUMENTATION.md`
- Unit tests: `test_db_neighbors_stats.py`
- Integration tests: `test_db_nb_integration.py`
- Demo script: `demo_db_neighbors.py`
