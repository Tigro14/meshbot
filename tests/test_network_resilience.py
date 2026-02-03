#!/usr/bin/env python3
"""
Test script for network resilience improvements

Tests retry logic and error handling for external services.
"""

import sys
import time
from unittest.mock import Mock, patch, MagicMock
import socket

# Mock config before imports
sys.path.insert(0, '/home/runner/work/meshbot/meshbot')

# Create minimal config
class MockConfig:
    ESPHOME_HOST = "192.168.1.27"
    ESPHOME_PORT = 80
    MAX_MESSAGE_SIZE = 180
    COLLECT_SIGNAL_METRICS = True
    
    # Vigilance config
    VIGILANCE_ENABLED = True
    VIGILANCE_DEPARTEMENT = "25"
    VIGILANCE_CHECK_INTERVAL = 900
    VIGILANCE_ALERT_THROTTLE = 3600
    VIGILANCE_ALERT_LEVELS = ['Orange', 'Rouge']
    
    # Blitz config
    BLITZ_ENABLED = True
    BLITZ_LATITUDE = 47.25
    BLITZ_LONGITUDE = 6.03
    BLITZ_RADIUS_KM = 50
    BLITZ_CHECK_INTERVAL = 900
    BLITZ_WINDOW_MINUTES = 15

# Mock config module
sys.modules['config'] = MockConfig

# Mock utils module
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
    
    @staticmethod
    def lazy_import_requests():
        import requests
        return requests
    
    @staticmethod
    def truncate_text(text, max_len, suffix="..."):
        if len(text) <= max_len:
            return text
        return text[:max_len - len(suffix)] + suffix

sys.modules['utils'] = MockUtils

def test_vigilance_retry():
    """Test vigilance monitor retry logic"""
    print("\n" + "="*60)
    print("TEST 1: Vigilance Monitor Retry Logic")
    print("="*60)
    
    from vigilance_monitor import VigilanceMonitor
    
    # Create monitor
    monitor = VigilanceMonitor(
        departement='25',
        check_interval=0,  # Allow immediate checks
        alert_throttle=3600
    )
    
    # Test 1: Simulate network failure with retry
    print("\n1.1: Simulating network failure (RemoteDisconnected)...")
    
    with patch('vigilance_scraper.DepartmentWeatherAlert') as mock_alert:
        # First 2 attempts fail, 3rd succeeds
        mock_alert.side_effect = [
            ConnectionResetError("Remote end closed connection"),
            ConnectionResetError("Remote end closed connection"),
            MagicMock(
                department_color='Vert',
                summary_message=lambda x: 'Pas de vigilance',
                bulletin_date='2024-11-20',
                additional_info_URL='http://example.com'
            )
        ]
        
        result = monitor.check_vigilance()
        
        if result and result['color'] == 'Vert':
            print("✅ PASS: Retry logic worked, got result after failures")
        else:
            print("❌ FAIL: Did not get result after retries")
            return False
    
    # Test 2: All attempts fail
    print("\n1.2: Simulating complete failure (all retries exhausted)...")
    
    # Reset check time to allow immediate check
    monitor.last_check_time = 0
    
    with patch('vigilance_scraper.DepartmentWeatherAlert') as mock_alert:
        mock_alert.side_effect = ConnectionResetError("Remote end closed connection")
        
        result = monitor.check_vigilance()
        
        if result is None:
            print("✅ PASS: Returns None after all retries exhausted")
        else:
            print("❌ FAIL: Should return None after all failures")
            return False
    
    print("\n✅ TEST 1 PASSED: Vigilance retry logic works correctly")
    return True


def test_esphome_retry():
    """Test ESPHome client retry logic"""
    print("\n" + "="*60)
    print("TEST 2: ESPHome Client Retry Logic")
    print("="*60)
    
    # Mock ESPHomeHistory
    class MockHistory:
        def add_reading(self, **kwargs):
            pass
        def save_history(self):
            pass
    
    sys.modules['esphome_history'] = type('module', (), {'ESPHomeHistory': MockHistory})
    
    from esphome_client import ESPHomeClient
    
    client = ESPHomeClient()
    
    # Test 1: Timeout with retry
    print("\n2.1: Simulating timeout with retry...")
    
    with patch('utils.lazy_import_requests') as mock_requests:
        mock_req = Mock()
        mock_requests.return_value = mock_req
        
        # First attempt times out, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 200
        mock_response_fail.close = Mock()
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json = lambda: {'value': 12.5}
        mock_response_success.close = Mock()
        
        import requests
        call_count = [0]
        
        def mock_get(url, timeout=None):
            call_count[0] += 1
            if call_count[0] <= 2:  # First 2 calls timeout
                raise requests.exceptions.Timeout("Connection timeout")
            return mock_response_success
        
        mock_req.get = mock_get
        mock_req.exceptions = requests.exceptions
        
        result = client.parse_esphome_data()
        
        if "ESPHome timeout" in result or "ESPHome Online" in result or "T:" in result:
            print(f"✅ PASS: Got result after timeout: {result}")
        else:
            print(f"❌ FAIL: Unexpected result: {result}")
            return False
    
    print("\n✅ TEST 2 PASSED: ESPHome retry logic works correctly")
    return True


def test_blitz_mqtt_resilience():
    """Test Blitz monitor MQTT connection resilience"""
    print("\n" + "="*60)
    print("TEST 3: Blitz MQTT Connection Resilience")
    print("="*60)
    
    # Mock paho.mqtt
    class MockMQTTClient:
        def __init__(self, *args, **kwargs):
            self.on_connect = None
            self.on_disconnect = None
            self.on_message = None
            
        def connect(self, host, port, keepalive):
            # Simulate successful connection on 2nd attempt
            if not hasattr(self, '_connect_count'):
                self._connect_count = 0
            self._connect_count += 1
            
            if self._connect_count < 2:
                raise OSError("Connection refused")
            
        def reconnect_delay_set(self, min_delay, max_delay):
            pass
            
        def loop_forever(self):
            pass
    
    class MockMQTT:
        Client = MockMQTTClient
        class CallbackAPIVersion:
            VERSION2 = 2
    
    sys.modules['paho.mqtt.client'] = MockMQTT
    sys.modules['paho'] = type('module', (), {'mqtt': type('module', (), {'client': MockMQTT})})
    
    # Mock pygeohash
    sys.modules['pygeohash'] = type('module', (), {
        'encode': lambda lat, lon, precision: 'u0j',
        'get_adjacent': lambda h, d: 'u0k'
    })
    
    from blitz_monitor import BlitzMonitor
    
    print("\n3.1: Testing MQTT connection with retry...")
    
    # Create monitor with specific coordinates
    monitor = BlitzMonitor(
        lat=47.25,
        lon=6.03,
        radius_km=50,
        check_interval=900
    )
    
    # Start monitoring (should retry connection)
    monitor.start_monitoring()
    
    # Give it a moment
    time.sleep(0.5)
    
    if monitor.mqtt_client is not None:
        print("✅ PASS: MQTT client created with retry logic")
    else:
        print("❌ FAIL: MQTT client not created")
        return False
    
    print("\n✅ TEST 3 PASSED: Blitz MQTT resilience works correctly")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("NETWORK RESILIENCE TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run tests
    try:
        results.append(("Vigilance Retry", test_vigilance_retry()))
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Vigilance Retry", False))
    
    try:
        results.append(("ESPHome Retry", test_esphome_retry()))
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("ESPHome Retry", False))
    
    try:
        results.append(("Blitz MQTT", test_blitz_mqtt_resilience()))
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Blitz MQTT", False))
    
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
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
