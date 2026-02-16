#!/usr/bin/env python3
"""
Verification script for vigilance refactor deployment

This script checks that:
1. vigilance_scraper module is importable
2. Production code uses vigilance_scraper (not vigilancemeteo)
3. Required dependencies are installed
4. Test suite passes
5. No references to old vigilancemeteo in production code
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import os
import subprocess

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_result(test_name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        for line in details.split('\n'):
            print(f"     {line}")

def check_imports():
    """Check that vigilance_scraper can be imported"""
    print_header("CHECK 1: Module Imports")
    
    try:
        import vigilance_scraper
        print_result("vigilance_scraper import", True, "Module found and importable")
        return True
    except ImportError as e:
        print_result("vigilance_scraper import", False, f"ImportError: {e}")
        return False

def check_dependencies():
    """Check required dependencies are installed"""
    print_header("CHECK 2: Dependencies")
    
    required = ['beautifulsoup4', 'lxml', 'requests']
    all_ok = True
    
    for package in required:
        try:
            result = subprocess.run(
                ['pip', 'show', package],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Extract version
                version_line = [l for l in result.stdout.split('\n') if l.startswith('Version:')]
                version = version_line[0].split(':')[1].strip() if version_line else 'unknown'
                print_result(f"{package} installed", True, f"Version: {version}")
            else:
                print_result(f"{package} installed", False, "Not found")
                all_ok = False
        except Exception as e:
            print_result(f"{package} installed", False, f"Error: {e}")
            all_ok = False
    
    return all_ok

def check_production_code():
    """Check production code uses vigilance_scraper"""
    print_header("CHECK 3: Production Code")
    
    files_to_check = [
        'vigilance_monitor.py',
    ]
    
    all_ok = True
    
    for filename in files_to_check:
        if not os.path.exists(filename):
            print_result(f"{filename} exists", False, "File not found")
            all_ok = False
            continue
        
        with open(filename, 'r') as f:
            content = f.read()
        
        # Check for correct import
        if 'import vigilance_scraper' in content:
            print_result(f"{filename} uses vigilance_scraper", True, 
                        "✓ Uses new scraper module")
        else:
            print_result(f"{filename} uses vigilance_scraper", False,
                        "⚠️  Does not import vigilance_scraper")
            all_ok = False
        
        # Check for old import (should not exist)
        if 'import vigilancemeteo' in content or 'from vigilancemeteo' in content:
            print_result(f"{filename} no vigilancemeteo", False,
                        "⚠️  Still contains vigilancemeteo import!")
            all_ok = False
        else:
            print_result(f"{filename} no vigilancemeteo", True,
                        "✓ No references to old module")
    
    return all_ok

def check_no_vigilancemeteo_installed():
    """Check that old vigilancemeteo is not installed"""
    print_header("CHECK 4: Old Package Removed")
    
    try:
        result = subprocess.run(
            ['pip', 'show', 'vigilancemeteo'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print_result("vigilancemeteo uninstalled", True,
                        "✓ Old broken package not found")
            return True
        else:
            print_result("vigilancemeteo uninstalled", False,
                        "⚠️  Old package still installed! Run: pip uninstall vigilancemeteo -y")
            return False
    except Exception as e:
        print_result("vigilancemeteo check", False, f"Error: {e}")
        return False

def run_scraper_tests():
    """Run vigilance_scraper test suite"""
    print_header("CHECK 5: Test Suite")
    
    if not os.path.exists('test_vigilance_scraper.py'):
        print_result("test_vigilance_scraper.py exists", False, "Test file not found")
        return False
    
    try:
        result = subprocess.run(
            ['python3', 'test_vigilance_scraper.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and 'ALL TESTS PASSED' in result.stdout:
            print_result("Test suite", True, "✓ All scraper tests passed")
            return True
        else:
            print_result("Test suite", False, 
                        f"Some tests failed\nOutput:\n{result.stdout[-500:]}")
            return False
    except subprocess.TimeoutExpired:
        print_result("Test suite", False, "Tests timed out")
        return False
    except Exception as e:
        print_result("Test suite", False, f"Error running tests: {e}")
        return False

def check_git_status():
    """Check if we're on the right branch/commit"""
    print_header("CHECK 6: Git Status")
    
    try:
        # Check current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        branch = result.stdout.strip()
        print_result("Git branch", True, f"Current branch: {branch}")
        
        # Check if vigilance_monitor.py uses scraper
        result = subprocess.run(
            ['git', 'log', '--all', '--oneline', '--grep=vigilance.*scraper', '-1'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout:
            commit = result.stdout.strip()[:50]
            print_result("Vigilance refactor commit", True, f"Found: {commit}")
        else:
            print_result("Vigilance refactor commit", False, 
                        "No vigilance scraper commits found")
        
        return True
    except Exception as e:
        print_result("Git check", False, f"Error: {e}")
        return False

def main():
    """Run all verification checks"""
    print("\n" + "🔍"*35)
    print("VIGILANCE REFACTOR VERIFICATION")
    print("🔍"*35)
    
    checks = [
        ("Module Imports", check_imports),
        ("Dependencies", check_dependencies),
        ("Production Code", check_production_code),
        ("Old Package Removed", check_no_vigilancemeteo_installed),
        ("Test Suite", run_scraper_tests),
        ("Git Status", check_git_status),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 ALL CHECKS PASSED!")
        print("\nThe vigilance refactor is correctly deployed.")
        print("You can now safely use the vigilance monitoring feature.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} check(s) failed")
        print("\nPlease review the errors above and:")
        print("1. Ensure you've pulled the latest code (git pull)")
        print("2. Installed required dependencies (pip install -r requirements.txt)")
        print("3. Uninstalled old vigilancemeteo package (pip uninstall vigilancemeteo -y)")
        print("\nSee VIGILANCE_DEPLOYMENT_GUIDE.md for detailed instructions.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
