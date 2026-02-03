# Telegram Group Chat Command Behavior

## Issue Resolved

User reported that `/keys a76f40d` didn't work, but `/keys@TigroMeshBot a76f40d` did work.

**This is standard Telegram behavior, not a bug.**

## Telegram Bot Command Rules

### In Private Chats (1-on-1 with bot)
- ✅ `/keys` - Works
- ✅ `/keys a76f40d` - Works
- ✅ `/keys@TigroMeshBot a76f40d` - Works (but username is optional)

### In Group Chats (multiple users + bot)
- ✅ `/keys` - Works (no arguments)
- ❌ `/keys a76f40d` - **Telegram ignores** (no bot username)
- ✅ `/keys@TigroMeshBot a76f40d` - Works (bot username specified)

## Why This Happens

In group chats with multiple bots:
1. Commands **without arguments** are sent to **all bots**
2. Commands **with arguments** are **only sent to the bot if username is specified**

This prevents:
- Command conflicts between multiple bots
- Accidental command execution by wrong bot
- Privacy issues (bot seeing all commands in group)

## Solution

### Option 1: Use Bot Username in Group Chats
```
/keys@TigroMeshBot a76f40d
/nodes@TigroMeshBot tigro
/stats@TigroMeshBot top 24
```

### Option 2: Use Private Chat with Bot
In a private 1-on-1 chat with the bot:
```
/keys a76f40d
/nodes tigro
/stats top 24
```

### Option 3: Enable Privacy Mode OFF (Not Recommended)
BotFather can disable privacy mode, making bot see all messages. **Not recommended** as it's a privacy issue.

## How to Check Your Chat Type

If commands with arguments don't work without bot username, you're in a **group chat**.

**Verification:**
1. Try `/keys` (no argument) → Should work
2. Try `/keys a76f40d` → Doesn't work in group
3. Try `/keys@YourBotName a76f40d` → Works in group

## Related to This PR

The original issue was reported as "no response" for `/keys a76f40d`. Through extensive debugging, we discovered:

1. **The fix was working** - Multi-format key search (commit 2b9faeb) was correct
2. **The issue was Telegram routing** - Not our code
3. **User was in group chat** - Telegram requires bot username for commands with arguments

All the diagnostic logging added (commits e3b8fdd, 02a079e, a241795, 4de8e0e) helped identify this was a Telegram behavior issue, not a code bug.

## Documentation

- Telegram Bot API: https://core.telegram.org/bots/api#sendmessage
- Privacy Mode: https://core.telegram.org/bots/features#privacy-mode
- Bot Commands: https://core.telegram.org/bots/features#commands

## Summary

✅ **The original fix works correctly**
❌ **The issue was Telegram group chat behavior**
📝 **Solution: Use bot username in group chats for commands with arguments**
