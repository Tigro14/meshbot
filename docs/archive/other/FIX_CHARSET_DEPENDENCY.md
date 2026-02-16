# Fix: Missing Character Detection Dependency

## Problem

The bot was failing to start with the following warning/error:

```
/usr/local/lib/python3.13/dist-packages/requests/__init__.py:86: RequestsDependencyWarning: 
Unable to find acceptable character detection dependency (chardet or charset_normalizer).
```

This warning was appearing during bot startup and could cause issues with HTTP requests that need character encoding detection.

## Root Cause

The `requests` library (version >=2.31.0) requires a character encoding detection library to properly handle text encoding in HTTP responses. It looks for either:

1. `charset-normalizer` (modern, recommended)
2. `chardet` (legacy fallback)

However, these dependencies were not explicitly listed in `requirements.txt`, causing the warning on fresh installations.

## Solution

Added `charset-normalizer>=3.0.0` to `requirements.txt` as an explicit dependency.

### Why charset-normalizer?

- **Modern**: Actively maintained, more accurate than chardet
- **Recommended**: The requests library maintainers recommend it
- **Faster**: Better performance than chardet
- **Compatible**: Works with all Python 3.8+ versions

## Changes Made

### requirements.txt

Added the following lines after the `requests>=2.31.0` entry:

```python
# Character encoding detection for requests
# Required by requests>=2.31.0 to properly detect text encoding
# Without this, requests will show: "Unable to find acceptable character detection dependency"
charset-normalizer>=3.0.0
```

## Testing

Created `test_charset_dependency.py` to verify:

1. ✅ Requests imports without warnings
2. ✅ charset-normalizer is available
3. ✅ Character encoding detection works

All tests pass:

```bash
$ python3 test_charset_dependency.py
======================================================================
Charset Detection Dependency Test Suite
======================================================================
Testing requests import without charset detection warnings...
✅ PASSED: No charset detection warnings

Testing charset-normalizer availability...
✅ PASSED: charset-normalizer version 3.4.4 is available

Testing requests character encoding detection...
✅ PASSED: Character encoding detection works correctly

======================================================================
Test Results Summary
======================================================================
Passed: 3/3

✅ ALL TESTS PASSED
```

## Deployment

For existing installations, update dependencies:

```bash
pip install -r requirements.txt --upgrade
```

Or on Raspberry Pi OS / managed systems:

```bash
pip install -r requirements.txt --upgrade --break-system-packages
```

## Verification

After updating, verify no warnings appear:

```bash
sudo systemctl restart meshbot
journalctl -u meshbot -n 50 | grep -i "character detection"
```

Expected: No output (no warnings)

## Related Issues

This fixes the startup warning that was preventing the bot from starting cleanly on fresh Python 3.13 installations.

## References

- [Requests library documentation](https://requests.readthedocs.io/)
- [charset-normalizer on PyPI](https://pypi.org/project/charset-normalizer/)
- [Requests changelog for v2.31.0](https://github.com/psf/requests/releases/tag/v2.31.0)
