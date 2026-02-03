#!/usr/bin/env python3
"""
CLI Test Script for Vigilance Météo-France API

⚠️  DEPRECATED: This script tests the OLD vigilancemeteo module which is
    broken and has been replaced by vigilance_scraper.py

    For testing the NEW scraper, use: test_vigilance_scraper.py

This script tests the vigilancemeteo module to verify:
1. Module installation and import
2. API connectivity and data retrieval
3. Department weather alert functionality
4. Error handling and retry logic
5. Data validation and format checking

Usage:
    python3 test_vigilance_cli.py [department_number]
    
    Example: python3 test_vigilance_cli.py 25
    
    If no department is specified, defaults to '75' (Paris)

NOTE: This test is kept for historical/diagnostic purposes only.
      Production code uses vigilance_scraper.py instead.
"""

import sys
import time
import socket
import http.client
from datetime import datetime


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(test_name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"     {details}")


def test_module_import():
    """Test 1: Check if vigilancemeteo module can be imported"""
    print_section("TEST 1: Module Import")
    
    try:
        import vigilancemeteo
        print_result("vigilancemeteo module import", True, 
                    f"Version: {getattr(vigilancemeteo, '__version__', 'unknown')}")
        return True, vigilancemeteo
    except ImportError as e:
        print_result("vigilancemeteo module import", False, str(e))
        print("\n💡 Fix: Install vigilancemeteo with:")
        print("   pip install vigilancemeteo")
        return False, None


def test_api_connectivity():
    """Test 2: Check connectivity to Météo-France API"""
    print_section("TEST 2: API Connectivity")
    
    # Météo-France vigilance API endpoints
    test_urls = [
        ('vigilance.meteofrance.fr', 80, '/data/NXFR33_LFPW_.xml'),
    ]
    
    all_passed = True
    for host, port, path in test_urls:
        try:
            # Test HTTP connection
            conn = http.client.HTTPConnection(host, port, timeout=10)
            conn.request("HEAD", path)
            response = conn.getresponse()
            conn.close()
            
            passed = response.status in [200, 301, 302]
            print_result(f"Connection to {host}", passed, 
                        f"Status: {response.status}")
            all_passed = all_passed and passed
            
        except Exception as e:
            print_result(f"Connection to {host}", False, str(e))
            all_passed = False
    
    return all_passed


def test_department_alert(departement='75', timeout=10):
    """Test 3: Retrieve department weather alert"""
    print_section(f"TEST 3: Department Alert Retrieval (Dept: {departement})")
    
    try:
        import vigilancemeteo
        
        # Test with timeout
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        
        try:
            print(f"🔍 Fetching vigilance data for department {departement}...")
            start_time = time.time()
            
            zone = vigilancemeteo.DepartmentWeatherAlert(departement)
            
            elapsed = time.time() - start_time
            print_result("Department alert creation", True, 
                        f"Completed in {elapsed:.2f}s")
            
            return True, zone
            
        except Exception as e:
            elapsed = time.time() - start_time
            print_result("Department alert creation", False, 
                        f"{type(e).__name__}: {str(e)[:100]}")
            print(f"     Time elapsed: {elapsed:.2f}s")
            return False, None
            
        finally:
            socket.setdefaulttimeout(old_timeout)
            
    except ImportError:
        print_result("Department alert creation", False, 
                    "vigilancemeteo not installed")
        return False, None


def test_alert_data(zone):
    """Test 4: Validate alert data structure and content"""
    print_section("TEST 4: Alert Data Validation")
    
    if zone is None:
        print_result("Alert data validation", False, "No zone object to validate")
        return False
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Department color
    tests_total += 1
    try:
        color = zone.department_color
        valid_colors = ['Vert', 'Jaune', 'Orange', 'Rouge']
        passed = color in valid_colors
        print_result(f"Department color: '{color}'", passed, 
                    f"Valid colors: {', '.join(valid_colors)}")
        tests_passed += passed
    except Exception as e:
        print_result("Department color", False, str(e))
    
    # Test 2: Summary message
    tests_total += 1
    try:
        summary = zone.summary_message('text')
        passed = isinstance(summary, str) and len(summary) > 0
        print_result("Summary message", passed, 
                    f"Length: {len(summary)} chars")
        if passed and len(summary) < 200:
            print(f"     Preview: {summary[:100]}...")
        tests_passed += passed
    except Exception as e:
        print_result("Summary message", False, str(e))
    
    # Test 3: Bulletin date
    tests_total += 1
    try:
        bulletin_date = zone.bulletin_date
        passed = bulletin_date is not None
        print_result("Bulletin date", passed, 
                    f"Date: {bulletin_date}")
        tests_passed += passed
    except Exception as e:
        print_result("Bulletin date", False, str(e))
    
    # Test 4: Additional info URL
    tests_total += 1
    try:
        url = zone.additional_info_URL
        passed = isinstance(url, str) and url.startswith('http')
        print_result("Additional info URL", passed, 
                    f"URL: {url[:50]}...")
        tests_passed += passed
    except Exception as e:
        print_result("Additional info URL", False, str(e))
    
    # Test 5: Alert list (if available)
    tests_total += 1
    try:
        if hasattr(zone, 'get_alerts'):
            alerts = zone.get_alerts()
            passed = alerts is not None
            print_result("Alert list", passed, 
                        f"Alerts: {len(alerts) if alerts else 0}")
        else:
            print_result("Alert list", True, "Method not available (optional)")
            passed = True
        tests_passed += passed
    except Exception as e:
        print_result("Alert list", False, str(e))
    
    print(f"\n📊 Data validation: {tests_passed}/{tests_total} tests passed")
    return tests_passed == tests_total


def test_retry_logic(departement='75'):
    """Test 5: Test retry logic with timeout"""
    print_section("TEST 5: Retry Logic and Error Handling")
    
    try:
        import vigilancemeteo
    except ImportError:
        print_result("Retry logic test", False, "vigilancemeteo not installed")
        return False
    
    max_retries = 3
    base_delay = 2
    timeout = 5  # Short timeout to potentially trigger retries
    
    print(f"🔄 Testing with {max_retries} retries, {timeout}s timeout...")
    
    for attempt in range(max_retries):
        try:
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(timeout)
            
            try:
                print(f"\n  Attempt {attempt + 1}/{max_retries}...")
                start = time.time()
                zone = vigilancemeteo.DepartmentWeatherAlert(departement)
                elapsed = time.time() - start
                
                color = zone.department_color
                print(f"  ✅ Success in {elapsed:.2f}s - Color: {color}")
                
                print_result("Retry logic test", True, 
                            f"Succeeded on attempt {attempt + 1}")
                return True
                
            finally:
                socket.setdefaulttimeout(old_timeout)
                
        except (http.client.RemoteDisconnected, 
                socket.timeout,
                ConnectionResetError) as e:
            
            elapsed = time.time() - start
            error_type = type(e).__name__
            
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"  ⚠️  {error_type} after {elapsed:.2f}s - Retry in {delay}s...")
                time.sleep(delay)
            else:
                print(f"  ❌ {error_type} after {elapsed:.2f}s - All retries exhausted")
                print_result("Retry logic test", False, 
                            f"Failed after {max_retries} attempts")
                return False
                
        except Exception as e:
            print_result("Retry logic test", False, 
                        f"{type(e).__name__}: {str(e)[:100]}")
            return False
    
    return False


def display_summary(zone):
    """Display detailed summary of vigilance data"""
    print_section("VIGILANCE DATA SUMMARY")
    
    if zone is None:
        print("❌ No data available")
        return
    
    try:
        print(f"📍 Department Color:  {zone.department_color}")
        print(f"📅 Bulletin Date:     {zone.bulletin_date}")
        print(f"🔗 Info URL:          {zone.additional_info_URL}")
        print(f"\n📝 Summary:")
        print(f"   {zone.summary_message('text')}")
        
        # Try to get more details if available
        if hasattr(zone, 'get_alerts'):
            try:
                alerts = zone.get_alerts()
                if alerts:
                    print(f"\n⚠️  Active Alerts: {len(alerts)}")
                    for i, alert in enumerate(alerts[:3], 1):  # Show max 3
                        print(f"   {i}. {alert}")
            except:
                pass
                
    except Exception as e:
        print(f"❌ Error displaying summary: {e}")


def main():
    """Main test runner"""
    # Print deprecation warning
    print("\n" + "🔔" * 40)
    print("⚠️  DEPRECATION WARNING")
    print("🔔" * 40)
    print()
    print("This test script is for the OLD 'vigilancemeteo' module which is")
    print("BROKEN and has been REPLACED in production code.")
    print()
    print("✅ For testing the NEW scraper, use: test_vigilance_scraper.py")
    print()
    print("This test is kept for historical/diagnostic purposes only.")
    print("Production code uses vigilance_scraper.py")
    print("🔔" * 40 + "\n")
    
    # Parse command line arguments
    departement = sys.argv[1] if len(sys.argv) > 1 else '75'
    
    print("=" * 80)
    print("  VIGILANCE MÉTÉO-FRANCE CLI TEST (DEPRECATED)")
    print("=" * 80)
    print(f"Department: {departement}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Track overall results
    results = {}
    
    # Test 1: Module import
    passed, vigilancemeteo_module = test_module_import()
    results['import'] = passed
    if not passed:
        print("\n❌ CRITICAL: Cannot proceed without vigilancemeteo module")
        sys.exit(1)
    
    # Test 2: API connectivity
    results['connectivity'] = test_api_connectivity()
    
    # Test 3: Department alert retrieval
    passed, zone = test_department_alert(departement)
    results['retrieval'] = passed
    
    # Test 4: Data validation
    if zone:
        results['validation'] = test_alert_data(zone)
    else:
        results['validation'] = False
        print_section("TEST 4: Alert Data Validation")
        print("⏭️  Skipped (no zone data available)")
    
    # Test 5: Retry logic
    results['retry'] = test_retry_logic(departement)
    
    # Display summary if we have data
    if zone:
        display_summary(zone)
    
    # Final summary
    print_section("FINAL RESULTS")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {test_name.upper()}")
    
    print(f"\n{'='*80}")
    print(f"  OVERALL: {passed_tests}/{total_tests} tests passed")
    print(f"{'='*80}")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ The vigilancemeteo module is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")
        print("❌ There may be issues with the vigilancemeteo module or API.")
        
        if not results['connectivity']:
            print("\n💡 Troubleshooting:")
            print("   - Check internet connection")
            print("   - Verify Météo-France API is accessible")
            print("   - Check firewall settings")
        
        if not results['retrieval'] and results['connectivity']:
            print("\n💡 Troubleshooting:")
            print("   - API may be temporarily unavailable")
            print("   - Try a different department number")
            print("   - Check vigilancemeteo package version")
        
        return 1


if __name__ == '__main__':
    sys.exit(main())
