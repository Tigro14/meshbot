# Testing Instructions - MeshCore Public Channel Support

## Current Status

**Phase 7 - Diagnostic Logging Deployed**

The bot now includes comprehensive diagnostic logging to identify why payload extraction is failing.

## Problem Summary

You're sending `/echo` commands on the MeshCore public channel, but:
- ❌ Payload shows as 0 bytes (should be 56 bytes)
- ❌ Command not processed by bot
- ❌ Previous debug logs not appearing (suggests code path issue)

## What We Added

**Unconditional diagnostic logging** that will ALWAYS show:
```
🔍 [RX_LOG] Checking decoded_packet for payload...
🔍 [RX_LOG] Has payload attribute: True/False
🔍 [RX_LOG] Payload value: <actual value>
🔍 [RX_LOG] Payload type: <type name>
```

This will reveal the **actual structure** of the packet and why extraction is failing.

## Testing Steps

### 1. Deploy Updated Code

```bash
cd /home/user/meshbot  # Or your meshbot directory
git pull origin copilot/add-echo-command-listener
```

### 2. Restart Bot

```bash
sudo systemctl restart meshbot
```

### 3. Monitor Logs

Open a terminal and watch the logs:
```bash
journalctl -u meshbot -f | grep -E "(RX_LOG|🔍)"
```

### 4. Send Test Command

On your MeshCore public channel, send:
```
/echo test
```

### 5. Collect Diagnostic Output

Look for these log lines:
```
[DEBUG][MC] 🔍 [RX_LOG] Checking decoded_packet for payload...
[DEBUG][MC] 🔍 [RX_LOG] Has payload attribute: ???
[DEBUG][MC] 🔍 [RX_LOG] Payload value: ???
[DEBUG][MC] 🔍 [RX_LOG] Payload type: ???
```

## What to Report

Please share the **complete log output** from sending `/echo test`, especially:

1. **The RX_LOG packet reception**:
   ```
   📡 [RX_LOG] Paquet RF reçu (??B) - From: ??? → To: ???
   📦 [RX_LOG] Type: Unknown(??) | Route: ??? | Size: ??B
   ```

2. **The new diagnostic lines** (most important!):
   ```
   🔍 [RX_LOG] Checking decoded_packet for payload...
   🔍 [RX_LOG] Has payload attribute: ???
   🔍 [RX_LOG] Payload value: ???
   ```

3. **The forwarding result**:
   ```
   ➡️ [RX_LOG] Forwarding ??? packet to bot callback
   ✅ [RX_LOG] Packet forwarded successfully
   ```

## Expected Outcomes

### Scenario A: Payload Attribute Missing
```
🔍 [RX_LOG] Has payload attribute: False
```
**Action**: Need to check alternate packet attributes.

### Scenario B: Payload is None
```
🔍 [RX_LOG] Has payload attribute: True
🔍 [RX_LOG] Payload value: None
```
**Action**: Payload exists but empty - check packet.raw_data.

### Scenario C: Payload is Empty Dict
```
🔍 [RX_LOG] Payload value: {}
🔍 [RX_LOG] Payload type: dict
```
**Action**: No data in payload - may need decoder changes.

### Scenario D: Payload Has Data (Good!)
```
🔍 [RX_LOG] Payload value: {'raw': '1a05...'}
🔍 [RX_LOG] Payload type: dict
```
**Action**: Should work with Phase 5 fix - investigate why not extracting.

## Quick Grep Commands

To see only diagnostic output:
```bash
journalctl -u meshbot -n 100 | grep "🔍"
```

To see RX_LOG flow:
```bash
journalctl -u meshbot -n 100 | grep "RX_LOG"
```

To see full context:
```bash
journalctl -u meshbot -n 100
```

## Next Steps

Once we see the diagnostic output, we can:
1. Identify the actual packet structure
2. Determine why payload extraction is failing
3. Add appropriate fix for your specific case
4. Test again to confirm command processing

## Questions?

If you see errors or unexpected behavior, please share:
- Full log output from one `/echo` command
- Any error messages
- Output of `journalctl -u meshbot -n 200`

This will help us quickly identify and fix the issue!
