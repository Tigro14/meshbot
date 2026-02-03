# Fix: /hop Telegram Alias Not Working

**Date**: 2025-12-11  
**Issue**: `/hop` telegram alias not working  
**Status**: ✅ Fixed

---

## Problem

The `/hop` command was working on Meshtastic/mesh interface but was not available via Telegram bot.

### Root Cause

The `/hop` command handler was:
- ✅ Implemented in `handlers/message_router.py` (for Meshtastic)
- ✅ Implemented in `handlers/command_handlers/utility_commands.py`
- ✅ Business logic available in `unified_stats.py::get_hop_stats()`
- ❌ **NOT registered in Telegram handlers**

### Symptoms

When users tried `/hop` in Telegram:
- No response from bot
- Command not recognized
- Works fine via Meshtastic mesh network

---

## Solution

Added Telegram command handler for `/hop`:

### 1. Added Handler Method

**File**: `telegram_bot/commands/stats_commands.py`  
**Lines**: 291-339

```python
async def hop_command(self, update: Update,
                      context: ContextTypes.DEFAULT_TYPE):
    """
    Commande /hop [heures] - Alias pour /stats hop
    Affiche les nœuds triés par hop_start (portée maximale)
    
    Usage:
        /hop           - Top 20 nœuds par portée (24h)
        /hop 48        - Top 20 nœuds par portée (48h)
        /hop 168       - Top 20 nœuds par portée (7 jours)
    """
    user = update.effective_user
    
    # Parser les arguments
    hours = 24
    if context.args and len(context.args) > 0:
        try:
            hours = int(context.args[0])
            hours = max(1, min(168, hours))  # Entre 1h et 7 jours
        except ValueError:
            hours = 24
    
    info_print(f"📱 Telegram /hop {hours}h: {user.username}")
    
    # Vérifier que unified_stats est disponible
    if not hasattr(self.telegram, 'unified_stats') or not self.telegram.unified_stats:
        await update.effective_message.reply_text("❌ Système de stats non disponible")
        return
    
    def get_hop_stats():
        """Appeler le système unifié pour obtenir les stats hop"""
        try:
            params = [str(hours)] if hours != 24 else []
            return self.telegram.unified_stats.get_stats(
                subcommand='hop',
                params=params,
                channel='telegram'  # Format détaillé pour Telegram
            )
        except Exception as e:
            error_print(f"Erreur hop stats: {e}")
            import traceback
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"
    
    # Exécuter dans un thread séparé
    response = await asyncio.to_thread(get_hop_stats)
    
    # Envoyer la réponse
    await self.send_message(update, response)
```

### 2. Registered Handler

**File**: `telegram_integration.py`  
**Line**: 260

```python
# Commandes statistiques
self.application.add_handler(CommandHandler("stats", self.stats_commands.stats_command))
self.application.add_handler(CommandHandler("top", self.stats_commands.top_command))
self.application.add_handler(CommandHandler("packets", self.stats_commands.packets_command))
self.application.add_handler(CommandHandler("histo", self.stats_commands.histo_command))
self.application.add_handler(CommandHandler("hop", self.stats_commands.hop_command))  # ← NEW
self.application.add_handler(CommandHandler("trafic", self.stats_commands.trafic_command))
```

---

## Implementation Pattern

Follows the same pattern as other stat command aliases:

| Command | Telegram Handler | Business Logic | Default |
|---------|-----------------|----------------|---------|
| `/top` | `top_command()` | `business_stats.get_top_talkers()` | 24h |
| `/packets` | `packets_command()` | `business_stats.get_packet_type_summary()` | 1h |
| `/histo` | `histo_command()` | `traffic_monitor.get_hourly_histogram()` | 24h |
| **`/hop`** | **`hop_command()`** | **`unified_stats.get_stats('hop')`** | **24h** |

---

## Testing

### Validation Performed

1. ✅ Python syntax check passed
2. ✅ Handler registration verified
3. ✅ Method signature correct (async with update, context)
4. ✅ Help text already includes `/hop` documentation

### Test File

Created `test_hop_telegram.py` to validate:
- Handler method exists in `StatsCommands`
- Handler is async
- Handler is registered in `telegram_integration.py`
- Method signature matches other handlers
- Documentation present

### Manual Testing Required

Since Telegram bot requires API token and running instance:

```bash
# Start the bot (requires Telegram token configured)
python3 main_script.py

# Test commands in Telegram:
/hop           # Should show top 20 nodes by hop_start (24h)
/hop 48        # Should show top 20 nodes (48h)
/hop 168       # Should show top 20 nodes (7 days)
```

---

## Files Modified

```
telegram_bot/commands/stats_commands.py  (+50 lines)
telegram_integration.py                  (+1 line)
test_hop_telegram.py                     (+170 lines, new file)
```

---

## Verification Checklist

- [x] Handler method added to `StatsCommands` class
- [x] Handler registered in `telegram_integration.py`
- [x] Uses `unified_stats.get_stats()` for consistency
- [x] Async/await pattern followed
- [x] Error handling implemented
- [x] Logging included
- [x] Hours parameter validated (1-168h)
- [x] Thread-safe execution via `asyncio.to_thread()`
- [x] Help text already includes command

---

## Usage Examples

### Basic Usage
```
User: /hop
Bot: 🔄 Hop(24h) Top20
     tigrog2: 7 hops
     tigrobot: 7 hops
     node123: 6 hops
     ...
```

### With Custom Hours
```
User: /hop 48
Bot: 🔄 Hop(48h) Top20
     [Statistics for last 48 hours]
```

### Maximum Range
```
User: /hop 168
Bot: 🔄 Hop(168h) Top20
     [Statistics for last 7 days]
```

---

## Backward Compatibility

✅ **No Breaking Changes**

- Existing Meshtastic `/hop` command continues to work
- All other Telegram commands unaffected
- Business logic (`unified_stats`) unchanged
- Help text already documented the command

---

## Conclusion

The `/hop` Telegram alias is now fully functional and follows the same implementation pattern as other stat command aliases (`/top`, `/packets`, `/histo`).

**Status**: ✅ Complete and ready for testing
