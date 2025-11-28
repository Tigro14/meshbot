#!/usr/bin/env python3
"""
Test script for vigilance_scraper.py

This tests the web scraper that replaces the broken vigilancemeteo module.
"""

import sys
import os

# Add repo to path
repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, repo_root)

def test_scraper_import():
    """Test that the scraper module can be imported"""
    print("\n" + "="*70)
    print("TEST 1: Import vigilance_scraper module")
    print("="*70)
    
    try:
        import vigilance_scraper
        print("✅ PASS: vigilance_scraper module imported successfully")
        return True
    except ImportError as e:
        print(f"❌ FAIL: Could not import vigilance_scraper: {e}")
        return False


def test_scraper_interface():
    """Test that the scraper has the required interface"""
    print("\n" + "="*70)
    print("TEST 2: Check scraper interface compatibility")
    print("="*70)
    
    try:
        from vigilance_scraper import DepartmentWeatherAlert
        
        # Check that the class exists
        print("✅ PASS: DepartmentWeatherAlert class exists")
        
        # Check required attributes/methods
        required_attrs = [
            'department_color',
            'summary_message',
            'bulletin_date',
            'additional_info_URL'
        ]
        
        # Note: We can't actually instantiate without network access
        # but we can check the class has the required methods
        for attr in required_attrs:
            if hasattr(DepartmentWeatherAlert, attr):
                print(f"✅ PASS: Has attribute/method '{attr}'")
            else:
                print(f"❌ FAIL: Missing attribute/method '{attr}'")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error checking interface: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_department_name_mapping():
    """Test that department name mapping works"""
    print("\n" + "="*70)
    print("TEST 3: Department name mapping")
    print("="*70)
    
    try:
        from vigilance_scraper import DepartmentWeatherAlert
        
        # Create a dummy instance to test the method
        # We'll mock the _fetch_data to avoid network call
        import unittest.mock as mock
        
        with mock.patch.object(DepartmentWeatherAlert, '_fetch_data'):
            alert = DepartmentWeatherAlert('75')
            
            # Test various department mappings
            test_cases = [
                ('75', 'paris'),
                ('25', 'besancon'),
                ('13', 'marseille'),
                ('69', 'lyon'),
                ('99', '99'),  # Unknown dept should return the number
            ]
            
            for dept, expected in test_cases:
                result = alert._get_department_name(dept)
                if result == expected:
                    print(f"✅ PASS: Department {dept} → {result}")
                else:
                    print(f"❌ FAIL: Department {dept} expected {expected}, got {result}")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing department mapping: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_color_normalization():
    """Test color normalization function"""
    print("\n" + "="*70)
    print("TEST 4: Color normalization")
    print("="*70)
    
    try:
        from vigilance_scraper import DepartmentWeatherAlert
        import unittest.mock as mock
        
        with mock.patch.object(DepartmentWeatherAlert, '_fetch_data'):
            alert = DepartmentWeatherAlert('75')
            
            # Test various color inputs
            test_cases = [
                ('vert', 'Vert'),
                ('green', 'Vert'),
                ('jaune', 'Jaune'),
                ('yellow', 'Jaune'),
                ('orange', 'Orange'),
                ('rouge', 'Rouge'),
                ('red', 'Rouge'),
                ('unknown', 'Vert'),  # Unknown should default to Vert
            ]
            
            for input_color, expected in test_cases:
                result = alert._normalize_color(input_color)
                if result == expected:
                    print(f"✅ PASS: '{input_color}' → '{result}'")
                else:
                    print(f"❌ FAIL: '{input_color}' expected '{expected}', got '{result}'")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing color normalization: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mock_html_parsing():
    """Test HTML parsing with mock data"""
    print("\n" + "="*70)
    print("TEST 5: HTML parsing with mock data")
    print("="*70)
    
    try:
        from vigilance_scraper import DepartmentWeatherAlert
        from bs4 import BeautifulSoup
        import unittest.mock as mock
        
        # Create mock HTML with vigilance information
        mock_html = """
        <html>
            <body>
                <div class="vigilance-orange">
                    <h1>Vigilance Météo</h1>
                    <p class="summary">Vigilance orange pour vents violents et pluie-inondation</p>
                    <time datetime="2024-11-23T10:00:00">23/11/2024 10:00</time>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        
        with mock.patch.object(DepartmentWeatherAlert, '_fetch_data'):
            alert = DepartmentWeatherAlert('75')
            
            # Test color extraction
            color = alert._extract_color(soup)
            print(f"Extracted color: {color}")
            if color == 'Orange':
                print("✅ PASS: Color extraction works")
            else:
                print(f"❌ FAIL: Expected 'Orange', got '{color}'")
                return False
            
            # Test summary extraction
            summary = alert._extract_summary(soup)
            print(f"Extracted summary: {summary[:50]}...")
            if 'vents violents' in summary.lower() or 'vigilance' in summary.lower():
                print("✅ PASS: Summary extraction works")
            else:
                print(f"❌ FAIL: Summary doesn't contain expected content")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing HTML parsing: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_no_false_positive_from_legend_text():
    """Test that legend/explanatory text doesn't trigger false color detection"""
    print("\n" + "="*70)
    print("TEST 6: No false positive from legend/explanatory text")
    print("="*70)
    
    try:
        from vigilance_scraper import DepartmentWeatherAlert
        from bs4 import BeautifulSoup
        import unittest.mock as mock
        
        # This HTML simulates a page with NO active alert but mentions
        # colors in legend and explanatory text - the bug was that this
        # was incorrectly detected as "Rouge"
        mock_html_no_alert = """
        <html>
            <body>
                <h1>Vigilance Météo</h1>
                <div class="vigilance-map">
                    <p>La carte de vigilance pour demain sera disponible à partir de 06h.</p>
                </div>
                <div class="legend">
                    <p>Niveaux de vigilance:</p>
                    <ul>
                        <li>Vert: Pas de vigilance</li>
                        <li>Jaune: Soyez attentif</li>
                        <li>Orange: Soyez très vigilant</li>
                        <li>Rouge: Une vigilance absolue</li>
                    </ul>
                </div>
                <div class="footer">
                    Pour la vigilance rouge, consultez les recommandations.
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(mock_html_no_alert, 'html.parser')
        
        with mock.patch.object(DepartmentWeatherAlert, '_fetch_data'):
            alert = DepartmentWeatherAlert('75')
            
            # Test color extraction - should be Vert, not Rouge
            color = alert._extract_color(soup)
            print(f"Extracted color: {color}")
            
            if color == 'Vert':
                print("✅ PASS: Correctly returned Vert (no false positive)")
                return True
            else:
                print(f"❌ FAIL: Expected 'Vert' but got '{color}' (false positive from legend text)")
                return False
        
    except Exception as e:
        print(f"❌ FAIL: Error testing false positive prevention: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("VIGILANCE SCRAPER TEST SUITE")
    print("Testing replacement for broken vigilancemeteo module")
    print("="*70)
    
    results = []
    
    # Run tests
    tests = [
        ("Module Import", test_scraper_import),
        ("Interface Compatibility", test_scraper_interface),
        ("Department Mapping", test_department_name_mapping),
        ("Color Normalization", test_color_normalization),
        ("HTML Parsing", test_mock_html_parsing),
        ("No False Positive From Legend", test_no_false_positive_from_legend_text),
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
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe vigilance_scraper module is ready to replace vigilancemeteo")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
