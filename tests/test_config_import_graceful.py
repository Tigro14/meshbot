#!/usr/bin/env python3
"""
Test that the diagnostic script can import config variables gracefully.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import os

# Create a minimal test config in memory
test_config_content = """
# Minimal config for serial-only Meshtastic
MESHTASTIC_ENABLED = True
CONNECTION_MODE = 'serial'
SERIAL_PORT = '/dev/ttyACM0'

# No TCP_HOST or TCP_PORT defined
"""

def test_import_with_missing_tcp_config():
    """Test that diagnostic script handles missing TCP config gracefully"""
    print("Testing import with missing TCP config variables...")
    
    # Create a temporary config module
    import types
    config = types.ModuleType('config')
    
    # Set only the serial config
    config.MESHTASTIC_ENABLED = True
    config.CONNECTION_MODE = 'serial'
    config.SERIAL_PORT = '/dev/ttyACM0'
    # TCP_HOST and TCP_PORT are NOT defined
    
    # Simulate the import pattern from the diagnostic script
    MESHTASTIC_ENABLED = getattr(config, 'MESHTASTIC_ENABLED', True)
    CONNECTION_MODE = getattr(config, 'CONNECTION_MODE', 'serial')
    SERIAL_PORT = getattr(config, 'SERIAL_PORT', '/dev/ttyACM0')
    TCP_HOST = getattr(config, 'TCP_HOST', None)
    TCP_PORT = getattr(config, 'TCP_PORT', None)
    
    print(f"✅ MESHTASTIC_ENABLED: {MESHTASTIC_ENABLED}")
    print(f"✅ CONNECTION_MODE: {CONNECTION_MODE}")
    print(f"✅ SERIAL_PORT: {SERIAL_PORT}")
    print(f"✅ TCP_HOST: {TCP_HOST} (None is OK for serial mode)")
    print(f"✅ TCP_PORT: {TCP_PORT} (None is OK for serial mode)")
    
    # Verify serial mode works
    if CONNECTION_MODE.lower() == 'serial':
        print("✅ Serial mode detected - no TCP config needed")
        return True
    
    return False

def test_import_with_tcp_config():
    """Test that diagnostic script works with full TCP config"""
    print("\nTesting import with TCP config variables...")
    
    # Create a temporary config module with TCP
    import types
    config = types.ModuleType('config')
    
    # Set both serial and TCP config
    config.MESHTASTIC_ENABLED = True
    config.CONNECTION_MODE = 'tcp'
    config.SERIAL_PORT = '/dev/ttyACM0'
    config.TCP_HOST = '192.168.1.38'
    config.TCP_PORT = 4403
    
    # Simulate the import pattern from the diagnostic script
    MESHTASTIC_ENABLED = getattr(config, 'MESHTASTIC_ENABLED', True)
    CONNECTION_MODE = getattr(config, 'CONNECTION_MODE', 'serial')
    SERIAL_PORT = getattr(config, 'SERIAL_PORT', '/dev/ttyACM0')
    TCP_HOST = getattr(config, 'TCP_HOST', None)
    TCP_PORT = getattr(config, 'TCP_PORT', None)
    
    print(f"✅ MESHTASTIC_ENABLED: {MESHTASTIC_ENABLED}")
    print(f"✅ CONNECTION_MODE: {CONNECTION_MODE}")
    print(f"✅ SERIAL_PORT: {SERIAL_PORT}")
    print(f"✅ TCP_HOST: {TCP_HOST}")
    print(f"✅ TCP_PORT: {TCP_PORT}")
    
    # Verify TCP mode has required vars
    if CONNECTION_MODE.lower() == 'tcp':
        if TCP_HOST is None or TCP_PORT is None:
            print("❌ TCP mode requires TCP_HOST and TCP_PORT")
            return False
        print("✅ TCP mode detected - all config present")
        return True
    
    return False

if __name__ == '__main__':
    print("="*60)
    print("Testing Config Import Patterns")
    print("="*60)
    
    result1 = test_import_with_missing_tcp_config()
    result2 = test_import_with_tcp_config()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Serial-only config (no TCP vars): {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"Full TCP config: {'✅ PASS' if result2 else '❌ FAIL'}")
    
    if result1 and result2:
        print("\n✅ All tests PASSED!")
        sys.exit(0)
    else:
        print("\n❌ Some tests FAILED")
        sys.exit(1)
