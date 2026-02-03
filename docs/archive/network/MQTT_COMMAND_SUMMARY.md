# /mqtt Telegram Command - Implementation Summary

## Overview
This PR implements a new `/mqtt` Telegram command that displays all nodes heard directly via MQTT with their LongNames and lastHeard information.

## Problem Statement
Users need a way to see which nodes are actively sending NEIGHBORINFO packets via MQTT, along with their human-readable names and when they were last heard. This is different from the existing `/rx` command which shows MQTT collector stats or neighbor relationships for a specific node.

## Solution

### 1. New Method: `MQTTNeighborCollector.get_directly_heard_nodes(hours=48)`

**File**: `mqtt_neighbor_collector.py`

**Purpose**: Query the neighbors database to find unique nodes that have sent NEIGHBORINFO packets via MQTT.

**Logic**:
1. Load neighbor data from persistence layer (SQLite)
2. Identify unique nodes by looking at the `node_id` field (nodes that sent NEIGHBORINFO)
3. Find the most recent `timestamp` for each node
4. Resolve node IDs to LongNames via NodeManager
5. Sort by most recent first
6. Return list of dicts with: `node_id`, `longname`, `last_heard`

**Key Features**:
- Configurable time window (default: 48h)
- Automatic name resolution with fallback to node_id
- Graceful error handling
- Sorted by recency (most recent first)

### 2. New Telegram Command: `/mqtt [hours]`

**File**: `telegram_bot/commands/network_commands.py`

**Usage**:
- `/mqtt` - Show all MQTT nodes (48h default)
- `/mqtt 24` - Show nodes from last 24 hours
- `/mqtt 168` - Show nodes from last 7 days (max)

**Features**:
- Color-coded status icons based on recency:
  - 🟢 Green: < 1 hour
  - 🟡 Yellow: < 24 hours
  - 🟠 Orange: > 24 hours
- Shows MQTT connection status (Connecté 🟢 / Déconnecté 🔴)
- Displays node count and time window
- Each node shows: number, icon, **LongName** (bold), `short_id` (monospace), elapsed time
- Handles disabled MQTT collector with helpful config message
- Validates hours parameter (1h min, 168h max)

**Output Format**:
```
📡 Nœuds MQTT entendus directement (5 nœuds, 48h)

Statut MQTT: Connecté 🟢

1. 🟢 tigrobot 5678 (2m)
2. 🟢 tigrog2 4321 (30m)
3. 🟡 Paris-Gateway ef01 (5h)
4. 🟡 Unknown-Node beef (10h)
5. 🟠 Lyon-Mesh-001 d3dc (1j)
```

### 3. Command Registration

**File**: `telegram_integration.py`

Added command handler registration:
```python
self.application.add_handler(CommandHandler("mqtt", self.network_commands.mqtt_command))
```

### 4. Help Text Update

**File**: `telegram_bot/commands/basic_commands.py`

Added `/mqtt [heures] - Nœuds MQTT` to the start command help text.

## Testing

### Unit Tests: `test_mqtt_command.py`
Tests the core logic of `get_directly_heard_nodes()`:
1. **Test 1**: All nodes (48h window) - 4 nodes expected
2. **Test 2**: Recent nodes (24h window) - 2 nodes expected  
3. **Test 3**: Very recent nodes (1h window) - 1 node expected
4. **Test 4**: Node name resolution - all names verified

**Result**: ✅ All tests pass

### Integration Tests: `test_mqtt_command_integration.py`
Tests the full message formatting as sent to Telegram:
1. **Test 1**: Standard formatting (48h, all nodes)
2. **Test 2**: Filtered on 24h (recent nodes only)
3. **Test 3**: Disconnected MQTT status
4. **Test 4**: Empty result (no nodes)

**Result**: ✅ All tests pass

## Code Quality

### Follows Repository Patterns
- ✅ Async command handler pattern (similar to other Telegram commands)
- ✅ Thread execution with `asyncio.to_thread()` for blocking operations
- ✅ Authorization check via `check_authorization()`
- ✅ Error handling with try/except and informative user messages
- ✅ Logging with `info_print()` and `error_print()`
- ✅ Docstrings for all new methods

### Error Handling
- Graceful fallback when MQTT collector is disabled
- Helpful configuration message when feature is not enabled
- Validation of hours parameter (1-168 range)
- Exception handling with truncated error messages for users

### Performance
- No blocking operations in async context
- Efficient database query (reuses existing `load_neighbors()`)
- Minimal memory footprint (returns only necessary data)

## Files Changed

| File | Lines Added | Purpose |
|------|-------------|---------|
| `mqtt_neighbor_collector.py` | +69 | New `get_directly_heard_nodes()` method |
| `telegram_bot/commands/network_commands.py` | +98 | New `/mqtt` command handler |
| `telegram_integration.py` | +1 | Command registration |
| `telegram_bot/commands/basic_commands.py` | +1 | Help text update |
| `test_mqtt_command.py` | +226 | Unit tests |
| `test_mqtt_command_integration.py` | +246 | Integration tests |
| **Total** | **641** | **6 files** |

## Dependencies

No new dependencies required. Uses existing:
- `mqtt_neighbor_collector.MQTTNeighborCollector` (already in repo)
- `traffic_persistence.TrafficPersistence` (already in repo)
- `node_manager.NodeManager` (already in repo)
- `telegram` library (already a dependency)

## Comparison with Existing Commands

### vs `/rx` command
- `/rx` without args: Shows MQTT collector statistics
- `/rx <node>`: Shows neighbors of a specific node
- `/mqtt`: Shows all nodes that sent NEIGHBORINFO via MQTT (NEW)

### vs `/nodes` command
- `/nodes`: Shows direct nodes from REMOTE_NODE (via TCP query)
- `/mqtt`: Shows nodes heard via MQTT (from database)

### Unique Value
The `/mqtt` command fills a gap by showing which nodes are actively participating in the MQTT network topology reporting, with their human-readable names and recency information.

## Future Enhancements (Optional)

Potential improvements for future PRs:
1. Add filtering by node name (e.g., `/mqtt 48 tigro`)
2. Add sorting options (by name, SNR, distance)
3. Show additional stats (neighbor count, average SNR)
4. Export to CSV/JSON for analysis
5. Add geographic filtering (nodes within X km)

## Deployment Notes

1. No database migrations needed (uses existing `neighbors` table)
2. No config changes required (uses existing MQTT collector settings)
3. Command automatically available when MQTT collector is enabled
4. Gracefully handles disabled state with user-friendly message
5. Works with both encrypted and unencrypted MQTT packets (already supported by collector)

## Security Considerations

- ✅ Command respects Telegram authorization check
- ✅ No sensitive data exposed (only public node info)
- ✅ Input validation on hours parameter
- ✅ Error messages don't leak internal details
- ✅ No SQL injection risk (uses parameterized queries in persistence layer)

## Documentation

The command is self-documenting:
- Docstring explains usage
- Help text in `/start` command
- Error messages guide users to correct usage
- Example output shows expected format

## Conclusion

This implementation provides a clean, tested, and user-friendly way to view nodes heard via MQTT. It follows all repository conventions, includes comprehensive tests, and integrates seamlessly with the existing codebase.

**Status**: ✅ Ready for review and merge
