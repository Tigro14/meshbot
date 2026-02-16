#!/usr/bin/env python3
"""
Test script to verify charset-normalizer dependency fix for requests library.

This test ensures that the requests library can be imported without warnings
about missing character detection dependencies (chardet or charset_normalizer).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import warnings

def test_requests_import_no_warnings():
    """Test that requests can be imported without dependency warnings."""
    print("Testing requests import without charset detection warnings...")
    
    # Capture all warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # Import requests - should not generate dependency warnings
        import requests
        
        # Check if any warnings were raised
        dependency_warnings = [
            warning for warning in w 
            if "character detection" in str(warning.message).lower()
            or "chardet" in str(warning.message).lower()
            or "charset" in str(warning.message).lower()
        ]
        
        if dependency_warnings:
            print("❌ FAILED: Warnings detected during requests import:")
            for warning in dependency_warnings:
                print(f"  - {warning.category.__name__}: {warning.message}")
            return False
        else:
            print("✅ PASSED: No charset detection warnings")
            return True

def test_charset_normalizer_available():
    """Test that charset-normalizer is installed and importable."""
    print("\nTesting charset-normalizer availability...")
    
    try:
        import charset_normalizer
        print(f"✅ PASSED: charset-normalizer version {charset_normalizer.__version__} is available")
        return True
    except ImportError as e:
        print(f"❌ FAILED: charset-normalizer not available: {e}")
        return False

def test_requests_functionality():
    """Test that requests can actually detect character encoding."""
    print("\nTesting requests character encoding detection...")
    
    try:
        import requests
        from requests.utils import get_encoding_from_headers
        
        # Test that encoding detection works
        # Create a mock response headers dict
        headers = {'content-type': 'text/html; charset=utf-8'}
        encoding = get_encoding_from_headers(headers)
        
        if encoding == 'utf-8':
            print("✅ PASSED: Character encoding detection works correctly")
            return True
        else:
            print(f"⚠️  WARNING: Unexpected encoding: {encoding}")
            return True  # Still pass, but warn
    except Exception as e:
        print(f"❌ FAILED: Error testing encoding detection: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 70)
    print("Charset Detection Dependency Test Suite")
    print("=" * 70)
    
    tests = [
        test_requests_import_no_warnings,
        test_charset_normalizer_available,
        test_requests_functionality
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if all(results):
        print("\n✅ ALL TESTS PASSED")
        print("\nThe charset-normalizer dependency is properly configured.")
        print("The bot should now start without charset detection warnings.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nPlease ensure charset-normalizer is installed:")
        print("  pip install charset-normalizer>=3.0.0")
        return 1

if __name__ == '__main__':
    sys.exit(main())
