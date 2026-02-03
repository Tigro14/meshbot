# Meshcore/Meshtastic Separation - Implementation Summary

## Overview

This document summarizes the implementation of clear separation between **Meshtastic** (radio-learned) and **MeshCore** (CLI-learned) nodes and packets in both `browse_traffic_db.py` and the `/db` command.

## Problem Statement

Previously, the system did not distinguish between:
- **Meshtastic nodes**: Learned via radio NODEINFO_APP packets
- **MeshCore contacts**: Learned via meshcore-cli companion

This made it difficult to:
- Understand the source of node information
- Troubleshoot data collection issues
- Analyze network topology accurately

## Solution

### 1. browse_traffic_db.py Changes

#### New View Structure
The view cycle now includes 5 distinct views instead of 3:

**Before:**
```
packets → messages → nodes → (cycle)
```

**After:**
```
packets → messages → nodes_stats → meshtastic_nodes → meshcore_contacts → (cycle)
```

#### View Descriptions

| View | Icon | Description | Source |
|------|------|-------------|--------|
| `packets` | 📦 | ALL PACKETS | All received packets (any type) |
| `messages` | 💬 | MESSAGES | Public broadcast text messages |
| `nodes_stats` | 🌐 | NODE STATS | Aggregated statistics per node |
| `meshtastic_nodes` | 📡 | MESHTASTIC | Nodes learned via radio (NODEINFO_APP) |
| `meshcore_contacts` | 🔧 | MESHCORE | Contacts learned via meshcore-cli |

#### Display Format

**Meshtastic Nodes View:**
```
Name                 (Short)    !Node ID  Model        GPS Key
═══════════════════════════════════════════════════════════════════
Node1                (ND1)      !12345678 RAK4631      📍 🔑
Node2                (ND2)      !abcdef01 TBEAM        📍  
Unknown              (???)      !deadbeef UNKNOWN        
```

**MeshCore Contacts View:**
```
Name                 (Short)    !Node ID  Model        GPS Key  Source
═════════════════════════════════════════════════════════════════════════
Contact1             (CT1)      !11111111 HELTEC_V3    📍 🔑  meshcore
Contact2             (CT2)      !22222222 RAK4631      📍     companion
```

#### Detail View Example

**Meshtastic Node Details:**
```
═══════════════════════════════════════════════════════════════
📡 MESHTASTIC NODE (learned via radio)
═══════════════════════════════════════════════════════════════
Node ID      : !12345678
Name         : MyMeshNode
Short Name   : MMN
Hardware     : RAK4631
Last Updated : 11-17 14:30

📍 GPS Location:
─────────────────────────────────────────────────────────────
  Latitude   : 47.123456
  Longitude  : 6.789012
  Altitude   : 450 m

🔑 Public Key:
─────────────────────────────────────────────────────────────
  a1b2c3d4e5f6789012345678901234567890123456789012345678901234
  567890
  Length: 32 bytes
```

**MeshCore Contact Details:**
```
═══════════════════════════════════════════════════════════════
🔧 MESHCORE CONTACT (learned via meshcore-cli)
═══════════════════════════════════════════════════════════════
Node ID      : !11111111
Name         : MeshCoreNode
Short Name   : MCN
Hardware     : HELTEC_V3
Source       : meshcore
Last Updated : 11-17 13:45

📍 GPS Location:
─────────────────────────────────────────────────────────────
  Latitude   : 47.234567
  Longitude  : 6.890123
  Altitude   : 520 m

🔑 Public Key:
─────────────────────────────────────────────────────────────
  1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab
  cdef
  Length: 32 bytes
```

### 2. /db Command Enhancements

#### Enhanced /db stats Output

**Mesh Channel (compact):**
```
🗄️ DB: 15.3MB
12543pkt 4251msg
📡MT:45 🔧MC:12
17/11 08:00-17/11 16:30
(8h)
```

**Telegram Channel (detailed):**
```
🗄️ STATISTIQUES BASE DE DONNÉES
══════════════════════════════════════════════════

📊 Taille: 15.32 MB
Fichier: traffic_history.db

📦 Entrées:
• Paquets: 12,543
• Messages publics: 4,251
• Stats nœuds (agrégé): 58

📡 Nœuds (par source):
• Meshtastic (radio): 45
• MeshCore (cli): 12

⏰ Plage temporelle:
• Plus ancien: 17/11 08:00
• Plus récent: 17/11 16:30
• Durée: 8.5 heures
```

#### New /db mt Command

Display all Meshtastic nodes with full details:

**Usage:**
```
/db mt          # Mesh: compact view
/db meshtastic  # Same as above
```

**Output (Telegram):**
```
📡 **TABLE MESHTASTIC NODES**
══════════════════════════════════════════════════

**Statistiques globales:**
• Total nœuds: 45
• Avec GPS: 38
• Avec clé publique: 42

**Plage temporelle:**
• Plus ancien: 17/11 08:00
• Plus récent: 17/11 16:30
• Durée: 8.5 heures

**Nœuds (détails complets):**
══════════════════════════════════════════════════

**MyMeshNode** (15m)
├─ Node ID: `!12345678`
├─ Short: MMN
├─ Model: RAK4631
├─ GPS: 47.123456, 6.789012
│  └─ Alt: 450m
├─ PubKey: `a1b2c3d4...01234567` (32 bytes)
├─ Source: radio (NODEINFO_APP)
└─ Mise à jour: 2025-11-17 14:30:45

[... more nodes ...]
```

#### Updated /db mc Command

Enhanced to clearly indicate MeshCore source:

**Output (Telegram):**
```
📡 **TABLE MESHCORE CONTACTS**
══════════════════════════════════════════════════

**Statistiques globales:**
• Total contacts: 12
• Avec GPS: 10
• Avec clé publique: 11

[... similar format to Meshtastic ...]

**MeshCoreNode** (2h)
├─ Node ID: `!11111111`
├─ Short: MCN
├─ Model: HELTEC_V3
├─ GPS: 47.234567, 6.890123
├─ PubKey: `12345678...abcdef01` (32 bytes)
├─ Source: meshcore  ← Clearly labeled!
└─ Mise à jour: 2025-11-17 13:45:12
```

#### Updated Help Text

**Mesh Channel:**
```
🗄️ /db [cmd]
s=stats i=info
nb=neighbors mt=meshtastic mc=meshcore
clean <pwd>=nettoyage
v <pwd>=vacuum pw=weather
```

**Telegram Channel:**
```
🗄️ BASE DE DONNÉES - OPTIONS

Sous-commandes:
• stats - Statistiques DB (avec distinction Meshtastic/MeshCore)
• info - Informations détaillées
• nb - Stats voisinage (neighbors)
• mt - Table Meshtastic nodes (radio)
• mc - Table MeshCore contacts (cli)
• clean <password> [hours] - Nettoyer données anciennes
• vacuum <password> - Optimiser DB (VACUUM)
• purgeweather - Purger cache météo
```

## Technical Details

### Files Modified

1. **browse_traffic_db.py** (987 lines)
   - Added `load_meshtastic_nodes()` method
   - Added `load_meshcore_contacts()` method
   - Added `draw_meshtastic_node_line()` method
   - Added `draw_meshcore_contact_line()` method
   - Updated `draw_list()` for new views
   - Updated `draw_detail_view()` with source-specific formatting
   - Updated export functions (text, CSV, screen)
   - Updated view cycle and help text

2. **handlers/command_handlers/db_commands.py** (850+ lines)
   - Enhanced `_get_db_stats()` to count both sources
   - Added `_get_meshtastic_table()` method
   - Updated `_get_help()` with mt command
   - Added command routing for mt/meshtastic

3. **telegram_bot/commands/db_commands.py** (114 lines)
   - Added mt/meshtastic command routing
   - Integrated with `_get_meshtastic_table()`

### Database Tables

The implementation uses existing database tables:

```sql
-- Meshtastic nodes (learned via radio)
CREATE TABLE meshtastic_nodes (
    node_id TEXT PRIMARY KEY,
    name TEXT,
    shortName TEXT,
    hwModel TEXT,
    publicKey BLOB,
    lat REAL,
    lon REAL,
    alt REAL,
    last_updated REAL
);

-- MeshCore contacts (learned via CLI)
CREATE TABLE meshcore_contacts (
    node_id TEXT PRIMARY KEY,
    name TEXT,
    shortName TEXT,
    hwModel TEXT,
    publicKey BLOB,
    lat REAL,
    lon REAL,
    alt REAL,
    last_updated REAL,
    source TEXT DEFAULT 'meshcore'
);
```

## Benefits

### For Users
- **Clear data provenance**: Understand where node information comes from
- **Better troubleshooting**: Identify which collection method is working
- **Informed decisions**: Know which nodes are radio-active vs companion-fed

### For Developers
- **Maintainability**: Clear separation of concerns
- **Extensibility**: Easy to add more data sources in the future
- **Consistency**: Unified approach across browse UI and commands

### For Network Analysis
- **Topology understanding**: Distinguish between direct radio contact and indirect CLI data
- **Coverage mapping**: Identify gaps in radio coverage
- **Data quality**: Assess reliability of different data sources

## Testing

A comprehensive test suite has been created (`test_meshcore_meshtastic_separation.py`) that verifies:
- ✅ View cycle includes all 5 views
- ✅ All new methods exist and are callable
- ✅ Command routing handles mt/meshtastic
- ✅ Stats enhancement counts both sources
- ✅ Help text documents new commands
- ✅ Source labels are clear and consistent

## Usage Examples

### Browse Traffic DB

```bash
# Start the browser
python3 browse_traffic_db.py

# Navigate views with 'v' key:
# packets → messages → nodes_stats → meshtastic_nodes → meshcore_contacts

# Focus on a node with 'F' key (from any node view)
# Export current view with 'x', 'c', or 'S'
```

### Command Line

```bash
# Mesh channel (compact)
/db stats              # Shows counts for both sources
/db mt                 # List Meshtastic nodes (compact)
/db mc                 # List MeshCore contacts (compact)

# Telegram channel (detailed)
/db stats              # Full stats with source breakdown
/db meshtastic         # Full Meshtastic table
/db meshcore           # Full MeshCore table
```

## Future Enhancements

Potential improvements for future iterations:
- Add source indicator in packet list view
- Show data freshness (time since last update from each source)
- Add filtering by source in browse UI
- Export capabilities per source
- Statistics per source (packet counts, etc.)

## Conclusion

This implementation provides a clear, user-friendly separation between Meshtastic and MeshCore data sources throughout the system. Users can now easily distinguish between radio-learned and CLI-learned node information, leading to better understanding and troubleshooting of the mesh network.
