# Broadcast Deduplication Issue - Investigation Notes

## Issue Report

User reports that after implementing the broadcast deduplication fix (commit b31a3d3), the bot became "deaf" to both DM and broadcast commands, while still processing other mesh traffic (stats collection still works).

## Current Status

**Deduplication DISABLED** (commits 2512c41 + 3cbfd49) - Bot should work normally now.

## Symptoms

1. Bot doesn't respond to commands (both DM and broadcast)
2. Bot still collects traffic statistics (packets are received)
3. Suggests filtering happens AFTER stats collection but BEFORE command processing

## Expected Behavior

The deduplication logic should ONLY filter:
- Messages that are broadcasts (`to_id == 0xFFFFFFFF`)
- Whose content hash matches a message we recently sent (within 60s)

This means:
- ✅ User's `/rain` command should NOT be filtered (different hash than our response)
- ✅ Our response `"40da: 🌧️ Paris..."` should be tracked
- ✅ When we receive our own response back, it should be filtered
- ✅ DMs should NEVER be filtered (not broadcasts)

## Potential Root Causes

### 1. Hash Collision (Unlikely)
- MD5 hash collision between user command and our response
- Probability: ~10^-38 for random strings
- Would need to see actual hashes to verify

### 2. Tracking Wrong Messages
- Maybe we're tracking user commands instead of our responses?
- Check: What message is passed to `_track_broadcast()`?
- Evidence: Line 428 in utility_commands.py passes `response`, not original command

### 3. Logic Error in Check Conditions
```python
if is_broadcast and self._is_recent_broadcast(message):
    return  # Filter
```
- `is_broadcast` should be False for DMs
- But user reports DMs are also affected
- Suggests issue is NOT with this check?

### 4. Exception Being Thrown Silently
- If `_is_recent_broadcast()` throws exception, message might be dropped
- Now wrapped in try/except (commit 3cbfd49)
- Should see error logs if this happens

### 5. Race Condition
- Broadcast thread tracks message
- Message sent via TCP
- Message received back very quickly
- Hash already in `_recent_broadcasts`
- ??? But timing should still be correct

### 6. Variable Scope Issue
- Is `is_broadcast` being set correctly?
- Is `message` the actual message content?
- Could variables be carrying over?

## Diagnostic Strategy

### What We Need From Logs

When user tests with commits 2512c41 + 3cbfd49, look for:

1. **Tracking logs** - What are we tracking?
   ```
   🔖 Broadcast tracké: <hash>... | msg: '<content>' | actifs: N
   ```

2. **Recognition logs** - What do we recognize?
   ```
   🔍 Broadcast reconnu (Xs): <hash>... | msg: '<content>'
   ```

3. **Filter logs** - What would we filter?
   ```
   ⚠️ DEDUP: Broadcast qui serait filtré: '<content>'
   ```

4. **Normal message flow** - Are messages being processed?
   ```
   📨 MESSAGE REÇU
   De: 0x...
   Pour: ...
   Contenu: ...
   ```

### Analysis Questions

1. Are we tracking user commands or only our responses?
2. Are the hashes of user commands matching our response hashes?
3. Is `is_broadcast` being set correctly for DMs?
4. Are there any exceptions in the dedup check?
5. How many broadcasts are being tracked concurrently?

## Possible Solutions

### Solution A: More Conservative Filtering
Only filter if BOTH:
- Message is broadcast
- Message starts with short_name prefix (e.g., "40da:")
- Hash matches recent sends

### Solution B: Track More Context
Instead of just message content, track:
- Message content hash
- Sender ID (should be tigrog2_id for our broadcasts)
- Only filter if BOTH hash AND sender match

### Solution C: Delay Tracking
Track message AFTER it's confirmed sent, not before:
- Send broadcast
- Wait for confirmation
- Then track
- Reduces race condition window

### Solution D: Stricter Hash Matching
Use SHA256 instead of MD5 for less collision risk (though MD5 should be fine):
```python
msg_hash = hashlib.sha256(message.encode('utf-8')).hexdigest()
```

## Test Plan

Once we identify root cause:

1. **Unit test** for the specific failure case
2. **Integration test** with actual message flow
3. **Manual test** with diagnostic logging
4. **Deployment test** with gradual rollout

## Timeline

- [x] 2024-11-19 16:14 - Original broadcast loop issue reported
- [x] 2024-11-19 commits - Implemented deduplication fix
- [x] 2024-11-19 ~17:00 - "Deaf" issue reported
- [x] 2024-11-19 ~17:00 - Disabled filtering, added diagnostics
- [ ] Waiting for diagnostic logs from user
- [ ] Root cause analysis
- [ ] Implement proper fix
- [ ] Re-enable with confidence

## Notes

- The original broadcast loop issue IS real and needs fixing
- But the deduplication approach may need refinement
- Alternative: Could we use node ID matching instead of content hashing?
  - Track: (message_hash, from_id)
  - Filter only if: message_hash matches AND from_id == tigrog2_id
  - Pro: More precise
  - Con: Doesn't handle multi-node deployments
