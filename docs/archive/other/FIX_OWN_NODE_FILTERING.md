# Fix: Bot Filtering Own Node's Public Channel Messages

## Problem Statement

From production logs:
```
Feb 14 18:27:25 DietPi meshtastic-bot[134108]: [INFO][MC] 📢 [CHANNEL] Message de 0x16fad3dc sur canal 0: Tigro: /echo kissé
Feb 14 18:27:25 DietPi meshtastic-bot[134108]: [INFO][MC] ✅ [CHANNEL] Message transmis au bot pour traitement
```

**No response was sent!** Message was received, sender correctly identified, but bot didn't respond.

## Root Cause

The bot was running on user "Tigro's" node (ID: 0x16fad3dc). When Tigro sent a public channel message, the bot:

1. ✅ Received the message correctly
2. ✅ Extracted sender name "Tigro" from prefix
3. ✅ Looked up Tigro's node ID: 0x16fad3dc
4. ✅ Attributed message to correct sender
5. ❌ **Filtered message as "from self"** because `from_id == my_id`
6. ❌ Never processed the command
7. ❌ No response sent

### The Filtering Logic Bug

In `main_bot.py` line 916-917:

```python
# Filtrer les messages auto-générés
if is_from_me:
    return
```

This check was **too broad**. It filtered:
- ✅ Direct messages from bot to itself (CORRECT - prevent DM loops)
- ❌ Public channel broadcasts from bot's node (WRONG - legitimate user commands!)

## The Scenario

```
User "Tigro" setup:
├─ Node ID: 0x16fad3dc
├─ Runs bot on this node
└─ Sends command: "/echo kissé" on public channel

Message flow:
┌─────────────────────────────────────────────┐
│ Tigro sends: "Tigro: /echo kissé"          │
│ (Public channel broadcast)                   │
└─────────────────┬───────────────────────────┘
                  │ Broadcasts to all nodes
                  │ including sender
                  ▼
┌─────────────────────────────────────────────┐
│ Bot receives on node 0x16fad3dc             │
│ - from_id: 0x16fad3dc (Tigro)              │
│ - my_id: 0x16fad3dc (Bot's node = Tigro)   │
│ - is_from_me: TRUE                          │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ OLD LOGIC (WRONG):                          │
│   if is_from_me:                            │
│       return  # FILTERED OUT!               │
└─────────────────────────────────────────────┘
                  │
                  ▼
            ❌ NO RESPONSE
```

## The Fix

Modified the filtering logic to only filter **direct messages** from own node:

```python
# Filtrer les messages auto-générés (sauf broadcasts)
# Pour les broadcasts, la déduplication par contenu (_is_recent_broadcast) gère les doublons
# Cela permet de traiter les commandes publiques envoyées depuis le nœud du bot
if is_from_me and not is_broadcast:
    debug_print(f"📤 Message DM de nous-même ignoré: 0x{from_id:08x}")
    return
```

### Why This Works

The fix leverages the existing broadcast deduplication system:

1. **Public channel messages from own node:** NOT filtered by `is_from_me` check
2. **Broadcast loop prevention:** Handled by `_is_recent_broadcast()` (line 976)
3. **Direct messages from own node:** Still filtered (you don't DM yourself)

### Broadcast Deduplication System

The bot already has sophisticated broadcast loop prevention in `main_bot.py`:

```python
# Line 974-981
if is_broadcast:
    try:
        if self._is_recent_broadcast(message):
            debug_print(f"🔄 Broadcast ignoré (envoyé par nous): {message[:30]}")
            return  # Ne pas traiter ce broadcast
```

This checks the **message content** against recently sent broadcasts, not just the sender ID. This is the correct way to prevent loops while allowing legitimate public channel commands.

## Test Coverage

### Test Suite: `test_own_node_broadcast_filtering.py`

Three comprehensive tests:

1. **test_own_node_broadcast_not_filtered**
   - Scenario: Broadcast from bot's own node
   - Expected: NOT filtered (allow user commands)
   - Result: ✅ PASS

2. **test_own_node_dm_is_filtered**
   - Scenario: Direct message from bot's own node
   - Expected: Filtered (prevent DM loops)
   - Result: ✅ PASS

3. **test_other_node_message_not_filtered**
   - Scenario: Message from different node
   - Expected: NOT filtered (normal operation)
   - Result: ✅ PASS

## Comparison: Old vs New Logic

### Old Logic (WRONG)
```python
if is_from_me:
    return  # Filtered ALL messages from own node
```

**Problems:**
- ❌ Filtered legitimate public channel commands from users on bot's node
- ❌ Made bot unusable for users running bot on their own node
- ❌ Relied only on sender ID, not message content

### New Logic (CORRECT)
```python
if is_from_me and not is_broadcast:
    return  # Only filter DMs from own node
```

**Benefits:**
- ✅ Allows public channel commands from bot's own node
- ✅ Still prevents DM loops (DMs from self filtered)
- ✅ Works with existing broadcast deduplication
- ✅ Bot usable for users on any node

## Impact Analysis

### Who Was Affected
- Users running bot on their own node
- Public channel commands from bot's node
- ~100% of commands failed if user = bot node

### What Now Works
```
Scenario                          Before  After
────────────────────────────────  ──────  ─────
User on bot's node sends /echo    ❌      ✅
User on different node sends /echo ✅      ✅
Bot's own broadcast echo          ✅      ✅ (dedup)
DM from bot to itself            ✅      ✅ (still filtered)
```

## Edge Cases Handled

1. **User on bot's node, public channel:** ✅ Works (main fix)
2. **User on different node, public channel:** ✅ Works (unchanged)
3. **Bot's own echo response:** ✅ Deduplicated by content
4. **DM from bot to itself:** ✅ Still filtered
5. **Broadcast loop:** ✅ Prevented by `_is_recent_broadcast()`

## Deployment Notes

### No Configuration Changes
This fix requires no configuration changes. It's a pure logic fix.

### Monitoring
Look for these log patterns after deployment:

**Success (message NOT filtered):**
```
[INFO][MC] 📢 [CHANNEL] Message de 0x16fad3dc sur canal 0: Tigro: /echo test
[DEBUG] 📨 MESSAGE REÇU De: 0x16fad3dc Contenu: Tigro: /echo test
[INFO] ECHO PUBLIC de tigro PVCavityABIOT: '/echo test'
```

**DM correctly filtered:**
```
[DEBUG] 📤 Message DM de nous-même ignoré: 0x16fad3dc
```

**Broadcast correctly deduplicated:**
```
[DEBUG] 🔄 Broadcast ignoré (envoyé par nous): user: /echo test response
```

### Rollback Plan
If issues occur, revert to:
```python
if is_from_me:
    return
```

This restores old behavior but breaks commands from bot's own node.

## Related Systems

### Broadcast Deduplication
The fix relies on existing `_is_recent_broadcast()` system:
- Tracks message content hashes
- 5-second deduplication window
- Prevents reprocessing bot's own responses
- Independent of sender ID

### Message Router
After passing this filter, messages go to message router which:
- Strips sender prefix from public channel messages
- Routes commands to appropriate handlers
- Handles both DMs and broadcasts

## Future Improvements

1. **Add node-aware logging:** Distinguish "from our node" vs "from us"
2. **Metrics:** Track how many messages from own node
3. **Configuration:** Optional setting to disable own-node commands (edge case)

## Verification Steps

To verify fix is working:

1. **Setup:** Run bot on a node
2. **Test:** Send `/echo test` on public channel from that node
3. **Check logs:**
   ```
   [INFO][MC] 📢 [CHANNEL] Message de 0xXXXXXXXX sur canal 0: YourName: /echo test
   [DEBUG] 📨 MESSAGE REÇU De: 0xXXXXXXXX Contenu: YourName: /echo test
   [INFO] ECHO PUBLIC de YourName: '/echo test'
   ```
4. **Verify:** Response is broadcast back to channel

## Summary

**Problem:** Bot filtered all messages from its own node, including legitimate public channel commands

**Cause:** Over-broad `is_from_me` check without considering message type

**Solution:** Only filter DMs from own node, allow public channel broadcasts

**Result:** Bot can now process commands from users on the same node as the bot
