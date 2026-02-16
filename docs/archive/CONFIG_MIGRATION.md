# Configuration Migration Guide

## Overview

The configuration has been refactored to separate **sensitive parameters** (tokens, passwords, user IDs) into a separate `config.priv.py` file that is gitignored.

## What Changed?

### Before (Single config.py)
```python
# config.py - Everything in one file
TELEGRAM_BOT_TOKEN = "1234567890:ABCdef..."  # Risky to commit!
TELEGRAM_AUTHORIZED_USERS = [123456789]       # User IDs exposed
REBOOT_PASSWORD = "secret123"                 # Password in git
# ... plus all other config
```

### After (Split configuration)
```python
# config.py - Public parameters only
TELEGRAM_ENABLED = True
MAX_MESSAGE_SIZE = 180
# ... (imports config_priv automatically)

# config_priv.py - Sensitive parameters (gitignored)
TELEGRAM_BOT_TOKEN = "1234567890:ABCdef..."
TELEGRAM_AUTHORIZED_USERS = [123456789]
REBOOT_PASSWORD = "secret123"
```

## Migration Steps

### For New Installations

1. **Copy the sample config:**
   ```bash
   cp config.py.sample config.py
   cp config.priv.py.sample config_priv.py
   ```

2. **Edit config_priv.py with your sensitive values:**
   ```bash
   nano config_priv.py
   ```
   
   Fill in:
   - `TELEGRAM_BOT_TOKEN` - Your bot token from @BotFather
   - `TELEGRAM_AUTHORIZED_USERS` - List of Telegram user IDs
   - `REBOOT_PASSWORD` - Your reboot password
   - `MQTT_NEIGHBOR_PASSWORD` - Your MQTT password
   - etc.

3. **Edit config.py for general settings:**
   ```bash
   nano config.py
   ```
   
   Configure:
   - Connection mode (serial/tcp)
   - Hardware settings (ports, hosts)
   - Feature toggles
   - etc.

4. **Verify configuration:**
   ```bash
   python3 test_config_separation.py
   ```

### For Existing Installations

If you already have a `config.py` file:

1. **Backup your current config:**
   ```bash
   cp config.py config.py.old
   ```

2. **Extract sensitive parameters:**
   ```bash
   # Create config_priv.py from template
   cp config.priv.py.sample config_priv.py
   ```

3. **Copy sensitive values from old config.py to config_priv.py:**
   
   Open both files and transfer these values:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_AUTHORIZED_USERS`
   - `TELEGRAM_ALERT_USERS`
   - `TELEGRAM_TO_MESH_MAPPING`
   - `MQTT_NEIGHBOR_PASSWORD`
   - `REBOOT_AUTHORIZED_USERS`
   - `REBOOT_PASSWORD`
   - `MESH_ALERT_SUBSCRIBED_NODES`
   - `CLI_TO_MESH_MAPPING`

4. **Update config.py from sample:**
   ```bash
   cp config.py.sample config.py
   ```

5. **Restore non-sensitive parameters:**
   
   Open `config.py.old` and `config.py` side by side.
   Transfer any customized non-sensitive values like:
   - `CONNECTION_MODE`
   - `SERIAL_PORT` or `TCP_HOST`/`TCP_PORT`
   - `LLAMA_HOST`/`LLAMA_PORT`
   - Feature enable/disable flags
   - Thresholds and intervals
   - etc.

6. **Verify configuration:**
   ```bash
   python3 test_config_separation.py
   ```

7. **Test the bot:**
   ```bash
   python3 main_script.py --debug
   ```

## What's in Each File?

### config.py (Public - Committed to Git)
- Hardware configuration (ports, hosts)
- Feature toggles (enable/disable)
- Thresholds and intervals
- AI configuration
- Non-sensitive network settings
- System limits and tuning

### config_priv.py (Private - Gitignored)
- API tokens (Telegram bot token)
- Passwords (reboot, MQTT)
- User IDs (authorized users, alert recipients)
- User-to-mesh mappings
- Subscribed node lists

## Benefits

✅ **Security**
- Secrets never committed to git
- Easier to share config publicly
- Reduced risk of token exposure

✅ **Clarity**
- Clear separation between public and private params
- Easier to review what's sensitive
- Template files show exactly what needs to be configured

✅ **No Duplicates**
- Removed duplicate CLI_* parameters
- Single source of truth for each parameter

✅ **Backward Compatible**
- Existing `from config import *` still works
- Automatic fallback if config_priv.py missing
- No code changes needed

## Troubleshooting

### Issue: "config.priv.py introuvable!" warning

**Cause:** config_priv.py doesn't exist

**Solution:**
```bash
cp config.priv.py.sample config_priv.py
nano config_priv.py  # Edit with your values
```

### Issue: Import errors when loading config

**Cause:** Syntax error in config_priv.py

**Solution:**
```bash
python3 -m py_compile config_priv.py
# Fix any syntax errors reported
```

### Issue: Bot uses wrong token/password

**Cause:** Values in config_priv.py not being imported

**Solution:**
```bash
python3 -c "import config; print(config.TELEGRAM_BOT_TOKEN)"
# Verify it shows your token, not "******************"
```

## Questions?

- Check `config.py.sample` for parameter descriptions
- Check `config.priv.py.sample` for sensitive parameter examples
- Run `python3 test_config_separation.py` to verify setup
- Consult README.md for general configuration help
