# Vigilance Scraper Deployment Guide

## Issue Summary

The deployed system at `/home/dietpi/bot/` is running **outdated code** that still uses the broken `vigilancemeteo` package. The repository code has already been updated to use the new `vigilance_scraper` module.

## Error Symptoms

```
zone = vigilancemeteo.DepartmentWeatherAlert(self.departement)
...
http.client.RemoteDisconnected: Remote end closed connection without response
```

## Root Cause

The deployed code predates the vigilance refactoring (commit `c4a29e7`). The repository has been updated but the production system hasn't.

## Solution: Deploy Latest Code

### Step 1: Update Code on Production System

```bash
# On DietPi/production system
cd /home/dietpi/bot

# Backup current state (optional but recommended)
cp -r /home/dietpi/bot /home/dietpi/bot.backup.$(date +%Y%m%d)

# Pull latest code
git fetch origin
git pull origin main

# Or if on a branch:
# git pull origin copilot/refactor-debug-vigilancemeteo
```

### Step 2: Uninstall Old Package

```bash
# Remove the broken vigilancemeteo package
pip uninstall vigilancemeteo -y
```

### Step 3: Install New Dependencies

```bash
# Install required dependencies for vigilance_scraper
pip install beautifulsoup4>=4.12.0 lxml>=4.9.0 --break-system-packages

# Or install all requirements
pip install -r requirements.txt --break-system-packages
```

### Step 4: Verify Installation

```bash
# Test the new scraper works
cd /home/dietpi/bot
python3 test_vigilance_scraper.py

# Expected output: "✅ 5/5 tests passed"
```

### Step 5: Restart Service

```bash
# Restart the meshbot service
sudo systemctl restart meshbot

# Check status
sudo systemctl status meshbot

# Check logs for errors
journalctl -u meshbot -f
```

## Verification

After deployment, verify vigilance monitoring works:

```bash
# Check logs for vigilance activity
journalctl -u meshbot | grep -i vigilance

# Should see successful checks like:
# "✅ Vigilance check département 25: Vert"
# NOT errors like "vigilancemeteo.DepartmentWeatherAlert"
```

## Files Changed in Repository

### Production Code (Already Updated)
- ✅ `vigilance_monitor.py` - Uses `vigilance_scraper` (line 100, 107)
- ✅ `vigilance_scraper.py` - New web scraper implementation
- ✅ `requirements.txt` - Has `beautifulsoup4` and `lxml`

### Test Code (Updated in This PR)
- ✅ `test_network_resilience.py` - Patches updated to `vigilance_scraper`
- ⚠️ `test_vigilance_cli.py` - Deprecated (tests old module)
- ✅ `test_vigilance_scraper.py` - Tests new scraper

## Rollback (If Needed)

If issues occur after deployment:

```bash
# Restore backup
cd /home/dietpi
sudo systemctl stop meshbot
mv bot bot.new
mv bot.backup.YYYYMMDD bot
sudo systemctl start meshbot
```

## Additional Notes

### Why the Old Package Failed

The `vigilancemeteo` package:
- Is broken/unmaintained
- Uses deprecated Météo-France API endpoints
- Causes `RemoteDisconnected` errors
- No longer works reliably

### Why the New Scraper is Better

The `vigilance_scraper` module:
- ✅ Web scrapes current Météo-France website directly
- ✅ Multi-strategy HTML parsing (resilient to site changes)
- ✅ Drop-in replacement (same interface)
- ✅ Actively maintained in this repository
- ✅ Includes retry logic and better error handling

### Configuration

No configuration changes needed! The scraper is a drop-in replacement:

```python
# Before (OLD - broken)
import vigilancemeteo
zone = vigilancemeteo.DepartmentWeatherAlert(departement)

# After (NEW - working)
import vigilance_scraper
zone = vigilance_scraper.DepartmentWeatherAlert(departement, timeout=10)
```

## Support

If you encounter issues during deployment:

1. Check logs: `journalctl -u meshbot -f`
2. Verify dependencies: `pip list | grep -E "beautifulsoup4|lxml"`
3. Test scraper: `python3 test_vigilance_scraper.py`
4. Check network: `curl https://vigilance.meteofrance.fr/fr/besancon`

## History

- **2025-11-23**: Initial vigilance scraper implementation (commit `c4a29e7`)
- **2025-11-24**: Fixed remaining test file references (this PR)

---

**Status**: Repository code is READY. Production deployment pending.
