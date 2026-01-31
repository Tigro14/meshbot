#!/usr/bin/env python3
"""
Diagnostic script to test message polling for Meshtastic and MeshCore

This script helps identify which component is failing:
1. Meshtastic pubsub system
2. MeshCore CLI wrapper event loop
3. MeshCore serial interface polling

Usage:
    python3 test_message_polling_diagnostic.py
"""

import sys
import time
import threading
from utils import info_print, error_print, debug_print

def test_meshtastic_pubsub():
    """Test if Meshtastic pub.subscribe works"""
    print("\n" + "="*60)
    print("TEST 1: Meshtastic pub.subscribe System")
    print("="*60)
    
    try:
        # Import dependencies
        from pubsub import pub
        import meshtastic.serial_interface
        from config import MESHTASTIC_ENABLED, CONNECTION_MODE, SERIAL_PORT, TCP_HOST, TCP_PORT
        
        if not MESHTASTIC_ENABLED:
            print("❌ MESHTASTIC_ENABLED=False - Test skipped")
            return False
        
        print(f"✅ Imports successful")
        print(f"   CONNECTION_MODE: {CONNECTION_MODE}")
        
        # Create interface
        if CONNECTION_MODE.lower() == 'tcp':
            print(f"   Creating TCP interface: {TCP_HOST}:{TCP_PORT}")
            interface = meshtastic.tcp_interface.TCPInterface(hostname=TCP_HOST, portNumber=TCP_PORT)
        else:
            print(f"   Creating serial interface: {SERIAL_PORT}")
            interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
        
        print("✅ Interface created")
        
        # Define callback
        messages_received = []
        def on_message(packet, interface):
            print(f"📨 CALLBACK INVOKED! Packet from: 0x{packet.get('from', 0):08x}")
            messages_received.append(packet)
        
        # Subscribe
        pub.subscribe(on_message, "meshtastic.receive")
        print("✅ Subscribed to meshtastic.receive")
        
        # Wait for messages
        print("\n⏳ Waiting 30 seconds for messages...")
        print("   👉 Send a test DM to the bot now!")
        time.sleep(30)
        
        # Results
        print(f"\n📊 Messages received: {len(messages_received)}")
        if len(messages_received) > 0:
            print("✅ pub.subscribe() is WORKING")
            for i, msg in enumerate(messages_received[:3]):
                print(f"   Message {i+1}: from 0x{msg.get('from', 0):08x}")
        else:
            print("❌ No messages received")
            print("   Possible causes:")
            print("   1. No messages sent to the bot")
            print("   2. Meshtastic library not publishing to topic")
            print("   3. Interface not connected properly")
        
        # Cleanup
        interface.close()
        return len(messages_received) > 0
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure Meshtastic library is installed")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_meshcore_cli_wrapper():
    """Test if MeshCore CLI wrapper event loop processes events"""
    print("\n" + "="*60)
    print("TEST 2: MeshCore CLI Wrapper Event Loop")
    print("="*60)
    
    try:
        # Import dependencies
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        from config import MESHCORE_ENABLED, MESHCORE_SERIAL_PORT
        
        if not MESHCORE_ENABLED:
            print("❌ MESHCORE_ENABLED=False - Test skipped")
            return False
        
        print(f"✅ Imports successful")
        print(f"   MESHCORE_SERIAL_PORT: {MESHCORE_SERIAL_PORT}")
        
        # Check if meshcore-cli is available
        try:
            from meshcore import MeshCore, EventType
            print("✅ meshcore-cli library available")
        except ImportError:
            print("❌ meshcore-cli library NOT available")
            print("   This test requires: pip install meshcore")
            return False
        
        # Create interface
        print(f"   Creating MeshCore CLI wrapper...")
        interface = MeshCoreCLIWrapper(MESHCORE_SERIAL_PORT)
        
        if not interface.connect():
            print("❌ Failed to connect")
            return False
        
        print("✅ Interface connected")
        
        # Track callbacks
        messages_received = []
        original_callback = interface._on_contact_message
        
        def tracked_callback(event):
            print(f"📨 _on_contact_message CALLBACK INVOKED!")
            messages_received.append(event)
            original_callback(event)
        
        interface._on_contact_message = tracked_callback
        
        # Start reading
        if not interface.start_reading():
            print("❌ Failed to start reading")
            interface.close()
            return False
        
        print("✅ Reading started")
        
        # Wait for messages
        print("\n⏳ Waiting 30 seconds for messages...")
        print("   👉 Send a test DM to the MeshCore node now!")
        time.sleep(30)
        
        # Results
        print(f"\n📊 Messages received: {len(messages_received)}")
        if len(messages_received) > 0:
            print("✅ Event loop is WORKING - callbacks invoked!")
        else:
            print("❌ No callbacks invoked")
            print("   Possible causes:")
            print("   1. No messages sent to the bot")
            print("   2. Event loop not processing events (fixed in this PR)")
            print("   3. meshcore-cli not dispatching events")
        
        # Cleanup
        interface.close()
        return len(messages_received) > 0
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_meshcore_serial_interface():
    """Test if MeshCore serial interface polls for messages"""
    print("\n" + "="*60)
    print("TEST 3: MeshCore Serial Interface Polling")
    print("="*60)
    
    try:
        # Import dependencies
        from meshcore_serial_interface import MeshCoreSerialInterface
        from config import MESHCORE_ENABLED, MESHCORE_SERIAL_PORT
        
        if not MESHCORE_ENABLED:
            print("❌ MESHCORE_ENABLED=False - Test skipped")
            return False
        
        print(f"✅ Imports successful")
        print(f"   MESHCORE_SERIAL_PORT: {MESHCORE_SERIAL_PORT}")
        
        # Create interface
        print(f"   Creating MeshCore serial interface...")
        interface = MeshCoreSerialInterface(MESHCORE_SERIAL_PORT)
        
        if not interface.connect():
            print("❌ Failed to connect")
            return False
        
        print("✅ Interface connected")
        
        # Track callbacks
        messages_received = []
        original_callback = interface._process_meshcore_line
        
        def tracked_callback(line):
            if line.startswith("DM:"):
                print(f"📨 Message parsed: {line[:50]}")
                messages_received.append(line)
            original_callback(line)
        
        interface._process_meshcore_line = tracked_callback
        
        # Start reading
        if not interface.start_reading():
            print("❌ Failed to start reading")
            interface.close()
            return False
        
        print("✅ Reading started (both read and poll threads)")
        
        # Check if polling thread is running
        time.sleep(1)
        if interface.poll_thread and interface.poll_thread.is_alive():
            print("✅ Poll thread is running")
        else:
            print("❌ Poll thread NOT running")
        
        # Wait for messages and polling
        print("\n⏳ Waiting 30 seconds for messages and polling...")
        print("   👉 Send a test DM to the MeshCore node now!")
        print("   👉 Watch for 'MESHCORE-POLL' messages in logs")
        time.sleep(30)
        
        # Results
        print(f"\n📊 Messages received: {len(messages_received)}")
        if len(messages_received) > 0:
            print("✅ Polling is WORKING - messages received!")
            for i, msg in enumerate(messages_received[:3]):
                print(f"   Message {i+1}: {msg[:70]}")
        else:
            print("❌ No messages received")
            print("   Possible causes:")
            print("   1. No messages sent to the bot")
            print("   2. MeshCore device not responding to SYNC_NEXT")
            print("   3. Protocol mismatch (expecting text format)")
        
        # Cleanup
        interface.close()
        return len(messages_received) > 0
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all diagnostic tests"""
    print("\n" + "="*60)
    print("MESSAGE POLLING DIAGNOSTIC TEST SUITE")
    print("="*60)
    print("\nThis script tests the message polling fixes for:")
    print("  1. Meshtastic pub.subscribe system")
    print("  2. MeshCore CLI wrapper event loop")
    print("  3. MeshCore serial interface polling")
    print("\nDuring the tests, please send test DMs to the bot.")
    print("="*60)
    
    results = {
        'meshtastic': test_meshtastic_pubsub(),
        'meshcore_cli': test_meshcore_cli_wrapper(),
        'meshcore_serial': test_meshcore_serial_interface(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name:20s}: {status}")
    
    print("\n" + "="*60)
    
    if all(results.values()):
        print("✅ All tests PASSED!")
        return 0
    else:
        print("❌ Some tests FAILED")
        print("\nPlease check:")
        print("  1. Configuration (config.py)")
        print("  2. Hardware connections")
        print("  3. Test messages were actually sent")
        return 1


if __name__ == '__main__':
    sys.exit(main())
