# MeshCore NODEINFO Storage Implementation

## Overview
This implementation adds support for storing MeshCore contact information (equivalent to NODEINFO in Meshtastic) in the SQLite database, enabling the `/nodes` command to work in MeshCore mode.

## Problem Statement
The `/nodes` command didn't work for MeshCore because contact information was not persisted to the database. While the `meshcore_contacts` table and `save_meshcore_contact()` method existed, contacts received from MeshCore were never actually saved.

## Solution Architecture

### 1. Contact Storage (meshcore_cli_wrapper.py)
When MeshCore contacts are synchronized via `sync_contacts()`:
```python
# After sync_contacts() completes successfully
for contact in post_contacts:
    contact_data = {
        'node_id': contact_id,
        'name': name,
        'shortName': contact.get('short_name', ''),
        'hwModel': contact.get('hw_model', None),
        'publicKey': public_key,
        'lat': contact.get('latitude', None),
        'lon': contact.get('longitude', None),
        'alt': contact.get('altitude', None),
        'source': 'meshcore'
    }
    self.node_manager.persistence.save_meshcore_contact(contact_data)
```

### 2. Contact Retrieval (remote_nodes_client.py)
New methods to query and display contacts:
- `get_meshcore_contacts_from_db(days_filter=30)` - Queries SQLite
- `get_meshcore_paginated(page=1, days_filter=30)` - Formats for display

### 3. Command Integration (network_commands.py)
The `/nodes` command detects the connection mode:
```python
connection_mode = getattr(config, 'CONNECTION_MODE', 'serial').lower()
meshcore_enabled = getattr(config, 'MESHCORE_ENABLED', False)

if connection_mode == 'meshcore' or meshcore_enabled:
    report = self.remote_nodes_client.get_meshcore_paginated(page)
else:
    report = self.remote_nodes_client.get_tigrog2_paginated(page)
```

## Database Schema
Table: `meshcore_contacts`
```sql
CREATE TABLE IF NOT EXISTS meshcore_contacts (
    node_id TEXT PRIMARY KEY,
    name TEXT,
    shortName TEXT,
    hwModel TEXT,
    publicKey BLOB,
    lat REAL,
    lon REAL,
    alt INTEGER,
    last_updated REAL,
    source TEXT DEFAULT 'meshcore'
)
```

## Usage

### Configuration
Set in `config.py`:
```python
CONNECTION_MODE = 'meshcore'  # Enable MeshCore mode
MESHCORE_ENABLED = True       # Alternative flag
```

### Command Examples
```
/nodes         → Show first page of MeshCore contacts
/nodes 2       → Show second page
```

### Example Output
```
📡 Contacts MeshCore (<30j) (15):
• Node-Alpha 5m
• Node-Bravo 12m
• Node-Charlie 1h
• Node-Delta 2h
• Node-Echo 3h
• Node-Foxtrot 4h
• Node-Golf 5h
1/3
```

## Benefits

1. **Persistent Storage**: Contacts survive bot restarts
2. **Automatic Sync**: Contacts saved after each `sync_contacts()`
3. **Pagination**: Consistent with Meshtastic display
4. **UPSERT Logic**: Updates existing contacts, no duplicates
5. **Data Separation**: MeshCore and Meshtastic contacts in separate tables
6. **Mode Detection**: Automatically uses correct source

## Testing

### Automated Tests
Run: `python test_meshcore_nodeinfo_storage.py`

Tests cover:
- Contact storage
- Contact retrieval
- Paginated display
- Command integration
- Update behavior

### Demonstration
Run: `python demo_meshcore_nodeinfo_storage.py`

Shows:
- Database creation
- Contact saving
- Contact retrieval
- Paginated output
- Update without duplicates

## Implementation Notes

### Key Design Decisions
1. **Separate Table**: MeshCore contacts stored separately from Meshtastic nodes
2. **Same Interface**: Uses existing `TrafficPersistence` infrastructure
3. **Format Compatibility**: Contacts formatted like Meshtastic nodes for consistency
4. **Graceful Degradation**: Missing signal metrics (SNR/RSSI) handled gracefully

### Signal Metrics
MeshCore contacts don't have SNR/RSSI data:
- Set to `None` in database
- Formatted without signal icons
- Display shows time only: `• NodeName 5m`

### GPS Coordinates
- Stored if available from MeshCore
- Used for distance calculations if bot position configured
- Display format: `• NodeName 2.5km 10m`

## Files Changed
- `meshcore_cli_wrapper.py` - Contact saving logic
- `remote_nodes_client.py` - Contact retrieval and display
- `handlers/command_handlers/network_commands.py` - Command routing
- `main_bot.py` - Persistence initialization
- `test_meshcore_nodeinfo_storage.py` (NEW) - Test suite
- `demo_meshcore_nodeinfo_storage.py` (NEW) - Demonstration

## Future Enhancements
- [ ] Add signal metrics from MeshCore if available
- [ ] Support filtering by hardware model
- [ ] Add search by contact name
- [ ] Export contacts to JSON/CSV
- [ ] Visualize network topology from contacts

## Troubleshooting

### Contacts not appearing in /nodes
1. Check `CONNECTION_MODE` in config.py
2. Verify `MESHCORE_ENABLED = True`
3. Check database: `sqlite3 traffic_history.db "SELECT * FROM meshcore_contacts;"`
4. Enable debug mode to see sync logs

### Contacts not syncing
1. Verify meshcore-cli connection is active
2. Check logs for "sync_contacts" messages
3. Ensure node_manager has persistence reference
4. Verify `sync_contacts()` completes successfully

### Database errors
1. Check traffic_history.db file permissions
2. Verify SQLite version supports the schema
3. Check disk space availability
4. Review logs for SQLite error messages

## References
- Issue: "Store NODEINFO for meshcore in SQLite DB as we do for Meshtastic"
- PR: copilot/store-nodeinfo-in-sqlite
- Similar implementation: Meshtastic NODEINFO storage (meshtastic_nodes table)
- Database: traffic_persistence.py
- MeshCore protocol: meshcore-cli library

## Changelog

### 2026-01-21 - Initial Implementation
- Added contact saving after sync_contacts()
- Added database retrieval methods
- Integrated with /nodes command
- Added comprehensive tests
- Added demonstration script
- Fixed None handling for signal metrics
- All tests passing

---
**Status**: ✅ Complete and ready for testing with real MeshCore devices
**Tested**: Automated tests passing, demonstration working
**Ready for**: Manual testing with actual MeshCore connection
