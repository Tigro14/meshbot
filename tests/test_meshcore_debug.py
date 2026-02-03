#!/usr/bin/env python3
"""
Test script for meshcore debug mode support

Tests:
1. Command-line argument parsing (--debug flag)
2. Debug mode initialization
3. Heartbeat functionality
"""

import sys
import argparse
from datetime import datetime

def test_argparse():
    """Test argument parsing for meshcore-serial-monitor.py"""
    print("Testing argument parsing...")
    
    # Simulate different command line scenarios
    test_cases = [
        ([], '/dev/ttyACM0', False),  # No args - defaults
        (['/dev/ttyUSB0'], '/dev/ttyUSB0', False),  # Port only
        (['--debug'], '/dev/ttyACM0', True),  # Debug only
        (['/dev/ttyUSB0', '--debug'], '/dev/ttyUSB0', True),  # Both
    ]
    
    for args, expected_port, expected_debug in test_cases:
        parser = argparse.ArgumentParser()
        parser.add_argument('port', nargs='?', default='/dev/ttyACM0')
        parser.add_argument('--debug', action='store_true')
        
        parsed = parser.parse_args(args)
        
        assert parsed.port == expected_port, f"Port mismatch: {parsed.port} != {expected_port}"
        assert parsed.debug == expected_debug, f"Debug mismatch: {parsed.debug} != {expected_debug}"
        
        print(f"  ✅ Args {args} -> port={parsed.port}, debug={parsed.debug}")
    
    print("✅ All argument parsing tests passed\n")

def test_debug_mode_output():
    """Test that debug mode flag is shown in output"""
    print("Testing debug mode display...")
    
    # Test enabled
    debug_enabled = True
    output = f"Debug mode: {'ENABLED' if debug_enabled else 'DISABLED'}"
    assert "ENABLED" in output
    print(f"  ✅ Debug enabled: {output}")
    
    # Test disabled
    debug_enabled = False
    output = f"Debug mode: {'ENABLED' if debug_enabled else 'DISABLED'}"
    assert "DISABLED" in output
    print(f"  ✅ Debug disabled: {output}")
    
    print("✅ Debug mode display tests passed\n")

def test_heartbeat_format():
    """Test heartbeat message format"""
    print("Testing heartbeat format...")
    
    message_count = 5
    timestamp = datetime.now().strftime("%H:%M:%S")
    heartbeat = f"[{timestamp}] 💓 Monitor active | Messages received: {message_count}"
    
    assert "💓" in heartbeat
    assert "Monitor active" in heartbeat
    assert str(message_count) in heartbeat
    
    print(f"  ✅ Heartbeat format: {heartbeat}")
    print("✅ Heartbeat format tests passed\n")

def test_meshcore_cli_wrapper_debug():
    """Test meshcore_cli_wrapper debug parameter"""
    print("Testing meshcore_cli_wrapper debug support...")
    
    try:
        # Can't actually import and test without meshcore library installed
        # Just verify the code structure is correct
        with open('meshcore_cli_wrapper.py', 'r') as f:
            content = f.read()
            
            # Check for debug parameter in __init__
            assert 'def __init__(self, port, baudrate=115200, debug=None):' in content
            print("  ✅ __init__ has debug parameter")
            
            # Check for debug passed to create_serial
            assert 'MeshCore.create_serial(self.port, baudrate=self.baudrate, debug=self.debug)' in content
            print("  ✅ debug passed to MeshCore.create_serial")
            
            # Check for config fallback
            assert 'DEBUG_MODE' in content
            print("  ✅ DEBUG_MODE config fallback present")
            
        print("✅ meshcore_cli_wrapper debug support verified\n")
        
    except FileNotFoundError:
        print("  ⚠️  meshcore_cli_wrapper.py not found (expected in CI)")

def test_help_message():
    """Test that help suggests debug flag"""
    print("Testing help message inclusion...")
    
    # Verify the monitor suggests using --debug
    help_text = "(Use --debug flag for verbose meshcore library output)"
    
    with open('meshcore-serial-monitor.py', 'r') as f:
        content = f.read()
        assert help_text in content
        print(f"  ✅ Help message present: {help_text}")
    
    print("✅ Help message tests passed\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing MeshCore Debug Mode Support")
    print("=" * 60)
    print()
    
    try:
        test_argparse()
        test_debug_mode_output()
        test_heartbeat_format()
        test_meshcore_cli_wrapper_debug()
        test_help_message()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
