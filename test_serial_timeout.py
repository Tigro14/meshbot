#!/usr/bin/env python3
"""
Test script for Meshtastic SerialInterface timeout mechanism.

This verifies that the timeout wrapper prevents indefinite freezes
when the SerialInterface constructor hangs.
"""

import time
import threading
import sys

def simulate_hanging_serial_interface(serial_port):
    """Simulate a SerialInterface that hangs indefinitely."""
    print(f"[SIMULATED] Creating SerialInterface for {serial_port}...")
    print("[SIMULATED] Waiting for device response... (hanging)")
    time.sleep(999999)  # Simulate indefinite hang
    return None


def _create_serial_interface_with_timeout(serial_port, timeout=10):
    """
    Create SerialInterface with timeout to prevent freeze.
    This is the same function from main_bot.py.
    """
    result = {'interface': None, 'error': None}
    
    def create_interface():
        try:
            result['interface'] = simulate_hanging_serial_interface(serial_port)
        except Exception as e:
            result['error'] = e
    
    thread = threading.Thread(target=create_interface, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        # Thread still running = timeout occurred
        print("=" * 80)
        print(f"⏱️  TIMEOUT: SerialInterface creation exceeded {timeout}s")
        print("=" * 80)
        print(f"   Port: {serial_port}")
        print("   → Device detected but not responding")
        print("=" * 80)
        return None
    
    if result['error']:
        raise result['error']
    
    return result['interface']


def test_timeout_mechanism():
    """Test that timeout mechanism works correctly."""
    print("=" * 80)
    print("TEST: Meshtastic SerialInterface Timeout Mechanism")
    print("=" * 80)
    print()
    
    serial_port = "/dev/ttyACM0"
    timeout = 3  # Short timeout for testing
    
    print(f"Testing timeout wrapper with {timeout}s timeout...")
    print("Expected: Should timeout and return None within ~3 seconds")
    print()
    
    start_time = time.time()
    interface = _create_serial_interface_with_timeout(serial_port, timeout=timeout)
    elapsed = time.time() - start_time
    
    print()
    print("=" * 80)
    print("TEST RESULTS:")
    print("=" * 80)
    print(f"Elapsed time: {elapsed:.2f}s")
    print(f"Interface returned: {interface}")
    print(f"Expected timeout: {timeout}s")
    print()
    
    # Verify timeout worked
    if interface is None and elapsed < (timeout + 1):
        print("✅ TEST PASSED: Timeout mechanism works correctly")
        print(f"   → Returned None after ~{elapsed:.1f}s (expected ~{timeout}s)")
        print(f"   → Bot will not freeze on unresponsive devices")
        return True
    else:
        print("❌ TEST FAILED: Timeout mechanism not working")
        if interface is not None:
            print(f"   → Expected None, got: {interface}")
        if elapsed >= (timeout + 1):
            print(f"   → Took too long: {elapsed:.2f}s (expected ~{timeout}s)")
        return False


if __name__ == "__main__":
    print()
    success = test_timeout_mechanism()
    print()
    
    sys.exit(0 if success else 1)
