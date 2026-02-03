# Troubleshooting: /propag Command Not Appearing in Telegram

## Issue
The `/propag` command handler is registered in the code but does not show up in the bot's debug logs when invoked via Telegram.

## Debug Logging Added

### Startup Logging (telegram_integration.py)
```
🔍 DEBUG: Enregistrement du handler /propag...
✅ DEBUG: Handler /propag enregistré (méthode: <bound method ...>)
```

These messages confirm:
- The handler registration code is being executed
- The method reference is valid

### Runtime Logging (network_commands.py)
```
🔍 DEBUG: propag_command appelée par user 123456 (username)
⚠️ DEBUG: User 123456 NON autorisé pour /propag
📱 Telegram /propag (24h, top 5): username
```

These messages show:
- Whether the method is being called at all
- If authorization is blocking the user
- Normal execution flow

## Diagnostic Steps

### 1. Verify Bot Restart
The bot must be fully restarted to load new code:

```bash
# Stop the bot
sudo systemctl stop meshbot

# Verify it's stopped
sudo systemctl status meshbot

# Start the bot
sudo systemctl start meshbot

# Watch the logs
journalctl -u meshbot -f
```

**Expected at startup:**
```
Enregistrement des handlers de commandes...
🔍 DEBUG: Enregistrement du handler /propag...
✅ DEBUG: Handler /propag enregistré (méthode: <bound method NetworkCommands.propag_command ...>)
✅ 36 handlers enregistrés
```

### 2. Clear Python Cache
Python bytecode cache can cause old code to run:

```bash
cd /home/user/meshbot
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete
```

### 3. Verify Code Version
Ensure the latest code is deployed:

```bash
cd /home/user/meshbot
git log --oneline -1
# Should show: c7abe12 Add debug logging to /propag command handler

git status
# Should show: nothing to commit, working tree clean
```

### 4. Check Handler Registration
Verify the handler was actually registered:

```bash
# In Python, after bot starts:
python3 << 'EOF'
from telegram_integration import TelegramIntegration
# Check if method exists
import telegram_bot.commands.network_commands as nc
print(hasattr(nc.NetworkCommands, 'propag_command'))
EOF
```

### 5. Test Command
Send `/propag` to the bot via Telegram.

**Expected in logs:**
```
🔍 DEBUG: propag_command appelée par user 123456789 (YourUsername)
📱 Telegram /propag (24h, top 5): YourUsername
```

**If you see authorization error:**
```
⚠️ DEBUG: User 123456789 NON autorisé pour /propag
```

Check `config.py`:
```python
# If empty, all users are authorized
TELEGRAM_AUTHORIZED_USERS = []

# If populated, only these users can use commands
TELEGRAM_AUTHORIZED_USERS = [123456789, 987654321]
```

## Common Issues

### Issue 1: No debug logs at all
**Cause**: Bot not restarted or old code still running
**Solution**: 
1. Fully restart bot: `sudo systemctl restart meshbot`
2. Clear cache: `find . -name __pycache__ -exec rm -rf {} +`
3. Verify git version: `git log -1`

### Issue 2: Handler registration logs appear, but command doesn't work
**Cause**: Handler registered but method has runtime error
**Solution**: Check for exceptions in logs around the time you sent /propag

### Issue 3: "User X NON autorisé" message
**Cause**: User not in `TELEGRAM_AUTHORIZED_USERS` list
**Solution**: 
1. Add user ID to config.py: `TELEGRAM_AUTHORIZED_USERS = [YOUR_USER_ID]`
2. Or make list empty to allow all users: `TELEGRAM_AUTHORIZED_USERS = []`
3. Restart bot

### Issue 4: Method called but no response
**Cause**: Error in `get_propagation_report()` or network issue
**Solution**: Look for these in logs:
```
❌ Erreur /propag: ...
❌ Traffic monitor non disponible
```

## Verification Checklist

- [ ] Bot fully restarted with `systemctl restart meshbot`
- [ ] Python cache cleared
- [ ] Git shows latest commit (c7abe12)
- [ ] Startup logs show handler registration debug messages
- [ ] Command invocation shows debug messages
- [ ] User is authorized (check TELEGRAM_AUTHORIZED_USERS)
- [ ] No errors in logs when command is invoked

## Expected Full Log Flow

```
# At bot startup:
Initialisation bot Telegram...
Enregistrement des handlers de commandes...
🔍 DEBUG: Enregistrement du handler /propag...
✅ DEBUG: Handler /propag enregistré (méthode: <bound method NetworkCommands.propag_command of <telegram_bot.commands.network_commands.NetworkCommands object at 0x...>>)
✅ 36 handlers enregistrés
Bot Telegram en écoute (polling optimisé)...

# When user sends /propag:
🔍 DEBUG: propag_command appelée par user 123456789 (Username)
📱 Telegram /propag (24h, top 5): Username
```

## Next Steps

If after following all these steps the command still doesn't work:

1. **Capture full logs**: `journalctl -u meshbot --since "5 minutes ago" > meshbot-logs.txt`
2. **Check for errors**: `grep -i "error\|exception\|traceback" meshbot-logs.txt`
3. **Verify handler count**: Look for `✅ X handlers enregistrés` - should be 36 or more
4. **Test other commands**: Try `/nodes` or `/mqtt` to verify Telegram bot is working at all

## Code References

- **Handler registration**: `telegram_integration.py` line 250-253
- **Method implementation**: `telegram_bot/commands/network_commands.py` line 448-515
- **Base class**: `telegram_bot/command_base.py` line 18-31
- **Authorization check**: `telegram_bot/command_base.py` line 33-45
