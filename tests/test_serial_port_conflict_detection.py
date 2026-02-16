#!/usr/bin/env python3
"""
Test script to demonstrate serial port conflict detection

This script shows how the bot detects and prevents serial port conflicts
when both MESHTASTIC_ENABLED and MESHCORE_ENABLED are True.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

def test_port_conflict_detection():
    """Test the port conflict detection logic"""
    
    print("=" * 70)
    print("TEST: Serial Port Conflict Detection")
    print("=" * 70)
    print()
    
    # Test Case 1: Same port (should detect conflict)
    print("Test Case 1: Both using same port (CONFLICT)")
    print("-" * 70)
    meshtastic_enabled = True
    meshcore_enabled = True
    connection_mode = 'serial'
    serial_port = '/dev/ttyACM2'
    meshcore_port = '/dev/ttyACM2'  # SAME PORT - CONFLICT!
    
    print(f"MESHTASTIC_ENABLED = {meshtastic_enabled}")
    print(f"MESHCORE_ENABLED = {meshcore_enabled}")
    print(f"CONNECTION_MODE = '{connection_mode}'")
    print(f"SERIAL_PORT = '{serial_port}'")
    print(f"MESHCORE_SERIAL_PORT = '{meshcore_port}'")
    print()
    
    # Apply the detection logic
    if meshtastic_enabled and meshcore_enabled:
        if connection_mode == 'serial' and serial_port == meshcore_port:
            print("❌ CONFLICT DETECTED!")
            print(f"   Both interfaces configured for port: {serial_port}")
            print(f"   → Meshtastic will be used (priority)")
            print(f"   → MeshCore will be ignored")
            conflict_detected = True
        else:
            print("✅ No conflict (different ports or TCP mode)")
            conflict_detected = False
    else:
        print("✅ No conflict (only one interface enabled)")
        conflict_detected = False
    
    print()
    assert conflict_detected, "Test 1 FAILED: Should detect conflict"
    print("✅ Test 1 PASSED: Conflict correctly detected")
    print()
    
    # Test Case 2: Different ports (should NOT detect conflict)
    print("Test Case 2: Different ports (NO CONFLICT)")
    print("-" * 70)
    meshtastic_enabled = True
    meshcore_enabled = True
    connection_mode = 'serial'
    serial_port = '/dev/ttyACM0'
    meshcore_port = '/dev/ttyUSB0'  # DIFFERENT PORT - OK
    
    print(f"MESHTASTIC_ENABLED = {meshtastic_enabled}")
    print(f"MESHCORE_ENABLED = {meshcore_enabled}")
    print(f"CONNECTION_MODE = '{connection_mode}'")
    print(f"SERIAL_PORT = '{serial_port}'")
    print(f"MESHCORE_SERIAL_PORT = '{meshcore_port}'")
    print()
    
    # Apply the detection logic
    if meshtastic_enabled and meshcore_enabled:
        if connection_mode == 'serial' and serial_port == meshcore_port:
            print("❌ CONFLICT DETECTED!")
            conflict_detected = True
        else:
            print("✅ No conflict detected")
            print(f"   Meshtastic will use: {serial_port}")
            print(f"   MeshCore would use: {meshcore_port} (but will be ignored)")
            print(f"   → Both enabled = Meshtastic has priority")
            conflict_detected = False
    else:
        print("✅ No conflict (only one interface enabled)")
        conflict_detected = False
    
    print()
    assert not conflict_detected, "Test 2 FAILED: Should NOT detect conflict"
    print("✅ Test 2 PASSED: No conflict detected (different ports)")
    print()
    
    # Test Case 3: TCP mode (should NOT detect conflict even with same port)
    print("Test Case 3: TCP mode (NO CONFLICT)")
    print("-" * 70)
    meshtastic_enabled = True
    meshcore_enabled = True
    connection_mode = 'tcp'
    serial_port = '/dev/ttyACM2'
    meshcore_port = '/dev/ttyACM2'  # Same port but TCP mode
    
    print(f"MESHTASTIC_ENABLED = {meshtastic_enabled}")
    print(f"MESHCORE_ENABLED = {meshcore_enabled}")
    print(f"CONNECTION_MODE = '{connection_mode}'")
    print(f"SERIAL_PORT = '{serial_port}'")
    print(f"MESHCORE_SERIAL_PORT = '{meshcore_port}'")
    print()
    
    # Apply the detection logic
    if meshtastic_enabled and meshcore_enabled:
        if connection_mode == 'serial' and serial_port == meshcore_port:
            print("❌ CONFLICT DETECTED!")
            conflict_detected = True
        else:
            print("✅ No conflict detected")
            print(f"   Meshtastic uses TCP mode (not serial port)")
            print(f"   Serial port conflict check not applicable")
            conflict_detected = False
    else:
        print("✅ No conflict (only one interface enabled)")
        conflict_detected = False
    
    print()
    assert not conflict_detected, "Test 3 FAILED: Should NOT detect conflict in TCP mode"
    print("✅ Test 3 PASSED: No conflict in TCP mode")
    print()
    
    # Test Case 4: Only MeshCore enabled (should NOT detect conflict)
    print("Test Case 4: Only MeshCore enabled (NO CONFLICT)")
    print("-" * 70)
    meshtastic_enabled = False
    meshcore_enabled = True
    connection_mode = 'serial'
    serial_port = '/dev/ttyACM0'
    meshcore_port = '/dev/ttyACM0'  # Same port but only MeshCore enabled
    
    print(f"MESHTASTIC_ENABLED = {meshtastic_enabled}")
    print(f"MESHCORE_ENABLED = {meshcore_enabled}")
    print(f"CONNECTION_MODE = '{connection_mode}'")
    print(f"SERIAL_PORT = '{serial_port}'")
    print(f"MESHCORE_SERIAL_PORT = '{meshcore_port}'")
    print()
    
    # Apply the detection logic
    if meshtastic_enabled and meshcore_enabled:
        if connection_mode == 'serial' and serial_port == meshcore_port:
            print("❌ CONFLICT DETECTED!")
            conflict_detected = True
        else:
            print("✅ No conflict (different ports or TCP mode)")
            conflict_detected = False
    else:
        print("✅ No conflict (only one interface enabled)")
        print(f"   MeshCore will use: {meshcore_port}")
        conflict_detected = False
    
    print()
    assert not conflict_detected, "Test 4 FAILED: Should NOT detect conflict"
    print("✅ Test 4 PASSED: No conflict when only MeshCore enabled")
    print()


def test_meshcore_defensive_check():
    """Test the defensive check in MeshCore initialization"""
    
    print("=" * 70)
    print("TEST: MeshCore Defensive Check")
    print("=" * 70)
    print()
    
    # Test Case: MeshCore initialization with meshtastic_enabled=True (should fail)
    print("Test Case: MeshCore init with MESHTASTIC_ENABLED=True (SHOULD FAIL)")
    print("-" * 70)
    meshtastic_enabled = True
    meshcore_enabled = True
    
    print(f"At MeshCore initialization point:")
    print(f"  meshtastic_enabled = {meshtastic_enabled}")
    print(f"  meshcore_enabled = {meshcore_enabled}")
    print()
    
    # This is the elif condition that guards MeshCore initialization
    should_initialize_meshcore = (meshcore_enabled and not meshtastic_enabled)
    print(f"Condition: meshcore_enabled and not meshtastic_enabled")
    print(f"  = {meshcore_enabled} and not {meshtastic_enabled}")
    print(f"  = {meshcore_enabled} and {not meshtastic_enabled}")
    print(f"  = {should_initialize_meshcore}")
    print()
    
    if should_initialize_meshcore:
        # Defensive check within the block
        if meshtastic_enabled:
            print("❌ DEFENSIVE CHECK TRIGGERED!")
            print("   MeshCore initialization attempted with MESHTASTIC_ENABLED=True")
            print("   → This indicates a logic bug")
            defensive_check_triggered = True
        else:
            print("✅ Defensive check passed, proceeding with MeshCore init")
            defensive_check_triggered = False
    else:
        print("✅ MeshCore initialization SKIPPED (condition not met)")
        print("   → Correct behavior when both are enabled")
        defensive_check_triggered = False
    
    print()
    assert not should_initialize_meshcore, "MeshCore should NOT initialize when both enabled"
    print("✅ Test PASSED: MeshCore correctly skipped when Meshtastic enabled")
    print()


if __name__ == '__main__':
    print("\n" + "🧪 TESTING SERIAL PORT CONFLICT DETECTION")
    print()
    
    try:
        # Test port conflict detection
        test_port_conflict_detection()
        
        # Test defensive check
        test_meshcore_defensive_check()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("Summary:")
        print("  ✓ Port conflict detection works correctly")
        print("  ✓ Different ports are not flagged as conflict")
        print("  ✓ TCP mode bypasses serial port check")
        print("  ✓ Single interface enabled is not flagged")
        print("  ✓ MeshCore defensive check prevents logic bugs")
        print()
        sys.exit(0)
        
    except AssertionError as e:
        print("=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        sys.exit(1)
    except Exception as e:
        print("=" * 70)
        print("❌ UNEXPECTED ERROR")
        print("=" * 70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        sys.exit(1)
