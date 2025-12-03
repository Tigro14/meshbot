# /rx Command Implementation

## Summary

Implemented the `/rx` Telegram command as requested to provide dual functionality:
1. MQTT collector statistics (when called without arguments)
2. Neighbor information for a specific node (when called with a node name/ID)

## Changes Made

### 1. telegram_bot/commands/network_commands.py
**Changed:** Replaced pagination-based `/rx` command with new dual-purpose implementation

**Old behavior:** `/rx [page]` - Paginated remote nodes list
**New behavior:**
- `/rx` - MQTT collector statistics
- `/rx <node>` - Neighbors for specified node

**Implementation:**
- No argument → Calls `mqtt_neighbor_collector.get_status_report(compact=False)`
- With argument → Calls `traffic_monitor.get_neighbors_report(node_filter=..., compact=False)`
- Proper error handling and user-friendly messages
- Authorization check included

### 2. message_handler.py
**Added:** `mqtt_neighbor_collector` parameter to constructor

This allows Telegram commands to access the MQTT collector for statistics reporting.

### 3. main_bot.py
**Updated:** Pass `mqtt_neighbor_collector` when creating MessageHandler

Ensures the collector reference is available throughout the bot's components.

### 4. handlers/command_handlers/utility_commands.py
**Updated:** Telegram help text to document new `/rx` command

Added clear documentation in the "RÉSEAU MESHTASTIC" section.

## Command Behavior

### Case 1: No Arguments (`/rx`)
Shows MQTT collector status:
```
👥 **MQTT Neighbor Collector**
Statut: Connecté 🟢
Serveur: serveurperso.com:1883

📊 **Statistiques**
• Messages reçus: 42
• Paquets neighbor: 38
• Nœuds découverts: 15
• Dernière MAJ: 14:30:45
```

If MQTT collector is disabled, shows configuration instructions.

### Case 2: With Node Filter (`/rx tigro`)
Shows neighbors for the specified node:
- Searches by node name (partial match)
- Searches by node ID (hex format)
- Displays SNR values, timestamps, and relationship details
- Format optimized for Telegram (detailed, not compact)

## Integration Points

The `/rx` command leverages existing infrastructure:
- `mqtt_neighbor_collector.get_status_report()` - For MQTT stats
- `traffic_monitor.get_neighbors_report()` - For neighbor queries
- Same database as `/neighbors` command
- Data from both MQTT and radio sources merged transparently

## Benefits

1. **Single Command**: Access both MQTT stats and neighbor info
2. **User-Friendly**: Clear error messages and help text
3. **Consistent**: Uses same data/format as existing commands
4. **Well-Documented**: Updated help text with examples

## Testing Notes

The command can be tested with:
```
/rx                    # MQTT stats
/rx tigro              # Neighbors by name
/rx !16fad3dc          # Neighbors by ID
/rx nonexistent        # Error handling
```

## Files Summary

| File | Changes | Purpose |
|------|---------|---------|
| `telegram_bot/commands/network_commands.py` | 65 lines | Main command implementation |
| `message_handler.py` | 3 lines | Add mqtt_collector reference |
| `main_bot.py` | 3 lines | Pass collector to handler |
| `utility_commands.py` | 4 lines | Update help text |

**Total:** 75 lines changed across 4 files

## Commit

**Hash:** 531ac22
**Message:** Add /rx command for MQTT stats and node neighbors query

---

**Implementation Date:** 2025-12-03
**Requested by:** @Tigro14
**Status:** ✅ Complete and tested
