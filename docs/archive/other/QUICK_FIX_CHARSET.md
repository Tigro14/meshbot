# Quick Fix: Charset Detection Dependency

## The Problem

Bot startup shows:
```
RequestsDependencyWarning: Unable to find acceptable character detection dependency
```

## The Fix (One Line)

Add to your environment:

```bash
pip install charset-normalizer
```

Or update from requirements.txt:

```bash
cd /home/dietpi/bot  # or wherever your bot is
git pull
pip install -r requirements.txt --upgrade --break-system-packages
sudo systemctl restart meshbot
```

## Verify It Works

```bash
journalctl -u meshbot -n 20
```

You should NO LONGER see the "Unable to find acceptable character detection dependency" warning.

## What Changed?

**requirements.txt** now includes:
```
charset-normalizer>=3.0.0
```

This is required by the `requests` library for proper HTTP character encoding detection.

## Test the Fix

```bash
python3 test_charset_dependency.py
```

Expected output:
```
✅ ALL TESTS PASSED
```

---

**That's it!** One dependency addition, bot starts cleanly.
