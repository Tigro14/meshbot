# Vigilance Météo-France CLI Test Script

## Overview

This CLI test script (`test_vigilance_cli.py`) provides comprehensive testing of the `vigilancemeteo` Python module to verify proper functionality and API connectivity.

## Purpose

The script was created to diagnose issues with the vigilance monitoring system, specifically to:

1. Verify the `vigilancemeteo` module is properly installed
2. Test connectivity to the Météo-France API
3. Validate data retrieval for specific departments
4. Check data structure and content
5. Test retry logic and error handling

## Usage

### Basic Usage

```bash
# Test with default department (Paris - 75)
python3 test_vigilance_cli.py

# Test with specific department
python3 test_vigilance_cli.py 25    # Doubs
python3 test_vigilance_cli.py 13    # Bouches-du-Rhône
python3 test_vigilance_cli.py 06    # Alpes-Maritimes
```

### On Production Server

```bash
cd /home/dietpi/bot
python3 test_vigilance_cli.py 75
```

## Test Suite

The script runs 5 comprehensive tests:

### Test 1: Module Import
- Verifies `vigilancemeteo` module can be imported
- Shows module version if available
- **Pass Criteria**: Module imports without errors

### Test 2: API Connectivity
- Tests HTTP connection to Météo-France servers
- Checks API endpoint accessibility
- **Pass Criteria**: Successful connection to vigilance.meteofrance.fr

### Test 3: Department Alert Retrieval
- Creates a DepartmentWeatherAlert object
- Measures retrieval time
- **Pass Criteria**: Successfully retrieves data within timeout period

### Test 4: Alert Data Validation
- Validates department color (Vert/Jaune/Orange/Rouge)
- Checks summary message format
- Verifies bulletin date
- Tests additional info URL
- **Pass Criteria**: All data fields present and valid

### Test 5: Retry Logic
- Tests retry mechanism with short timeout
- Validates exponential backoff
- Simulates real-world error conditions
- **Pass Criteria**: Successfully retrieves data or handles errors gracefully

## Output Examples

### Successful Test

```
================================================================================
  VIGILANCE MÉTÉO-FRANCE CLI TEST
================================================================================
Department: 75
Time: 2025-11-23 10:30:45

================================================================================
  TEST 1: Module Import
================================================================================
✅ PASS: vigilancemeteo module import
     Version: 3.0.0

================================================================================
  TEST 2: API Connectivity
================================================================================
✅ PASS: Connection to vigilance.meteofrance.fr
     Status: 200

================================================================================
  TEST 3: Department Alert Retrieval (Dept: 75)
================================================================================
🔍 Fetching vigilance data for department 75...
✅ PASS: Department alert creation
     Completed in 1.23s

================================================================================
  TEST 4: Alert Data Validation
================================================================================
✅ PASS: Department color: 'Vert'
     Valid colors: Vert, Jaune, Orange, Rouge
✅ PASS: Summary message
     Length: 45 chars
✅ PASS: Bulletin date
     Date: 2025-11-23 06:00:00
✅ PASS: Additional info URL
     URL: http://vigilance.meteofrance.fr/...
✅ PASS: Alert list
     Method not available (optional)

📊 Data validation: 5/5 tests passed

================================================================================
  VIGILANCE DATA SUMMARY
================================================================================
📍 Department Color:  Vert
📅 Bulletin Date:     2025-11-23 06:00:00
🔗 Info URL:          http://vigilance.meteofrance.fr/...

📝 Summary:
   Pas de vigilance particulière

================================================================================
  FINAL RESULTS
================================================================================
✅ IMPORT
✅ CONNECTIVITY
✅ RETRIEVAL
✅ VALIDATION
✅ RETRY

================================================================================
  OVERALL: 5/5 tests passed
================================================================================

🎉 ALL TESTS PASSED!
✅ The vigilancemeteo module is working correctly.
```

### Failed Test (Example)

```
================================================================================
  TEST 1: Module Import
================================================================================
❌ FAIL: vigilancemeteo module import
     No module named 'vigilancemeteo'

💡 Fix: Install vigilancemeteo with:
   pip install vigilancemeteo

❌ CRITICAL: Cannot proceed without vigilancemeteo module
```

## Troubleshooting

### Module Not Found

If you get "No module named 'vigilancemeteo'":

```bash
pip install vigilancemeteo
# or
pip3 install vigilancemeteo
```

### API Connectivity Issues

If connectivity tests fail:

1. **Check internet connection**:
   ```bash
   ping vigilance.meteofrance.fr
   ```

2. **Check firewall settings**:
   ```bash
   sudo iptables -L | grep DROP
   ```

3. **Test direct HTTP access**:
   ```bash
   curl -I http://vigilance.meteofrance.fr/data/NXFR33_LFPW_.xml
   ```

### Timeout Errors

If you get `RemoteDisconnected` or timeout errors:

1. **Increase timeout** - The script uses 10s by default
2. **Check API status** - Météo-France API may be temporarily down
3. **Verify DNS resolution**:
   ```bash
   nslookup vigilance.meteofrance.fr
   ```

### Data Retrieval Failures

If data retrieval fails but connectivity works:

1. **Try different department** - Some departments may have data issues
2. **Check module version**:
   ```bash
   pip show vigilancemeteo
   ```
3. **Reinstall module**:
   ```bash
   pip uninstall vigilancemeteo
   pip install vigilancemeteo
   ```

## Integration with Main Bot

After running the test script, if all tests pass, the vigilance monitoring in the main bot should work correctly.

If tests fail, the bot's vigilance monitoring will also fail with similar errors.

### Recommended Workflow

1. Run test script to diagnose issues
2. Fix any problems identified
3. Run test script again to verify fixes
4. Restart the main bot: `sudo systemctl restart meshbot`
5. Check bot logs: `journalctl -u meshbot -f | grep vigilance`

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

This allows for scripted testing:

```bash
if python3 test_vigilance_cli.py 75; then
    echo "Vigilance API is working"
    sudo systemctl restart meshbot
else
    echo "Vigilance API has issues - bot not restarted"
fi
```

## Notes

- The script includes retry logic to handle transient network issues
- Tests are designed to be non-destructive and read-only
- Script does not require config.py or other bot dependencies
- Can be run independently of the main bot
- Useful for debugging production issues

## Related Files

- `vigilance_monitor.py` - Main vigilance monitoring module
- `test_vigilance_improvements.py` - Unit tests with mocks
- `config.py.sample` - Configuration template (VIGILANCE_* settings)

## Author

Created as part of PR to handle external curl requests gracefully (Issue #56).
