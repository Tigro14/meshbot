#!/usr/bin/env python3
"""
Integration test for vigilance_monitor + vigilance_scraper

This test validates that the VigilanceMonitor correctly uses the new
vigilance_scraper module as a drop-in replacement for vigilancemeteo.
"""

import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add repo to path
repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, repo_root)

# Mock config
class MockConfig:
    DEBUG_MODE = True
    
sys.modules['config'] = MockConfig

# Mock utils
class MockUtils:
    @staticmethod
    def debug_print(msg):
        print(f"[DEBUG] {msg}")
    
    @staticmethod
    def info_print(msg):
        print(f"[INFO] {msg}")
    
    @staticmethod
    def error_print(msg):
        print(f"[ERROR] {msg}")

sys.modules['utils'] = MockUtils


def test_integration_basic():
    """Test basic integration of VigilanceMonitor with vigilance_scraper"""
    print("\n" + "="*70)
    print("TEST 1: Basic Integration")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    import vigilance_scraper
    
    # Create monitor
    monitor = VigilanceMonitor('75', check_interval=0, alert_throttle=3600)
    
    # Mock the scraper's constructor to return a pre-configured object
    with patch('vigilance_scraper.DepartmentWeatherAlert') as MockAlert:
        # Create a mock alert object with realistic data
        mock_alert = MagicMock()
        mock_alert.department_color = 'Jaune'
        mock_alert.summary_message = lambda x: 'Vigilance jaune pour orages isolés'
        mock_alert.bulletin_date = datetime.now()
        mock_alert.additional_info_URL = 'https://vigilance.meteofrance.fr/fr/paris'
        
        MockAlert.return_value = mock_alert
        
        # Check vigilance
        result = monitor.check_vigilance()
        
        if result:
            print(f"✅ PASS: Got vigilance data")
            print(f"   Color: {result['color']}")
            print(f"   Summary: {result['summary'][:50]}...")
            
            if result['color'] == 'Jaune':
                print("✅ PASS: Correct color extracted")
            else:
                print(f"❌ FAIL: Expected 'Jaune', got '{result['color']}'")
                return False
            
            if 'orages' in result['summary'].lower():
                print("✅ PASS: Correct summary extracted")
            else:
                print(f"❌ FAIL: Summary doesn't contain expected content")
                return False
        else:
            print("❌ FAIL: No vigilance data returned")
            return False
    
    print("\n✅ TEST 1 PASSED")
    return True


def test_integration_alert_logic():
    """Test alert triggering logic with new scraper"""
    print("\n" + "="*70)
    print("TEST 2: Vigilance Level Detection")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    import vigilance_scraper
    
    # Test 1: Vert level detection
    print("\n2.1: Testing Vert level detection...")
    monitor = VigilanceMonitor('75', check_interval=0, alert_throttle=3600)
    with patch('vigilance_scraper.DepartmentWeatherAlert') as MockAlert:
        mock_alert = MagicMock()
        mock_alert.department_color = 'Vert'
        mock_alert.summary_message = lambda x: 'Pas de vigilance particulière'
        mock_alert.bulletin_date = datetime.now()
        mock_alert.additional_info_URL = 'https://vigilance.meteofrance.fr/fr/paris'
        MockAlert.return_value = mock_alert
        
        result = monitor.check_vigilance()
        
        if result and result['color'] == 'Vert':
            print("✅ PASS: Vert level detected correctly")
        else:
            print(f"❌ FAIL: Expected Vert, got {result}")
            return False
    
    # Test 2: Orange level detection
    print("\n2.2: Testing Orange level detection...")
    monitor2 = VigilanceMonitor('75', check_interval=0, alert_throttle=3600)
    with patch('vigilance_scraper.DepartmentWeatherAlert') as MockAlert:
        mock_alert = MagicMock()
        mock_alert.department_color = 'Orange'
        mock_alert.summary_message = lambda x: 'Vigilance orange pour vents violents'
        mock_alert.bulletin_date = datetime.now()
        mock_alert.additional_info_URL = 'https://vigilance.meteofrance.fr/fr/paris'
        MockAlert.return_value = mock_alert
        
        result = monitor2.check_vigilance()
        
        if result and result['color'] == 'Orange':
            print("✅ PASS: Orange level detected correctly")
        else:
            print(f"❌ FAIL: Expected Orange, got {result}")
            return False
    
    # Test 3: Message formatting
    print("\n2.3: Testing message formatting...")
    if result:
        compact_msg = monitor2.format_alert_message(result, compact=True)
        long_msg = monitor2.format_alert_message(result, compact=False)
        
        print(f"Compact message ({len(compact_msg)} chars):\n{compact_msg}")
        print(f"\nLong message ({len(long_msg)} chars):\n{long_msg}")
        
        if len(compact_msg) <= 180:
            print("✅ PASS: Compact message fits in LoRa limit")
        else:
            print(f"❌ FAIL: Compact message too long ({len(compact_msg)} > 180)")
            return False
        
        if 'ORANGE' in compact_msg.upper() and 'ORANGE' in long_msg.upper():
            print("✅ PASS: Both messages contain color")
        else:
            print("❌ FAIL: Messages missing color information")
            return False
    
    print("\n✅ TEST 2 PASSED")
    return True


def test_integration_error_handling():
    """Test error handling in integration"""
    print("\n" + "="*70)
    print("TEST 3: Error Handling Integration")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    import vigilance_scraper
    import requests
    
    # Create monitor
    monitor = VigilanceMonitor('75', check_interval=0, alert_throttle=3600)
    
    # Test network error handling
    print("\n3.1: Testing network error handling...")
    with patch('vigilance_scraper.DepartmentWeatherAlert') as MockAlert:
        # Simulate network error
        MockAlert.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        # Should return None after retries
        result = monitor.check_vigilance()
        
        if result is None:
            print("✅ PASS: Network error handled gracefully")
        else:
            print(f"❌ FAIL: Expected None on error, got {result}")
            return False
    
    # Test timeout error handling
    print("\n3.2: Testing timeout error handling...")
    monitor.last_check_time = 0  # Reset
    with patch('vigilance_scraper.DepartmentWeatherAlert') as MockAlert:
        import socket
        MockAlert.side_effect = socket.timeout("Request timed out")
        
        result = monitor.check_vigilance()
        
        if result is None:
            print("✅ PASS: Timeout handled gracefully")
        else:
            print(f"❌ FAIL: Expected None on timeout, got {result}")
            return False
    
    print("\n✅ TEST 3 PASSED")
    return True


def test_integration_department_mapping():
    """Test that different departments work correctly"""
    print("\n" + "="*70)
    print("TEST 4: Department Mapping Integration")
    print("="*70)
    
    from vigilance_monitor import VigilanceMonitor
    import vigilance_scraper
    
    departments = [
        ('75', 'Paris'),
        ('25', 'Besançon'),
        ('13', 'Marseille'),
    ]
    
    for dept_num, dept_name in departments:
        print(f"\n4.{departments.index((dept_num, dept_name)) + 1}: Testing département {dept_num} ({dept_name})...")
        
        monitor = VigilanceMonitor(dept_num, check_interval=0, alert_throttle=3600)
        
        with patch('vigilance_scraper.DepartmentWeatherAlert') as MockAlert:
            mock_alert = MagicMock()
            mock_alert.department_color = 'Vert'
            mock_alert.summary_message = lambda x: f'Pas de vigilance pour {dept_name}'
            mock_alert.bulletin_date = datetime.now()
            mock_alert.additional_info_URL = f'https://vigilance.meteofrance.fr/fr/{dept_num}'
            MockAlert.return_value = mock_alert
            
            result = monitor.check_vigilance()
            
            if result and result['color'] == 'Vert':
                print(f"✅ PASS: Département {dept_num} works correctly")
            else:
                print(f"❌ FAIL: Département {dept_num} failed")
                return False
    
    print("\n✅ TEST 4 PASSED")
    return True


def main():
    """Run all integration tests"""
    print("\n" + "="*70)
    print("VIGILANCE INTEGRATION TEST SUITE")
    print("Testing VigilanceMonitor + vigilance_scraper integration")
    print("="*70)
    
    results = []
    
    tests = [
        ("Basic Integration", test_integration_basic),
        ("Vigilance Level Detection", test_integration_alert_logic),
        ("Error Handling", test_integration_error_handling),
        ("Department Mapping", test_integration_department_mapping),
    ]
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("\nThe vigilance_scraper is fully integrated with VigilanceMonitor")
        print("Ready for production use!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
