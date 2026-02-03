#!/usr/bin/env python3
"""
Diagnostic test to verify MeshCore packet flow with enhanced logging.
"""

import sys
import time
from unittest.mock import Mock, MagicMock

# Mock config
config_mock = MagicMock()
config_mock.DEBUG_MODE = True
config_mock.MESHCORE_ENABLED = True
sys.modules['config'] = config_mock

# Mock globals
import builtins
original_globals = builtins.globals

def mock_globals():
    base_globals = original_globals()
    base_globals.update({
        'MESHCORE_ENABLED': True,
        'MESHTASTIC_ENABLED': False,
        'CONNECTION_MODE': 'serial',
        'DEBUG_MODE': True
    })
    return base_globals

builtins.globals = mock_globals

print("="*70)
print("DIAGNOSTIC TEST: MeshCore Packet Flow with Enhanced Logging")
print("="*70)

# Test 1: Verify callback setup logs
print("\n1️⃣ Testing callback setup logging...")
from meshcore_serial_interface import MeshCoreSerialInterface

# Create a mock serial
mock_serial = Mock()
mock_serial.is_open = True
mock_serial.port = "/dev/ttyUSB0"

# Create interface
interface = MeshCoreSerialInterface("/dev/ttyUSB0")
interface.serial = mock_serial  # Inject mock

# Create a mock callback
def test_callback(packet, iface):
    print(f"   TEST CALLBACK CALLED! packet from 0x{packet.get('from', 0):08x}")

# Set the callback (should trigger diagnostic log)
print("   Setting callback...")
interface.set_message_callback(test_callback)

print("\n2️⃣ Testing message processing with callback invocation...")
# Simulate receiving a DM message
test_line = "DM:12345678:Test message from MeshCore"
print(f"   Processing line: {test_line}")
interface._process_meshcore_line(test_line)

print("\n3️⃣ Testing CLI wrapper callback...")
try:
    from meshcore_cli_wrapper import MeshCoreCLIWrapper
    
    # Create a minimal mock MeshCore object
    mock_meshcore = Mock()
    mock_meshcore.events = Mock()
    mock_meshcore.events.subscribe = Mock()
    
    # Create wrapper
    wrapper = MeshCoreCLIWrapper("/dev/ttyUSB0")
    wrapper.meshcore = mock_meshcore
    
    # Set callback
    print("   Setting CLI wrapper callback...")
    wrapper.set_message_callback(test_callback)
    
    # Simulate an event
    print("   Simulating contact message event...")
    mock_event = Mock()
    mock_event.payload = {
        'contact_id': 0x87654321,
        'text': 'Test CLI message',
        'pubkey_prefix': 'testkey'
    }
    wrapper._on_contact_message(mock_event)
    
except Exception as e:
    print(f"   ⚠️ CLI wrapper test skipped (meshcore-cli not available): {e}")

print("\n" + "="*70)
print("✅ DIAGNOSTIC TEST COMPLETE")
print("="*70)
print("\nExpected logs to see:")
print("  • 📝 Setting message_callback messages")
print("  • 🔍 _process_meshcore_line CALLED")
print("  • 📞 Calling message_callback messages")
print("  • 🔔🔔🔔 _on_contact_message CALLED (for CLI wrapper)")
print("  • TEST CALLBACK CALLED messages")
print("\nThese logs will help identify where packets are being lost.")
