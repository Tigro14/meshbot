#!/usr/bin/env python3
"""
Test script for weather SQLite caching enhancements
Tests the "serve first, refresh later" pattern implementation
"""

import sys
import os
import time
import tempfile

def test_persistence_weather_cache_with_age():
    """Test get_weather_cache_with_age method exists and works"""
    print("🧪 Test 1: TrafficPersistence.get_weather_cache_with_age()...")
    
    from traffic_persistence import TrafficPersistence
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        persistence = TrafficPersistence(db_path)
        
        # Test 1a: Store some data
        persistence.set_weather_cache('test_location', 'weather', 'Test weather data')
        print("  ✅ set_weather_cache() works")
        
        # Test 1b: Retrieve with age
        data, age_hours = persistence.get_weather_cache_with_age('test_location', 'weather')
        assert data == 'Test weather data', f"Expected 'Test weather data', got '{data}'"
        assert age_hours == 0, f"Expected age_hours=0 (just created), got {age_hours}"
        print("  ✅ get_weather_cache_with_age() returns data and age")
        
        # Test 1c: Non-existent location returns (None, 0)
        data, age_hours = persistence.get_weather_cache_with_age('nonexistent', 'weather')
        assert data is None, f"Expected None, got '{data}'"
        assert age_hours == 0, f"Expected age_hours=0, got {age_hours}"
        print("  ✅ get_weather_cache_with_age() returns (None, 0) for missing data")
        
        persistence.close()
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


def test_get_weather_data_persistence_param():
    """Test that get_weather_data accepts persistence parameter"""
    print("\n🧪 Test 2: get_weather_data() accepts persistence parameter...")
    
    with open('utils_weather.py', 'r') as f:
        content = f.read()
    
    # Check function signature
    if 'def get_weather_data(location=None, persistence=None):' in content:
        print("  ✅ get_weather_data() has persistence parameter")
        return True
    else:
        print("  ❌ get_weather_data() missing persistence parameter")
        return False


def test_serve_first_pattern_in_get_weather_data():
    """Test that get_weather_data implements serve-first pattern"""
    print("\n🧪 Test 3: get_weather_data() implements serve-first pattern...")
    
    with open('utils_weather.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('get_weather_cache_with_age', 'Uses get_weather_cache_with_age'),
        ('Cache SQLite FRESH', 'Fresh cache handling'),
        ('Cache SQLite STALE', 'Stale cache handling'),
        ('persistence.set_weather_cache', 'Saves to SQLite cache'),
    ]
    
    all_ok = True
    for check, desc in checks:
        if check in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ Missing: {check}")
            all_ok = False
    
    return all_ok


def test_serve_first_pattern_in_get_rain_graph():
    """Test that get_rain_graph implements serve-first pattern"""
    print("\n🧪 Test 4: get_rain_graph() implements serve-first pattern...")
    
    with open('utils_weather.py', 'r') as f:
        content = f.read()
    
    # Check for cached_data initialization before try block
    checks = [
        ('cached_data = None', 'cached_data initialized'),
        ('cache_age_seconds = 0', 'cache_age_seconds initialized'),
        ('Cache SQLite rain FRESH', 'Fresh rain cache handling'),
        ('Cache SQLite rain STALE', 'Stale rain cache handling'),
    ]
    
    all_ok = True
    for check, desc in checks:
        if check in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ Missing: {check}")
            all_ok = False
    
    return all_ok


def test_serve_first_pattern_in_get_weather_astro():
    """Test that get_weather_astro implements serve-first pattern"""
    print("\n🧪 Test 5: get_weather_astro() implements serve-first pattern...")
    
    with open('utils_weather.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('Cache SQLite astro FRESH', 'Fresh astro cache handling'),
        ('Cache SQLite astro STALE', 'Stale astro cache handling'),
    ]
    
    all_ok = True
    for check, desc in checks:
        if check in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ Missing: {check}")
            all_ok = False
    
    return all_ok


def test_utility_commands_uses_persistence():
    """Test that utility_commands.py passes persistence to weather functions"""
    print("\n🧪 Test 6: utility_commands.py uses persistence for weather...")
    
    with open('handlers/command_handlers/utility_commands.py', 'r') as f:
        content = f.read()
    
    checks = [
        ('get_weather_data(location, persistence=persistence)', 'get_weather_data uses persistence'),
        ('get_rain_graph(', 'get_rain_graph is used'),
        ('get_weather_astro(', 'get_weather_astro is used'),
    ]
    
    all_ok = True
    for check, desc in checks:
        if check in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ Missing: {check}")
            all_ok = False
    
    return all_ok


def test_syntax():
    """Test Python syntax of modified files"""
    print("\n🧪 Test 7: Python syntax validation...")
    
    import subprocess
    
    files = [
        'utils_weather.py',
        'traffic_persistence.py',
        'handlers/command_handlers/utility_commands.py'
    ]
    
    all_ok = True
    for file in files:
        try:
            result = subprocess.run(
                ['python3', '-m', 'py_compile', file],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"  ✅ {file} - syntax OK")
            else:
                print(f"  ❌ {file} - syntax error:")
                print(f"     {result.stderr}")
                all_ok = False
        except Exception as e:
            print(f"  ❌ {file} - error: {e}")
            all_ok = False
    
    return all_ok


def main():
    print("=" * 70)
    print("🧪 Weather SQLite Cache Enhancement Tests")
    print("=" * 70)
    
    tests = [
        test_persistence_weather_cache_with_age,
        test_get_weather_data_persistence_param,
        test_serve_first_pattern_in_get_weather_data,
        test_serve_first_pattern_in_get_rain_graph,
        test_serve_first_pattern_in_get_weather_astro,
        test_utility_commands_uses_persistence,
        test_syntax,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
