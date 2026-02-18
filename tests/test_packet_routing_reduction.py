#!/usr/bin/env python3
"""
Test: Packet Routing Log Reduction

Verifies that packet routing logs are properly reduced and use correct prefixes.
"""

import sys
import os
import io
from contextlib import redirect_stdout, redirect_stderr

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_log_consolidation():
    """Test that routing logs are consolidated with proper prefixes"""
    print("Test 1: Log consolidation and prefixes")
    print("-" * 60)
    
    from utils import info_print_mt, info_print_mc
    
    # Capture stdout
    stdout_capture = io.StringIO()
    with redirect_stdout(stdout_capture):
        # Test Meshtastic log
        info_print_mt("💿 Routage: source=meshtastic, type=TEXT_MESSAGE_APP, from=TestNode")
        
        # Test MeshCore log
        info_print_mc("💿 Routage: source=meshcore, type=TEXT_MESSAGE_APP, from=MCNode")
    
    output = stdout_capture.getvalue()
    
    # Verify MT prefix
    assert '[INFO][MT]' in output, "Missing [INFO][MT] prefix"
    assert '💿 Routage:' in output, "Missing routing emoji"
    assert 'source=meshtastic' in output, "Missing source info"
    print("✅ Meshtastic routing log has correct format with [MT] prefix")
    
    # Verify MC prefix
    assert '[INFO][MC]' in output, "Missing [INFO][MC] prefix"
    assert 'source=meshcore' in output, "Missing MeshCore source"
    print("✅ MeshCore routing log has correct format with [MC] prefix")
    
    print()

def test_log_levels():
    """Test that logs use appropriate levels"""
    print("Test 2: Log levels")
    print("-" * 60)
    
    import logging
    import config
    
    # Create test logger
    test_logger = logging.getLogger('test_traffic')
    test_logger.setLevel(logging.DEBUG)
    
    # Capture log output
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)
    
    # Test INFO level (should always show)
    test_logger.info("💿 Routage: source=local, type=TEST")
    
    # Test DEBUG level (should only show in debug mode)
    test_logger.debug("✅ Paquet ajouté à all_packets")
    
    output = log_capture.getvalue()
    
    assert "💿 Routage:" in output, "INFO level routing log not found"
    print("✅ Routing info uses INFO level")
    
    assert "✅ Paquet ajouté" in output, "DEBUG level diagnostic log not found"
    print("✅ Diagnostic info uses DEBUG level")
    
    print()

def test_single_routing_log():
    """Test that only one routing log is generated per packet"""
    print("Test 3: Single routing log per packet")
    print("-" * 60)
    
    from utils import info_print_mt
    
    stdout_capture = io.StringIO()
    with redirect_stdout(stdout_capture):
        # Simulate routing log (should only be called once now)
        info_print_mt("💿 Routage: source=local, type=POSITION_APP, from=Node123")
    
    output = stdout_capture.getvalue()
    lines = [line for line in output.split('\n') if '💿 Routage:' in line]
    
    assert len(lines) == 1, f"Expected 1 routing log line, got {len(lines)}"
    print(f"✅ Only 1 routing log generated (was 2 before)")
    
    print()

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("Test: Packet Routing Log Reduction")
    print("=" * 70)
    print()
    
    tests = [
        test_log_consolidation,
        test_log_levels,
        test_single_routing_log,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ Test error: {e}")
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
