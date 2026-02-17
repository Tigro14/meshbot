#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for /trafficmc command handler
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import only what we need to test the specific functionality
# We'll test the TrafficMonitor method directly since BusinessStatsCommands is a thin wrapper


def test_trafficmc_method_exists():
    """Test that the get_traffic_report_mc method exists and is callable"""
    print("=" * 60)
    print("TEST: Method Availability Check")
    print("=" * 60)
    
    # Import just the traffic_monitor module
    from traffic_monitor import TrafficMonitor
    
    # Check that the method exists
    assert hasattr(TrafficMonitor, 'get_traffic_report_mc'), \
        "TrafficMonitor should have get_traffic_report_mc method"
    
    # Check that it's callable
    import inspect
    assert callable(getattr(TrafficMonitor, 'get_traffic_report_mc')), \
        "get_traffic_report_mc should be callable"
    
    # Check method signature
    sig = inspect.signature(TrafficMonitor.get_traffic_report_mc)
    params = list(sig.parameters.keys())
    print(f"\nMethod signature: {sig}")
    print(f"Parameters: {params}")
    
    assert 'self' in params, "Should have self parameter"
    assert 'hours' in params, "Should have hours parameter"
    
    # Check default value for hours
    default_hours = sig.parameters['hours'].default
    print(f"Default hours: {default_hours}")
    assert default_hours == 8, "Default hours should be 8"
    
    print("\n✅ Method exists with correct signature!")
    print("=" * 60)


def test_method_docstring():
    """Test that the method has proper documentation"""
    print("\n" + "=" * 60)
    print("TEST: Documentation Check")
    print("=" * 60)
    
    from traffic_monitor import TrafficMonitor
    
    docstring = TrafficMonitor.get_traffic_report_mc.__doc__
    print(f"\nDocstring:\n{docstring}")
    
    assert docstring is not None, "Method should have a docstring"
    assert "MeshCore" in docstring, "Docstring should mention MeshCore"
    
    print("\n✅ Method has proper documentation!")
    print("=" * 60)


def test_comparison_with_existing_method():
    """Compare the new method with the existing get_traffic_report method"""
    print("\n" + "=" * 60)
    print("TEST: Method Comparison")
    print("=" * 60)
    
    from traffic_monitor import TrafficMonitor
    import inspect
    
    # Get signatures
    sig_original = inspect.signature(TrafficMonitor.get_traffic_report)
    sig_new = inspect.signature(TrafficMonitor.get_traffic_report_mc)
    
    print(f"\nOriginal method: {sig_original}")
    print(f"New MC method: {sig_new}")
    
    # Both should have same parameters
    assert list(sig_original.parameters.keys()) == list(sig_new.parameters.keys()), \
        "Both methods should have same parameters"
    
    print("\n✅ Method signatures match!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_trafficmc_method_exists()
        test_method_docstring()
        test_comparison_with_existing_method()
        
        print("\n" + "=" * 60)
        print("🎉 ALL INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nSummary:")
        print("  ✅ get_traffic_report_mc() method exists")
        print("  ✅ Method has correct signature (hours=8)")
        print("  ✅ Method has proper documentation")
        print("  ✅ Method signature matches existing get_traffic_report()")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
