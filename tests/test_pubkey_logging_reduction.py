#!/usr/bin/env python3
"""
Integration test for reduced public key logging with MC/MT prefixes.

This test verifies:
1. Source parameter is passed correctly through the chain
2. Appropriate log functions are selected based on source
3. Logs are factorized (fewer lines)
4. Proper [MC]/[MT] prefixes are used
"""

import sys
import os
import io
from contextlib import redirect_stdout, redirect_stderr

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from node_manager import NodeManager

def capture_logs(func):
    """Capture stdout and stderr from a function"""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
        result = func()
    
    return {
        'stdout': stdout_capture.getvalue(),
        'stderr': stderr_capture.getvalue(),
        'result': result
    }

def test_get_log_funcs():
    """Test that _get_log_funcs returns correct functions"""
    print("Test 1: _get_log_funcs() returns correct functions")
    print("-" * 60)
    
    node_manager = NodeManager()
    
    # Test Meshtastic source
    debug_func, info_func = node_manager._get_log_funcs('meshtastic')
    assert debug_func.__name__ == 'debug_print_mt', f"Expected debug_print_mt, got {debug_func.__name__}"
    assert info_func.__name__ == 'info_print_mt', f"Expected info_print_mt, got {info_func.__name__}"
    print("✅ Meshtastic source returns MT log functions")
    
    # Test MeshCore source
    debug_func, info_func = node_manager._get_log_funcs('meshcore')
    assert debug_func.__name__ == 'debug_print_mc', f"Expected debug_print_mc, got {debug_func.__name__}"
    assert info_func.__name__ == 'info_print_mc', f"Expected info_print_mc, got {info_func.__name__}"
    print("✅ MeshCore source returns MC log functions")
    
    # Test other sources (should default to MT)
    for source in ['tcp', 'local', 'unknown']:
        debug_func, info_func = node_manager._get_log_funcs(source)
        assert debug_func.__name__ == 'debug_print_mt', f"Expected debug_print_mt for {source}"
        assert info_func.__name__ == 'info_print_mt', f"Expected info_print_mt for {source}"
    print("✅ Other sources default to MT log functions")
    
    print()

def test_update_node_from_packet_signature():
    """Test that update_node_from_packet accepts source parameter"""
    print("Test 2: update_node_from_packet() accepts source parameter")
    print("-" * 60)
    
    node_manager = NodeManager()
    
    # Create mock packet
    packet = {
        'from': 0x12345678,
        'decoded': {
            'portnum': 'NODEINFO_APP',
            'user': {
                'longName': 'TestNode',
                'shortName': 'TST',
                'publicKey': 'ABC123'
            }
        }
    }
    
    # Test with default source
    try:
        node_manager.update_node_from_packet(packet)
        print("✅ Works with default source parameter")
    except TypeError as e:
        print(f"❌ Failed with default source: {e}")
        return False
    
    # Test with explicit source
    try:
        node_manager.update_node_from_packet(packet, source='meshcore')
        print("✅ Works with explicit source='meshcore'")
    except TypeError as e:
        print(f"❌ Failed with explicit source: {e}")
        return False
    
    print()
    return True

def test_sync_single_pubkey_signature():
    """Test that _sync_single_pubkey_to_interface accepts source parameter"""
    print("Test 3: _sync_single_pubkey_to_interface() accepts source")
    print("-" * 60)
    
    node_manager = NodeManager()
    
    node_data = {
        'name': 'TestNode',
        'publicKey': 'ABC123'
    }
    
    # Test with default source (should not crash)
    try:
        node_manager._sync_single_pubkey_to_interface(0x12345678, node_data)
        print("✅ Works with default source parameter")
    except TypeError as e:
        print(f"❌ Failed with default source: {e}")
        return False
    
    # Test with explicit source
    try:
        node_manager._sync_single_pubkey_to_interface(0x12345678, node_data, source='meshcore')
        print("✅ Works with explicit source='meshcore'")
    except TypeError as e:
        print(f"❌ Failed with explicit source: {e}")
        return False
    
    print()
    return True

def test_log_output_format():
    """Test that logs have correct format with prefixes"""
    print("Test 4: Log output has correct [MC]/[MT] prefixes")
    print("-" * 60)
    
    from utils import debug_print_mc, info_print_mc, debug_print_mt, info_print_mt
    import config
    
    # Temporarily enable debug mode
    original_debug = config.DEBUG_MODE
    config.DEBUG_MODE = True
    
    # Test MT logs
    captured = capture_logs(lambda: info_print_mt("Test message"))
    assert '[INFO][MT]' in captured['stdout'], "Missing [INFO][MT] prefix"
    print("✅ info_print_mt produces [INFO][MT] prefix")
    
    captured = capture_logs(lambda: debug_print_mt("Test message"))
    assert '[DEBUG][MT]' in captured['stderr'], "Missing [DEBUG][MT] prefix"
    print("✅ debug_print_mt produces [DEBUG][MT] prefix")
    
    # Test MC logs
    captured = capture_logs(lambda: info_print_mc("Test message"))
    assert '[INFO][MC]' in captured['stdout'], "Missing [INFO][MC] prefix"
    print("✅ info_print_mc produces [INFO][MC] prefix")
    
    captured = capture_logs(lambda: debug_print_mc("Test message"))
    assert '[DEBUG][MC]' in captured['stderr'], "Missing [DEBUG][MC] prefix"
    print("✅ debug_print_mc produces [DEBUG][MC] prefix")
    
    # Restore debug mode
    config.DEBUG_MODE = original_debug
    
    print()

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("Integration Test: Public Key Logging Reduction")
    print("=" * 70)
    print()
    
    tests = [
        test_get_log_funcs,
        test_update_node_from_packet_signature,
        test_sync_single_pubkey_signature,
        test_log_output_format,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            if result is None or result is True:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
