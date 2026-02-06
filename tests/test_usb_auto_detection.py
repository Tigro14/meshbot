#!/usr/bin/env python3
"""
Test USB port auto-detection functionality
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from usb_port_detector import USBPortDetector


def test_port_config_parsing():
    """Test various configuration string formats"""
    
    print("Testing port configuration parsing...")
    
    # Test 1: Regular port should pass through unchanged
    result = USBPortDetector.detect_port("/dev/ttyACM0")
    assert result == "/dev/ttyACM0", f"Expected /dev/ttyACM0, got {result}"
    print("✅ Test 1: Regular port passes through")
    
    # Test 2: None should return None
    result = USBPortDetector.detect_port(None)
    assert result is None, f"Expected None, got {result}"
    print("✅ Test 2: None passes through")
    
    # Test 3: Empty string should return empty string
    result = USBPortDetector.detect_port("")
    assert result == "", f"Expected empty string, got {result}"
    print("✅ Test 3: Empty string passes through")
    
    # Test 4: Non-auto config should pass through
    result = USBPortDetector.detect_port("/dev/ttyUSB0")
    assert result == "/dev/ttyUSB0", f"Expected /dev/ttyUSB0, got {result}"
    print("✅ Test 4: Non-auto config passes through")
    
    print("")
    print("All configuration parsing tests passed!")


def test_detection_formats():
    """Test detection logic with various format strings"""
    
    print("")
    print("Testing detection format parsing...")
    
    # These tests won't find actual devices, but should parse correctly
    # and return None (not raise exceptions)
    
    test_cases = [
        "auto",
        "auto:HT-n5262",
        "auto:product=HT-n5262",
        "auto:serial=B5A131E366B43F18",
        "auto:manufacturer=Heltec",
        "auto:product=HT-n5262,serial=B5A1",
        "auto:vendor=239a,productid=4405",
    ]
    
    for config in test_cases:
        try:
            result = USBPortDetector.detect_port(config)
            # Should return None (no device found) but not crash
            print(f"✅ Parsed: {config} → {result or 'Not found (expected)'}")
        except Exception as e:
            print(f"❌ Failed to parse: {config}")
            print(f"   Error: {e}")
            raise
    
    print("")
    print("All detection format tests passed!")


def test_list_devices():
    """Test device listing (may return empty list if no devices)"""
    
    print("")
    print("Testing device listing...")
    
    try:
        devices = USBPortDetector.list_usb_serial_devices()
        print(f"✅ Device listing successful: {len(devices)} device(s) found")
        
        if devices:
            print("")
            print("Detected devices:")
            for dev in devices:
                print(f"  - {dev['port']}: {dev.get('manufacturer', 'N/A')} {dev.get('product', 'N/A')}")
        else:
            print("  (No USB serial devices detected - this is OK for testing)")
            
    except Exception as e:
        print(f"❌ Device listing failed: {e}")
        raise
    
    print("")
    print("Device listing test passed!")


def test_resolve_port():
    """Test the main resolve_port function"""
    
    print("")
    print("Testing port resolution...")
    
    # Test with regular port
    result = USBPortDetector.resolve_port("/dev/ttyACM0", "TestDevice")
    assert result == "/dev/ttyACM0", f"Expected /dev/ttyACM0, got {result}"
    print("✅ Regular port resolution works")
    
    # Test with auto (will fallback if no devices)
    result = USBPortDetector.resolve_port("auto:NonExistent", "TestDevice")
    # Should return original config as fallback
    assert result == "auto:NonExistent", f"Expected fallback to config, got {result}"
    print("✅ Auto-detection fallback works")
    
    print("")
    print("Port resolution test passed!")


def run_all_tests():
    """Run all tests"""
    
    print("=" * 80)
    print("USB Port Auto-Detection Tests")
    print("=" * 80)
    
    try:
        test_port_config_parsing()
        test_detection_formats()
        test_list_devices()
        test_resolve_port()
        
        print("")
        print("=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        return True
        
    except Exception as e:
        print("")
        print("=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
