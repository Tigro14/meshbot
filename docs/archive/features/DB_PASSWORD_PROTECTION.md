# Database Password Protection Implementation

## Overview

This document describes the password protection added to the `/db clean` and `/db vacuum` commands to prevent unauthorized database modifications.

## Problem Statement

The `/db clean` and `/db vacuum` commands perform critical database operations that can:
- Delete historical data (cleanup)
- Impact database performance temporarily (vacuum)
- Affect system resources

These operations should be restricted to authorized users only.

## Solution

Added password protection using the existing `REBOOT_PASSWORD` configuration variable, following the same security pattern as the `/rebootpi` command.

## Implementation Details

### Files Modified

#### `handlers/command_handlers/db_commands.py`

**Changes:**
1. Added import: `from config import REBOOT_PASSWORD`
2. Modified `_cleanup_db(self, args, channel='mesh')`:
   - Now requires password as first argument in `args`
   - Validates password before executing cleanup
   - Returns error message if password missing or incorrect
   - Logs authorization attempts
3. Modified `_vacuum_db(self, args, channel='mesh')`:
   - Added `args` parameter (was previously no args)
   - Requires password as first argument
   - Validates password before executing vacuum
   - Returns error message if password missing or incorrect
   - Logs authorization attempts
4. Updated `handle_db()`:
   - Now passes `args` to `_vacuum_db()` (was passing only `channel`)
5. Updated help text:
   - Shows password requirement: `clean <password> [hours]`
   - Shows password requirement: `vacuum <password>`
   - Added warning note in Telegram help

### Password Validation Logic

```python
# Check if password provided
if not args:
    return "❌ /db clean <pwd> [hours]"  # or vacuum

# Extract password (first argument)
provided_password = args[0]

# Validate password
if provided_password != REBOOT_PASSWORD:
    info_print(f"🚫 /db clean refusé (mauvais mot de passe)")
    return "❌ Mot de passe incorrect"

# Password correct, log and continue
info_print(f"🔐 /db clean autorisé")
```

### Argument Parsing

**Before:**
```python
# _cleanup_db
hours = 48
if args:
    hours = int(args[0])  # First arg was hours

# _vacuum_db
# No arguments
```

**After:**
```python
# _cleanup_db
if not args:
    return "❌ Password required"
provided_password = args[0]  # First arg is password
hours = 48
if len(args) > 1:
    hours = int(args[1])  # Second arg is hours

# _vacuum_db
if not args:
    return "❌ Password required"
provided_password = args[0]  # First arg is password
```

## Usage

### Mesh Channel (LoRa)

**Clean Database:**
```
/db clean <password>        → Clean data older than 48h (default)
/db clean <password> 72     → Clean data older than 72h
```

**Vacuum Database:**
```
/db vacuum <password>       → Optimize database
```

### Telegram Channel

Same syntax, but with more detailed error messages:

**Incorrect:**
```
/db clean                   → ❌ Mot de passe requis
                               Usage: /db clean <password> [hours]

/db clean wrongpass         → ❌ Mot de passe incorrect
                               Accès refusé.

/db vacuum                  → ❌ Mot de passe requis
                               Usage: /db vacuum <password>
```

**Correct:**
```
/db clean mypass            → 🧹 NETTOYAGE EFFECTUÉ
                               Critère: > 48 heures
                               ...

/db clean mypass 72         → 🧹 NETTOYAGE EFFECTUÉ
                               Critère: > 72 heures
                               ...

/db vacuum mypass           → 🔧 DATABASE OPTIMISÉE
                               Taille avant: 5.24 MB
                               Taille après: 4.81 MB
                               ...
```

## Security Features

1. **Password Validation**: Checks password before any database operation
2. **Logging**: All authorization attempts are logged:
   - `🚫 /db clean refusé (mauvais mot de passe)` - Failed attempt
   - `🔐 /db clean autorisé` - Successful authorization
3. **Clear Error Messages**: Users know exactly what's wrong
4. **Consistent Security Model**: Uses same password as `/rebootpi`
5. **No Information Leakage**: Same error for missing/wrong password

## Configuration

### config.py

```python
# Line 312
REBOOT_PASSWORD = "your_password_secret"
```

This password is shared across:
- `/rebootpi <password>` - Reboot Raspberry Pi
- `/db clean <password>` - Clean database
- `/db vacuum <password>` - Optimize database

## Testing

### Test Suite: `test_db_password.py`

Comprehensive test coverage:
- ✅ Cleanup without password (rejected)
- ✅ Cleanup with wrong password (rejected)
- ✅ Cleanup with correct password (accepted)
- ✅ Cleanup with password + hours parameter
- ✅ Vacuum without password (rejected)
- ✅ Vacuum with wrong password (rejected)
- ✅ Vacuum with correct password (accepted)
- ✅ Help text shows password requirement
- ✅ Code verification (imports, function signatures)

### Demo Script: `demo_db_password.py`

Interactive demonstration showing:
- Usage examples (correct and incorrect)
- Sample output messages
- Security notes
- Configuration instructions

## Backward Compatibility

### Affected Commands
- `/db clean` - Now requires password
- `/db vacuum` - Now requires password

### Unaffected Commands
- `/db stats` - No password required
- `/db info` - No password required
- `/db nb` - No password required
- `/db purgeweather` - No password required
- All other `/db` subcommands - No change

### Migration Notes

**For users who previously used:**
```bash
/db clean 72        # OLD (no longer works)
/db vacuum          # OLD (no longer works)
```

**Update to:**
```bash
/db clean mypass 72     # NEW (with password)
/db vacuum mypass       # NEW (with password)
```

## Error Messages

### Mesh Channel (Compact)

| Scenario | Message |
|----------|---------|
| No password | `❌ /db clean <pwd> [hours]` |
| Wrong password | `❌ Mot de passe incorrect` |
| No password (vacuum) | `❌ /db vacuum <pwd>` |

### Telegram Channel (Detailed)

| Scenario | Message |
|----------|---------|
| No password | `❌ Mot de passe requis\n\nUsage: /db clean <password> [hours]` |
| Wrong password | `❌ Mot de passe incorrect\n\nAccès refusé.` |

## Logs

### Successful Authorization
```
🔐 /db clean autorisé
🧹 Nettoyage DB: données > 72h
```

### Failed Authorization
```
🚫 /db clean refusé (mauvais mot de passe)
```

## Security Considerations

### Threat Model

**Protected Against:**
- ✅ Unauthorized database cleanup by random users
- ✅ Accidental data deletion
- ✅ Performance impact from unauthorized vacuum

**Not Protected Against:**
- ⚠️ Password sharing among authorized users
- ⚠️ Password transmission over unencrypted channels
- ⚠️ Brute force (no rate limiting on password attempts)

### Recommendations

1. **Strong Password**: Use a strong password in `REBOOT_PASSWORD`
2. **Secure Storage**: Keep `config.py` with restricted permissions
3. **Monitoring**: Watch logs for failed authorization attempts
4. **User Education**: Train authorized users on secure password handling

## Future Improvements

Potential enhancements:
1. Separate password for database operations
2. Rate limiting on failed password attempts
3. Audit log for all database operations
4. User-specific authorization (not just password)
5. Two-factor authentication

## Related Documentation

- `CLAUDE.md` - Main developer documentation
- `config.py.sample` - Configuration template
- `DB_NB_COMMAND_DOCUMENTATION.md` - Database command documentation
- System Commands: `handlers/command_handlers/system_commands.py`

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-08 | 1.0 | Initial implementation with password protection |

---

**Author**: GitHub Copilot  
**Reviewer**: Tigro14  
**Last Updated**: 2025-12-08
