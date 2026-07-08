#!/usr/bin/env python3
"""
Test script for Open-Meteo API integration

Tests the new get_weather_openmeteo() function with France's weather model.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils_weather import get_weather_openmeteo
from utils import info_print, error_print


def test_openmeteo_default():
    """Test with default config (Paris)"""
    print("\n" + "="*60)
    print("TEST 1: Open-Meteo avec config par défaut (Paris)")
    print("="*60)
    
    result = get_weather_openmeteo()
    print(f"\nRésultat:\n{result}")
    
    # Vérifier que le résultat n'est pas une erreur
    if "❌" in result:
        error_print("❌ Test échoué: erreur retournée")
        return False
    else:
        info_print("✅ Test réussi: données météo reçues")
        return True


def test_openmeteo_custom_coords():
    """Test avec coordonnées personnalisées (Lyon)"""
    print("\n" + "="*60)
    print("TEST 2: Open-Meteo avec coordonnées Lyon (45.75, 4.85)")
    print("="*60)
    
    result = get_weather_openmeteo(lat=45.75, lon=4.85)
    print(f"\nRésultat:\n{result}")
    
    # Vérifier que le résultat n'est pas une erreur
    if "❌" in result:
        error_print("❌ Test échoué: erreur retournée")
        return False
    else:
        info_print("✅ Test réussi: données météo reçues")
        return True


def test_weather_data_integration():
    """Test intégration avec get_weather_data()"""
    print("\n" + "="*60)
    print("TEST 3: Intégration get_weather_data() (WEATHER_USE_OPENMETEO=True)")
    print("="*60)
    
    from utils_weather import get_weather_data
    
    result = get_weather_data()
    print(f"\nRésultat:\n{result}")
    
    # Vérifier que le résultat n'est pas une erreur
    if "❌" in result:
        error_print("❌ Test échoué: erreur retournée")
        return False
    else:
        info_print("✅ Test réussi: données météo reçues via get_weather_data()")
        return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 TESTS OPEN-METEO API")
    print("="*60)
    
    results = []
    
    # Test 1: Default config
    results.append(("Default config (Paris)", test_openmeteo_default()))
    
    # Test 2: Custom coordinates
    results.append(("Custom coords (Lyon)", test_openmeteo_custom_coords()))
    
    # Test 3: Integration
    results.append(("get_weather_data() integration", test_weather_data_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    # Overall result
    all_passed = all(result[1] for result in results)
    print("\n" + "="*60)
    if all_passed:
        print("✅ TOUS LES TESTS RÉUSSIS")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
