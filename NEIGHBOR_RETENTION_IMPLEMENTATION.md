# Neighbor Data Retention Extension - Implementation Summary

## Problem Statement

The user reported that their network map (`map.html`) was nearly empty despite having a SQLite database full of neighbor relationships. The `/db nb` command showed:
- **1,278 total entries**
- **18 nodes with neighbors**
- **178 unique relationships**
- **83.6 hours** of data in the database

However, the export script (`infoup_db.sh`) was only retrieving:
- **106 neighbor entries**
- **14 nodes with neighbors**

## Root Cause Analysis

The issue was caused by a mismatch between:
1. **Database retention**: The periodic cleanup was deleting neighbor data older than **48 hours**
2. **Export window**: The export script was only looking at the last **48 hours** of data
3. **Actual needs**: For a well-populated network map, **30 days** of retention is more appropriate

The 48-hour retention period was too short for networks where:
- Nodes don't broadcast frequently
- Neighbor relationships change slowly
- Users want to see historical network topology

## Solution Implemented

### 1. Configuration Option Added (`config.py.sample`)

```python
# Configuration rétention des données de voisinage dans SQLite
# Durée de conservation des données de voisinage (en heures)
# 720h = 30 jours - Recommandé pour avoir une carte réseau bien peuplée
# 48h = 2 jours - Valeur historique (peut donner une carte vide)
NEIGHBOR_RETENTION_HOURS = 720  # 30 jours de rétention
```

**Benefits:**
- ✅ Configurable retention period
- ✅ Clear documentation with examples
- ✅ Default value of 720h (30 days) provides better results
- ✅ Can be adjusted per installation needs

### 2. Main Bot Updated (`main_bot.py`)

**Before:**
```python
# Nettoyage des anciennes données SQLite (> 48h)
self.traffic_monitor.cleanup_old_persisted_data(hours=48)
```

**After:**
```python
# Nettoyage des anciennes données SQLite
# Utilise NEIGHBOR_RETENTION_HOURS pour les voisins (config.py)
retention_hours = globals().get('NEIGHBOR_RETENTION_HOURS', 48)
self.traffic_monitor.cleanup_old_persisted_data(hours=retention_hours)
```

**Benefits:**
- ✅ Uses configuration value instead of hardcoded 48h
- ✅ Falls back to 48h if config not set (backward compatible)
- ✅ Single place to control retention policy

### 3. Export Script Updated (`map/infoup_db.sh`)

**Changed neighbor export from 48h to 720h:**
```bash
# Before:
EXPORT_CMD="/home/dietpi/bot/map/export_neighbors_from_db.py $DB_PATH 48"

# After:
EXPORT_CMD="/home/dietpi/bot/map/export_neighbors_from_db.py $DB_PATH 720"
```

**Changed node export from 48h to 720h:**
```bash
# Before:
/home/dietpi/bot/map/export_nodes_from_db.py "$NODE_NAMES_FILE" "$DB_PATH" 48 > /tmp/info_temp.json

# After:
# Utilise 720 heures (30 jours) pour cohérence avec export neighbors
/home/dietpi/bot/map/export_nodes_from_db.py "$NODE_NAMES_FILE" "$DB_PATH" 720 > /tmp/info_temp.json
```

**Benefits:**
- ✅ Consistent 30-day export window for all data
- ✅ More complete network topology visualization
- ✅ Better historical perspective on network evolution

## Verification and Testing

### Test Suite Created (`test_neighbor_retention_config.py`)

Automated tests verify:
1. ✅ `config.py.sample` contains `NEIGHBOR_RETENTION_HOURS = 720`
2. ✅ `main_bot.py` uses the configuration value correctly
3. ✅ `map/infoup_db.sh` exports 720h for both neighbors and nodes
4. ✅ Documentation is clear and complete

**All tests passed successfully!**

## Expected Results

After deploying these changes, users should see:

### Before (48h retention):
```
📊 Statistiques finales:
   • Nœuds avec voisins: 14/14
   • Total entrées voisins: 106
   • Moyenne voisins/nœud: 7.6
```

### After (30 days retention):
```
📊 Statistiques finales:
   • Nœuds avec voisins: 18+/18+
   • Total entrées voisins: 178+
   • Moyenne voisins/nœud: 9.89+
```

**Note:** Actual numbers will depend on network activity and when the cleanup runs next.

## Deployment Instructions

### For New Installations:
1. Use the updated `config.py.sample` as template
2. `NEIGHBOR_RETENTION_HOURS = 720` will be the default

### For Existing Installations:
1. Add this line to your `config.py`:
   ```python
   NEIGHBOR_RETENTION_HOURS = 720  # 30 jours de rétention
   ```
2. Restart the bot: `sudo systemctl restart meshbot`
3. Wait for the next periodic cleanup (runs every 5 minutes)
4. Run the map update script: `cd /home/dietpi/bot/map && ./infoup_db.sh`

### Customization:
You can adjust the retention period based on your needs:
- **48h** (2 days) - Minimal retention, lower disk usage
- **168h** (7 days) - Weekly view
- **720h** (30 days) - Default, recommended for most users
- **2160h** (90 days) - Quarterly view
- **8760h** (365 days) - Yearly archive

## Impact Analysis

### Positive Impacts:
- ✅ More populated and useful network maps
- ✅ Better visualization of network topology over time
- ✅ Configurable to suit different needs
- ✅ No breaking changes (backward compatible)
- ✅ Minimal code changes (surgical approach)

### Considerations:
- 📊 Slightly larger SQLite database (proportional to retention)
- 💾 For 30-day retention vs 48h: estimate 15x database size
- 🔄 Database cleanup and VACUUM will take slightly longer

### Database Size Estimation:
With typical mesh network activity:
- 48h retention: ~5-20 MB
- 30 days retention: ~75-300 MB
- Still very manageable on modern hardware

## Files Modified

1. **`config.py.sample`** - Configuration template with new option
2. **`main_bot.py`** - Uses configuration for cleanup
3. **`map/infoup_db.sh`** - Export scripts use 30-day window
4. **`test_neighbor_retention_config.py`** - Test suite (NEW)
5. **`CLAUDE.md`** - Documentation update

## Related Commands

Users can monitor neighbor data with:
```bash
# Check neighbor statistics
/db nb

# Force map regeneration
cd /home/dietpi/bot/map && ./infoup_db.sh

# View database size
ls -lh /home/dietpi/bot/traffic_history.db

# Manual database cleanup (if needed)
/db clean 720  # Keep only 30 days
```

## References

- Issue discussion: User reported empty maps despite full database
- Solution approach: Extend retention from 48h to 30 days
- Implementation: Configurable retention with sensible defaults
- Testing: Automated test suite validates all changes

---

**Implementation Status**: ✅ Complete and Tested
**Date**: December 2025
**Impact**: Low risk, high value
