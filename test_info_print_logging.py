#!/usr/bin/env python3
"""
Test to verify MeshCore packets are logged with info_print (ALWAYS visible).
This test simulates the full packet flow and verifies logs appear WITHOUT DEBUG_MODE.
"""

import sys
import time
from unittest.mock import Mock, MagicMock, patch
from io import StringIO

# Mock config WITHOUT DEBUG_MODE
config_mock = MagicMock()
config_mock.DEBUG_MODE = False  # CRITICAL: Test without DEBUG mode
config_mock.MESHCORE_ENABLED = True
sys.modules['config'] = config_mock

print("="*70)
print("TEST: MeshCore Packets Logged Without DEBUG_MODE")
print("="*70)
print(f"DEBUG_MODE = {config_mock.DEBUG_MODE} (should be False)")
print()

# Capture stdout to check what gets logged
captured_output = StringIO()

# Import after config is mocked
from traffic_monitor import TrafficMonitor
from meshcore_serial_interface import MeshCoreSerialInterface

print("1️⃣ Testing TrafficMonitor packet logging WITHOUT DEBUG_MODE...")
print()

# Create traffic monitor
node_manager_mock = Mock()
node_manager_mock.get_node_name = Mock(return_value="TestNode")

monitor = TrafficMonitor(node_manager=node_manager_mock)

# Mock the persistence
monitor.persistence.save_meshcore_packet = Mock()
monitor.persistence.save_packet = Mock()

# Create a test MeshCore packet with all required fields
test_packet = {
    'from': 0x12345678,
    'to': 0x87654321,
    'id': 865992,
    'rxTime': int(time.time()),
    'rssi': 0,
    'snr': 0.0,
    'hopLimit': 0,
    'hopStart': 0,
    'channel': 0,
    'decoded': {
        'portnum': 'TEXT_MESSAGE_APP',
        'payload': b'Test MeshCore message'
    }
}

# Add packet with source='meshcore'
print("Adding MeshCore packet to traffic monitor...")
monitor.add_packet(test_packet, source='meshcore')
print()

# Check what was logged
print("✅ Test completed!")
print()
print("Expected logs (should appear ABOVE without DEBUG_MODE):")
print("  • 📊 Paquet enregistré ([meshcore]): TEXT_MESSAGE_APP de TestNode")
print("  • 📦 TEXT_MESSAGE_APP de TestNode <id> [direct] (SNR:n/a)")
print()

print("2️⃣ Testing MeshCore serial interface message reception...")
print()

# Create serial interface
interface = MeshCoreSerialInterface("/dev/ttyUSB0")
interface.serial = Mock()
interface.serial.is_open = True

# Mock callback
def test_callback(packet, iface):
    print(f"   ✓ Callback called with packet from 0x{packet.get('from', 0):08x}")

interface.set_message_callback(test_callback)

# Simulate receiving a message
test_line = "DM:87654321:Hello from MeshCore"
print(f"Processing line: {test_line}")
interface._process_meshcore_line(test_line)
print()

print("Expected logs (should appear ABOVE without DEBUG_MODE):")
print("  • 🔍 [MESHCORE-SERIAL] _process_meshcore_line CALLED with: <line>")
print("  • 📬 [MESHCORE-DM] De: 0x87654321 | Message: Hello from MeshCore")
print("  • 📞 [MESHCORE-TEXT] Calling message_callback for message from 0x87654321")
print("  • ✅ [MESHCORE-TEXT] Callback completed successfully")
print()

print("="*70)
print("✅ TEST COMPLETE")
print("="*70)
print()
print("VERIFICATION:")
print("-------------")
print("1. All logs above should be visible WITHOUT DEBUG_MODE")
print("2. Look for 📊, 📦, 📨, 🔍, 📞 emoji indicators")
print("3. These use info_print() so they're ALWAYS visible")
print()
print("If logs are NOT visible:")
print("  → Bug: Still using debug_print() instead of info_print()")
print("  → Fix: Change critical logs to info_print()")
print()
print("If logs ARE visible:")
print("  → SUCCESS: MeshCore packets will now appear in production logs")
